"""Profile Momentum engine — streaming mechanics (RTH gating, slot, warmup, position/action logic, restart).
Signal-math parity vs the backtest is proven separately on real data (verify_momentum_parity.py: 0/94344)."""
import numpy as np
import pandas as pd
import pytest
from profile_momentum_engine import ProfileMomentumEngine as PME

ET = "America/New_York"


def _warm(eng, days=55, bars=5):
    """Populate the buffer with enough distinct days to pass warmup (>= trend_len+2)."""
    base = pd.Timestamp("2026-01-05 09:35", tz=ET)
    for d in range(days):
        day = base + pd.Timedelta(days=d)
        for s in range(bars):
            eng.add_bar(day + pd.Timedelta(minutes=5 * s), 20000, 20010, 19990, 20000 + d, 100)


def test_add_bar_rth_only_and_slot():
    eng = PME()
    eng.add_bar(pd.Timestamp("2026-01-05 08:00", tz=ET), 1, 1, 1, 1)   # pre-market -> ignored
    eng.add_bar(pd.Timestamp("2026-01-05 16:30", tz=ET), 1, 1, 1, 1)   # post-market -> ignored
    assert len(eng.buf) == 0
    eng.add_bar(pd.Timestamp("2026-01-05 09:30", tz=ET), 1, 1, 1, 1)   # RTH open -> slot 0
    eng.add_bar(pd.Timestamp("2026-01-05 10:00", tz=ET), 1, 1, 1, 1)   # +30min -> slot 6
    assert eng.buf["slot"].tolist() == [0, 6]


def test_warmup_returns_none():
    eng = PME()
    _warm(eng, days=20)                  # < trend_len+2 distinct days
    assert eng.latest_signal() is None


def test_action_transitions(monkeypatch):
    eng = PME(); _warm(eng, days=55)
    seq = {"v": 0.0}
    monkeypatch.setattr(eng, "compute", lambda *a, **k: np.array([0.0, 0.0, seq["v"]]))
    seq["v"] = 1.0;  s = eng.latest_signal(); assert s["action"] == "enter" and s["position"] == 1
    seq["v"] = 1.0;  s = eng.latest_signal(); assert s["action"] == "hold"
    seq["v"] = -1.0; s = eng.latest_signal(); assert s["action"] == "flip" and s["side"] == "short"
    seq["v"] = 0.0;  s = eng.latest_signal(); assert s["action"] == "flatten" and s["position"] == 0
    seq["v"] = 0.0;  s = eng.latest_signal(); assert s["action"] == "hold"


def test_buffer_trim_to_buffer_days():
    eng = PME(buffer_days=10)
    _warm(eng, days=25, bars=2)
    assert eng.buf["date"].nunique() == 10            # trimmed to the last 10 days


def test_compute_is_deterministic_flat_data():
    # TRULY flat prices (rfo=0 -> sigma=0 -> no band break) -> all-flat signal (no NaN/crash)
    eng = PME()
    base = pd.Timestamp("2026-01-05 09:35", tz=ET)
    for d in range(55):
        day = base + pd.Timedelta(days=d)
        for s in range(5):
            eng.add_bar(day + pd.Timedelta(minutes=5 * s), 20000, 20000, 20000, 20000, 100)
    out = eng.compute(eng.buf)
    assert set(np.unique(out)).issubset({0.0}) and len(out) == len(eng.buf)


def test_restart_snapshot_restore():
    eng = PME(); _warm(eng, days=55); eng.position = -1
    snap = eng.snapshot()
    eng2 = PME(); eng2.restore(snap)
    assert eng2.position == -1 and eng2.buf["date"].nunique() == eng.buf["date"].nunique()


def test_restore_ignores_bad_state():
    eng = PME(); eng.restore(None); eng.restore({"position": "x"})   # must not raise
    assert eng.position in (0, )
