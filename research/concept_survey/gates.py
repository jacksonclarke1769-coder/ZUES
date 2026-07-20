"""
Gates A/B/C (PREREG §4).

Gate B resolution (documented): the one-sided stationary-block-bootstrap p-value
is computed for ALL 36 cells (not just Gate-A survivors) and BH-FDR (q=0.10) is
applied across the full N=36 ladder — PREREG §4 Gate-B header and §5/§7 both say
"across all N=36 cells"; computing the correction over a pre-filtered subset
would defeat the purpose of an FDR control over the whole tested family. A cell
needs BOTH Gate A and Gate B to proceed to Gate C.

Gate C resolution (documented): "same number of entries" is read as the SAME
RAW CANDIDATE COUNT the real cell's detector produced pre-filter (not the
post-filter realized trade count), executed through the IDENTICAL
one-position-at-a-time execution template — this keeps the null's realized
trade count naturally comparable to the real cell's (rather than exactly
bit-equal, which would require ad hoc redraw-on-drop logic not specified in
PREREG). Entry price = random bar's Close (market-style probe, no zone
concept for a random null). Stop distance is drawn (with replacement) from the
real cell's own realized |entry-stop| distribution. Target = the same nearest-
opposite-swing->=1ATR-else-2R rule, using the SAME swing/ATR structure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from common import LONG, SHORT, TICK, exch_day_cutoff, finish
from survey_engine import _nearest_target, _atr_at

RNG_SEED = 20260720


def block_bootstrap_p(R: np.ndarray, block_len: int, B: int = 10000, seed: int = RNG_SEED,
                       chunk: int = 1000) -> float:
    n = len(R)
    if n == 0:
        return 1.0
    block_len = max(1, int(block_len))
    n_blocks = int(np.ceil(n / block_len))
    rng = np.random.default_rng(seed)
    means = np.empty(B, dtype=np.float64)
    done = 0
    while done < B:
        b = min(chunk, B - done)
        starts = rng.integers(0, n, size=(b, n_blocks), dtype=np.int64)
        offsets = np.arange(block_len, dtype=np.int64)
        idx = (starts[:, :, None] + offsets[None, None, :]) % n
        idx = idx.astype(np.int32).reshape(b, n_blocks * block_len)[:, :n]
        vals = R[idx]
        means[done:done + b] = vals.mean(axis=1)
        done += b
    p = float((means <= 0).mean())
    if p == 0.0:
        p = 1.0 / (B + 1)
    return p


def bh_fdr(pvals: dict, q: float = 0.10):
    """Benjamini-Hochberg. Returns (cutoff_p, dict cell->passed, ladder list)."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items)
    ladder = []
    thresh_idx = -1
    for rank, (cell, p) in enumerate(items, start=1):
        bh_thresh = (rank / m) * q
        passed_rank = p <= bh_thresh
        ladder.append(dict(cell=cell, p=p, rank=rank, bh_threshold=round(bh_thresh, 6),
                            passes_rank_threshold=passed_rank))
        if passed_rank:
            thresh_idx = rank
    cutoff_p = items[thresh_idx - 1][1] if thresh_idx > 0 else None
    passed = {cell: (cutoff_p is not None and p <= cutoff_p) for cell, p in items}
    return cutoff_p, passed, ladder


# --------------------------------------------------------------------------- #
# Gate C: randomized-entry null
# --------------------------------------------------------------------------- #
def _eligible_session_bars(ts_ns: np.ndarray, window_start_ns: int, window_end_ns: int) -> np.ndarray:
    lo = np.searchsorted(ts_ns, window_start_ns, side="left")
    hi = np.searchsorted(ts_ns, window_end_ns, side="left")
    return np.arange(lo, hi)


def simulate_null_run(arrs, ctx, direction, eligible_idx, n_draws, stop_pool, rng):
    """One null run: draw n_draws random entry bars, stop distances from stop_pool,
    identical target rule + OCO exit + one-position-at-a-time. Returns total R.
    `arrs` must include a precomputed 'eod_ns' array (build_eod_cutoff_array),
    aligned 1:1 with ts_ns, to avoid per-trade tz-aware Timestamp construction.
    Target search uses an incrementally-maintained SortedList (draw_bar is sorted
    ascending so fill order is time-monotonic within a run) instead of an O(k)
    linear filter per trade -- this is the dominant cost at 1000-run scale."""
    from sortedcontainers import SortedList
    ts_ns = arrs["ts_ns"]; Open = arrs["Open"]; High = arrs["High"]; Low = arrs["Low"]; Close = arrs["Close"]
    eod_ns_arr = arrs["eod_ns"]
    n1m = len(ts_ns)
    draw_bar = rng.choice(eligible_idx, size=n_draws, replace=True)
    draw_bar.sort()
    stop_dists = rng.choice(stop_pool, size=n_draws, replace=True)

    events_ts = ctx["sh_ts"] if direction == LONG else ctx["sl_ts"]
    events_price = ctx["sh_price"] if direction == LONG else ctx["sl_price"]
    ptr = 0
    n_events = len(events_ts)
    sl_prices = SortedList()

    total_R = 0.0
    in_pos_until_ns = -1
    for k in range(n_draws):
        i = int(draw_bar[k])
        entry_ns = int(ts_ns[i])
        if entry_ns < in_pos_until_ns:
            continue
        entry_ref = Close[i]
        risk = float(stop_dists[k])
        if not np.isfinite(risk) or risk <= 0:
            continue
        stop_price = entry_ref - risk * direction
        eod_ns = int(eod_ns_arr[i])

        while ptr < n_events and events_ts[ptr] <= entry_ns:
            sl_prices.add(float(events_price[ptr]))
            ptr += 1

        atr_val = _atr_at(ctx, entry_ns)
        target = None
        if np.isfinite(atr_val) and atr_val > 0:
            if direction == LONG:
                floor = entry_ref + atr_val
                pos = sl_prices.bisect_left(floor)
                if pos < len(sl_prices):
                    target = sl_prices[pos]
            else:
                floor = entry_ref - atr_val
                pos = sl_prices.bisect_right(floor)
                if pos > 0:
                    target = sl_prices[pos - 1]
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
            exit_level = Close[eod_i]
            exit_i = eod_i
        net_dollars, R, e_fill, x_fill = finish(direction, entry_ref, exit_level, risk)
        total_R += R
        in_pos_until_ns = int(ts_ns[exit_i]) + 60_000_000_000
    return total_R


def gate_c_null(arrs, ctx, direction, window_start, window_end, n_draws, stop_pool,
                 n_runs, real_totR, seed=RNG_SEED):
    ts_ns = arrs["ts_ns"]
    eligible = _eligible_session_bars(ts_ns, window_start.value, window_end.value)
    rng = np.random.default_rng(seed)
    null_totals = np.empty(n_runs)
    for r in range(n_runs):
        null_totals[r] = simulate_null_run(arrs, ctx, direction, eligible, n_draws, stop_pool, rng)
    p95 = float(np.percentile(null_totals, 95))
    return dict(n_runs=n_runs, n_draws=n_draws, null_p95=round(p95, 4),
                null_mean=round(float(null_totals.mean()), 4),
                null_median=round(float(np.median(null_totals)), 4),
                real_totR=round(real_totR, 4), beats_null_95=bool(real_totR > p95),
                null_totals=[round(float(x), 3) for x in null_totals])
