"""Swings (SPEC.md "Engine definitions (v0 pins)" -> "Swings"): three
independent, causal pivot/level detectors over 5m bars.

  * Method A (`SwingMethodA`) -- symmetric fractal pivot, `left`/`right`
    default 3/3. `origin_time` = the pivot bar's own close_time; `confirmed_at`
    = close_time of the bar `right` bars later. MIRRORS the frozen oracle
    `~/trading-team/backtests/ict-nq-framework/engine/primitives.py::swings` /
    `last_known_swings` exactly -- including its inequality directions, which
    read (STRICT on the left window, `>=`/`<=` on the right window):
        swing high @ i:  H[i] >  max(H[i-left .. i-1])   AND
                          H[i] >= max(H[i+1 .. i+right])
        swing low  @ i:  L[i] <  min(L[i-left .. i-1])   AND
                          L[i] <= min(L[i+1 .. i+right])
    NOTE: SPEC.md's own prose ("H_i >= max(left l) and > max(right r)") states
    the inequality directions the OTHER way round from the actual oracle code.
    Per the explicit instruction to "wrap/mirror frozen primitives.py math ...
    exactly" (needed for the WP-D 581-signal parity canary), this
    implementation follows primitives.py's CODE, not SPEC.md's prose; the
    discrepancy is called out here and in the WP-B summary for Fable's
    review, and is directly checked by
    `tests/test_swings.py::test_method_a_matches_frozen_last_known_swings`.

  * Method B (`SwingMethodB`) -- directional-change / zigzag: a running
    extreme is confirmed the instant price reverses from it by at least
    `max(swing_b_min_reversal_ticks, swing_b_min_reversal_atr_mult * ATR20)`
    points, confirmed at that reversal bar's own close (single-bar
    detection, no look-ahead). Before the first pivot is found, BOTH a
    running up-extreme and a running down-extreme are tracked simultaneously
    (there is no direction yet to commit to); whichever reverses first wins
    and fixes the initial direction. ATR20 is INCLUSIVE of the current bar
    (see `engines/_util.py::ATR`), so during ATR warmup (first 19 bars) no
    reversal can be confirmed yet even though extremes are still tracked.

  * Method C (`SwingMethodC`) -- trailing extreme over the last
    `swing_c_lookback_bars` (v0=20) COMPLETED bars (inclusive of the current
    bar). This is explicitly "a level, not a pivot" (SPEC.md): it has no
    confirmation lag and is re-emitted every bar once warmed up, carrying the
    window's current high AND low together as one event (`price_high`/
    `price_low`).
"""
from __future__ import annotations

from collections import deque
from typing import Any, Deque, Iterable, List, Optional, Tuple

from ..core.config import ICT_V2_PARAMS_V0, ParamSet
from ..core.events import CausalEvent, compute_event_id
from ._util import ATR, next_actionable

RULE_A = "SWINGS_METHOD_A_V0"
RULE_B = "SWINGS_METHOD_B_V0"
RULE_C = "SWINGS_METHOD_C_V0"


def _swing_event(
    event_type: str,
    instrument: str,
    timeframe: str,
    origin_time,
    confirmed_at,
    rule_version: str,
    param_version: str,
    discriminator: str,
    price_low: Optional[float] = None,
    price_high: Optional[float] = None,
    attributes: Optional[dict] = None,
) -> CausalEvent:
    eid = compute_event_id(event_type, instrument, origin_time, rule_version, discriminator=discriminator)
    actionable = next_actionable(confirmed_at, timeframe)
    return CausalEvent(
        event_id=eid,
        event_type=event_type,
        instrument=instrument,
        timeframe=timeframe,
        origin_time=origin_time,
        observed_at=confirmed_at,
        confirmed_at=confirmed_at,
        actionable_at=actionable,
        rule_version=rule_version,
        param_version=param_version,
        price_low=price_low,
        price_high=price_high,
        attributes=attributes or {},
    )


class SwingMethodA:
    """Symmetric fractal pivot (`SWING_HIGH_A` / `SWING_LOW_A`)."""

    def __init__(
        self,
        instrument: str = "NQ",
        timeframe: str = "5m",
        params: ParamSet = ICT_V2_PARAMS_V0,
        left: Optional[int] = None,
        right: Optional[int] = None,
    ) -> None:
        self.instrument = instrument
        self.timeframe = timeframe
        self.params = params
        self.left = left if left is not None else params.swing_left
        self.right = right if right is not None else params.swing_right
        self._buf: Deque[Any] = deque(maxlen=self.left + self.right + 1)

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        self._buf.append(bar)
        events: List[CausalEvent] = []
        span = self.left + self.right + 1
        if len(self._buf) < span:
            return events
        window = list(self._buf)
        center = window[self.left]
        left_bars = window[: self.left]
        right_bars = window[self.left + 1 :]
        left_max_h = max(b.high for b in left_bars)
        right_max_h = max(b.high for b in right_bars)
        left_min_l = min(b.low for b in left_bars)
        right_min_l = min(b.low for b in right_bars)
        confirmed_at = bar.close_time  # newest bar == center + right
        if center.high > left_max_h and center.high >= right_max_h:
            events.append(
                _swing_event(
                    "SWING_HIGH_A",
                    self.instrument,
                    self.timeframe,
                    center.close_time,
                    confirmed_at,
                    RULE_A,
                    self.params.param_version,
                    discriminator=f"high|{self.left}|{self.right}|{center.high:.6f}",
                    price_high=center.high,
                    attributes={"left": self.left, "right": self.right, "price": center.high},
                )
            )
        if center.low < left_min_l and center.low <= right_min_l:
            events.append(
                _swing_event(
                    "SWING_LOW_A",
                    self.instrument,
                    self.timeframe,
                    center.close_time,
                    confirmed_at,
                    RULE_A,
                    self.params.param_version,
                    discriminator=f"low|{self.left}|{self.right}|{center.low:.6f}",
                    price_low=center.low,
                    attributes={"left": self.left, "right": self.right, "price": center.low},
                )
            )
        return events


