"""VPC fill-realism slippage stress (AUDIT, read-only, new file).

Reproduces the certified 408-trade VPC stream via vpc_apex_eval_sim.vpc_trades_rich (5m native)
and re-prices each trade under EXTRA slippage added to BOTH the market entry (next-bar open) and
the trailing-stop exit, on top of the 0.75pt base RT cost already baked in. Reports PF(pts),
PF(R), WR, expR, total pts at each slippage level and the breakeven crossing. NQ tick = 0.25 pt.
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/..")
import nq_vwap_pullback as v
import vpc_apex_eval_sim as VS

feats = v.features(VS.real_rth_5m())
feats = feats[feats.date >= pd.Timestamp("2022-01-01", tz=VS.NY)]
tr = VS.vpc_trades_rich(feats)   # pnl_pts already net of 0.75 RT base cost
pnl0 = tr.pnl_pts.values
stop = tr.stop_pts.values
n = len(tr)
print(f"certified stream: n={n}  net={pnl0.sum():.1f}pt  base RT cost=0.75pt (0.375/side)")

def stats(pnl, rr):
    wins = pnl[pnl > 0].sum(); loss = -pnl[pnl < 0].sum()
    pf = wins / loss if loss else float('inf')
    wr = (pnl > 0).mean() * 100
    return pf, wr, pnl.sum(), rr.mean()

TICK = 0.25
print(f"\n{'extra RT slip':>14} {'(ticks/side)':>13} | {'PF_pts':>7} {'PF_R':>6} {'WR%':>5} {'expR':>7} {'net_pts':>9}")
rows = []
for ticks_side in [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0]:
    extra_rt = 2 * ticks_side * TICK           # both legs
    pnl = pnl0 - extra_rt
    rr = pnl / stop
    pf, wr, tot, expr = stats(pnl, rr)
    rows.append((ticks_side, extra_rt, pf))
    print(f"{extra_rt:>14.2f} {ticks_side:>13.1f} | {pf:>7.3f} {pf/ (-pnl[pnl<0].sum()/stop[pnl<0].sum() if False else 1):>6.3f} {wr:>5.1f} {expr:>7.4f} {tot:>9.0f}")

# PF_R breakeven scan (fine)
print("\nfine breakeven scan (PF_pts crossing 1.0):")
prev = None
for i in range(0, 120):
    extra_rt = i * 0.25
    pnl = pnl0 - extra_rt
    wins = pnl[pnl > 0].sum(); loss = -pnl[pnl < 0].sum()
    pf = wins / loss if loss else 9.9
    if pf < 1.0:
        print(f"  PF crosses 1.0 at extra RT = {extra_rt:.2f}pt = {extra_rt/2/TICK:.1f} ticks/side "
              f"({extra_rt/2:.3f}pt/side); PF={pf:.3f}")
        break
    prev = extra_rt
print(f"  (last PF>=1.0 at extra RT = {prev:.2f}pt = {prev/2/TICK:.1f} ticks/side)")
