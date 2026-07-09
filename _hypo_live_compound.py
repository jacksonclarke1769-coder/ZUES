"""HYPOTHETICAL (operator request 2026-07-04): $50k LIVE account, real money, NO prop rules.

Frozen machine UNCHANGED: A-only Exit#3 + D1c drift gate, 1m-truth fills (the locked signal edge).
Wrapper stripped of everything the operator said to remove:
  - NO DLL, NO trailing floor, NO 50% consistency rule, NO $550/$1000 daily stop.
  - Every signal the frozen machine fires is taken.
  - COMPOUNDING: size-to-risk scales with the LIVE account instead of freezing at $1,200.
    The frozen eval risks $1,200 on a $50k base = 2.4% of equity per trade. We hold that
    SAME risk fraction and let the dollars grow with the account. Nothing in the strategy
    changes; only the account base compounds (exactly 'how sizing suits a live account').

Per-trade return = R * f  (size-to-risk => contracts chosen so $risk = f*equity, pnl = R*$risk).
  equity_{i+1} = equity_i * (1 + f * R_i)

Outputs: year-by-year money made + end balance, for the frozen 2.4% fraction plus a sensitivity
band, and the linear (non-compounding, fixed $1,200) anchor = certified truth.
"""
import os, sys, warnings, json
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strategy_engine_profileA as E
import config
import run_d1c_real as RD
import apex_eval_eod_databento as DB
from tools_1m_truth_recert import M1Map
from tools_phase3_config_sweep import a_streams_d1c

START = 50_000.0

print("loading 1m+5m Databento and frozen A/Exit#3/D1c stream (1m-truth)…", flush=True)
d1 = RD.load_1m()
if d1.index.tz is not None:
    d1 = d1.tz_localize(None)
df5 = DB.load_databento_5m()
mp = M1Map(d1, df5)
eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
feats = eng._features()
d1_tz = RD.load_1m()  # tz-aware copy for attach_drift
rows, dropped = a_streams_d1c(feats, mp, d1_tz)["exit3"]

# ordered trade stream
tr = sorted([(pd.Timestamp(r["ts"]), float(r["R"])) for r in rows], key=lambda x: x[0])
Rs = np.array([r for _, r in tr])
years = np.array([t.year for t, _ in tr])
print(f"  trades kept={len(tr)}  D1c-dropped={dropped}  span {tr[0][0].date()} -> {tr[-1][0].date()}")
print(f"  full-period netR={Rs.sum():+.1f}  WR={100*(Rs>0).mean():.1f}%  "
      f"PF={Rs[Rs>0].sum()/-Rs[Rs<=0].sum():.3f}  worstR={Rs.min():+.2f}  bestR={Rs.max():+.2f}")

yr_list = sorted(set(years.tolist()))


def compound(f):
    """Return (year_rows, final_equity, max_dd_pct). year_rows: (yr, start_eq, pnl, end_eq, ntr, ret%)."""
    eq = START
    peak = START
    maxdd = 0.0
    out = []
    for y in yr_list:
        s = eq
        n = 0
        for (t, R), yy in zip(tr, years):
            if yy != y:
                continue
            eq *= (1 + f * R)
            peak = max(peak, eq)
            maxdd = max(maxdd, (peak - eq) / peak)
            n += 1
        out.append((y, s, eq - s, eq, n, 100 * (eq / s - 1)))
    return out, eq, 100 * maxdd


def linear(budget):
    """Fixed dollar risk, no compounding (certified-style). year -> pnl$."""
    out = []
    eq = START
    for y in yr_list:
        pnl = float(Rs[years == y].sum()) * budget
        out.append((y, eq, pnl, eq + pnl, int((years == y).sum())))
        eq += pnl
    return out, eq


print("\n================ LINEAR (no compounding, fixed $1,200 risk = certified truth) ================")
lrows, lend = linear(1200)
print(f"{'year':>6}{'start$':>13}{'made$':>13}{'end$':>13}{'trades':>8}")
for y, s, p, e, n in lrows:
    print(f"{y:>6}{s:>13,.0f}{p:>+13,.0f}{e:>13,.0f}{n:>8}")
print(f"  5yr total made = {lend-START:+,.0f}   end = {lend:,.0f}")

for f, tag in [(0.012, "1.2% risk/trade (HALF the frozen fraction — conservative)"),
               (0.024, "2.4% risk/trade  <-- FROZEN $1,200/$50k fraction, compounding"),
               (0.036, "3.6% risk/trade (1.5x — aggressive)")]:
    crows, cend, mdd = compound(f)
    print(f"\n================ COMPOUNDING @ {tag} ================")
    print(f"{'year':>6}{'start$':>15}{'made$':>15}{'end$':>15}{'trades':>8}{'yr%':>9}")
    for y, s, p, e, n, r in crows:
        print(f"{y:>6}{s:>15,.0f}{p:>+15,.0f}{e:>15,.0f}{n:>8}{r:>+8.1f}%")
    print(f"  5yr total made = {cend-START:+,.0f}   end = {cend:,.0f}   "
          f"({cend/START:.2f}x)   max intratrade drawdown = {mdd:.1f}%")

# persist for the write-up
res = dict(machine="ZEUS v2026.07.02b frozen (A/Exit#3/D1c, 1m-truth) — NO prop rules, compounding",
          start=START, trades=len(tr), netR=float(Rs.sum()), WR=float(100*(Rs>0).mean()),
          span=[str(tr[0][0].date()), str(tr[-1][0].date())],
          linear_1200=dict(rows=lrows, end=lend),
          compound={f"{f}": dict(rows=compound(f)[0], end=compound(f)[1], maxdd=compound(f)[2])
                    for f in (0.012, 0.024, 0.036)})
json.dump(res, open("reports/_hypo_live_compound.json", "w"), indent=1, default=str)
print("\nwrote reports/_hypo_live_compound.json")
