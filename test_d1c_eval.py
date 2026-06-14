"""ARES-D1c — the 12 required tests. D1c reduces risk on Profile A only; it can never
add trades, change size, touch Profile B, override daily-stop/P3, or advance ATHENA."""
import json
import os
import pytest
from store import Store
from journal import Journal
import auto_safety as A
import d1c_filter as D
import ares_mode
import auto_runner


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("data", exist_ok=True)
    os.makedirs("evidence/approvals", exist_ok=True)
    os.makedirs("out/ares", exist_ok=True)
    return Store("data/bot.db"), Journal("data/journal.db")


class Args:
    def __init__(self, **k):
        self.mode = k.get("mode", "eval"); self.account = k.get("account", "ACC")
        self.tier = k.get("tier", "50K-conservative")
        self.dry_run = True; self.paper = k.get("paper", False); self.live = k.get("live", False)
        self.dashboard_green = False; self.d1c_mode = k.get("d1c_mode", "shadow")


# 1. active eval mode can BLOCK Profile A (drift disagrees)
def test_1_active_blocks_profile_a():
    r = D.profile_a_permission("ACTIVE_EVAL_FILTER", signal_present=True,
                               daily_stopped=False, p3_blocked=False,
                               drift_value=12, drift_sign=-1, direction="long",
                               feed_age_s=10, has_open=True)
    assert r["permit"] is False and r["d1c_decision"] == "BLOCK"
    # and ALLOW when drift agrees
    r2 = D.profile_a_permission("ACTIVE_EVAL_FILTER", signal_present=True,
                                daily_stopped=False, p3_blocked=False,
                                drift_value=12, drift_sign=1, direction="long",
                                feed_age_s=10, has_open=True)
    assert r2["permit"] is True and r2["d1c_decision"] == "ALLOW"


# 2. cannot create trades — no A signal => no trade regardless of D1c ALLOW
def test_2_cannot_create_trades():
    r = D.profile_a_permission("ACTIVE_EVAL_FILTER", signal_present=False,
                               daily_stopped=False, p3_blocked=False,
                               drift_value=12, drift_sign=1, direction="long",
                               feed_age_s=10, has_open=True)
    assert r["permit"] is False and "no Profile A signal" in r["reason"]


# 3. cannot affect Profile B
def test_3_profile_b_unaffected():
    for mode in ("OFF", "SHADOW", "ACTIVE_EVAL_FILTER", "PRODUCTION_FUNDED"):
        b = D.profile_b_permission(signal_present=True, daily_stopped=False, p3_blocked=False)
        assert b["permit"] is True          # B never consults D1c
    assert D.profile_b_permission(signal_present=True, daily_stopped=True,
                                  p3_blocked=False)["permit"] is False  # but obeys daily stop


# 4. stale feed suspends Profile A
def test_4_stale_feed_suspends():
    r = D.profile_a_permission("ACTIVE_EVAL_FILTER", signal_present=True,
                               daily_stopped=False, p3_blocked=False,
                               drift_value=12, drift_sign=1, direction="long",
                               feed_age_s=99999, has_open=True)
    assert r["d1c_decision"] == "SUSPEND" and r["permit"] is False


# 5. missing 09:30 open suspends Profile A
def test_5_missing_open_suspends():
    r = D.profile_a_permission("ACTIVE_EVAL_FILTER", signal_present=True,
                               daily_stopped=False, p3_blocked=False,
                               drift_value=12, drift_sign=1, direction="long",
                               feed_age_s=10, has_open=False)
    assert r["d1c_decision"] == "SUSPEND" and not r["permit"]


# 6. zero drift suspends Profile A
def test_6_zero_drift_suspends():
    for dv, ds in ((0, 1), (12, 0), (None, 1), (12, None)):
        r = D.profile_a_permission("ACTIVE_EVAL_FILTER", signal_present=True,
                                   daily_stopped=False, p3_blocked=False,
                                   drift_value=dv, drift_sign=ds, direction="long",
                                   feed_age_s=10, has_open=True)
        assert r["d1c_decision"] == "SUSPEND" and not r["permit"]


