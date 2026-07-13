"""Zones (SPEC.md "Engine definitions (v0 pins)" -> "Zones"): FVG / IFVG /
OrderBlock / Breaker lifecycles, all driven by a single `ZonesEngine`.

Dependency wiring: `ZonesEngine` drives PRIVATE internal `StructureEngine`
and `DisplacementEngine` instances and consumes only ITS OWN copies of their
emitted events for the same bar -- mirrors WP-B's established "no cross-
engine state sharing" convention (`core/runner.py`'s BatchRunner docstring;
`structure.py`'s own private `SwingMethodA`), same pattern `sweeps.py` (WP-C)
uses for its private `LevelRegistry`.

FVG -- mirrors the frozen oracle's `primitives.py::fvgs()` triple-candle
test EXACTLY: candle A = bar two back, candle B = bar one back ("origin"),
candle C = the bar just closed (confirms the gap). Bullish iff `A.high <
C.low` (zone `[A.high, C.low]`); bearish iff `A.low > C.high` (zone
`[C.high, A.low]`) -- verified bit-for-bit vs the oracle in `tests/test_
zones.py::test_fvg_matches_oracle_fvgs`. min-size (`fvg_min_ticks`, v0=4) is
NEVER a filter: EVERY 3-candle gap is emitted as `FVG_CREATED` (this is the
UNFILTERED stream the oracle-equivalence test compares against), carrying
`size_ticks`/`qualifies_min_size`; a SEPARATE `FVG_QUALIFIED` event
(`source_event_ids` -> the `FVG_CREATED`) fires additionally only when the
gap clears the threshold.

IFVG -- created ONLY as a direct side effect of an `FVG_INVALIDATED` event
(never independently detected): same box `[zone_low, zone_high]`, polarity
flipped (an invalidated bullish FVG becomes a bearish IFVG and vice versa),
`source_event_ids` -> the `FVG_INVALIDATED` event (not the original `FVG_
CREATED`). Own lifecycle (`IFVG_CREATED/TESTED/INVALIDATED/EXPIRED`).

OrderBlock -- fires on a `BOS` or `MSS` event from the private `StructureEngine`
THAT COINCIDES (same bar) WITH a `DISPLACEMENT_QUALIFIED` event of the SAME
direction from the private `DisplacementEngine` (documented interpretive
reading of SPEC.md's "on DISPLACEMENT_QUALIFIED ... coinciding with/preceding
a structure break": MSS in `structure.py` already only ever confirms on a
bar that independently satisfies the identical displacement-qualification
formula, so an MSS bar is BY CONSTRUCTION always coincident with a real
DISPLACEMENT_QUALIFIED bar; BOS carries no such built-in guarantee, so it is
additionally gated on a same-bar DISPLACEMENT_QUALIFIED here. Bare `CHOCH` is
deliberately EXCLUDED -- `structure.py`'s own docstring: "CHoCH is not an
auto-reversal", i.e. not yet a confirmed structure break. Flagged here for
Fable's review, same class of judgment call as WP-B's own documented
interpretive calls -- non-blocking.). On a qualifying bar, scans back <=
`orderblock_scan_back_bars` (10) prior bars, NEAREST FIRST, for the last
"opposing" candle (opposite color to the break direction -- mirrors
`model01_sweep_mss_fvg.py::_detect`'s own order-block scan, `for j in
range(mss_bar, i-1, -1): if d>0 and c[j]<o[j]: ob=j`); if none is found
within the window, nothing is emitted (there is no candidate object to
report, same "nothing observed" logic `opening_range.py` uses for a total
data gap -- not a suppressed candidate). `origin=that candle`, `created_at =
confirmed_at` of the qualifying BOS/MSS event (structurally, by construction,
always the SAME bar as the candle scan, so `first_eligible_retest_at =
next_actionable(created_at) > created_at` holds automatically). zone = full
candle range (`orderblock_zone_mode` v0="full_candle"; "body" = alt param).
`impulse_id` = the qualifying BOS/MSS event's own `event_id`.

Breaker -- created ONLY as a direct side effect of an `OB_INVALIDATED` event:
same box, polarity flipped, `impulse_id` carried through from the source OB
(so all zones descended from one qualifying impulse share it, per SPEC.md).

Shared lifecycle (ALL FOUR kinds): `<KIND>_CREATED -> zero or more <KIND>_
TESTED -> exactly one of <KIND>_INVALIDATED | <KIND>_EXPIRED` (every zone
reaches a terminal event, EXPIRED at latest -- SPEC.md's zone hard rule).
TESTED = a later bar's `[low, high]` overlaps the zone. INVALIDATED = a
later bar's CLOSE crosses the zone's far boundary relative to its polarity
(bullish zone: close < zone_low; bearish zone: close > zone_high) -- SPEC.md
only states this expiry/invalidation convention for FVG explicitly; it is
applied UNIFORMLY to IFVG/OB/Breaker here too (SPEC.md's blanket "every zone
reaches a terminal event" requirement needs SOME rule for all four, and this
is the only one SPEC.md gives -- documented extension, non-blocking). Expiry
(`fvg_expiry_mode` v0="full_session": end of the CURRENT/next PRIMARY_ORDER
session slot after creation, via `_util.advance_sessions`; alt "bars" mode:
`fvg_expiry_bars` completed bars after creation) is likewise applied
uniformly to all four kinds. No zone is tested/invalidated/expired on its
own creation bar (`first_eligible_retest_at = next_actionable(created_at,
timeframe)`, enforced structurally: newly-created zones are appended to the
active set AFTER this bar's lifecycle pass, so the earliest a zone can be
advanced is the bar strictly after it was created).
"""
from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, List, Optional

