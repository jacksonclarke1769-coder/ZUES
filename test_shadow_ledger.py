"""Tests for shadow_ledger.py — OFFLINE, observation-only shadow-sizing ledger.

Every test uses tmp_path for the ledger / decision-log dir / fill-telemetry dir / rows.jsonl /
status.json, so nothing here ever touches the repo's real out/ or logs/ directories.
"""
import json
import os

import fill_telemetry
import shadow_ledger as SL

LEDGER_COLS = ["date", "mode", "account", "strategy", "direction", "contracts", "pnl", "note"]


def _write_ledger(path, rows):
    """rows: list of dicts with (at least) date/account/strategy/direction/contracts/pnl.
    mode defaults to 'live', strategy defaults to 'A'."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        fh.write(",".join(LEDGER_COLS) + "\n")
        for r in rows:
            vals = [
                r.get("date", "2026-06-01"), r.get("mode", "live"), r.get("account", "TESTACCT"),
                r.get("strategy", "A"), r.get("direction", "long"), r.get("contracts", 4),
                r.get("pnl", 0), r.get("note", "fill-backed · test"),
            ]
            fh.write(",".join(str(v) for v in vals) + "\n")


def _write_decision_log(log_dir, rows, fname="2026-06-01.jsonl"):
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, fname), "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def _decision_row(*, bar_ts, account="TESTACCT", profile="A", side="long",
                   entry=20000.0, stop=19990.0, qty=4, final_action="live_send"):
    return {"final_action": final_action, "bar_ts": bar_ts, "account": account, "profile": profile,
            "side": side, "entry_price": entry, "stop_price": stop, "qty_total": qty}


def _write_fill_telem(base_dir, rows, fname="2026-06-01.jsonl"):
    os.makedirs(base_dir, exist_ok=True)
    with open(os.path.join(base_dir, fname), "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def _ft_decision_row(*, bar_ts, account_tag="abc123", strategy="A", side="long",
                      submitted_price=20000.0, stop=19990.0, qty_formula=24, qty_cap=40):
    return {"event": "DECISION", "bar_ts": bar_ts, "account_tag": account_tag, "strategy": strategy,
            "side": side, "submitted_price": submitted_price, "stop": stop,
            "qty_formula": qty_formula, "qty_cap": qty_cap}


def _paths(tmp_path):
    return dict(
        ledger_path=str(tmp_path / "trade_results.csv"),
        decision_log_dir=str(tmp_path / "live_engine_decisions"),
        fill_telem_dir=str(tmp_path / "fill_telemetry"),
        rows_path=str(tmp_path / "shadow_ledger" / "rows.jsonl"),
        status_path=str(tmp_path / "shadow_ledger" / "status.json"),
    )


# --------------------------------------------------------------------------- 1. shadow sizing math

def test_build_shadow_rows_cap_clipping_and_qty_formula_present():
    trade = dict(date="2026-06-01", ts="2026-06-01T10:05:00-04:00", pnl=400.0, qty_filled=10,
                 entry=20000.0, stop=19990.0, qty_formula=24)
    rows, reason = SL.build_shadow_rows(trade, caps=SL.CAPS)
    assert reason is None
    by_cap = {r["cap"]: r for r in rows}
    # qty_formula=24: caps 15/20 clip to themselves; caps 25/30/40 clip to 24 (the uncapped ask)
    assert by_cap[15]["q_shadow"] == 15
    assert by_cap[20]["q_shadow"] == 20
    assert by_cap[25]["q_shadow"] == 24
    assert by_cap[30]["q_shadow"] == 24
    assert by_cap[40]["q_shadow"] == 24
    # pnl_per_contract = 400/10 = 40 -> shadow_pnl = 40 * q_shadow
    assert by_cap[15]["shadow_pnl"] == 600.0
    assert by_cap[25]["shadow_pnl"] == 960.0
    assert by_cap[15]["derived"] is False
    assert by_cap[15]["stop_pts"] == 10.0
    assert by_cap[15]["q_live"] == 10
    assert by_cap[15]["pnl_live"] == 400.0


def test_build_shadow_rows_derives_qty_formula_when_missing():
    trade = dict(date="2026-06-01", ts="2026-06-01T10:05:00-04:00", pnl=100.0, qty_filled=2,
                 entry=20000.0, stop=19990.0, qty_formula=None)
    rows, reason = SL.build_shadow_rows(trade, caps=(15,))
    assert reason is None
    # derived = int(1200 // (10 * 2)) = int(1200 // 20) = 60
    assert rows[0]["qty_formula"] == 60
    assert rows[0]["derived"] is True
    assert rows[0]["q_shadow"] == 15                # cap(15) < derived(60) -> clip to cap


def test_build_shadow_rows_skips_on_zero_qty_filled():
    trade = dict(date="2026-06-01", ts=None, pnl=100.0, qty_filled=0, entry=20000.0, stop=19990.0,
                 qty_formula=10)
    rows, reason = SL.build_shadow_rows(trade)
    assert rows == []
    assert reason == "qty_filled_missing_or_zero"


def test_build_shadow_rows_skips_on_none_qty_filled():
    trade = dict(date="2026-06-01", ts=None, pnl=100.0, qty_filled=None, entry=20000.0, stop=19990.0,
                 qty_formula=10)
    rows, reason = SL.build_shadow_rows(trade)
    assert rows == []
    assert reason == "qty_filled_missing_or_zero"


def test_build_shadow_rows_skips_when_no_entry_stop_and_no_qty_formula():
    trade = dict(date="2026-06-01", ts=None, pnl=100.0, qty_filled=4, entry=None, stop=None,
                 qty_formula=None)
    rows, reason = SL.build_shadow_rows(trade)
    assert rows == []
    assert reason == "no_entry_stop_for_derivation"


# --------------------------------------------------------------------------- 5. caveat on every row

def test_caveat_string_present_on_every_row():
    trade = dict(date="2026-06-01", ts="2026-06-01T10:05:00-04:00", pnl=400.0, qty_filled=10,
                 entry=20000.0, stop=19990.0, qty_formula=24)
    rows, _ = SL.build_shadow_rows(trade, caps=SL.CAPS)
    assert len(rows) == len(SL.CAPS)
    for r in rows:
        assert r["caveat"] == ("SHADOW FILLS INHERIT THE A10 FILL — upper bound at size; "
                                "NEVER a promotion criterion alone")


# --------------------------------------------------------------------------- 2. trajectory replay: PASS / BUST

def test_eval_replay_classifies_synthetic_pass():
    day_rows = [("2026-06-01", 1000.0), ("2026-06-02", 1000.0), ("2026-06-03", 1100.0)]
    ev = SL.eval_replay(day_rows)
    assert ev["status"] == "PASSED"
    assert ev["days_elapsed"] == 3
    assert ev["balance"] >= SL.EVAL_START + SL.EVAL_TARGET


def test_eval_replay_classifies_synthetic_bust():
    # three -1000 days in a row eats through the $2.5k trail (threshold stays 47500 since balance
    # never exceeds start) -> balance 47000 <= threshold 47500 on day 3 -> BUSTED
    day_rows = [("2026-06-01", -1000.0), ("2026-06-02", -1000.0), ("2026-06-03", -1000.0)]
    ev = SL.eval_replay(day_rows)
    assert ev["status"] == "BUSTED"
    assert ev["days_elapsed"] == 3


def test_eval_replay_running_when_neither_hit():
    day_rows = [("2026-06-01", 100.0), ("2026-06-02", -50.0)]
    ev = SL.eval_replay(day_rows)
    assert ev["status"] == "RUNNING"
    assert ev["days_elapsed"] == 2


def test_day_rows_for_cap_applies_day_stop_and_dll_clamp():
    # 3 losing shadow trades same day, each -300 -> day stop (-550) trips after the 2nd trade
    # (-600 <= -550), the 3rd trade is excluded from that day's total.
    rows = [
        {"date": "2026-06-01", "ts": "2026-06-01T09:00:00-04:00", "shadow_pnl": -300.0},
        {"date": "2026-06-01", "ts": "2026-06-01T09:05:00-04:00", "shadow_pnl": -300.0},
        {"date": "2026-06-01", "ts": "2026-06-01T09:10:00-04:00", "shadow_pnl": -300.0},
    ]
    out = SL.day_rows_for_cap(rows)
    assert out == [("2026-06-01", -600.0)]


def test_day_rows_for_cap_applies_dll_clamp_on_large_single_day_loss():
    rows = [{"date": "2026-06-01", "ts": "2026-06-01T09:00:00-04:00", "shadow_pnl": -3000.0}]
    out = SL.day_rows_for_cap(rows)
    assert out == [("2026-06-01", -1000.0)]        # clamped to -EVAL_DLL


# --------------------------------------------------------------------------- end-to-end run(): PASS/BUST per cap

def test_run_end_to_end_trajectory_bust_for_small_cap_pass_for_large(tmp_path):
    """Construct a ledger where every trade nets +$1000/contract and qty_formula is large (40), so
    a small cap (15) contracts less absolute $ per trade than a large cap (40) -- both should still
    PASS given enough winning trades, so instead we make ALL trades LOSERS to get a clean BUST for
    every cap, verifying the per-cap replay actually runs off real ledger data end to end."""
    p = _paths(tmp_path)
    rows = []
    decisions = []
    for i in range(5):
        d = f"2026-06-0{i + 1}"
        rows.append({"date": d, "account": "TESTACCT", "strategy": "A", "direction": "long",
                      "contracts": 10, "pnl": -1000.0, "note": "fill-backed · loss"})
        decisions.append(_decision_row(bar_ts=f"{d} 10:05:00-04:00", entry=20000.0, stop=19990.0, qty=10))
    _write_ledger(p["ledger_path"], rows)
    _write_decision_log(p["decision_log_dir"], decisions)

    status = SL.run(**p, dry_run=False)

    assert status["n_trades_new"] == 5
    assert status["errors"] == [] or all("fatal" not in e for e in status["errors"])
    for c in SL.CAPS:
        assert status["per_cap"][str(c)]["status"] == "BUSTED"


# --------------------------------------------------------------------------- 3. idempotent re-run

def test_idempotent_rerun_adds_nothing(tmp_path):
    p = _paths(tmp_path)
    rows = [{"date": "2026-06-01", "account": "TESTACCT", "strategy": "A", "direction": "long",
             "contracts": 10, "pnl": 500.0, "note": "fill-backed · win"}]
    decisions = [_decision_row(bar_ts="2026-06-01 10:05:00-04:00", entry=20000.0, stop=19990.0, qty=10)]
    _write_ledger(p["ledger_path"], rows)
    _write_decision_log(p["decision_log_dir"], decisions)

    status1 = SL.run(**p, dry_run=False)
    assert status1["n_trades_new"] == 1
    assert status1["n_rows_written_this_run"] == len(SL.CAPS)
    assert os.path.exists(p["rows_path"])
    with open(p["rows_path"]) as fh:
        n_lines_1 = sum(1 for _ in fh)
    assert n_lines_1 == len(SL.CAPS)

    # second run against the SAME ledger/state -- offset already advanced, nothing new to process
    status2 = SL.run(**p, dry_run=False)
    assert status2["n_trades_new"] == 0
    assert status2["n_rows_written_this_run"] == 0
    with open(p["rows_path"]) as fh:
        n_lines_2 = sum(1 for _ in fh)
    assert n_lines_2 == n_lines_1                                  # rows.jsonl unchanged
    # cumulative per-cap totals are unaffected by the no-op re-run
    assert status1["per_cap"] == status2["per_cap"]


def test_idempotent_rerun_processes_only_new_rows(tmp_path):
    p = _paths(tmp_path)
    rows = [{"date": "2026-06-01", "account": "TESTACCT", "strategy": "A", "direction": "long",
             "contracts": 10, "pnl": 500.0, "note": "fill-backed · win"}]
    decisions = [_decision_row(bar_ts="2026-06-01 10:05:00-04:00", entry=20000.0, stop=19990.0, qty=10)]
    _write_ledger(p["ledger_path"], rows)
    _write_decision_log(p["decision_log_dir"], decisions)
    SL.run(**p, dry_run=False)

    # append one more trade + decision, re-run
    rows.append({"date": "2026-06-02", "account": "TESTACCT", "strategy": "A", "direction": "long",
                 "contracts": 10, "pnl": 300.0, "note": "fill-backed · win"})
    decisions.append(_decision_row(bar_ts="2026-06-02 10:05:00-04:00", entry=20000.0, stop=19990.0, qty=10))
    _write_ledger(p["ledger_path"], rows)
    _write_decision_log(p["decision_log_dir"], decisions)

    status2 = SL.run(**p, dry_run=False)
    assert status2["n_trades_new"] == 1                             # only the new trade processed
    with open(p["rows_path"]) as fh:
        n_lines = sum(1 for _ in fh)
    assert n_lines == 2 * len(SL.CAPS)                               # 2 trades total * 5 caps


# --------------------------------------------------------------------------- 4. fail-open

def test_fail_open_missing_all_inputs(tmp_path):
    p = _paths(tmp_path)
    status = SL.run(**p, dry_run=False)
    assert status["n_trades_new"] == 0
    assert status["per_cap"] == {} or all(v["n_shadow_trades"] == 0 for v in status["per_cap"].values())
    assert isinstance(status["errors"], list)
    assert os.path.exists(p["status_path"])


def test_fail_open_corrupt_ledger_populates_errors(tmp_path):
    p = _paths(tmp_path)
    # a directory where a file is expected -> open() raises inside the reader; must be caught,
    # logged into errors[], and NOT raise out of run().
    os.makedirs(p["ledger_path"], exist_ok=True)

    status = SL.run(**p, dry_run=False)                            # must not raise

    assert status["n_trades_new"] == 0
    assert any("ledger" in e for e in status["errors"])


def test_fail_open_corrupt_decision_log_populates_errors(tmp_path):
    p = _paths(tmp_path)
    rows = [{"date": "2026-06-01", "account": "TESTACCT", "strategy": "A", "direction": "long",
             "contracts": 10, "pnl": 100.0}]
    _write_ledger(p["ledger_path"], rows)
    os.makedirs(p["decision_log_dir"], exist_ok=True)
    os.makedirs(os.path.join(p["decision_log_dir"], "bad.jsonl"), exist_ok=True)  # "file" is a dir

    status = SL.run(**p, dry_run=False)                            # must not raise

    assert any("bad.jsonl" in e for e in status["errors"])
    # the trade itself still gets skipped for lack of entry/stop, tracked, not crashed
    assert status["skipped"].get("no_entry_stop_for_derivation") == 1


def test_cli_main_never_raises_and_returns_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = SL.main(["--dry-run"])
    assert rc == 0


def test_dry_run_does_not_write_rows_or_status(tmp_path):
    p = _paths(tmp_path)
    rows = [{"date": "2026-06-01", "account": "TESTACCT", "strategy": "A", "direction": "long",
             "contracts": 10, "pnl": 500.0}]
    decisions = [_decision_row(bar_ts="2026-06-01 10:05:00-04:00", entry=20000.0, stop=19990.0, qty=10)]
    _write_ledger(p["ledger_path"], rows)
    _write_decision_log(p["decision_log_dir"], decisions)

    status = SL.run(**p, dry_run=True)

    assert status["n_trades_new"] == 1
    assert not os.path.exists(p["rows_path"])
    assert not os.path.exists(p["status_path"])


# --------------------------------------------------------------------------- fill-telemetry DECISION match (qty_formula)

def test_run_uses_fill_telemetry_qty_formula_when_matched(tmp_path):
    p = _paths(tmp_path)
    account = "TESTACCT"
    tag = fill_telemetry.account_tag(account)
    rows = [{"date": "2026-06-01", "account": account, "strategy": "A", "direction": "long",
             "contracts": 10, "pnl": 500.0}]
    _write_ledger(p["ledger_path"], rows)
    _write_fill_telem(p["fill_telem_dir"], [
        _ft_decision_row(bar_ts="2026-06-01 10:05:00-04:00", account_tag=tag, qty_formula=33),
    ])

    status = SL.run(**p, dry_run=True)

    assert status["n_trades_new"] == 1
    assert status["skipped"] == {}
    assert status["per_cap"]["40"]["n_shadow_trades"] == 1
    # qty_formula=33 -> cap 40 clips to 33, not derived
    assert status["per_cap"]["40"]["cumulative_shadow_pnl"] == round(500.0 / 10 * 33, 2)


# --------------------------------------------------------------------------- pooled fill-evidence counters

def test_fill_evidence_pools_touch_and_fill_confirmed_events(tmp_path):
    base = str(tmp_path / "fill_telemetry")
    os.makedirs(base, exist_ok=True)
    events = [
        {"event": "TOUCH", "sid": "s1", "side": "long", "level": 100.0, "low": 99.0, "high": 100.5},
        {"event": "ORDER_RESOLVED", "sid": "s1", "touch_seq": 1, "reason": "ttl"},
        {"event": "TOUCH", "sid": "s2", "side": "short", "level": 100.0, "low": 99.5, "high": 100.8},
        {"event": "FILL_CONFIRMED", "expected": 4, "broker": 2, "partial_fill": True,
         "time_to_fill_s": 12.5},
    ]
    with open(os.path.join(base, "2026-06-01.jsonl"), "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")

    errors = []
    ev = SL._read_fill_evidence(base, errors)

    assert ev["distinct_touched_orders"] == 2
    assert ev["touch_without_fill_count"] == 1
    assert ev["touch_without_fill_rate"] == 0.5
    assert ev["mean_abs_penetration"] == round((1.0 + 0.8) / 2, 4)
    assert ev["partial_fill_count"] == 1
    assert ev["fill_confirmed_count"] == 1
    assert ev["mean_time_to_fill_s"] == 12.5


def test_fill_evidence_empty_dir_returns_none_stats(tmp_path):
    errors = []
    ev = SL._read_fill_evidence(str(tmp_path / "nonexistent"), errors)
    assert ev["distinct_touched_orders"] == 0
    assert ev["touch_without_fill_rate"] is None
    assert ev["mean_abs_penetration"] is None
    assert ev["mean_time_to_fill_s"] is None


# --------------------------------------------------------------------------- Task-3 placeholders never auto-flag

def test_kill_switch_placeholders_reported_never_flagged(tmp_path):
    p = _paths(tmp_path)
    status = SL.run(**p, dry_run=False)
    assert status["kill_touch_no_fill_pct"] is None
    assert status["kill_slip_r"] == -0.05
