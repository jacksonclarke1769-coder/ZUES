"""Shared, pure helpers used by multiple WP-B detector engines (SPEC.md
"Engine definitions (v0 pins)"). Nothing here emits events or holds
cross-engine state -- every engine still computes its own numbers from bars
it has itself seen (BatchRunner's "engines never share state or read each
other's events" rule, `core/runner.py`); this module only avoids literally
duplicating the same causal math (rolling means, session-boundary walks,
tick rounding, ...) across `engines/*.py` files.
"""
from __future__ import annotations

from collections import deque
from datetime import date, datetime, time, timedelta
from typing import Deque, Dict, List, Optional, Tuple

from ..core.clock import NY, PRIMARY_ORDER, SessionEngine

# --- bar timing --------------------------------------------------------------

_TIMEFRAME_MINUTES: Dict[str, int] = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}


def bar_duration(timeframe: str) -> timedelta:
    if timeframe not in _TIMEFRAME_MINUTES:
        raise ValueError(f"unknown timeframe {timeframe!r}; add it to _TIMEFRAME_MINUTES")
    return timedelta(minutes=_TIMEFRAME_MINUTES[timeframe])


def next_actionable(confirmed_at: datetime, timeframe: str) -> datetime:
    """actionable_at = next bar or later: confirmed_at + one bar's duration,
    computed purely from the timeframe convention (never by peeking at the
    next actual bar) so it stays causal/deterministic."""
    return confirmed_at + bar_duration(timeframe)


# --- rolling causal statistics -------------------------------------------------


class RollingMean:
    """Causal rolling mean over the PRIOR `window` samples (current sample is
    NOT included in its own mean) -- mirrors pandas' `.shift(1).rolling(window)
    .mean()` used throughout the frozen `primitives.py` oracle. `update(x)`
    returns the mean available BEFORE `x` is folded in (None during warmup),
    then folds `x` into the window for subsequent calls."""

    def __init__(self, window: int) -> None:
        self.window = window
        self._buf: Deque[float] = deque(maxlen=window)

    def update(self, x: float) -> Optional[float]:
        prior_mean = (sum(self._buf) / len(self._buf)) if len(self._buf) == self.window else None
        self._buf.append(x)
        return prior_mean

    @property
    def ready(self) -> bool:
        return len(self._buf) == self.window


class RollingMeanStd:
    """Causal rolling (mean, population-std) over the prior `window` samples,
    same shift-by-one convention as `RollingMean`."""

    def __init__(self, window: int) -> None:
        self.window = window
        self._buf: Deque[float] = deque(maxlen=window)

    def update(self, x: float) -> Tuple[Optional[float], Optional[float]]:
        if len(self._buf) == self.window:
            n = len(self._buf)
            mean = sum(self._buf) / n
            var = sum((v - mean) ** 2 for v in self._buf) / n
            prior = (mean, var**0.5)
        else:
            prior = (None, None)
        self._buf.append(x)
        return prior

    @property
    def ready(self) -> bool:
        return len(self._buf) == self.window


class RollingMedian:
    """Causal rolling median over the PRIOR `window` samples (current sample
    excluded from its own median, same shift-by-one convention as
    `RollingMean`). Used for displacement's `sigma_TOD` (median |5m return|
    for a given time-of-day slot over the trailing N occurrences of that
    slot -- SPEC.md "Displacement")."""

    def __init__(self, window: int) -> None:
        self.window = window
        self._buf: Deque[float] = deque(maxlen=window)

    def update(self, x: float) -> Optional[float]:
        if len(self._buf) == self.window:
            ordered = sorted(self._buf)
            mid = self.window // 2
            prior = ordered[mid] if self.window % 2 == 1 else (ordered[mid - 1] + ordered[mid]) / 2
        else:
            prior = None
        self._buf.append(x)
        return prior

    @property
    def ready(self) -> bool:
        return len(self._buf) == self.window


class RollingWindow:
    """Causal rolling window of the last `n` completed samples (includes the
    current one being folded in) -- used for Method-C trailing extremes and
    True-Range/ATR accumulation."""

    def __init__(self, window: int) -> None:
        self.window = window
        self._buf: Deque[float] = deque(maxlen=window)

    def push(self, x: float) -> None:
        self._buf.append(x)

    @property
    def ready(self) -> bool:
        return len(self._buf) == self.window

    @property
    def values(self) -> List[float]:
        return list(self._buf)


def body(o: float, c: float) -> float:
    return abs(c - o)


def true_range(high: float, low: float, prev_close: Optional[float]) -> float:
    if prev_close is None:
        return high - low
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


class ATR:
    """Causal ATR(window): simple rolling mean of True Range, INCLUSIVE of the
    current bar -- mirrors the oracle's own convention (`models/model01_sweep_
    mss_fvg.py`'s `atr_arr = pd.Series(_tr).rolling(14).mean()`, NOT shifted),
    unlike `RollingMean`'s prior-only convention used for displacement's body
    ratio (`primitives.py::body_ratio` IS shifted). `update()` returns None
    during warmup (fewer than `window` bars seen, including this one)."""

    def __init__(self, window: int) -> None:
        self.window = window
        self._buf: Deque[float] = deque(maxlen=window)
        self._prev_close: Optional[float] = None

    def update(self, high: float, low: float, close: float) -> Optional[float]:
        tr = true_range(high, low, self._prev_close)
        self._prev_close = close
        self._buf.append(tr)
        if len(self._buf) < self.window:
            return None
        return sum(self._buf) / self.window


# --- tick helpers --------------------------------------------------------------


def ticks(points: float, tick_size: float) -> float:
    return points / tick_size


