"""INC-20260706-1141 permanent regression: runs the REAL D1c pipeline (real Databento
1m data, real `htf.build_features`, the real FROZEN `model01_sweep_mss_fvg`, and the
FIXED `run_d1c_real.attach_drift`) on a small real slice and asserts every evaluated
timestamp is at (or before, never after) its trade's true fill-bar timestamp.

Also proves the defect class is detectable in this exact slice: the OLD path (parsing
the trade's `date`/`time` strings and re-localizing as `tz=NY`) would have evaluated at
least one DST-season (summer ET, UTC-4) trade's drift >=3600s AFTER its true fill.

Skips if the real Databento parquet / research pipeline directory is unavailable (dev
machines without the research data mirror).
"""
import os
import sys

import pandas as pd
import pytest

FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
DBNT = os.path.expanduser("~/trading-team/data/real_futures/NQ_databento_1m_5y.parquet")
NY = "America/New_York"


def _have_prereqs():
    if not os.path.isdir(FW) or not os.path.isfile(DBNT):
        return False
    try:
        sys.path.insert(0, FW)
        sys.path.insert(0, os.path.join(FW, "engine"))
        sys.path.insert(0, os.path.join(FW, "models"))
        import run_d1c_real   # noqa: F401
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _have_prereqs(),
                                 reason="needs the real Databento parquet + ict-nq-framework research pipeline")


def _build_small_slice_stream():
    """Real Databento 1m -> 5m -> features -> model01 trades, restricted to a small
    (~4 month) real slice spanning summer 2021 (DST/EDT season). Small enough to run in
    under a second; large enough to reproduce the auditor's exact worked example
    (2021-06-25 fill) and contain several trades."""
    import data as D
    import htf
    import model01_sweep_mss_fvg as M1
    import run_d1c_real as RD

    d1_full = RD.load_1m()
    d1 = d1_full["2021-05-01":"2021-08-31"]
    realdf = RD.real_5m(d1)

    _orig = D.load_spine
    D.load_spine = lambda inst="NQ", tf="5m": realdf.copy() if (inst == "NQ" and tf == "5m") else _orig(inst, tf)
    try:
        feats = htf.build_features("NQ", "5m")
        feats.index.name = "timestamp"
    finally:
        D.load_spine = _orig

    tr = M1.run(feats, "NQ", {**RD.BASE, "partial": [(1, 0.5)]})
    tr = tr[tr.session == "ny_am"].copy()
    return RD, tr, d1, feats


def test_every_eval_ts_at_or_before_true_fill():
    import run_d1c_real as RD
    _, tr, d1, feats = _build_small_slice_stream()
    assert len(tr) > 0, "small real slice produced zero trades -- widen the window"

    out = RD.attach_drift(tr, d1, feats.index)
    for i in range(len(out)):
        fb = int(out["fill_bar"].iloc[i])
        true_fill_ts = feats.index[fb]
        eval_ts = out["eval_ts"].iloc[i]
        seconds_ahead_used = (eval_ts - true_fill_ts).total_seconds()
        assert seconds_ahead_used <= 0, (
            f"row {i}: eval_ts {eval_ts} is AHEAD of true fill_ts {true_fill_ts} "
            f"by {seconds_ahead_used}s -- lookahead regression (INC-20260706-1141)"
        )
        assert eval_ts == true_fill_ts   # exact equality: eval ts IS the true fill-bar ts


def test_old_string_path_would_have_been_future_evaluated_in_dst_season():
    """Using the trades' own `date`/`time` strings (still emitted, unchanged, by the
    FROZEN model01 -- they are UTC wall-clock numbers), reconstruct what the OLD, buggy
    `attach_drift` would have used as its evaluation timestamp, and show that for at
    least one trade in this real DST-season slice it differs from the true fill-bar
    timestamp by >=3600s -- proving the defect class is real and detectable on real data."""
    _, tr, d1, feats = _build_small_slice_stream()
    assert len(tr) > 0

    max_abs_delta_s = 0.0
    any_future = False
    for _, t in tr.iterrows():
        fb = int(t["fill_bar"])
        true_fill_ts = feats.index[fb]
        old_poisoned_ets = pd.Timestamp(f"{t['date']} {t['time']}", tz=NY)
        delta_s = (old_poisoned_ets - true_fill_ts).total_seconds()
        max_abs_delta_s = max(max_abs_delta_s, abs(delta_s))
        if delta_s > 0:
            any_future = True

    assert any_future, "expected at least one trade where the old string-parsed ts is future-evaluated"
    assert max_abs_delta_s >= 3600, (
        f"expected the old date/time-string path to diverge from the true fill ts by "
        f">=3600s for at least one DST-season trade; got max |delta|={max_abs_delta_s}s"
    )
