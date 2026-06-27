"""ARGUS-M — Profile MOMENTUM decision-logger tests. Proves a zero-trade momentum (shadow)
session is provable: every RTH 5m evaluation (warmup / flat / holding / signal / feed-not-green)
writes one JSONL row, secrets never leak, and a logger failure can't break the momentum lane."""
import json
import os

import decision_log as DL
from auto_live import LiveAuto
from store import Store
from journal import Journal


class _FakeExec:                       # stands in for MomentumExecutor (only .shadow is read)
    def __init__(self, shadow=True):
        self.shadow = shadow


def _auto(tmp_path, mode="paper", shadow=True):
    auto = LiveAuto("MFFU-50K-1", "50K-balanced", mode,
                    Store(str(tmp_path / "s.db")), Journal(str(tmp_path / "j.db")),
                    sender=None, daily_stop=700, d1c_mode="OFF")
    auto.m_dlogger = DL.DecisionLogger("MFFU-50K-1", mode, "sess-M", profile="M",
                                       feed_source="tradingview-1m", log_dir=str(tmp_path))
    auto.m_executor = _FakeExec(shadow=shadow)
    return auto


def _rows(tmp_path):
    files = [f for f in os.listdir(tmp_path) if f.endswith(".jsonl")]
    assert files, "no jsonl written"
    return [json.loads(l) for l in open(os.path.join(tmp_path, files[0])) if l.strip()]


TS = "2026-06-26T10:00:00-04:00"


def test_feed_not_green_is_skipped(tmp_path):
    _auto(tmp_path)._log_m_decision(TS, None, data_state="RED")
    r = _rows(tmp_path)[0]
    assert r["final_action"] == "skipped" and r["rejection_reason"] == "feed_not_green"
    assert r["profile"] == "M" and r["data_ready"] is False


def test_warmup_is_skipped(tmp_path):
    _auto(tmp_path)._log_m_decision(TS, None, data_state="GREEN")     # ready feed, sig None -> warming up
    r = _rows(tmp_path)[0]
    assert r["final_action"] == "skipped" and r["rejection_reason"] == "momentum_warmup"
    assert r["exit_model"] == "MOMENTUM_POSITION"


def test_flat_is_no_signal(tmp_path):
    sig = dict(changed=False, position=0, side="flat", slot=6, close=29440.0, prev=0)
    _auto(tmp_path)._log_m_decision(TS, sig, data_state="GREEN")
    r = _rows(tmp_path)[0]
    assert r["final_action"] == "no_signal" and r["candidate_detected"] is False
    assert r["note"] == "flat" and r["position"] == 0


def test_holding_is_no_signal_with_note(tmp_path):
    sig = dict(changed=False, position=1, side="long", slot=20, close=29600.0, prev=1)
    _auto(tmp_path)._log_m_decision(TS, sig, data_state="GREEN")
    r = _rows(tmp_path)[0]
    assert r["final_action"] == "no_signal" and r["note"] == "holding" and r["position"] == 1


def test_signal_shadow_is_paper_signal(tmp_path):
    sig = dict(changed=True, position=1, prev=0, action="enter", side="long", slot=8, close=29464.0)
    _auto(tmp_path, mode="live", shadow=True)._log_m_decision(TS, sig, data_state="GREEN")
    r = _rows(tmp_path)[0]
    assert r["final_action"] == "paper_signal"        # live mode but NOT approved -> shadow
    assert r["side"] == "long" and r["m_action"] == "enter" and r["shadow"] is True


def test_signal_live_is_live_send(tmp_path):
    sig = dict(changed=True, position=-1, prev=0, action="enter", side="short", slot=30, close=29400.0)
    _auto(tmp_path, mode="live", shadow=False)._log_m_decision(TS, sig, data_state="GREEN")
    r = _rows(tmp_path)[0]
    assert r["final_action"] == "live_send" and r["shadow"] is False and r["side"] == "short"


def test_logger_error_never_raises(tmp_path):
    auto = _auto(tmp_path)
    class Boom:
        def log(self, *a, **k): raise RuntimeError("boom")
    auto.m_dlogger = Boom()
    auto._log_m_decision(TS, None, data_state="GREEN")               # must NOT raise
    sig = dict(changed=True, position=1, prev=0, action="enter", side="long", slot=8, close=1.0)
    auto._log_m_decision(TS, sig, data_state="GREEN")                # must NOT raise


def test_no_logger_is_noop(tmp_path):
    auto = _auto(tmp_path)
    auto.m_dlogger = None
    auto._log_m_decision(TS, None, data_state="GREEN")               # no logger -> silent no-op, no file
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".jsonl")]
