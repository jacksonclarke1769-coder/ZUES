"""
SMC3 — faithful, no-lookahead Python mirror of the 3-timeframe ICT/SMC Pine
strategy "SMC HTF Sweep -> 5M Confirm -> 1M Entry".

Native/chart TF = 1m.  Two higher TFs pulled via request.security(lookahead_off):
    HTF     = 60m   (Tier 1 liquidity levels: pivot 3/3, sweep+reclaim)
    confirm = 5m    (Tier 2 BOS / FVG structural confirm, latched)
    trigger = 1m    (Tier 3 BOS / FVG native entry trigger)

Faithfulness contract (mirrors the Pine semantics exactly):
  * request.security(..., "60"/"5", ..., barmerge.lookahead_off): the HTF value
    used on a 1m bar is the value from the most-recent HTF bar whose CLOSE time
    is <= the 1m bar's OPEN time.  A 60m bar [12:00,13:00) closes at 13:00 and
    first becomes readable on the 1m bar opening 13:00.  (searchsorted, side
    'right', on the closed-HTF-bar close-time array.)
  * ta.pivothigh(high, L, R): a pivot at bar c is CONFIRMED only R bars later at
    bar c+R.  60m uses 3/3 (3h lag), 5m and 1m use 2/2.  "Last confirmed pivot"
    = valuewhen carry-forward (forward fill of the confirmation-bar series).
  * Bias state machine, 5m-confirm latch and 1m trigger are stepped/evaluated on
    the 1m timeline.  Entry = trigger-bar CLOSE (process_orders_on_close=true).
  * OCO bracket (fixed stop + 2R limit), simulated on 1m bars STARTING THE BAR
    AFTER entry; stop-first if a single bar spans both.  No time-based exit — a
    trade may stay open to data end (marked OPEN, excluded from closed stats).
  * Costs: commission $2.50/contract PER SIDE ($5 round-trip) + 1 tick (0.25pt)
    adverse slippage on entry AND on each exit.

No lookahead: every 60m level, 5m confirm flag and 1m pivot used to fire a trade
derives from bars closed at/before the trigger bar; entry fills at the trigger
bar's close.  Asserted in-code (see run_backtest -> `lookahead_ok`).
"""

from __future__ import annotations

import sys
import os
import numpy as np
import pandas as pd
from dataclasses import dataclass, field

# Reuse shared helpers from the parent engine (resample, load_data, constants).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import resample_ohlc, load_data, POINT_VALUE, TICK  # noqa: E402

# --- SMC3 cost model (overrides the parent engine's cheaper commission) ------
COMMISSION_PER_SIDE = 2.50   # $ / contract / side  ($5 round-trip)
SLIPPAGE_TICKS = 1.0         # adverse ticks per fill

LONG, SHORT, FLAT = 1, -1, 0


# --------------------------------------------------------------------------- #
# Config — every Pine input exposed as a parameter
# --------------------------------------------------------------------------- #
@dataclass
class Config:
    # --- timeframes ---
    htfTf: int = 60             # Tier-1 liquidity TF (minutes)
    confirmTf: int = 5          # Tier-2 confirm TF (minutes)
    # native/trigger TF is always 1m

    # --- Tier 1: liquidity pivots + sweep ---
    htfPivotLen: int = 3        # ta.pivothigh/low(high, L, L) left=right on 60m
    sweepBufferTicks: float = 2.0   # ticks beyond level required to count a sweep
    reclaimClose: bool = True   # require close back across the level same bar
    contextExpiryBars: int = 180    # 1m bars; clear context if stale

    # --- Tier 2: 5m confirm ---
    confirmPivotLen: int = 2    # 5m pivot left=right
    useBosConfirm: bool = True  # 5m BOS counts as a confirm
    useFvgConfirm: bool = True  # 5m FVG counts as a confirm

    # --- Tier 3: 1m trigger ---
    triggerPivotLen: int = 2    # 1m pivot left=right
    useBosTrigger: bool = True  # 1m BOS counts as a trigger
    useFvgTrigger: bool = True  # 1m FVG counts as a trigger

    # --- stops / targets ---
    stopMode: str = "Recent Swing"   # "Recent Swing" | "Sweep Extreme" | "Wider Of Both"
    swingLookback: int = 10          # lowest(low,N)/highest(high,N)
    stopBufferTicks: float = 4.0     # ticks beyond swing/extreme for the stop
    rrTarget: float = 2.0            # target = entry + rr * risk
    maxStopPoints: float = 120.0     # reject if risk > this (points)
    minRiskPoints: float = TICK      # reject if risk <= this (points)

    # --- execution / session ---
    tradeType: str = "BOTH"     # BOTH | LONG | SHORT
    useSession: bool = False    # default 0000-2359 = always in session
    sessStart: str = "00:00"    # ET, only used when useSession
    sessEnd: str = "23:59"


