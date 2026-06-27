"""Fan-out SecondaryBook — routes signals at its own size to its own sender, scales P&L from the primary,
enforces the daily-stop + Apex $1k daily-kill (flatten + halt), fully isolated (never raises)."""
import pytest
from fanout_book import SecondaryBook
from auto_safety import EVAL_TIERS
_T = EVAL_TIERS["Apex-50K-eval"]                            # read sizes from the tier (robust to config changes)


class FakeSender:
    def __init__(self): self.cap = []
    def send(self, p, **k): self.cap.append(p); return {"sent": True}
    def send_exit3(self, legs, account, root="MNQ"):
        for L in legs:
            self.cap.append(L["payload"])
        return {"ok": True}


A_SIG = dict(side="long", entry=20000.0, stop=19956.0, target=20088.0, ts_signal="2026-06-30T13:46:00+00:00", liq="pdh")
B_SIG = dict(side="short", entry=20000.0, stop=20025.0, target=19962.5, ts_signal="2026-06-30T13:50:00+00:00", liq="orb")
TS = "2026-06-30 10:00:00-04:00"


def _book(sender=None, mode="paper"):
    return SecondaryBook("APEX-50K-1", EVAL_TIERS["Apex-50K-eval"], sender or FakeSender(), mode)


def test_route_a_exit3_at_apex_size():
    s = FakeSender(); b = SecondaryBook("APEX-50K-1", EVAL_TIERS["Apex-50K-eval"], s, "paper")
    b.route_a(A_SIG, TS)
    assert len(s.cap) == 2 and b.sent == 1                  # exit3_split(am) -> 2 legs
    assert sum(p["quantity"] for p in s.cap) == _T["am"]
    assert all(p["extras"]["strategy"] == "A" for p in s.cap)


def test_route_b_partial_at_apex_size():
    s = FakeSender(); b = SecondaryBook("APEX-50K-1", EVAL_TIERS["Apex-50K-eval"], s, "paper")
    b.route_b(B_SIG, TS)
    assert sum(p["quantity"] for p in s.cap) == _T["bm"] and b.sent == 1   # B split at the tier's bm
    assert all(p["extras"]["strategy"] == "B" for p in s.cap)


def test_apex_daily_kill_flattens_and_halts():
    s = FakeSender(); b = SecondaryBook("APEX-50K-1", EVAL_TIERS["Apex-50K-eval"], s, "paper")
    # one big A loss at 8 MNQ: r=-1, risk=44 -> -1*44*2*8 = -$704 -> crosses the -$700 kill floor
    b.on_resolved("A", -1.0, 44.0, TS)
    assert b.halted() and "kill" in b.halt_reason
    assert any(p["action"] == "exit" for p in s.cap)        # flatten was sent
    s.cap.clear()
    b.route_a(A_SIG, TS)                                     # halted -> no new entry
    assert s.cap == [] and b.blocked >= 1


def test_daily_stop_halts_without_flatten():
    s = FakeSender(); b = SecondaryBook("APEX-50K-1", EVAL_TIERS["Apex-50K-eval"], s, "paper")
    # losses summing past the daily stop but UNDER the kill: 2x B -1R sized to land between the two
    _r = ((_T["daily_stop"] + _T["dll"] * _T["kill_margin"]) / 2) / (4 * _T["bm"])   # total ~ midpoint
    b.on_resolved("B", -1.0, _r, TS)
    b.on_resolved("B", -1.0, _r, TS)                        # -> crosses the daily-stop, stays under the kill
    assert b.halted() and b.halt_reason == "daily-stop"
    assert not any(p.get("action") == "exit" for p in s.cap)  # daily-stop halts entries, no forced flatten


def test_pnl_scales_to_book_size_and_resets_next_day():
    b = _book()
    b.on_resolved("B", 2.0, 25.0, TS)                        # +2*25*2*bm
    assert round(b.day_pnl) == 2 * 25 * 2 * _T["bm"] and not b.halted()
    b.on_resolved("A", 1.0, 44.0, "2026-07-01 10:00:00-04:00")  # new day -> resets, +1*44*2*am
    assert round(b.day_pnl) == 1 * 44 * 2 * _T["am"]


def test_halt_blocks_all_routes():
    s = FakeSender(); b = _book(s)
    b._roll(TS); b.halt = True                               # establish today, then halt (same-day -> no reset)
    b.route_a(A_SIG, TS); b.route_b(B_SIG, TS)
    assert s.cap == []


def test_isolation_never_raises():
    b = _book()
    b.route_a({"bad": "sig"}, TS)                            # malformed -> swallowed, no raise
    b.on_resolved("A", "x", None, TS)
    assert True


def test_momentum_lane_built_from_mm():
    b = _book()
    assert b.m_exec is not None and b.m_exec.base_qty == _T["mm"]   # momentum size from the Apex eval tier
