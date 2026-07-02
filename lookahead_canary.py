"""LOOK-AHEAD CANARY — mandatory causality check for every research feature (AGENTS.md rule).

Born 2026-07-02 from two caught leaks:
  * F1: fill simulators booked targets off the FILL BAR's own extremes (entry-vs-target sequencing).
  * Z : an HTF feature indexed a full-frame resample at "the bucket containing ts" — a full-frame
        resample fills that bucket with its FINAL close = post-signal data. The resulting "edge"
        (era-consistent, +3pp pass!) evaporated under the causal definition.

THE TEST: a feature fn(df, ts) is causal iff poisoning every row STRICTLY AFTER ts leaves its value
unchanged. Any feature whose research reference cannot pass assert_causal() must not be believed,
certified, or ticketed. Use completed_bucket_slope() below as the canonical causal way to read a
higher-timeframe indicator at time ts.
"""
import numpy as np
import pandas as pd

PRICE_COLS = ("Open", "High", "Low", "Close")


def poison_after(df, ts, seed=7):
    """Corrupt every row with index > ts (prices scrambled + shifted, volume zeroed)."""
    out = df.copy()
    m = out.index > ts
    if m.any():
        rng = np.random.default_rng(seed)
        n = int(m.sum())
        for c in PRICE_COLS:
            if c in out.columns:
                out.loc[m, c] = out.loc[m, c].values * (1 + rng.normal(0.05, 0.02, n)) + 500.0
        if "Volume" in out.columns:
            out.loc[m, "Volume"] = 0
    return out


def assert_causal(fn, df, ts_list, label="feature", seed=7):
    """fn(df, ts) -> value. Raises AssertionError naming the first timestamp whose value changes
    when the future is poisoned. NaN == NaN counts as equal."""
    for ts in ts_list:
        a, b = fn(df, ts), fn(poison_after(df, ts, seed), ts)
        ok = (a == b) or (a != a and b != b) or (
            isinstance(a, tuple) and isinstance(b, tuple)
            and all((x == y) or (x != x and y != y) for x, y in zip(a, b)))
        assert ok, (f"LOOK-AHEAD in {label} at {ts}: clean={a!r} poisoned={b!r} — the feature reads "
                    f"data from after ts (Z-class bug: check resample bucket boundaries / fill bars)")
    return True


def completed_bucket_slope(df5, rule, ts, span=20, col="Close"):
    """CANONICAL causal HTF read: EMA(span) slope sign from the last resample bucket whose window
    FULLY CLOSED at or before ts. Never reads the in-progress bucket (that is the Z bug)."""
    width = pd.tseries.frequencies.to_offset(rule)
    c = df5[col].resample(rule, label="left", closed="left").last().dropna()
    sl = c.ewm(span=span).mean().diff()
    i = sl.index.searchsorted(ts - width, side="right") - 1   # bucket start <= ts - width => closed
    if i < 0 or sl.iloc[i] != sl.iloc[i]:
        return float("nan")
    return float(np.sign(sl.iloc[i]))