# --------------------------------------------------------------------------- #
# Pivots (Pine ta.pivothigh / ta.pivotlow semantics)
# --------------------------------------------------------------------------- #
def _pivot(arr: np.ndarray, left: int, right: int, high: bool) -> np.ndarray:
    """Return a series that is the pivot price at the CONFIRMATION bar (c+right)
    and NaN elsewhere.  A pivot high at candidate c requires arr[c] strictly >
    the `left` bars before and the `right` bars after (mirror for low)."""
    n = len(arr)
    cand = np.ones(n, dtype=bool)
    fill = -np.inf if high else np.inf
    for k in range(1, left + 1):
        sh = np.full(n, fill)
        sh[k:] = arr[:-k]                        # arr[c-k]
        cand &= (arr > sh) if high else (arr < sh)
    for k in range(1, right + 1):
        sh = np.full(n, fill)
        sh[:-k] = arr[k:]                        # arr[c+k]
        cand &= (arr > sh) if high else (arr < sh)
    cand[:left] = False                          # not enough left history
    if right > 0:
        cand[n - right:] = False                 # cannot confirm (no right bars)
    out = np.full(n, np.nan)
    c_idx = np.where(cand)[0]
    conf = c_idx + right
    ok = conf < n
    out[conf[ok]] = arr[c_idx[ok]]
    return out


def _ffill(arr: np.ndarray) -> np.ndarray:
    """Forward-fill NaNs (valuewhen carry-forward)."""
    out = arr.copy()
    mask = np.isnan(out)
    idx = np.where(~mask, np.arange(len(out)), 0)
    np.maximum.accumulate(idx, out=idx)
    out = out[idx]
    # leading region before first valid stays NaN
    first_valid = np.argmax(~mask) if (~mask).any() else len(out)
    out[:first_valid] = np.nan
    return out


# --------------------------------------------------------------------------- #
# HTF -> 1m stepping (request.security lookahead_off)
# --------------------------------------------------------------------------- #
def _step_idx(src_close_ns: np.ndarray, t_open_ns: np.ndarray) -> np.ndarray:
    """For each 1m OPEN time, index of the most-recent HTF bar closed at/before
    it (or -1 if none).  This is the lookahead_off mapping."""
    return np.searchsorted(src_close_ns, t_open_ns, side="right") - 1


def _gather(idx: np.ndarray, vals: np.ndarray) -> np.ndarray:
    out = np.full(len(idx), np.nan)
    ok = idx >= 0
    out[ok] = vals[idx[ok]]
    return out


# --------------------------------------------------------------------------- #
# Session helper
# --------------------------------------------------------------------------- #
def _in_session_mask(t_open_ns: np.ndarray, cfg: Config) -> np.ndarray:
    if not cfg.useSession:
        return np.ones(len(t_open_ns), dtype=bool)
    idx = pd.to_datetime(t_open_ns, utc=True).tz_convert("America/New_York")
    mins = np.asarray(idx.hour) * 60 + np.asarray(idx.minute)
    sh, sm = map(int, cfg.sessStart.split(":"))
    eh, em = map(int, cfg.sessEnd.split(":"))
    lo = sh * 60 + sm
    hi = eh * 60 + em
    return (mins >= lo) & (mins <= hi)


# --------------------------------------------------------------------------- #
# Main backtest
# --------------------------------------------------------------------------- #
@dataclass
class RunResult:
    trades: pd.DataFrame        # closed trades
    open_trade: dict | None     # trade still open at data end (or None)
    funnel: dict
    lookahead_ok: bool
    metrics: dict


