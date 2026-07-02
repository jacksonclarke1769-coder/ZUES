"""Look-ahead canary (2026-07-02): proves the canary catches the Z-class bug and blesses the
canonical causal helper. Every NEW research feature must ship with an assert_causal() test."""
import numpy as np
import pandas as pd
import pytest

from lookahead_canary import assert_causal, completed_bucket_slope, poison_after

NY = "America/New_York"


def _frame(n=2000, seed=3):
    idx = pd.date_range("2026-03-02 09:30", periods=n, freq="5min", tz=NY)
    rng = np.random.default_rng(seed)
    c = 20000 + np.cumsum(rng.normal(0, 8, n))
    return pd.DataFrame({"Open": c, "High": c + 5, "Low": c - 5, "Close": c,
                         "Volume": np.full(n, 100.0)}, index=idx)


def _ts_samples(df, k=12):
    return list(df.index[len(df) // 3::len(df) // (3 * k)][:k])


def test_canary_catches_the_z_bug():
    """The EXACT buggy pattern from ticket Z: full-frame resample indexed at the bucket
    CONTAINING ts. The canary must flag it."""
    df = _frame()

    def buggy(frame, ts):
        c = frame.Close.resample("4h").last().dropna()
        sl = np.sign(c.ewm(span=20).mean().diff())
        i = sl.index.searchsorted(ts, side="right") - 1      # in-progress bucket -> future close
        return float(sl.iloc[i]) if i >= 0 else float("nan")

    with pytest.raises(AssertionError, match="LOOK-AHEAD"):
        assert_causal(buggy, df, _ts_samples(df), label="z-bug-repro")


def test_completed_bucket_slope_is_causal():
    df = _frame()
    for rule in ("15min", "1h", "4h"):
        assert_causal(lambda f, ts, r=rule: completed_bucket_slope(f, r, ts),
                      df, _ts_samples(df), label=f"completed_bucket_slope({rule})")


def test_canary_catches_fill_bar_style_peek():
    """F1-class: a 'feature' that reads the bar AFTER ts (e.g. same-bar/next-bar outcome peeking)."""
    df = _frame()

    def peeker(frame, ts):
        i = frame.index.searchsorted(ts, side="right")       # first bar strictly after ts
        return float(frame.Close.iloc[i]) if i < len(frame) else float("nan")

    with pytest.raises(AssertionError, match="LOOK-AHEAD"):
        assert_causal(peeker, df, _ts_samples(df), label="f1-style-peek")


def test_causal_feature_passes():
    df = _frame()
    assert_causal(lambda f, ts: float(f.Close.loc[:ts].iloc[-1]), df, _ts_samples(df),
                  label="last-close<=ts")


def test_poison_changes_only_future():
    df = _frame()
    ts = df.index[len(df) // 2]
    p = poison_after(df, ts)
    pd.testing.assert_frame_equal(df.loc[:ts], p.loc[:ts])
    assert not np.allclose(df.loc[df.index > ts, "Close"], p.loc[p.index > ts, "Close"])