def within_ticks(a: float, b: float, tick_size: float, max_ticks: float) -> bool:
    return abs(a - b) <= max_ticks * tick_size + 1e-9


def is_round_number(price: float, step: float, tick_size: float) -> bool:
    remainder = price % step
    return remainder <= tick_size / 2 + 1e-9 or (step - remainder) <= tick_size / 2 + 1e-9


# --- bucketed high/low accumulation (day / week / session / windowed) ---------


class BucketHL:
    """Accumulates running (high, low, last_close, first_bar_close_time,
    last_bar_close_time, n_bars) per bucket key. Causal: `update(key, bar)`
    returns the FINALIZED previous bucket's tuple the instant `key` changes
    (i.e. the moment a bar belonging to a NEW bucket is seen -- we only ever
    look at bars already fed, never a bucket we haven't reached yet), else
    None while the current bucket is still open."""

    def __init__(self) -> None:
        self._key = None
        self._hi: Optional[float] = None
        self._lo: Optional[float] = None
        self._last_close: Optional[float] = None
        self._first_close_time: Optional[datetime] = None
        self._last_close_time: Optional[datetime] = None
        self._n = 0

    def update(self, key, bar) -> Optional[dict]:
        finalized = None
        if self._key is not None and key != self._key:
            finalized = {
                "key": self._key,
                "high": self._hi,
                "low": self._lo,
                "last_close": self._last_close,
                "first_close_time": self._first_close_time,
                "last_close_time": self._last_close_time,
                "n_bars": self._n,
            }
            self._key = None
        if self._key is None:
            self._key = key
            self._hi = bar.high
            self._lo = bar.low
            self._first_close_time = bar.close_time
            self._n = 0
        else:
            self._hi = max(self._hi, bar.high)
            self._lo = min(self._lo, bar.low)
        self._last_close = bar.close
        self._last_close_time = bar.close_time
        self._n += 1
        return finalized

    def current(self) -> Optional[dict]:
        if self._key is None:
            return None
        return {
            "key": self._key,
            "high": self._hi,
            "low": self._lo,
            "last_close": self._last_close,
            "first_close_time": self._first_close_time,
            "last_close_time": self._last_close_time,
            "n_bars": self._n,
        }


def trade_week_key(session_engine: SessionEngine, ts: datetime) -> Tuple[int, int]:
    d = session_engine.trade_date(ts)
    iso = d.isocalendar()
    return (iso[0], iso[1])


# --- deterministic session-boundary expiry walks (calendar math only; NEVER
# derived from future bars -- this is the same category of "known in advance"
# fact as the holiday calendar itself) -----------------------------------------


def _session_slots_for_trade_date(d: date) -> List[Tuple[str, datetime, datetime]]:
    """The 5 PRIMARY_ORDER session windows that belong to CME trade_date `d`,
    as tz-aware NY datetimes. asia's wall-clock window (18:00-24:00) sits on
    the PRECEDING calendar day but rolls forward into trade_date `d` (mirrors
    `SessionEngine.trade_date`'s +6h roll); the other four sit on calendar
    day `d` itself."""
    prev = d - timedelta(days=1)
    return [
        ("asia", datetime.combine(prev, time(18, 0), tzinfo=NY), datetime.combine(d, time(0, 0), tzinfo=NY)),
        ("london", datetime.combine(d, time(2, 0), tzinfo=NY), datetime.combine(d, time(5, 0), tzinfo=NY)),
        ("ny_am", datetime.combine(d, time(9, 30), tzinfo=NY), datetime.combine(d, time(11, 30), tzinfo=NY)),
        ("ny_lunch", datetime.combine(d, time(11, 30), tzinfo=NY), datetime.combine(d, time(13, 30), tzinfo=NY)),
        ("ny_pm", datetime.combine(d, time(13, 30), tzinfo=NY), datetime.combine(d, time(15, 0), tzinfo=NY)),
    ]


assert PRIMARY_ORDER == ["asia", "london", "ny_am", "ny_lunch", "ny_pm"], (
    "core/clock.py PRIMARY_ORDER changed; _session_slots_for_trade_date must be kept in sync"
)


def advance_sessions(session_engine: SessionEngine, start_ts: datetime, n: int) -> datetime:
    """The end-timestamp of the Nth PRIMARY_ORDER sub-session window (of a
    TRADING day) whose end is strictly after `start_ts`. Used for `expires_at`
    of "intraday"-class levels (v0: 2 sessions)."""
    if n <= 0:
        raise ValueError("n must be >= 1")
    d = session_engine.trade_date(start_ts)
    count = 0
    guard = 0
    while True:
        guard += 1
        if guard > 60:
            raise RuntimeError("advance_sessions: exceeded search guard (bad calendar data?)")
        if session_engine.is_trading_day(d):
            for _name, _start, end in _session_slots_for_trade_date(d):
                if end > start_ts:
                    count += 1
                    if count == n:
                        return end
        d = d + timedelta(days=1)


def advance_trading_days(session_engine: SessionEngine, start_ts: datetime, n: int) -> datetime:
    """The close (ny_pm end, 15:00 ET) of the Nth subsequent CME TRADING day
    after `start_ts`'s trade_date. Used for `expires_at` of "weekly"-class
    levels (v0: 5 trading days)."""
    if n <= 0:
        raise ValueError("n must be >= 1")
    d = session_engine.trade_date(start_ts)
    count = 0
    guard = 0
    while count < n:
        guard += 1
        if guard > 400:
            raise RuntimeError("advance_trading_days: exceeded search guard (bad calendar data?)")
        d = d + timedelta(days=1)
        if session_engine.is_trading_day(d):
            count += 1
    return datetime.combine(d, time(15, 0), tzinfo=NY)
