"""Gate C: randomized-entry null (numba-accelerated core, gates_jit.py --
cross-checked bit-identical against the pure-Python SortedList reference
before use). Survivors of A+B get 1000 runs (decisive); ALL 36 cells also get
the cheaper 200-run global null. Checkpointed to gate_c_result.json after
every cell so a rerun resumes from where it left off (synchronous, foreground,
chunkable across calls)."""
import json
import os
import time

import numpy as np
import pandas as pd

from common import load_1m, LONG, SHORT
from harness import build_all_contexts, all_cells, cell_key
from survey_engine import SPLIT_TS, WINDOW_END, df1m_to_arrays
from gates import _eligible_session_bars
from gates_jit import simulate_null_run_jit, prep_events

CKPT = "gate_c_result.json"
RAW_CANDIDATE_COUNTS_NOTE = (
    "n_draws = the real cell's REALIZED holdout trade count (n from holdout_stats.json) "
    "-- 'entries' read literally as executed positions, matching the real cell 1:1.")


def load_checkpoint():
    if os.path.exists(CKPT):
        with open(CKPT) as f:
            return json.load(f)
    return {}


def save_checkpoint(results):
    tmp = CKPT + ".tmp"
    with open(tmp, "w") as f:
        json.dump(results, f, indent=2)
    os.replace(tmp, CKPT)


def run_one_cell(key, concept, tf, d, dname, ctx, arrs, eligible, events_cache, n_runs, real_totR, seed):
    tr = pd.read_json(f"trade_ledgers/holdout_{key}.json")
    if not len(tr):
        return dict(skipped="no holdout trades", n_runs=n_runs)
    stop_pool = tr["risk_pts"].to_numpy(float)
    n_draws = len(tr)

    cache_key = (tf, d)
    if cache_key not in events_cache:
        events_ts_src = ctx["sh_ts"] if d == LONG else ctx["sl_ts"]
        events_price_src = ctx["sh_price"] if d == LONG else ctx["sl_price"]
        events_cache[cache_key] = prep_events(events_ts_src, events_price_src)
    events_ts, events_rank, price_sorted, tsize = events_cache[cache_key]
    tree_buf = np.zeros(2 * tsize, dtype=np.uint8)

    rng = np.random.default_rng(seed)
    null_totals = np.empty(n_runs)
    null_pf = np.empty(n_runs)
    for r in range(n_runs):
        db = rng.choice(eligible, size=n_draws, replace=True)
        db.sort()
        db = db.astype(np.int64)
        sd = rng.choice(stop_pool, size=n_draws, replace=True).astype(np.float64)
        tree_buf[:] = 0
        tR, wS, lS = simulate_null_run_jit(
            arrs["ts_ns"], arrs["Low"], arrs["High"], arrs["Close"], arrs["eod_ns"],
            ctx["atr_ts"], ctx["atr_vals"], events_ts, events_rank, price_sorted, tsize,
            d, db, sd, tree_buf)
        null_totals[r] = tR
        null_pf[r] = (wS / lS) if lS > 0 else (np.inf if wS > 0 else np.nan)

    p95 = float(np.percentile(null_totals, 95))
    valid_pf = null_pf[~np.isnan(null_pf)]
    return dict(
        n_runs=n_runs, n_draws=n_draws,
        null_p95=round(p95, 4), null_mean=round(float(null_totals.mean()), 4),
        null_median=round(float(np.median(null_totals)), 4),
        real_totR=round(real_totR, 4), beats_null_95=bool(real_totR > p95),
        null_frac_totR_gt_0=float((null_totals > 0).mean()),
        null_frac_pf_gt_1_2=float((valid_pf > 1.2).mean()) if valid_pf.size else None,
        n_draws_note=RAW_CANDIDATE_COUNTS_NOTE,
    )


def main():
    with open("gate_ab_result.json") as f:
        gab = json.load(f)
    survivors = set(gab["gate_ab"])

    print("loading data + building contexts...")
    t0 = time.time()
    df1m = load_1m()
    contexts = build_all_contexts(df1m)
    arrs = df1m_to_arrays(df1m)
    eligible = _eligible_session_bars(arrs["ts_ns"], SPLIT_TS.value, WINDOW_END.value)
    print(f"ready in {time.time()-t0:.1f}s")

    with open("holdout_stats.json") as f:
        stats = json.load(f)

    results = load_checkpoint()
    print(f"resuming with {len(results)} cells already checkpointed")

    events_cache = {}
    t0 = time.time()
    for concept, tf, d, dname in all_cells():
        key = cell_key(concept, tf, dname)
        if key in results and "error" not in results[key]:
            continue
        n_runs = 1000 if key in survivors else 200
        real_totR = stats[key]["totR"]
        tS = time.time()
        try:
            res = run_one_cell(key, concept, tf, d, dname, contexts[tf], arrs, eligible,
                                events_cache, n_runs, real_totR, seed=hash(key) % (2**31))
        except Exception as e:
            res = dict(error=str(e), n_runs=n_runs)
        res["is_survivor_AB"] = key in survivors
        results[key] = res
        save_checkpoint(results)
        dt = time.time() - tS
        if "error" not in res and "skipped" not in res:
            print(f"{key}: n_runs={n_runs} n_draws={res['n_draws']} real_totR={real_totR:.1f} "
                  f"null_p95={res['null_p95']:.1f} beats={res['beats_null_95']} ({dt:.2f}s)")
        else:
            print(f"{key}: {res} ({dt:.2f}s)")

    print(f"\nGate C total time {(time.time()-t0)/60:.1f} min")

    passed_c = [k for k in survivors if results.get(k, {}).get("beats_null_95")]
    print(f"\nGate A+B+C survivors ({len(passed_c)}): {passed_c}")
    with open("gate_abc_survivors.json", "w") as f:
        json.dump(passed_c, f, indent=2)


if __name__ == "__main__":
    main()
