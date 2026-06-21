"""P3 + Profile B LIVE integration in auto_live.LiveAuto — P3 sizing on A, B routing
(single bracket, no D1c), P3 brake zeros B. Dry-run sender (no live, no flag)."""
import pandas as pd
import pytest

from auto_live import LiveAuto
from bridge_sender import BridgeSender
from store import Store
from journal import Journal

A_SIG = dict(side="short", entry=30654.83, stop=30771.50, target=30421.49,
             ts_signal="2026-06-22T13:46:00+00:00", liq="pdh")
B_SIG = dict(side="long", entry=30000.0, stop=29950.0, target=30075.0,
             ts_signal="2026-06-22T13:50:00+00:00", liq="orb", profile="B")
DD = 2000.0


def _auto(tmp_path, cushion):
    s = BridgeSender(store=Store(str(tmp_path / "s.db")), journal=Journal(str(tmp_path / "j.db")),
                     mode="dry-run")
    a = LiveAuto("MFFU-50K-1", "50K-conservative", "paper",
                 Store(str(tmp_path / "st.db")), Journal(str(tmp_path / "jj.db")), s, 700,
                 d1c_mode="OFF")
    a.cushion_fn = lambda: (cushion, DD)
    cap = []
    _orig = s.send
    s.send = lambda p, **k: (cap.append(p), _orig(p, **k))[1]
    return a, cap


# ---- P3 sizing on Profile A ----
def test_a_full_size_when_cushion_healthy(tmp_path):
    a, cap = _auto(tmp_path, cushion=1500)                  # > $1200 -> not braked
    a.on_decision(A_SIG, True, "placed", pd.Timestamp(A_SIG["ts_signal"]))
    assert a.p3.braked is False
    assert sum(p["quantity"] for p in cap) == 3             # full A3 -> 2 legs (1+2)
    assert len(cap) == 2

def test_a_halved_when_p3_braked(tmp_path):
    a, cap = _auto(tmp_path, cushion=500)                   # < $800 -> braked
    a.on_decision(A_SIG, True, "placed", pd.Timestamp(A_SIG["ts_signal"]))
    assert a.p3.braked is True
    assert sum(p["quantity"] for p in cap) == 1             # max(3//2,1)=1 -> single core leg


# ---- Profile B routing ----
def test_b_routes_single_bracket_strategy_b(tmp_path):
    a, cap = _auto(tmp_path, cushion=1500)
    a.on_b_signal(B_SIG, pd.Timestamp(B_SIG["ts_signal"]))
    assert len(cap) == 1                                    # single bracket (not Exit #3 split)
    p = cap[0]
    assert p["quantity"] == 2                               # bm for 50K-conservative
    assert p["extras"]["strategy"] == "B"
    assert "takeProfit" in p and "stopLoss" in p
    assert a.b_sent == 1

def test_b_blocked_when_p3_braked(tmp_path):
    a, cap = _auto(tmp_path, cushion=500)                   # braked -> B size 0
    a.on_b_signal(B_SIG, pd.Timestamp(B_SIG["ts_signal"]))
    assert cap == []                                        # no B order
    assert a.b_blocked == 1

def test_b_blocked_by_daily_stop(tmp_path):
    a, cap = _auto(tmp_path, cushion=1500)
    a.store.set_state(auto_live_kill="1")                   # kill switch
    a.on_b_signal(B_SIG, pd.Timestamp(B_SIG["ts_signal"]))
    assert cap == [] and a.b_blocked == 1

def test_b_disabled_flag(tmp_path):
    a, cap = _auto(tmp_path, cushion=1500)
    a.profile_b = False
    a.on_b_signal(B_SIG, pd.Timestamp(B_SIG["ts_signal"]))
    assert cap == []


# ---- B does not consult D1c (no DriftGate call) ----
def test_b_never_touches_d1c(tmp_path):
    a, cap = _auto(tmp_path, cushion=1500)
    # break the drift gate; B must still route (proves it never calls D1c)
    a.gate = None
    a.on_b_signal(B_SIG, pd.Timestamp(B_SIG["ts_signal"]))
    assert len(cap) == 1 and a.b_sent == 1


# ---- B paper-P&L wiring: signal -> tracker -> calendar ----
def test_b_signal_records_pnl_via_tracker(tmp_path):
    import trade_results as TR
    a, cap = _auto(tmp_path, cushion=1500)
    a.b_tracker.path = str(tmp_path / "tr.csv")                 # isolate from the real ledger
    a.on_b_signal(B_SIG, pd.Timestamp(B_SIG["ts_signal"]), bar_i=0)
    assert len(a.b_tracker.open) == 1                           # registered with the tracker
    # fill on retest then hit target (B_SIG long 30000/stop 29950/target 30075)
    a.b_tracker.on_bar(1, "2026-06-22 09:50", 30000, 30005, 29995, 30000)
    a.b_tracker.on_bar(2, "2026-06-22 09:55", 30005, 30080, 30000, 30075)
    assert a.b_tracker.closed == 1
    day = TR.by_day(a.b_tracker.path)["2026-06-22"]
    assert day["hypothetical_pnl"] > 0 and day["pnl"] == 0.0    # B paper P&L on the calendar (hypothetical)
