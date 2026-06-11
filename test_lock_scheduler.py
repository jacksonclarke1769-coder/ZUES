"""W2/W3 battery: instance lock (incl. crash recovery via subprocess kill -9)
and wall-clock authority (DST boundaries, holidays, half-days, fire-once, restart)."""
import os
import signal
import subprocess
import sys
import time as _time
from datetime import datetime, timezone, date
import pytest
from instance_lock import InstanceLock, LockHeld
from scheduler import Scheduler, ET


# ---------------- W2: instance lock ----------------

def test_lock_blocks_second_acquire_same_host(tmp_path):
    p = str(tmp_path / "bot.lock")
    a = InstanceLock(p).acquire()
    with pytest.raises(LockHeld):
        InstanceLock(p).acquire()
    a.release()
    InstanceLock(p).acquire().release()          # released -> reacquirable


def test_lock_blocks_separate_process(tmp_path):
    p = str(tmp_path / "bot.lock")
    a = InstanceLock(p).acquire()
    code = ("import sys; sys.path.insert(0, %r)\n"
            "from instance_lock import InstanceLock, LockHeld\n"
            "try:\n InstanceLock(%r).acquire(); sys.exit(7)\n"
            "except LockHeld:\n sys.exit(0)\n") % (os.getcwd(), p)
    r = subprocess.run([sys.executable, "-c", code])
    assert r.returncode == 0                     # second PROCESS failed closed
    a.release()


def test_lock_released_on_process_death_kill9(tmp_path):
    p = str(tmp_path / "bot.lock")
    code = ("import sys, time; sys.path.insert(0, %r)\n"
            "from instance_lock import InstanceLock\n"
            "InstanceLock(%r).acquire(); print('HELD', flush=True); time.sleep(60)\n"
            ) % (os.getcwd(), p)
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE)
    assert proc.stdout.readline().strip() == b"HELD"
    with pytest.raises(LockHeld):
        InstanceLock(p).acquire()                # held by live child
    proc.send_signal(signal.SIGKILL)             # simulate crash
    proc.wait()
    _time.sleep(0.1)
    InstanceLock(p).acquire().release()          # OS released it: recovery automatic


# ---------------- W3: wall-clock authority ----------------

def utc(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def et_as_utc(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=ET).astimezone(timezone.utc)


@pytest.fixture
def s():
    return Scheduler()


def test_naive_datetime_refused(s):
    with pytest.raises(ValueError):
        s.in_entry_window(datetime(2026, 6, 11, 10, 0))


def test_entry_window_normal_day(s):
    assert s.in_entry_window(et_as_utc(2026, 6, 11, 9, 30))
    assert s.in_entry_window(et_as_utc(2026, 6, 11, 11, 30))
    assert not s.in_entry_window(et_as_utc(2026, 6, 11, 11, 31))
    assert not s.in_entry_window(et_as_utc(2026, 6, 11, 9, 29))


def test_dst_boundaries_2026(s):
    # winter (EST, UTC-5): 9:30 ET == 14:30 UTC — Mar 6 2026 (pre-DST Friday)
    assert s.in_entry_window(utc(2026, 3, 6, 14, 30))
    assert not s.in_entry_window(utc(2026, 3, 6, 13, 30))
    # DST starts Sun Mar 8 2026 -> Mon Mar 9 (EDT, UTC-4): 9:30 ET == 13:30 UTC
    assert s.in_entry_window(utc(2026, 3, 9, 13, 30))
    assert not s.in_entry_window(utc(2026, 3, 9, 15, 31))        # 11:31 ET (EDT)
    # DST ends Sun Nov 1 2026 -> Mon Nov 2 (EST): 9:30 ET == 14:30 UTC again
    assert s.in_entry_window(utc(2026, 11, 2, 14, 30))
    assert not s.in_entry_window(utc(2026, 11, 2, 13, 30))


def test_holiday_blocks_everything(s):
    d = et_as_utc(2026, 7, 3, 10, 0)             # Independence Day observed
    assert not s.in_entry_window(d)
    assert not s.in_rth(d)
    assert not s.flatten_due(d)
    assert not s.daily_reset_due(d)


def test_weekend_blocks(s):
    assert not s.in_entry_window(et_as_utc(2026, 6, 13, 10, 0))   # Saturday


def test_half_day_early_flatten(s):
    d = date(2026, 11, 27)
    assert s.is_half_day(d)
    assert not s.flatten_due(et_as_utc(2026, 11, 27, 12, 30))     # before 12:45
    assert s.flatten_due(et_as_utc(2026, 11, 27, 12, 45))         # half-day flatten
    # normal day: 12:45 must NOT flatten
    s2 = Scheduler()
    assert not s2.flatten_due(et_as_utc(2026, 6, 11, 12, 45))
    assert s2.flatten_due(et_as_utc(2026, 6, 11, 14, 30))


def test_fire_once_semantics(s):
    t1 = et_as_utc(2026, 6, 11, 14, 30)
    assert s.flatten_due(t1)
    assert not s.flatten_due(et_as_utc(2026, 6, 11, 14, 35))      # same day: once
    assert s.flatten_due(et_as_utc(2026, 6, 12, 14, 30))          # next day: fires


def test_flatten_fires_even_if_called_late(s):
    """Feed died at 13:00; first wall-clock check at 15:47 -> still fires."""
    assert s.flatten_due(et_as_utc(2026, 6, 11, 15, 47))


def test_eod_and_reset_cycle(s):
    day = et_as_utc(2026, 6, 11, 9, 0)
    assert s.daily_reset_due(day)
    assert not s.daily_reset_due(et_as_utc(2026, 6, 11, 9, 5))
    assert not s.eod_due(et_as_utc(2026, 6, 11, 17, 9))
    assert s.eod_due(et_as_utc(2026, 6, 11, 17, 10))
    assert not s.eod_due(et_as_utc(2026, 6, 11, 18, 0))


def test_restart_restore_prevents_refire(s):
    t = et_as_utc(2026, 6, 11, 14, 30)
    assert s.flatten_due(t)
    persisted = s.fired_today(t)
    s2 = Scheduler()                              # restart
    s2.restore_fired(persisted)
    assert not s2.flatten_due(et_as_utc(2026, 6, 11, 15, 0))      # no double flatten


def test_can_hold_position_boundary(s):
    assert s.can_hold_position(et_as_utc(2026, 6, 11, 14, 29))
    assert not s.can_hold_position(et_as_utc(2026, 6, 11, 14, 30))
