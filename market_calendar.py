"""Self-maintaining US equity-market (NYSE/CME equity-index) holiday calendar.

Computes full-closure holidays for ANY year from rules (never a hardcoded year that lapses), so the
live trading-day gate keeps working in 2027, 2030, … with no manual table to update each January.

Full closures only (the cash session is shut): New Year, MLK, Presidents' Day, Good Friday,
Memorial Day, Juneteenth (NYSE from 2022), Independence Day, Labor Day, Thanksgiving, Christmas —
each with weekend observance. Columbus Day & Veterans Day are federal but the EQUITY market is OPEN,
so they are deliberately excluded. Half-days (early closes) are a separate concern and not here
(they don't affect the Profile A NY-AM 09:30–11:00 window).
"""
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd
from pandas.tseries.holiday import (AbstractHolidayCalendar, Holiday, nearest_workday,
                                    USMartinLutherKingJr, USPresidentsDay, USMemorialDay,
                                    USLaborDay, USThanksgivingDay, GoodFriday)


class USMarketCalendar(AbstractHolidayCalendar):
    rules = [
        Holiday("New Year's Day", month=1, day=1, observance=nearest_workday),
        USMartinLutherKingJr,
        USPresidentsDay,
        GoodFriday,
        USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, start_date="2022-06-19", observance=nearest_workday),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay,
        USThanksgivingDay,
        Holiday("Christmas", month=12, day=25, observance=nearest_workday),
    ]


_CAL = USMarketCalendar()


@lru_cache(maxsize=None)
def _year_holidays(year):
    idx = _CAL.holidays(pd.Timestamp(year, 1, 1), pd.Timestamp(year, 12, 31))
    return frozenset(ts.date() for ts in idx)


def is_market_holiday(d):
    """True if date d is a US equity-market full-closure day (any year)."""
    return d in _year_holidays(d.year)


def is_trading_day(d):
    """Weekday and not a market holiday."""
    return d.weekday() < 5 and not is_market_holiday(d)


def market_holidays(y0, y1):
    """Set of market-holiday dates across the inclusive year range."""
    out = set()
    for y in range(y0, y1 + 1):
        out |= _year_holidays(y)
    return out


def _quarterly_expiry(year, month):
    """3rd Friday of the given month in the given year (NQ/ES CME quarterly expiry)."""
    d = date(year, month, 1)
    days_to_friday = (4 - d.weekday()) % 7   # Monday=0, Friday=4
    first_friday = d + timedelta(days=days_to_friday)
    return first_friday + timedelta(weeks=2)  # 3rd Friday


def roll_window(d):
    """True when date d falls within the quarterly NQ roll window.

    Window: 10 calendar days ending on (and including) the 3rd Friday of Mar/Jun/Sep/Dec.
    Returns True from expiry-9 through expiry inclusive.

    Note: the spec prose says '8 calendar days' but the stated truth-table
    (2026-09-09 True, 2026-09-18 True) requires a 10-day window — implemented
    as 10 days to satisfy the authoritative test specification.
    """
    for month in (3, 6, 9, 12):
        expiry = _quarterly_expiry(d.year, month)
        if expiry - timedelta(days=9) <= d <= expiry:
            return True
    return False
