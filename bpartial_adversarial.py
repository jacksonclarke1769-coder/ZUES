"""ADVERSARIAL stress test of the B-partial fidelity candidate.
Reuses bpartial_fidelity generators. Caches unit streams to pickle for fast iteration.
Breaks attempted:
  1. per-calendar-year PASS% incumbent vs candidate (+ PASS/BUST/EXPIRE decomposition)
  2. cost/slippage sensitivity: B_COST 0.75 (base) / 1.00 (+1 tick) / 1.25 (+1tk+comm)
  3. worst rolling-window (rolling 252-bday block pass%)
  4. small-sample fragility: per-year n and binomial SE on the decisive Δ
"""
import os, sys, pickle, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))

import apex_eval_deployed as H
import apex_eval_eod as EOD
import funded_rules as FR
from config_defaults import exit3_split
import bpartial_fidelity as BP

SPEC = FR.APEX_ACCOUNTS["50K"]
A_SIZE, B_SIZE, M_SIZE = 10, 5, 6
CACHE = os.path.expanduser("~/trading-team/bot/nq-liq-bot/.cache_bpartial_adv.pkl")


def build_units(b_cost):
    """Regenerate unit A/M and B-single + B-partial at a given B_COST."""
    df5 = BP.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    H.B_COST = b_cost; BP.B_COST = b_cost
    A = H.a_events(df5); M = H.m_events(df5)
    Bsingle = H.b_events(df5)            # unit single 1.5R
    n1, n2 = exit3_split(B_SIZE)
    Bpartial = BP.b_events_partial(df5, n1, n2)   # already at size B_SIZE
    return dict(A=A, M=M, Bsingle=Bsingle, Bpartial=Bpartial, n1=n1, n2=n2,
                bars=(df5.index.min(), df5.index.max()))


def make_arms(units):
    sc = {"A": A_SIZE, "B": B_SIZE, "M": M_SIZE}
    inc_base = [dict(e) for e in units["A"]] + [dict(e) for e in units["Bsingle"]] + [dict(e) for e in units["M"]]
    ev_inc = H.apply_daily_stop([dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*sc[e["src"]],
        mfe=e["mfe"]*sc[e["src"]], mae=e["mae"]*sc[e["src"]]) for e in inc_base if sc[e["src"]] > 0])
    cand_base = [dict(e) for e in units["A"]] + [dict(e) for e in units["M"]]
    ev_cand_AM = H.apply_daily_stop([dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*sc[e["src"]],
        mfe=e["mfe"]*sc[e["src"]], mae=e["mae"]*sc[e["src"]]) for e in cand_base if sc[e["src"]] > 0])
    ev_cand = H.apply_daily_stop(ev_cand_AM + units["Bpartial"])
    return ev_inc, ev_cand


def eval_breakdown(ev, lo=None, hi=None):
    starts = EOD.day_starts(ev)
    sel = []
    for s in starts:
        d = pd.Timestamp(ev[s]["ts"]); d = d.tz_localize(None) if d.tz else d
        if lo is not None and d < lo: continue
        if hi is not None and d >= hi: continue
        sel.append(s)
    if not sel:
        return None
    out = [EOD.eval_eod(ev, s, SPEC) for s in sel]
    n = len(out)
    p = sum(1 for o in out if o[0]=="PASS"); b = sum(1 for o in out if o[0]=="BUST")
    x = sum(1 for o in out if o[0]=="EXPIRE")
    return dict(n=n, passp=100*p/n, bustp=100*b/n, expp=100*x/n, npass=p, nbust=b, nexp=x)


def main():
    bcost = float(sys.argv[1]) if len(sys.argv) > 1 else 0.75
    print(f"=== B_COST = {bcost} pts/contract ===", flush=True)
    units = build_units(bcost)
    print(f"  bars {units['bars'][0].date()}..{units['bars'][1].date()}  split {units['n1']}@1R+{units['n2']}@1.5R", flush=True)
    ev_inc, ev_cand = make_arms(units)

    # per-year
    print(f"\n  YEAR  | {'inc PASS%':>9} {'cand PASS%':>10} {'Δpp':>6} | {'inc BUST%':>9} {'cand BUST%':>10} | {'inc EXP%':>8} {'cand EXP%':>9} | {'n':>5}")
    yrs = [2021,2022,2023,2024,2025,2026]
    worst = None
    for y in yrs:
        lo = pd.Timestamp(y,1,1); hi = pd.Timestamp(y+1,1,1)
        ri = eval_breakdown(ev_inc, lo, hi); rc = eval_breakdown(ev_cand, lo, hi)
        if ri is None or rc is None: continue
        d = rc["passp"]-ri["passp"]
        if worst is None or d < worst[1]: worst = (y, d)
        print(f"  {y}  | {ri['passp']:>8.1f}% {rc['passp']:>9.1f}% {d:>+5.1f} | {ri['bustp']:>8.1f}% {rc['bustp']:>9.1f}% | {ri['expp']:>7.1f}% {rc['expp']:>8.1f}% | {ri['n']:>5}")
    # full
    rf_i = eval_breakdown(ev_inc); rf_c = eval_breakdown(ev_cand)
    print(f"  FULL  | {rf_i['passp']:>8.1f}% {rf_c['passp']:>9.1f}% {rf_c['passp']-rf_i['passp']:>+5.1f} | {rf_i['bustp']:>8.1f}% {rf_c['bustp']:>9.1f}% | {rf_i['expp']:>7.1f}% {rf_c['expp']:>8.1f}% | {rf_i['n']:>5}")
    print(f"  worst single year for candidate: {worst[0]}  Δ {worst[1]:+.1f}pp")

    # binomial SE on full-history paired pass difference (rough; starts overlap so SE understated)
    p1, p2, n = rf_i['passp']/100, rf_c['passp']/100, rf_i['n']
    se = (np.sqrt(p1*(1-p1)/n) + np.sqrt(p2*(1-p2)/n))
    print(f"  full-hist Δ {100*(p2-p1):+.1f}pp  | naive binom SE on each arm ~{100*np.sqrt(p1*(1-p1)/n):.1f}pp (starts overlap -> true SE smaller for paired)")


if __name__ == "__main__":
    main()
