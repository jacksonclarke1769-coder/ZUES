"""Overnight inventory (SPEC.md "Engine definitions (v0 pins)" -> "Overnight
inventory"): at 09:30 ET, overnight H/L/range (18:00 ET prior day -> 09:30 ET,
`core.clock`'s `in_overnight` flag), gap vs prior RTH close, overnight net
return.

Bars are bucketed by CME `trade_date` (the 18:00 ET roll already places the
whole overnight span -- prior evening through this morning -- on the SAME
trade_date as the day it feeds into, `core/clock.py`). `prior_rth_close` is
the close of the last bar seen with `in_overnight=False` immediately before
this trade_date's overnight span began -- snapshotted the instant the first
`in_overnight=True` bar of the trade_date is seen (causal: only ever looks
at bars already processed).

The event fires on the FIRST bar of the trade_date whose primary session
flips to `ny_am` (09:30 ET) -- gap-tolerant the same way as
`opening_range.py` (a missing exact-09:30 bar just means the trigger is
whichever ny_am bar arrives first). `OVERNIGHT_COMPLETED` carries
`overnight_high`/`overnight_low` (as `price_high`/`price_low`),
`overnight_range`, `gap_vs_prior_rth_close` (this trigger bar's OPEN minus
`prior_rth_close` -- the actual price gap at the cash open) and
`overnight_net_return` (the overnight session's own drift: last overnight
bar's close vs `prior_rth_close`).

If either the overnight accumulation or `prior_rth_close` is unavailable
(stream/data warmup -- e.g. the very first trading day in a dataset, or a
trade_date with zero overnight bars) `OVERNIGHT_WARMUP` is emitted instead;
nothing is ever fabricated.
"""
from __future__ import annotations

from datetime import datetime as _datetime
from datetime import time
from typing import Any, Dict, List, Optional

from ..core.clock import NY, SessionEngine
from ..core.config import ICT_V2_PARAMS_V0, ParamSet
from ..core.events import CausalEvent, compute_event_id
from ._util import next_actionable

RULE_VERSION = "OVERNIGHT_V0"


class OvernightEngine:
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
        self._accum: Dict[Any, dict] = {}
        self._prior_rth_close_for_date: Dict[Any, Optional[float]] = {}
        self._last_non_overnight_close: Optional[float] = None
        self._resolved: set = set()

    def _event(
        self,
        event_type: str,
        trade_date,
        confirmed_at,
        high: Optional[float],
        low: Optional[float],
        attributes: dict,
    ) -> CausalEvent:
        origin_time = _datetime.combine(trade_date, time(9, 30), tzinfo=NY)
        eid = compute_event_id(
            event_type, self.instrument, origin_time, RULE_VERSION, discriminator=str(trade_date)
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
            attributes={"trade_date": str(trade_date), **attributes},
        )

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        flags = self._sessions.flags(bar.close_time)
        trade_date = self._sessions.trade_date(bar.close_time)
        in_overnight = flags["in_overnight"]

        if in_overnight:
            acc = self._accum.get(trade_date)
            if acc is None:
                acc = {"high": bar.high, "low": bar.low, "n_bars": 0, "last_close": bar.close}
                self._accum[trade_date] = acc
                self._prior_rth_close_for_date[trade_date] = self._last_non_overnight_close
            else:
                acc["high"] = max(acc["high"], bar.high)
                acc["low"] = min(acc["low"], bar.low)
            acc["n_bars"] += 1
            acc["last_close"] = bar.close
            return []

        self._last_non_overnight_close = bar.close

        session_label = self._sessions.session(bar.close_time)
        if session_label != "ny_am" or trade_date in self._resolved:
            return []

        self._resolved.add(trade_date)
        acc = self._accum.pop(trade_date, None)
        prior_close = self._prior_rth_close_for_date.pop(trade_date, None)

        if acc is None or prior_close is None:
            missing = []
            if acc is None:
                missing.append("no_overnight_bars")
            if prior_close is None:
                missing.append("no_prior_rth_close")
            return [
                self._event(
                    "OVERNIGHT_WARMUP",
                    trade_date,
                    bar.close_time,
                    None,
                    None,
                    {"reason": missing, "n_overnight_bars": 0 if acc is None else acc["n_bars"]},
                )
            ]

        gap = bar.open - prior_close
        net_return = (acc["last_close"] - prior_close) / prior_close if prior_close != 0 else None
        return [
            self._event(
                "OVERNIGHT_COMPLETED",
                trade_date,
                bar.close_time,
                acc["high"],
                acc["low"],
                {
                    "overnight_range": acc["high"] - acc["low"],
                    "prior_rth_close": prior_close,
                    "gap_vs_prior_rth_close": gap,
                    "overnight_net_return": net_return,
                    "n_overnight_bars": acc["n_bars"],
                },
            )
        ]
