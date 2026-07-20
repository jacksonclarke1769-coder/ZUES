"""Phase 2 step 5: run all 36 cells on HOLDOUT (2025-06-22 -> 2026-06-22), plus
the quarterly walk-forward variant (8 equal ~91-day quarters spanning the full
2y window, per-quarter total-R sign per cell). Only run after train_ranking.json
exists (train ranking already frozen)."""
import hashlib
import json
import os
import time

import pandas as pd

from common import load_1m
from harness import build_all_contexts, run_all_cells, stats_table, all_cells, cell_key
from survey_engine import WINDOW_START, SPLIT_TS, WINDOW_END, run_cell, df1m_to_arrays


def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def main():
    assert os.path.exists("train_ranking.json"), "train_ranking.json must exist before HOLDOUT is opened"

    t0 = time.time()
    df1m = load_1m()
    contexts = build_all_contexts(df1m)
    print(f"contexts built in {time.time()-t0:.1f}s")

    # ---- HOLDOUT ----
    t1 = time.time()
    trades_holdout = run_all_cells(df1m, contexts, SPLIT_TS, WINDOW_END)
    print(f"holdout cells run in {time.time()-t1:.1f}s")
    stats = stats_table(trades_holdout)
    with open("holdout_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    # persist per-cell trade ledgers (needed for gates B/C/D + correlation)
    os.makedirs("trade_ledgers", exist_ok=True)
    for k, tr in trades_holdout.items():
        tr2 = tr.copy()
        for c in ("conf_ts", "fill_ts", "exit_ts"):
            tr2[c] = tr2[c].astype(str)
        tr2.to_json(f"trade_ledgers/holdout_{k}.json", orient="records", indent=1)

    # ---- quarterly walk-forward (8 quarters across the 2y window) ----
    t2 = time.time()
    total_days = (WINDOW_END - WINDOW_START).days
    q_days = total_days / 8.0
    quarters = [(WINDOW_START + pd.Timedelta(days=q_days * i),
                 WINDOW_START + pd.Timedelta(days=q_days * (i + 1))) for i in range(8)]
    arrs = df1m_to_arrays(df1m)
    quarterly = {}
    for concept, tf, d, dname in all_cells():
        key = cell_key(concept, tf, dname)
        ctx = contexts[tf]
        signs = []
        totRs = []
        for (qs, qe) in quarters:
            tr = run_cell(arrs, ctx, concept, d, qs, qe)
            r = float(tr["R"].sum()) if len(tr) else 0.0
            totRs.append(round(r, 4))
            signs.append("+" if r > 0 else ("-" if r < 0 else "0"))
        quarterly[key] = dict(totR_by_quarter=totRs, sign_by_quarter=signs,
                               n_positive_quarters=sum(1 for s in signs if s == "+"))
    print(f"quarterly walk-forward run in {time.time()-t2:.1f}s")
    with open("quarterly_stats.json", "w") as f:
        json.dump(dict(quarter_bounds=[(str(a), str(b)) for a, b in quarters],
                        cells=quarterly), f, indent=2)

    print("holdout_stats.json sha256:", sha256_of_file("holdout_stats.json"))
    print("quarterly_stats.json sha256:", sha256_of_file("quarterly_stats.json"))
    print(f"total {time.time()-t0:.1f}s")

    for k, v in sorted(stats.items()):
        print(k, v)


if __name__ == "__main__":
    main()
