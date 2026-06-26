"""Profile Momentum executor + paper tracker — order routing (enter/flip/flatten), gating, overlap
sizing, EOD flat, and modeled episode P&L. Uses the real bridge builders + a capturing fake sender."""
import pytest
from profile_momentum_live import MomentumExecutor, MomentumPaperTracker
from overlap_gate import OverlapGate


class FakeSender:
    def __init__(self): self.cap = []
    def send(self, p, **k): self.cap.append(p); return {"sent": True, "reason": "dry"}


def _exec(**kw):
    s = FakeSender()
    e = MomentumExecutor("MFFU-50K-1", s, base_qty=2, stop_pts=120.0, mode="paper", **kw)
    return e, s


def _sig(action, position, close=20000.0):
    side = "long" if position > 0 else "short" if position < 0 else "flat"
    return dict(action=action, position=position, side=side, close=close, slot=20, date="2026-06-26")


def test_enter_sends_market_entry_wide_stop():
    e, s = _exec()
    e.on_signal(_sig("enter", 1, 20000.0), "2026-06-26 10:00")
    assert len(s.cap) == 1 and e.position == 1 and e.sent == 1
    p = s.cap[0]
    assert p["action"] == "buy" and p["orderType"] == "market" and p["quantity"] == 2
    assert "stopLoss" in p and "takeProfit" not in p                 # position strat: stop only, no target
    assert p["stopLoss"]["stopPrice"] == 19880.0                     # 20000 - 120pt wide stop


def test_flip_exits_then_enters_opposite():
    e, s = _exec()
    e.on_signal(_sig("enter", 1, 20000), "2026-06-26 10:00")
    s.cap.clear()
    e.on_signal(_sig("flip", -1, 20030), "2026-06-26 10:30")
    assert [p["action"] for p in s.cap] == ["exit", "sell"]          # close long, open short
    assert e.position == -1


def test_flatten_exits_only():
    e, s = _exec()
    e.on_signal(_sig("enter", -1, 20000), "2026-06-26 10:00"); s.cap.clear()
    e.on_signal(_sig("flatten", 0, 19950), "2026-06-26 14:55")
    assert len(s.cap) == 1 and s.cap[0]["action"] == "exit" and e.position == 0


def test_hold_does_nothing():
    e, s = _exec()
    e.on_signal(_sig("enter", 1, 20000), "t1"); s.cap.clear()
    e.on_signal(_sig("hold", 1, 20010), "t2")
    assert s.cap == [] and e.position == 1


def test_kill_blocks_entry_but_not_exit():
    killed = {"v": "operator kill"}
    e, s = _exec(killed=lambda: killed["v"])
    e.on_signal(_sig("enter", 1, 20000), "t1")
    assert s.cap == [] and e.blocked == 1 and e.position == 0        # entry blocked
    # but if we somehow held a position, flatten still routes (exits never blocked)
    killed["v"] = None; e.on_signal(_sig("enter", 1, 20000), "t2"); killed["v"] = "kill"; s.cap.clear()
    e.on_signal(_sig("flatten", 0, 19990), "t3")
    assert len(s.cap) == 1 and s.cap[0]["action"] == "exit"


def test_data_gate_blocks_entry():
    e, s = _exec(entry_gate=lambda: (False, "data RED"))
    e.on_signal(_sig("enter", 1, 20000), "t1")
    assert s.cap == [] and e.blocked == 1


def test_overlap_gate_halves_when_other_strategy_same_dir():
    g = OverlapGate(); g.on_open("A", "long")
    e, s = _exec(overlap_gate=g)
    e.on_signal(_sig("enter", 1, 20000), "t1")
    assert s.cap[0]["quantity"] == 1                                 # 2 -> 1 (A already long)


def test_eod_flat_safety():
    e, s = _exec()
    e.on_signal(_sig("enter", 1, 20000), "t1"); s.cap.clear()
    e.eod_flat("2026-06-26 16:00", ref=20040)
    assert len(s.cap) == 1 and s.cap[0]["action"] == "exit" and e.position == 0


# ---- paper tracker P&L ----
def test_tracker_long_win(tmp_path):
    t = MomentumPaperTracker("M-acct", "paper", dpp=2.0, stop_pts=120.0, path=str(tmp_path / "tr.csv"))
    t.on_entry("long", 2, 20000, "2026-06-26 10:00")
    t.on_exit(20050, "2026-06-26 11:00", "flip")
    # gross 50pt, net 50-0.75=49.25, $ = 49.25*2*2 = 197
    assert round(t.recorded[0]["pnl"], 2) == 197.0 and t.closed == 1


def test_tracker_short_loss(tmp_path):
    t = MomentumPaperTracker("M-acct", "paper", dpp=2.0, stop_pts=120.0, path=str(tmp_path / "tr.csv"))
    t.on_entry("short", 2, 20000, "2026-06-26 10:00")
    t.on_exit(20030, "2026-06-26 11:00", "eod")              # short, price up 30 -> loss
    assert round(t.recorded[0]["pnl"], 2) == -123.0          # (-30-0.75)*2*2


def test_resolve_momentum_live_flag_gating(tmp_path):
    from config_defaults import resolve_momentum_live
    d = str(tmp_path)
    assert resolve_momentum_live("paper", approval_dir=d) is True       # paper -> routes (paper sender)
    assert resolve_momentum_live("dry-run", approval_dir=d) is True
    assert resolve_momentum_live("live", approval_dir=d) is False        # live + NO flag -> shadow
    open(str(tmp_path / "momentum-approved.flag"), "w").write("ok")
    assert resolve_momentum_live("live", approval_dir=d) is True         # live + flag -> route


def test_shadow_models_but_does_not_route(tmp_path):
    # simulate LIVE-without-approval: shadow=True -> models P&L but sends NO broker order
    t = MomentumPaperTracker("M-acct", "live", path=str(tmp_path / "tr.csv"))
    e, s = _exec(tracker=t); e.mode = "live"; e.shadow = True
    e.on_signal(_sig("enter", 1, 20000), "2026-06-26 10:00")
    assert s.cap == [] and e.position == 1 and t.open is not None        # NO order, but modeled
    e.on_signal(_sig("flatten", 0, 20020), "2026-06-26 11:00")
    assert s.cap == [] and t.closed == 1                                 # exit modeled, no order
    e.shadow = False                                                     # approved -> now routes
    e.on_signal(_sig("enter", -1, 20000), "2026-06-26 12:00")
    assert len(s.cap) == 1 and s.cap[0]["action"] == "sell"


def test_executor_tracker_wired(tmp_path):
    t = MomentumPaperTracker("M-acct", "paper", path=str(tmp_path / "tr.csv"))
    e, s = _exec(tracker=t)
    e.on_signal(_sig("enter", 1, 20000), "2026-06-26 10:00")
    assert t.open and t.open["entry"] == 20000
    e.on_signal(_sig("flatten", 0, 20020), "2026-06-26 11:00")
    assert t.closed == 1 and t.recorded[0]["pnl"] > 0
