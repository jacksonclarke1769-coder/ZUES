"""GAUNTLET on the survivor family: A_30_comp_breakout (30-min OR breakout, overnight-range
COMPRESSED gate ratio<0.8). Runs IS/OOS, per-year PF, cost x1/x2/x3, +1-bar-shift lookahead canary.
Kill on ANY failure. Also shows the whole comp-breakout exit family for robustness."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search as S
import sim_engine as SE

IS_YRS = {2022, 2023, 2024}
OOS_YRS = {2025, 2026}


def split_stats(df):
    df = df.copy(); df["yr"] = pd.to_datetime(df["date"]).dt.year
    is_ = df[df.yr.isin(IS_YRS)]; oos = df[df.yr.isin(OOS_YRS)]
    return SE.stats(is_), SE.stats(oos), SE.by_year(df)


def line(tag, df):
    s = SE.stats(df); isS, oosS, yrs = split_stats(df)
    yrstr = " ".join(f"{y}:{yrs[y]['pf']}({yrs[y]['n']})" for y in sorted(yrs))
    return (f"{tag:28s} n={s['n']:4d} PF={s['pf']:.3f} WR={s['wr']:.3f} tot={s['tot']:8.1f} | "
            f"IS PF={isS['pf']}(n{isS['n']}) OOS PF={oosS['pf']}(n{oosS['n']})\n"
            f"    per-yr: {yrstr}")


print("=" * 100)
print("GAUNTLET — survivor family A_30_comp_breakout (30m ORB, overnight-range COMPRESSED ratio<0.8)")
print("=" * 100)

print("\n[1] Full-sample family across exit types (base cost 0.75pt, adverse-first, 1m):")
for target in ["1R", "2R", "close", "trail"]:
    df = S.fam_A(30, "comp", "breakout", target)
    print(line(f"A_30_comp_breakout_{target}", df))

print("\n[2] COST STRESS on the two cleanest exits (2R, close):")
for target in ["2R", "close"]:
    for c, lab in [(0.75, "x1"), (1.5, "x2"), (2.25, "x3")]:
        df = S.fam_A(30, "comp", "breakout", target, cost=c)
        s = SE.stats(df)
        print(f"  {target:6s} cost {lab} ({c}pt): PF={s['pf']:.3f} WR={s['wr']:.3f} tot={s['tot']:8.1f} n={s['n']}")

print("\n[3] +1-bar-shift LOOKAHEAD CANARY (enter 1 min AFTER trigger bar, at that bar's open):")
for target in ["2R", "close"]:
    df0 = S.fam_A(30, "comp", "breakout", target)
    df1 = S.fam_A(30, "comp", "breakout", target, entry_delay=1)
    s0 = SE.stats(df0); s1 = SE.stats(df1)
    print(f"  {target:6s} base PF={s0['pf']:.3f} tot={s0['tot']:.1f}  ->  +1bar PF={s1['pf']:.3f} tot={s1['tot']:.1f} (n={s1['n']})")

print("\n[4] CONTROL — same breakout with NO regime gate and with EXPANDED gate (is the edge the gate?):")
for gate in ["all", "exp", "comp"]:
    df = S.fam_A(30, gate, "breakout", "2R")
    print(line(f"A_30_{gate}_breakout_2R", df))

print("\n[5] Robustness — 15m OR version of the compressed breakout (different OR window):")
for target in ["2R", "close"]:
    df = S.fam_A(15, "comp", "breakout", target)
    print(line(f"A_15_comp_breakout_{target}", df))
