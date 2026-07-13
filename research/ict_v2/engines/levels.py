"""Levels (SPEC.md "Engine definitions (v0 pins)" -> "Levels"): the level
registry. A single `LevelRegistry` engine tracks every level KIND named in
SPEC.md simultaneously and manages its full lifecycle
(`LEVEL_CREATED` -> zero or more `LEVEL_TESTED` -> optional `LEVEL_EXPIRED`).

Kinds (`attributes["kind"]` on every level event):
  - `pdh` / `pdl`           -- prior CME trade_date's high/low.
  - `pwh` / `pwl`           -- prior ISO trading-week's high/low.
  - `session_high` / `session_low` (attributes["session"] in {asia, london,
    ny_am}) -- prior occurrence of that named session's high/low (SPEC.md
    names exactly these three sessions, not ny_lunch/ny_pm).
  - `or_high` / `or_low`    -- the completed opening range (v0 duration,
    `or_duration_minutes_default`) high/low. Computed INTERNALLY here (SPEC.md
    gives either choice explicitly; consuming `opening_range.py`'s emitted
    events would violate BatchRunner's "engines never share state/read each
    other's events" rule, `core/runner.py`, so this mirrors the same window
    logic independently instead).
  - `overnight_high` / `overnight_low` -- likewise computed internally,
    mirroring `overnight.py`'s accumulation independently.
  - `swing_high_a` / `swing_low_a` -- every confirmed Method-A pivot
    (`engines/swings.py::SwingMethodA`, run as a private internal instance).
  - `equal_highs` / `equal_lows` -- >=2 Method-A pivots of the same type
    within `equal_level_tolerance_ticks`, >= `equal_level_min_bars_apart`
    origin bars apart, both within `equal_level_max_sessions_old` PRIMARY
    sub-sessions of each other; level price = the OUTERMOST of the matching
    pivots (higher for highs, lower for lows).
  - `round_number_major` / `round_number_minor` -- multiples of
    `round_number_step` (100) / `round_number_minor_step` (50), registered
    lazily the first time a bar's [low, high] range actually touches one
    (unbounded pre-registration across all possible NQ prices is not
    meaningful; "all candidates" here means all round numbers price has
    actually reached).

Every level's `expires_at` is set at creation from a `timeframe_class`
("intraday" -> 2 sub-sessions, "weekly" -> 5 trading days, SPEC.md v0):
`pwh`/`pwl` are "weekly"; everything else is "intraday" (documented choice --
SPEC.md's 2-value expiry table maps naturally onto exactly two timeframe
classes). `active_from` = the creation event's own `actionable_at` (a level
can only be tested starting when it was itself actionable).

Salience is recorded as raw COMPONENTS on `LEVEL_CREATED` (SPEC.md: "NO
weights, NO score"): `timeframe_class`, `prominence_above_pts` /
`prominence_below_pts` (distance to the nearest already-known Method-A swing
price on each side, `None` if none known yet), `roundness_major` /
`roundness_minor` (bool), `equality_count` (2 for equal-H/L levels, else 1).
`LEVEL_TESTED` carries the running `test_count` and `age_seconds` (time since
`created_at`).
"""
from __future__ import annotations

import math
from datetime import datetime as _datetime
from datetime import time, timedelta
from typing import Any, Dict, List, Optional

from ..core.clock import NY, SessionEngine
from ..core.config import ICT_V2_PARAMS_V0, ParamSet
from ..core.events import CausalEvent, compute_event_id
from ._util import BucketHL, advance_sessions, advance_trading_days, is_round_number, next_actionable, trade_week_key
from .swings import SwingMethodA

RULE_VERSION = "LEVELS_V0"

_WEEKLY_KINDS = {"pwh", "pwl"}
_SESSION_KIND_NAMES = ("asia", "london", "ny_am")


def _timeframe_class(kind: str) -> str:
    return "weekly" if kind in _WEEKLY_KINDS else "intraday"


class _LevelState:
    __slots__ = (
        "created_event_id", "kind", "price", "created_at", "active_from",
        "expires_at", "test_count", "last_test_at", "expired",
    )

    def __init__(self, created_event_id, kind, price, created_at, active_from, expires_at):
        self.created_event_id = created_event_id
        self.kind = kind
        self.price = price
        self.created_at = created_at
        self.active_from = active_from
        self.expires_at = expires_at
        self.test_count = 0
        self.last_test_at: Optional[Any] = None
        self.expired = False


