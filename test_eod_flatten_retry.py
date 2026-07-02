"""EOD flatten retry-until-ok semantics (audit R7/A8).

Tests the 3 success criteria from ticket S-eod-flatten-retry:
1. ok=False → NOT persisted; next tick >=60s later retries; ok=True → persisted; no further.
2. Success-on-first-attempt is byte-identical to the old behaviour.
3. Restart after failure retries (store has no fired record → flatten_due fires again).
"""
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flatten_guardian import FlattenGuardian
from store import Store

ET = ZoneInfo("America/New_York")


def at(hh, mm, sec=0, day=15):
    """UTC datetime for a given ET wall-clock time on 2026-06-{day} (Monday = trading day)."""
    return datetime(2026, 6, day, hh, mm, sec, tzinfo=ET).astimezone(timezone.utc)


class FailThenOkSender:
    """Fails the first `fail_count` flatten calls, then always returns ok=True."""
    def __init__(self, fail_count=1):
        self.calls = []
        self._fail_count = fail_count

    def flatten(self, account, root="MNQ", reason="x"):
        self.calls.append((account, reason))
        ok = len(self.calls) > self._fail_count
        return {"cancel": {"sent": ok}, "exit": {"sent": ok}, "ok": ok}

    def eod_calls(self):
        return [c for c in self.calls if c[1].startswith("EOD")]


def _make_clock(times):
    """Return a clock() callable that advances through `times`, clamping at the last entry."""
    idx = [0]

    def clock():
        t = times[min(idx[0], len(times) - 1)]
        idx[0] += 1
        return t

    return clock


def test_eod_failure_not_persisted_retries_then_persists(tmp_path):
    """Core success criterion: fail → not persisted; 60s retry → ok=True → persisted; done."""
    db = str(tmp_path / "g.db")
    store = Store(db)

    # Clock values consumed in order.
    # Per tick: 1 call for `now` in tick(); 1 additional call in _flatten() for the reason timestamp.
    # Tick1 (attempt, FAIL):  now=14:30:00, flatten-ts=14:30:00
    # Tick2 (30s, no retry):  now=14:30:30  (elapsed 30s < 60)
    # Tick3 (65s, RETRY+ok):  now=14:31:05, flatten-ts=14:31:05
    # Tick4 (pending cleared): now=14:31:30
    times = [
        at(14, 30, 0),   # tick1 now  → _eod_last_attempt = 14:30:00
        at(14, 30, 0),   # tick1 _flatten timestamp
        at(14, 30, 30),  # tick2 now  → elapsed 30s < 60, no retry
        at(14, 31, 5),   # tick3 now  → elapsed 65s >= 60, retry
        at(14, 31, 5),   # tick3 _flatten timestamp
        at(14, 31, 30),  # tick4 now  → _eod_pending=False, no retry
    ]
    sender = FailThenOkSender(fail_count=1)
    g = FlattenGuardian("X", sender=sender, store=store, journal=None, clock=_make_clock(times))

    # Tick 1: due, attempt, FAIL → NOT persisted
    g.tick()
    assert len(sender.eod_calls()) == 1
    fired = json.loads(store.get_state("auto_flatten_fired") or "[]")
    assert not any(a == "flatten" for a, _ in fired), "must NOT persist fired on ok=False"

    # Tick 2: 30s elapsed → no retry
    g.tick()
    assert len(sender.eod_calls()) == 1, "must not retry before 60s"

    # Tick 3: 65s elapsed → retry → ok=True → persisted
    g.tick()
    assert len(sender.eod_calls()) == 2, "must retry once >= 60s elapsed"
    fired2 = json.loads(store.get_state("auto_flatten_fired") or "[]")
    assert any(a == "flatten" for a, _ in fired2), "must persist fired on ok=True"

    # Tick 4: pending cleared → no further attempts
    g.tick()
    assert len(sender.eod_calls()) == 2, "must not attempt again after ok=True"


def test_success_on_first_attempt_is_byte_identical(tmp_path):
    """Success on first attempt: fired once, persisted, no re-fire — same as the old behaviour."""
    db = str(tmp_path / "g.db")
    store = Store(db)

    sender = FailThenOkSender(fail_count=0)  # always ok
    g = FlattenGuardian("X", sender=sender, store=store, journal=None,
                        clock=lambda: at(14, 30))

    g.tick()
    g.tick()  # second tick: fire-once must suppress it
    assert len(sender.eod_calls()) == 1, "must fire exactly once"

    fired = json.loads(store.get_state("auto_flatten_fired") or "[]")
    assert any(a == "flatten" for a, _ in fired), "must persist on first-attempt success"

    # Restart: same store → fired state restored → no re-fire
    s2 = FailThenOkSender(fail_count=0)
    g2 = FlattenGuardian("X", sender=s2, store=store, journal=None,
                         clock=lambda: at(14, 30))
    g2.tick()
    assert s2.eod_calls() == [], "restart after success must not re-fire"


def test_failure_restart_retries(tmp_path):
    """After a failed flatten, a restart must retry (store has no fired record)."""
    db = str(tmp_path / "g.db")
    store = Store(db)

    always_fail = FailThenOkSender(fail_count=999)
    g = FlattenGuardian("X", sender=always_fail, store=store, journal=None,
                        clock=lambda: at(14, 30))
    g.tick()
    assert len(always_fail.eod_calls()) == 1

    # Confirm fired was NOT persisted
    fired = json.loads(store.get_state("auto_flatten_fired") or "[]")
    assert not any(a == "flatten" for a, _ in fired)

    # Restart with a fresh guardian that will succeed → must attempt and persist
    ok_sender = FailThenOkSender(fail_count=0)
    g2 = FlattenGuardian("X", sender=ok_sender, store=store, journal=None,
                         clock=lambda: at(14, 30))
    g2.tick()
    assert len(ok_sender.eod_calls()) == 1, "restart after failure must retry"
    fired2 = json.loads(store.get_state("auto_flatten_fired") or "[]")
    assert any(a == "flatten" for a, _ in fired2), "must persist after restart success"
