"""
Numba-jitted core for Gate C's randomized-entry null (same semantics as
gates.simulate_null_run, verified equivalent). Target search uses a point-set
segment tree over PRICE RANK (events inserted in TIME order as the run's query
clock advances; O(log n) leftmost/rightmost-set-bit-in-range queries) --
a plain O(n) linear scan per query was benchmarked and is too slow at
1000-run x large-n-cell scale (this is a straight speed fix, not a change to
the statistical procedure -- cross-checked bit-identical against the
pure-Python SortedList reference in run_gate_c.py before use).
"""
import numpy as np
from numba import njit

TICK = 0.25
POINT_VALUE = 20.0
COMMISSION_PER_SIDE = 0.50
SLIPPAGE_TICKS = 1.0


def next_pow2(n):
    p = 1
    while p < n:
        p *= 2
    return max(p, 1)


@njit(cache=True)
def _st_update(tree, tsize, pos):
    i = tsize + pos
    tree[i] = 1
    i //= 2
    while i >= 1:
        tree[i] = tree[2 * i] | tree[2 * i + 1]
        i //= 2


@njit(cache=True)
def _st_leftmost(tree, tsize, lo, hi):
    """Leftmost set leaf index in [lo,hi] (inclusive), -1 if none."""
    if lo > hi or lo < 0 or hi >= tsize:
        return -1
    stack = np.empty(64, dtype=np.int64)
    stack_lo = np.empty(64, dtype=np.int64)
    stack_hi = np.empty(64, dtype=np.int64)
    sp = 0
    stack[sp] = 1; stack_lo[sp] = 0; stack_hi[sp] = tsize - 1; sp += 1
    while sp > 0:
        sp -= 1
        node = stack[sp]; nlo = stack_lo[sp]; nhi = stack_hi[sp]
        if nhi < lo or nlo > hi or tree[node] == 0:
            continue
        if nlo == nhi:
            return nlo
        mid = (nlo + nhi) // 2
        # push right first so left is processed first (LIFO) -> leftmost found first
        stack[sp] = 2 * node + 1; stack_lo[sp] = mid + 1; stack_hi[sp] = nhi; sp += 1
        stack[sp] = 2 * node; stack_lo[sp] = nlo; stack_hi[sp] = mid; sp += 1
    return -1


@njit(cache=True)
def _st_rightmost(tree, tsize, lo, hi):
    """Rightmost set leaf index in [lo,hi] (inclusive), -1 if none."""
    if lo > hi or lo < 0 or hi >= tsize:
        return -1
    stack = np.empty(64, dtype=np.int64)
    stack_lo = np.empty(64, dtype=np.int64)
    stack_hi = np.empty(64, dtype=np.int64)
    sp = 0
    stack[sp] = 1; stack_lo[sp] = 0; stack_hi[sp] = tsize - 1; sp += 1
    while sp > 0:
        sp -= 1
        node = stack[sp]; nlo = stack_lo[sp]; nhi = stack_hi[sp]
        if nhi < lo or nlo > hi or tree[node] == 0:
            continue
        if nlo == nhi:
            return nlo
        mid = (nlo + nhi) // 2
        # push left first so right is processed first (LIFO) -> rightmost found first
        stack[sp] = 2 * node; stack_lo[sp] = nlo; stack_hi[sp] = mid; sp += 1
        stack[sp] = 2 * node + 1; stack_lo[sp] = mid + 1; stack_hi[sp] = nhi; sp += 1
    return -1


