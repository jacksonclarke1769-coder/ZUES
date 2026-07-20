"""
STEP 1 fill-path pre-gate — same-bar fill/invalidation sequencing regression test for
THIS chain's walker (chain.run_chain), adapted from
backtests/zeus-ict-2026-07/concept_survey/test_fill_sequencing.py (the certified
same-bar-fill-bug regression, PREREG_CHAIN.md "Fills" section / AUDIT-20260720-0941).

A synthetic 1m bar whose range spans BOTH the limit entry price (proximal edge) and the
structural stop (1 tick beyond the sweep extreme) must be recorded as a filled-then-stopped
trade (reason == 'stop_samebar', R < 0) — never silently cancelled. A second test confirms a
real pre-fill invalidation (distal-edge breach strictly before the entry is ever touched) is
still a legitimate cancel (0 trades), so the pre-gate is checking the RIGHT convention, not
just "always book a trade".
"""
import numpy as np
import pandas as pd

from chain import LONG, run_chain, df1m_to_arrays


def build_synthetic_1m(n=10):
    idx = pd.date_range("2025-01-06 14:00:00", periods=n, freq="1min", tz="UTC")  # Monday, mid-session
    o = np.full(n, 102.0)
    h = np.full(n, 102.2)
    l = np.full(n, 101.8)
    c = np.full(n, 102.0)
    v = np.full(n, 10, dtype=np.uint64)
    # bar 2: range spans BOTH entry (100.0, proximal) and invalidate/stop (99.0, distal/stop)
    l[2] = 98.5
    h[2] = 102.5
    o[2] = 102.3
    c[2] = 98.8
    return pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c, "Volume": v}, index=idx)


def build_candidates(df1m, invalidate_equals_stop=True):
    cols = ["direction", "mode", "entry_price", "stop_price", "invalidate_price",
            "zone_lo", "zone_hi", "conf_ts", "order_end_ns", "sweep_ts", "sweep_extreme",
            "fvg_idx", "sweep_idx"]
    order_end_ns = (df1m.index[-1] + pd.Timedelta(minutes=1)).value
    row = dict(direction=LONG, mode="limit", entry_price=100.0, stop_price=99.0,
               invalidate_price=99.0 if invalidate_equals_stop else 97.0,
               zone_lo=99.0, zone_hi=101.0, conf_ts=df1m.index[0], order_end_ns=order_end_ns,
               sweep_ts=df1m.index[0], sweep_extreme=99.25, fvg_idx=0, sweep_idx=0)
    return pd.DataFrame([row], columns=cols)


def build_target_ctx():
    empty_i = np.array([], dtype=np.int64)
    empty_f = np.array([], dtype=np.float64)
    return dict(sh_ts=empty_i, sh_price=empty_f, sl_ts=empty_i, sl_price=empty_f,
                atr_ts=empty_i, atr_vals=empty_f)


def test_same_bar_entry_and_stop_records_filled_then_stopped_loss():
    df1m = build_synthetic_1m()
    cand = build_candidates(df1m)
    tctx = build_target_ctx()
    arrs = df1m_to_arrays(df1m)
    trades = run_chain(arrs, tctx, cand, df1m.index[0], df1m.index[-1] + pd.Timedelta(minutes=1))
    assert len(trades) == 1, f"expected exactly 1 trade (fill+same-bar-stop), got {len(trades)}"
    t = trades.iloc[0]
    assert t["reason"] == "stop_samebar", f"expected reason='stop_samebar', got {t['reason']!r}"
    assert t["R"] < 0, f"expected a losing trade (R<0), got R={t['R']}"
    assert t["entry_ref"] == 100.0
    assert t["stop"] == 99.0
    print(f"PASS: same-bar entry+stop -> filled-then-stopped (reason={t['reason']}, R={t['R']:.4f})")


def test_strict_precede_invalidation_is_a_real_cancel():
    df1m = build_synthetic_1m()
    # bar 1 touches ONLY invalidation (distal), not entry; bar 2 no longer dips to invalidate
    df1m.loc[df1m.index[1], "Low"] = 98.0
    df1m.loc[df1m.index[1], "High"] = 98.9
    df1m.loc[df1m.index[2], "Low"] = 99.9
    df1m.loc[df1m.index[2], "High"] = 100.5
    cand = build_candidates(df1m)
    tctx = build_target_ctx()
    arrs = df1m_to_arrays(df1m)
    trades = run_chain(arrs, tctx, cand, df1m.index[0], df1m.index[-1] + pd.Timedelta(minutes=1))
    assert len(trades) == 0, f"expected a real cancel (0 trades), got {len(trades)}"
    print("PASS: distal-invalidation strictly before entry touch -> real cancel (0 trades)")


if __name__ == "__main__":
    test_same_bar_entry_and_stop_records_filled_then_stopped_loss()
    test_strict_precede_invalidation_is_a_real_cancel()
    print("ALL FILL-SEQUENCING REGRESSION TESTS PASS (chain.run_chain)")
