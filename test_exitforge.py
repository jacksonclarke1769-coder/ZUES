"""EXITFORGE — true Exit #3 two-leg live routing. Locks the split payloads, the
fail-closed failure policy, flatten-both, dedup per leg, two-leg P&L, and the
hypothetical/realised dashboard split. Live entries stay blocked (no flag)."""
import os
import pytest

import bridge_sender
from bridge_sender import BridgeSender
import bridge_traderspost as BP
import trade_results as TR
from store import Store
from journal import Journal

E, S, T = 30654.83, 30771.50, 30421.49
COMMON = dict(account="MFFU-50K-1", strategy="A", setup="sweep-OTE",
              signal_ts="2026-06-16T13:46:00+00:00", side="short", qty=3,
              entry=E, stop=S, target=T)


def _legs():
    legs, err = BP.build_entry_exit3(**COMMON)
    assert err is None
    return legs


def _approvals(tmp_path, exit_model=False):
    d = tmp_path/"approvals"; d.mkdir(exist_ok=True)
    (d/"traderspost-approved.flag").write_text("x")
    if exit_model: (d/"exit-model-approved.flag").write_text("x")
    bridge_sender.APPROVAL_DIR = str(d)
    return d


class ScriptedSender(BridgeSender):
    """Returns queued send() results so the failure policy can be exercised offline."""
    def __init__(self, results, **kw):
        super().__init__(**kw); self._q = list(results); self.flattened = []
    def send(self, payload, **kw):
        return self._q.pop(0) if self._q else dict(sent=True, status=200)
    def flatten(self, account, root="MNQ", reason="emergency"):
        self.flattened.append((account, reason)); return dict(ok=True)


def _ss(tmp_path, results):
    return ScriptedSender(results, store=Store(str(tmp_path/"s.db")),
                          journal=Journal(str(tmp_path/"j.db")), mode="live",
                          live_url="https://x/wh")


# ---- 3,4,5,6,7,18 — split payload shape ----
def test_exit3_builds_exactly_two_legs():
    assert len(_legs()) == 2

def test_tp1_leg_qty1_target_plus1R():
    tp1 = [L for L in _legs() if L["role"] == "entry_tp1"][0]
    assert tp1["qty"] == 1 and tp1["r_target"] == 1.0
    assert tp1["payload"]["takeProfit"]["limitPrice"] == 30538.25   # entry-1R, tick-rounded

def test_tp2_leg_qty2_target_plus2R():
    tp2 = [L for L in _legs() if L["role"] == "entry_tp2"][0]
    assert tp2["qty"] == 2 and tp2["r_target"] == 2.0
    assert tp2["payload"]["takeProfit"]["limitPrice"] == 30421.5    # the strategy 2R target

def test_both_legs_share_same_stop():
    stops = {L["payload"]["stopLoss"]["stopPrice"] for L in _legs()}
    assert stops == {30771.5}

def test_legs_have_distinct_deterministic_ids():
    a = [L["payload"]["extras"]["signalId"] for L in _legs()]
    b = [L["payload"]["extras"]["signalId"] for L in _legs()]
    assert a == b and len(set(a)) == 2                              # stable + distinct

def test_send_order_is_core_first():
    assert [L["role"] for L in _legs()] == ["entry_tp2", "entry_tp1"]

def test_no_single_full_qty_target_under_exit3():
    import config
    assert config.EXIT_MODEL == "EXIT3_FIXED_PARTIAL"
    assert all(L["payload"]["quantity"] < 3 for L in _legs())       # never full 3 @ one target


# ---- 1,2 — gate still holds for the split path ----
def test_live_split_entry_blocked_without_flag(tmp_path):
    _approvals(tmp_path, exit_model=False)
    s = BridgeSender(store=Store(str(tmp_path/"s.db")), journal=Journal(str(tmp_path/"j.db")),
                     mode="live", live_url="https://x/wh")
    res = s.send_exit3(_legs(), "MFFU-50K-1")
    assert res["ok"] is False                                       # core leg blocked -> abort
    assert res["reason"] == "ENTRY_ABORTED"

def test_flatten_allowed_without_flag(tmp_path):
    _approvals(tmp_path, exit_model=False)
    s = BridgeSender(store=Store(str(tmp_path/"s.db")), journal=Journal(str(tmp_path/"j.db")),
                     mode="live", live_url="https://x/wh")
    fp, _ = BP.build_flatten(account="MFFU-50K-1", reason="t")
    ok, fails = s._live_ok(fp)
    assert not any("exit model" in f.lower() for f in fails)


