"""
Gate D — live-achievable (deployability, not significance). PREREG §7.

Methodology (fill_verify.py-style, adapted; documented resolutions):
  - Poll cadence: bot polls at 5m bar closes. poll_ts = first 5m boundary >= conf_ts.
  - "limit entries are placed AT that poll (not the signal bar)": the resting
    order's fill-search window starts at poll_ts (not conf_ts); its END is
    unchanged (conf_ts + 20 signal-TF bars, or EOD of the signal's exchange
    day -- both anchored to the ORIGINAL confirmation instant, since that is a
    strategy-level definition independent of poll cadence). If poll_ts already
    >= that end, the order is suppressed (never gets a chance to rest).
  - Market-mode signals: the order can only be SENT at poll_ts, so live entry
    reference = price at poll_ts (first 1m bar with Open>=poll_ts).
  - certified_gate literal staleness test ("fill instant >10min old at the
    earliest poll that could surface it"): computed and reported AS SPECIFIED,
    but note structurally: with 5-minute poll cadence and this survey's clean
    single-instant confirmations (no multi-bar internal state machine like
    Profile A's), the maximum possible poll latency is <5 minutes -- always
    under the 10-min certified_gate threshold. This channel is expected to be
    ~0% for every cell; the SUBSTANTIVE deployability effect here is the
    order-timing shift itself (poll_ts vs conf_ts), captured by the re-walk
    below (a trade can be missed/repriced by the few-minute poll delay).
  - Both channels are reported per survivor: literal 10-min staleness % (R-
    weighted) AND the full re-walked live-achievable stats/suppression %.
"""
import json
import time

import numpy as np
import pandas as pd

from common import load_1m, LONG, SHORT, TICK, LIMIT_LIFETIME_BARS, exch_day_cutoff, finish
from harness import build_all_contexts, cell_key
from survey_engine import SPLIT_TS, WINDOW_END, df1m_to_arrays, _nearest_target, _atr_at


def ceil_5m(ts: pd.Timestamp) -> pd.Timestamp:
    floored = ts.floor("5min")
    return floored if floored == ts else floored + pd.Timedelta(minutes=5)


def live_walk_trade(row, ctx, arrs, direction, tf_min):
    ts_ns = arrs["ts_ns"]; Low = arrs["Low"]; High = arrs["High"]; Close = arrs["Close"]
    n1m = len(ts_ns)
    conf_ts = pd.Timestamp(row["conf_ts"])
    fill_ts_hist = pd.Timestamp(row["fill_ts"])
    poll_ts = ceil_5m(conf_ts)
    poll_ns = poll_ts.value

    # literal certified_gate staleness (10-min test), on the ORIGINAL historical fill
    earliest_poll_for_fill = ceil_5m(fill_ts_hist)
    staleness_min = (earliest_poll_for_fill - fill_ts_hist).total_seconds() / 60.0
    certified_stale = staleness_min > 10.0

    eod_cut = exch_day_cutoff(conf_ts)
    eod_ns = eod_cut.value

    if row["mode"] == "limit":
        lifetime_end_ns = (conf_ts + pd.Timedelta(minutes=tf_min * LIMIT_LIFETIME_BARS)).value
        order_end_ns = min(lifetime_end_ns, eod_ns)
        i0 = np.searchsorted(ts_ns, poll_ns, side="left")
        i1 = np.searchsorted(ts_ns, order_end_ns, side="left")
        if i1 <= i0 or i0 >= n1m:
            return dict(achievable=False, reason="poll_after_order_end", certified_stale=certified_stale,
                        staleness_min=staleness_min)
        entry_price = row["entry_ref"] if row["reason"] != "__unused__" else None
        entry_price = row["_entry_price"]
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
            return dict(achievable=False, reason="invalidated_before_fill", certified_stale=certified_stale,
                        staleness_min=staleness_min)
        if e_hit is None:
            return dict(achievable=False, reason="never_filled_in_window", certified_stale=certified_stale,
                        staleness_min=staleness_min)
        fill_i = i0 + int(e_hit)
        entry_ref = entry_price
    else:
        fill_i = np.searchsorted(ts_ns, poll_ns, side="left")
        if fill_i >= n1m:
            return dict(achievable=False, reason="poll_after_data_end", certified_stale=certified_stale,
                        staleness_min=staleness_min)
        entry_ref = Close[fill_i]

    fill_ns = int(ts_ns[fill_i])
    stop_price = row["_stop_price"]
    risk = abs(entry_ref - stop_price)
    if not np.isfinite(risk) or risk <= 0:
        return dict(achievable=False, reason="degenerate_risk", certified_stale=certified_stale,
                    staleness_min=staleness_min)

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
        return dict(achievable=False, reason="no_scan_room", certified_stale=certified_stale,
                    staleness_min=staleness_min)
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
    elif t_rel is not None:
        exit_level = target
    else:
        exit_level = Close[eod_i]
    net_dollars, R, e_fill, x_fill = finish(direction, entry_ref, exit_level, risk)
    return dict(achievable=True, R=R, certified_stale=certified_stale, staleness_min=staleness_min,
                poll_delay_min=(poll_ts - conf_ts).total_seconds() / 60.0)


