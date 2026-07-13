"""Diagnose the 25 sweep-pairing mismatches: does the reference sweep correspond to the ASCENDING
(earliest reclaim, largest gap) or DESCENDING (latest reclaim, smallest gap) valid sweep that
confirms MSS at `last`? For each signal, on the full-feats slice ending at mss_bar, enumerate ALL
sweep bars i in [last-W_MSS, last-1] whose frozen _detect gives mss_bar==last, and see which pick
(first-ascending vs first-descending vs 'the one matching ref sweep_bar') reproduces the certified
entry/stop/target."""
import os, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
BOT = os.path.expanduser("~/trading-team/bot/nq-liq-bot")
FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
for p in (os.path.join(FW, "engine"), os.path.join(FW, "models"),
          os.path.expanduser("~/trading-team/backtests"), FW, BOT):
    if p not in sys.path: sys.path.insert(0, p)
import model01_sweep_mss_fvg as M1
import apex_eval_eod_databento as DB
from strategy_engine_profileA import ProfileAEngine
from tools_1m_truth_recert import A_PARAMS
import surface_at_mss as SM

REF = os.path.expanduser("~/trading-team/research/atlas/profile_a_edge/outputs/signals_583_classified.csv")
PARAMS = {**M1.DEFAULT_PARAMS, **A_PARAMS["exit3"]}
STRAT = {"nyam_start_min":570,"nyam_end_min":690,"flat_min":870}
ref = pd.read_csv(REF, parse_dates=["ts"])
tp = ref[ref["class"].isin(["FULLY-AVAILABLE","DELAYED"])].copy().reset_index(drop=True)
eng = ProfileAEngine(STRAT); eng.buf = DB.load_databento_5m()
feats = eng._features(); n = len(feats)
print(f"feats bars {n}", flush=True)

def all_sweeps_for_last(pre, last):
    """every sweep bar i whose _detect confirms mss==last, with its emission."""
    out = []
    for i in range(max(2,last-M1.W_MSS), last):
        if not SM._allowed_trigger(pre, i): continue
        setup = SM._detect_at(pre, i)
        if setup is None or setup[5] != last: continue
        emis = SM._emission_from_setup(pre, setup, i)
        if emis is not None:
            out.append((i, emis))
    return out

asc=desc=refpick=multi=0; tot=0
mismatch_multi=0
for _, r in tp.iterrows():
    mss=int(r["mss_bar"]); sw=int(r["sweep_bar"])
    if not (0<=mss<n): continue
    tot+=1
    sl=feats.iloc[:mss+1]
    pre=SM._preamble(sl, PARAMS)
    cands=all_sweeps_for_last(pre, mss)
    if not cands: continue
    if len(cands)>1: multi+=1
    def ok(emis):
        return (abs(float(r["entry"])-emis["entry"])<1e-6 and abs(float(r["stop"])-emis["stop"])<1e-6
                and abs(float(r["target"])-emis["target"])<1e-6 and r["direction"]==emis["direction"])
    if ok(cands[0][1]): asc+=1                    # ascending-first (current impl)
    if ok(cands[-1][1]): desc+=1                  # descending-first (latest reclaim)
    # does ANY candidate match ref sweep_bar exactly?
    if any(c[0]==sw and ok(c[1]) for c in cands): refpick+=1
    elif len(cands)>1: mismatch_multi+=1

print(f"total={tot}")
print(f"ascending-first (current) matches ref e/s/t/d : {asc}")
print(f"descending-first (latest reclaim) matches ref : {desc}")
print(f"ref sweep_bar present among candidates & matches: {refpick}")
print(f"signals with >1 candidate sweep at last-bar    : {multi}")
print(f"mismatch where ref-sweep NOT among candidates   : {tot-refpick}")
