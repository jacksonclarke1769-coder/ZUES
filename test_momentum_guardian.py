"""Momentum 15:30 guardian — when the momentum lane is on, the EOD backstop defers from 14:30 to 15:30
so it doesn't cut the momentum position (the validated PF-1.83 edge needs holding past 14:30). A is flat by
14:30 via its own model; B closes via its own bracket/max-hold/RTH-end; KILL flattens fire instantly (here
we only move the scheduled EOD flatten). Proves the time override + fire-once timing, and half-day safety."""
from datetime import datetime, time, date
from zoneinfo import ZoneInfo

from scheduler import Scheduler

ET = ZoneInfo("America/New_York")


def _et(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=ET)


# ---- flatten-time override ----
def test_momentum_scheduler_flatten_is_1530():
    assert Scheduler(flatten_at=time(15, 30)).flatten_time(date(2026, 6, 29)) == time(15, 30)


def test_default_scheduler_flatten_is_1430():
    assert Scheduler().flatten_time(date(2026, 6, 29)) == time(14, 30)


def test_momentum_scheduler_keeps_halfday_1245():
    # on an early-close day momentum can't run late anyway — half-day flat stays 12:45
    assert Scheduler(flatten_at=time(15, 30)).flatten_time(date(2026, 12, 24)) == time(12, 45)


# ---- fire-once timing ----
def test_momentum_backstop_does_not_fire_at_1435():
    s = Scheduler(flatten_at=time(15, 30))
    assert s.flatten_due(_et(2026, 6, 29, 14, 35)) is False     # momentum still holding -> NOT flattened


def test_momentum_backstop_fires_at_1535_once():
    s = Scheduler(flatten_at=time(15, 30))
    assert s.flatten_due(_et(2026, 6, 29, 15, 35)) is True
    assert s.flatten_due(_et(2026, 6, 29, 15, 40)) is False      # fire-once per ET date


def test_default_backstop_still_fires_at_1435():
    assert Scheduler().flatten_due(_et(2026, 6, 29, 14, 35)) is True   # A/B account unchanged when momentum off
