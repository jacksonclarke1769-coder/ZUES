"""P3 cushion brake gates MOMENTUM near the floor (added 2026-06-27 when momentum was enabled on Apex
funded). Braked + flat -> no new momentum entry; braked + holding -> flatten; unbraked -> routes normally."""
import os
import pytest
import pandas as pd
from store import Store
from journal import Journal
from bridge_sender import BridgeSender
from profile_momentum_live import MomentumExecutor
import auto_live

NY = "America/New_York"


class FakeSender:
    def __init__(self): self.cap = []
    def send(self, p, **k): self.cap.append(p); return {"sent": True, "reason": "dry"}


class FakeEngine:
    """Returns a fixed momentum signal each bar (stands in for ProfileMomentumEngine)."""
    def __init__(self, sig): self._sig = sig
    def add_bar(self, *a, **k): pass
    def latest_signal(self): return self._sig


def _enter(): return dict(action="enter", position=1, side="long", close=20000.0, slot=20,
                          date="2026-06-15", changed=True, prev=0)


@pytest.fixture
def auto(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for d in ("data", "evidence/approvals", "out/ares"):
        os.makedirs(d, exist_ok=True)
    s, j = Store("data/b.db"), Journal("data/j.db")
    a = auto_live.LiveAuto("Apex-50K-demo", "Apex-50K", "paper", s, j,
                           BridgeSender(store=s, journal=j, mode="dry-run"), 550)
    return a


def _wire_mm(a):
    snd = FakeSender()
    a.m_engine = FakeEngine(_enter())
    a.m_executor = MomentumExecutor("Apex-50K-demo", snd, base_qty=2, stop_pts=120.0, mode="paper")
    return snd


def test_braked_and_flat_blocks_momentum_entry(auto):
    snd = _wire_mm(auto)
    auto.p3.braked = True
    auto.on_m_bar(pd.Timestamp("2026-06-15 10:00", tz=NY), 20000, 20005, 19995, 20000)
    assert snd.cap == []                                  # near the floor: no new momentum exposure
    assert auto.m_executor.position == 0


def test_unbraked_routes_momentum_entry(auto):
    snd = _wire_mm(auto)
    auto.p3.braked = False
    auto.on_m_bar(pd.Timestamp("2026-06-15 10:00", tz=NY), 20000, 20005, 19995, 20000)
    assert len(snd.cap) == 1 and snd.cap[0]["action"] == "buy" and snd.cap[0]["quantity"] == 2
    assert auto.m_executor.position == 1


def test_braked_while_holding_flattens(auto):
    snd = _wire_mm(auto)
    auto.p3.braked = False                                # open a position first
    auto.on_m_bar(pd.Timestamp("2026-06-15 10:00", tz=NY), 20000, 20005, 19995, 20000)
    snd.cap.clear()
    auto.p3.braked = True                                 # now braked; a fresh enter/flip must flatten, not add
    auto.m_engine = FakeEngine(dict(action="flip", position=-1, side="short", close=20030.0,
                                    slot=22, date="2026-06-15", changed=True, prev=1))
    auto.on_m_bar(pd.Timestamp("2026-06-15 10:30", tz=NY), 20030, 20035, 20025, 20030)
    assert [p["action"] for p in snd.cap] == ["exit"]     # flattened, did NOT open the short
    assert auto.m_executor.position == 0
