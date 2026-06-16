"""APOLLO full-auto gate + D1c-feed enforcement tests (no network, no live)."""
import json
import os

import pytest

import auto_safety as A
from store import Store


# ----------------------------- D1c feed enforcement (Task 4) -----------------------------
def test_feed_timeframe_mapping():
    assert A.feed_timeframe("tradingview-1m") == 1
    assert A.feed_timeframe("tradingview-5m") == 5
    assert A.feed_timeframe("tradingview") == 5
    assert A.feed_timeframe("dukascopy") == 5


def test_d1c_active_forced_shadow_on_5m():
    mode, reason = A.resolve_d1c_for_feed("ACTIVE_EVAL_FILTER", "tradingview-5m", True)
    assert mode == "SHADOW" and "not 1m" in reason


def test_d1c_active_forced_shadow_when_not_realtime():
    mode, reason = A.resolve_d1c_for_feed("ACTIVE_EVAL_FILTER", "tradingview-1m", False)
    assert mode == "SHADOW" and "real-time" in reason


def test_d1c_active_allowed_on_realtime_1m():
    mode, reason = A.resolve_d1c_for_feed("ACTIVE_EVAL_FILTER", "tradingview-1m", True)
    assert mode == "ACTIVE_EVAL_FILTER" and reason is None


def test_d1c_shadow_stays_shadow():
    mode, reason = A.resolve_d1c_for_feed("SHADOW", "tradingview-5m", True)
    assert mode == "SHADOW" and reason is None


# ----------------------------- full-auto preflight (Task 3) -----------------------------
def _ready_env(tmp_path, monkeypatch):
    """Set up an all-green world in a temp APPROVAL_DIR + temp store; return (store, ds)."""
    appr = tmp_path / "approvals"
    appr.mkdir()
    (tmp_path / "launchlock" / "traderspost").mkdir(parents=True)
    for f in ("full-auto-approved.flag", "traderspost-approved.flag", "bracket-verified.flag",
              "feed-soak-passed.flag", "controlled-tv-live-test-approved.flag"):
        (appr / f).write_text("ok")
    (tmp_path / "launchlock" / "traderspost" / "PROVEN.flag").write_text("ok")
    monkeypatch.setattr(A, "APPROVAL_DIR", str(appr))
    monkeypatch.setenv("TRADERSPOST_LIVE_URL", "https://example.test/live")
    store = Store(str(tmp_path / "t.db"))
    store.set_state(ares_mode=json.dumps({"MFFU-50K-1": {"tier": "50K-conservative"}}),
                    bridge_sent="{}")
    # dead-man healthy by default (override per-test to exercise the failure paths)
    monkeypatch.setattr("heimdall_monitor.deadman_status",
                        lambda *a, **k: dict(alive=True, state="OK", reason="fresh"))
    ds = dict(DATA_READY=True, data_state="GREEN", realtime_confirmed=True, reasons=[], daily_stop=700.0)
    return store, ds


def test_preflight_passes_on_proper_soaked_feed(tmp_path, monkeypatch):
    # full auto can pass on a proper, soak-passed API feed (tradovate is 5m -> D1c runs SHADOW)
    store, ds = _ready_env(tmp_path, monkeypatch)
    ok, fails, eff_d1c, summ = A.full_auto_preflight(
        "MFFU-50K-1", "tradovate", "ACTIVE_EVAL_FILTER", ds,
        store=store, dashboard_green=True)
    assert ok, fails
    assert eff_d1c == "SHADOW"               # 5m feed -> D1c downgraded, but full auto still passes


def test_controlled_test_passes_on_browser_feed_with_flag(tmp_path, monkeypatch):
    # SUPERVISED controlled test MAY use the browser feed (test flag + all other gates present)
    store, ds = _ready_env(tmp_path, monkeypatch)
    ok, fails, eff_d1c, summ = A.full_auto_preflight(
        "MFFU-50K-1", "tradingview-1m", "ACTIVE_EVAL_FILTER", ds,
        store=store, dashboard_green=True, controlled_test=True)
    assert ok, fails
    assert eff_d1c == "ACTIVE_EVAL_FILTER"          # 1m + realtime -> legal


def test_controlled_test_fails_without_test_flag(tmp_path, monkeypatch):
    store, ds = _ready_env(tmp_path, monkeypatch)
    os.remove(os.path.join(A.APPROVAL_DIR, "controlled-tv-live-test-approved.flag"))
    ok, fails, _, _ = A.full_auto_preflight(
        "MFFU-50K-1", "tradingview-1m", "ACTIVE_EVAL_FILTER", ds,
        store=store, dashboard_green=True, controlled_test=True)
    assert not ok
    assert any("controlled-tv-live-test-approved.flag" in f for f in fails)


def test_production_browser_feed_still_blocked_even_with_test_flag(tmp_path, monkeypatch):
    # the controlled test flag must NOT open production full auto on a browser feed
    store, ds = _ready_env(tmp_path, monkeypatch)
    ok, fails, _, _ = A.full_auto_preflight(
        "MFFU-50K-1", "tradingview-1m", "ACTIVE_EVAL_FILTER", ds,
        store=store, dashboard_green=True, controlled_test=False)
    assert not ok
    assert any("browser/CDP" in f for f in fails)


