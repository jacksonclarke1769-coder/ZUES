"""
Stage B integration — the read-back sentinel wired into LiveAuto.
  * a successful Profile A entry updates the sentinel's expected broker position
  * a halted sentinel makes the entry gate fail-closed (no send)
  * with no sentinel (default), behaviour is unchanged
"""
import os
import pytest
import pandas as pd
from store import Store
from journal import Journal
from bridge_sender import BridgeSender
import auto_live
from live_readback import ReadbackSentinel

NY = "America/New_York"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for d in ("data", "evidence/approvals", "out/ares"):
        os.makedirs(d, exist_ok=True)
    return Store("data/b.db"), Journal("data/j.db")


def _bar(t):
    return pd.Timestamp(f"2026-06-15 {t}", tz=NY)


def _auto(env, readback=None):
    s, j = env
    return auto_live.LiveAuto("MFFU-50K-1", "50K-conservative", "paper", s, j,
                              BridgeSender(store=s, journal=j, mode="dry-run"), 700,
                              d1c_mode="OFF", readback=readback)


def _feed_up(a):
    a.feed_gate(_bar("09:30:00"), 22000.0, 22005.0)
    a.feed_gate(_bar("09:35:00"), 22005.0, 22018.0)
    a.feed_gate(_bar("09:45:00"), 22018.0, 22030.0)


def _sig(side="long"):
    return dict(side=side, ts_signal="2026-06-15T09:45:00", entry=22030.0,
                stop=21980.0, target=22120.0, liq="sweep")


def test_entry_updates_sentinel_expected(env):
    """A filled Profile A long (3 MNQ on 50K-conservative) sets expected = +3."""
    s = ReadbackSentinel("MFFU-50K-1", floor=48_000.0)
    a = _auto(env, readback=s); _feed_up(a)
    a.on_decision(_sig("long"), True, "ok", _bar("09:45:30"))
    assert a.sent == 1
    assert s.expected == 3                        # am=3 for 50K-conservative


def test_halted_sentinel_blocks_entry(env):
    """When the sentinel has halted, the entry gate goes fail-closed -> no send."""
    s = ReadbackSentinel("MFFU-50K-1", floor=48_000.0)
    a = _auto(env, readback=s); _feed_up(a)
    # mirror the live _entry_ready wiring: gate consults the sentinel
    a.entry_gate = lambda: ((not s.halted), ("readback HALT: " + (s.reason or "")))
    s.halted = True; s.reason = "ORPHAN_POSITION(broker net=2)"
    a.on_decision(_sig("long"), True, "ok", _bar("09:45:30"))
    assert a.sent == 0                            # blocked, no webhook
    assert s.expected == 0                        # never opened


def test_no_sentinel_is_unchanged(env):
    """Default (no read-back) path still trades normally."""
    a = _auto(env, readback=None); _feed_up(a)
    a.on_decision(_sig("long"), True, "ok", _bar("09:45:30"))
    assert a.sent == 1 and a.readback is None
