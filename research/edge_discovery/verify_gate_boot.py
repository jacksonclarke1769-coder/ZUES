"""Front 3 (threshold sensitivity) + Front 4 (OOS bootstrap CI, per-year OOS)."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search as S
import sim_engine as SE

f = S.f
rth = S.rth
IS_YRS = {2022, 2023, 2024}; OOS_YRS = {2025, 2026}

def fam_A_thr(orm, lo, hi, target="2R", cost=0.75):
    """breakout gated by lo <= on_rng_ratio < hi"""
    days = set(f.index[(f["on_rng_ratio"] >= lo) & (f["on_rng_ratio"] < hi)])
    ORl = S.ORD[orm]; trades = []
    for day in days:
        day = pd.Timestamp(day)
        if day not in ORl: continue
        orh, orl, end = ORl[day]; width = orh - orl
        if width < 5: continue
        force = day + pd.Timedelta(hours=15, minutes=59)
        trig_end = day + pd.Timedelta(hours=10, minutes=30)
        for brk_side, lvl, opp in [(1, orh, orl), (-1, orl, orh)]:
            side = brk_side; stop = opp; r = width
            tgt = lvl + side * 2 * r if target == "2R" else None
            trades.append(dict(date=day, side=side, entry_level=lvl, trig_start=end,
                               trig_end=trig_end, stop=stop, target=tgt, trail_atr=None,
                               exit_ts=force, tag="thr"))
    df = SE.simulate(trades, rth, cost)
    if len(df) == 0: return df
    return df.sort_values("ent_ts").groupby("date", as_index=False).first()

def split(df):
    df = df.copy(); df["yr"] = pd.to_datetime(df["date"]).dt.year
    return SE.stats(df[df.yr.isin(IS_YRS)]), SE.stats(df[df.yr.isin(OOS_YRS)]), SE.stats(df)

print("="*80)
print("FRONT 3 — GATE THRESHOLD SENSITIVITY (upper-bound gate: on_rng_ratio < thr), 2R")
print("A real regime effect should be SMOOTH/monotonic, not a lone spike at 0.8")
print("="*80)
print(f"{'thr(<)':>8}{'n':>6}{'PF_full':>9}{'IS_PF':>8}{'OOS_PF':>8}{'OOS_n':>7}")
for thr in [0.5,0.6,0.7,0.8,0.9,1.0,1.1,1.2]:
    df = fam_A_thr(30, -1e9, thr)
    isS, oosS, full = split(df)
    print(f"{thr:>8.1f}{full['n']:>6}{full['pf']:>9.3f}{isS['pf']:>8}{oosS['pf']:>8}{oosS['n']:>7}")

print("\nBAND gates (disjoint) to see WHERE the edge lives:")
print(f"{'band':>12}{'n':>6}{'PF_full':>9}{'OOS_PF':>8}")
for lo,hi in [(-1e9,0.6),(0.6,0.8),(0.8,1.0),(1.0,1.2),(1.2,1e9)]:
    df = fam_A_thr(30, lo, hi)
    _,oosS,full = split(df)
    lbl = f"[{max(lo,0):.1f},{hi if hi<10 else 99:.1f})"
    print(f"{lbl:>12}{full['n']:>6}{full['pf']:>9.3f}{oosS['pf']:>8}")

print("\n"+"="*80)
print("FRONT 4 — OOS BOOTSTRAP (survivor A_30_comp_breakout_2R), resample trades")
print("="*80)
df = S.fam_A(30, "comp", "breakout", "2R")
df["yr"] = pd.to_datetime(df["date"]).dt.year
oos = df[df.yr.isin(OOS_YRS)].copy()
pnl = oos["pnl"].values
def pf(x):
    w = x[x>0].sum(); l = -x[x<0].sum(); return w/l if l>0 else np.inf
obs = pf(pnl)
rng = np.random.default_rng(42)
boots = np.array([pf(rng.choice(pnl, size=len(pnl), replace=True)) for _ in range(10000)])
boots = boots[np.isfinite(boots)]
print(f"OOS n={len(pnl)}  observed PF={obs:.3f}  mean bal={pnl.mean():.2f}pt")
print(f"bootstrap PF: 5%={np.percentile(boots,5):.3f}  50%={np.percentile(boots,50):.3f}  95%={np.percentile(boots,95):.3f}")
print(f"P(PF<=1.0) = {(boots<=1.0).mean()*100:.1f}%")
# per-year OOS
print("\nOOS per-year:")
for y in sorted(OOS_YRS):
    g = oos[oos.yr==y]
    print(f"  {y}: n={len(g)} PF={SE.stats(g)['pf']} tot={SE.stats(g)['tot']}")
# OOS by quarter
oos["q"] = pd.to_datetime(oos["date"]).dt.to_period("Q").astype(str)
print("\nOOS by quarter:")
for q,g in oos.groupby("q"):
    print(f"  {q}: n={len(g)} PF={SE.stats(g)['pf']} tot={SE.stats(g)['tot']:.0f}")