def run_backtest(df1m: pd.DataFrame, cfg: Config) -> RunResult:
    tick = TICK
    sweep_buf = cfg.sweepBufferTicks * tick
    stop_buf = cfg.stopBufferTicks * tick
    slip = SLIPPAGE_TICKS * tick

    # ---- 1m native arrays --------------------------------------------------
    t_open = df1m.index.view("int64").astype("int64")
    o1 = df1m["open"].to_numpy(float)
    h1 = df1m["high"].to_numpy(float)
    l1 = df1m["low"].to_numpy(float)
    c1 = df1m["close"].to_numpy(float)
    N = len(t_open)
    minute_ns = np.int64(60) * 1_000_000_000

    # ---- Tier 1: 60m liquidity levels -> stepped to 1m ---------------------
    htf = resample_ohlc(df1m, cfg.htfTf)
    htf_open_ns = htf.index.view("int64").astype("int64")
    htf_close_ns = htf_open_ns + np.int64(cfg.htfTf) * minute_ns
    ph60 = _pivot(htf["high"].to_numpy(float), cfg.htfPivotLen, cfg.htfPivotLen, high=True)
    pl60 = _pivot(htf["low"].to_numpy(float), cfg.htfPivotLen, cfg.htfPivotLen, high=False)
    buySide60 = _ffill(ph60)   # most-recent confirmed 60m pivot HIGH (sell buy-side liq above)
    sellSide60 = _ffill(pl60)  # most-recent confirmed 60m pivot LOW  (sell-side liq below)

    idx60 = _step_idx(htf_close_ns, t_open)
    buySideLevel = _gather(idx60, buySide60)     # level above (buy-side liquidity)
    sellSideLevel = _gather(idx60, sellSide60)   # level below (sell-side liquidity)
    src60_close = np.where(idx60 >= 0, htf_close_ns[np.clip(idx60, 0, None)], -1)

    # ---- Tier 2: 5m confirm flags -> stepped to 1m -------------------------
    cf = resample_ohlc(df1m, cfg.confirmTf)
    cf_open_ns = cf.index.view("int64").astype("int64")
    cf_close_ns = cf_open_ns + np.int64(cfg.confirmTf) * minute_ns
    cf_h = cf["high"].to_numpy(float)
    cf_l = cf["low"].to_numpy(float)
    cf_c = cf["close"].to_numpy(float)
    ph5 = _pivot(cf_h, cfg.confirmPivotLen, cfg.confirmPivotLen, high=True)
    pl5 = _pivot(cf_l, cfg.confirmPivotLen, cfg.confirmPivotLen, high=False)
    lastPH5 = _ffill(ph5)
    lastPL5 = _ffill(pl5)
    bull_bos5 = np.where(np.isnan(lastPH5), False, cf_c > lastPH5)
    bear_bos5 = np.where(np.isnan(lastPL5), False, cf_c < lastPL5)
    cf_h2 = np.full(len(cf_h), np.nan); cf_h2[2:] = cf_h[:-2]      # high[2]
    cf_l2 = np.full(len(cf_l), np.nan); cf_l2[2:] = cf_l[:-2]      # low[2]
    bull_fvg5 = np.where(np.isnan(cf_h2), False, cf_l > cf_h2)     # low > high[2]
    bear_fvg5 = np.where(np.isnan(cf_l2), False, cf_h < cf_l2)     # high < low[2]

    idx5 = _step_idx(cf_close_ns, t_open)
    bb5 = _gather(idx5, bull_bos5.astype(float)) > 0.5
    br5 = _gather(idx5, bear_bos5.astype(float)) > 0.5
    bf5 = _gather(idx5, bull_fvg5.astype(float)) > 0.5
    rf5 = _gather(idx5, bear_fvg5.astype(float)) > 0.5
    src5_close = np.where(idx5 >= 0, cf_close_ns[np.clip(idx5, 0, None)], -1)

    bull_confirm5 = (cfg.useBosConfirm & bb5) | (cfg.useFvgConfirm & bf5)
    bear_confirm5 = (cfg.useBosConfirm & br5) | (cfg.useFvgConfirm & rf5)

    # ---- Tier 3: native 1m BOS / FVG ---------------------------------------
    ph1 = _pivot(h1, cfg.triggerPivotLen, cfg.triggerPivotLen, high=True)
    pl1 = _pivot(l1, cfg.triggerPivotLen, cfg.triggerPivotLen, high=False)
    lastPH1 = _ffill(ph1)
    lastPL1 = _ffill(pl1)
    bull1mBOS = np.where(np.isnan(lastPH1), False, c1 > lastPH1)
    bear1mBOS = np.where(np.isnan(lastPL1), False, c1 < lastPL1)
    h1_2 = np.full(N, np.nan); h1_2[2:] = h1[:-2]
    l1_2 = np.full(N, np.nan); l1_2[2:] = l1[:-2]
    bull1mFVG = np.where(np.isnan(h1_2), False, l1 > h1_2)
    bear1mFVG = np.where(np.isnan(l1_2), False, h1 < l1_2)
    bull_trig1 = (cfg.useBosTrigger & bull1mBOS) | (cfg.useFvgTrigger & bull1mFVG)
    bear_trig1 = (cfg.useBosTrigger & bear1mBOS) | (cfg.useFvgTrigger & bear1mFVG)

    # ---- swing stops -------------------------------------------------------
    recentLow = pd.Series(l1).rolling(cfg.swingLookback, min_periods=cfg.swingLookback).min().to_numpy()
    recentHigh = pd.Series(h1).rolling(cfg.swingLookback, min_periods=cfg.swingLookback).max().to_numpy()

    in_sess = _in_session_mask(t_open, cfg)

    # ---- global no-lookahead assertion on the stepped source arrays --------
    m60 = src60_close >= 0
    m5 = src5_close >= 0
    la60 = bool((src60_close[m60] <= t_open[m60]).all())
    la5 = bool((src5_close[m5] <= t_open[m5]).all())
    lookahead_ok = la60 and la5

    # ---- state machine + execution loop ------------------------------------
    longCtx = shortCtx = False
    longSweepBar = shortSweepBar = -1
    longExtreme = shortExtreme = np.nan
    longSweptLevel = shortSweptLevel = np.nan   # 60m level that was swept (for magnitude)
    long_conf_type = short_conf_type = ""       # "BOS" | "FVG" | "both" at latch
    long5 = short5 = False
    entry_sweep_mag = np.nan                     # points price swept beyond the level
    entry_conf_type = ""                         # 5m-confirm type that latched this setup

    n_sweeps = 0
    n_confirms = 0
    n_triggers = 0
    n_valid = 0
    n_reject = 0

    pos = FLAT
    entry_ref = entry_stop = entry_target = entry_risk = np.nan
    entry_idx = -1
    entry_ns = 0
    trade_la_ok = True

    trades = []
    open_trade = None

    allow_long = cfg.tradeType in ("BOTH", "LONG")
    allow_short = cfg.tradeType in ("BOTH", "SHORT")

    def _finish(direction, ex_level, ex_ns, reason):
        if direction == LONG:
            e_fill = entry_ref + slip
            x_fill = ex_level - slip
            net_pts = x_fill - e_fill
        else:
            e_fill = entry_ref - slip
            x_fill = ex_level + slip
            net_pts = e_fill - x_fill
        comm = COMMISSION_PER_SIDE * 2.0
        net_dollars = net_pts * POINT_VALUE - comm
        risk_dollars = entry_risk * POINT_VALUE
        R = net_dollars / risk_dollars if risk_dollars > 0 else np.nan
        hold_min = (ex_ns - entry_ns) / 1e9 / 60.0
        return {
            "dir": "long" if direction == LONG else "short",
            "entry_idx": entry_idx,  # additive: 1m bar index of entry (bar whose CLOSE = entry fill); no effect on existing fields
            "entry_time": pd.Timestamp(entry_ns, tz="UTC"),
            "exit_time": pd.Timestamp(ex_ns, tz="UTC"),
            "entry": round(entry_ref, 2),
            "stop": round(entry_stop, 2),
            "target": round(entry_target, 2),
            "exit": round(ex_level, 2),
            "risk_pts": round(entry_risk, 4),
            "net_pts": net_pts,
            "net_dollars": net_dollars,
            "R": R,
            "reason": reason,
            "hold_min": hold_min,
            "lookahead_ok": trade_la_ok,
            "sweep_mag": entry_sweep_mag,
            "confirm_type": entry_conf_type,
        }

    for i in range(N):
        # (A) expiry — clear stale context (5m latch dies with its context)
        if longCtx and (i - longSweepBar) > cfg.contextExpiryBars:
            longCtx = False; long5 = False
        if shortCtx and (i - shortSweepBar) > cfg.contextExpiryBars:
            shortCtx = False; short5 = False

        # (B) Tier-1 sweep + reclaim (same 1m bar)
        ss = sellSideLevel[i]   # sell-side liquidity below (60m pivot low)
        bs = buySideLevel[i]    # buy-side liquidity above (60m pivot high)
        longSweep = (not np.isnan(ss)) and (l1[i] < ss - sweep_buf) and \
                    ((c1[i] > ss) if cfg.reclaimClose else True)
        shortSweep = (not np.isnan(bs)) and (h1[i] > bs + sweep_buf) and \
                     ((c1[i] < bs) if cfg.reclaimClose else True)
        if longSweep:
            longCtx = True
            longSweepBar = i
            longExtreme = l1[i]
            longSweptLevel = ss
            if shortCtx:
                shortCtx = False; short5 = False
            n_sweeps += 1
        elif shortSweep:
            shortCtx = True
            shortSweepBar = i
            shortExtreme = h1[i]
            shortSweptLevel = bs
            if longCtx:
                longCtx = False; long5 = False
            n_sweeps += 1

        # (C) Tier-2 5m confirm latch  (record which flag latched, additive only)
        if longCtx and (not long5) and bull_confirm5[i]:
            long5 = True; n_confirms += 1
            _b = bool(cfg.useBosConfirm and bb5[i]); _f = bool(cfg.useFvgConfirm and bf5[i])
            long_conf_type = "both" if (_b and _f) else ("BOS" if _b else "FVG")
        if shortCtx and (not short5) and bear_confirm5[i]:
            short5 = True; n_confirms += 1
            _b = bool(cfg.useBosConfirm and br5[i]); _f = bool(cfg.useFvgConfirm and rf5[i])
            short_conf_type = "both" if (_b and _f) else ("BOS" if _b else "FVG")

        # (D) Tier-3 1m trigger
        longTrigger = longCtx and long5 and bull_trig1[i]
        shortTrigger = shortCtx and short5 and bear_trig1[i]
        if longTrigger or shortTrigger:
            n_triggers += 1

        # (E) position management -------------------------------------------
        # exits start the bar AFTER entry
        if pos != FLAT and i > entry_idx:
            if pos == LONG:
                hit_stop = l1[i] <= entry_stop
                hit_tgt = h1[i] >= entry_target
            else:
                hit_stop = h1[i] >= entry_stop
                hit_tgt = l1[i] <= entry_target
            if hit_stop and hit_tgt:
                trades.append(_finish(pos, entry_stop, int(t_open[i] + minute_ns), "stop"))
                pos = FLAT
            elif hit_stop:
                trades.append(_finish(pos, entry_stop, int(t_open[i] + minute_ns), "stop"))
                pos = FLAT
            elif hit_tgt:
                trades.append(_finish(pos, entry_target, int(t_open[i] + minute_ns), "target"))
                pos = FLAT

        # entry only when flat & in session
        if pos == FLAT and in_sess[i]:
            fire_dir = 0
            if longTrigger and allow_long:
                fire_dir = LONG
            elif shortTrigger and allow_short:
                fire_dir = SHORT
            if fire_dir != 0:
                px = c1[i]
                if fire_dir == LONG:
                    if cfg.stopMode == "Recent Swing":
                        stop = recentLow[i] - stop_buf
                    elif cfg.stopMode == "Sweep Extreme":
                        stop = longExtreme - stop_buf
                    else:  # Wider Of Both
                        stop = min(recentLow[i] - stop_buf,
                                   (longExtreme - stop_buf) if not np.isnan(longExtreme) else np.inf)
                    risk = px - stop
                    target = px + cfg.rrTarget * risk
                else:
                    if cfg.stopMode == "Recent Swing":
                        stop = recentHigh[i] + stop_buf
                    elif cfg.stopMode == "Sweep Extreme":
                        stop = shortExtreme + stop_buf
                    else:
                        stop = max(recentHigh[i] + stop_buf,
                                   (shortExtreme + stop_buf) if not np.isnan(shortExtreme) else -np.inf)
                    risk = stop - px
                    target = px - cfg.rrTarget * risk

                valid = (not np.isnan(risk)) and (risk > cfg.minRiskPoints) and (risk <= cfg.maxStopPoints)
                if valid:
                    # no-lookahead check for THIS fire
                    ok60 = (src60_close[i] < 0) or (src60_close[i] <= t_open[i])
                    ok5 = (src5_close[i] < 0) or (src5_close[i] <= t_open[i])
                    trade_la_ok = ok60 and ok5
                    pos = fire_dir
                    entry_ref = px
                    entry_stop = stop
                    entry_target = target
                    entry_risk = risk
                    entry_idx = i
                    entry_ns = int(t_open[i] + minute_ns)   # trigger-bar CLOSE
                    # additive entry-context recording (no effect on logic)
                    if fire_dir == LONG:
                        entry_sweep_mag = (longSweptLevel - longExtreme) \
                            if not (np.isnan(longSweptLevel) or np.isnan(longExtreme)) else np.nan
                        entry_conf_type = long_conf_type
                    else:
                        entry_sweep_mag = (shortExtreme - shortSweptLevel) \
                            if not (np.isnan(shortSweptLevel) or np.isnan(shortExtreme)) else np.nan
                        entry_conf_type = short_conf_type
                    # consume the setup
                    if fire_dir == LONG:
                        longCtx = False; long5 = False
                    else:
                        shortCtx = False; short5 = False
                    n_valid += 1
                else:
                    n_reject += 1

    # trade still open at data end
    if pos != FLAT:
        open_trade = {
            "dir": "long" if pos == LONG else "short",
            "entry_time": pd.Timestamp(entry_ns, tz="UTC"),
            "entry": round(entry_ref, 2),
            "stop": round(entry_stop, 2),
            "target": round(entry_target, 2),
            "risk_pts": round(entry_risk, 4),
        }

    tdf = pd.DataFrame(trades)
    funnel = {
        "htf_sweeps": n_sweeps,
        "confirms_5m": n_confirms,
        "triggers_1m": n_triggers,
        "valid_trades": n_valid,
        "risk_rejects": n_reject,
        "open_at_end": 0 if open_trade is None else 1,
    }
    return RunResult(trades=tdf, open_trade=open_trade, funnel=funnel,
                     lookahead_ok=lookahead_ok, metrics=compute_metrics(tdf))


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def compute_metrics(tdf: pd.DataFrame) -> dict:
    if tdf is None or len(tdf) == 0:
        return {"n": 0}
    d = tdf["net_dollars"].to_numpy()
    wins = d[d > 0]
    losses = d[d < 0]
    gp = wins.sum()
    gl = -losses.sum()
    pf = gp / gl if gl > 0 else np.inf
    eq = np.cumsum(d)
    peak = np.maximum.accumulate(eq)
    maxdd = float(-(eq - peak).min()) if len(eq) else 0.0
    R = tdf["R"].to_numpy()
    return {
        "n": int(len(tdf)),
        "win_pct": float((d > 0).mean() * 100),
        "pf": float(pf) if pf != np.inf else np.inf,
        "net_dollars": float(d.sum()),
        "avg_dollars": float(d.mean()),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "total_R": float(R.sum()),
        "avg_R": float(R.mean()),
        "maxdd_dollars": maxdd,
        "median_hold_min": float(tdf["hold_min"].median()),
    }


def per_year(tdf: pd.DataFrame) -> dict:
    if tdf is None or len(tdf) == 0:
        return {}
    out = {}
    yrs = tdf["exit_time"].dt.year
    for y in sorted(yrs.unique()):
        sub = tdf[yrs == y]["net_dollars"].to_numpy()
        gp = sub[sub > 0].sum(); gl = -sub[sub < 0].sum()
        pf = gp / gl if gl > 0 else (np.inf if gp > 0 else np.nan)
        wr = float((sub > 0).mean() * 100)
        out[int(y)] = {"n": int(len(sub)), "wr": wr, "pf": pf, "net": float(sub.sum())}
    return out


def window_stats(tdf: pd.DataFrame, start_year: int, end_year: int) -> dict:
    if tdf is None or len(tdf) == 0:
        return {"n": 0}
    yrs = tdf["exit_time"].dt.year
    sub = tdf[(yrs >= start_year) & (yrs <= end_year)]
    return compute_metrics(sub)
