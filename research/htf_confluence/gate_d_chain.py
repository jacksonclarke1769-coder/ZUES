"""
Live-achievable (Gate D / freshness-gated) re-walk for the HTF confluence chain — adapted
from backtests/zeus-ict-2026-07/concept_survey/gate_d.py (fill_verify.py-style methodology,
PREREG_CHAIN.md / task Step 2). Same two channels as the certified methodology:
  - certified_gate literal 10-min staleness test on the historical fill instant.
  - full re-walk: bot polls at 5m bar closes (poll_ts = first 5m boundary >= conf_ts); a
    resting limit's fill-search window starts at poll_ts (not conf_ts); its END is
    unchanged (the original order_end_ns, anchored to the arm window / EOD).
"""
import numpy as np
import pandas as pd

from chain import LONG, SHORT, exch_day_cutoff, finish
from survey_engine import _nearest_target, _atr_at  # certified helpers, reused


def ceil_5m(ts: pd.Timestamp) -> pd.Timestamp:
    floored = ts.floor("5min")
    return floored if floored == ts else floored + pd.Timedelta(minutes=5)


def live_walk_one(row, target_ctx, arrs):
    ts_ns = arrs["ts_ns"]; Low = arrs["Low"]; High = arrs["High"]; Close = arrs["Close"]
    n1m = len(ts_ns)
    conf_ts = pd.Timestamp(row["conf_ts"])
    fill_ts_hist = pd.Timestamp(row["fill_ts"])
    direction = int(row["direction"])
    poll_ts = ceil_5m(conf_ts)
    poll_ns = poll_ts.value

    earliest_poll_for_fill = ceil_5m(fill_ts_hist)
    staleness_min = (earliest_poll_for_fill - fill_ts_hist).total_seconds() / 60.0
    certified_stale = staleness_min > 10.0

    eod_cut = exch_day_cutoff(conf_ts)
    eod_ns = eod_cut.value
    order_end_ns = min(int(row["order_end_ns"]), eod_ns)

    i0 = np.searchsorted(ts_ns, poll_ns, side="left")
    i1 = np.searchsorted(ts_ns, order_end_ns, side="left")
    if i1 <= i0 or i0 >= n1m:
        return dict(achievable=False, reason="poll_after_order_end",
                    certified_stale=certified_stale, staleness_min=staleness_min)
    entry_price = row["entry_ref"]
    invalidate_price = row["_invalidate_price"]
    lo_w, hi_w = Low[i0:i1], High[i0:i1]
    entry_touch = (lo_w <= entry_price) & (hi_w >= entry_price)
    if direction == LONG:
        inv_touch = lo_w <= invalidate_price
    else:
        inv_touch = hi_w >= invalidate_price
    e_hit = np.argmax(entry_touch) if entry_touch.any() else None
    v_hit = np.argmax(inv_touch) if inv_touch.any() else None
    if v_hit is not None and (e_hit is None or v_hit <= e_hit):
        return dict(achievable=False, reason="invalidated_before_or_with_fill",
                    certified_stale=certified_stale, staleness_min=staleness_min)
    if e_hit is None:
        return dict(achievable=False, reason="never_filled_in_window",
                    certified_stale=certified_stale, staleness_min=staleness_min)
    fill_i = i0 + int(e_hit)
    entry_ref = entry_price

    fill_ns = int(ts_ns[fill_i])
    stop_price = row["stop"]
    risk = abs(entry_ref - stop_price)
    if not np.isfinite(risk) or risk <= 0:
        return dict(achievable=False, reason="degenerate_risk", certified_stale=certified_stale,
                    staleness_min=staleness_min)

    atr_val = _atr_at(target_ctx, fill_ns)
    target = _nearest_target(direction, entry_ref, atr_val, target_ctx, fill_ns)
    if target is None:
        target = entry_ref + 2.0 * risk * direction

    scan_start = fill_i + 1
    eod_i = np.searchsorted(ts_ns, eod_ns, side="left") - 1
    if eod_i < scan_start:
        eod_i = scan_start
    if eod_i >= n1m:
        eod_i = n1m - 1
    if scan_start > eod_i:
        return dict(achievable=False, reason="no_scan_room", certified_stale=certified_stale,
                    staleness_min=staleness_min)
    lo_w2 = Low[scan_start:eod_i + 1]
    hi_w2 = High[scan_start:eod_i + 1]
    if direction == LONG:
        s_mask = lo_w2 <= stop_price
        t_mask = hi_w2 >= target
    else:
        s_mask = hi_w2 >= stop_price
        t_mask = lo_w2 <= target
    s_rel = int(np.argmax(s_mask)) if s_mask.any() else None
    t_rel = int(np.argmax(t_mask)) if t_mask.any() else None
    if s_rel is not None and (t_rel is None or s_rel <= t_rel):
        exit_level = stop_price
    elif t_rel is not None:
        exit_level = target
    else:
        exit_level = Close[eod_i]
    net_dollars, R, e_fill, x_fill = finish(direction, entry_ref, exit_level, risk)
    return dict(achievable=True, R=R, certified_stale=certified_stale, staleness_min=staleness_min,
                poll_delay_min=(poll_ts - conf_ts).total_seconds() / 60.0)


