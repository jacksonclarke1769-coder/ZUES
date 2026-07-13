"""core/clock.py: SessionEngine -- session tagging, killzone/overnight/maintenance
flags, trade-date roll at 18:00 ET, DST transition days, CME holidays, early closes.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest

from research.ict_v2.core.clock import NY, SessionEngine

UTC = timezone.utc


def ny(y, m, d, h, mi=0, s=0):
    return datetime(y, m, d, h, mi, s, tzinfo=NY)


@pytest.fixture
def eng():
    return SessionEngine()


# --- session tagging (mirrors model01's engine/data.py SESSIONS exactly) ------

@pytest.mark.parametrize(
    "hh, mm, expected_session",
    [
        (18, 0, "asia"),
        (23, 59, "asia"),
        (2, 0, "london"),
        (4, 59, "london"),
        (5, 0, "off"),  # london ends at 05:00 exclusive, ny_am hasn't started
        (9, 29, "off"),  # boundary: just before ny_am
        (9, 30, "ny_am"),  # boundary: ny_am starts inclusive
        (11, 29, "ny_am"),
        (11, 30, "ny_lunch"),  # boundary: ny_am ends exclusive, ny_lunch starts
        (13, 29, "ny_lunch"),
        (13, 30, "ny_pm"),
        (14, 59, "ny_pm"),
        (15, 0, "off"),  # ny_pm ends exclusive
        (17, 0, "off"),  # maintenance break (separate flag, not a primary session)
        (1, 59, "off"),  # asia ended at 00:00, london hasn't started
    ],
)
def test_primary_session_label_matches_model01_windows(eng, hh, mm, expected_session):
    ts = ny(2024, 6, 18, hh, mm)  # an ordinary Tuesday, no DST edge
    assert eng.session(ts) == expected_session


def test_killzone_flag_matches_model01_ny_am_window(eng):
    assert eng.flags(ny(2024, 6, 18, 9, 30))["in_killzone"] is True
    assert eng.flags(ny(2024, 6, 18, 11, 29))["in_killzone"] is True
    assert eng.flags(ny(2024, 6, 18, 11, 30))["in_killzone"] is False
    assert eng.flags(ny(2024, 6, 18, 9, 29))["in_killzone"] is False


def test_overnight_flag_wraps_midnight(eng):
    assert eng.flags(ny(2024, 6, 18, 19, 0))["in_overnight"] is True  # evening
    assert eng.flags(ny(2024, 6, 18, 2, 0))["in_overnight"] is True  # after midnight
    assert eng.flags(ny(2024, 6, 18, 9, 29))["in_overnight"] is True  # just before cash open
    assert eng.flags(ny(2024, 6, 18, 9, 30))["in_overnight"] is False  # cash open starts
    assert eng.flags(ny(2024, 6, 18, 12, 0))["in_overnight"] is False


def test_maintenance_break_flag(eng):
    assert eng.flags(ny(2024, 6, 18, 17, 0))["in_maintenance_break"] is True
    assert eng.flags(ny(2024, 6, 18, 17, 59))["in_maintenance_break"] is True
    assert eng.flags(ny(2024, 6, 18, 18, 0))["in_maintenance_break"] is False
    assert eng.flags(ny(2024, 6, 18, 16, 59))["in_maintenance_break"] is False


def test_accepts_non_ny_tz_aware_input_via_astimezone(eng):
    # 13:30 UTC == 09:30 EDT (summer, UTC-4)
    ts_utc = datetime(2024, 6, 18, 13, 30, tzinfo=UTC)
    assert eng.session(ts_utc) == "ny_am"


def test_rejects_naive_timestamp(eng):
    with pytest.raises(ValueError):
        eng.session(datetime(2024, 6, 18, 9, 30))  # no tzinfo


# --- trade-date roll at 18:00 ET -----------------------------------------------

def test_trade_date_rolls_forward_at_1800_et(eng):
    assert eng.trade_date(ny(2024, 1, 2, 17, 59, 59)) == date(2024, 1, 2)
    assert eng.trade_date(ny(2024, 1, 2, 18, 0, 0)) == date(2024, 1, 3)  # roll happens exactly at 18:00
    assert eng.trade_date(ny(2024, 1, 2, 23, 59, 59)) == date(2024, 1, 3)
    assert eng.trade_date(ny(2024, 1, 3, 0, 0, 0)) == date(2024, 1, 3)
    assert eng.trade_date(ny(2024, 1, 3, 9, 30, 0)) == date(2024, 1, 3)


def test_trade_date_roll_month_and_year_boundary(eng):
    assert eng.trade_date(ny(2023, 12, 31, 18, 0, 0)) == date(2024, 1, 1)


# --- DST transition days --------------------------------------------------------

def test_dst_spring_forward_2024_03_10_killzone_and_offset_correct(eng):
    """2024-03-10 is US spring-forward (02:00 EST -> 03:00 EDT). A fixed-offset
    bug (assuming ET is always UTC-5) would compute 09:30 ET as 14:30 UTC on this
    date; the correct EDT offset (UTC-4) gives 13:30 UTC."""
    ts_930_et = ny(2024, 3, 10, 9, 30)
    ts_utc = ts_930_et.astimezone(UTC)
    assert (ts_utc.hour, ts_utc.minute) == (13, 30)
    assert eng.session(ts_utc) == "ny_am"
    assert eng.flags(ts_utc)["in_killzone"] is True

    # feeding the raw UTC instant (as real stored bars would be) round-trips correctly
    assert eng.session(ts_930_et) == eng.session(ts_utc)
    assert eng.trade_date(ts_930_et) == eng.trade_date(ts_utc) == date(2024, 3, 10)


def test_dst_fall_back_2025_11_02_killzone_and_offset_correct(eng):
    """2025-11-02 is US fall-back (02:00 EDT -> 01:00 EST). A fixed-offset bug
    (assuming ET is always UTC-4) would compute 09:30 ET as 13:30 UTC; the
    correct EST offset (UTC-5) on this date gives 14:30 UTC."""
    ts_930_et = ny(2025, 11, 2, 9, 30)
    ts_utc = ts_930_et.astimezone(UTC)
    assert (ts_utc.hour, ts_utc.minute) == (14, 30)
    assert eng.session(ts_utc) == "ny_am"
    assert eng.flags(ts_utc)["in_killzone"] is True
    assert eng.trade_date(ts_930_et) == date(2025, 11, 2)


def test_dst_days_do_not_crash_across_the_whole_session_day(eng):
    """Sweep every 5-minute UTC bar across both DST transition days -- must not
    raise, and every bar gets exactly one primary session label (or 'off')."""
    for base_date, tz in [(datetime(2024, 3, 10, tzinfo=UTC), NY), (datetime(2025, 11, 2, tzinfo=UTC), NY)]:
        for minutes in range(0, 24 * 60, 5):
            ts = base_date.replace(hour=0, minute=0) + timedelta(minutes=minutes)
            label = eng.session(ts)
            assert label in {"asia", "london", "ny_am", "ny_lunch", "ny_pm", "off"}
            eng.trade_date(ts)  # must not raise


# --- CME holidays ---------------------------------------------------------------

def test_cme_holiday_flagged_and_not_a_trading_day(eng):
    d = date(2024, 1, 1)  # New Year's Day, a Monday
    assert eng.is_holiday(d) is True
    assert eng.is_trading_day(d) is False


def test_ordinary_weekday_is_a_trading_day(eng):
    d = date(2024, 1, 2)  # ordinary Tuesday
    assert eng.is_holiday(d) is False
    assert eng.is_trading_day(d) is True


def test_weekend_is_not_a_trading_day_but_not_a_holiday_flag(eng):
    d = date(2024, 1, 6)  # Saturday
    assert eng.is_trading_day(d) is False


# --- early closes ---------------------------------------------------------------

def test_early_close_thanksgiving_friday_2024(eng):
    d = date(2024, 11, 29)
    assert eng.is_early_close(d) is True
    assert eng.early_close_time(d) == time(13, 0)


def test_early_close_false_on_ordinary_day(eng):
    d = date(2024, 6, 18)
    assert eng.is_early_close(d) is False
    assert eng.early_close_time(d) is None


# --- SessionInfo aggregate --------------------------------------------------------

def test_info_bundles_everything_consistently(eng):
    ts = ny(2024, 6, 18, 9, 30)
    info = eng.info(ts)
    assert info.session == "ny_am"
    assert info.flags["in_killzone"] is True
    assert info.trade_date == date(2024, 6, 18)
    assert info.is_trading_day is True
    assert info.is_holiday is False
    assert info.is_early_close is False


def test_info_flags_is_read_only_mapping(eng):
    info = eng.info(ny(2024, 6, 18, 9, 30))
    with pytest.raises(TypeError):
        info.flags["in_killzone"] = False  # type: ignore[index]
