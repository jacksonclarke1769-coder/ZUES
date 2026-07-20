"""
Concept detectors — PREREG.md §6, frozen 2026-07-20. Every detector is CAUSAL:
a signal's `idx` is the signal-TF bar at whose CLOSE the signal becomes known.
Candidates DataFrame columns (uniform across concepts):
  idx            int, signal-TF bar index of confirmation
  direction      +1 long / -1 short
  mode           'limit' or 'market'
  entry_price    float (zone mid for limit; signal-bar close for market)
  stop_price     float, FINAL structural stop level (tick offset already applied
                 per the concept's own §6 rule — this is a trigger LEVEL, distinct
                 from the execution-slippage tick applied at actual fill time)
  zone_lo/hi     float or NaN (limit-order box, for touch/invalidation checks)
  invalidate_price float or NaN (pre-fill cancellation trigger for limit orders;
                    literal resolution: touching beyond the stop level before the
                    entry is touched invalidates/cancels the working order — same
                    "worst case" spirit as the stop-fills-first fill convention)

Literal-reading resolutions (documented per directive, not tuned):
  - Order Block "last opposing candle immediately before a displacement candle":
    read literally as candle i-1 exactly (no backward scan). If i-1 is not
    opposite-colored, no OB forms at that displacement bar.
  - IFVG "far edge closed through inverts" has no stated search horizon; bounded
    to 100 signal-TF bars, borrowing the Breaker Block's explicit fail-window
    (PREREG §6.4) for consistency and to keep the scan O(n), not tuned per-concept.
  - Sweep/MSS reference "the most recent confirmed swing level/opposing swing":
    read as the level known as of the PRIOR bar (i-1) for the level being acted
    on (it must pre-exist the bar that breaks/sweeps it); the break/reclaim
    bar's own close is compared same-bar (matches cited code's own elementwise
    convention, e.g. smc3 `bull_bos5 = cf_c > lastPH5`).
  - MSS/BOS fires once per break (transition from not-broken to broken), not on
    every bar price remains beyond the level (a literal per-bar re-read of "close
    beyond the level" would double/triple count a trending run into ~1 signal
    per bar, which is not what "MSS/BOS" denotes in ICT usage).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import (TICK, ATR_LEN, GAP_ATR_FLOOR, BREAKER_FAIL_WINDOW, SWEEP_MAX_BARS,
                     LONG, SHORT, fvgs_causal, displacement_strength)

COLS = ["idx", "direction", "mode", "entry_price", "stop_price", "zone_lo", "zone_hi",
        "invalidate_price"]


def _empty():
    return pd.DataFrame({c: pd.Series(dtype=float) for c in COLS})


# --------------------------------------------------------------------------- #
# 1. FVG
# --------------------------------------------------------------------------- #
def detect_fvg(df, atr, swings, disp, fv_cache=None):
    fv = fv_cache if fv_cache is not None else fvgs_causal(df, atr, GAP_ATR_FLOOR)
    if not len(fv):
        return _empty(), fv
    rows = []
    for r in fv.itertuples(index=False):
        mid = (r.top + r.bottom) / 2.0
        if r.direction > 0:
            stop = r.bottom - TICK
            rows.append((r.idx, LONG, "limit", mid, stop, r.bottom, r.top, stop))
        else:
            stop = r.top + TICK
            rows.append((r.idx, SHORT, "limit", mid, stop, r.bottom, r.top, stop))
    return pd.DataFrame(rows, columns=COLS), fv


# --------------------------------------------------------------------------- #
# 2. IFVG — inversion of a rule-1 FVG (far edge closed through), bounded to
#    BREAKER_FAIL_WINDOW signal-TF bars (documented resolution, see module docstring).
# --------------------------------------------------------------------------- #
def detect_ifvg(df, atr, swings, disp, fv_cache=None):
    fv = fv_cache if fv_cache is not None else fvgs_causal(df, atr, GAP_ATR_FLOOR)
    if not len(fv):
        return _empty()
    c = df["Close"].to_numpy(float)
    n = len(df)
    rows = []
    for r in fv.itertuples(index=False):
        i = int(r.idx)
        end = min(i + 1 + BREAKER_FAIL_WINDOW, n)
        if end <= i + 1:
            continue
        window = c[i + 1:end]
        if r.direction > 0:  # bull FVG; far edge = bottom; close < bottom inverts -> SHORT
            hit = np.where(window < r.bottom)[0]
            if hit.size == 0:
                continue
            j = i + 1 + int(hit[0])
            mid = (r.top + r.bottom) / 2.0
            stop = r.top + TICK
            rows.append((j, SHORT, "limit", mid, stop, r.bottom, r.top, stop))
        else:                # bear FVG; far edge = top; close > top inverts -> LONG
            hit = np.where(window > r.top)[0]
            if hit.size == 0:
                continue
            j = i + 1 + int(hit[0])
            mid = (r.top + r.bottom) / 2.0
            stop = r.bottom - TICK
            rows.append((j, LONG, "limit", mid, stop, r.bottom, r.top, stop))
    return pd.DataFrame(rows, columns=COLS)


# --------------------------------------------------------------------------- #
# 3. Order Block — literal "candle i-1 immediately before displacement candle i"
# --------------------------------------------------------------------------- #
def detect_ob(df, atr, swings, disp, disp_cache=None):
    is_disp, ddir = disp_cache if disp_cache is not None else disp
    o = df["Open"].to_numpy(float); c = df["Close"].to_numpy(float)
    l = df["Low"].to_numpy(float); h = df["High"].to_numpy(float)
    n = len(df)
    rows = []
    idxs = np.where(is_disp)[0]
    for i in idxs:
        if i < 1:
            continue
        d = ddir[i]
        if d == 0:
            continue
        j = i - 1
        ob_bear = c[j] < o[j]
        ob_bull = c[j] > o[j]
        lo, hi = l[j], h[j]
        mid = (lo + hi) / 2.0
        if d > 0 and ob_bear:      # bullish displacement after bearish OB candle -> LONG
            stop = lo - TICK
            rows.append((i, LONG, "limit", mid, stop, lo, hi, stop))
        elif d < 0 and ob_bull:    # bearish displacement after bullish OB candle -> SHORT
            stop = hi + TICK
            rows.append((i, SHORT, "limit", mid, stop, lo, hi, stop))
    return pd.DataFrame(rows, columns=COLS)


def _ob_events(df, disp_cache):
    """Internal: OB events with the displacement-bar index, OB candle bounds and
    the ORIGINAL rule-3 direction — feeds the Breaker detector."""
    is_disp, ddir = disp_cache
    o = df["Open"].to_numpy(float); c = df["Close"].to_numpy(float)
    l = df["Low"].to_numpy(float); h = df["High"].to_numpy(float)
    idxs = np.where(is_disp)[0]
    out = []
    for i in idxs:
        if i < 1:
            continue
        d = ddir[i]
        if d == 0:
            continue
        j = i - 1
        ob_bear = c[j] < o[j]
        ob_bull = c[j] > o[j]
        if d > 0 and ob_bear:
            out.append((i, l[j], h[j], LONG))     # bull OB, extreme=low
        elif d < 0 and ob_bull:
            out.append((i, l[j], h[j], SHORT))    # bear OB, extreme=high
    return out


# --------------------------------------------------------------------------- #
# 4. Breaker Block — NEW detector (no existing causal implementation; PREREG §6.4)
# --------------------------------------------------------------------------- #
def detect_breaker(df, atr, swings, disp, disp_cache=None):
    disp_cache = disp_cache if disp_cache is not None else disp
    obs = _ob_events(df, disp_cache)
    if not obs:
        return _empty()
    c = df["Close"].to_numpy(float)
    n = len(df)
    rows = []
    for i, lo, hi, rule3_dir in obs:
        end = min(i + 1 + BREAKER_FAIL_WINDOW, n)
        if end <= i + 1:
            continue
        window = c[i + 1:end]
        mid = (lo + hi) / 2.0
        if rule3_dir == LONG:      # bull OB (support @ lo); fails if close < lo -> SHORT breaker
            hit = np.where(window < lo)[0]
            if hit.size == 0:
                continue
            j = i + 1 + int(hit[0])
            stop = hi + TICK
            rows.append((j, SHORT, "limit", mid, stop, lo, hi, stop))
        else:                      # bear OB (resistance @ hi); fails if close > hi -> LONG breaker
            hit = np.where(window > hi)[0]
            if hit.size == 0:
                continue
            j = i + 1 + int(hit[0])
            stop = lo - TICK
            rows.append((j, LONG, "limit", mid, stop, lo, hi, stop))
    return pd.DataFrame(rows, columns=COLS)


# --------------------------------------------------------------------------- #
# 5. Liquidity Sweep/Raid — primitives.sweep_of_level convention
# --------------------------------------------------------------------------- #
def detect_sweep(df, atr, swings, disp):
    l = df["Low"].to_numpy(float); h = df["High"].to_numpy(float); c = df["Close"].to_numpy(float)
    sl_at, sh_at = swings["sl_at"], swings["sh_at"]
    n = len(df)
    rows = []
    for i in range(1, n):
        lvl_lo = sl_at[i - 1]
        if np.isfinite(lvl_lo) and l[i] < lvl_lo - TICK:
            end = min(i + SWEEP_MAX_BARS, n)
            win_c = c[i:end]
            hit = np.where(win_c > lvl_lo)[0]
            if hit.size:
                j = i + int(hit[0])
                extreme = float(np.min(l[i:j + 1]))
                stop = extreme - TICK
                rows.append((j, LONG, "market", c[j], stop, np.nan, np.nan, np.nan))
        lvl_hi = sh_at[i - 1]
        if np.isfinite(lvl_hi) and h[i] > lvl_hi + TICK:
            end = min(i + SWEEP_MAX_BARS, n)
            win_c = c[i:end]
            hit = np.where(win_c < lvl_hi)[0]
            if hit.size:
                j = i + int(hit[0])
                extreme = float(np.max(h[i:j + 1]))
                stop = extreme + TICK
                rows.append((j, SHORT, "market", c[j], stop, np.nan, np.nan, np.nan))
    return pd.DataFrame(rows, columns=COLS)


# --------------------------------------------------------------------------- #
# 6. MSS/BOS — close beyond most-recent confirmed opposing swing; fires once
#    per break (transition), stop = 1 tick beyond the preceding same-side swing.
# --------------------------------------------------------------------------- #
def detect_mss(df, atr, swings, disp):
    c = df["Close"].to_numpy(float)
    sh_at, sl_at = swings["sh_at"], swings["sl_at"]
    n = len(df)
    rows = []
    for i in range(1, n):
        lvl = sh_at[i]
        if np.isfinite(lvl) and c[i] > lvl and not (np.isfinite(sh_at[i - 1]) and c[i - 1] > sh_at[i - 1]):
            origin = sl_at[i - 1]
            if np.isfinite(origin):
                stop = origin - TICK
                rows.append((i, LONG, "market", c[i], stop, np.nan, np.nan, np.nan))
        lvl2 = sl_at[i]
        if np.isfinite(lvl2) and c[i] < lvl2 and not (np.isfinite(sl_at[i - 1]) and c[i - 1] < sl_at[i - 1]):
            origin = sh_at[i - 1]
            if np.isfinite(origin):
                stop = origin + TICK
                rows.append((i, SHORT, "market", c[i], stop, np.nan, np.nan, np.nan))
    return pd.DataFrame(rows, columns=COLS)


CONCEPTS = {
    "FVG": detect_fvg,
    "IFVG": detect_ifvg,
    "OB": detect_ob,
    "Breaker": detect_breaker,
    "Sweep": detect_sweep,
    "MSS": detect_mss,
}
