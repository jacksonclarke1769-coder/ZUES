"""
Fill engine — PREREG §3. Reuses zeus-occ-optimize/engine.py conventions:
first-touch on 1m, stop-fills-first-on-tie, $1 round-turn, 1-tick adverse slip
both sides, one position at a time per cell (signals dropped while in-position).

Window boundaries (TRAIN/HOLDOUT/quarters) are UTC calendar timestamps matching
the data's own UTC index (PREREG does not specify a tz for the split boundaries;
literal resolution, documented in the report).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import (TICK, ATR_LEN, LIMIT_LIFETIME_BARS, LONG, SHORT,
                     resample_causal, confirmed_swings, wilder_atr, displacement_strength,
                     fvgs_causal, exch_day_cutoff, build_eod_cutoff_array, finish, GAP_ATR_FLOOR)
from detectors import CONCEPTS

WINDOW_START = pd.Timestamp("2024-06-22", tz="UTC")
SPLIT_TS = pd.Timestamp("2025-06-22", tz="UTC")
WINDOW_END = pd.Timestamp("2026-06-22", tz="UTC")
BUFFER_START = pd.Timestamp("2024-01-01", tz="UTC")   # warmup lookback, not scored


def idx_to_ts(sig_index: pd.DatetimeIndex, tf_min: int, idx) -> pd.DatetimeIndex:
    return sig_index[idx] + pd.Timedelta(minutes=tf_min)


def build_tf_context(df1m: pd.DataFrame, tf_min: int) -> dict:
    df = resample_causal(df1m.loc[BUFFER_START:WINDOW_END], tf_min)
    o, h, l, c = (df["Open"].to_numpy(float), df["High"].to_numpy(float),
                  df["Low"].to_numpy(float), df["Close"].to_numpy(float))
    atr = wilder_atr(h, l, c, ATR_LEN)
    swings = confirmed_swings(df)
    disp = displacement_strength(df)
    fv = fvgs_causal(df, atr, GAP_ATR_FLOOR)

    sig_index = df.index
    cand = {}
    for name, fn in CONCEPTS.items():
        if name in ("FVG", "IFVG"):
            out = fn(df, atr, swings, disp, fv_cache=fv)
            if isinstance(out, tuple):
                out = out[0]
        elif name in ("OB", "Breaker"):
            out = fn(df, atr, swings, disp, disp_cache=disp)
        else:
            out = fn(df, atr, swings, disp)
        if len(out):
            out = out.copy()
            out["conf_ts"] = idx_to_ts(sig_index, tf_min, out["idx"].astype(int).to_numpy())
            out = out.sort_values("conf_ts").reset_index(drop=True)
        cand[name] = out

    sh_idx, sh_price = swings["sh_events"]
    sl_idx, sl_price = swings["sl_events"]
    sh_ts = idx_to_ts(sig_index, tf_min, sh_idx).asi8 if len(sh_idx) else np.array([], dtype=np.int64)
    sl_ts = idx_to_ts(sig_index, tf_min, sl_idx).asi8 if len(sl_idx) else np.array([], dtype=np.int64)

    # signal-TF ATR lookup by timestamp (nearest known bar close <= query ts)
    atr_ts = (sig_index + pd.Timedelta(minutes=tf_min)).asi8

    return dict(df=df, atr=atr, swings=swings, disp=disp, fv=fv, candidates=cand,
                sh_ts=sh_ts, sh_price=np.asarray(sh_price, float),
                sl_ts=sl_ts, sl_price=np.asarray(sl_price, float),
                atr_ts=atr_ts, atr_vals=atr, tf_min=tf_min)


def _nearest_target(direction, entry, atr_val, ctx, fill_ts_ns):
    if not np.isfinite(atr_val) or atr_val <= 0:
        return None
    if direction == LONG:
        k = np.searchsorted(ctx["sh_ts"], fill_ts_ns, side="right")
        sub = ctx["sh_price"][:k]
        floor = entry + atr_val
        elig = sub[sub >= floor]
        if elig.size:
            return float(elig.min())
        return None
    else:
        k = np.searchsorted(ctx["sl_ts"], fill_ts_ns, side="right")
        sub = ctx["sl_price"][:k]
        floor = entry - atr_val
        elig = sub[sub <= floor]
        if elig.size:
            return float(elig.max())
        return None


def _atr_at(ctx, ts_ns):
    k = np.searchsorted(ctx["atr_ts"], ts_ns, side="right") - 1
    if k < 0:
        return np.nan
    return ctx["atr_vals"][k]


def run_cell(df1m_arrays: dict, ctx: dict, concept: str, direction: int,
             window_start: pd.Timestamp, window_end: pd.Timestamp) -> pd.DataFrame:
    """Walk one (concept, tf, direction) cell over [window_start, window_end)."""
    cand = ctx["candidates"].get(concept)
    tf_min = ctx["tf_min"]
    ts_ns = df1m_arrays["ts_ns"]
    Open, High, Low, Close = (df1m_arrays["Open"], df1m_arrays["High"],
                               df1m_arrays["Low"], df1m_arrays["Close"])
    n1m = len(ts_ns)
    if cand is None or not len(cand):
        return _empty_trades()
    sub = cand[(cand["direction"] == direction) & (cand["conf_ts"] >= window_start) &
               (cand["conf_ts"] < window_end)]
    if not len(sub):
        return _empty_trades()

    trades = []
    in_pos_until_ns = -1
    for r in sub.itertuples(index=False):
        conf_ts = r.conf_ts
        conf_ns = conf_ts.value
        if conf_ns < in_pos_until_ns:
            continue   # dropped: in-position
        eod_cut = exch_day_cutoff(conf_ts)
        eod_ns = eod_cut.value

        if r.mode == "limit":
            lifetime_end = conf_ts + pd.Timedelta(minutes=tf_min * LIMIT_LIFETIME_BARS)
            order_end_ns = min(lifetime_end.value, eod_ns)
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
                continue   # cancelled: never filled within the working-order window
            if v_hit is not None and v_hit < e_hit:
                continue   # legit cancel: invalidated on a STRICTLY earlier bar than the fill
            if v_hit is not None and v_hit == e_hit:
                # SAME 1m bar touches both entry and invalidation: intrabar order is
                # unknowable -- conservative "stop-fills-first on ambiguous bars" (PREREG
                # §3) convention extended to this case: the resting limit DID fill at
                # entry_price (it was touched), and is immediately stopped out on that
                # same bar (worst case). This is a real stop-loss trade, not a cancel --
                # excluding it was a same-bar fill/invalidation selection-bias bug
                # (audited 2026-07-20; see report v2 correction notice).
                fill_i = i0 + int(e_hit)
                entry_ref = r.entry_price
                risk = abs(entry_ref - r.stop_price)
                if not np.isfinite(risk) or risk <= 0:
                    continue
                atr_val = _atr_at(ctx, int(ts_ns[fill_i]))
                target_sb = _nearest_target(direction, entry_ref, atr_val, ctx, int(ts_ns[fill_i]))
                if target_sb is None:
                    target_sb = entry_ref + 2.0 * risk * direction
                net_dollars, R, e_fill, x_fill = finish(direction, entry_ref, r.stop_price, risk)
                exit_i = fill_i
                exit_ns = int(ts_ns[exit_i]) + 60_000_000_000
                trades.append(dict(
                    concept=concept, direction=direction, conf_ts=conf_ts,
                    fill_ts=pd.Timestamp(int(ts_ns[fill_i]), tz="UTC"),
                    exit_ts=pd.Timestamp(exit_ns, tz="UTC"),
                    entry_ref=entry_ref, stop=r.stop_price, target=target_sb, risk_pts=risk,
                    reason="stop_samebar", R=R, net_dollars=net_dollars, mode=r.mode,
                ))
                in_pos_until_ns = exit_ns
                continue
            fill_i = i0 + int(e_hit)
            entry_ref = r.entry_price
        else:  # market
            fill_i = np.searchsorted(ts_ns, conf_ns, side="left")
            if fill_i >= n1m:
                continue
            entry_ref = r.entry_price

        fill_ns = int(ts_ns[fill_i])
        risk = abs(entry_ref - r.stop_price)
        if not np.isfinite(risk) or risk <= 0:
            continue

        atr_val = _atr_at(ctx, fill_ns)
        target = _nearest_target(direction, entry_ref, atr_val, ctx, fill_ns)
        if target is None:
            target = entry_ref + 2.0 * risk * direction

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
            concept=concept, direction=direction, conf_ts=conf_ts,
            fill_ts=pd.Timestamp(fill_ns, tz="UTC"), exit_ts=pd.Timestamp(exit_ns, tz="UTC"),
            entry_ref=entry_ref, stop=r.stop_price, target=target, risk_pts=risk,
            reason=reason, R=R, net_dollars=net_dollars, mode=r.mode,
        ))
        in_pos_until_ns = exit_ns

    return pd.DataFrame(trades) if trades else _empty_trades()


def _empty_trades():
    return pd.DataFrame(columns=["concept", "direction", "conf_ts", "fill_ts", "exit_ts",
                                  "entry_ref", "stop", "target", "risk_pts", "reason", "R",
                                  "net_dollars", "mode"])


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
