"""Sweep FSM (SPEC.md "Engine definitions (v0 pins)" -> "Sweep FSM"): per
active level, a small state machine decides whether a liquidity excursion
resolves as a genuine sweep (wick beyond, close back inside), gets accepted
as a real breakout, or times out ambiguously.

Level wiring: `SweepEngine` drives a PRIVATE internal `LevelRegistry`
instance and consumes its own emitted `LEVEL_CREATED`/`LEVEL_EXPIRED` events
to build its level book -- this MIRRORS how WP-B already wires cross-engine
dependencies (`structure.py`'s private `SwingMethodA`, `levels.py`'s own
private `SwingMethodA`): `core/runner.py`'s BatchRunner explicitly states
"engines never share state or read each other's events", so every engine
that needs another detector's output drives its own private copy of that
detector rather than reading from an external store.

Level "side" (which direction constitutes "beyond" a level -- SPEC.md's FSM
prose is level-direction-agnostic, but a level object needs a side to know
which excursion direction is the liquidity-grab direction): `kind`s that are
inherently a HIGH (pdh, pwh, session_high, or_high, overnight_high,
swing_high_a, equal_highs) get side="buy" (buy-side liquidity resting above
price -- excursion = trade goes ABOVE the level, reclaim = close back
BELOW). `kind`s that are inherently a LOW get side="sell" (mirror image).
`round_number_major`/`round_number_minor` are ambidextrous (a round number
sits neither above nor below price by construction) -- BOTH sides are
tracked independently as separate episodes for these two kinds only. This
side-mapping is a documented engineering decision (SPEC.md doesn't spell it
out explicitly) flagged here for Fable's review, same class of judgment call
as WP-B's STRUCTURE_INITIALIZED bootstrap event / MSS-window interpretation.

FSM per (level, side) "episode" -- ALL bar-index counting is 1-based from
the excursion-open bar itself (bar 1), matching the frozen oracle's own
window convention (`primitives.py::sweep_of_level`'s `for j in range(i, i +
max_bars)` -- the loop starts AT the breach bar `i`, so the breach bar's own
close is already checked for reclaim):

  * EXCURSION_OPEN fires the instant a bar's wick trades >=1 tick beyond the
    level (SPEC.md's literal "trade >=1 tick beyond level" -- uses `>=`;
    NOTE this is a small, documented divergence from the oracle's strict
    `>` at the identical threshold `level +/- tick`, e.g.
    `primitives.py::sweep_of_level`'s `h[i] > level + tick`. SPEC.md's own
    engine-definition prose governs the OPEN trigger; the oracle is mirrored
    exactly for the RECLAIM comparison instead -- see below and
    `tests/test_sweeps.py::test_sweep_confirmed_matches_oracle_sweep_of_level`).

  * Each subsequent bar (including the open bar itself, per the oracle's
    `j` starting at `i`) is classified, using the SAME strict comparison
    the oracle uses for reclaim (`c[j] > level` / `c[j] < level`):
      - RECLAIMED   (close strictly back inside)      -> mirrors oracle exactly
      - STILL_BEYOND (close strictly still beyond)
      - BOUNDARY TIE (close == level exactly)          -> neither of the above
    Priority per bar, `h` = `sweep_h_default` (param family {1,3,6}):
      1. `bars_elapsed > h` (past the patience window with nothing resolved
         inside it) -> `ACCEPTED_BREAKOUT` unconditionally (this is the
         "dwell > h bars" clause of SPEC.md's FSM prose, as a GRACE bar: the
         engine grants exactly one bar past the window before forcing this
         outcome -- see the resolution note below).
      2. RECLAIMED and `bars_elapsed <= h` -> `SWEEP_CONFIRMED` (SPEC.md's
         "close back inside" clause; `reclaim_speed_bars = bars_elapsed`).
      3. STILL_BEYOND -> increment the running `consecutive_beyond` streak
         (a BOUNDARY TIE resets it to 0); `consecutive_beyond >= 2` ->
         `ACCEPTED_BREAKOUT` (SPEC.md's "2 consecutive closes beyond"
         clause), at ANY bar, not only at the window edge.
      4. Otherwise, if this is the window's LAST bar (`bars_elapsed == h`)
         and it was a BOUNDARY TIE -> `EXCURSION_TIMEOUT` (the window closed
         on a genuinely ambiguous bar -- neither a clean reclaim nor a clean
         continuation was ever observed).
      5. Otherwise: keep waiting (this only happens at `bars_elapsed == h`
         when the final bar was STILL_BEYOND but the streak had been reset
         by an earlier boundary tie, so `consecutive_beyond` is still < 2 --
         the engine grants exactly one grace bar, resolved by rule 1 above).

    RESOLUTION NOTE (documented interpretive call, non-blocking -- SPEC.md's
    prose "2 consecutive closes beyond OR dwell > h bars -> ACCEPTED_
    BREAKOUT; else EXCURSION_TIMEOUT" is under-specified about how these
    three outcomes are meant to be mutually exclusive: taken maximally
    literally, "dwell > h" and "2 consecutive" together with strict binary
    reclaim/still-beyond classification make EXCURSION_TIMEOUT structurally
    UNREACHABLE for `h >= 2` (2 consecutive closes-beyond always resolves by
    bar 2), which would fail SPEC.md's own "full lifecycle walk incl. every
    failure/timeout branch" test requirement. Introducing the BOUNDARY-TIE
    case (`close == level` exactly, a real, non-contrived possibility on a
    tick-quantized price grid revisiting a tick-quantized level) makes all
    three outcomes independently and non-degenerately reachable for every
    `h` in the param family, including the v0 default `h=3` -- see
    `tests/test_sweeps.py` for one hand-built walk per terminal outcome.

  * ALL THREE terminal events carry: `excursion_depth_ticks` (the deepest
    wick excursion beyond the level observed over the whole episode, in
    ticks), `duration_bars` (`bars_elapsed` at termination), `reclaim_speed_
    bars` (== `duration_bars` for `SWEEP_CONFIRMED`, `None` otherwise),
    `level_id` (the originating `LEVEL_CREATED` event_id, also in
    `source_event_ids`), and a flat snapshot of the level's salience
    components as of excursion-open time (`level_timeframe_class`, `level_
    prominence_above_pts`, `level_prominence_below_pts`, `level_roundness_
    major`, `level_roundness_minor`, `level_equality_count` -- same flat-
    attribute convention `levels.py` itself uses for `LEVEL_CREATED`, not
    nested).

  * A level already flagged `LEVEL_EXPIRED` by the internal registry cannot
    OPEN a new episode, but an episode already open when its level expires
    is allowed to run to its own natural terminal outcome (mirrors `levels.
    py`'s own "no level is tested strictly after its own expiry" guarantee
    for NEW candidates, without inventing a 4th "expired mid-sweep" outcome
    SPEC.md doesn't name).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..core.config import ICT_V2_PARAMS_V0, ParamSet
from ..core.events import CausalEvent, compute_event_id
from ._util import next_actionable
from .levels import LevelRegistry

RULE_VERSION = "SWEEPS_V0"

_HIGH_KINDS = {"pdh", "pwh", "session_high", "or_high", "overnight_high", "swing_high_a", "equal_highs"}
_LOW_KINDS = {"pdl", "pwl", "session_low", "or_low", "overnight_low", "swing_low_a", "equal_lows"}
_AMBIDEXTROUS_KINDS = {"round_number_major", "round_number_minor"}

_SALIENCE_KEYS = (
    "timeframe_class", "prominence_above_pts", "prominence_below_pts",
    "roundness_major", "roundness_minor", "equality_count",
)


def _sides_for_kind(kind: str) -> Tuple[str, ...]:
    if kind in _HIGH_KINDS:
        return ("buy",)
    if kind in _LOW_KINDS:
        return ("sell",)
    if kind in _AMBIDEXTROUS_KINDS:
        return ("buy", "sell")
    raise ValueError(f"sweeps.py: unmapped level kind {kind!r}; add it to a side set")


class _Episode:
    __slots__ = (
        "open_event_id", "level_id", "side", "level_kind", "level_price",
        "salience", "bars_elapsed", "consecutive_beyond", "extreme_price",
        "open_origin_time",
    )

    def __init__(self, open_event_id, level_id, side, level_kind, level_price, salience, open_origin_time):
        self.open_event_id = open_event_id
        self.level_id = level_id
        self.side = side
        self.level_kind = level_kind
        self.level_price = level_price
        self.salience = salience
        self.bars_elapsed = 0
        self.consecutive_beyond = 0
        self.extreme_price = level_price
        self.open_origin_time = open_origin_time


class SweepEngine:
    def __init__(
        self,
        instrument: str = "NQ",
        timeframe: str = "5m",
        params: ParamSet = ICT_V2_PARAMS_V0,
        h_bars: Optional[int] = None,
    ) -> None:
        self.instrument = instrument
        self.timeframe = timeframe
        self.params = params
        self.h_bars = h_bars if h_bars is not None else params.sweep_h_default
        if self.h_bars not in params.sweep_h_bars:
            raise ValueError(f"h_bars ({self.h_bars}) must be one of {params.sweep_h_bars}")
        if params.sweep_reclaim_rule != "close_back_inside":
            # SPEC.md: "variants enumerated but not all built" -- only the v0
            # close_back_inside reclaim rule is implemented by this FSM.
            raise ValueError(
                f"sweep_reclaim_rule {params.sweep_reclaim_rule!r} is not implemented "
                "(only 'close_back_inside' is built in v0)"
            )
        self._levels_engine = LevelRegistry(instrument, timeframe, params)
        self._levels: Dict[str, dict] = {}  # level_id -> {kind, price, salience, expired}
        self._episodes: Dict[Tuple[str, str], _Episode] = {}  # (level_id, side) -> episode

    # -- level bookkeeping (private internal LevelRegistry) -----------------

    def _sync_levels(self, bar: Any) -> None:
        for ev in self._levels_engine.on_bar(bar):
            if ev.event_type == "LEVEL_CREATED":
                self._levels[ev.event_id] = {
                    "kind": ev.attributes["kind"],
                    "price": ev.attributes["price"],
                    "salience": {k: ev.attributes[k] for k in _SALIENCE_KEYS},
                    "expired": False,
                    # mirrors LevelRegistry's own "active_from = actionable_at" gate: a
                    # level can't be tested/swept on the very same bar it was created.
                    "active_from": ev.actionable_at,
                }
            elif ev.event_type == "LEVEL_EXPIRED":
                src = ev.source_event_ids[0]
                if src in self._levels:
                    self._levels[src]["expired"] = True

    def _breached(self, bar: Any, level_price: float, side: str) -> bool:
        tick = self.params.tick_size
        if side == "buy":
            return bar.high >= level_price + tick
        return bar.low <= level_price - tick

    # -- event construction ---------------------------------------------------

    def _event(
        self,
        event_type: str,
        origin_time,
        confirmed_at,
        price_low: float,
        price_high: float,
        discriminator: str,
        attributes: dict,
        source_event_ids: tuple = (),
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

    def _salience_attrs(self, salience: dict) -> dict:
        return {f"level_{k}": v for k, v in salience.items()}

    def _open_episode(self, level_id: str, info: dict, side: str, bar: Any) -> CausalEvent:
        breach_price = bar.high if side == "buy" else bar.low
        disc = f"{level_id}|{side}|{bar.close_time.isoformat()}"
        lo, hi = (info["price"], breach_price) if info["price"] <= breach_price else (breach_price, info["price"])
        ev = self._event(
            "EXCURSION_OPEN",
            bar.close_time,
            bar.close_time,
            lo,
            hi,
            disc,
            attributes={
                "level_id": level_id,
                "side": side,
                "level_kind": info["kind"],
                "level_price": info["price"],
                "breach_price": breach_price,
                "h_bars": self.h_bars,
                **self._salience_attrs(info["salience"]),
            },
            source_event_ids=(level_id,),
        )
        self._episodes[(level_id, side)] = _Episode(
            ev.event_id, level_id, side, info["kind"], info["price"], dict(info["salience"]), bar.close_time
        )
        return ev

    def _terminal(self, key: Tuple[str, str], event_type: str, bar: Any, reason: str) -> CausalEvent:
        ep = self._episodes[key]
        tick = self.params.tick_size
        depth_ticks = abs(ep.extreme_price - ep.level_price) / tick
        reclaim_speed = ep.bars_elapsed if event_type == "SWEEP_CONFIRMED" else None
        lo, hi = (
            (ep.level_price, ep.extreme_price) if ep.level_price <= ep.extreme_price
            else (ep.extreme_price, ep.level_price)
        )
        disc = f"{ep.level_id}|{ep.side}|{ep.open_origin_time.isoformat()}"
        return self._event(
            event_type,
            ep.open_origin_time,
            bar.close_time,
            lo,
            hi,
            disc,
            attributes={
                "level_id": ep.level_id,
                "side": ep.side,
                "level_kind": ep.level_kind,
                "level_price": ep.level_price,
                "excursion_depth_ticks": depth_ticks,
                "duration_bars": ep.bars_elapsed,
                "reclaim_speed_bars": reclaim_speed,
                "reason": reason,
                "h_bars": self.h_bars,
                **self._salience_attrs(ep.salience),
            },
            source_event_ids=(ep.open_event_id,),
        )

    # -- main loop ------------------------------------------------------------

    def _advance_episode(self, key: Tuple[str, str], bar: Any) -> Optional[CausalEvent]:
        ep = self._episodes[key]
        side = ep.side
        level_price = ep.level_price
        if side == "buy":
            ep.extreme_price = max(ep.extreme_price, bar.high)
        else:
            ep.extreme_price = min(ep.extreme_price, bar.low)
        ep.bars_elapsed += 1
        h = self.h_bars

        if ep.bars_elapsed > h:
            return self._terminal(key, "ACCEPTED_BREAKOUT", bar, reason="dwell_exceeded_window")

        reclaimed = (bar.close < level_price) if side == "buy" else (bar.close > level_price)
        still_beyond = (bar.close > level_price) if side == "buy" else (bar.close < level_price)

        if reclaimed:
            return self._terminal(key, "SWEEP_CONFIRMED", bar, reason="close_back_inside")

        if still_beyond:
            ep.consecutive_beyond += 1
            if ep.consecutive_beyond >= 2:
                return self._terminal(key, "ACCEPTED_BREAKOUT", bar, reason="two_consecutive_closes_beyond")
        else:
            ep.consecutive_beyond = 0  # boundary tie (close == level exactly): resets the streak

        if ep.bars_elapsed >= h and not still_beyond:
            return self._terminal(key, "EXCURSION_TIMEOUT", bar, reason="window_elapsed_on_boundary_tie")

        return None  # keep waiting (at most one grace bar past h, see rule 1 above)

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        events: List[CausalEvent] = []
        self._sync_levels(bar)

        for level_id, info in self._levels.items():
            if info["expired"] or bar.close_time < info["active_from"]:
                continue
            for side in _sides_for_kind(info["kind"]):
                key = (level_id, side)
                if key in self._episodes:
                    continue
                if self._breached(bar, info["price"], side):
                    events.append(self._open_episode(level_id, info, side, bar))

        for key in list(self._episodes.keys()):
            term = self._advance_episode(key, bar)
            if term is not None:
                events.append(term)
                del self._episodes[key]

        return events