def run_gate_d(survivors, contexts, arrs, direction_of, tf_of):
    out = {}
    for key in survivors:
        concept, tf_s, dname = key.rsplit("_", 2)
        tf = int(tf_s.replace("m", ""))
        direction = LONG if dname == "long" else SHORT
        ctx = contexts[tf]
        tr = pd.read_json(f"trade_ledgers/holdout_{key}.json")
        if not len(tr):
            out[key] = dict(n=0)
            continue
        # recover raw structural stop/entry/invalidate prices from the candidate stream
        cand = ctx["candidates"][concept]
        cand = cand[(cand["direction"] == direction)]
        cmap_by_ts = {}
        for r in cand.itertuples(index=False):
            cmap_by_ts.setdefault(r.conf_ts, r)

        results = []
        R_orig_sum_abs = 0.0
        for _, row in tr.iterrows():
            conf_ts = pd.Timestamp(row["conf_ts"])
            c = cmap_by_ts.get(conf_ts)
            row2 = dict(row)
            row2["_entry_price"] = c.entry_price if c is not None else row["entry_ref"]
            row2["_stop_price"] = c.stop_price if c is not None else row["stop"]
            row2["_invalidate_price"] = c.invalidate_price if c is not None else row["stop"]
            res = live_walk_trade(row2, ctx, arrs, direction, tf)
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
        edge_lives_in_suppressed = bool(totR is not None and totR <= 0 < sum(r["R_orig"] for r in results))

        out[key] = dict(
            n_original=len(tr), n_live_achievable=n,
            live_wr=round(wr, 4) if wr is not None else None,
            live_pf=round(pf, 4) if (pf not in (None, float("inf"))) else pf,
            live_totR=round(totR, 4) if totR is not None else None,
            live_expectancy=round(expectancy, 4) if expectancy is not None else None,
            r_weighted_suppression_pct=round(supp_R_weighted * 100, 2),
            r_weighted_certified_gate_stale_pct=round(certified_stale_R_weighted * 100, 2),
            median_poll_delay_min=round(float(np.median([r.get("poll_delay_min", np.nan)
                                                           for r in achievable])), 3) if achievable else None,
            edge_lives_in_suppressed_trades=edge_lives_in_suppressed,
            original_holdout_totR=round(float(tr["R"].sum()), 4),
        )
        print(key, out[key])
    return out


def main():
    with open("gate_abc_survivors.json") as f:
        survivors = json.load(f)
    if not survivors:
        print("No Gate A+B+C survivors -- Gate D has nothing to run.")
        with open("gate_d_result.json", "w") as f:
            json.dump({}, f, indent=2)
        return
    df1m = load_1m()
    contexts = build_all_contexts(df1m)
    arrs = df1m_to_arrays(df1m)
    t0 = time.time()
    out = run_gate_d(survivors, contexts, arrs, None, None)
    print(f"Gate D done in {time.time()-t0:.1f}s")
    with open("gate_d_result.json", "w") as f:
        json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
