"""TTL enforcement on the controlled-test approval flag (task U).

Checks that full_auto_preflight:
  - accepts the flag when mtime is within 24 hours
  - blocks with a re-touch message when mtime is >24 hours old
"""
import datetime
import json
import os
import time

import pytest

import auto_safety as A
from store import Store

TRADING_DAY = datetime.date(2026, 6, 22)  # pinned normal trading day


def _ready_env(tmp_path, monkeypatch):
    """All-green environment with a fresh controlled-test flag."""
    appr = tmp_path / "approvals"
    appr.mkdir()
    (tmp_path / "launchlock" / "traderspost").mkdir(parents=True)
    for f in (
        "full-auto-approved.flag",
        "traderspost-approved.flag",
        "bracket-verified.flag",
        "feed-soak-passed.flag",
    ):
        (appr / f).write_text("ok")
    (tmp_path / "launchlock" / "traderspost" / "PROVEN.flag").write_text("ok")
    # Write the primary controlled-test flag; mtime will be set per-test.
    flag_path = appr / "controlled-tv-full-live-test-approved.flag"
    flag_path.write_text("ok")
    monkeypatch.setattr(A, "APPROVAL_DIR", str(appr))
    monkeypatch.setenv("TRADERSPOST_LIVE_URL", "https://example.test/live")
    store = Store(str(tmp_path / "t.db"))
    store.set_state(
        ares_mode=json.dumps({"APEX-50K-EVAL-1": {"tier": "Apex-50K-eval"}}),
        bridge_sent="{}",
    )
    monkeypatch.setattr(
        "heimdall_monitor.deadman_status",
        lambda *a, **k: dict(alive=True, state="OK", reason="fresh"),
    )
    ds = dict(DATA_READY=True, data_state="GREEN", realtime_confirmed=True, reasons=[], daily_stop=700.0)
    return store, ds, flag_path


def test_controlled_flag_fresh_is_accepted(tmp_path, monkeypatch):
    """Flag touched just now (mtime = now) → preflight passes the TTL check."""
    store, ds, flag_path = _ready_env(tmp_path, monkeypatch)
    # mtime is already "now" from write_text; no adjustment needed
    ok, fails, _, _ = A.full_auto_preflight(
        "APEX-50K-EVAL-1", "tradingview-1m", "ACTIVE_EVAL_FILTER", ds,
        store=store, dashboard_green=True, controlled_test=True, today=TRADING_DAY,
    )
    assert ok, "fresh flag should be accepted; fails=%r" % fails
    assert not any("24h" in f or "re-authorize" in f.lower() for f in fails)


def test_controlled_flag_expired_is_blocked(tmp_path, monkeypatch):
    """Flag mtime set 25 hours ago → preflight blocks with a re-touch message."""
    store, ds, flag_path = _ready_env(tmp_path, monkeypatch)
    # Set mtime to 25 hours in the past
    stale_ts = time.time() - 25 * 3600
    os.utime(str(flag_path), (stale_ts, stale_ts))
    ok, fails, _, _ = A.full_auto_preflight(
        "APEX-50K-EVAL-1", "tradingview-1m", "ACTIVE_EVAL_FILTER", ds,
        store=store, dashboard_green=True, controlled_test=True, today=TRADING_DAY,
    )
    assert not ok, "stale flag must block"
    ttl_fail = [f for f in fails if "24h" in f or "re-authorize" in f.lower() or "touch" in f]
    assert ttl_fail, "failure message must mention re-touch; fails=%r" % fails
    # Message must include the exact flag path so the operator knows what to touch
    assert str(flag_path) in ttl_fail[0], "re-touch message must contain the flag path"
