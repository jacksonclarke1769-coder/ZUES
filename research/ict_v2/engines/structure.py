"""Structure (SPEC.md "Engine definitions (v0 pins)" -> "Structure"): protected-
swing BOS / CHoCH / MSS state machine, per instrument/timeframe, built on top
of Method-A swings (`engines/swings.py::SwingMethodA`).

State machine (`direction` in {"undefined", "bullish", "bearish",
"transitional"}):

  * "undefined" (startup): no state committed yet. The first close beyond
    the most-recently-confirmed Method-A swing high OR swing low (whichever
    is known and gets broken first) fires `STRUCTURE_INITIALIZED` and commits
    the initial direction. This is NOT a BOS (there is no prior state to
    continue) -- SPEC.md doesn't name this bootstrap event explicitly; it is
    structurally required (rule 4, "no silent filters": the very first
    direction has to be recorded as SOME event) and is called out here for
    Fable's review.

  * "bullish": `protected_low` = most-recently-confirmed Method-A swing low
    (must hold); `target_high` = most-recently-confirmed Method-A swing high.
        close beyond target_high (continuation)      -> BOS
        close beyond protected_low (counter-move)     -> CHOCH, direction ->
                                                          "transitional",
                                                          pending="bearish"
    "bearish" is the mirror image.

  * "transitional" (post-CHoCH, awaiting MSS): BOS/CHoCH evaluation is
    suspended (Method-A swing tracking keeps running underneath regardless of
    FSM state). For up to `mss_window_bars` (W_MSS=12) bars AFTER the CHoCH
    bar (i.e. bars choch+1 .. choch+W_MSS, mirroring model01's `range(i+1,
    i+1+W_MSS)` bar count -- the CHoCH bar's own candle is NOT part of the
    search window, since by construction its close has already produced the
    break; SPEC.md's "mirror model01" instruction is read here as pinning the
    WINDOW SIZE and the "close beyond most-recent opposing confirmed swing"
    style of the break test, not a literal bar-offset-for-bar-offset replay
    of model01's separate sweep-anchor -- that full replay is WP-D's job in
    `parity/model01_canary.py`; documented here for Fable's review), the
    first bar whose body qualifies as a displacement in the pending direction
    (body >= `displacement_body_mult` * mean-20 body, SAME formula as
    `primitives.py::body_ratio` / `engines/displacement.py`, computed with an
    internal, independent `RollingMean(20)` -- NOT read from `displacement.py`'s
    emitted events; BatchRunner engines never share state, `core/runner.py`)
    fires `MSS` and commits `direction = pending`. If the window elapses with
    no qualifying bar, `MSS_WINDOW_EXPIRED` fires and `direction` reverts to
    the PRE-CHoCH direction (the challenge to structure failed to confirm),
    resuming normal BOS/CHoCH evaluation from there.

`break_type` (v0="close"): which OHLC field is compared to the level.
"""
from __future__ import annotations

from typing import Any, List, Optional

from ..core.config import ICT_V2_PARAMS_V0, ParamSet
from ..core.events import CausalEvent, compute_event_id
from ._util import RollingMean, body, next_actionable
from .swings import SwingMethodA

RULE_VERSION = "STRUCTURE_V0"


def _break_price(bar: Any, params: ParamSet, side: str) -> float:
    """`side`: "up" (comparing against a level being broken to the upside) or
    "down". v0 break_type="close" uses the same close for both sides; the
    "wick" alternative (not exercised by any v0 test, param present for
    forward compatibility) uses the extreme in the break direction."""
    if params.break_type == "close":
        return bar.close
    if params.break_type == "wick":
        return bar.high if side == "up" else bar.low
    raise ValueError(f"unknown break_type {params.break_type!r}")


