"""Opening range (SPEC.md "Engine definitions (v0 pins)" -> "Opening range"):
09:30 ET anchor, `or_duration_minutes` window (v0=15; param family {5,15,30}).

Per CME trade_date, every bar whose `close_time` falls in the half-open-on-
the-left window `(09:30 ET, 09:30 ET + duration]` contributes to that date's
opening range:

  - a bar closing STRICTLY BEFORE the window's end -> `OR_DEVELOPING`
    (explicitly flagged `developing=True`), running high/low as of that bar.
  - a bar closing EXACTLY AT the window's end -> `OR_COMPLETED`, final
    high/low over every bar seen in the window (including this one).
  - a bar closing AFTER the window's end, seen BEFORE any exact-boundary bar
    (gap/missing-bar case -- e.g. the 09:45 bar itself is missing) ->
    `OR_COMPLETED` is finalized on THIS triggering bar (we only learn the
    window is over once we've actually observed a bar proving time has
    passed it -- causal), using ONLY the bars already accumulated STRICTLY
    inside the window (the triggering bar's own H/L is outside the window
    and is NOT folded in).

`origin_time` for every event of a given trade_date is the nominal 09:30 ET
session-open instant for that date (calendar fact, not derived from any
bar); `confirmed_at` is the triggering bar's own `close_time`.

If a trade_date's window never receives a single bar (a total data gap over
the whole 09:30-09:30+duration span), no event is fabricated for it -- there
is no candidate to report (nothing was observed), so nothing is emitted; the
window is still marked resolved so a later out-of-window bar cannot
retroactively "complete" it.
"""
from __future__ import annotations

from datetime import datetime as _datetime
from datetime import time, timedelta
from typing import Any, Dict, List, Optional

from ..core.clock import NY, SessionEngine
from ..core.config import ICT_V2_PARAMS_V0, ParamSet
from ..core.events import CausalEvent, compute_event_id
from ._util import BucketHL, next_actionable

RULE_VERSION = "OPENING_RANGE_V0"


class OpeningRangeEngine:
    def __init__(
        self,
        instrument: str = "NQ",
        timeframe: str = "5m",
        params: ParamSet = ICT_V2_PARAMS_V0,
        duration_minutes: Optional[int] = None,
    ) -> None:
        self.instrument = instrument
        self.timeframe = timeframe
        self.params = params
        self.duration_minutes = (
            duration_minutes if duration_minutes is not None else params.or_duration_minutes_default
        )
        if self.duration_minutes not in params.or_duration_minutes_options:
            raise ValueError(
                f"duration_minutes ({self.duration_minutes}) must be one of "
                f"{params.or_duration_minutes_options}"
            )
        self._sessions = SessionEngine()
        self._accum: Dict[Any, dict] = {}  # trade_date -> {"high","low","n_bars"}
        self._resolved: set = set()

    def _window(self, trade_date):
        session_open = _datetime.combine(trade_date, time(9, 30), tzinfo=NY)
        window_end = session_open + timedelta(minutes=self.duration_minutes)
        return session_open, window_end

    def _event(self, event_type: str, trade_date, origin_time, confirmed_at, high, low, developing: bool, n_bars: int) -> CausalEvent:
        # discriminator includes confirmed_at: OR_DEVELOPING fires once per bar within
        # the window (same origin_time/trade_date each time), so trade_date alone would
        # collide across bars -- the triggering bar's own close_time disambiguates.
        eid = compute_event_id(
            event_type, self.instrument, origin_time, RULE_VERSION,
            discriminator=f"{trade_date}|{confirmed_at.isoformat()}",
        )
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
            price_low=low,
            price_high=high,
            attributes={
                "trade_date": str(trade_date),
                "duration_minutes": self.duration_minutes,
                "developing": developing,
                "n_bars": n_bars,
            },
        )

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        trade_date = self._sessions.trade_date(bar.close_time)
        if trade_date in self._resolved:
            return []
        session_open, window_end = self._window(trade_date)

        if bar.close_time <= session_open:
            return []  # not yet in the OR window at all

        if bar.close_time > window_end:
            # gap/missing-bar: OR window has elapsed without an exact-boundary bar.
            acc = self._accum.pop(trade_date, None)
            self._resolved.add(trade_date)
            if acc is None:
                return []  # total data gap over the window: nothing was ever observed
            return [
                self._event(
                    "OR_COMPLETED", trade_date, session_open, bar.close_time,
                    acc["high"], acc["low"], developing=False, n_bars=acc["n_bars"],
                )
            ]

        acc = self._accum.get(trade_date)
        if acc is None:
            acc = {"high": bar.high, "low": bar.low, "n_bars": 0}
            self._accum[trade_date] = acc
        else:
            acc["high"] = max(acc["high"], bar.high)
            acc["low"] = min(acc["low"], bar.low)
        acc["n_bars"] += 1

        if bar.close_time == window_end:
            self._resolved.add(trade_date)
            del self._accum[trade_date]
            return [
                self._event(
                    "OR_COMPLETED", trade_date, session_open, bar.close_time,
                    acc["high"], acc["low"], developing=False, n_bars=acc["n_bars"],
                )
            ]

        return [
            self._event(
                "OR_DEVELOPING", trade_date, session_open, bar.close_time,
                acc["high"], acc["low"], developing=True, n_bars=acc["n_bars"],
            )
        ]
