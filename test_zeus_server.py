"""ZEUS terminal tests: state shape, freshness, voice, oracle, and the CRITICAL
SAFETY REQUIREMENTS (no control paths: no lockout override, no live-enable,
no strategy mutation, alerts not hideable)."""
import json
import pytest
import zeus_server
from zeus_server import APP, CFG


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)               # isolated dbs/evidence
    import os
    os.makedirs("data", exist_ok=True)
    CFG["demo"] = False
    return APP.test_client()


def test_state_shape_and_freshness(client):
    r = client.get("/api/state")
    s = r.get_json()
    for key in ("meta", "header", "portfolio", "accounts", "strategies", "weekly",
                "trades", "journal", "recon", "alerts", "evidence"):
        assert key in s, key
    assert s["meta"]["refresh_ms"] is not None          # recomputed, timed
    assert s["meta"]["refreshed"]                       # last-refreshed shown
    assert s["meta"]["mode"] in ("SIM", "PAPER", "LIVE", "LOCKED", "DEMO-PREVIEW")
    assert isinstance(s["meta"]["trading_allowed"], bool)
    assert s["meta"]["next_session"]


def test_two_refreshes_recompute(client):
    a = client.get("/api/state").get_json()["meta"]["refreshed"]
    b = client.get("/api/state").get_json()["meta"]["refreshed"]
    assert b >= a and a != ""                           # nothing cached/stale


def test_voice_lines():
    v = zeus_server.voice("SIM", None, [], True, "FULL STRENGTH")
    assert "ZEUS is awake" in v
    v = zeus_server.voice("SIM", None, [], False, "FULL STRENGTH")
    assert "gates" in v.lower()
    v = zeus_server.voice("LOCKED", "x|y", [], False, "FULL STRENGTH")
    assert "BLACK ALERT" in v and "throne is locked" in v.lower() or "throne" in v.lower()
    v = zeus_server.voice("SIM", None, [], True, "DEGRADED")
    assert "oracle weakens" in v.lower()


def test_lockout_forces_black_and_voice(client, monkeypatch):
    j, store = zeus_server.dbs()
    store.set_state(emergency_lockout="2026|ALL|test|flat=True")
    s = client.get("/api/state").get_json()
    assert s["header"]["tier"] == "BLACK"
    assert s["meta"]["trading_allowed"] is False
    assert "throne is locked" in s["meta"]["voice"].lower()
    store.set_state(emergency_lockout="")


def test_oracle_ten_sections(client):
    o = client.get("/api/oracle").get_json()
    assert len(o["sections"]) == 10
    assert "frozen" in o["sections"]["10. Proposed refinements"]
    assert all(r["label"] in ("OBSERVATION", "INVESTIGATION", "PROPOSED TEST",
                              "REJECTED", "APPROVED FOR PAPER", "APPROVED FOR LIVE")
               for r in o["recommendations"])


def test_SAFETY_no_control_endpoints():
    """The server must expose NO route that can mutate trading logic/state."""
    forbidden = ("enable", "live", "lockout", "clear", "override", "strategy",
                 "size", "p3", "config", "flatten", "order", "trade/place")
    for rule in APP.url_map.iter_rules():
        r = str(rule).lower()
        if r.startswith("/api/"):
            assert r in ("/api/state", "/api/oracle", "/api/trade/<cl>", "/api/ack", "/api/campaign",
                         "/api/calendar",          # calendar = read-only daily-P&L view
                         "/api/review_trades",     # review_trades = read-only per-trade list
                         "/api/review_week",       # review_week = read-only fidelity verdict
                         "/api/validation",        # v3: read-only apex_validation.json
                         "/api/heartbeat",         # v3: read-only heartbeat + freshness
                         "/api/exec_telemetry",     # v3: read-only exec telemetry CSV
                         "/api/forecast"), r        # v3: read-only conditional pass forecast
        methods = rule.methods - {"HEAD", "OPTIONS"}
        if "POST" in methods:
            assert str(rule) == "/api/ack"              # the ONLY write: journaled ack


def test_SAFETY_ack_does_not_dismiss_alert(client):
    """Ack records awareness; alert remains while its condition persists."""
    j, store = zeus_server.dbs()
    store.set_state(emergency_lockout="2026|ALL|sticky|flat=True")
    client.post("/api/ack", json=dict(name="lockout_active", note="seen it"))
    s = client.get("/api/state").get_json()
    names = [a["name"] for a in s["alerts"]]
    assert "lockout_active" in names                    # NOT hidden by ack
    acked = [a for a in s["alerts"] if a["name"] == "lockout_active"][0]
    assert acked["acked"] is True
    # and the ack is journaled
    n = j.con.execute("SELECT COUNT(*) FROM ledger WHERE payload_json LIKE '%alert_ack%'"
                      ).fetchone()[0]
    assert n >= 1
    store.set_state(emergency_lockout="")


def test_every_alert_has_action(client):
    j, store = zeus_server.dbs()
    store.set_state(emergency_lockout="2026|ALL|t|flat=True")
    s = client.get("/api/state").get_json()
    for a in s["alerts"]:
        assert a["action"] and len(a["action"]) > 3
    store.set_state(emergency_lockout="")


def test_trade_evidence_export(client):
    j, _ = zeus_server.dbs()
    cl = j.intent("A1", "A", "A", "tz", "entry", dict(side="Buy", qty=4, entry=1.0,
                                                      stop=0.5, target=2.0))
    r = client.get(f"/api/trade/{cl}").get_json()
    assert r[0]["cl_ord_id"] == cl and r[0]["events"][0]["event_type"] == "INTENT"


