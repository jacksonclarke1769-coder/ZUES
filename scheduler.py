"""W3 — Wall-Clock Authority. THOR kill-path #2: time must never depend on bars.

All trading time comes from the tz-database clock (America/New_York), never from
feed timestamps. The Scheduler answers "what is due NOW?" from wall clock alone and
keeps fire-once semantics per ET trading date, so a stale feed, dead API, or closed
market cannot stop the EOD flatten, session gating, or daily resets.

Calendar: curated 2026 CME equity-index table below. OPERATOR MUST VERIFY against the
official CME holiday calendar each January (weekly procedure has the line item).
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from market_calendar import is_market_holiday as _is_market_holiday

ET = ZoneInfo("America/New_York")

# Reference/sanity table only — the live trading-day gate now uses the SELF-MAINTAINING
# market_calendar (any year, no annual update). Kept to cross-check the calendar for 2026.
HOLIDAYS_2026 = {
    date(2026, 1, 1),    # New Year's Day
    date(2026, 1, 19),   # MLK
    date(2026, 2, 16),   # Presidents' Day
    date(2026, 4, 3),    # Good Friday
    date(2026, 5, 25),   # Memorial Day
    date(2026, 6, 19),   # Juneteenth
    date(2026, 7, 3),    # Independence Day (observed)
    date(2026, 9, 7),    # Labor Day
    date(2026, 11, 26),  # Thanksgiving
    date(2026, 12, 25),  # Christmas
}
HALF_DAYS_2026 = {       # early close 13:00 ET
    date(2026, 11, 27),  # day after Thanksgiving
    date(2026, 12, 24),  # Christmas Eve
}


class Scheduler:
    """All inputs/outputs are timezone-AWARE datetimes (UTC in, ET internally)."""

    def __init__(self, entry_start=time(9, 30), entry_end=time(11, 30),
                 flatten_at=time(14, 30), half_day_flatten=time(12, 45),
                 eod_at=time(17, 10), holidays=None, half_days=HALF_DAYS_2026):
        self.entry_start = entry_start
        self.entry_end = entry_end
        self.flatten_at = flatten_at
        self.half_day_flatten = half_day_flatten
        self.eod_at = eod_at
        self.holidays = holidays
        self.half_days = half_days
        self._fired = set()          # (action, et_date)

    # ---------------- clock ----------------

    def et(self, now_utc):
        if now_utc.tzinfo is None:
            raise ValueError("naive datetime refused — wall-clock authority is tz-aware only")
        return now_utc.astimezone(ET)

    # ---------------- calendar ----------------

    def is_trading_day(self, d):
        if d.weekday() >= 5:
            return False
        if self.holidays is not None:          # explicit override (tests / custom calendars)
            return d not in self.holidays
        return not _is_market_holiday(d)        # default: self-maintaining US market calendar (any year)

    def is_half_day(self, d):
        return d in self.half_days

    def session_close(self, d):
        return time(13, 0) if self.is_half_day(d) else time(16, 0)

    def flatten_time(self, d):
        return self.half_day_flatten if self.is_half_day(d) else self.flatten_at

    # ---------------- gates (pure, no side effects) ----------------

    def in_entry_window(self, now_utc):
        t = self.et(now_utc)
        return (self.is_trading_day(t.date())
                and self.entry_start <= t.time() <= self.entry_end)

    def can_hold_position(self, now_utc):
        t = self.et(now_utc)
        return (self.is_trading_day(t.date())
                and t.time() < self.flatten_time(t.date()))

    def in_rth(self, now_utc):
        t = self.et(now_utc)
        return (self.is_trading_day(t.date())
                and time(9, 30) <= t.time() < self.session_close(t.date()))

    # ---------------- fire-once duties ----------------

    def _due_once(self, action, now_utc, at_time):
        t = self.et(now_utc)
        d = t.date()
        if not self.is_trading_day(d):
            return False
        key = (action, d)
        if key in self._fired or t.time() < at_time:
            return False
        self._fired.add(key)
        return True

    def flatten_due(self, now_utc):
        """True exactly once per ET trading date at/after the flatten time.
        Independent of bars BY CONSTRUCTION — feed death cannot suppress it."""
        t = self.et(now_utc)
        return self._due_once("flatten", now_utc, self.flatten_time(t.date()))

    def eod_due(self, now_utc):
        """Daily state close (mffu EOD update, counters reset) at/after 17:10 ET."""
        return self._due_once("eod", now_utc, self.eod_at)

    def daily_reset_due(self, now_utc):
        """First call on a new ET trading date (session prep, counter zeroing)."""
        t = self.et(now_utc)
        d = t.date()
        if not self.is_trading_day(d) or ("reset", d) in self._fired:
            return False
        self._fired.add(("reset", d))
        return True

    # ---------------- restart support ----------------

    def restore_fired(self, action_dates):
        """Re-arm protection after restart: pass [(action, et_date_iso)] persisted in
        Store so a mid-day restart does not re-fire (or skip) today's duties."""
        for action, d_iso in action_dates:
            self._fired.add((action, date.fromisoformat(d_iso)))

    def fired_today(self, now_utc):
        d = self.et(now_utc).date()
        return [(a, dd.isoformat()) for (a, dd) in self._fired if dd == d]
