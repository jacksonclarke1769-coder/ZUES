"""ARES AUTO safety-rail tests — each HARD REJECTION CONDITION must fail closed."""
import json
import os
import pytest
from store import Store
from journal import Journal
import auto_safety as A
import ares_mode
import auto_runner


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("data", exist_ok=True)
    os.makedirs("evidence/approvals", exist_ok=True)
    return Store("data/bot.db"), Journal("data/journal.db")


class Args:
    def __init__(self, **k):
        self.mode = k.get("mode", "eval"); self.account = k.get("account", "ACC")
        self.tier = k.get("tier", "50K-conservative")
        self.dry_run = k.get("dry_run", True); self.paper = k.get("paper", False)
        self.live = k.get("live", False); self.dashboard_green = k.get("dashboard_green", False)


# 1. account cannot default silently — argparse requires it
def test_account_required():
    with pytest.raises(SystemExit):
        auto_runner.main(["--mode", "eval", "--tier", "50K-conservative"])  # no --account


# 2. worst-day >= buffer must BLOCK
def test_size_block_worstday_exceeds_buffer(env):
    s, _ = env
    spec = A.tier_spec("eval", "150K-aggressive")    # worst day 4892
    ok, why = A.validate_size(spec, 4500)            # buffer 4500 -> block
    assert not ok and "BLOCK" in why
    ok2, _ = A.validate_size(A.tier_spec("eval", "150K-balanced"), 4500)  # 3841<4500
    assert ok2


# 3. ARES cannot run on a funded account
def test_ares_refused_on_funded(env):
    s, j = env
    s.set_state(zeus_accounts=json.dumps([dict(name="F1", phase="FUNDED")]))
    with pytest.raises(RuntimeError):
        ares_mode.arm_eval("F1", "50K-conservative", store=s, journal=j)
    plan, blockers = auto_runner.resolve_plan(
        Args(mode="eval", account="F1", tier="50K-conservative"), s)
    assert any("FUNDED" in b for b in blockers)


# 4. D1c production cannot turn on accidentally — locked without all flags
def test_d1c_production_locked(env):
    s, _ = env
    s.set_state(d1c_requested_mode="PRODUCTION")     # requested, but no flags
    assert A.D1cGate(s).mode() == "SHADOW"           # falls back to shadow
    for f in ("approve-d1c-production.flag", "athena-allows-d1c.flag",
              "d1c-gate-test-pass.flag"):
        open(os.path.join("evidence/approvals", f), "w").close()
    assert A.D1cGate(s).mode() == "PRODUCTION"        # only with ALL flags


# 5. daily stop cannot be bypassed by restart (persisted by date)
def test_daily_stop_survives_restart(env):
    s, _ = env
    g = A.DailyGuard(s)
    g.record("ACC", "2026-06-14", -800, 700)         # exceeds -700
    assert g.is_stopped("ACC", "2026-06-14")
    g2 = A.DailyGuard(Store("data/bot.db"))           # "restart": new instance, same db
    assert g2.is_stopped("ACC", "2026-06-14")         # still stopped
    plan, blockers = auto_runner.resolve_plan(
        Args(account="ACC", tier="50K-conservative"), s)
    # note: et_date() is today; seed today's stop to assert the runner blocks
    g.stop_now("ACC", auto_runner.et_date())
    _, blockers2 = auto_runner.resolve_plan(Args(account="ACC", tier="50K-conservative"), s)
    assert any("DAILY STOP" in b for b in blockers2)


# 6. live cannot start without the full latch set
def test_live_blocked_without_latches(env):
    s, _ = env
    ok, fails = A.live_latches("ACC", s, dashboard_green=False)
    assert not ok
    assert any("approval" in f for f in fails)
    assert any("smoke" in f for f in fails)
    assert any("B1" in f for f in fails)
    # even with approval+firm+dash, B1 + smoke still block (honest: not ready today)
    for f in ("live-approved.flag", "firm-rules-confirmed.flag"):
        open(os.path.join("evidence/approvals", f), "w").close()
    ok2, fails2 = A.live_latches("ACC", s, dashboard_green=True)
    assert not ok2 and any("B1" in f for f in fails2)


# 7. broker smoke without creds = fail -> live blocked
def test_broker_smoke_fails_without_creds(env):
    s, _ = env
    r = A.broker_smoke(creds_available=False)
    assert not r["passed"] and not r["ran"]
    assert not A.smoke_passed(Store("data/bot.db"))


# 8. dry-run is the default and places no orders (returns 0, valid plan)
def test_dryrun_default_safe(env):
    s, _ = env
    plan, blockers = auto_runner.resolve_plan(
        Args(account="FRESH-50K", tier="50K-conservative"), s)
    assert plan["exec_mode"] == "dry-run"
    assert plan["available_buffer"] == 2000           # fresh eval = full buffer
    assert plan["size_ok"] and not blockers           # conservative passes on fresh 50K


# 9. switch-funded ends ARES and sets lower-size funded mode + P3
def test_switch_funded(env):
    s, j = env
    s.set_state(zeus_accounts=json.dumps([dict(name="E1", phase="EVAL")]))
    ares_mode.arm_eval("E1", "50K-balanced", store=s, journal=j)
    assert ares_mode.current_mode(s, "E1") == "ARES"
    fm = ares_mode.switch_funded("E1", store=s, journal=j)
    assert fm["p3"] and fm["size"] == "A2/B1"          # lower size, P3 on
    assert ares_mode.current_mode(s, "E1") == "ZEUS_FUNDED"
    assert "E1" not in json.loads(s.get_state("ares_mode") or "{}")


# 10. ops_flatten paper path works (emergency control present + functional)
def test_ops_flatten_paper(env):
    import ops_flatten
    rc = ops_flatten.main(["--paper", "--account", "PAPER-1"])
    assert rc == 0
