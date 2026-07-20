"""
STEP 3(a) NULL — randomized-entry test (gates.py methodology, adapted). Same number of
entries as the real holdout chain, drawn from the same bias/session-eligible 1m bars
(eligible = bars where the 1H bias — Condition 1 — equals the entry's own direction,
i.e. the population the chain could have possibly fired from), same stop-distance
distribution (pooled risk_pts from the real holdout trades, drawn with replacement),
same target rule (nearest opposite liquidity >=1xATR(15m) else 2R fallback) and costs
($1 round-turn, 1-tick slip via common.finish). One position at a time, EOD flat 16:55 ET,
across BOTH directions combined (matching this chain's own walker semantics). 1,000 runs;
real total R compared to the null 95th percentile.

"Session-eligible": no additional session-hours restriction is applied beyond the bias gate
itself — the chain has no stated trading-hours restriction besides the global EOD-flat, and
sweeps/FVGs may form at any hour (documented resolution, matches chain.py's own detectors,
which impose no time-of-day filter beyond EOD).
"""
import numpy as np
import pandas as pd

from chain import LONG, SHORT, exch_day_cutoff, finish, bias_at
from survey_engine import _nearest_target, _atr_at


def eligible_bars_by_direction(bias_ctx: dict, ts_ns: np.ndarray, window_start_ns: int,
                                window_end_ns: int) -> dict:
    lo = np.searchsorted(ts_ns, window_start_ns, side="left")
    hi = np.searchsorted(ts_ns, window_end_ns, side="left")
    idx = np.arange(lo, hi)
    b = bias_at(bias_ctx, ts_ns[idx])
    return {LONG: idx[b == LONG], SHORT: idx[b == SHORT]}


def simulate_null_run(arrs, target_ctx, eligible: dict, directions: np.ndarray,
                       stop_pool: np.ndarray, rng: np.random.Generator) -> float:
    ts_ns = arrs["ts_ns"]; Low = arrs["Low"]; High = arrs["High"]; Close = arrs["Close"]
    eod_ns_arr = arrs["eod_ns"]
    n1m = len(ts_ns)

    draw_bar = np.empty(len(directions), dtype=np.int64)
    for k, d in enumerate(directions):
        pool = eligible[d]
        draw_bar[k] = rng.choice(pool) if len(pool) else -1
    stop_dists = rng.choice(stop_pool, size=len(directions), replace=True)

    order = np.argsort(draw_bar, kind="stable")
    total_R = 0.0
    in_pos_until_ns = -1
    for k in order:
        i = int(draw_bar[k])
        if i < 0:
            continue
        entry_ns = int(ts_ns[i])
        if entry_ns < in_pos_until_ns:
            continue
        direction = int(directions[k])
        entry_ref = float(Close[i])
        risk = float(stop_dists[k])
        if risk <= 0:
            continue
        stop_price = entry_ref - risk * direction
        eod_ns = int(eod_ns_arr[i])

        atr_val = _atr_at(target_ctx, entry_ns)
        target = _nearest_target(direction, entry_ref, atr_val, target_ctx, entry_ns)
        if target is None:
            target = entry_ref + 2.0 * risk * direction

        scan_start = i + 1
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
            s_mask = lo_w <= stop_price
            t_mask = hi_w >= target
        else:
            s_mask = hi_w >= stop_price
            t_mask = lo_w <= target
        s_rel = int(np.argmax(s_mask)) if s_mask.any() else None
        t_rel = int(np.argmax(t_mask)) if t_mask.any() else None
        if s_rel is not None and (t_rel is None or s_rel <= t_rel):
            exit_level = stop_price
            exit_i = scan_start + s_rel
        elif t_rel is not None:
            exit_level = target
            exit_i = scan_start + t_rel
        else:
            exit_level = float(Close[eod_i])
            exit_i = eod_i

        net_dollars, R, e_fill, x_fill = finish(direction, entry_ref, exit_level, risk)
        total_R += R
        in_pos_until_ns = int(ts_ns[exit_i]) + 60_000_000_000
    return total_R


def run_null_test(arrs, target_ctx, bias_ctx, trades: pd.DataFrame,
                   window_start: pd.Timestamp, window_end: pd.Timestamp,
                   n_runs=1000, seed=20260720) -> dict:
    n_draws = len(trades)
    if n_draws == 0:
        return dict(n_runs=n_runs, n_draws=0, note="no real trades in window; null test not meaningful")
    directions = trades["direction"].to_numpy(int)
    stop_pool = trades["risk_pts"].to_numpy(float)
    real_totR = float(trades["R"].sum())

    eligible = eligible_bars_by_direction(bias_ctx, arrs["ts_ns"], window_start.value, window_end.value)
    rng = np.random.default_rng(seed)
    null_totals = np.empty(n_runs)
    for r in range(n_runs):
        null_totals[r] = simulate_null_run(arrs, target_ctx, eligible, directions, stop_pool, rng)
    p95 = float(np.percentile(null_totals, 95))
    return dict(n_runs=n_runs, n_draws=n_draws,
                n_eligible_long=int(len(eligible[LONG])), n_eligible_short=int(len(eligible[SHORT])),
                null_p95=round(p95, 4), null_mean=round(float(null_totals.mean()), 4),
                null_median=round(float(np.median(null_totals)), 4),
                real_totR=round(real_totR, 4), beats_null_95=bool(real_totR > p95),
                pctile_of_real_in_null=float((null_totals < real_totR).mean()))
