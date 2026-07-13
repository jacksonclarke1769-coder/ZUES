"""OPTIMIZED full-581 parity + no-overlap diagnosis.

Preamble arrays (displacement/swings/FVGs/levels) are causal, so we build them ONCE on full feats
and SLICE per signal (seconds vs minutes). Then, per certified signal, evaluate:
  (A) STATELESS emit (current default): scan the W_MSS window, first sweep whose MSS==last.
  (B) NO-OVERLAP emit: pass start_bar = the bar the bot became flat (one past the prior trade's
      exit, from model01.run()'s OWN trade timeline) -> reproduces run()'s sweep-pairing.
Reports match counts for both and confirms the reference sweep is always a reproducible candidate
(so the 25 stateless misses are purely a no-overlap SELECTION effect, not an emission-math error).
"""
import json, os, sys, warnings
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
OUT = os.path.join(BOT, "reports", "fork_a")
PARAMS = {**M1.DEFAULT_PARAMS, **A_PARAMS["exit3"]}
STRAT = {"nyam_start_min":570,"nyam_end_min":690,"flat_min":870}

ref = pd.read_csv(REF, parse_dates=["ts"])
tp = ref[ref["class"].isin(["FULLY-AVAILABLE","DELAYED"])].copy().reset_index(drop=True)
eng = ProfileAEngine(STRAT); eng.buf = DB.load_databento_5m()
feats = eng._features(); n = len(feats)
print(f"[opt] feats bars {n}", flush=True)

# full preamble ONCE
full = SM._preamble(feats, PARAMS)
ARR_KEYS = ["o","h","l","c","ds","sh_at","sl_at","fdir","fmid","fbot","ftop","sess","mins"]

def sliced_pre(last):
    """A pre-dict for a buffer ending exactly at `last` (n=last+1), by slicing the causal full
    arrays -- identical to rebuilding on truncated data (features are causal)."""
    pre = dict(full)
    for k in ARR_KEYS:
        pre[k] = full[k][:last+1]
    pre["L"] = {nm: v[:last+1] for nm, v in full["L"].items()}
    pre["Sx"] = {nm: v[:last+1] for nm, v in full["Sx"].items()}
    pre["n"] = last+1
    return pre

def emit_from(pre, last, start_bar=None):
    lo = max(2, last - M1.W_MSS)
    if start_bar is not None: lo = max(lo, int(start_bar))
    for i in range(lo, last):
        if not SM._allowed_trigger(pre, i): continue
        setup = SM._detect_at(pre, i)
        if setup is None or setup[5] != last: continue
        e = SM._emission_from_setup(pre, setup, i)
        if e is not None: return e
    return None

# ---- no-overlap timeline from run()'s OWN trades (all sessions; no-overlap spans them) ----
print("[opt] running model01.run() backtest once for the no-overlap timeline ...", flush=True)
alltr = M1.run(feats, "NQ", PARAMS)          # backtest, all sessions
alltr = alltr.sort_values("sweep_bar").reset_index(drop=True)
# free_since[mss_bar] = prior trade's exit_bar + 1 (0 for the first)
prev_exit = -1
free_by_mss = {}
for _, t in alltr.iterrows():
    free_by_mss[int(t["mss_bar"])] = prev_exit + 1
    prev_exit = int(t["exit_bar"])

def ok(r, e):
    return (e is not None and abs(float(r["entry"])-e["entry"])<1e-6 and abs(float(r["stop"])-e["stop"])<1e-6
            and abs(float(r["target"])-e["target"])<1e-6 and r["direction"]==e["direction"])

rows=[]
a=b=refcand=0
for _, r in tp.iterrows():
    mss=int(r["mss_bar"]); sw=int(r["sweep_bar"])
    if not (0<=mss<n): continue
    pre = sliced_pre(mss)
    e_state = emit_from(pre, mss, None)                       # (A) stateless
    fs = free_by_mss.get(mss, None)
    e_nolap = emit_from(pre, mss, fs)                         # (B) no-overlap (flat-since)
    # is the ref sweep reproducible at all? force the scan to consider ONLY the ref sweep bar
    e_refsweep = None
    setup = SM._detect_at(pre, sw)
    if setup is not None and setup[5]==mss:
        e_refsweep = SM._emission_from_setup(pre, setup, sw)
    A = ok(r, e_state); B = ok(r, e_nolap); RC = ok(r, e_refsweep)
    a+=A; b+=B; refcand+=RC
    rows.append(dict(signal_id=r["signal_id"], mss=mss, sw=sw, free_since=fs,
                     stateless_ok=A, nolap_ok=B, refsweep_ok=RC, R=float(r["R"]),
                     gap_sm=mss-sw, gap_mf=int(r["fill_bar"])-mss))

d=pd.DataFrame(rows); d.to_csv(os.path.join(OUT,"03_optimized_parity.csv"), index=False)
tot=len(d)
def pf(x):
    w=x[x["R"]>0]["R"].sum(); l=-x[x["R"]<0]["R"].sum(); return round(w/l,4) if l>0 else float("inf")
m_state=d[d.stateless_ok]; m_nolap=d[d.nolap_ok]
summ=dict(total=tot,
          stateless_match=int(a), stateless_PF=pf(m_state), stateless_sumR=round(float(m_state["R"].sum()),3),
          nooverlap_match=int(b), nooverlap_PF=pf(m_nolap), nooverlap_sumR=round(float(m_nolap["R"].sum()),3),
          refsweep_reproducible=int(refcand),
          nolap_misses=int(tot-b))
if tot-b:
    summ["nolap_miss_examples"]=d[~d.nolap_ok].head(15).to_dict("records")
json.dump(summ, open(os.path.join(OUT,"03_optimized_parity_summary.json"),"w"), indent=2, default=str)
print("\n===== OPTIMIZED PARITY (stateless vs no-overlap) =====", flush=True)
print(json.dumps({k:v for k,v in summ.items() if k!="nolap_miss_examples"}, indent=2, default=str), flush=True)
if tot-b:
    print("NO-OVERLAP MISSES (first 15):", flush=True)
    for x in summ["nolap_miss_examples"]:
        print("  ", {k:x[k] for k in ("signal_id","mss","sw","free_since","gap_sm","refsweep_ok")}, flush=True)