def run_gate_d_chain(trades: pd.DataFrame, candidates: pd.DataFrame, target_ctx: dict, arrs: dict) -> dict:
    if not len(trades):
        return dict(n_original=0, n_live_achievable=0)
    cmap = {}
    for r in candidates.itertuples(index=False):
        cmap.setdefault(r.conf_ts, r)

    results = []
    R_orig_sum_abs = 0.0
    for _, row in trades.iterrows():
        c = cmap.get(row["conf_ts"])
        row2 = dict(row)
        row2["_invalidate_price"] = c.invalidate_price if c is not None else row["stop"]
        row2["order_end_ns"] = int(c.order_end_ns) if c is not None else row["exit_ts"].value
        res = live_walk_one(row2, target_ctx, arrs)
        res["R_orig"] = row["R"]
        R_orig_sum_abs += abs(row["R"])
        results.append(res)

    achievable = [r for r in results if r["achievable"]]
    suppressed = [r for r in results if not r["achievable"]]
    Rs_live = np.array([r["R"] for r in achievable]) if achievable else np.array([])
    n = len(Rs_live)
    if n:
        wins = Rs_live[Rs_live > 0]; losses = Rs_live[Rs_live < 0]
        wr = float((Rs_live > 0).mean())
        pf = float(wins.sum() / (-losses.sum())) if losses.sum() < 0 else (float("inf") if wins.sum() > 0 else None)
        totR = float(Rs_live.sum())
        expectancy = float(Rs_live.mean())
    else:
        wr = pf = totR = expectancy = None

    supp_R_weighted = (sum(abs(r["R_orig"]) for r in suppressed) / R_orig_sum_abs) if R_orig_sum_abs > 0 else 0.0
    certified_stale_R_weighted = (sum(abs(r["R_orig"]) for r in results if r["certified_stale"]) / R_orig_sum_abs
                                   ) if R_orig_sum_abs > 0 else 0.0

    return dict(
        n_original=len(trades), n_live_achievable=n,
        live_wr=round(wr, 4) if wr is not None else None,
        live_pf=round(pf, 4) if (pf not in (None, float("inf"))) else pf,
        live_totR=round(totR, 4) if totR is not None else None,
        live_expectancy=round(expectancy, 4) if expectancy is not None else None,
        r_weighted_suppression_pct=round(supp_R_weighted * 100, 2),
        r_weighted_certified_gate_stale_pct=round(certified_stale_R_weighted * 100, 2),
        suppressed_reasons=[r["reason"] for r in suppressed],
        original_totR=round(float(trades["R"].sum()), 4),
    )