class LevelRegistry:
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

        self._day_hl = BucketHL()
        self._week_hl = BucketHL()
        self._session_hl = {name: BucketHL() for name in _SESSION_KIND_NAMES}

        self._or_accum: Dict[Any, dict] = {}
        self._or_resolved: set = set()

        self._overnight_accum: Dict[Any, dict] = {}
        self._overnight_resolved: set = set()

        self._swings = SwingMethodA(instrument, timeframe, params)
        self._known_swing_prices: List[float] = []  # causal history, price only, for prominence
        self._recent_pivot_highs: List[dict] = []
        self._recent_pivot_lows: List[dict] = []

        self._registered_round_numbers: set = set()  # (step, price)

        self._active: List[_LevelState] = []

        self._bar_index = -1
        self._time_to_index: Dict[Any, int] = {}
        self._session_index = 0
        self._last_session_label: Optional[str] = None

    # -- shared event builder ---------------------------------------------------

    def _make_created(
        self,
        kind: str,
        price: float,
        origin_time,
        confirmed_at,
        salience: dict,
        discriminator: str,
    ) -> CausalEvent:
        eid = compute_event_id("LEVEL_CREATED", self.instrument, origin_time, RULE_VERSION, discriminator=discriminator)
        actionable = next_actionable(confirmed_at, self.timeframe)
        tf_class = _timeframe_class(kind)
        expires_at = (
            advance_trading_days(self._sessions, confirmed_at, self.params.level_expiry_sessions_weekly)
            if tf_class == "weekly"
            else advance_sessions(self._sessions, confirmed_at, self.params.level_expiry_sessions_intraday)
        )
        event = CausalEvent(
            event_id=eid,
            event_type="LEVEL_CREATED",
            instrument=self.instrument,
            timeframe=self.timeframe,
            origin_time=origin_time,
            observed_at=confirmed_at,
            confirmed_at=confirmed_at,
            actionable_at=actionable,
            rule_version=RULE_VERSION,
            param_version=self.params.param_version,
            price_low=price,
            price_high=price,
            attributes={
                "kind": kind,
                "price": price,
                "expires_at": expires_at,
                **salience,
            },
        )
        state = _LevelState(event.event_id, kind, price, confirmed_at, actionable, expires_at)
        self._active.append(state)
        return event

    def _salience(self, kind: str, price: float, equality_count: int = 1) -> dict:
        above = min((p for p in self._known_swing_prices if p > price), default=None)
        below = max((p for p in self._known_swing_prices if p < price), default=None)
        return {
            "timeframe_class": _timeframe_class(kind),
            "prominence_above_pts": (above - price) if above is not None else None,
            "prominence_below_pts": (price - below) if below is not None else None,
            "roundness_major": is_round_number(price, self.params.round_number_step, self.params.tick_size),
            "roundness_minor": is_round_number(price, self.params.round_number_minor_step, self.params.tick_size),
            "equality_count": equality_count,
        }

    # -- lifecycle: test / expire -------------------------------------------------

    def _test_and_expire(self, bar: Any) -> List[CausalEvent]:
        events: List[CausalEvent] = []
        tol = self.params.level_test_tolerance_ticks * self.params.tick_size
        for lvl in self._active:
            if lvl.expired:
                continue
            if bar.close_time >= lvl.active_from and (bar.low - tol) <= lvl.price <= (bar.high + tol):
                lvl.test_count += 1
                lvl.last_test_at = bar.close_time
                eid = compute_event_id(
                    "LEVEL_TESTED", self.instrument, bar.close_time, RULE_VERSION,
                    discriminator=f"{lvl.created_event_id}|{lvl.test_count}",
                )
                events.append(
                    CausalEvent(
                        event_id=eid,
                        event_type="LEVEL_TESTED",
                        instrument=self.instrument,
                        timeframe=self.timeframe,
                        origin_time=bar.close_time,
                        observed_at=bar.close_time,
                        confirmed_at=bar.close_time,
                        actionable_at=next_actionable(bar.close_time, self.timeframe),
                        rule_version=RULE_VERSION,
                        param_version=self.params.param_version,
                        price_low=lvl.price,
                        price_high=lvl.price,
                        source_event_ids=(lvl.created_event_id,),
                        attributes={
                            "kind": lvl.kind,
                            "test_count": lvl.test_count,
                            "age_seconds": (bar.close_time - lvl.created_at).total_seconds(),
                        },
                    )
                )
            if not lvl.expired and bar.close_time >= lvl.expires_at:
                lvl.expired = True
                eid = compute_event_id(
                    "LEVEL_EXPIRED", self.instrument, lvl.expires_at, RULE_VERSION,
                    discriminator=lvl.created_event_id,
                )
                events.append(
                    CausalEvent(
                        event_id=eid,
                        event_type="LEVEL_EXPIRED",
                        instrument=self.instrument,
                        timeframe=self.timeframe,
                        origin_time=lvl.expires_at,
                        observed_at=bar.close_time,
                        confirmed_at=bar.close_time,
                        actionable_at=next_actionable(bar.close_time, self.timeframe),
                        rule_version=RULE_VERSION,
                        param_version=self.params.param_version,
                        price_low=lvl.price,
                        price_high=lvl.price,
                        source_event_ids=(lvl.created_event_id,),
                        attributes={"kind": lvl.kind, "test_count": lvl.test_count},
                    )
                )
        return events

    # -- bucket-based kinds (pdh/pdl, pwh/pwl, session H/L) ------------------------

    def _bucket_events(self, bar: Any) -> List[CausalEvent]:
        events: List[CausalEvent] = []
        trade_date = self._sessions.trade_date(bar.close_time)

        finalized = self._day_hl.update(trade_date, bar)
        if finalized:
            events.append(self._finalize_bucket_level("pdh", finalized["high"], finalized, bar.close_time))
            events.append(self._finalize_bucket_level("pdl", finalized["low"], finalized, bar.close_time))

        week_key = trade_week_key(self._sessions, bar.close_time)
        finalized = self._week_hl.update(week_key, bar)
        if finalized:
            events.append(self._finalize_bucket_level("pwh", finalized["high"], finalized, bar.close_time))
            events.append(self._finalize_bucket_level("pwl", finalized["low"], finalized, bar.close_time))

        label = self._sessions.session(bar.close_time)
        if label in self._session_hl:
            finalized = self._session_hl[label].update(trade_date, bar)
            if finalized:
                events.append(
                    self._finalize_bucket_level(f"session_high", finalized["high"], finalized, bar.close_time, extra={"session": label})
                )
                events.append(
                    self._finalize_bucket_level(f"session_low", finalized["low"], finalized, bar.close_time, extra={"session": label})
                )
        return events

    def _finalize_bucket_level(self, kind: str, price: float, finalized: dict, confirmed_at, extra: Optional[dict] = None) -> CausalEvent:
        salience = self._salience(kind, price)
        if extra:
            salience.update(extra)
        disc = f"{kind}|{finalized['key']}|{price:.6f}"
        return self._make_created(kind, price, finalized["last_close_time"], confirmed_at, salience, disc)

    # -- opening range (internal) --------------------------------------------------

    def _or_events(self, bar: Any) -> List[CausalEvent]:
        trade_date = self._sessions.trade_date(bar.close_time)
        if trade_date in self._or_resolved:
            return []
        session_open = _datetime.combine(trade_date, time(9, 30), tzinfo=NY)
        window_end = session_open + timedelta(minutes=self.params.or_duration_minutes_default)
        if bar.close_time <= session_open:
            return []
        if bar.close_time > window_end:
            acc = self._or_accum.pop(trade_date, None)
            self._or_resolved.add(trade_date)
            if acc is None:
                return []
            return self._finalize_or(trade_date, session_open, bar.close_time, acc)
        acc = self._or_accum.get(trade_date)
        if acc is None:
            acc = {"high": bar.high, "low": bar.low}
            self._or_accum[trade_date] = acc
        else:
            acc["high"] = max(acc["high"], bar.high)
            acc["low"] = min(acc["low"], bar.low)
        if bar.close_time == window_end:
            self._or_resolved.add(trade_date)
            del self._or_accum[trade_date]
            return self._finalize_or(trade_date, session_open, bar.close_time, acc)
        return []

    def _finalize_or(self, trade_date, session_open, confirmed_at, acc: dict) -> List[CausalEvent]:
        events = []
        for kind, price in (("or_high", acc["high"]), ("or_low", acc["low"])):
            salience = self._salience(kind, price)
            disc = f"{kind}|{trade_date}|{price:.6f}"
            events.append(self._make_created(kind, price, session_open, confirmed_at, salience, disc))
        return events

    # -- overnight (internal) -------------------------------------------------------

    def _overnight_events(self, bar: Any) -> List[CausalEvent]:
        flags = self._sessions.flags(bar.close_time)
        trade_date = self._sessions.trade_date(bar.close_time)
        if flags["in_overnight"]:
            acc = self._overnight_accum.get(trade_date)
            if acc is None:
                acc = {"high": bar.high, "low": bar.low}
                self._overnight_accum[trade_date] = acc
            else:
                acc["high"] = max(acc["high"], bar.high)
                acc["low"] = min(acc["low"], bar.low)
            return []
        label = self._sessions.session(bar.close_time)
        if label != "ny_am" or trade_date in self._overnight_resolved:
            return []
        self._overnight_resolved.add(trade_date)
        acc = self._overnight_accum.pop(trade_date, None)
        if acc is None:
            return []
        origin = _datetime.combine(trade_date, time(9, 30), tzinfo=NY)
        events = []
        for kind, price in (("overnight_high", acc["high"]), ("overnight_low", acc["low"])):
            salience = self._salience(kind, price)
            disc = f"{kind}|{trade_date}|{price:.6f}"
            events.append(self._make_created(kind, price, origin, bar.close_time, salience, disc))
        return events

    # -- Method-A swings + equal highs/lows ------------------------------------------

    def _swing_events(self, bar: Any) -> List[CausalEvent]:
        events: List[CausalEvent] = []
        for ev in self._swings.on_bar(bar):
            is_high = ev.event_type == "SWING_HIGH_A"
            price = ev.price_high if is_high else ev.price_low
            self._known_swing_prices.append(price)
            kind = "swing_high_a" if is_high else "swing_low_a"
            salience = self._salience(kind, price)
            disc = f"{kind}|{ev.origin_time.isoformat()}|{price:.6f}"
            events.append(self._make_created(kind, price, ev.origin_time, ev.confirmed_at, salience, disc))
            events.extend(self._check_equal(is_high, price, ev))
        return events

    def _check_equal(self, is_high: bool, price: float, swing_event: CausalEvent) -> List[CausalEvent]:
        tol = self.params.equal_level_tolerance_ticks * self.params.tick_size
        bucket = self._recent_pivot_highs if is_high else self._recent_pivot_lows
        min_apart = self.params.equal_level_min_bars_apart
        max_age = self.params.equal_level_max_sessions_old
        new_index = self._time_to_index.get(swing_event.origin_time, self._bar_index)
        new_session = self._session_index

        # prune stale entries
        bucket[:] = [e for e in bucket if (new_session - e["session_index"]) <= max_age]

        match = None
        for entry in bucket:
            if abs(entry["bar_index"] - new_index) < min_apart:
                continue
            if abs(entry["price"] - price) > tol:
                continue
            match = entry
            break

        events: List[CausalEvent] = []
        if match is not None:
            outer_price = max(price, match["price"]) if is_high else min(price, match["price"])
            kind = "equal_highs" if is_high else "equal_lows"
            salience = self._salience(kind, outer_price, equality_count=2)
            disc = f"{kind}|{swing_event.event_id}|{match['event_id']}"
            events.append(
                self._make_created(kind, outer_price, swing_event.origin_time, swing_event.confirmed_at, salience, disc)
            )

        bucket.append(
            {"price": price, "bar_index": new_index, "session_index": new_session, "event_id": swing_event.event_id}
        )
        return events

    # -- round numbers ---------------------------------------------------------------

    def _round_number_events(self, bar: Any) -> List[CausalEvent]:
        events: List[CausalEvent] = []
        for step, kind in (
            (self.params.round_number_step, "round_number_major"),
            (self.params.round_number_minor_step, "round_number_minor"),
        ):
            v = math.ceil(bar.low / step) * step
            while v <= bar.high + 1e-9:
                key = (step, round(v, 6))
                if key not in self._registered_round_numbers:
                    self._registered_round_numbers.add(key)
                    salience = self._salience(kind, v)
                    disc = f"{kind}|{v:.6f}"
                    events.append(self._make_created(kind, v, bar.close_time, bar.close_time, salience, disc))
                v += step
        return events

    # -- bar-index / session-index bookkeeping ---------------------------------------

    def _advance_counters(self, bar: Any) -> None:
        self._bar_index += 1
        self._time_to_index[bar.close_time] = self._bar_index
        label = self._sessions.session(bar.close_time)
        if self._last_session_label is not None and label != self._last_session_label:
            self._session_index += 1
        self._last_session_label = label

    # -- main loop ---------------------------------------------------------------------

    def on_bar(self, bar: Any) -> List[CausalEvent]:
        self._advance_counters(bar)
        events: List[CausalEvent] = []
        events.extend(self._bucket_events(bar))
        events.extend(self._or_events(bar))
        events.extend(self._overnight_events(bar))
        events.extend(self._swing_events(bar))
        events.extend(self._round_number_events(bar))
        events.extend(self._test_and_expire(bar))
        return events
