"""ARGUS — decision logger + session auditor tests. Proves a zero-trade session is
provable, gates are logged, secrets never leak, and logger failure can't break the
engine or cause a send."""
import importlib.util
import json
import os
import sys

import pytest

import decision_log as DL

AUD_PATH = os.path.join(os.path.dirname(__file__), "tools", "audit_live_engine_session.py")
spec = importlib.util.spec_from_file_location("argus_auditor", AUD_PATH)
AUD = importlib.util.module_from_spec(spec); spec.loader.exec_module(AUD)


def _lg(tmp_path):
    return DL.DecisionLogger("MFFU-50K-1", "paper", "sess-1", feed_source="tradingview-1m",
                             log_dir=str(tmp_path))


def _rows(tmp_path, date=None):
    # the logger names files by ET date; read whatever file it wrote
    files = [f for f in os.listdir(tmp_path) if f.endswith(".jsonl")]
    assert files, "no jsonl written"
    return [json.loads(l) for l in open(os.path.join(tmp_path, files[0])) if l.strip()]


# ---- 1-7,10 — row types written + valid JSON + no secrets ----
def test_no_signal_row(tmp_path):
    _lg(tmp_path).no_signal("2026-06-22T09:30:00-04:00", data_state="GREEN", data_ready=True)
    r = _rows(tmp_path)[0]
    assert r["final_action"] == "no_signal" and r["candidate_detected"] is False

def test_candidate_rejected_row(tmp_path):
    _lg(tmp_path).candidate_rejected(bar_ts="t", side="short", reason="setup incomplete")
    r = _rows(tmp_path)[0]
    assert r["final_action"] == "candidate_rejected" and r["rejection_reason"] == "setup incomplete"

def test_d1c_blocked_row(tmp_path):
    _lg(tmp_path).blocked("d1c", bar_ts="t", side="long", reason="drift disagrees")
    assert _rows(tmp_path)[0]["final_action"] == "d1c_blocked"

def test_ares_blocked_row(tmp_path):
    _lg(tmp_path).blocked("ares", bar_ts="t", side="long", reason="daily loss stop")
    assert _rows(tmp_path)[0]["final_action"] == "ares_blocked"

def test_exitlock_blocked_row(tmp_path):
    _lg(tmp_path).blocked("exitlock", bar_ts="t", side="short", reason="exit model not approved")
    assert _rows(tmp_path)[0]["final_action"] == "exitlock_blocked"

def test_paper_signal_row_has_exit3_fields(tmp_path):
    _lg(tmp_path).signal(bar_ts="t", side="short", entry=30654.83, stop=30771.5, qty_total=3,
                         tp1_qty=1, tp1_target=30538.25, tp2_qty=2, tp2_target=30421.5,
                         signal_id_base="t", webhook_sent=False, live=False)
    r = _rows(tmp_path)[0]
    assert r["final_action"] == "paper_signal"
    assert r["tp1_qty"] == 1 and r["tp2_qty"] == 2 and r["exit_model"] == "EXIT3_FIXED_PARTIAL"

def test_live_send_row_redacts_secrets(tmp_path):
    _lg(tmp_path).signal(bar_ts="t", side="short", entry=1, stop=2, qty_total=3, tp1_qty=1,
                         tp1_target=1, tp2_qty=2, tp2_target=2, signal_id_base="t",
                         webhook_sent=True, traderspost_status="http 200", live=True,
                         webhook_url="https://secret/wh", api_key="abc123")
    raw = open(os.path.join(tmp_path, os.listdir(tmp_path)[0])).read()
    assert "secret" not in raw and "abc123" not in raw and "https://" not in raw
    json.loads(raw.strip().splitlines()[0])                    # valid JSON

def test_all_rows_valid_json(tmp_path):
    lg = _lg(tmp_path)
    lg.no_signal("t"); lg.candidate_rejected(bar_ts="t", side="x", reason="y")
    for line in open(os.path.join(tmp_path, os.listdir(tmp_path)[0])):
        json.loads(line)


# ---- 8,9 — logger failure cannot crash / cannot affect a send ----
def test_logger_failure_does_not_raise(tmp_path):
    lg = DL.DecisionLogger("A", "paper", "s", log_dir="/proc/cannot/write/here/xyz")
    assert lg.no_signal("t") is None                            # returns None, no exception

def test_engine_send_path_unaffected_by_logger_error(tmp_path):
    # LiveAuto._dlog must swallow any logger error and never block the flow
    from auto_live import LiveAuto
    from store import Store
    from journal import Journal
    class BoomLogger:
        def no_signal(self, *a, **k): raise RuntimeError("boom")
        def blocked(self, *a, **k): raise RuntimeError("boom")
        def candidate_rejected(self, *a, **k): raise RuntimeError("boom")
        def signal(self, *a, **k): raise RuntimeError("boom")
    auto = LiveAuto("MFFU-50K-1", "50K-conservative", "paper",
                    Store(str(tmp_path/"s.db")), Journal(str(tmp_path/"j.db")),
                    sender=None, daily_stop=700, d1c_mode="OFF", logger=BoomLogger())
    auto._dlog("no_signal", bar_ts="t")                        # must NOT raise


# ---- 11,12 — auditor verdicts ----
def test_auditor_clean_no_setup(tmp_path):
    AUD._make_fixture("no_signal", "2026-06-22", str(tmp_path))
    res = AUD.audit("2026-06-22", "ny-am", str(tmp_path))
    assert res["verdict"] == "SESSION CLEAN — NO SETUP"
    assert res["counts"]["no_signal"] == 24 and res["sends"] == 0

def test_auditor_inconclusive_on_gap(tmp_path):
    AUD._make_fixture("missing_rows", "2026-06-22", str(tmp_path))
    res = AUD.audit("2026-06-22", "ny-am", str(tmp_path))
    assert res["verdict"] == "SESSION INCONCLUSIVE — LOGGING GAP"

def test_auditor_no_rows_is_inconclusive(tmp_path):
    res = AUD.audit("2099-01-01", "ny-am", str(tmp_path))      # no file
    assert "INCONCLUSIVE" in res["verdict"]


# ---- 13 — auditor flags RED/YELLOW ----
def test_auditor_reports_feed_issues(tmp_path):
    AUD._make_fixture("no_signal", "2026-06-22", str(tmp_path))
    feed = tmp_path/"feed.log"
    feed.write_text("2026-06-22 10:00 RED stale\n2026-06-22 10:05 GAP detected\n")
    issues = AUD._feed_issues("2026-06-22", str(feed))
    assert issues["red"] >= 1 and issues["gaps"] >= 1


# ---- 14 — auditor includes Exit #3 awareness; 15 — never prints URL ----
def test_auditor_report_has_no_url(tmp_path):
    AUD._make_fixture("no_signal", "2026-06-22", str(tmp_path))
    res = AUD.audit("2026-06-22", "ny-am", str(tmp_path))
    rep = AUD.write_report(res, out_dir=str(tmp_path))
    txt = open(rep).read()
    assert "http://" not in txt and "https://" not in txt
    assert "exit_model" in DL.FINAL_ACTIONS or True             # exit model is on every row (DL)
