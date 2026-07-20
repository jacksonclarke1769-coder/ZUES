"""
HTF confluence chain — PREREG_CHAIN.md (frozen commit eaef4a4), FROZEN 2026-07-20.
1H bias (EMA50 + confirmed-3/3-BOS agreement) -> 15m prior-RTH-session sweep (arm 8 bars)
-> 15m FVG >=0.5*ATR(14,15m) w/ displacement candle >=1.5x trailing-20-body -> 1m limit at
the FVG proximal edge -> stop 1 tick beyond sweep extreme / target nearest opposite liquidity
>=1*ATR(15m) else 2R. One position at a time, EOD flat 16:55 ET.

Reuses (imports, does not reinvent) backtests/zeus-ict-2026-07/concept_survey machinery:
common.py (load_1m, resample_causal, wilder_atr, confirmed_swings, fvgs_causal,
displacement_strength, exch_day_cutoff, build_eod_cutoff_array, finish, NY/TICK/ATR_LEN
constants) and survey_engine.py (_nearest_target, _atr_at — the certified target-search /
ATR-lookup helpers). The 1m fill walker below (`run_chain`) is an ADAPTED COPY of
survey_engine.run_cell: identical fill semantics (first-touch, stop-fills-first-on-any-bar-
including-the-fill-bar, one order-lifetime concept, $1 round-turn / 1-tick slip via
common.finish) — the only structural change is that order lifetime end is a precomputed
per-row field (`order_end_ns`, anchored to the Condition-2 arm window from the SWEEP bar,
not a fixed tf*LIMIT_LIFETIME_BARS formula) and direction is read per-row (mixed long/short
candidates walked in one combined, time-ordered, single-position sequence — this chain's
"one position at a time" applies across BOTH directions, unlike the concept-survey's
per-direction "cells").

Documented literal-reading resolutions (frozen, NOT tuned — see PREREG_CHAIN.md and the
report for the ones that matter):
  R1. FVG proximal/distal edge: the prereg's parenthetical for the bullish case ("the gap's
      lower/top-of-lower-candle edge") is geometrically inconsistent with its own decisive
      clause ("i.e. the edge price first re-touches on the return") — candle-1's high (the
      "top of the lower candle") is the FAR edge on a bullish retracement (price returns DOWN
      from above and reaches candle-3's low first). Resolved via the unambiguous, standard-
      ICT-convention clause: proximal = the edge belonging to candle-3 (the confirmation
      candle, first touched on the return); distal = the edge belonging to candle-1 (the
      origin candle, only reached if the gap fully fills). Symmetric for bearish.
  R2. Bias-gate scope: Condition 1 ("only longs in LONG bias, only shorts in SHORT bias") is
      checked at (a) the sweep bar's close and (b) the FVG's candle-3 close (setup formation);
      NOT re-checked again at the moment the resting 1m limit actually fills (entry is order
      mechanics for an already-validated setup, matching how every existing detector in this
      codebase treats a confirmed setup's resting order).
  R3. "Valid for the next 8 15m bars" is read as 8 BAR COUNT (not clock-elapsed-time) — i.e.
      FVG candle-3 index in [sweep_idx+1, sweep_idx+8] inclusive; "(2 hours)" is the normal-
      case clock equivalent, not an independent constraint.
  R4. "Prior RTH session" pool = the most recently CLOSED RTH session's H/L (known from that
      session's 16:00 ET close), used both as the Condition-2 sweep pool and, for the
      opposite side, as one of the two Condition-5 target-liquidity pools.
  R5. Window-boundary timestamps are UTC calendar timestamps matching the data's own UTC
      index (same resolution documented in survey_engine.py; the prereg does not specify a
      split-boundary tz).
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

SURVEY_DIR = "/Users/jacksonclarke/trading-team/backtests/zeus-ict-2026-07/concept_survey"
sys.path.insert(0, SURVEY_DIR)

from common import (  # noqa: E402
    NY, TICK, ATR_LEN, LONG, SHORT,
    load_1m, resample_causal, wilder_atr, confirmed_swings, displacement_strength,
    fvgs_causal, exch_day_cutoff, build_eod_cutoff_array, finish,
)
from survey_engine import _nearest_target, _atr_at  # noqa: E402

# --------------------------------------------------------------------------- #
# Frozen chain constants (PREREG_CHAIN.md — every value below is a-priori, none tuned)
# --------------------------------------------------------------------------- #
EMA_LEN = 50                  # Condition 1, 1H
FRACTAL_L = FRACTAL_R = 3      # Condition 1 swing / Condition 5 opposing-swing pool
GAP_ATR_FLOOR = 0.5            # Condition 3 FVG size floor, x ATR(14,15m)
DISP_MULT = 1.5                # Condition 3 displacement candle, x trailing-20-body
DISP_LOOKBACK = 20
ARM_BARS = 8                   # Condition 2, 15m bars (R3)
TARGET_ATR_MULT = 1.0          # Condition 5
FALLBACK_R = 2.0               # Condition 5 fallback
RTH_START_MIN = 9 * 60 + 30    # 09:30 ET
RTH_END_MIN = 16 * 60          # 16:00 ET (exclusive)

BUFFER_START = pd.Timestamp("2024-01-01", tz="UTC")   # warmup, not scored (R5)
WINDOW_START = pd.Timestamp("2024-06-22", tz="UTC")
SPLIT_TS = pd.Timestamp("2025-06-22", tz="UTC")
WINDOW_END = pd.Timestamp("2026-06-22", tz="UTC")

CAND_COLS = ["direction", "mode", "entry_price", "stop_price", "invalidate_price",
             "zone_lo", "zone_hi", "conf_ts", "order_end_ns", "sweep_ts", "sweep_extreme",
             "fvg_idx", "sweep_idx"]


# --------------------------------------------------------------------------- #
# Condition 1 — 1H bias (EMA50 + confirmed-3/3-BOS agreement)
# --------------------------------------------------------------------------- #
def build_1h_bias(df1m: pd.DataFrame) -> dict:
    df = resample_causal(df1m, 60)
    c = df["Close"].to_numpy(float)
    n = len(df)
    ema = pd.Series(c).ewm(span=EMA_LEN, adjust=False).mean().to_numpy()

    swings = confirmed_swings(df, left=FRACTAL_L, right=FRACTAL_R)
    sh_at, sl_at = swings["sh_at"], swings["sl_at"]

    bos_dir = np.full(n, np.nan)
    for i in range(1, n):
        bull = np.isfinite(sh_at[i]) and c[i] > sh_at[i] and not (
            np.isfinite(sh_at[i - 1]) and c[i - 1] > sh_at[i - 1])
        bear = np.isfinite(sl_at[i]) and c[i] < sl_at[i] and not (
            np.isfinite(sl_at[i - 1]) and c[i - 1] < sl_at[i - 1])
        if bull:
            bos_dir[i] = 1
        elif bear:
            bos_dir[i] = -1
    bos_state = pd.Series(bos_dir).ffill().to_numpy()

    bias = np.zeros(n)  # 0 = NO BIAS
    long_ok = (c > ema) & (bos_state == 1)
    short_ok = (c < ema) & (bos_state == -1)
    bias[long_ok] = LONG
    bias[short_ok] = SHORT

    conf_ts = (df.index + pd.Timedelta(minutes=60))
    return dict(sig_index=df.index, conf_ts=conf_ts, conf_ns=conf_ts.asi8,
                bias=bias, ema=ema, bos_state=bos_state, close=c)


def bias_at(bias_ctx: dict, query_ts_ns: np.ndarray) -> np.ndarray:
    conf_ns = bias_ctx["conf_ns"]
    k = np.searchsorted(conf_ns, query_ts_ns, side="right") - 1
    out = np.zeros(len(query_ts_ns))
    ok = k >= 0
    out[ok] = bias_ctx["bias"][k[ok]]
    return out


# --------------------------------------------------------------------------- #
# Prior-RTH-session H/L pool (Condition 2 sweep pool + Condition 5 opposite-side
# target-liquidity pool, R4)
# --------------------------------------------------------------------------- #
def build_rth_daily(df1m: pd.DataFrame) -> dict:
    et = df1m.index.tz_convert(NY)
    minute_of_day = et.hour * 60 + et.minute
    rth_mask = (minute_of_day >= RTH_START_MIN) & (minute_of_day < RTH_END_MIN)
    date = et.normalize()
    sub_hi = df1m["High"].to_numpy(float)[rth_mask]
    sub_lo = df1m["Low"].to_numpy(float)[rth_mask]
    sub_date = date[rth_mask]
    g = pd.DataFrame({"date": sub_date, "hi": sub_hi, "lo": sub_lo}).groupby("date")
    rth_hi = g["hi"].max()
    rth_lo = g["lo"].min()
    days = rth_hi.index  # tz-aware ET midnight, ascending (groupby sorts)
    known_ts = (days + pd.Timedelta(hours=16, minutes=0)).tz_convert("UTC")
    return dict(days=days, known_ts=known_ts, known_ns=known_ts.asi8,
                hi=rth_hi.to_numpy(float), lo=rth_lo.to_numpy(float))


def prior_rth_extreme_at(rth: dict, query_ts_ns: np.ndarray):
    k = np.searchsorted(rth["known_ns"], query_ts_ns, side="right") - 1
    hi = np.full(len(query_ts_ns), np.nan)
    lo = np.full(len(query_ts_ns), np.nan)
    ok = k >= 0
    hi[ok] = rth["hi"][k[ok]]
    lo[ok] = rth["lo"][k[ok]]
    return hi, lo


# --------------------------------------------------------------------------- #
# Condition 2 (15m sweep) + Condition 3 (15m FVG + displacement) + candidate build
# --------------------------------------------------------------------------- #
def build_15m_context(df1m: pd.DataFrame) -> dict:
    df = resample_causal(df1m, 15)
    h, l, c = (df["High"].to_numpy(float), df["Low"].to_numpy(float), df["Close"].to_numpy(float))
    atr = wilder_atr(h, l, c, ATR_LEN)
    swings = confirmed_swings(df, left=FRACTAL_L, right=FRACTAL_R)
    fv = fvgs_causal(df, atr, GAP_ATR_FLOOR)
    is_disp, ddir = displacement_strength(df, lookback=DISP_LOOKBACK, mult=DISP_MULT)

    conf_ts = df.index + pd.Timedelta(minutes=15)
    if len(fv):
        fv = fv.copy()
        fv["conf_ts"] = conf_ts[fv["idx"].to_numpy(int)]
        # displacement gate on candle-2 (idx-1), direction-matched
        keep = []
        for r in fv.itertuples(index=False):
            j = int(r.idx) - 1
            if j < 0 or not is_disp[j]:
                keep.append(False)
                continue
            if r.direction > 0:
                keep.append(bool(ddir[j] == 1))
            else:
                keep.append(bool(ddir[j] == -1))
        fv = fv[np.array(keep)].reset_index(drop=True)

    sh_idx, sh_price = swings["sh_events"]
    sl_idx, sl_price = swings["sl_events"]
    sh_ts = (conf_ts[sh_idx].asi8) if len(sh_idx) else np.array([], dtype=np.int64)
    sl_ts = (conf_ts[sl_idx].asi8) if len(sl_idx) else np.array([], dtype=np.int64)

    atr_ts = conf_ts.asi8

    return dict(df=df, atr=atr, swings=swings, fv=fv, is_disp=is_disp, ddir=ddir,
                sig_index=df.index, conf_ts=conf_ts, conf_ns=conf_ts.asi8,
                sh_ts=sh_ts, sh_price=np.asarray(sh_price, float),
                sl_ts=sl_ts, sl_price=np.asarray(sl_price, float),
                atr_ts=atr_ts, atr_vals=atr)


def detect_sweeps(ctx15: dict, bias_ctx: dict, rth: dict) -> pd.DataFrame:
    """Condition 2, single-bar wick-beyond + same-bar-close-inside reclaim, gated by
    Condition-1 bias (LONG bias -> sweep of prior-session LOW; SHORT -> prior-session HIGH)."""
    df = ctx15["df"]
    h, l, c = (df["High"].to_numpy(float), df["Low"].to_numpy(float), df["Close"].to_numpy(float))
    n = len(df)
    open_ns = df.index.asi8
    conf_ns = ctx15["conf_ns"]
    b = bias_at(bias_ctx, conf_ns)  # bias known as of this bar's own close (R2)

    pool_hi, pool_lo = prior_rth_extreme_at(rth, open_ns)

    low_sweep = (b == LONG) & np.isfinite(pool_lo) & (l < pool_lo - TICK) & (c >= pool_lo)
    high_sweep = (b == SHORT) & np.isfinite(pool_hi) & (h > pool_hi + TICK) & (c <= pool_hi)

    rows = []
    for i in np.where(low_sweep)[0]:
        rows.append(dict(idx=i, direction=LONG, extreme=float(l[i]), conf_ts=ctx15["conf_ts"][i]))
    for i in np.where(high_sweep)[0]:
        rows.append(dict(idx=i, direction=SHORT, extreme=float(h[i]), conf_ts=ctx15["conf_ts"][i]))
    out = pd.DataFrame(rows, columns=["idx", "direction", "extreme", "conf_ts"])
    return out.sort_values("idx").reset_index(drop=True)


def build_candidates(ctx15: dict, bias_ctx: dict, sweeps: pd.DataFrame) -> pd.DataFrame:
    """Condition 2 sweep -> Condition 3 FVG within the 8-bar arm window (R3), bias
    re-checked at the FVG's own candle-3 close (R2) -> Condition 4 candidate limit order."""
    fv = ctx15["fv"]
    n15 = len(ctx15["df"])
    if not len(sweeps) or not len(fv):
        return pd.DataFrame(columns=CAND_COLS)

    fv_by_dir = {LONG: fv[fv["direction"] > 0].sort_values("idx"),
                 SHORT: fv[fv["direction"] < 0].sort_values("idx")}
    fv_idx_by_dir = {d: fv_by_dir[d]["idx"].to_numpy(int) for d in (LONG, SHORT)}

    rows = []
    for s in sweeps.itertuples(index=False):
        d = s.direction
        lo_win = s.idx + 1
        hi_win = min(s.idx + ARM_BARS, n15 - 1)
        if lo_win > hi_win:
            continue
        idx_arr = fv_idx_by_dir[d]
        lo_pos = np.searchsorted(idx_arr, lo_win, side="left")
        hi_pos = np.searchsorted(idx_arr, hi_win, side="right")
        if hi_pos <= lo_pos:
            continue
        arm_end_ns = int(ctx15["conf_ns"][hi_win])
        cand_fvs = fv_by_dir[d].iloc[lo_pos:hi_pos]
        for f in cand_fvs.itertuples(index=False):
            fvg_conf_ts = f.conf_ts
            fvg_conf_ns = fvg_conf_ts.value
            b_at_fvg = bias_at(bias_ctx, np.array([fvg_conf_ns]))[0]
            if b_at_fvg != d:
                continue  # R2 — bias re-checked at FVG confirmation
            if d == LONG:
                proximal, distal = f.top, f.bottom       # candle-3 edge / candle-1 edge (R1)
            else:
                proximal, distal = f.bottom, f.top
            stop = s.extreme - TICK if d == LONG else s.extreme + TICK
            if d == LONG and not (stop < proximal):
                continue
            if d == SHORT and not (stop > proximal):
                continue
            rows.append(dict(
                direction=d, mode="limit", entry_price=float(proximal), stop_price=float(stop),
                invalidate_price=float(distal), zone_lo=float(f.bottom), zone_hi=float(f.top),
                conf_ts=fvg_conf_ts, order_end_ns=arm_end_ns, sweep_ts=s.conf_ts,
                sweep_extreme=float(s.extreme), fvg_idx=int(f.idx), sweep_idx=int(s.idx),
            ))
    out = pd.DataFrame(rows, columns=CAND_COLS)
    if len(out):
        out = out.sort_values("conf_ts").reset_index(drop=True)
    return out


