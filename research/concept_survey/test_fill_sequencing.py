"""
Regression test for the same-bar fill/invalidation sequencing bug (audited
2026-07-20). A synthetic 1m bar whose range spans BOTH the limit entry price
and the invalidation/stop price must be recorded as a filled-then-stopped
trade (reason == 'stop_samebar', R < 0), never silently cancelled.
"""
import sys

import numpy as np
import pandas as pd

from common import LONG
from survey_engine import run_cell, df1m_to_arrays


def build_synthetic_1m(n=10):
    idx = pd.date_range("2025-01-06 14:00:00", periods=n, freq="1min", tz="UTC")  # a Monday, mid-session
    # default bars sit well ABOVE both entry (100.0) and invalidate/stop (99.0) so
    # neither is touched until the designated bar
    o = np.full(n, 102.0)
    h = np.full(n, 102.2)
    l = np.full(n, 101.8)
    c = np.full(n, 102.0)
    v = np.full(n, 10, dtype=np.uint64)
    # bar index 2: range spans BOTH entry (100.0) and invalidate/stop (99.0) -- the
    # first (and only, in this synthetic series) bar to touch either level
    l[2] = 98.5
    h[2] = 102.5
    o[2] = 102.3
    c[2] = 98.8
    return pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c, "Volume": v}, index=idx)


def build_ctx(df1m, tf_min=1):
    cand = pd.DataFrame([dict(
        idx=0, direction=LONG, mode="limit",
        entry_price=100.0, stop_price=99.0, zone_lo=99.0, zone_hi=101.0,
        invalidate_price=99.0,
    )])
    cand["conf_ts"] = df1m.index[0]
    empty_i = np.array([], dtype=np.int64)
    empty_f = np.array([], dtype=np.float64)
    return dict(
        candidates={"TEST": cand},
        tf_min=tf_min,
        atr_ts=empty_i, atr_vals=empty_f,
        sh_ts=empty_i, sh_price=empty_f,
        sl_ts=empty_i, sl_price=empty_f,
    )


def test_same_bar_fill_and_invalidation_records_stop_not_cancel():
    df1m = build_synthetic_1m()
    ctx = build_ctx(df1m)
    arrs = df1m_to_arrays(df1m)
    trades = run_cell(arrs, ctx, "TEST", LONG, df1m.index[0], df1m.index[-1] + pd.Timedelta(minutes=1))
    assert len(trades) == 1, f"expected exactly 1 trade (fill+same-bar-stop), got {len(trades)}"
    t = trades.iloc[0]
    assert t["reason"] == "stop_samebar", f"expected reason='stop_samebar', got {t['reason']!r}"
    assert t["R"] < 0, f"expected a losing trade (R<0), got R={t['R']}"
    assert t["entry_ref"] == 100.0
    assert t["stop"] == 99.0
    print("PASS: same-bar entry+invalidation -> filled-then-stopped trade recorded "
          f"(reason={t['reason']}, R={t['R']:.4f})")


def test_strict_precede_invalidation_is_a_real_cancel():
    """Invalidation touched on a bar STRICTLY BEFORE the entry is ever touched ->
    still a legit cancel (order never had a chance to fill cleanly)."""
    df1m = build_synthetic_1m()
    # bar 1 (before bar 2's mixed bar) touches ONLY invalidation, not entry
    df1m.loc[df1m.index[1], "Low"] = 98.0
    df1m.loc[df1m.index[1], "High"] = 98.9   # never reaches 100.0 entry
    df1m.loc[df1m.index[2], "Low"] = 99.9    # bar 2 no longer dips to invalidate
    df1m.loc[df1m.index[2], "High"] = 100.5  # bar 2 touches entry only
    ctx = build_ctx(df1m)
    arrs = df1m_to_arrays(df1m)
    trades = run_cell(arrs, ctx, "TEST", LONG, df1m.index[0], df1m.index[-1] + pd.Timedelta(minutes=1))
    assert len(trades) == 0, f"expected a real cancel (0 trades), got {len(trades)}"
    print("PASS: invalidation strictly before entry touch -> real cancel (0 trades)")


if __name__ == "__main__":
    test_same_bar_fill_and_invalidation_records_stop_not_cancel()
    test_strict_precede_invalidation_is_a_real_cancel()
    print("ALL FILL-SEQUENCING REGRESSION TESTS PASS")
