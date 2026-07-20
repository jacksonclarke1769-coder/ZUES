"""Phase 1 step 4: run all 36 cells on TRAIN ONLY (2024-06-22 -> 2025-06-22).
Writes train_stats.json + train_ranking.json, prints sha256 of both.
"""
import hashlib
import json
import time

from common import load_1m
from harness import build_all_contexts, run_all_cells, stats_table
from survey_engine import WINDOW_START, SPLIT_TS


def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def main():
    t0 = time.time()
    df1m = load_1m()
    contexts = build_all_contexts(df1m)
    print(f"contexts built in {time.time()-t0:.1f}s")

    t1 = time.time()
    trades = run_all_cells(df1m, contexts, WINDOW_START, SPLIT_TS)
    print(f"train cells run in {time.time()-t1:.1f}s")

    stats = stats_table(trades)
    with open("train_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    ranked = sorted(
        [(k, v["expectancy"]) for k, v in stats.items() if v["expectancy"] is not None],
        key=lambda x: x[1], reverse=True)
    ranking = {"ranked_by_train_expectancy": [{"cell": k, "expectancy": v} for k, v in ranked],
               "cells_with_zero_trades": [k for k, v in stats.items() if v["n"] == 0]}
    with open("train_ranking.json", "w") as f:
        json.dump(ranking, f, indent=2)

    print("train_stats.json sha256:", sha256_of_file("train_stats.json"))
    print("train_ranking.json sha256:", sha256_of_file("train_ranking.json"))
    print(f"total {time.time()-t0:.1f}s")

    for k, v in sorted(stats.items()):
        print(k, v)


if __name__ == "__main__":
    main()
