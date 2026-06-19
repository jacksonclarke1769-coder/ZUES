"""Self-maintaining US market-holiday calendar tests (no network)."""
import datetime as dt

import market_calendar as MC
from scheduler import HOLIDAYS_2026, Scheduler


def H(y, m, d):
    return dt.date(y, m, d)


def test_known_full_closures_flagged():
    for d in [H(2016, 7, 4), H(2020, 12, 25), H(2024, 1, 1), H(2024, 3, 29),   # Good Friday 2024
              H(2024, 5, 27), H(2024, 7, 4), H(2024, 9, 2), H(2024, 11, 28), H(2024, 12, 25)]:
        assert MC.is_market_holiday(d), d


def test_trading_days_not_flagged():
    # ordinary day + Columbus Day + Veterans Day (federal but EQUITY MARKET OPEN) + Jul-5
    for d in [H(2024, 6, 18), H(2024, 10, 14), H(2024, 11, 11), H(2024, 7, 5)]:
        assert not MC.is_market_holiday(d), d


def test_juneteenth_starts_2022():
    assert not MC.is_market_holiday(H(2021, 6, 18))   # pre-2022 that Friday traded
    assert MC.is_market_holiday(H(2022, 6, 20))        # observed (Jun 19 2022 = Sunday)
    assert MC.is_market_holiday(H(2024, 6, 19))


def test_self_maintaining_future_years():
    # the whole point — no hardcoded table, future years just work
    assert MC.is_market_holiday(H(2030, 12, 25))       # Christmas 2030 (Wed)
    assert MC.is_market_holiday(H(2027, 1, 1))         # New Year 2027 (Fri)
    assert not MC.is_market_holiday(H(2030, 6, 18))    # ordinary Tuesday
    assert MC.is_trading_day(H(2030, 6, 18)) is True


def test_matches_curated_2026():
    assert MC.market_holidays(2026, 2026) == HOLIDAYS_2026


def test_scheduler_uses_calendar_by_default():
    s = Scheduler()                                    # holidays=None -> self-maintaining calendar
    assert s.is_trading_day(H(2026, 6, 19)) is False   # Juneteenth
    assert s.is_trading_day(H(2027, 12, 24)) is False  # Christmas 2027 observed (Dec 25 = Sat -> Fri)
    assert s.is_trading_day(H(2026, 6, 22)) is True     # Monday
    # explicit override still honoured
    s2 = Scheduler(holidays={H(2099, 1, 1)})
    assert s2.is_trading_day(H(2026, 6, 19)) is True    # not in the override set