class StructureEngine:
    def __init__(
        self,
        instrument: str = "NQ",
        timeframe: str = "5m",
        params: ParamSet = ICT_V2_PARAMS_V0,
    ) -> None:
        self.instrument = instrument
        self.timeframe = timeframe
        self.params = params
        self._swings = SwingMethodA(instrument, timeframe, params)
        self._body_mean = RollingMean(20)
        self._body_mean_prior: Optional[float] = None  # prior-20 body mean, refreshed every bar

        self.direction: str = "undefined"
        self._last_swing_high: Optional[float] = None
        self._last_swing_low: Optional[float] = None

        # transitional-episode state
        self._pending_direction: Optional[str] = None
        self._pre_choch_direction: Optional[str] = None
        self._choch_event: Optional[CausalEvent] = None
        self._transitional_bars_elapsed = 0

    # -- swing bookkeeping -------------------------------------------------

    def _update_swings(self, bar: Any) -> None:
        for ev in self._swings.on_bar(bar):
            if ev.event_type == "SWING_HIGH_A":
                self._last_swing_high = ev.price_high
            elif ev.event_type == "SWING_LOW_A":
                self._last_swing_low = ev.price_low

    def _is_displacement_qualified(self, bar: Any, direction: str) -> bool:
        # `_body_mean` MUST be fed every bar (see `on_bar`), not only while
        # transitional -- W_MSS (12 bars) is shorter than the mean-20 window,
        # so a roller only ever fed during transitional episodes would never
        # warm up in time to confirm anything.
        b = body(bar.open, bar.close)
        prior_mean = self._body_mean_prior
        if prior_mean is None or prior_mean <= 0:
            return False
        if b < self.params.displacement_body_mult * prior_mean:
            return False
        bar_direction = "bullish" if bar.close > bar.open else "bearish" if bar.close < bar.open else None
        return bar_direction == direction

    # -- event construction --------------------------------------------------

    def _event(
        self,
        event_type: str,
        origin_time,
        confirmed_at,
        level: float,
        break_price: float,
        discriminator: str,
        attributes: dict,
        source_event_ids: tuple = (),
    ) -> CausalEvent:
        eid = compute_event_id(
            event_type, self.instrument, origin_time, RULE_VERSION, discriminator=discriminator
        )
        lo, hi = (level, break_price) if level <= break_price else (break_price, level)
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
            price_low=lo,
            price_high=hi,
            source_event_ids=source_event_ids,
            attributes=attributes,
        )

    # -- main loop ------------------------------------------------------------

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        self._update_swings(bar)
        # feed the body-mean roller every bar (see `_is_displacement_qualified`);
        # `update()` returns the PRIOR mean (before this bar folds in), which is
        # exactly what a bar's own qualification check must compare against.
        self._body_mean_prior = self._body_mean.update(body(bar.open, bar.close))
        events: List[CausalEvent] = []

        if self.direction == "transitional":
            events.extend(self._advance_transitional(bar))
            return events

        if self.direction == "undefined":
            events.extend(self._evaluate_undefined(bar))
            return events

        events.extend(self._evaluate_established(bar))
        return events

    def _evaluate_undefined(self, bar: Any) -> List[CausalEvent]:
        up_break = self._last_swing_high is not None and _break_price(bar, self.params, "up") > self._last_swing_high
        down_break = self._last_swing_low is not None and _break_price(bar, self.params, "down") < self._last_swing_low
        if not up_break and not down_break:
            return []
        # deterministic tie-break if both trip on the same bar: larger excursion wins.
        if up_break and down_break:
            up_excess = _break_price(bar, self.params, "up") - self._last_swing_high
            down_excess = self._last_swing_low - _break_price(bar, self.params, "down")
            up_break, down_break = (up_excess >= down_excess), (down_excess > up_excess)
        if up_break:
            direction = "bullish"
            level = self._last_swing_high
        else:
            direction = "bearish"
            level = self._last_swing_low
        self.direction = direction
        ev = self._event(
            "STRUCTURE_INITIALIZED",
            bar.close_time,
            bar.close_time,
            level,
            bar.close,
            discriminator=f"{direction}|{level:.6f}",
            attributes={"direction": direction, "level": level},
        )
        return [ev]

    def _evaluate_established(self, bar: Any) -> List[CausalEvent]:
        if self.direction == "bullish":
            protected, target = self._last_swing_low, self._last_swing_high
            continuation_side, counter_side = "up", "down"
            pending = "bearish"
        else:
            protected, target = self._last_swing_high, self._last_swing_low
            continuation_side, counter_side = "down", "up"
            pending = "bullish"

        if target is not None:
            price = _break_price(bar, self.params, continuation_side)
            broke = price > target if continuation_side == "up" else price < target
            if broke:
                return [
                    self._event(
                        "BOS",
                        bar.close_time,
                        bar.close_time,
                        target,
                        price,
                        discriminator=f"{self.direction}|{target:.6f}|{bar.close_time.isoformat()}",
                        attributes={"direction": self.direction, "level": target},
                    )
                ]

        if protected is not None:
            price = _break_price(bar, self.params, counter_side)
            broke = price < protected if counter_side == "down" else price > protected
            if broke:
                choch = self._event(
                    "CHOCH",
                    bar.close_time,
                    bar.close_time,
                    protected,
                    price,
                    discriminator=f"{self.direction}|{protected:.6f}|{bar.close_time.isoformat()}",
                    attributes={"from_direction": self.direction, "to_direction_candidate": pending, "level": protected},
                )
                self._pre_choch_direction = self.direction
                self._pending_direction = pending
                self._choch_event = choch
                self._transitional_bars_elapsed = 0
                self.direction = "transitional"
                return [choch]

        return []

    def _advance_transitional(self, bar: Any) -> List[CausalEvent]:
        qualified = self._is_displacement_qualified(bar, self._pending_direction)
        self._transitional_bars_elapsed += 1
        if qualified:
            choch_level = self._choch_event.attributes["level"]
            mss = self._event(
                "MSS",
                self._choch_event.origin_time,
                bar.close_time,
                choch_level,
                bar.close,
                discriminator=f"{self._pending_direction}|{self._choch_event.event_id}",
                attributes={
                    "direction": self._pending_direction,
                    "choch_bars_elapsed": self._transitional_bars_elapsed,
                },
                source_event_ids=(self._choch_event.event_id,),
            )
            self.direction = self._pending_direction
            self._clear_transitional()
            return [mss]

        if self._transitional_bars_elapsed >= self.params.mss_window_bars:
            expired = self._event(
                "MSS_WINDOW_EXPIRED",
                self._choch_event.origin_time,
                bar.close_time,
                self._choch_event.price_low,
                self._choch_event.price_high,
                discriminator=f"{self._pending_direction}|{self._choch_event.event_id}",
                attributes={
                    "pending_direction": self._pending_direction,
                    "reverted_to": self._pre_choch_direction,
                    "window_bars": self.params.mss_window_bars,
                },
                source_event_ids=(self._choch_event.event_id,),
            )
            self.direction = self._pre_choch_direction
            self._clear_transitional()
            return [expired]

        return []

    def _clear_transitional(self) -> None:
        self._pending_direction = None
        self._pre_choch_direction = None
        self._choch_event = None
        self._transitional_bars_elapsed = 0