def test_command_centre_blocks(client):
    s = client.get("/api/state").get_json()
    for key in ("brief", "actions", "activity", "lights", "week_panel"):
        assert key in s, key
    assert isinstance(s["brief"], str) and len(s["brief"]) > 20
    assert set(s["lights"]) == {"Strategy A", "Strategy B (off)", "Journal",
                                "Reconciliation", "Broker", "Infrastructure"}
    assert all(v in ("green", "yellow", "red", "off") for v in s["lights"].values())
    assert len(s["activity"]) <= 5
    assert "pnl_ytd" in s["portfolio"]


def test_brief_reports_action_required_on_lockout(client):
    import zeus_server
    j, store = zeus_server.dbs()
    store.set_state(emergency_lockout="2026|ALL|brief-test|flat=True")
    s = client.get("/api/state").get_json()
    assert "locked" in s["brief"].lower()
    assert any("lockout" in a.lower() for a in s["actions"])
    store.set_state(emergency_lockout="")


def test_plan_block_and_strategy_stream_points(client):
    s = client.get("/api/state").get_json()
    assert s["plan"]["avg"]["pts_wk"] == 30 and s["plan"]["strong"]["pts_wk"] == 54
    assert "planning baseline" in s["brief"].lower() or s["week_panel"]["avg12"] is None
    # strategy-stream dedupe: same signal on N accounts counts points once
    import zeus_server
    j, _ = zeus_server.dbs()
    for acct in ("X1", "X2", "X3"):
        cl = j.intent(acct, "A", "A", "sigdup", "entry",
                      dict(side="Buy", qty=4, entry=100.0, stop=90.0, target=120.0))
        j.append("SEND", acct, cl); j.append("ACK", acct, cl)
        j.append("FILL", acct, cl, payload=dict(qty=4, side="Buy", px=100.0))
        j.append("EXIT", acct, cl, payload=dict(px=110.0, reason="target"))
    s = client.get("/api/state").get_json()
    wk = s["weekly"]["weeks"][0]
    assert abs(wk["A"] - 10.0) < 0.2         # 10 pts counted ONCE, not 3x
    assert abs(wk["usd"] - 3 * 80.0) < 1     # dollars: all 3 accounts (10pt*2$*4qty)


def test_regime_monitor_block_read_only(client):
    """ATHENA II monitoring: state carries regime + d1c shadow status; purely read-only."""
    s = client.get("/api/state").get_json()
    assert "regime_monitor" in s
    rm = s["regime_monitor"]
    assert set(rm.keys()) == {"regime", "d1c_shadow", "d1c_candidate", "stats_12mo"}
    st = rm["stats_12mo"]
    assert st["base"]["trades_wk"] > 0 and st["d1c"]["wr_pct"] > st["base"]["wr_pct"]
    assert "PAPER-ONLY" in st["note"]
    # frozen candidate stats must be clearly paper-only and display-only
    cd = rm["d1c_candidate"]
    assert cd["paper_only"] is True
    assert "production OFF" in cd["label"]
    assert cd["mc_net_delta_pct"] == 52
    # if the prometheus regime file exists it must carry the tripwire fields
    if rm["regime"] is not None:
        for k in ("status", "median_stop_distance_pts", "rolling_252_pf"):
            assert k in rm["regime"], k
        assert rm["regime"]["status"] in ("GREEN", "YELLOW", "RED")
    # no new routes were added for this (safety whitelist untouched)
    from zeus_server import APP as _APP
    api_rules = sorted(str(r) for r in _APP.url_map.iter_rules() if str(r).startswith("/api/"))
    assert api_rules == ["/api/ack", "/api/calendar", "/api/campaign", "/api/exec_telemetry",
                         "/api/forecast", "/api/heartbeat", "/api/oracle", "/api/review_trades",
                         "/api/review_week", "/api/state", "/api/trade/<cl>",
                         "/api/validation"]  # v3 read-only additions


def test_ares_safety_rail(client):
    """ARES cannot be armed on a funded account; if forced, dashboard raises RED."""
    import zeus_server, ares_mode, json
    j, store = zeus_server.dbs()
    # register one funded + one eval account
    store.set_state(zeus_accounts=json.dumps([
        dict(name="ACC-EVAL", phase="EVAL", size=150000, dd=4500, balance=152000,
             floor=145500, alloc_a=8, alloc_b=4, paid=0),
        dict(name="ACC-FUND", phase="FUNDED", size=150000, dd=4500, balance=151000,
             floor=145600, alloc_a=4, alloc_b=2, paid=0)]))
    # arming an EVAL account is allowed
    ares_mode.arm_eval("ACC-EVAL", "150K-balanced", store=store, journal=j)
    s = client.get("/api/state").get_json()
    assert s["ares"]["active"] and "ACC-EVAL" in s["ares"]["accounts"]
    assert s["ares"]["violation"] == []
    # arming a FUNDED account is REFUSED
    import pytest as _pt
    with _pt.raises(RuntimeError):
        ares_mode.arm_eval("ACC-FUND", "150K-balanced", store=store, journal=j)
    # if ARES somehow active on a funded account -> RED alert + violation
    store.set_state(ares_mode=json.dumps({"ACC-FUND": {"size": "A8/B4"}}))
    s = client.get("/api/state").get_json()
    assert "ACC-FUND" in s["ares"]["violation"]
    assert s["header"]["tier"] == "RED"
    assert any(a["name"] == "ares_on_funded_account" for a in s["alerts"])
    store.set_state(ares_mode="{}", zeus_accounts="[]")
