"""AMD FSM (SPEC.md "Engine definitions (v0 pins)" -> "AMD FSM"): Accumulation
-> Manipulation -> Distribution, one episode at a time, causal at every
transition (each transition is its own event at its own `confirmed_at` --
"retrospective labelling structurally impossible", SPEC.md).

States and transitions (`AmdEngine.state` in `{"SEARCH", "ACCUMULATION_
ACTIVE", "EXCURSION", "MANIPULATION_CANDIDATE"}`; `SEARCH` is the resting/
idle state, entered initially and after every episode resolves, success or
failure):

  * `SEARCH` -> `ACCUMULATION_ACTIVE` when the rolling `amd_range_window_
    bars` (12) high/low range is `< amd_range_atr_mult (0.6) * ATR20` for
    `>= amd_range_min_bars` (6) CONSECUTIVE bars; the range is FROZEN at
    entry (`frozen_low`/`frozen_high` = the window's own high/low at the
    instant the streak completes). SEARCH has no timeout/failure event --
    it is the null state (no episode has been committed yet), so there is
    nothing to "fail"; a streak reset (one non-qualifying bar) simply drops
    the running count back to 0 with no event (there is no candidate to
    report -- SPEC.md's "no silent filters" concerns candidates that WERE
    detected, not the absence of one).

  * `ACCUMULATION_ACTIVE` -> `EXCURSION` on the first bar whose wick trades
    beyond the frozen range (`bar.high > frozen_high` or `bar.low <
    frozen_low`; a same-bar double-break -- both sides -- is tie-broken
    deterministically toward the larger excess, mirroring `structure.py`'s
    own tie-break for a simultaneous up/down break). TIMEOUT: SPEC.md states
    no explicit dwell limit for `ACCUMULATION_ACTIVE` itself -- reusing `amd_
    range_window_bars` (12, the SAME window that defined the range in the
    first place) as its own patience window is the least-arbitrary choice
    available (no new, untuned param) and is what makes `ACCUMULATION_ACTIVE`
    actually bounded ("every state has a timeout" per SPEC.md's own FSM
    prose) rather than able to dwell forever; documented interpretive call,
    flagged for Fable's review, non-blocking. Timeout -> `AMD_FAILED_
    ACCUMULATION`, back to `SEARCH`.

  * `EXCURSION` -> `MANIPULATION_CANDIDATE` if price RECLAIMS back inside
    the frozen range on the broken side (close back `<= frozen_high` if the
    break was up, `>= frozen_low` if down) within `amd_manipulation_reclaim_
    bars` (6) bars. Timeout -> `AMD_FAILED_EXCURSION`, back to `SEARCH`.

  * `MANIPULATION_CANDIDATE` -> `DISTRIBUTION_CONFIRMED` (terminal SUCCESS)
    on the first `DISPLACEMENT_QUALIFIED` event, from a PRIVATE internal
    `DisplacementEngine` instance (mirrors `sweeps.py`/`zones.py`'s own "no
    cross-engine event sharing" convention), whose `direction` is OPPOSITE
    the excursion's break direction (excursion broke up -> need a bearish
    displacement, confirming the up-break was the manipulation/liquidity
    grab ahead of the real bearish distribution leg; mirror image for a
    down-break) within `amd_distribution_window_bars` (12) bars. On success,
    the FSM returns to `SEARCH` (ready for the next episode -- AMD is a
    repeating pattern detector, not single-shot). Timeout -> `AMD_FAILED_
    MANIPULATION`, back to `SEARCH`.

Every transition event's `origin_time` is carried forward from the episode's
OWN `AMD_ACCUMULATION_ACTIVE` origin (the frozen window's start bar) --
mirrors `structure.py`'s CHOCH -> MSS origin-time carry-forward -- while
`confirmed_at` is always the bar that produced THIS specific transition;
`source_event_ids` chains each event to the one immediately before it,
giving the full episode a traceable lineage.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.config import ICT_V2_PARAMS_V0, ParamSet
from ..core.events import CausalEvent, compute_event_id
from ._util import ATR, next_actionable
from .displacement import DisplacementEngine

RULE_VERSION = "AMD_V0"


class AmdEngine:
    def __init__(
        self,
        instrument: str = "NQ",
        timeframe: str = "5m",
        params: ParamSet = ICT_V2_PARAMS_V0,
    ) -> None:
        self.instrument = instrument
        self.timeframe = timeframe
        self.params = params
        self._atr = ATR(20)
        self._displacement = DisplacementEngine(instrument, timeframe, params)
        self._highs: List[float] = []
        self._lows: List[float] = []
        self._times: List[Any] = []
        self._window = params.amd_range_window_bars
        self._streak = 0

        self.state = "SEARCH"
        self._episode: Optional[Dict[str, Any]] = None

    # -- event construction ---------------------------------------------------

    def _event(self, event_type, origin_time, confirmed_at, price_low, price_high, discriminator, attributes, source_event_ids) -> CausalEvent:
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

    def _reset_to_search(self) -> None:
        self.state = "SEARCH"
        self._episode = None
        self._streak = 0

    # -- rolling range bookkeeping (fed every bar, any state) ------------------

    def _push_window(self, bar: Any) -> None:
        self._highs.append(bar.high)
        self._lows.append(bar.low)
        self._times.append(bar.close_time)
        if len(self._highs) > self._window:
            self._highs.pop(0)
            self._lows.pop(0)
            self._times.pop(0)

    # -- SEARCH -----------------------------------------------------------------

    def _advance_search(self, bar: Any, atr20: Optional[float]) -> List[CausalEvent]:
        if atr20 is None or len(self._highs) < self._window:
            return []
        rng = max(self._highs) - min(self._lows)
        threshold = self.params.amd_range_atr_mult * atr20
        if rng < threshold:
            self._streak += 1
        else:
            self._streak = 0
        if self._streak < self.params.amd_range_min_bars:
            return []

        frozen_low, frozen_high = min(self._lows), max(self._highs)
        origin_time = self._times[0]
        disc = f"acc|{origin_time.isoformat()}|{bar.close_time.isoformat()}"
        ev = self._event(
            "AMD_ACCUMULATION_ACTIVE", origin_time, bar.close_time, frozen_low, frozen_high, disc,
            attributes={
                "frozen_low": frozen_low, "frozen_high": frozen_high, "atr20": atr20,
                "range_pts": rng, "threshold_pts": threshold, "window_bars": self._window,
            },
            source_event_ids=(),
        )
        self.state = "ACCUMULATION_ACTIVE"
        self._episode = {
            "origin_time": origin_time, "entry_event_id": ev.event_id,
            "frozen_low": frozen_low, "frozen_high": frozen_high, "bars_in_state": 0,
        }
        self._streak = 0
        return [ev]

    # -- ACCUMULATION_ACTIVE ------------------------------------------------------

    def _advance_accumulation(self, bar: Any) -> List[CausalEvent]:
        ep = self._episode
        ep["bars_in_state"] += 1
        fh, fl = ep["frozen_high"], ep["frozen_low"]
        up_break = bar.high > fh
        down_break = bar.low < fl

        if up_break or down_break:
            if up_break and down_break:
                up_excess, down_excess = bar.high - fh, fl - bar.low
                up_break, down_break = (up_excess >= down_excess), (down_excess > up_excess)
            direction = "up" if up_break else "down"
            extreme = bar.high if direction == "up" else bar.low
            disc = f"exc|{ep['entry_event_id']}|{bar.close_time.isoformat()}"
            lo, hi = (min(fl, extreme), max(fh, extreme))
            ev = self._event(
                "AMD_EXCURSION", ep["origin_time"], bar.close_time, lo, hi, disc,
                attributes={
                    "direction": direction, "frozen_low": fl, "frozen_high": fh,
                    "excursion_extreme": extreme, "bars_in_accumulation": ep["bars_in_state"],
                },
                source_event_ids=(ep["entry_event_id"],),
            )
            self.state = "EXCURSION"
            ep.update({
                "excursion_event_id": ev.event_id, "direction": direction,
                "bars_since_excursion": 0, "excursion_extreme": extreme,
            })
            return [ev]

        if ep["bars_in_state"] > self.params.amd_range_window_bars:
            disc = f"fail_acc|{ep['entry_event_id']}|{bar.close_time.isoformat()}"
            ev = self._event(
                "AMD_FAILED_ACCUMULATION", ep["origin_time"], bar.close_time, fl, fh, disc,
                attributes={"frozen_low": fl, "frozen_high": fh, "bars_in_state": ep["bars_in_state"]},
                source_event_ids=(ep["entry_event_id"],),
            )
            self._reset_to_search()
            return [ev]

        return []

    # -- EXCURSION ----------------------------------------------------------------

    def _advance_excursion(self, bar: Any) -> List[CausalEvent]:
        ep = self._episode
        ep["bars_since_excursion"] += 1
        direction = ep["direction"]
        fh, fl = ep["frozen_high"], ep["frozen_low"]
        ep["excursion_extreme"] = max(ep["excursion_extreme"], bar.high) if direction == "up" else min(ep["excursion_extreme"], bar.low)
        reclaimed = (bar.close <= fh) if direction == "up" else (bar.close >= fl)

        if reclaimed:
            disc = f"manip|{ep['excursion_event_id']}|{bar.close_time.isoformat()}"
            ev = self._event(
                "AMD_MANIPULATION_CANDIDATE", ep["origin_time"], bar.close_time, fl, fh, disc,
                attributes={
                    "direction": direction, "frozen_low": fl, "frozen_high": fh,
                    "excursion_extreme": ep["excursion_extreme"], "reclaim_bars": ep["bars_since_excursion"],
                },
                source_event_ids=(ep["excursion_event_id"],),
            )
            self.state = "MANIPULATION_CANDIDATE"
            ep.update({"manipulation_event_id": ev.event_id, "bars_since_manipulation": 0})
            return [ev]

        if ep["bars_since_excursion"] > self.params.amd_manipulation_reclaim_bars:
            disc = f"fail_exc|{ep['excursion_event_id']}|{bar.close_time.isoformat()}"
            ev = self._event(
                "AMD_FAILED_EXCURSION", ep["origin_time"], bar.close_time, fl, fh, disc,
                attributes={
                    "direction": direction, "frozen_low": fl, "frozen_high": fh,
                    "excursion_extreme": ep["excursion_extreme"], "bars_since_excursion": ep["bars_since_excursion"],
                },
                source_event_ids=(ep["excursion_event_id"],),
            )
            self._reset_to_search()
            return [ev]

        return []

    # -- MANIPULATION_CANDIDATE ----------------------------------------------------

    def _advance_manipulation(self, bar: Any, displacement_events: List[CausalEvent]) -> List[CausalEvent]:
        ep = self._episode
        ep["bars_since_manipulation"] += 1
        direction = ep["direction"]
        opposite = "bearish" if direction == "up" else "bullish"
        match = next(
            (d for d in displacement_events if d.event_type == "DISPLACEMENT_QUALIFIED" and d.attributes.get("direction") == opposite),
            None,
        )
        fh, fl = ep["frozen_high"], ep["frozen_low"]

        if match is not None:
            disc = f"dist|{ep['manipulation_event_id']}|{bar.close_time.isoformat()}"
            ev = self._event(
                "AMD_DISTRIBUTION_CONFIRMED", ep["origin_time"], bar.close_time, fl, fh, disc,
                attributes={
                    "manipulation_direction": direction, "distribution_direction": opposite,
                    "frozen_low": fl, "frozen_high": fh, "bars_since_manipulation": ep["bars_since_manipulation"],
                },
                source_event_ids=(ep["manipulation_event_id"], match.event_id),
            )
            self._reset_to_search()
            return [ev]

        if ep["bars_since_manipulation"] > self.params.amd_distribution_window_bars:
            disc = f"fail_manip|{ep['manipulation_event_id']}|{bar.close_time.isoformat()}"
            ev = self._event(
                "AMD_FAILED_MANIPULATION", ep["origin_time"], bar.close_time, fl, fh, disc,
                attributes={
                    "direction": direction, "frozen_low": fl, "frozen_high": fh,
                    "bars_since_manipulation": ep["bars_since_manipulation"],
                },
                source_event_ids=(ep["manipulation_event_id"],),
            )
            self._reset_to_search()
            return [ev]

        return []

    # -- main loop ------------------------------------------------------------

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        atr20 = self._atr.update(bar.high, bar.low, bar.close)
        self._push_window(bar)
        displacement_events = self._displacement.on_bar(bar)

        if self.state == "SEARCH":
            return self._advance_search(bar, atr20)
        if self.state == "ACCUMULATION_ACTIVE":
            return self._advance_accumulation(bar)
        if self.state == "EXCURSION":
            return self._advance_excursion(bar)
        if self.state == "MANIPULATION_CANDIDATE":
            return self._advance_manipulation(bar, displacement_events)
        raise AssertionError(f"unreachable AMD state {self.state!r}")
