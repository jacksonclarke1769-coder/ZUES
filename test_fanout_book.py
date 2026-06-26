"""Fan-out SecondaryBook — routes signals at its own size to its own sender, scales P&L from the primary,
enforces the daily-stop + Apex $1k daily-kill (flatten + halt), fully isolated (never raises)."""
import pytest
from fanout_book import SecondaryBook
from auto_safety import EVAL_TIERS


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
    assert len(s.cap) == 2 and b.sent == 1                  # exit3_split(8) = (4,4) -> 2 legs
    assert sum(p["quantity"] for p in s.cap) == 8
    assert all(p["extras"]["strategy"] == "A" for p in s.cap)


def test_route_b_partial_at_apex_size():
    s = FakeSender(); b = SecondaryBook("APEX-50K-1", EVAL_TIERS["Apex-50K-eval"], s, "paper")
    b.route_b(B_SIG, TS)
    assert sum(p["quantity"] for p in s.cap) == 4 and b.sent == 1   # B4 split
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
    # losses summing to <= -$350 (the daily stop) but each under the kill: B -1R at 4 MNQ = -$200 x2 = -$400
    b.on_resolved("B", -1.0, 25.0, TS)                      # -1*25*2*4 = -$200
    b.on_resolved("B", -1.0, 25.0, TS)                      # -$400 total -> daily-stop
    assert b.halted() and b.halt_reason == "daily-stop"
    assert not any(p.get("action") == "exit" for p in s.cap)  # daily-stop halts entries, no forced flatten


def test_pnl_scales_to_book_size_and_resets_next_day():
    b = _book()
    b.on_resolved("B", 2.0, 25.0, TS)                        # +2*25*2*4 = +$400
    assert round(b.day_pnl) == 400 and not b.halted()
    b.on_resolved("A", 1.0, 44.0, "2026-07-01 10:00:00-04:00")  # new day -> resets, +1*44*2*8 = +$704
    assert round(b.day_pnl) == 704


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
    assert b.m_exec is not None and b.m_exec.base_qty == 4   # mm=4 on the Apex eval tier
