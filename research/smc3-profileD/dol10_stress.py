"""
STEP 4 stress test -- top-3 exit models (by ex-2024 avgR) under 2x costs,
-0.01R extra slip, -0.02R extra slip.  Research-only.
"""
from __future__ import annotations
import sys, os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import load_data  # noqa: E402
from smc3_engine import run_backtest, Config  # noqa: E402
from dol10_levels import DolLevels  # noqa: E402
from dol10_battery import (DATA, build_entries, run_model, compute_stats,
                          mk_dol_source, mk_fixed)  # noqa: E402

TOP3 = {
    "dol_htf_pocket_only": mk_dol_source("src_htf_pocket"),
    "dol_PDH_PDL_only": mk_dol_source("src_pdh_pdl"),
    "dol_prior_session_only": mk_dol_source("src_prior_session"),
}
BASELINE = {"fixed_2R_baseline": mk_fixed(2.0)}


def main():
    df = load_data(DATA)
    res = run_backtest(df, Config())
    tdf = res.trades
    dl = DolLevels(df)
    entries, h, l, c, t_open_ns = build_entries(df, dl, tdf)

    stress_variants = [
        ("base", 1.0, 0.0),
        ("2x_costs", 2.0, 0.0),
        ("slip_-0.01R", 1.0, None),   # handled specially below (R-based, not pts)
        ("slip_-0.02R", 1.0, None),
    ]

    rows = []
    for name, builder in {**TOP3, **BASELINE}.items():
        for label, cost_mult, extra_slip in stress_variants:
            if label.startswith("slip"):
                # convert an "extra R" of slip into points using each trade's own risk;
                # approximate: run with extra_slip_pts = target R-slip * median risk_pts
                target_R_slip = 0.01 if "0.01" in label else 0.02
                median_risk = pd.Series([e["risk_pts"] for e in entries]).median()
                extra_slip_pts = target_R_slip * median_risk
            else:
                extra_slip_pts = extra_slip
            trades, n_skip_rule, n_skip_busy = run_model(name, builder, entries, h, l, c, t_open_ns,
                                                        cost_mult=cost_mult, extra_slip=extra_slip_pts)
            stats = compute_stats(f"{name}__{label}", trades, n_skip_rule, n_skip_busy, len(entries))
            rows.append(stats)
            print(f"{name:26s} {label:14s} n={stats.get('n',0):5d} avgR={stats.get('avgR',float('nan')):+.4f} "
                 f"avgR_ex2024={stats.get('avgR_ex2024',float('nan')):+.4f} PF={stats.get('pf_R',float('nan')):.3f}")

    out = pd.DataFrame(rows)
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports/ifvg_optimisation")
    out.to_csv(os.path.join(outdir, "10_dol_exit_stress.csv"), index=False)
    print(f"\n[written] {outdir}/10_dol_exit_stress.csv")


if __name__ == "__main__":
    main()