from ..core.clock import SessionEngine
from ..core.config import ICT_V2_PARAMS_V0, ParamSet
from ..core.events import CausalEvent, compute_event_id
from ._util import advance_sessions, bar_duration, next_actionable
from .displacement import DisplacementEngine
from .structure import StructureEngine

RULE_VERSION = "ZONES_V0"

_EVENT_PREFIX = {"fvg": "FVG", "ifvg": "IFVG", "ob": "OB", "breaker": "BREAKER"}


def fvg_from_triple(bar_a: Any, bar_c: Any) -> Optional[dict]:
    """Pure FVG math, mirrors `primitives.py::fvgs()`'s per-triple test
    exactly (bull: `c1.high < c3.low`; bear: `c1.low > c3.high`). Exposed as
    a standalone function so the oracle-equivalence test can exercise it in
    isolation."""
    if bar_a.high < bar_c.low:
        return {"direction": "bullish", "top": bar_c.low, "bottom": bar_a.high}
    if bar_a.low > bar_c.high:
        return {"direction": "bearish", "top": bar_a.low, "bottom": bar_c.high}
    return None


class _ZoneState:
    __slots__ = (
        "kind", "direction", "zone_low", "zone_high", "created_event_id",
        "created_at", "expires_at", "first_eligible_retest_at", "test_count",
        "impulse_id", "terminal",
    )

    def __init__(self, kind, direction, zone_low, zone_high, created_event_id, created_at, expires_at, impulse_id, timeframe):
        self.kind = kind
        self.direction = direction
        self.zone_low = zone_low
        self.zone_high = zone_high
        self.created_event_id = created_event_id
        self.created_at = created_at
        self.expires_at = expires_at
        self.first_eligible_retest_at = next_actionable(created_at, timeframe)
        self.test_count = 0
        self.impulse_id = impulse_id
        self.terminal = False


