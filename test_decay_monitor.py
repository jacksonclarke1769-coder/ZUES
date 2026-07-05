"""Tests for decay_monitor.py — OBSERVATION-ONLY decay monitoring.

Every test uses tmp_path for the ledger / decision-log dir / fill-telemetry dir / status.json /
log file, so nothing here ever touches the repo's real out/ or logs/ directories.
"""
import json
import os

import decay_monitor as DM

LEDGER_COLS = ["date", "mode", "account", "strategy", "direction", "contracts", "pnl", "note"]


def _write_ledger(path, rows):
    """rows: list of dicts with (at least) date/account/strategy/direction/pnl. mode defaults live."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        fh.write(",".join(LEDGER_COLS) + "\n")
        for r in rows:
            vals = [
                r.get("date", "2026-06-01"), r.get("mode", "live"), r.get("account", "TESTACCT"),
                r.get("strategy", "A"), r.get("direction", "long"), r.get("contracts", 1),
                r.get("pnl", 0), r.get("note", "fill-backed · test"),
            ]
            fh.write(",".join(str(v) for v in vals) + "\n")


def _write_decision_log(log_dir, rows, fname="2026-06-01.jsonl"):
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, fname), "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def _decision_row(*, bar_ts, account="TESTACCT", profile="A", side="long",
                   entry=100.0, stop=90.0, qty=2, final_action="live_send"):
    return {"final_action": final_action, "bar_ts": bar_ts, "account": account, "profile": profile,
            "side": side, "entry_price": entry, "stop_price": stop, "qty_total": qty}


def _paths(tmp_path):
    return dict(
        ledger_path=str(tmp_path / "trade_results.csv"),
        decision_log_dir=str(tmp_path / "live_engine_decisions"),
        fill_telem_dir=str(tmp_path / "fill_telemetry"),          # left empty/non-existent -> guarded skip
        status_path=str(tmp_path / "status.json"),
        log_path=str(tmp_path / "decay_monitor.log"),
    )


class _FakeTelegram:
    def __init__(self):
        self.calls = []

    def info(self, text):
        self.calls.append(text)
        return True


# --------------------------------------------------------------------------- 1. healthy stream -> no alarm

def test_healthy_stream_no_alarm(tmp_path):
    rows = []
    for i in range(30):
        rows.append({"date": "2026-06-01", "pnl": 120.0, "note": "fill-backed · win"})
        rows.append({"date": "2026-06-01", "pnl": -100.0, "note": "fill-backed · loss"})
    p = _paths(tmp_path)
    _write_ledger(p["ledger_path"], rows)
    fake = _FakeTelegram()

    status = DM.run(**p, dry_run=False, telegram=fake)

    assert status["n_trades_total"] == 60
    assert status["rolling60"]["n"] == 60
    assert status["rolling60"]["insufficient"] is False
    assert status["rolling60"]["pf"] > 1.0
    assert status["alarm_pf"] is False
    assert status["alarm_streak"] == 0
    assert fake.calls == []                                     # no alert fired
    # status.json was actually written (not dry-run)
    assert os.path.exists(p["status_path"])
    on_disk = json.load(open(p["status_path"]))
    assert on_disk["alarm_pf"] is False


# --------------------------------------------------------------------------- 2. PF<1.0 sustained 20+ -> alarm once

def test_sustained_pf_below_one_alarms_once_on_transition(tmp_path):
    # 60 winners (+50 each) then 40 losers (-100 each): the trailing-60-window PF crosses below
    # 1.0 exactly 20 evaluations before the end (see decay_monitor test-design notes / task math:
    # PF(k) = 30/k - 0.5 for k losers in the window -> PF<1 iff k>20, k maxes at 40 -> exactly the
    # last 20 of the 41 possible trailing-60 evaluations are <1.0).
    rows = [{"date": "2026-06-01", "pnl": 50.0, "note": "fill-backed · win"} for _ in range(60)]
    rows += [{"date": "2026-06-02", "pnl": -100.0, "note": "fill-backed · loss"} for _ in range(40)]
    p = _paths(tmp_path)
    _write_ledger(p["ledger_path"], rows)
    fake = _FakeTelegram()

    status1 = DM.run(**p, dry_run=False, telegram=fake)
    assert status1["n_trades_total"] == 100
    assert status1["rolling60"]["insufficient"] is False
    assert status1["alarm_streak"] == 20
    assert status1["alarm_pf"] is True
    assert len(fake.calls) == 1                                  # transition off -> on: exactly one alert
    assert "PF" in fake.calls[0]

    # second run against the SAME ledger/state: alarm stays True but must NOT re-alert (no new
    # transition -- previous status.json already recorded alarm_pf True).
    status2 = DM.run(**p, dry_run=False, telegram=fake)
    assert status2["alarm_pf"] is True
    assert len(fake.calls) == 1                                  # unchanged -- no repeat alert


# --------------------------------------------------------------------------- 3. insufficient sample -> suppressed

def test_insufficient_sample_suppresses_alarm(tmp_path):
    # only 10 trades, all losers (would be PF=0 / "alarming" if judged alone) -- must be suppressed.
    rows = [{"date": "2026-06-01", "pnl": -50.0, "note": "fill-backed · loss"} for _ in range(10)]
    p = _paths(tmp_path)
    _write_ledger(p["ledger_path"], rows)
    fake = _FakeTelegram()

    status = DM.run(**p, dry_run=False, telegram=fake)

    assert status["n_trades_total"] == 10
    assert status["rolling60"]["n"] == 10
    assert status["rolling60"]["insufficient"] is True
    assert status["alarm_pf"] is False                            # suppressed despite pf==0
    assert status["window_1000_1030"]["insufficient"] is True
    assert status["window_1000_1030"]["flag"] is False
    assert fake.calls == []


# --------------------------------------------------------------------------- 4. fail-open on corrupt/missing input

def test_fail_open_missing_ledger_and_decision_log(tmp_path):
    p = _paths(tmp_path)
    # ledger_path/decision_log_dir/fill_telem_dir all point at nonexistent paths
    status = DM.run(**p, dry_run=False)
    assert status["n_trades_total"] == 0
    assert status["alarm_pf"] is False
    assert isinstance(status["errors"], list)
    # no exception -> we got this far; status.json still gets written
    assert os.path.exists(p["status_path"])


def test_fail_open_corrupt_ledger_populates_errors(tmp_path):
    p = _paths(tmp_path)
    # a directory where a file is expected -> open() raises inside the reader; must be caught,
    # logged into errors[], and NOT raise out of run().
    os.makedirs(p["ledger_path"], exist_ok=True)
    os.makedirs(p["decision_log_dir"], exist_ok=True)
    os.makedirs(os.path.join(p["decision_log_dir"], "bad.jsonl"), exist_ok=True)  # "file" is a dir

    status = DM.run(**p, dry_run=False)                          # must not raise

    assert status["n_trades_total"] == 0
    assert status["alarm_pf"] is False
    assert len(status["errors"]) >= 2                             # one for the ledger, one for the bad jsonl
    assert any("ledger" in e for e in status["errors"])
    assert any("bad.jsonl" in e for e in status["errors"])


def test_cli_main_never_raises_and_returns_zero(tmp_path, monkeypatch):
    # exercise the real CLI entrypoint against a totally empty environment (missing everything),
    # using --dry-run so nothing touches the repo's real out/ or logs/.
    monkeypatch.chdir(tmp_path)
    rc = DM.main(["--dry-run"])
    assert rc == 0


# --------------------------------------------------------------------------- 5. window filter (10:00-10:30 ET, tz-aware)

def test_engine_window_filter_selects_1000_1030_et_only():
    # 09:59:59 ET -> excluded (one second before the window)
    before = DM._parse_dt("2026-06-25 09:59:59-04:00")
    # 10:00:00 ET -> included (window start, inclusive)
    start = DM._parse_dt("2026-06-25 10:00:00-04:00")
    # 10:29:59 ET -> included (last second of the window)
    end = DM._parse_dt("2026-06-25 10:29:59-04:00")
    # 10:30:00 ET -> excluded (window end, exclusive)
    after = DM._parse_dt("2026-06-25 10:30:00-04:00")
    # same instant expressed in UTC during EDT (UTC-4): 14:00 UTC == 10:00 ET -> included
    utc_summer = DM._parse_dt("2026-06-25T14:00:00+00:00")
    # winter (EST, UTC-5): 15:00 UTC == 10:00 ET -> included (verifies DST-aware conversion)
    utc_winter = DM._parse_dt("2026-01-15T15:00:00+00:00")
    # 15:00 UTC in JUNE (EDT, UTC-4) == 11:00 ET -> excluded
    utc_summer_wrong_hour = DM._parse_dt("2026-06-25T15:00:00+00:00")

    assert DM._in_engine_window(before) is False
    assert DM._in_engine_window(start) is True
    assert DM._in_engine_window(end) is True
    assert DM._in_engine_window(after) is False
    assert DM._in_engine_window(utc_summer) is True
    assert DM._in_engine_window(utc_winter) is True
    assert DM._in_engine_window(utc_summer_wrong_hour) is False


def test_window_health_end_to_end_join_and_filter(tmp_path):
    """A ledger with 3 same-day/account/profile/side trades, joined via the decision log to entry
    times before / inside / after the 10:00-10:30 ET window -- only the inside one should count."""
    rows = [
        {"date": "2026-06-25", "account": "TESTACCT", "strategy": "A", "direction": "long", "pnl": 100.0},
        {"date": "2026-06-25", "account": "TESTACCT", "strategy": "A", "direction": "long", "pnl": 200.0},
        {"date": "2026-06-25", "account": "TESTACCT", "strategy": "A", "direction": "long", "pnl": -50.0},
    ]
    p = _paths(tmp_path)
    _write_ledger(p["ledger_path"], rows)
    decisions = [
        _decision_row(bar_ts="2026-06-25 09:45:00-04:00"),        # before window
        _decision_row(bar_ts="2026-06-25 10:05:00-04:00"),        # inside window
        _decision_row(bar_ts="2026-06-25 11:00:00-04:00"),        # after window
    ]
    _write_decision_log(p["decision_log_dir"], decisions)

    status = DM.run(**p, dry_run=False)

    assert status["window_1000_1030"]["n"] == 1
    assert "2026-W26" in status["window_1000_1030"]["week_counts"]
    assert status["window_1000_1030"]["week_counts"]["2026-W26"] == 1


def test_window_rolling40_expectancy_flag(tmp_path):
    """40 in-window trades, all losers -> rolling40_exp_r < 0 -> flag True (not suppressed, n==40)."""
    rows, decisions = [], []
    for i in range(40):
        rows.append({"date": "2026-06-25", "account": "TESTACCT", "strategy": "A",
                      "direction": "long", "pnl": -80.0})
        decisions.append(_decision_row(bar_ts=f"2026-06-25 10:1{i % 5}:0{i % 6}-04:00",
                                        entry=100.0, stop=90.0, qty=2))
    p = _paths(tmp_path)
    _write_ledger(p["ledger_path"], rows)
    _write_decision_log(p["decision_log_dir"], decisions)

    status = DM.run(**p, dry_run=False)

    assert status["window_1000_1030"]["n"] == 40
    assert status["window_1000_1030"]["insufficient"] is False
    assert status["window_1000_1030"]["rolling40_exp_r"] < 0
    assert status["window_1000_1030"]["flag"] is True


# --------------------------------------------------------------------------- misc: --dry-run doesn't write/alert

def test_dry_run_does_not_write_or_alert(tmp_path, capsys):
    rows = [{"date": "2026-06-01", "pnl": 50.0} for _ in range(5)]
    p = _paths(tmp_path)
    _write_ledger(p["ledger_path"], rows)
    fake = _FakeTelegram()

    status = DM.run(**p, dry_run=True, telegram=fake)

    assert status["n_trades_total"] == 5
    assert not os.path.exists(p["status_path"])                  # dry-run must not persist
    assert not os.path.exists(p["log_path"])                     # dry-run must not append to the log
    assert fake.calls == []                                       # dry-run never alerts (even if it would)
    out = capsys.readouterr().out
    assert '"n_trades_total": 5' in out                           # printed instead of written
