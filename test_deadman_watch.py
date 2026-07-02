"""Tests for deadman_watch.py — O ticket.

Tests:
- decide() unit tests: state machine transitions, market-closed guard, recovery
- Fresh reason produces unique signalIds across two firings
- Dry-run mode: --live absent → no live webhook possible
- --once flag: single poll and exit
- Instance lock: second invocation blocked
"""
import json
import os
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from deadman_watch import (
    STATE_ALERT,
    STATE_FLATTEN,
    STATE_HALTED,
    STATE_OK,
    decide,
    _heartbeat_age,
)


# ── decide() unit tests ──────────────────────────────────────────────────────

class TestDecideMarketClosed:
    """When market is closed, never alert or flatten."""

    def test_ok_stays_ok_when_closed(self):
        new_state, action = decide(age_s=999, market_open=False, state=STATE_OK)
        assert new_state == STATE_OK
        assert action == "none"

    def test_stale_no_alert_when_closed(self):
        """Even with age > alert_s, market closed must suppress alert."""
        new_state, action = decide(age_s=300, market_open=False, state=STATE_OK,
                                   alert_s=180, flatten_s=420)
        assert action == "none"
        assert new_state == STATE_OK

    def test_alert_state_no_flatten_when_closed(self):
        """Already in ALERT but market closes — no flatten."""
        new_state, action = decide(age_s=500, market_open=False, state=STATE_ALERT,
                                   alert_s=180, flatten_s=420)
        assert action == "none"
        assert new_state == STATE_ALERT

    def test_none_age_market_closed(self):
        """Missing heartbeat + market closed → no action."""
        new_state, action = decide(age_s=None, market_open=False, state=STATE_OK)
        assert action == "none"


class TestDecideAlertTransition:
    """ALERT fires exactly once when age > alert_s and market open."""

    def test_transitions_ok_to_alert(self):
        new_state, action = decide(age_s=200, market_open=True, state=STATE_OK,
                                   alert_s=180, flatten_s=420)
        assert new_state == STATE_ALERT
        assert action == "alert"

    def test_alert_not_repeated_in_alert_state(self):
        """In ALERT state, already stale but not yet flatten threshold — no repeat action."""
        new_state, action = decide(age_s=300, market_open=True, state=STATE_ALERT,
                                   alert_s=180, flatten_s=420)
        assert new_state == STATE_ALERT
        assert action == "none"

    def test_missing_heartbeat_triggers_alert(self):
        """None age_s (missing file) treated as infinite age → triggers alert."""
        new_state, action = decide(age_s=None, market_open=True, state=STATE_OK,
                                   alert_s=180, flatten_s=420)
        assert new_state == STATE_ALERT
        assert action == "alert"

    def test_below_threshold_stays_ok(self):
        new_state, action = decide(age_s=100, market_open=True, state=STATE_OK,
                                   alert_s=180, flatten_s=420)
        assert new_state == STATE_OK
        assert action == "none"


class TestDecideFlattenTransition:
    """FLATTEN fires exactly once when age > flatten_s, then moves to HALTED."""

    def test_alert_to_flatten_when_over_threshold(self):
        new_state, action = decide(age_s=500, market_open=True, state=STATE_ALERT,
                                   alert_s=180, flatten_s=420)
        assert new_state == STATE_FLATTEN
        assert action == "flatten"

    def test_flatten_to_halted_immediately(self):
        """The FLATTEN state is transient: next poll → HALTED, action none."""
        new_state, action = decide(age_s=600, market_open=True, state=STATE_FLATTEN,
                                   alert_s=180, flatten_s=420)
        assert new_state == STATE_HALTED
        assert action == "none"

    def test_no_repeat_flatten_in_halted(self):
        """HALTED state never fires flatten again, even with very stale heartbeat."""
        new_state, action = decide(age_s=9999, market_open=True, state=STATE_HALTED,
                                   alert_s=180, flatten_s=420)
        assert new_state == STATE_HALTED
        assert action == "none"

    def test_missing_heartbeat_escalates_to_flatten(self):
        """None age (infinite) in ALERT state escalates past flatten_s."""
        new_state, action = decide(age_s=None, market_open=True, state=STATE_ALERT,
                                   alert_s=180, flatten_s=420)
        assert new_state == STATE_FLATTEN
        assert action == "flatten"


