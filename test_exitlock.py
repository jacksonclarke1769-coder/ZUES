"""EXITLOCK — exit-model approval gate + P&L-model truth tests.
The live bridge sends full-qty single-target, which does NOT match the validated
Exit #3 partial backtest. Until aligned/approved, every live ENTRY must fail closed;
exits/cancels/flatten must always pass. Plus: lock down the P&L arithmetic so the
three exit models are unambiguous in code."""
import os
import pytest

import bridge_sender
from bridge_sender import BridgeSender
import bridge_traderspost as BP
from store import Store
from journal import Journal
import trade_results as TR

ENTRY, STOP, TARGET = 30654.83, 30771.50, 30421.49   # the reported $1,400 short
RISK = abs(STOP - ENTRY)


def _sender(tmp_path, approval_dir, live=True):
    s = BridgeSender(store=Store(str(tmp_path/"s.db")), journal=Journal(str(tmp_path/"j.db")),
                     mode="live" if live else "dry-run", live_url="https://example/webhook")
    bridge_sender.APPROVAL_DIR = str(approval_dir)        # redirect flag dir for the test
    return s


def _approvals(tmp_path, exit_model=False, traderspost=True):
    d = tmp_path/"approvals"; d.mkdir(exist_ok=True)
    if traderspost: (d/"traderspost-approved.flag").write_text("test")
    if exit_model: (d/"exit-model-approved.flag").write_text("test")
    return d


def _entry_payload():
    p, err = BP.build_entry(account="MFFU-50K-1", strategy="A", setup="sweep-OTE",
                            signal_ts="2026-06-16T13:46:00+00:00", side="short", qty=3,
                            entry=ENTRY, stop=STOP, target=TARGET)
    assert err is None
    return p


# ---------------- Phase 9.1 — entry blocked without the flag ----------------
def test_live_entry_blocked_without_exit_model_flag(tmp_path):
    d = _approvals(tmp_path, exit_model=False)            # flag ABSENT
    s = _sender(tmp_path, d)
    res = s.send(_entry_payload())
    assert res["sent"] is False
    assert "exit model not approved" in res["reason"].lower()


def test_live_entry_allowed_when_exit_model_flag_present(tmp_path):
    d = _approvals(tmp_path, exit_model=True)             # flag PRESENT
    s = _sender(tmp_path, d)
    ok, fails = s._live_ok(_entry_payload())
    assert not any("exit model" in f.lower() for f in fails)   # exit-model gate passes


# ---------------- Phase 9.2 — exits/cancels/flatten never blocked ----------------
def test_exit_not_blocked_by_exit_model_gate(tmp_path):
    d = _approvals(tmp_path, exit_model=False)
    s = _sender(tmp_path, d)
    exit_p, _ = BP.build_exit(account="MFFU-50K-1", strategy="A",
                              signal_ts="2026-06-16T13:46:00+00:00")
    ok, fails = s._live_ok(exit_p)
    assert not any("exit model" in f.lower() for f in fails)


def test_emergency_flatten_not_blocked_by_exit_model_gate(tmp_path):
    d = _approvals(tmp_path, exit_model=False)
    s = _sender(tmp_path, d)
    flat_p, _ = BP.build_flatten(account="MFFU-50K-1", reason="t")
    cancel_p, _ = BP.build_cancel(account="MFFU-50K-1", strategy="EMERGENCY",
                                  signal_ts="t")
    for p in (flat_p, cancel_p):
        _ok, fails = s._live_ok(p)
        assert not any("exit model" in f.lower() for f in fails)


# ---------------- Phase 9.3-9.6 — P&L truth for each exit model ----------------
def test_single_target_full_qty_pnl_is_1400():
    pnl = TR.pnl_from_r(2.0, ENTRY, STOP, 3)             # full 3 @ +2R
    assert round(pnl) == 1400


def test_exit3_fractional_pnl_is_1050():
    pnl = TR.pnl_from_r(1.5, ENTRY, STOP, 3)            # blended 1.5R on 3
    assert round(pnl) == 1050


def test_exit3_integer_1at1R_2at2R_is_1167():
    pnl = TR.pnl_from_r(1.0, ENTRY, STOP, 1) + TR.pnl_from_r(2.0, ENTRY, STOP, 2)
    assert round(pnl) == 1167


def test_exit3_integer_2at1R_1at2R_is_933():
    pnl = TR.pnl_from_r(1.0, ENTRY, STOP, 2) + TR.pnl_from_r(2.0, ENTRY, STOP, 1)
    assert round(pnl) == 933


def test_dollar_per_point_is_mnq():
    assert TR.DOLLARS_PER_POINT == 2.0                  # MNQ; guards against silent NQ swap


# ---------------- Phase 9.9 — live payload remains single-target ----------------
def test_live_payload_is_single_target_no_partials():
    p = _entry_payload()
    assert p["quantity"] == 3                            # full qty (no split)
    assert "takeProfit" in p and "limitPrice" in p["takeProfit"]   # exactly one target
    assert "stopLoss" in p
    for k in ("TP1", "TP2", "takeProfit2", "partials", "legs"):
        assert k not in p                                # no partial/runner keys exist


# ---------------- Phase 9.10 — no secrets in the webhook log line ----------------
def test_webhook_log_has_no_url_or_secret(tmp_path):
    d = _approvals(tmp_path, exit_model=False)
    s = _sender(tmp_path, d)
    s.send(_entry_payload())                             # refused, but logs a line
    if os.path.exists(bridge_sender.LOG):
        txt = open(bridge_sender.LOG).read()
        assert "https://" not in txt and "webhook" not in txt.lower()
