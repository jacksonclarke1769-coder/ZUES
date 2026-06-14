"""BRIDGE — TradersPost execution layer tests. The 17 required + hard rejections.
ZEUS decides, BRIDGE transmits, TradersPost executes. If ZEUS blocks, no webhook."""
import json
import os
import pytest
from store import Store
from journal import Journal
import bridge_traderspost as BP
import bridge_sender as BS
import auto_runner


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("data", exist_ok=True)
    os.makedirs("evidence/approvals", exist_ok=True)
    os.makedirs("out/ares", exist_ok=True)
    return Store("data/bot.db"), Journal("data/journal.db")


def _entry(**kw):
    base = dict(account="MFFU-50K-1", strategy="A", setup="sweep-OTE",
                signal_ts="2026-06-14T09:35:00", side="long", qty=3,
                entry=22050.0, stop=21985.0, target=22180.0, root="MNQ",
                mode_meta=dict(mode="ARES"), d1c_meta=dict(decision="ALLOW"))
    base.update(kw)
    return BP.build_entry(**base)


# 1. long bracket payload correct
def test_1_long_bracket(env):
    p, err = _entry(side="long")
    assert err is None
    assert p["action"] == "buy" and p["quantity"] == 3
    assert p["stopLoss"]["stopPrice"] < p["limitPrice"] < p["takeProfit"]["limitPrice"]
    assert p["ticker"] == "MNQ" and p["extras"]["signalId"].startswith("ZB-")


# 2. short bracket payload correct
def test_2_short_bracket(env):
    p, err = _entry(side="short", entry=22050.0, stop=22115.0, target=21920.0)
    assert err is None
    assert p["action"] == "sell"
    assert p["takeProfit"]["limitPrice"] < p["limitPrice"] < p["stopLoss"]["stopPrice"]


# 3. stop/target on wrong side blocks payload
def test_3_wrong_side_blocks(env):
    p, err = _entry(side="long", stop=22115.0, target=21985.0)   # inverted
    assert p is None and "wrong side" in err
    p2, err2 = _entry(side="short", stop=21985.0, target=22180.0)  # inverted
    assert p2 is None and "wrong side" in err2


# 4. MNQ tick rounding correct
def test_4_tick_rounding(env):
    assert BP.round_tick(22050.13, "MNQ") == 22050.25
    assert BP.round_tick(22050.10, "MNQ") == 22050.00
    p, _ = _entry(entry=22050.13, stop=21985.06, target=22180.19)
    assert p["limitPrice"] == 22050.25 and p["stopLoss"]["stopPrice"] == 21985.0


# 5. duplicate signal id blocked
def test_5_duplicate_blocked(env):
    s, j = env
    snd = BS.BridgeSender(store=s, journal=j, mode="test", test_url="http://x")
    p, _ = _entry()
    snd._mark(p["extras"]["signalId"], "confirmed")     # pretend first send confirmed
    r = snd.send(p)
    assert not r["sent"] and "duplicate" in r["reason"]


# 6. dry-run cannot send live webhook
def test_6_dryrun_no_send(env):
    s, j = env
    snd = BS.BridgeSender(store=s, journal=j, mode="dry-run", live_url="http://should-not")
    p, _ = _entry()
    r = snd.send(p)
    assert not r["sent"] and "dry-run" in r["reason"]


# 7. live webhook requires approval file
def test_7_live_requires_approval(env):
    s, j = env
    snd = BS.BridgeSender(store=s, journal=j, mode="live", live_url="http://x")
    p, _ = _entry()
    r = snd.send(p)
    assert not r["sent"] and "traderspost-approved" in r["reason"]


# 8. missing account blocks
def test_8_missing_account(env):
    p, err = _entry(account="")
    # builder still builds (account empty in meta) but live send refuses no-account
    s, j = env
    open("evidence/approvals/traderspost-approved.flag", "w").close()
    snd = BS.BridgeSender(store=s, journal=j, mode="live", live_url="http://x")
    r = snd.send(p)
    assert not r["sent"] and "account" in r["reason"]


# 9. daily stop blocks (no payload reaches send)
def test_9_daily_stop_blocks(env):
    s, j = env
    snd = BS.BridgeSender(store=s, journal=j, mode="test", test_url="http://x")
    r = BS.process_profile_a(snd, lambda **k: _entry(**k), d1c_mode="ACTIVE_EVAL_FILTER",
                             daily_stopped=True, p3_blocked=False, drift_value=12,
                             drift_sign=1, account="A", strategy="A", setup="s",
                             signal_ts="t", side="long", qty=3, entry=22050.0,
                             stop=21985.0, target=22180.0)
    assert not r["sent"] and "daily stop" in r["reason"]