def test_preflight_fails_on_browser_feed(tmp_path, monkeypatch):
    # everything else proven, but a TradingView browser/CDP feed must FAIL (SEMI_AUTO_ONLY)
    store, ds = _ready_env(tmp_path, monkeypatch)
    ok, fails, _, _ = A.full_auto_preflight(
        "MFFU-50K-1", "tradingview-1m", "ACTIVE_EVAL_FILTER", ds,
        store=store, dashboard_green=True)
    assert not ok
    assert any("FEED" in f and "browser/CDP" in f for f in fails)


def test_preflight_fails_proper_feed_without_soak(tmp_path, monkeypatch):
    store, ds = _ready_env(tmp_path, monkeypatch)
    os.remove(os.path.join(A.APPROVAL_DIR, "feed-soak-passed.flag"))
    ok, fails, _, _ = A.full_auto_preflight(
        "MFFU-50K-1", "tradovate", "ACTIVE_EVAL_FILTER", ds,
        store=store, dashboard_green=True)
    assert not ok
    assert any("soak-pass" in f for f in fails)


def test_preflight_refuses_without_full_auto_flag(tmp_path, monkeypatch):
    store, ds = _ready_env(tmp_path, monkeypatch)
    os.remove(os.path.join(A.APPROVAL_DIR, "full-auto-approved.flag"))
    ok, fails, _, _ = A.full_auto_preflight("MFFU-50K-1", "tradingview-1m",
                                            "ACTIVE_EVAL_FILTER", ds, store=store, dashboard_green=True)
    assert not ok
    assert any("full-auto-approved.flag" in f for f in fails)


def test_preflight_refuses_when_data_not_ready(tmp_path, monkeypatch):
    store, ds = _ready_env(tmp_path, monkeypatch)
    ds["DATA_READY"] = False
    ds["reasons"] = ["stale bars"]
    ok, fails, _, _ = A.full_auto_preflight("MFFU-50K-1", "tradingview-5m",
                                            "SHADOW", ds, store=store, dashboard_green=True)
    assert not ok
    assert any("DATA not ready" in f for f in fails)


def test_preflight_refuses_without_proven_flag(tmp_path, monkeypatch):
    store, ds = _ready_env(tmp_path, monkeypatch)
    os.remove(os.path.join(A.APPROVAL_DIR, "..", "launchlock", "traderspost", "PROVEN.flag"))
    ok, fails, _, _ = A.full_auto_preflight("MFFU-50K-1", "tradingview-5m",
                                            "SHADOW", ds, store=store, dashboard_green=True)
    assert not ok
    assert any("not proven" in f for f in fails)


def test_preflight_refuses_when_dashboard_not_green(tmp_path, monkeypatch):
    store, ds = _ready_env(tmp_path, monkeypatch)
    ok, fails, _, _ = A.full_auto_preflight("MFFU-50K-1", "tradingview-5m",
                                            "SHADOW", ds, store=store, dashboard_green=False)
    assert not ok
    assert any("dashboard not green" in f for f in fails)


def test_preflight_refuses_when_ares_not_armed(tmp_path, monkeypatch):
    store, ds = _ready_env(tmp_path, monkeypatch)
    store.set_state(ares_mode="{}")                       # not armed on the account
    ok, fails, _, _ = A.full_auto_preflight("MFFU-50K-1", "tradingview-5m",
                                            "SHADOW", ds, store=store, dashboard_green=True)
    assert not ok
    assert any("ARES not armed" in f for f in fails)


def test_preflight_fails_when_deadman_dead(tmp_path, monkeypatch):
    store, ds = _ready_env(tmp_path, monkeypatch)
    monkeypatch.setattr("heimdall_monitor.deadman_status",
                        lambda *a, **k: dict(alive=False, state="RED", reason="heartbeat stale 999s"))
    ok, fails, _, _ = A.full_auto_preflight("MFFU-50K-1", "tradingview-1m",
                                            "ACTIVE_EVAL_FILTER", ds, store=store, dashboard_green=True)
    assert not ok
    assert any("DEAD-MAN" in f for f in fails)


def test_preflight_fails_when_data_state_not_green(tmp_path, monkeypatch):
    store, ds = _ready_env(tmp_path, monkeypatch)
    ds["data_state"] = "YELLOW"        # reconnect stabilizing
    ok, fails, _, _ = A.full_auto_preflight("MFFU-50K-1", "tradingview-1m",
                                            "ACTIVE_EVAL_FILTER", ds, store=store, dashboard_green=True)
    assert not ok
    assert any("DATA state YELLOW" in f for f in fails)


def test_preflight_downgrades_d1c_on_5m_even_when_passing(tmp_path, monkeypatch):
    store, ds = _ready_env(tmp_path, monkeypatch)
    ok, fails, eff_d1c, summ = A.full_auto_preflight(
        "MFFU-50K-1", "tradovate", "ACTIVE_EVAL_FILTER", ds,   # proper feed, 5m -> D1c SHADOW
        store=store, dashboard_green=True)
    assert ok, fails
    assert eff_d1c == "SHADOW"                        # forced shadow on a 5m feed
    assert summ["d1c_downgrade"]
