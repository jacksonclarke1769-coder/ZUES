"""Telegram wired into LiveAuto: a sent Profile A signal fires notify.signal; no notifier = unchanged."""
import os
import pytest
import pandas as pd
from store import Store
from journal import Journal
from bridge_sender import BridgeSender
import auto_live

NY = "America/New_York"


class FakeTG:
    enabled = True
    def __init__(self): self.signals = []; self.outcomes = []
    def signal(self, *a): self.signals.append(a)
    def outcome(self, *a): self.outcomes.append(a)
    def info(self, *a): pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for d in ("data", "evidence/approvals", "out/ares"):
        os.makedirs(d, exist_ok=True)
    return Store("data/b.db"), Journal("data/j.db")


def _bar(t): return pd.Timestamp(f"2026-06-15 {t}", tz=NY)


def _auto(env, notify=None):
    s, j = env
    return auto_live.LiveAuto("MFFU-50K-1", "50K-conservative", "paper", s, j,
                              BridgeSender(store=s, journal=j, mode="dry-run"), 700,
                              d1c_mode="OFF", notify=notify)


def _feed_up(a):
    a.feed_gate(_bar("09:30:00"), 22000.0, 22005.0)
    a.feed_gate(_bar("09:45:00"), 22018.0, 22030.0)


def _sig(side="long"):
    return dict(side=side, ts_signal="2026-06-15T09:45:00", entry=22030.0,
                stop=21980.0, target=22120.0, liq="sweep")


def test_signal_fires_telegram(env):
    tg = FakeTG()
    a = _auto(env, notify=tg); _feed_up(a)
    a.on_decision(_sig("long"), True, "ok", _bar("09:45:30"))
    assert a.sent == 1 and len(tg.signals) == 1
    prof, side, qty = tg.signals[0][0], tg.signals[0][1], tg.signals[0][2]
    assert prof == "A" and side == "long" and qty == 3        # 50K-conservative A=3


def test_no_notifier_unchanged(env):
    a = _auto(env, notify=None); _feed_up(a)
    a.on_decision(_sig("long"), True, "ok", _bar("09:45:30"))
    assert a.sent == 1 and a.notify is None