@njit(cache=True, fastmath=False)
def simulate_null_run_jit(ts_ns, Low, High, Close, eod_ns_arr,
                           atr_ts, atr_vals,
                           events_ts, events_rank, price_sorted, tsize,
                           direction, draw_bar, stop_dists, tree_buf):
    """events_ts: ascending event times. events_rank[k] = price-rank of the k-th
    (time-ordered) event, i.e. its position in `price_sorted` (ascending price).
    tree_buf: pre-zeroed uint8 array of length 2*tsize, reused per call (caller
    must zero it before each call -- avoids per-run allocation)."""
    n1m = ts_ns.shape[0]
    n_draws = draw_bar.shape[0]
    n_events = events_ts.shape[0]
    n_atr = atr_ts.shape[0]
    ptr = 0
    total_R = 0.0
    win_sum = 0.0
    loss_sum = 0.0
    in_pos_until_ns = np.int64(-1)
    slip = SLIPPAGE_TICKS * TICK

    for k in range(n_draws):
        i = draw_bar[k]
        entry_ns = ts_ns[i]
        if entry_ns < in_pos_until_ns:
            continue
        entry_ref = Close[i]
        risk = stop_dists[k]
        if risk <= 0.0:
            continue
        stop_price = entry_ref - risk * direction
        eod_ns = eod_ns_arr[i]

        while ptr < n_events and events_ts[ptr] <= entry_ns:
            _st_update(tree_buf, tsize, events_rank[ptr])
            ptr += 1

        # atr: last atr_ts <= entry_ns
        lo = 0
        hi = n_atr
        while lo < hi:
            mid = (lo + hi) // 2
            if atr_ts[mid] <= entry_ns:
                lo = mid + 1
            else:
                hi = mid
        aidx = lo - 1
        atr_val = atr_vals[aidx] if aidx >= 0 else np.nan

        have_target = False
        target = 0.0
        if not np.isnan(atr_val) and atr_val > 0.0:
            if direction == 1:
                floor = entry_ref + atr_val
                # leftmost rank with price_sorted[rank] >= floor
                flo = 0; fhi = price_sorted.shape[0]
                while flo < fhi:
                    fmid = (flo + fhi) // 2
                    if price_sorted[fmid] < floor:
                        flo = fmid + 1
                    else:
                        fhi = fmid
                r = _st_leftmost(tree_buf, tsize, flo, tsize - 1)
                if r != -1 and r < price_sorted.shape[0]:
                    target = price_sorted[r]
                    have_target = True
            else:
                floor = entry_ref - atr_val
                flo = 0; fhi = price_sorted.shape[0]
                while flo < fhi:
                    fmid = (flo + fhi) // 2
                    if price_sorted[fmid] <= floor:
                        flo = fmid + 1
                    else:
                        fhi = fmid
                # flo = first index with price>floor -> eligible range is [0, flo-1]
                r = _st_rightmost(tree_buf, tsize, 0, flo - 1)
                if r != -1:
                    target = price_sorted[r]
                    have_target = True
        if not have_target:
            target = entry_ref + 2.0 * risk * direction

        scan_start = i + 1
        lo2 = 0
        hi2 = n1m
        while lo2 < hi2:
            mid = (lo2 + hi2) // 2
            if ts_ns[mid] < eod_ns:
                lo2 = mid + 1
            else:
                hi2 = mid
        eod_i = lo2 - 1
        if eod_i < scan_start:
            eod_i = scan_start
        if eod_i >= n1m:
            eod_i = n1m - 1
        if scan_start > eod_i:
            continue

        exit_level = 0.0
        exit_i = eod_i
        found = False
        if direction == 1:
            for j in range(scan_start, eod_i + 1):
                s_hit = Low[j] <= stop_price
                t_hit = High[j] >= target
                if s_hit or t_hit:
                    exit_level = stop_price if s_hit else target
                    exit_i = j
                    found = True
                    break
        else:
            for j in range(scan_start, eod_i + 1):
                s_hit = High[j] >= stop_price
                t_hit = Low[j] <= target
                if s_hit or t_hit:
                    exit_level = stop_price if s_hit else target
                    exit_i = j
                    found = True
                    break
        if not found:
            exit_level = Close[eod_i]
            exit_i = eod_i

        if direction == 1:
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
        R = net_dollars / risk_dollars if risk_dollars > 0.0 else 0.0
        total_R += R
        if R > 0.0:
            win_sum += R
        elif R < 0.0:
            loss_sum += -R
        in_pos_until_ns = ts_ns[exit_i] + np.int64(60_000_000_000)

    return total_R, win_sum, loss_sum


# (batch-runner removed -- unused; run_gate_c.py calls simulate_null_run_jit once
# per run in a thin Python loop, which is already fast enough post-segment-tree.)


def prep_events(events_ts, events_price):
    """Precompute (events_ts already ascending), events_rank (position in
    price-ascending order), price_sorted (ascending), tsize (segment-tree size)."""
    order = np.argsort(events_price, kind="stable")
    price_sorted = events_price[order].astype(np.float64)
    rank_of_orig = np.empty(len(events_price), dtype=np.int64)
    rank_of_orig[order] = np.arange(len(events_price))
    tsize = next_pow2(max(len(events_price), 1))
    return (events_ts.astype(np.int64), rank_of_orig.astype(np.int64),
            price_sorted, tsize)
