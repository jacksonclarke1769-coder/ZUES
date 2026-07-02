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


def test_roll_window_sep_2026():
    # 3rd Friday Sep 2026 = Sep 18; 10-day window = Sep 9 to Sep 18
    assert MC.roll_window(H(2026, 9, 9))  is True    # window start
    assert MC.roll_window(H(2026, 9, 18)) is True    # expiry day
    assert MC.roll_window(H(2026, 9, 19)) is False   # day after expiry
    assert MC.roll_window(H(2026, 8, 1))  is False   # well outside any window


def test_roll_window_boundaries():
    # Sep 2026: expiry = Sep 18; window starts Sep 9 (expiry - 9)
    assert MC.roll_window(H(2026, 9, 8))  is False   # one day before window
    assert MC.roll_window(H(2026, 9, 9))  is True    # first day in window
    assert MC.roll_window(H(2026, 9, 18)) is True    # last day in window (expiry)
    assert MC.roll_window(H(2026, 9, 19)) is False   # first day after window


def test_roll_window_all_quarters():
    # Verify each of the four quarterly windows fires in 2026
    # Mar 2026: 3rd Friday = Mar 20 (Mar 1=Sun; first Fri=Mar 6; 3rd Fri=Mar 20)
    assert MC.roll_window(H(2026, 3, 11)) is True    # 9 days before Mar 20
    assert MC.roll_window(H(2026, 3, 20)) is True    # expiry
    assert MC.roll_window(H(2026, 3, 21)) is False   # day after
    # Jun 2026: 3rd Friday = Jun 19 (Jun 1=Mon; first Fri=Jun 5; 3rd Fri=Jun 19)
    assert MC.roll_window(H(2026, 6, 10)) is True
    assert MC.roll_window(H(2026, 6, 19)) is True
    assert MC.roll_window(H(2026, 6, 20)) is False
    # Dec 2026: 3rd Friday = Dec 18 (Dec 1=Tue; first Fri=Dec 4; 3rd Fri=Dec 18)
    assert MC.roll_window(H(2026, 12, 9)) is True
    assert MC.roll_window(H(2026, 12, 18)) is True
    assert MC.roll_window(H(2026, 12, 19)) is False


def test_roll_window_2027_march():
    # 2027 Mar: Mar 1=Mon; first Fri=Mar 5; 3rd Fri=Mar 19
    assert MC.roll_window(H(2027, 3, 10)) is True    # 9 days before Mar 19
    assert MC.roll_window(H(2027, 3, 19)) is True    # expiry
    assert MC.roll_window(H(2027, 3, 20)) is False   # day after
    assert MC.roll_window(H(2027, 3, 9))  is False   # one day before window start


def test_roll_window_no_overlap_between_quarters():
    # Ensure the day after one expiry is not in the next quarter's window
    # Jun 19 + 1 = Jun 20 should not be in Sep 2026 window (Sep 9 start)
    assert MC.roll_window(H(2026, 6, 20)) is False
    assert MC.roll_window(H(2026, 9, 8))  is False


def test_scheduler_uses_calendar_by_default():
    s = Scheduler()                                    # holidays=None -> self-maintaining calendar
    assert s.is_trading_day(H(2026, 6, 19)) is False   # Juneteenth
    assert s.is_trading_day(H(2027, 12, 24)) is False  # Christmas 2027 observed (Dec 25 = Sat -> Fri)
    assert s.is_trading_day(H(2026, 6, 22)) is True     # Monday
    # explicit override still honoured
    s2 = Scheduler(holidays={H(2099, 1, 1)})
    assert s2.is_trading_day(H(2026, 6, 19)) is True    # not in the override set