# 7. D1c does NOT change sizing
def test_7_sizing_unchanged(env):
    s, _ = env
    p_off, _ = auto_runner.resolve_plan(Args(account="FRESH-50K", d1c_mode="off"), s)
    p_act, _ = auto_runner.resolve_plan(Args(account="FRESH-50K", d1c_mode="active-eval-filter"), s)
    assert p_off["size"] == p_act["size"] == "A3/B2"
    assert p_off["daily_stop"] == p_act["daily_stop"]   # daily stop also unchanged


# 8. D1c cannot override the daily stop
def test_8_cannot_override_daily_stop():
    r = D.profile_a_permission("ACTIVE_EVAL_FILTER", signal_present=True,
                               daily_stopped=True, p3_blocked=False,
                               drift_value=12, drift_sign=1, direction="long",  # ALLOW
                               feed_age_s=10, has_open=True)
    assert r["permit"] is False and r["reason"] == "daily stop hit"


# 9. D1c cannot override P3
def test_9_cannot_override_p3():
    r = D.profile_a_permission("ACTIVE_EVAL_FILTER", signal_present=True,
                               daily_stopped=False, p3_blocked=True,
                               drift_value=12, drift_sign=1, direction="long",  # ALLOW
                               feed_age_s=10, has_open=True)
    assert r["permit"] is False and r["reason"] == "P3 block"


# 10. production-funded blocked without approval
def test_10_production_funded_blocked(env):
    s, _ = env
    s.set_state(d1c_requested_mode="PRODUCTION_FUNDED")
    assert A.D1cGate(s).resolve("funded") == "SHADOW"          # no flags -> shadow
    _, blockers = auto_runner.resolve_plan(
        Args(mode="funded", account="MFFU-150K-1", tier="150K",
             d1c_mode="production-funded"), s)
    assert any("PRODUCTION_FUNDED" in b for b in blockers)
    for f in A.D1cGate.PROD_FLAGS:
        open(os.path.join("evidence/approvals", f), "w").close()
    assert A.D1cGate(s).resolve("funded") == "PRODUCTION_FUNDED"   # all flags -> allowed


# 11. ARES cannot remain after funded transition; D1c active-eval-filter cannot follow
def test_11_no_ares_or_eval_filter_after_funded(env):
    s, j = env
    s.set_state(zeus_accounts=json.dumps([dict(name="E1", phase="EVAL")]))
    ares_mode.arm_eval("E1", "50K-balanced", store=s, journal=j)
    ares_mode.switch_funded("E1", store=s, journal=j)
    assert ares_mode.current_mode(s, "E1") == "ZEUS_FUNDED"
    assert "E1" not in json.loads(s.get_state("ares_mode") or "{}")
    # a funded account can never resolve to ACTIVE_EVAL_FILTER
    s.set_state(d1c_requested_mode="ACTIVE_EVAL_FILTER")
    assert A.D1cGate(s).resolve("funded") == "SHADOW"
    with pytest.raises(RuntimeError):
        ares_mode.set_d1c("active-eval-filter", "funded", store=s, journal=j)


# 12. ATHENA official count does not advance from ARES eval D1c logs
def test_12_athena_count_unaffected(env):
    log = "out/ares/d1c_eval_log.csv"
    for i in range(15):
        D.log_decision("E1", "ACTIVE_EVAL_FILTER", "A-sweep", "long", 12, -1,
                       "BLOCK", "drift disagrees", permit=False, source="ares_eval", log=log)
    assert D.athena_official_count(log) == 0          # ARES eval never counts
    # a real-forward decision DOES count (proves the mechanism works)
    D.log_decision("PAPER", "SHADOW", "A-sweep", "long", 12, 1, "ALLOW", "agree",
                   permit=True, source="athena_forward", log=log)
    assert D.athena_official_count(log) == 1
