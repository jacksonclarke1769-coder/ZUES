"""HTF trend alignment classifier for Profile A.

Pure function; no side effects; no live-engine imports.
Matches the research definition in tools_a_v2_score.py::build() exactly:
  resample 15min/1h/4h label-left closed-left from the 5m Close,
  ewm(span=20).mean().diff(), np.sign, lookup via searchsorted(ts,"right")-1,
  result multiplied by trade direction (+1 long / -1 short).
"""
import numpy as np
import pandas as pd


def compute_htf_alignment(df5: pd.DataFrame, ts, direction: str):
    """Compute HTF EMA(20)-slope alignment score at fill timestamp ts.

    Parameters
    ----------
    df5       : DataFrame with tz-aware DatetimeIndex and a 'Close' column.
                Should cover >= 35 days of 5m bars for a meaningful EMA warmup.
    ts        : fill-bar timestamp (tz-aware pd.Timestamp or compatible).
    direction : "long" or "short"

    Returns
    -------
    (htf15, htf1h, htf4h, alignment)
        htf15 / htf1h / htf4h : float, sign of EMA(20) slope * direction (+1/0/-1),
                                 or NaN if no bar precedes ts at that timeframe.
        alignment              : float, sum of non-NaN components. NaN if all three are NaN.
    """
    if not len(df5):
        nan = float("nan")
        return nan, nan, nan, nan

    ts = pd.Timestamp(ts)

    d = 1 if direction == "long" else -1

    def _slope_sign(freq: str) -> pd.Series:
        c = df5["Close"].resample(freq).last().dropna()
        return np.sign(c.ewm(span=20).mean().diff())

    def _lookup(series: pd.Series) -> float:
        if not len(series):
            return float("nan")
        i = series.index.searchsorted(ts, "right") - 1
        if i < 0:
            return float("nan")
        return float(series.iloc[i]) * d

    v15 = _lookup(_slope_sign("15min"))
    v1h = _lookup(_slope_sign("1h"))
    v4h = _lookup(_slope_sign("4h"))

    parts = [v for v in (v15, v1h, v4h) if not np.isnan(v)]
    alignment = float(sum(parts)) if parts else float("nan")

    return v15, v1h, v4h, alignment