# ---- 10,11,12 — failure policy ----
def test_tp2_fail_first_means_no_tp1_and_no_flatten(tmp_path):
    s = _ss(tmp_path, [dict(sent=False, reason="blocked")])        # core fails immediately
    res = s.send_exit3(_legs(), "MFFU-50K-1")
    assert res["reason"] == "ENTRY_ABORTED"
    assert len(res["legs"]) == 1                                    # TP1 never attempted
    assert s.flattened == []                                        # nothing to flatten

def test_tp1_fail_after_tp2_flattens_and_blocks(tmp_path):
    s = _ss(tmp_path, [dict(sent=True, status=200), dict(sent=False, reason="boom")])
    res = s.send_exit3(_legs(), "MFFU-50K-1")
    assert res["reason"] == "PARTIAL_ENTRY_FAILED"
    assert res["flattened"] is True and len(s.flattened) == 1       # flatten fired
    assert s.incident_blocked()                                     # entries now blocked
    assert s.send_exit3(_legs(), "MFFU-50K-1")["reason"].startswith("exit3 incident")

def test_missing_bracket_flattens_and_blocks(tmp_path):
    s = _ss(tmp_path, [])
    bad = _legs(); bad[0]["payload"].pop("stopLoss")                # corrupt a leg
    res = s.send_exit3(bad, "MFFU-50K-1")
    assert res["ok"] is False and res.get("flattened") is True
    assert s.incident_blocked()

def test_incident_clears_with_operator_note(tmp_path):
    s = _ss(tmp_path, [dict(sent=True), dict(sent=False)])
    s.send_exit3(_legs(), "MFFU-50K-1")
    assert s.incident_blocked()
    s.clear_incident("reviewed: TP1 reject, position confirmed flat at broker")
    assert not s.incident_blocked()


# ---- 8,9 — per-leg dedup ----
def test_duplicate_leg_blocked_per_role(tmp_path):
    _approvals(tmp_path)
    s = BridgeSender(store=Store(str(tmp_path/"s.db")), journal=Journal(str(tmp_path/"j.db")),
                     mode="live", live_url="https://x/wh")
    legs = _legs()
    for L in legs:                                                 # mark both confirmed
        s._mark(L["payload"]["extras"]["signalId"], "confirmed")
    for L in legs:
        assert "duplicate" in s.send(L["payload"])["reason"].lower()


# ---- 13 — flatten cancels both legs ----
def test_flatten_sends_cancel_then_exit(tmp_path):
    _approvals(tmp_path)
    s = BridgeSender(store=Store(str(tmp_path/"s.db")), journal=Journal(str(tmp_path/"j.db")),
                     mode="dry-run")
    out = s.flatten("MFFU-50K-1", reason="t")
    assert "cancel" in out and "exit" in out                       # cancel(all working) + exit


# ---- 14 — two-leg P&L math ----
def test_paper_pnl_uses_exit3_two_leg_math():
    assert round(TR.pnl_exit3(E, S, 3)) == 1167                    # 1@1R + 2@2R
    assert round(TR.pnl_from_r(2.0, E, S, 3)) == 1400              # single-target (legacy) differs
    legwin = sum(TR.pnl_from_r(L["r_target"], E, S, L["qty"]) for L in _legs())
    assert round(legwin) == 1167                                    # live payload == integer split


# ---- 15,16 — hypothetical vs fill-backed ----
def test_hypothetical_pnl_not_counted_as_realised(tmp_path):
    p = str(tmp_path/"tr.csv")
    TR.record("2026-06-16", "paper", "MFFU-50K-1", "A", "short", 3, 1167.0,
              note="modeled", fill_backed=False, path=p)
    day = TR.by_day(p)["2026-06-16"]
    assert day["pnl"] == 0.0                                        # realised stays 0
    assert day["hypothetical_pnl"] == 1167.0                        # labelled separately

def test_fill_backed_pnl_is_realised(tmp_path):
    p = str(tmp_path/"tr.csv")
    TR.record("2026-06-16", "live", "MFFU-50K-1", "A", "short", 3, 1167.0,
              note="broker fill", fill_backed=True, path=p)
    day = TR.by_day(p)["2026-06-16"]
    assert day["pnl"] == 1167.0 and day["hypothetical_pnl"] == 0.0


# ---- 17 — no secrets in log ----
def test_no_url_in_webhook_log(tmp_path):
    _approvals(tmp_path)
    s = BridgeSender(store=Store(str(tmp_path/"s.db")), journal=Journal(str(tmp_path/"j.db")),
                     mode="live", live_url="https://secret/wh")
    s.send(_legs()[0]["payload"])
    if os.path.exists(bridge_sender.LOG):
        assert "https://" not in open(bridge_sender.LOG).read()
