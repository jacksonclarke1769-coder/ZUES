"""
vce_gauntlet.py — hammer the top balanced candidates with the mandatory gauntlet:
cost x1/x2/x3, per-year PF, look-ahead +1-bar canary, and a genuine-compression cohort check.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
import vce_engine as E

IS_END = pd.Timestamp("2025-01-01", tz=E.NY)

CANDS = {
    103: dict(detector="ratio", c=2.0, W=4, trig_tk=1, E=8, exit_mode="trail", trail_atr=3.0),
    101: dict(detector="ratio", c=2.0, W=4, trig_tk=1, E=8, exit_mode="R", Rmult=2.0),
     71: dict(detector="ratio", c=1.5, W=6, trig_tk=1, E=8, exit_mode="trail", trail_atr=3.0),
    151: dict(detector="pctile", p=0.20, W=4, trig_tk=1, E=8, exit_mode="trail", trail_atr=3.0),
}


def pf_of(t, cost_mult=1.0):
    return E.stats(t, cost_mult=cost_mult)["pf"]


def report_cand(blk, idx, cfg):
    t = E.run_config(blk, **cfg)
    d = pd.to_datetime(t["date"]); yr = d.dt.year
    print(f"\n{'='*90}\nCANDIDATE idx={idx}  {cfg}")
    print(f"  n={len(t)}  WR={(t.pnl>0).mean()*100:.1f}%  net={t.pnl.sum():+.0f}pt  "
          f"trades/wk={len(t)/((d.max()-d.min()).days/7):.1f}")
    # cost stress
    for cm in (1.0, 2.0, 3.0):
        s = E.stats(t, cost_mult=cm)
        print(f"   cost x{cm:.0f}: PF {s['pf']:.3f}  net {s['net']:+7.0f}pt  expR {s['expR']:+.3f}  maxDD {s['maxdd']:.0f}pt")
    # IS/OOS
    for tag, seg in (("IS 22-24", t[d < IS_END]), ("OOS 25-26", t[d >= IS_END])):
        s = E.stats(seg); s2 = E.stats(seg, cost_mult=2.0)
        print(f"   {tag}: n={s['n']:4d}  PF {s['pf']:.3f}  (costx2 PF {s2['pf']:.3f})")
    # per year
    print("   per-year:", end="")
    for y in sorted(yr.unique()):
        s = E.stats(t[yr.values == y])
        print(f"  {y}:PF{s['pf']:.2f}(n{s['n']})", end="")
    print()
    # look-ahead +1 canary (edge must NOT jump)
    tc = E.run_config(blk, shift=1, **cfg)
    print(f"   +1-bar look-ahead CANARY: PF {pf_of(tc):.3f} (n{len(tc)})   [base PF {pf_of(t):.3f}] "
          f"-> {'OK (no jump)' if pf_of(tc) < pf_of(t)+0.3 else 'WARN jump'}")
    return t


def genuine_compression_cohort(res):
    """Isolate configs that are ACTUALLY compression (tight coil): ratio c<=1.0, or pctile p<=0.20
    with W>=6. Report their PF distribution to show real coils have no edge."""
    tight = res[((res.detector == "ratio") & (res.c <= 1.0)) |
                ((res.detector == "pctile") & (res.p <= 0.20) & (res.W >= 6))]
    print(f"\n{'='*90}\nGENUINE-COMPRESSION COHORT (tight coils only): {len(tight)} configs")
    print(f"  full-sample PF: median {tight.pf.median():.3f}  max {tight.pf.max():.3f}  "
          f"frac>1.0 {(tight.pf>1.0).mean():.2f}")
    print(f"  IS PF median {tight.is_pf.median():.3f} ; OOS PF median {tight.oos_pf.median():.3f}")
    print(f"  configs with BOTH IS>1.05 and OOS>1.05: {len(tight[(tight.is_pf>1.05)&(tight.oos_pf>1.05)&(tight.n>=50)])}")


def main():
    df, d1 = E.load_5m_rth(); df = E.add_atr(df)
    df = df[df["date"] >= pd.Timestamp("2022-01-01", tz=E.NY)]
    blk = E.day_blocks(df)
    for idx, cfg in CANDS.items():
        report_cand(blk, idx, cfg)
    res = pd.read_csv(os.path.join(os.path.dirname(__file__), "vce_grid_results.csv"))
    genuine_compression_cohort(res)


if __name__ == "__main__":
    main()