class ZonesEngine:
    def __init__(
        self,
        instrument: str = "NQ",
        timeframe: str = "5m",
        params: ParamSet = ICT_V2_PARAMS_V0,
    ) -> None:
        self.instrument = instrument
        self.timeframe = timeframe
        self.params = params
        self._sessions = SessionEngine()
        self._structure = StructureEngine(instrument, timeframe, params)
        self._displacement = DisplacementEngine(instrument, timeframe, params)
        self._bar_buf: Deque[Any] = deque(maxlen=max(3, params.orderblock_scan_back_bars + 1))
        self._active: Dict[str, _ZoneState] = {}

    # -- event construction ---------------------------------------------------

    def _event(
        self, event_type: str, origin_time, confirmed_at, price_low, price_high,
        discriminator: str, attributes: dict, source_event_ids: tuple,
    ) -> CausalEvent:
        eid = compute_event_id(event_type, self.instrument, origin_time, RULE_VERSION, discriminator=discriminator)
        return CausalEvent(
            event_id=eid,
            event_type=event_type,
            instrument=self.instrument,
            timeframe=self.timeframe,
            origin_time=origin_time,
            observed_at=confirmed_at,
            confirmed_at=confirmed_at,
            actionable_at=next_actionable(confirmed_at, self.timeframe),
            rule_version=RULE_VERSION,
            param_version=self.params.param_version,
            price_low=price_low,
            price_high=price_high,
            source_event_ids=source_event_ids,
            attributes=attributes,
        )

    def _expires_at(self, created_at):
        mode = self.params.fvg_expiry_mode
        if mode == "full_session":
            return advance_sessions(self._sessions, created_at, 1)
        if mode == "bars":
            return created_at + bar_duration(self.timeframe) * self.params.fvg_expiry_bars
        raise ValueError(f"unknown fvg_expiry_mode {mode!r}")

    def _register(self, kind: str, direction: str, zlo: float, zhi: float, created_event: CausalEvent, impulse_id: Optional[str]) -> None:
        expires_at = self._expires_at(created_event.confirmed_at)
        self._active[created_event.event_id] = _ZoneState(
            kind, direction, zlo, zhi, created_event.event_id, created_event.confirmed_at,
            expires_at, impulse_id, self.timeframe,
        )

    # -- FVG detection ----------------------------------------------------------

    def _impulse_id(self, direction: str, structure_events: List[CausalEvent], displacement_events: List[CausalEvent]) -> Optional[str]:
        for ev in displacement_events:
            if ev.event_type == "DISPLACEMENT_QUALIFIED" and ev.attributes.get("direction") == direction:
                return ev.event_id
        for ev in structure_events:
            if ev.event_type in ("BOS", "MSS") and ev.attributes.get("direction") == direction:
                return ev.event_id
        return None

    def _detect_fvg(self, bar: Any, structure_events: List[CausalEvent], displacement_events: List[CausalEvent]) -> List[CausalEvent]:
        if len(self._bar_buf) < 3:
            return []
        bar_a, bar_b, bar_c = list(self._bar_buf)[-3:]
        gap = fvg_from_triple(bar_a, bar_c)
        if gap is None:
            return []
        events: List[CausalEvent] = []
        tick = self.params.tick_size
        size_pts = gap["top"] - gap["bottom"]
        size_ticks = size_pts / tick
        qualifies = size_ticks >= self.params.fvg_min_ticks
        impulse_id = self._impulse_id(gap["direction"], structure_events, displacement_events)
        disc = f"fvg|{gap['direction']}|{bar_b.close_time.isoformat()}|{bar_c.close_time.isoformat()}"
        created = self._event(
            "FVG_CREATED", bar_b.close_time, bar_c.close_time, gap["bottom"], gap["top"], disc,
            attributes={
                "direction": gap["direction"], "size_pts": size_pts, "size_ticks": size_ticks,
                "qualifies_min_size": qualifies, "min_ticks": self.params.fvg_min_ticks,
                "impulse_id": impulse_id,
            },
            source_event_ids=(),
        )
        events.append(created)
        self._register("fvg", gap["direction"], gap["bottom"], gap["top"], created, impulse_id)
        if qualifies:
            events.append(
                self._event(
                    "FVG_QUALIFIED", bar_b.close_time, bar_c.close_time, gap["bottom"], gap["top"],
                    disc, attributes={"direction": gap["direction"], "size_ticks": size_ticks},
                    source_event_ids=(created.event_id,),
                )
            )
        return events

    # -- OrderBlock detection -----------------------------------------------------

    def _detect_orderblock(self, bar: Any, structure_events: List[CausalEvent], displacement_events: List[CausalEvent]) -> List[CausalEvent]:
        events: List[CausalEvent] = []
        for sev in structure_events:
            if sev.event_type not in ("BOS", "MSS"):
                continue
            direction = sev.attributes.get("direction")
            disp_match = next(
                (d for d in displacement_events if d.event_type == "DISPLACEMENT_QUALIFIED" and d.attributes.get("direction") == direction),
                None,
            )
            if disp_match is None:
                continue
            history = list(self._bar_buf)[: -1]  # every bar strictly before the current one
            scan_window = history[-self.params.orderblock_scan_back_bars:]
            opposing = None
            for cand in reversed(scan_window):  # nearest-first
                if direction == "bullish" and cand.close < cand.open:
                    opposing = cand
                    break
                if direction == "bearish" and cand.close > cand.open:
                    opposing = cand
                    break
            if opposing is None:
                continue
            events.append(self._create_ob(sev, disp_match, opposing, direction))
        return events

    def _create_ob(self, structure_event: CausalEvent, disp_event: CausalEvent, opposing_bar: Any, direction: str) -> CausalEvent:
        if self.params.orderblock_zone_mode == "full_candle":
            zlo, zhi = opposing_bar.low, opposing_bar.high
        elif self.params.orderblock_zone_mode == "body":
            zlo, zhi = min(opposing_bar.open, opposing_bar.close), max(opposing_bar.open, opposing_bar.close)
        else:
            raise ValueError(f"unknown orderblock_zone_mode {self.params.orderblock_zone_mode!r}")
        created_at = structure_event.confirmed_at
        # impulse_id = the coincident DISPLACEMENT_QUALIFIED event's own id -- SAME
        # priority `_impulse_id()` uses for FVG, so an FVG and an OB born of the same
        # bar+direction share one impulse_id (SPEC.md's "zones from one qualifying
        # impulse share an impulse_id" requirement).
        impulse_id = disp_event.event_id
        disc = f"ob|{direction}|{structure_event.event_id}|{opposing_bar.close_time.isoformat()}"
        ev = self._event(
            "OB_CREATED", opposing_bar.close_time, created_at, zlo, zhi, disc,
            attributes={
                "direction": direction, "structure_event_type": structure_event.event_type,
                "zone_mode": self.params.orderblock_zone_mode, "impulse_id": impulse_id,
            },
            source_event_ids=(structure_event.event_id, disp_event.event_id),
        )
        self._register("ob", direction, zlo, zhi, ev, impulse_id)
        return ev

    # -- IFVG / Breaker: spawned ONLY from an invalidation ---------------------------

    def _spawn_flip(self, source_kind: str, target_kind: str, zone: _ZoneState, inv_event: CausalEvent, bar: Any) -> CausalEvent:
        flipped_direction = "bearish" if zone.direction == "bullish" else "bullish"
        disc = f"{target_kind}|{inv_event.event_id}"
        ev = self._event(
            f"{_EVENT_PREFIX[target_kind]}_CREATED", bar.close_time, bar.close_time, zone.zone_low, zone.zone_high, disc,
            attributes={
                "direction": flipped_direction, "impulse_id": zone.impulse_id,
                f"source_{source_kind}_id": zone.created_event_id,
            },
            source_event_ids=(inv_event.event_id,),
        )
        self._register(target_kind, flipped_direction, zone.zone_low, zone.zone_high, ev, zone.impulse_id)
        return ev

    # -- lifecycle: test / invalidate / expire every active zone --------------------

    def _advance_zones(self, bar: Any) -> List[CausalEvent]:
        events: List[CausalEvent] = []
        for zone in list(self._active.values()):
            if zone.terminal or bar.close_time < zone.first_eligible_retest_at:
                continue
            touched = bar.low <= zone.zone_high and bar.high >= zone.zone_low
            if touched:
                zone.test_count += 1
                disc = f"{zone.created_event_id}|tested|{bar.close_time.isoformat()}"
                events.append(
                    self._event(
                        f"{_EVENT_PREFIX[zone.kind]}_TESTED", bar.close_time, bar.close_time, zone.zone_low, zone.zone_high,
                        disc, attributes={"direction": zone.direction, "test_count": zone.test_count, "impulse_id": zone.impulse_id},
                        source_event_ids=(zone.created_event_id,),
                    )
                )
            invalidated = (bar.close < zone.zone_low) if zone.direction == "bullish" else (bar.close > zone.zone_high)
            if invalidated:
                zone.terminal = True
                disc = f"{zone.created_event_id}|invalidated|{bar.close_time.isoformat()}"
                inv_ev = self._event(
                    f"{_EVENT_PREFIX[zone.kind]}_INVALIDATED", bar.close_time, bar.close_time, zone.zone_low, zone.zone_high,
                    disc, attributes={"direction": zone.direction, "test_count": zone.test_count, "impulse_id": zone.impulse_id},
                    source_event_ids=(zone.created_event_id,),
                )
                events.append(inv_ev)
                if zone.kind == "fvg":
                    events.append(self._spawn_flip("fvg", "ifvg", zone, inv_ev, bar))
                elif zone.kind == "ob":
                    events.append(self._spawn_flip("ob", "breaker", zone, inv_ev, bar))
                continue
            if bar.close_time >= zone.expires_at:
                zone.terminal = True
                disc = f"{zone.created_event_id}|expired|{bar.close_time.isoformat()}"
                events.append(
                    self._event(
                        f"{_EVENT_PREFIX[zone.kind]}_EXPIRED", bar.close_time, bar.close_time, zone.zone_low, zone.zone_high,
                        disc, attributes={"direction": zone.direction, "test_count": zone.test_count, "impulse_id": zone.impulse_id},
                        source_event_ids=(zone.created_event_id,),
                    )
                )
        return events

    # -- main loop ------------------------------------------------------------

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        structure_events = self._structure.on_bar(bar)
        displacement_events = self._displacement.on_bar(bar)
        events: List[CausalEvent] = []
        events.extend(self._advance_zones(bar))  # nothing created THIS bar is advanced (see module docstring)
        self._bar_buf.append(bar)
        events.extend(self._detect_fvg(bar, structure_events, displacement_events))
        events.extend(self._detect_orderblock(bar, structure_events, displacement_events))
        return events
