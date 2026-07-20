"""
Shared machinery for the ICT concept survey (PREREG.md).

Single-vendor Databento NQ 1m data only. All timestamps tz-aware; ET conversions
via zoneinfo America/New_York. Fill/exit conventions reused (not reinvented) from
zeus-occ-optimize/engine.py (stop-fills-first-on-tie, wilder_atr, POINT_VALUE/
TICK/COMMISSION/SLIPPAGE constants) and smc3_engine.py (_pivot confirmed-swing
convention: left=3/right=3, strict both sides, value posted at confirm bar).
"""
from __future__ import annotations

import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

NY = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# ---- execution constants (PREREG §3 / reused from zeus-occ-optimize/engine.py) ----
POINT_VALUE = 20.0            # $ per NQ point per contract
TICK = 0.25                   # point
COMMISSION_PER_SIDE = 0.50    # $/contract/side -> $1.00 round-turn (PREREG §3)
SLIPPAGE_TICKS = 1.0          # adverse ticks per fill (entry AND exit)

DATA_PATH = "/Users/jacksonclarke/trading-team/data/real_futures/NQ_databento_1m_5y.parquet"

FRACTAL_LEFT = 3
FRACTAL_RIGHT = 3
ATR_LEN = 14
DISPLACEMENT_LOOKBACK = 20
DISPLACEMENT_MULT = 2.0
GAP_ATR_FLOOR = 0.25
LIMIT_LIFETIME_BARS = 20       # signal-TF bars
BREAKER_FAIL_WINDOW = 100      # signal-TF bars
EOD_FLAT_HHMM = (16, 55)       # ET, on the signal's exchange day
SWEEP_MAX_BARS = 3

LONG, SHORT = 1, -1


# --------------------------------------------------------------------------- #
# Data load
# --------------------------------------------------------------------------- #
def load_1m(path: str = DATA_PATH) -> pd.DataFrame:
    """bar-open UTC index, columns open/high/low/close/volume. Single-vendor only."""
    df = pd.read_parquet(path)
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                             "close": "Close", "volume": "Volume"})
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df[["Open", "High", "Low", "Close", "Volume"]]


def resample_causal(df1m: pd.DataFrame, tf_min: int) -> pd.DataFrame:
    """Resample 1m -> tf_min bars, label=left/closed=left (a signal-TF bar's
    OWN index value is its OPEN time; it is only 'known' at OPEN + tf_min,
    i.e. at the next bar's open). Native 1m returns df1m unchanged (copy)."""
    if tf_min == 1:
        return df1m.copy()
    o = df1m["Open"].resample(f"{tf_min}min", label="left", closed="left").first()
    h = df1m["High"].resample(f"{tf_min}min", label="left", closed="left").max()
    l = df1m["Low"].resample(f"{tf_min}min", label="left", closed="left").min()
    c = df1m["Close"].resample(f"{tf_min}min", label="left", closed="left").last()
    v = df1m["Volume"].resample(f"{tf_min}min", label="left", closed="left").sum()
    out = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c, "Volume": v}).dropna(
        subset=["Open", "High", "Low", "Close"])
    return out


# --------------------------------------------------------------------------- #
# Confirmed fractal swings — smc3 `_pivot` convention (strict both sides),
# left=3 / right=3, value posted at the CONFIRMATION bar (pivot_idx + right).
# --------------------------------------------------------------------------- #
def pivot_confirmed(arr: np.ndarray, left: int, right: int, high: bool) -> np.ndarray:
    n = len(arr)
    cand = np.ones(n, dtype=bool)
    fill = -np.inf if high else np.inf
    for k in range(1, left + 1):
        sh = np.full(n, fill)
        sh[k:] = arr[:-k]
        cand &= (arr > sh) if high else (arr < sh)
    for k in range(1, right + 1):
        sh = np.full(n, fill)
        sh[:-k] = arr[k:]
        cand &= (arr > sh) if high else (arr < sh)
    cand[:left] = False
    if right > 0:
        cand[n - right:] = False
    out = np.full(n, np.nan)
    c_idx = np.where(cand)[0]
    conf = c_idx + right
    ok = conf < n
    out[conf[ok]] = arr[c_idx[ok]]
    return out


def ffill(arr: np.ndarray) -> np.ndarray:
    s = pd.Series(arr)
    return s.ffill().to_numpy()


def confirmed_swings(df: pd.DataFrame, left=FRACTAL_LEFT, right=FRACTAL_RIGHT):
    """Returns dict with:
      sh_at, sl_at : last-known confirmed swing high/low price as of bar t (incl. t)
      sh_events, sl_events : (conf_idx array asc, price array) of confirmation events
    """
    h, l = df["High"].to_numpy(float), df["Low"].to_numpy(float)
    ph = pivot_confirmed(h, left, right, True)
    pl = pivot_confirmed(l, left, right, False)
    sh_at = ffill(ph)
    sl_at = ffill(pl)
    sh_idx = np.where(~np.isnan(ph))[0]
    sl_idx = np.where(~np.isnan(pl))[0]
    return dict(sh_at=sh_at, sl_at=sl_at,
                sh_events=(sh_idx, ph[sh_idx]),
                sl_events=(sl_idx, pl[sl_idx]))