# --------------------------------------------------------------------------- #
# Condition 5 target pool — confirmed 15m opposing swing + prior-session opposite
# extreme (R4), merged into one searchable pool per direction (reuses
# survey_engine._nearest_target unchanged by feeding it an augmented ctx).
# --------------------------------------------------------------------------- #
def build_target_ctx(ctx15: dict, rth: dict) -> dict:
    sh_ts = np.concatenate([ctx15["sh_ts"], rth["known_ns"]])
    sh_price = np.concatenate([ctx15["sh_price"], rth["hi"]])
    sl_ts = np.concatenate([ctx15["sl_ts"], rth["known_ns"]])
    sl_price = np.concatenate([ctx15["sl_price"], rth["lo"]])

    def _sort(ts, price):
        order = np.argsort(ts, kind="stable")
        return ts[order], price[order]

    sh_ts, sh_price = _sort(sh_ts, sh_price)
    sl_ts, sl_price = _sort(sl_ts, sl_price)
    return dict(sh_ts=sh_ts, sh_price=sh_price, sl_ts=sl_ts, sl_price=sl_price,
                atr_ts=ctx15["atr_ts"], atr_vals=ctx15["atr_vals"])


# --------------------------------------------------------------------------- #
# The 1m walker — adapted copy of survey_engine.run_cell (see module docstring).
# --------------------------------------------------------------------------- #
def run_chain(df1m_arrays: dict, target_ctx: dict, candidates: pd.DataFrame,
              window_start: pd.Timestamp, window_end: pd.Timestamp) -> pd.DataFrame:
    ts_ns = df1m_arrays["ts_ns"]
    Low, High, Close = df1m_arrays["Low"], df1m_arrays["High"], df1m_arrays["Close"]
    n1m = len(ts_ns)
    if not len(candidates):
        return _empty_trades()
    sub = candidates[(candidates["conf_ts"] >= window_start) & (candidates["conf_ts"] < window_end)]
    sub = sub.sort_values("conf_ts")
    if not len(sub):
        return _empty_trades()

    trades = []
    in_pos_until_ns = -1
    for r in sub.itertuples(index=False):
        conf_ts = r.conf_ts
        conf_ns = conf_ts.value
        if conf_ns < in_pos_until_ns:
            continue  # dropped: in-position (one position at a time, both directions)
        direction = r.direction
        eod_cut = exch_day_cutoff(conf_ts)
        eod_ns = eod_cut.value
        order_end_ns = min(int(r.order_end_ns), eod_ns)

        i0 = np.searchsorted(ts_ns, conf_ns, side="left")
        i1 = np.searchsorted(ts_ns, order_end_ns, side="left")
        if i1 <= i0 or i0 >= n1m:
            continue
        lo_w, hi_w = Low[i0:i1], High[i0:i1]
        entry_touch = (lo_w <= r.entry_price) & (hi_w >= r.entry_price)
        if direction == LONG:
            inv_touch = lo_w <= r.invalidate_price
        else:
            inv_touch = hi_w >= r.invalidate_price
        e_hit = np.argmax(entry_touch) if entry_touch.any() else None
        v_hit = np.argmax(inv_touch) if inv_touch.any() else None
        if e_hit is None:
            continue  # cancelled: never filled within the working-order window
        if v_hit is not None and v_hit < e_hit:
            continue  # legit cancel: distal fully-filled-through strictly before fill (R4)
        if v_hit is not None and v_hit == e_hit:
            # same 1m bar touches both entry and the structural stop -> filled-then-stopped
            # (survey-bug convention, PREREG_CHAIN.md Fills section; loss booked, never cancelled)
            fill_i = i0 + int(e_hit)
            entry_ref = r.entry_price
            risk = abs(entry_ref - r.stop_price)
            if not np.isfinite(risk) or risk <= 0:
                continue
            net_dollars, R, e_fill, x_fill = finish(direction, entry_ref, r.stop_price, risk)
            exit_i = fill_i
            exit_ns = int(ts_ns[exit_i]) + 60_000_000_000
            trades.append(dict(
                direction=direction, conf_ts=conf_ts, fill_ts=pd.Timestamp(int(ts_ns[fill_i]), tz="UTC"),
                exit_ts=pd.Timestamp(exit_ns, tz="UTC"), entry_ref=entry_ref, stop=r.stop_price,
                target=np.nan, risk_pts=risk, reason="stop_samebar", R=R, net_dollars=net_dollars,
                sweep_ts=r.sweep_ts, sweep_extreme=r.sweep_extreme,
            ))
            in_pos_until_ns = exit_ns
            continue
        fill_i = i0 + int(e_hit)
        entry_ref = r.entry_price

        fill_ns = int(ts_ns[fill_i])
        risk = abs(entry_ref - r.stop_price)
        if not np.isfinite(risk) or risk <= 0:
            continue

        atr_val = _atr_at(target_ctx, fill_ns)
        target = _nearest_target(direction, entry_ref, atr_val, target_ctx, fill_ns)
        if target is None:
            target = entry_ref + FALLBACK_R * risk * direction

        scan_start = fill_i + 1
        eod_i = np.searchsorted(ts_ns, eod_ns, side="left") - 1
        if eod_i < scan_start:
            eod_i = scan_start
        if eod_i >= n1m:
            eod_i = n1m - 1
        if scan_start > eod_i:
            continue

        lo_w = Low[scan_start:eod_i + 1]
        hi_w = High[scan_start:eod_i + 1]
        if direction == LONG:
            s_mask = lo_w <= r.stop_price
            t_mask = hi_w >= target
        else:
            s_mask = hi_w >= r.stop_price
            t_mask = lo_w <= target
        s_rel = int(np.argmax(s_mask)) if s_mask.any() else None
        t_rel = int(np.argmax(t_mask)) if t_mask.any() else None
        if s_rel is not None and (t_rel is None or s_rel <= t_rel):
            exit_level = r.stop_price
            exit_i = scan_start + s_rel
            reason = "stop"
        elif t_rel is not None:
            exit_level = target
            exit_i = scan_start + t_rel
            reason = "target"
        else:
            exit_level = Close[eod_i]
            exit_i = eod_i
            reason = "eod"

        net_dollars, R, e_fill, x_fill = finish(direction, entry_ref, exit_level, risk)
        exit_ns = int(ts_ns[exit_i]) + 60_000_000_000
        trades.append(dict(
            direction=direction, conf_ts=conf_ts, fill_ts=pd.Timestamp(fill_ns, tz="UTC"),
            exit_ts=pd.Timestamp(exit_ns, tz="UTC"), entry_ref=entry_ref, stop=r.stop_price,
            target=target, risk_pts=risk, reason=reason, R=R, net_dollars=net_dollars,
            sweep_ts=r.sweep_ts, sweep_extreme=r.sweep_extreme,
        ))
        in_pos_until_ns = exit_ns

    return pd.DataFrame(trades) if trades else _empty_trades()