class SwingMethodB:
    """Directional-change / zigzag pivot (`SWING_HIGH_B` / `SWING_LOW_B`)."""

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
        self._direction: Optional[str] = None  # None until first pivot
        self._up_extreme: Optional[float] = None
        self._up_bar: Any = None
        self._down_extreme: Optional[float] = None
        self._down_bar: Any = None

    def _threshold(self, atr20: float) -> float:
        return max(
            self.params.swing_b_min_reversal_ticks * self.params.tick_size,
            self.params.swing_b_min_reversal_atr_mult * atr20,
        )

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        atr20 = self._atr.update(bar.high, bar.low, bar.close)
        events: List[CausalEvent] = []

        if self._up_extreme is None or bar.high > self._up_extreme:
            self._up_extreme, self._up_bar = bar.high, bar
        if self._down_extreme is None or bar.low < self._down_extreme:
            self._down_extreme, self._down_bar = bar.low, bar

        if atr20 is None:
            return events  # extremes tracked, but no reversal can be confirmed yet

        threshold = self._threshold(atr20)
        reversal_from_up = self._up_extreme - bar.low
        reversal_from_down = bar.high - self._down_extreme

        if self._direction is None:
            up_ok = reversal_from_up >= threshold
            down_ok = reversal_from_down >= threshold
            if up_ok and (not down_ok or reversal_from_up >= reversal_from_down):
                events.append(self._confirm_high(bar, confirmed_at=bar.close_time, atr20=atr20, threshold=threshold))
                self._direction = "down"
                self._down_extreme, self._down_bar = bar.low, bar
            elif down_ok:
                events.append(self._confirm_low(bar, confirmed_at=bar.close_time, atr20=atr20, threshold=threshold))
                self._direction = "up"
                self._up_extreme, self._up_bar = bar.high, bar
            return events

        if self._direction == "up" and reversal_from_up >= threshold:
            events.append(self._confirm_high(bar, confirmed_at=bar.close_time, atr20=atr20, threshold=threshold))
            self._direction = "down"
            self._down_extreme, self._down_bar = bar.low, bar
        elif self._direction == "down" and reversal_from_down >= threshold:
            events.append(self._confirm_low(bar, confirmed_at=bar.close_time, atr20=atr20, threshold=threshold))
            self._direction = "up"
            self._up_extreme, self._up_bar = bar.high, bar
        return events

    def _confirm_high(self, reversal_bar: Any, confirmed_at, atr20: float, threshold: float) -> CausalEvent:
        pivot_bar = self._up_bar
        return _swing_event(
            "SWING_HIGH_B",
            self.instrument,
            self.timeframe,
            pivot_bar.close_time,
            confirmed_at,
            RULE_B,
            self.params.param_version,
            discriminator=f"high|{pivot_bar.close_time.isoformat()}|{self._up_extreme:.6f}",
            price_high=self._up_extreme,
            attributes={
                "price": self._up_extreme,
                "reversal_bar_close_time": reversal_bar.close_time,
                "atr20": atr20,
                "threshold_pts": threshold,
            },
        )

    def _confirm_low(self, reversal_bar: Any, confirmed_at, atr20: float, threshold: float) -> CausalEvent:
        pivot_bar = self._down_bar
        return _swing_event(
            "SWING_LOW_B",
            self.instrument,
            self.timeframe,
            pivot_bar.close_time,
            confirmed_at,
            RULE_B,
            self.params.param_version,
            discriminator=f"low|{pivot_bar.close_time.isoformat()}|{self._down_extreme:.6f}",
            price_low=self._down_extreme,
            attributes={
                "price": self._down_extreme,
                "reversal_bar_close_time": reversal_bar.close_time,
                "atr20": atr20,
                "threshold_pts": threshold,
            },
        )


class SwingMethodC:
    """Trailing extreme over the last `swing_c_lookback_bars` completed bars
    (`TRAILING_EXTREME_C`) -- a level, not a pivot: re-emitted every bar once
    the window is warmed up."""

    def __init__(
        self,
        instrument: str = "NQ",
        timeframe: str = "5m",
        params: ParamSet = ICT_V2_PARAMS_V0,
    ) -> None:
        self.instrument = instrument
        self.timeframe = timeframe
        self.params = params
        self._highs: Deque[float] = deque(maxlen=params.swing_c_lookback_bars)
        self._lows: Deque[float] = deque(maxlen=params.swing_c_lookback_bars)

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        self._highs.append(bar.high)
        self._lows.append(bar.low)
        if len(self._highs) < self.params.swing_c_lookback_bars:
            return []
        trailing_high = max(self._highs)
        trailing_low = min(self._lows)
        return [
            _swing_event(
                "TRAILING_EXTREME_C",
                self.instrument,
                self.timeframe,
                bar.close_time,
                bar.close_time,
                RULE_C,
                self.params.param_version,
                discriminator=f"{self.params.swing_c_lookback_bars}",
                price_high=trailing_high,
                price_low=trailing_low,
                attributes={"lookback_bars": self.params.swing_c_lookback_bars},
            )
        ]
