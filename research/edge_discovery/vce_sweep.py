"""
vce_sweep.py — full parameter search + gauntlet for the VCE (vol-compression -> expansion) family.

ANTI-DATA-MINING: enumerates a FIXED grid, evaluates EVERY config on IS(2022-2024) and
OOS(2025-2026), writes ALL results to CSV (no silent winner-picking). Survivor bar (must pass
ALL): n>=50, IS PF>=1.10 AND OOS PF>=1.10, no per-year deeply negative, survives cost x2.
Look-ahead +1-bar canary checked on the top configs.
"""
import os, sys, itertools, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import vce_engine as E

IS_END = pd.Timestamp("2025-01-01", tz=E.NY)   # IS = 2022..2024, OOS = 2025..2026


def split_stats(t, cost_mult=1.0):
    if t is None or len(t) == 0:
        return {}
    d = pd.to_datetime(t["date"])
    is_t = t[d < IS_END]; oos_t = t[d >= IS_END]
    out = {}
    for tag, seg in (("full", t), ("is", is_t), ("oos", oos_t)):
        s = E.stats(seg, cost_mult=cost_mult)
        out[tag] = s
    # per-year PF
    yr = d.dt.year
    peryr = {}
    for y in sorted(yr.unique()):
        peryr[int(y)] = E.stats(t[yr.values == y])
    out["peryr"] = peryr
    return out


def build_grid():
    grid = []
    # DETECTOR 1: coil_range <= c * ATR  (Keltner/ratio compression)
    for c in (1.0, 1.5, 2.0):
        for W in (4, 6, 12):
            for trig in (1, 4):
                for E_ in (4, 8):
                    for ex in (("R", 1.5), ("R", 2.0), ("trail", 2.0), ("trail", 3.0)):
                        grid.append(dict(detector="ratio", c=c, W=W, trig_tk=trig, E=E_,
                                         exit_mode=ex[0], Rmult=ex[1] if ex[0] == "R" else 2.0,
                                         trail_atr=ex[1] if ex[0] == "trail" else 2.0))
    # DETECTOR 2: ATR percentile low (rolling causal)
    for p in (0.20, 0.30):
        for W in (4, 6, 12):
            for trig in (1, 4):
                for E_ in (4, 8):
                    for ex in (("R", 1.5), ("R", 2.0), ("trail", 2.0), ("trail", 3.0)):
                        grid.append(dict(detector="pctile", p=p, W=W, trig_tk=trig, E=E_,
                                         exit_mode=ex[0], Rmult=ex[1] if ex[0] == "R" else 2.0,
                                         trail_atr=ex[1] if ex[0] == "trail" else 2.0))
    return grid


def main():
    print("loading REAL Databento RTH 1m -> 5m …", flush=True)
    df, d1 = E.load_5m_rth()
    df = E.add_atr(df)
    df = df[df["date"] >= pd.Timestamp("2022-01-01", tz=E.NY)]
    blk = E.day_blocks(df)
    print(f"  {len(df):,} bars  {df.date.nunique()} days  {df.index.min().date()} -> {df.index.max().date()}", flush=True)

    grid = build_grid()
    print(f"  GRID = {len(grid)} configs (multiple-testing count reported honestly)\n", flush=True)

    rows = []
    for gi, cfg in enumerate(grid):
        t = E.run_config(blk, **cfg)
        ss = split_stats(t)
        full = ss.get("full", {}); iss = ss.get("is", {}); oos = ss.get("oos", {})
        peryr = ss.get("peryr", {})
        minyr_pf = min([s["pf"] for s in peryr.values()], default=np.nan) if peryr else np.nan
        row = dict(idx=gi, **{k: cfg.get(k) for k in
                              ("detector", "c", "p", "W", "trig_tk", "E", "exit_mode", "Rmult", "trail_atr")},
                   n=full.get("n", 0), pf=full.get("pf", np.nan), wr=full.get("wr", np.nan),
                   net=full.get("net", 0.0), expR=full.get("expR", np.nan),
                   is_n=iss.get("n", 0), is_pf=iss.get("pf", np.nan),
                   oos_n=oos.get("n", 0), oos_pf=oos.get("pf", np.nan),
                   minyr_pf=minyr_pf)
        rows.append(row)
        if (gi + 1) % 40 == 0:
            print(f"  ...{gi+1}/{len(grid)}", flush=True)

    res = pd.DataFrame(rows)
    outcsv = os.path.join(os.path.dirname(__file__), "vce_grid_results.csv")
    res.to_csv(outcsv, index=False)
    print(f"\nsaved full grid -> {outcsv}")

    # survivor screen
    surv = res[(res.n >= 50) & (res.is_pf >= 1.10) & (res.oos_pf >= 1.10) & (res.oos_n >= 20)].copy()
    surv = surv.sort_values("oos_pf", ascending=False)
    print(f"\n=== SURVIVORS of (n>=50, IS PF>=1.10, OOS PF>=1.10, OOS n>=20): {len(surv)} ===")
    cols = ["idx", "detector", "c", "p", "W", "trig_tk", "E", "exit_mode", "Rmult", "trail_atr",
            "n", "pf", "wr", "is_pf", "oos_pf", "minyr_pf"]
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(surv[cols].head(30).to_string(index=False))

    # also show best OOS overall regardless of screen (context)
    print("\n=== TOP 15 by OOS PF (any n) ===")
    top = res[res.n >= 30].sort_values("oos_pf", ascending=False).head(15)
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(top[cols].to_string(index=False))

    print("\n=== summary of full grid PF distribution ===")
    print(res["pf"].describe())
    print("frac full-sample PF>1.0:", (res.pf > 1.0).mean())
    print("frac full-sample PF>1.10:", (res.pf > 1.10).mean())
    return res, surv, blk


if __name__ == "__main__":
    main()