# --------------------------------------------------------------------------- #
# ATR (Wilder RMA), displacement, FVGs — reused conventions
# --------------------------------------------------------------------------- #
def wilder_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, length: int = ATR_LEN) -> np.ndarray:
    prev_close = np.roll(close, 1)
    prev_close[0] = np.nan
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    tr[0] = high[0] - low[0]
    atr = np.full(len(tr), np.nan)
    if len(tr) < length:
        return atr
    atr[length - 1] = np.nanmean(tr[:length])
    alpha = 1.0 / length
    for i in range(length, len(tr)):
        atr[i] = atr[i - 1] + alpha * (tr[i] - atr[i - 1])
    return atr


def displacement_strength(df: pd.DataFrame, lookback=DISPLACEMENT_LOOKBACK, mult=DISPLACEMENT_MULT):
    """Signed body-ratio displacement. +1 bull disp / -1 bear disp / 0 none at mult threshold."""
    o, c = df["Open"].to_numpy(float), df["Close"].to_numpy(float)
    body = np.abs(c - o)
    avg = pd.Series(body).shift(1).rolling(lookback).mean().to_numpy()
    ratio = body / avg
    direction = np.sign(c - o)
    is_disp = ratio >= mult
    return is_disp, direction.astype(int)


def fvgs_causal(df: pd.DataFrame, atr: np.ndarray, size_floor_mult=GAP_ATR_FLOOR):
    """3-candle FVGs, causal at candle-3 close (idx i). direction +1 bull/-1 bear.
    top/bottom per primitives.fvgs convention. Size floor = size_floor_mult*ATR[i]."""
    h, l = df["High"].to_numpy(float), df["Low"].to_numpy(float)
    n = len(df)
    idx, direction, top, bottom = [], [], [], []
    for i in range(2, n):
        c1h, c1l, c3h, c3l = h[i - 2], l[i - 2], h[i], l[i]
        a = atr[i]
        if not np.isfinite(a):
            continue
        floor = size_floor_mult * a
        if c1h < c3l and (c3l - c1h) >= floor:
            idx.append(i); direction.append(1); top.append(c3l); bottom.append(c1h)
        elif c1l > c3h and (c1l - c3h) >= floor:
            idx.append(i); direction.append(-1); top.append(c1l); bottom.append(c3h)
    return pd.DataFrame(dict(idx=idx, direction=direction, top=top, bottom=bottom))


# --------------------------------------------------------------------------- #
# Exchange-day / EOD-flat timestamp helpers
# --------------------------------------------------------------------------- #
def exch_day_cutoff(ts_utc: pd.Timestamp) -> pd.Timestamp:
    """16:55 ET cutoff of ts's CME exchange trading day (session begins ~18:00 ET
    prior evening, labeled the NEXT calendar day; boundary used here = 17:00 ET)."""
    ts_et = ts_utc.tz_convert(NY)
    if ts_et.time() >= pd.Timestamp("17:00").time():
        day = (ts_et + pd.Timedelta(days=1)).normalize()
    else:
        day = ts_et.normalize()
    cutoff = day + pd.Timedelta(hours=16, minutes=55)
    if ts_et >= cutoff:
        cutoff = cutoff + pd.Timedelta(days=1)
    return cutoff.tz_convert("UTC")


def build_eod_cutoff_array(ts_index_utc: pd.DatetimeIndex) -> np.ndarray:
    """Vectorized 16:55 ET cutoff (as int64 ns) for every bar in ts_index_utc."""
    et = ts_index_utc.tz_convert(NY)
    minute_of_day = et.hour * 60 + et.minute
    is_next = minute_of_day >= (17 * 60)
    day = et.normalize()
    day = day.where(~is_next, day + pd.Timedelta(days=1))
    cutoff = day + pd.Timedelta(hours=16, minutes=55)
    past = et >= cutoff
    cutoff = cutoff.where(~past, cutoff + pd.Timedelta(days=1))
    return cutoff.tz_convert("UTC").asi8


# --------------------------------------------------------------------------- #
# Cost/slip finish (reused from zeus-occ-optimize/engine.py `finish`)
# --------------------------------------------------------------------------- #
def finish(direction, entry_ref, exit_level, risk):
    slip = SLIPPAGE_TICKS * TICK
    if direction == LONG:
        e_fill = entry_ref + slip
        x_fill = exit_level - slip
        net_pts = x_fill - e_fill
    else:
        e_fill = entry_ref - slip
        x_fill = exit_level + slip
        net_pts = e_fill - x_fill
    comm = COMMISSION_PER_SIDE * 2.0
    net_dollars = net_pts * POINT_VALUE - comm
    risk_dollars = risk * POINT_VALUE
    R = net_dollars / risk_dollars if risk_dollars > 0 else np.nan
    return net_dollars, R, e_fill, x_fill
