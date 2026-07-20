"""Same-bar fill-convention audit tests for tools_1m_truth_recert.b_streams / walk_5m.

Follow-up to tests/test_fork_a_fill_convention.py (FORK-A audit, AUDIT-20260720-0952):
walk_5m is the legacy 5m baseline walker for Profile B (R_old column). Certified B numbers are
R_new (walk_1m, separately verified). walk_5m is a closure inside b_streams, so these tests
drive the REAL code path end-to-end with a synthetic frame.

Pinned behaviors:
1. A retest (fill) bar that also breaches the stop books a filled-then-stopped -1.0R —
   never skipped/cancelled (the survey bug class, AUDIT-20260720-0941).
2. KNOWN SOFTNESS (documented, pinned): walk_5m credits target on the fill bar after the
   stop check (optimistic legacy convention); walk_1m does not. If this test starts failing
   because walk_5m stopped crediting fill-bar targets, that is a convention change to the
   legacy baseline — re-run any comparison that cites R_old.
"""
import numpy as np
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools_1m_truth_recert as T1M

NY = "America/New_York"


def _mk_day(retest_low, retest_high=20012.0, post_flat=20005.0, retest_1m=None):
    """One synthetic session: premarket for ATR, 3-bar OR (orh=20010), break bar,
    then a retest bar with the given low, then a flat afternoon."""
    rows, times = [], []
    day = "2026-03-02"
    # premarket 04:00-09:25 -> ATR(14) ~ 10pts
    for t in pd.date_range(f"{day} 04:00", f"{day} 09:25", freq="5min", tz=NY):
        rows.append((20005.0, 19995.0, 20000.0)); times.append(t)
    # OR bars 09:30-09:40: orh 20010, orl 20000
    for t in pd.date_range(f"{day} 09:30", f"{day} 09:40", freq="5min", tz=NY):
        rows.append((20010.0, 20000.0, 20005.0)); times.append(t)
    # 09:45 break bar: close above orh
    times.append(pd.Timestamp(f"{day} 09:45", tz=NY)); rows.append((20013.0, 20008.0, 20012.0))
    # 09:50 retest bar (the fill bar under audit)
    times.append(pd.Timestamp(f"{day} 09:50", tz=NY)); rows.append((retest_high, retest_low, 20008.0))
    # flat rest of RTH (>=20 RTH bars total)
    for t in pd.date_range(f"{day} 09:55", f"{day} 15:55", freq="5min", tz=NY):
        rows.append((post_flat + 2, post_flat - 2, post_flat)); times.append(t)
    df5 = pd.DataFrame(rows, columns=["High", "Low", "Close"], index=pd.DatetimeIndex(times))
    # 1m frame for M1Map: 5 identical 1m slices per 5m bar (naive, like load_frames output)
    retest_ts = pd.Timestamp(f"{day} 09:50", tz=NY)
    t1, r1 = [], []
    for t, (h, l, c) in zip(times, rows):
        for k in range(5):
            t1.append(t.tz_localize(None) + pd.Timedelta(minutes=k))
            if t == retest_ts and retest_1m is not None:
                r1.append(retest_1m[k])          # custom 1m decomposition of the retest bar
            else:
                r1.append((h, l, c))
    d1 = pd.DataFrame(r1, columns=["high", "low", "close"], index=pd.DatetimeIndex(t1))
    return df5, T1M.M1Map(d1, df5)


def test_retest_bar_breaching_stop_books_loss_not_cancel():
    # atr0 ~= 10 -> stop = 20010 - 10 = 20000. Retest bar low 19995 breaches it.
    df5, mp = _mk_day(retest_low=19995.0)
    out = T1M.b_streams(df5, mp)
    assert len(out) == 1, f"synthetic day produced {len(out)} trades, expected 1"
    row = out[0]
    for k in ("single1", "single15", "partial"):
        assert row["R_old"][k] == -1.0, (
            f"walk_5m {k}: retest bar breaching stop gave {row['R_old'][k]} — "
            "must be filled-then-stopped -1.0R, never skipped (survey bug class)")
        assert row["filled"][k] and row["R_new"][k] is not None and row["R_new"][k] < -0.9, (
            f"walk_1m {k}: same-bar loss not booked (R_new={row['R_new'][k]})")


def test_fill_bar_target_convention_divergence_is_pinned():
    # Retest bar spans entry AND the 1.0-ATR target (high 20021 > 20010+10), no stop breach.
    # 1m decomposition: ONLY the first 1m bar (the fill bar) touches entry and target;
    # the remaining 1m bars stay between entry and target so a next-bar target is impossible.
    fill_1m = [(20021.0, 20008.0, 20012.0)] + [(20012.0, 20011.0, 20011.5)] * 4
    df5, mp = _mk_day(retest_low=20008.0, retest_high=20021.0, retest_1m=fill_1m)
    out = T1M.b_streams(df5, mp)
    assert len(out) == 1
    row = out[0]
    # legacy walk_5m credits the fill-bar target (optimistic, documented softness)
    assert row["R_old"]["single1"] == 1.0, (
        f"walk_5m fill-bar-target convention changed (got {row['R_old']['single1']}) — "
        "legacy R_old baseline no longer comparable to prior reports")
    # certified walk_1m must NOT credit target on the fill bar
    assert row["R_new"]["single1"] is not None and row["R_new"]["single1"] < 1.0, (
        f"walk_1m credited a fill-bar target (R_new={row['R_new']['single1']}) — "
        "violates the conservative certified convention")
