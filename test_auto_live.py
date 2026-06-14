"""auto_live integration — D1c DriftGate wired into the live Profile A loop,
kill switch, daily guard, paper/live gating. Everything turns on Monday safely."""
import os
import pytest
import pandas as pd
from store import Store
from journal import Journal
from bridge_sender import BridgeSender
import auto_live

NY = "America/New_York"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for d in ("data", "evidence/approvals", "out/ares"):
        os.makedirs(d, exist_ok=True)
    return Store("data/b.db"), Journal("data/j.db")


def _bar(t):
    return pd.Timestamp(f"2026-06-15 {t}", tz=NY)


def _auto(env, mode):
    s, j = env
    return auto_live.LiveAuto("MFFU-50K-1", "50K-conservative", "paper", s, j,
                              BridgeSender(store=s, journal=j, mode="dry-run"), 700,
                              d1c_mode=mode)


def _feed_up(auto):
    """09:30 open 22000 -> drifts UP (favours LONG)."""
    auto.feed_gate(_bar("09:30:00"), 22000.0, 22005.0)
    auto.feed_gate(_bar("09:35:00"), 22005.0, 22018.0)
    auto.feed_gate(_bar("09:45:00"), 22018.0, 22030.0)


def _sig(side):
    return dict(side=side, ts_signal="2026-06-15T09:45:00",
                entry=22030.0, stop=(21980.0 if side == "long" else 22080.0),
                target=(22120.0 if side == "long" else 21940.0), liq="sweep")


def test_d1c_active_allows_drift_agreement(env):
    a = _auto(env, "ACTIVE_EVAL_FILTER"); _feed_up(a)
    a.on_decision(_sig("long"), True, "ok", _bar("09:45:30"))
    assert a.sent == 1 and a.d1c_blocked == 0


def test_d1c_active_blocks_drift_disagreement(env):
    a = _auto(env, "ACTIVE_EVAL_FILTER"); _feed_up(a)
    a.on_decision(_sig("short"), True, "ok", _bar("09:45:30"))
    assert a.sent == 0 and a.d1c_blocked == 1


def test_d1c_shadow_observes_only(env):
    a = _auto(env, "SHADOW"); _feed_up(a)
    a.on_decision(_sig("short"), True, "ok", _bar("09:45:30"))   # disagrees but shadow
    assert a.sent == 1 and a.d1c_blocked == 0


def test_d1c_off_bypasses(env):
    a = _auto(env, "OFF"); _feed_up(a)
    a.on_decision(_sig("short"), True, "ok", _bar("09:45:30"))
    assert a.sent == 1


def test_d1c_fail_closed_missing_open(env):
    """No 09:30 open fed -> D1c suspends in ACTIVE (fail closed)."""
    a = _auto(env, "ACTIVE_EVAL_FILTER")
    a.gate.on_bar_close(_bar("10:00:00"), 22030.0)             # close but no session open
    a.on_decision(_sig("long"), True, "ok", _bar("10:00:30"))
    assert a.sent == 0 and a.d1c_blocked == 1


def test_kill_switch_blocks(env):
    s, j = env
    a = _auto(env, "OFF"); _feed_up(a)
    s.set_state(auto_live_kill="1")
    a.on_decision(_sig("long"), True, "ok", _bar("09:45:30"))
    assert a.sent == 0 and a.blocked == 1


def test_daily_stop_blocks(env):
    s, j = env
    a = _auto(env, "OFF"); _feed_up(a)
    a.guard.stop_now("MFFU-50K-1", auto_live.et_date())
    a.on_decision(_sig("long"), True, "ok", _bar("09:45:30"))
    assert a.sent == 0 and a.blocked == 1


def test_not_placed_is_skipped(env):
    a = _auto(env, "ACTIVE_EVAL_FILTER"); _feed_up(a)
    a.on_decision(_sig("long"), False, "position_open", _bar("09:45:30"))
    assert a.sent == 0 and a.d1c_blocked == 0


def test_live_refused_without_flags(env, monkeypatch):
    monkeypatch.delenv("TRADERSPOST_LIVE_URL", raising=False)
    rc = auto_live.main(["--account", "MFFU-50K-1", "--tier", "50K-conservative", "--live"])
    assert rc == 2          # fail closed: missing flags + url


def test_d1c_decisions_logged_not_athena(env):
    import d1c_filter
    a = _auto(env, "ACTIVE_EVAL_FILTER"); _feed_up(a)
    a.on_decision(_sig("long"), True, "ok", _bar("09:45:30"))
    a.on_decision(_sig("short"), True, "ok", _bar("09:46:30"))
    assert d1c_filter.athena_official_count("out/ares/d1c_eval_log.csv") == 0   # ARES eval never counts