# 10. P3 red blocks
def test_10_p3_blocks(env):
    s, j = env
    snd = BS.BridgeSender(store=s, journal=j, mode="test", test_url="http://x")
    r = BS.process_profile_a(snd, lambda **k: _entry(**k), d1c_mode="ACTIVE_EVAL_FILTER",
                             daily_stopped=False, p3_blocked=True, drift_value=12,
                             drift_sign=1, account="A", strategy="A", setup="s",
                             signal_ts="t", side="long", qty=3, entry=22050.0,
                             stop=21985.0, target=22180.0)
    assert not r["sent"] and "P3" in r["reason"]


# 11. D1c block prevents webhook
def test_11_d1c_block(env):
    s, j = env
    snd = BS.BridgeSender(store=s, journal=j, mode="test", test_url="http://x")
    r = BS.process_profile_a(snd, lambda **k: _entry(**k), d1c_mode="ACTIVE_EVAL_FILTER",
                             daily_stopped=False, p3_blocked=False, drift_value=12,
                             drift_sign=-1, account="A", strategy="A", setup="s",
                             signal_ts="t", side="long", qty=3, entry=22050.0,
                             stop=21985.0, target=22180.0)   # drift disagrees -> BLOCK
    assert not r["sent"] and "blocked Profile A" in r["reason"]


# 12. ARES cannot run on funded account (through runner)
def test_12_ares_not_on_funded(env):
    s, _ = env
    s.set_state(zeus_accounts=json.dumps([dict(name="F1", phase="FUNDED")]))
    class A:
        mode="eval"; account="F1"; tier="50K-conservative"; dry_run=True
        paper=False; live=False; dashboard_green=False; d1c_mode="shadow"
        execution="traderspost"; webhook_mode="dry-run"
    _, blockers = auto_runner.resolve_plan(A(), s)
    assert any("FUNDED" in b for b in blockers)


# 13. funded cannot use ARES (eval) sizing
def test_13_funded_no_ares_size(env):
    import auto_safety
    with pytest.raises(ValueError):
        auto_safety.tier_spec("funded", "50K-conservative")   # eval tier not in funded table


# 14. emergency flatten payload exists
def test_14_emergency_flatten(env):
    p, err = BP.build_flatten(account="MFFU-50K-1", root="MNQ")
    assert err is None and p["action"] == "exit"
    assert p["extras"]["emergency"] is True and p["extras"]["signalId"].startswith("ZB-")


# 15. retry cannot duplicate orders (same signalId; pending != confirmed)
def test_15_retry_no_duplicate(env):
    s, j = env
    open("evidence/approvals/traderspost-approved.flag", "w").close()
    snd = BS.BridgeSender(store=s, journal=j, mode="live", live_url="http://127.0.0.1:0")
    p, _ = _entry()
    r1 = snd.send(p)                  # network fails -> left 'pending', not confirmed
    assert not r1["sent"]
    # a confirmed send would block; pending allows a genuine retry of the SAME id only
    assert not snd.already_sent(p["extras"]["signalId"])
    snd._mark(p["extras"]["signalId"], "confirmed")
    r2 = snd.send(p)
    assert not r2["sent"] and "duplicate" in r2["reason"]


# 16. dashboard shows TradersPost route
def test_16_dashboard_route(env, monkeypatch):
    import zeus_server
    s, _ = env
    s.set_state(execution_route="traderspost", webhook_mode="dry-run")
    zeus_server.CFG["demo"] = False
    monkeypatch.setattr(zeus_server, "dbs", lambda: (Journal("data/journal.db"), s))
    st = zeus_server.assemble_state()
    assert st["deployment"]["execution_route"] == "TRADERSPOST"
    assert st["deployment"]["webhook_mode"] == "DRY-RUN"


# 17. ATHENA official count unaffected by bridge webhooks
def test_17_athena_unaffected(env):
    import d1c_filter
    s, j = env
    snd = BS.BridgeSender(store=s, journal=j, mode="dry-run")
    for i in range(10):
        snd.send(_entry(signal_ts=f"t{i}")[0])
    # bridge log is separate from the d1c eval log; athena count reads d1c log only
    assert d1c_filter.athena_official_count("out/ares/d1c_eval_log.csv") == 0