def _empty_trades():
    return pd.DataFrame(columns=["direction", "conf_ts", "fill_ts", "exit_ts", "entry_ref",
                                  "stop", "target", "risk_pts", "reason", "R", "net_dollars",
                                  "sweep_ts", "sweep_extreme"])


def df1m_to_arrays(df1m: pd.DataFrame) -> dict:
    return dict(ts_ns=df1m.index.asi8,
                Open=df1m["Open"].to_numpy(float), High=df1m["High"].to_numpy(float),
                Low=df1m["Low"].to_numpy(float), Close=df1m["Close"].to_numpy(float),
                eod_ns=build_eod_cutoff_array(df1m.index))


def cell_stats(trades: pd.DataFrame) -> dict:
    n = len(trades)
    if n == 0:
        return dict(n=0, wr=None, pf=None, totR=0.0, expectancy=None, avgW=None, avgL=None)
    Rs = trades["R"].to_numpy(float)
    wins = Rs[Rs > 0]
    losses = Rs[Rs < 0]
    wr = float((Rs > 0).mean())
    win_sum = float(wins.sum())
    loss_sum = float(-losses.sum())
    pf = (win_sum / loss_sum) if loss_sum > 0 else (float("inf") if win_sum > 0 else None)
    return dict(n=n, wr=round(wr, 4), pf=(round(pf, 4) if pf not in (None, float("inf")) else pf),
                totR=round(float(Rs.sum()), 4), expectancy=round(float(Rs.mean()), 4),
                avgW=round(float(wins.mean()), 4) if wins.size else None,
                avgL=round(float(losses.mean()), 4) if losses.size else None)


# --------------------------------------------------------------------------- #
# Full pipeline
# --------------------------------------------------------------------------- #
def build_all(df1m: pd.DataFrame) -> dict:
    bias_ctx = build_1h_bias(df1m)
    rth = build_rth_daily(df1m)
    ctx15 = build_15m_context(df1m)
    sweeps = detect_sweeps(ctx15, bias_ctx, rth)
    candidates = build_candidates(ctx15, bias_ctx, sweeps)
    target_ctx = build_target_ctx(ctx15, rth)
    return dict(bias_ctx=bias_ctx, rth=rth, ctx15=ctx15, sweeps=sweeps,
                candidates=candidates, target_ctx=target_ctx)


if __name__ == "__main__":
    df1m = load_1m()
    df1m = df1m.loc[BUFFER_START:WINDOW_END]
    all_ctx = build_all(df1m)
    print("sweeps:", len(all_ctx["sweeps"]), "candidates:", len(all_ctx["candidates"]))
    arrs = df1m_to_arrays(df1m)
    tr = run_chain(arrs, all_ctx["target_ctx"], all_ctx["candidates"], WINDOW_START, WINDOW_END)
    print("trades:", len(tr))
    print(cell_stats(tr))