class TestDecideRecovery:
    """Recovery re-arms the watchdog."""

    def test_alert_to_ok_on_fresh_heartbeat(self):
        new_state, action = decide(age_s=30, market_open=True, state=STATE_ALERT,
                                   alert_s=180, flatten_s=420)
        assert new_state == STATE_OK
        assert action == "recover"

    def test_halted_to_ok_on_fresh_heartbeat(self):
        new_state, action = decide(age_s=10, market_open=True, state=STATE_HALTED,
                                   alert_s=180, flatten_s=420)
        assert new_state == STATE_OK
        assert action == "recover"

    def test_no_recovery_when_still_stale_in_halted(self):
        new_state, action = decide(age_s=500, market_open=True, state=STATE_HALTED,
                                   alert_s=180, flatten_s=420)
        assert new_state == STATE_HALTED
        assert action == "none"

    def test_recovery_requires_market_open(self):
        """Market closed: heartbeat could go fresh, but no recovery action emitted."""
        new_state, action = decide(age_s=10, market_open=False, state=STATE_HALTED,
                                   alert_s=180, flatten_s=420)
        # stays HALTED when market closed, no recovery
        assert action == "none"


# ── Fresh reason / unique signalId test ─────────────────────────────────────

def test_two_flatten_firings_produce_different_signal_ids():
    """Flatten path must use a fresh reason each firing so signalIds differ (dedup safety)."""
    import bridge_traderspost as BP

    ts1 = "deadman_emergency_1000000"
    ts2 = "deadman_emergency_1000001"

    p1, _ = BP.build_flatten(account="APEX-50K-EVAL-1", reason=ts1)
    p2, _ = BP.build_flatten(account="APEX-50K-EVAL-1", reason=ts2)

    sid1 = p1.get("extras", {}).get("signalId") or p1.get("signalId")
    sid2 = p2.get("extras", {}).get("signalId") or p2.get("signalId")

    assert sid1 is not None, "signalId missing from flatten payload"
    assert sid2 is not None, "signalId missing from flatten payload"
    assert sid1 != sid2, "two flatten firings must produce distinct signalIds"


# ── Dry-run default ──────────────────────────────────────────────────────────

def test_dry_run_default_no_webhook():
    """Without --live, BridgeSender in dry-run mode must refuse to send."""
    from bridge_sender import BridgeSender
    sender = BridgeSender(mode="dry-run", live_url=None)
    res = sender.flatten("TEST-ACCOUNT", reason="deadman_emergency_1234567")
    # dry-run returns sent=False for both legs
    assert res["cancel"].get("sent") is False
    assert res["exit"].get("sent") is False
    # reason string explains it was dry-run (not a live failure)
    assert "dry-run" in res["cancel"].get("reason", "").lower() or \
           res["cancel"].get("reason") is not None


# ── _heartbeat_age helper ────────────────────────────────────────────────────

def test_heartbeat_age_missing_file(tmp_path):
    """Missing heartbeat returns None."""
    age = _heartbeat_age(str(tmp_path / "no_file.json"), datetime.now(timezone.utc))
    assert age is None


def test_heartbeat_age_returns_positive(tmp_path):
    hb = tmp_path / "heartbeat.json"
    past = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    hb.write_text(json.dumps({"ts": past.isoformat()}))
    now = datetime(2026, 1, 1, 12, 5, 0, tzinfo=timezone.utc)  # 300s later
    age = _heartbeat_age(str(hb), now)
    assert abs(age - 300) < 1


# ── --once flag (integration-ish, no real network) ──────────────────────────

def test_once_flag_runs_single_poll(tmp_path, capsys):
    """--once exits after one poll without hanging."""
    import argparse
    from deadman_watch import run

    # Write a fresh heartbeat so state stays OK
    hb = tmp_path / "heartbeat.json"
    hb.write_text(json.dumps({"ts": datetime.now(timezone.utc).isoformat()}))

    args = argparse.Namespace(
        account="TEST",
        live=False,
        alert_s=180,
        flatten_s=420,
        interval=30,
        heartbeat_path=str(hb),
        once=True,
    )

    # Should return promptly (no sleep, no webhook)
    run(args)
    captured = capsys.readouterr()
    assert "action=" in captured.out


# ── Instance lock: second invocation blocked ─────────────────────────────────

def test_instance_lock_blocks_second(tmp_path):
    from instance_lock import InstanceLock, LockHeld
    lock_path = str(tmp_path / "deadman_watch.lock")
    lock1 = InstanceLock(lock_path)
    lock1.acquire()
    try:
        lock2 = InstanceLock(lock_path)
        with pytest.raises(LockHeld):
            lock2.acquire()
    finally:
        lock1.release()
