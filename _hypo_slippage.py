"""Slippage/market-impact haircut on the $50k-live-compounding hypothetical (operator 2026-07-04).

Same frozen stream (A/Exit#3/D1c, 1m-truth). Same 2.4% size-to-risk fraction, compounding.
Now charge realistic execution cost, split into two parts:

  * BASE spread/latency  = `base_pts` points per round trip (cross the spread on entry retest
    + stop/target exit). In R this is base_pts / stop_pts — SIZE-INDEPENDENT (bigger size costs
    more $ but risks more $; the ratio is fixed).

  * MARKET IMPACT = `imp_per100` points of adverse fill per 100 NQ contracts, per round trip.
    You must move q_nq contracts; walking the book costs points that GROW with size. In R:
    (imp_per100/100) * q_nq / stop_pts  — and q_nq = (f*equity)/(stop_pts*$20), so impact rises
    as the account compounds and as stops tighten. THIS is the realistic drag the ideal model omits.

per-trade:  R_net = R - base_pts/stop_pts - (imp_per100/100)*q_nq/stop_pts
            equity *= (1 + f * R_net)
NQ = $20/pt.  stop_pts = risk_usd/2  (risk_usd is per-MNQ = stop_pts*$2, from the real stream).

Parametric, not measured — live fill quality is the standing #1 unknown. We bracket mild/mod/severe.
"""
import os, sys, warnings, json
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import strategy_engine_profileA as E
import config, run_d1c_real as RD, apex_eval_eod_databento as DB
from tools_1m_truth_recert import M1Map
from tools_phase3_config_sweep import a_streams_d1c

START, F, PT = 50_000.0, 0.024, 20.0     # $50k, frozen 2.4% risk, NQ $/pt

print("loading frozen A/Exit#3/D1c stream (1m-truth)…", flush=True)
d1 = RD.load_1m()
if d1.index.tz is not None: d1 = d1.tz_localize(None)
df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
rows, _ = a_streams_d1c(eng._features(), mp, RD.load_1m())["exit3"]
tr = sorted([(pd.Timestamp(r["ts"]), float(r["R"]), float(r["risk_usd"])) for r in rows],
            key=lambda x: x[0])
yrs = sorted({t.year for t, _, _ in tr})
print(f"  {len(tr)} trades, {tr[0][0].date()}->{tr[-1][0].date()}  median stop = "
      f"{np.median([ru/2 for _,_,ru in tr]):.1f} pts")


def run(base_pts, imp_per100, f=F):
    eq, peak, mdd = START, START, 0.0
    yr = {y: dict(s=None, pnl=0.0, n=0, slip=0.0, q=[]) for y in yrs}
    tot_slip = 0.0
    for (t, R, ru) in tr:
        y = t.year
        if yr[y]["s"] is None: yr[y]["s"] = eq
        stop_pts = ru / 2.0
        D = f * eq                               # dollar risk this trade
        q_nq = D / (stop_pts * PT)               # contracts you must move
        hair_R = base_pts / stop_pts + (imp_per100 / 100.0) * q_nq / stop_pts
        R_net = R - hair_R
        pnl = f * R_net * eq
        slip_usd = f * hair_R * eq
        eq += pnl; tot_slip += slip_usd
        peak = max(peak, eq); mdd = max(mdd, (peak - eq) / peak)
        yr[y]["pnl"] += pnl; yr[y]["n"] += 1; yr[y]["slip"] += slip_usd; yr[y]["q"].append(q_nq)
    rowsout = []
    for y in yrs:
        d = yr[y]
        rowsout.append((y, d["s"], d["pnl"], d["s"] + d["pnl"], d["n"], d["slip"],
                        float(np.median(d["q"]))))
    return rowsout, eq, 100 * mdd, tot_slip


# idealized ceiling (no slippage at all) for reference
_, ideal_end, _, _ = run(0, 0)
print(f"\nIDEAL ceiling (zero slippage), 2.4% compounding: end = {ideal_end:,.0f}  ({ideal_end/START:.1f}x)")

SCEN = [
    ("MILD    (base 0.25pt · impact 0.5pt/100NQ)", 0.25, 0.5),
    ("MODERATE(base 0.50pt · impact 1.5pt/100NQ)  <-- realistic middle", 0.50, 1.5),
    ("SEVERE  (base 0.75pt · impact 4.0pt/100NQ)", 0.75, 4.0),
]
summary = {}
for name, b, imp in SCEN:
    ro, end, mdd, slip = run(b, imp)
    summary[name] = (end, mdd, slip)
    print(f"\n================ {name} ================")
    print(f"{'year':>6}{'start$':>14}{'made$':>14}{'end$':>14}{'trades':>7}{'slip$':>12}{'medNQ':>7}")
    for y, s, p, e, n, sl, q in ro:
        print(f"{y:>6}{s:>14,.0f}{p:>+14,.0f}{e:>14,.0f}{n:>7}{sl:>-12,.0f}{q:>7.0f}")
    print(f"  5yr made = {end-START:+,.0f}   end = {end:,.0f}   ({end/START:.1f}x)   "
          f"maxDD={mdd:.1f}%   total slippage paid = {slip:,.0f}")

print("\n================ BRACKET SUMMARY (2.4% compounding, $50k start) ================")
print(f"  {'IDEAL (0 slippage) ceiling':<44} {ideal_end:>14,.0f}   {ideal_end/START:>6.1f}x")
for name, b, imp in SCEN:
    end, mdd, slip = summary[name]
    print(f"  {name.split('(')[0].strip():<44} {end:>14,.0f}   {end/START:>6.1f}x")
print(f"  {'LINEAR floor (fixed $1,200, ~0 impact)':<44} {270731:>14,.0f}   {270731/START:>6.1f}x")

json.dump({"ideal_end": ideal_end,
           "scenarios": {n: {"end": summary[n][0], "maxdd": summary[n][1], "slip": summary[n][2]}
                         for n in summary}},
          open("reports/_hypo_slippage.json", "w"), indent=1)
print("\nwrote reports/_hypo_slippage.json")
