"""SessionEngine: CME/NY session tagging, trade-date roll, holidays, DST-safe.

All logic operates on tz-aware datetimes and converts to America/New_York via
`zoneinfo` (`datetime.astimezone(NY)`) -- never via `tz_localize` on a naive
wall-clock string (the D1c bug class: hard-coding a local-time string and
localizing it directly mishandles DST fold/gap edge cases and silently drifts
on the transition day).

Session windows below are picked to MIRROR the frozen framework's own session
tagging bar-for-bar (`~/trading-team/backtests/ict-nq-framework/engine/data.py`
-- `SESSIONS` / `PRIMARY_ORDER`, verified read-only 2026-07-13), because WP-D's
parity canary must reproduce model01's 581 certified signals exactly and any
session-window drift would silently break that. This DIVERGES from the
illustrative windows written in SPEC.md's "Core contracts" prose (asia
18:00-03:00, london 03:00-08:00, ny_am 08:00-12:00, ny_pm 12:00-16:00) -- see
the WP-A summary / divergence table for the full comparison; the `killzone`
name from SPEC.md is kept but is numerically identical to model01's `ny_am`
window (09:30-11:30 ET).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from types import MappingProxyType
from typing import Dict, Mapping, Optional
from zoneinfo import ZoneInfo

# --- robust read-only import of the bot repo's existing holiday calendar -----
# research/ict_v2/core/clock.py -> core -> ict_v2 -> research -> <repo root>
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import market_calendar as _mc  # noqa: E402  (bot repo root module, read-only import)

NY = ZoneInfo("America/New_York")

# Session windows in ET wall-clock, half-open [start, end). Mirrors model01's
# engine/data.py::SESSIONS EXACTLY.
SESSION_WINDOWS: Dict[str, tuple] = {
    "asia": ((18, 0), (24, 0)),
    "london": ((2, 0), (5, 0)),
    "ny_am": ((9, 30), (11, 30)),
    "ny_lunch": ((11, 30), (13, 30)),
    "ny_pm": ((13, 30), (15, 0)),
}
# Primary (non-overlapping) session label, decided in this order -- mirrors
# model01's PRIMARY_ORDER. A bar matching none of these is labelled "off".
PRIMARY_ORDER = ["asia", "london", "ny_am", "ny_lunch", "ny_pm"]

# SPEC.md's named NY-AM killzone: numerically == model01's ny_am window.
KILLZONE_WINDOW = ((9, 30), (11, 30))

# Overnight session (SPEC.md addition; not one of model01's primary labels):
# 18:00 ET -> 09:30 ET, the Globex session ahead of the NY cash open. Wraps midnight.
OVERNIGHT_WINDOW = ((18, 0), (9, 30))

# CME equity-index daily maintenance break: 17:00-18:00 ET (Sun-Thu evenings; the
# flag is purely time-of-day, callers combine it with is_trading_day for the date).
MAINTENANCE_WINDOW = ((17, 0), (18, 0))

# --- half-day (early close) schedule, ET, 13:00 close -------------------------
# market_calendar.py deliberately excludes half-days (see its module docstring:
# "Half-days ... are a separate concern and not here"). This is the standard
# published NYSE/CME-equity half-day schedule for 2021-2026 (day before
# Independence Day when a trading day, day after Thanksgiving, Christmas Eve when
# it falls Mon-Fri) -- computed by hand from the same USMarketCalendar rules
# market_calendar.py uses (nearest_workday observance), NOT sourced from
# market_calendar.py itself since it has no half-day data.
EARLY_CLOSE_DATES = frozenset(
    {
        date(2021, 11, 26), date(2021, 12, 24),
        date(2022, 7, 1), date(2022, 11, 25),
        date(2023, 7, 3), date(2023, 11, 24),
        date(2024, 7, 3), date(2024, 11, 29), date(2024, 12, 24),
        date(2025, 7, 3), date(2025, 11, 28), date(2025, 12, 24),
        date(2026, 7, 2), date(2026, 11, 27), date(2026, 12, 24),
    }
)
EARLY_CLOSE_TIME = time(13, 0)


def _require_tz_aware(ts) -> None:
    if getattr(ts, "tzinfo", None) is None:
        raise ValueError(
            f"SessionEngine requires tz-aware timestamps (got naive {ts!r}); never "
            "tz_localize a naive wall-clock string -- construct with an explicit tzinfo instead"
        )


def _in_window(mins: int, window: tuple) -> bool:
    (h0, m0), (h1, m1) = window
    a, b = h0 * 60 + m0, h1 * 60 + m1
    if a < b:
        return a <= mins < b
    return mins >= a or mins < b  # wraps midnight


@dataclass(frozen=True)
class SessionInfo:
    trade_date: date
    session: str
    flags: Mapping[str, bool]
    is_trading_day: bool
    is_holiday: bool
    is_early_close: bool


class SessionEngine:
    """Stateless session/calendar logic for NQ/ES-style CME equity-index futures.
    Every method takes a tz-aware timestamp; conversion to ET is via
    `datetime.astimezone(NY)` (zoneinfo), never tz_localize."""

    @staticmethod
    def _to_ny(ts: datetime) -> datetime:
        _require_tz_aware(ts)
        return ts.astimezone(NY)

    def trade_date(self, ts: datetime) -> date:
        """CME trade date: rolls forward at 18:00 ET (a bar at or after 18:00 ET
        belongs to the NEXT calendar day's trade date). Matches model01's
        `trading_day = (idx + 6h).normalize()` (adding 6 wall-clock hours pushes
        anything >=18:00 across midnight); verified equivalent across DST via
        zoneinfo's wall-clock timedelta arithmetic."""
        ny = self._to_ny(ts)
        return (ny + timedelta(hours=6)).date()

    def flags(self, ts: datetime) -> Dict[str, bool]:
        ny = self._to_ny(ts)
        mins = ny.hour * 60 + ny.minute
        out = {f"in_{name}": _in_window(mins, w) for name, w in SESSION_WINDOWS.items()}
        out["in_killzone"] = _in_window(mins, KILLZONE_WINDOW)
        out["in_overnight"] = _in_window(mins, OVERNIGHT_WINDOW)
        out["in_maintenance_break"] = _in_window(mins, MAINTENANCE_WINDOW)
        return out

    def session(self, ts: datetime) -> str:
        """Primary (non-overlapping) session label; "off" if none match. Mirrors
        model01's PRIMARY_ORDER mask-in-order logic."""
        f = self.flags(ts)
        for name in PRIMARY_ORDER:
            if f[f"in_{name}"]:
                return name
        return "off"

    def is_holiday(self, d: date) -> bool:
        return _mc.is_market_holiday(d)

    def is_trading_day(self, d: date) -> bool:
        return _mc.is_trading_day(d)

    def is_early_close(self, d: date) -> bool:
        return d in EARLY_CLOSE_DATES

    def early_close_time(self, d: date) -> Optional[time]:
        return EARLY_CLOSE_TIME if self.is_early_close(d) else None

    def info(self, ts: datetime) -> SessionInfo:
        ny = self._to_ny(ts)
        d = ny.date()
        return SessionInfo(
            trade_date=self.trade_date(ts),
            session=self.session(ts),
            flags=MappingProxyType(self.flags(ts)),
            is_trading_day=self.is_trading_day(d),
            is_holiday=self.is_holiday(d),
            is_early_close=self.is_early_close(d),
        )
