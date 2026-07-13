"""Shared synthetic-bar helpers for WP-A tests. Not collected by pytest itself
(pytest.ini restricts collection to `test_*.py`); imported by the `test_*.py`
modules in this package.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class Bar:
    """Minimal OHLCV bar with a tz-aware close_time -- the only field
    `core/prefix.py` and `core/runner.py` themselves rely on. `session` is
    optional (used by the prefix harness's session-boundary cut heuristic)."""

    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    session: Optional[str] = None


def make_5m_bars(start: datetime, n: int, start_price: float = 20000.0, step: float = 1.0) -> List[Bar]:
    """n deterministic 5m bars starting at `start` (tz-aware), monotonically
    increasing close_time, simple synthetic OHLC around a rising price."""
    bars = []
    price = start_price
    for i in range(n):
        ct = start + timedelta(minutes=5 * i)
        o = price
        c = price + step
        h = max(o, c) + 0.5
        lo = min(o, c) - 0.5
        bars.append(Bar(close_time=ct, open=o, high=h, low=lo, close=c, volume=100.0 + i))
        price = c
    return bars


def make_bars_from_closes(start: datetime, closes: List[float]) -> List[Bar]:
    """Deterministic 5m bars with an explicit, hand-picked close sequence
    (e.g. a non-monotonic zigzag) -- needed for tests where "the price only
    ever goes up" would make a running-max/running-extreme bug invisible."""
    bars = []
    prev = closes[0] - 1.0
    for i, c in enumerate(closes):
        ct = start + timedelta(minutes=5 * i)
        o = prev
        h = max(o, c) + 0.5
        lo = min(o, c) - 0.5
        bars.append(Bar(close_time=ct, open=o, high=h, low=lo, close=c, volume=100.0 + i))
        prev = c
    return bars
