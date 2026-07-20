import json
import time

import numpy as np
import pandas as pd

from harness import all_cells, cell_key
from gates import block_bootstrap_p, bh_fdr

N_HOLDOUT_TRADING_DAYS = 313   # unique ET calendar days with data in holdout window


def main():
    with open("holdout_stats.json") as f:
        stats = json.load(f)

    pvals = {}
    t0 = time.time()
    for concept, tf, d, dname in all_cells():
        key = cell_key(concept, tf, dname)
        tr = pd.read_json(f"trade_ledgers/holdout_{key}.json")
        R = tr["R"].to_numpy(float) if len(tr) else np.array([])
        n = len(R)
        trades_per_day = n / N_HOLDOUT_TRADING_DAYS if n else 0
        block_len = max(1, round(5 * trades_per_day))
        p = block_bootstrap_p(R, block_len) if n > 0 else 1.0
        pvals[key] = p
        print(key, "n=", n, "block_len=", block_len, "p=", round(p, 5))
    print(f"bootstrap done in {time.time()-t0:.1f}s")

    cutoff_p, passed, ladder = bh_fdr(pvals, q=0.10)
    gate_a = {}
    for k, s in stats.items():
        pf = s["pf"]; exp = s["expectancy"]
        gate_a[k] = bool(pf is not None and exp is not None and pf > 1.0 and exp > 0.0)

    out = dict(bh_cutoff_p=cutoff_p, q=0.10, n_cells=36,
               ladder=ladder,
               gate_a=gate_a, gate_b=passed,
               gate_ab=[k for k in gate_a if gate_a[k] and passed.get(k, False)])
    with open("gate_ab_result.json", "w") as f:
        json.dump(out, f, indent=2)

    survivors = out["gate_ab"]
    print(f"\nGate A survivors: {sum(gate_a.values())}/36")
    print(f"Gate B (BH q=0.10) survivors: {sum(passed.values())}/36, cutoff_p={cutoff_p}")
    print(f"Gate A+B survivors ({len(survivors)}): {survivors}")


if __name__ == "__main__":
    main()
