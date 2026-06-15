"""Tests for feed_watch self-healer decision logic + market-hours guard (no Chrome, no network)."""
from datetime import datetime
from zoneinfo import ZoneInfo

import feed_watch as W

ET = ZoneInfo("America/New_York")


def et(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=ET)


# ----------------------------- market-hours guard -----------------------------
def test_market_open_weekday():
    assert W.market_likely_open(et(2026, 6, 15, 10, 0)) is True       # Mon 10:00


def test_market_closed_saturday():
    assert W.market_likely_open(et(2026, 6, 13, 10, 0)) is False      # Sat


def test_market_sunday_reopen_boundary():
    assert W.market_likely_open(et(2026, 6, 14, 12, 0)) is False      # Sun noon (closed)
    assert W.market_likely_open(et(2026, 6, 14, 19, 0)) is True       # Sun 19:00 (reopened)


def test_market_closed_maintenance_break():
    assert W.market_likely_open(et(2026, 6, 15, 17, 30)) is False     # daily 17:00-18:00 break


def test_market_closed_friday_after_17():
    assert W.market_likely_open(et(2026, 6, 19, 18, 0)) is False      # Fri after close


# ----------------------------- heal decision -----------------------------
def test_no_heal_when_fresh():
    do, act = W.heal_decision(60, True, 999, 0)
    assert do is False and act == "no:fresh"


def test_stale_triggers_reload():
    do, act = W.heal_decision(400, True, 999, 0)
    assert do is True and act == "reload"


def test_escalates_to_relaunch_after_reloads():
    do, act = W.heal_decision(400, True, 999, 2)      # MAX_HEALS=3 -> attempt 2 = relaunch
    assert do is True and act == "relaunch"


def test_gives_up_after_max():
    do, act = W.heal_decision(400, True, 999, 3)
    assert do is False and act == "no:exhausted"


def test_cooldown_blocks_rapid_reheal():
    do, act = W.heal_decision(400, True, 10, 0)
    assert do is False and act == "no:cooldown"


def test_no_heal_when_market_closed():
    do, act = W.heal_decision(400, False, 999, 0)     # don't thrash overnight/weekends
    assert do is False and act == "no:market-closed"
