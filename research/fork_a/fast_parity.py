"""FAST full-581 parity for the BUILT surface-at-MSS emit path.

Features are causal (bar i's value is independent of bars > i -- PROVEN by the truncation canary,
581/581 exact). So slicing the ONCE-built full feature frame at feats.iloc[:mss_bar+1] is identical
to rebuilding features on raw data truncated at the mss_bar close, but ~581x faster. On each slice we
call the BUILT realtime emit (surface_at_mss.latest_mss_emission) and compare its emission to the
certified reference. This reproduces the same test as build_surface_mss_verify.py --full without the
per-signal feature rebuild.
"""
import json, os, sys, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

BOT = os.path.expanduser("~/trading-team/bot/nq-liq-bot")
FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
for p in (os.path.join(FW, "engine"), os.path.join(FW, "models"),
          os.path.expanduser("~/trading-team/backtests"), FW, BOT):
    if p not in sys.path:
        sys.path.insert(0, p)
import model01_sweep_mss_fvg as M1
import apex_eval_eod_databento as DB
from strategy_engine_profileA import ProfileAEngine
from tools_1m_truth_recert import A_PARAMS
import surface_at_mss as SM

REF = os.path.expanduser("~/trading-team/research/atlas/profile_a_edge/outputs/signals_583_classified.csv")
OUT = os.path.join(BOT, "reports", "fork_a")
PARAMS = {**M1.DEFAULT_PARAMS, **A_PARAMS["exit3"]}
STRAT = {"nyam_start_min": 570, "nyam_end_min": 690, "flat_min": 870}

ref = pd.read_csv(REF, parse_dates=["ts"])
tp = ref[ref["class"].isin(["FULLY-AVAILABLE", "DELAYED"])].copy().reset_index(drop=True)
print(f"[fast] FULLY+DELAYED = {len(tp)}", flush=True)
print("[fast] building FULL feats once ...", flush=True)
eng = ProfileAEngine(STRAT); eng.buf = DB.load_databento_5m()
feats = eng._features(); n = len(feats)
print(f"[fast] full feats bars = {n}", flush=True)

# No-overlap anchor lookup: model01.run()'s free bar (one past the prior trade's exit) keyed by the
# current trade's mss_bar. This is the SAME value surface_at_mss._anchor_from_run() computes on the
# truncated slice (proven identical: prior trades are all left of the edge; run(realtime True) on a
# slice reserves only the current setup). Precomputed once here so the 581-slice sweep is fast; the
# stateless self-contained path (start_bar=None -> internal run) is validated by the canary.
print("[fast] building no-overlap anchor timeline (one backtest run) ...", flush=True)
alltr = M1.run(feats, "NQ", PARAMS)           # realtime=False backtest, all sessions
alltr = alltr.sort_values("sweep_bar").reset_index(drop=True)
free_by_mss = {}; prev_exit = -1
for _, t in alltr.iterrows():
    free_by_mss[int(t["mss_bar"])] = prev_exit + 1
    prev_exit = int(t["exit_bar"])

rows = []
for _, r in tp.iterrows():
    mss_bar = int(r["mss_bar"]); fill_bar = int(r["fill_bar"]); sweep_bar = int(r["sweep_bar"])
    if not (0 <= mss_bar < n):
        rows.append(dict(signal_id=r["signal_id"], status="BAD-INDEX", R=float(r["R"]),
                         gap_sm=mss_bar - sweep_bar)); continue
    sl = feats.iloc[:mss_bar + 1]            # buffer ending exactly at mss_bar close (n=mss_bar+1)
    emis = SM.latest_mss_emission(sl, PARAMS, start_bar=free_by_mss.get(mss_bar))
    if emis is None:
        rows.append(dict(signal_id=r["signal_id"], status="NO-EMIT-AT-K", R=float(r["R"]),
                         gap_sm=mss_bar - sweep_bar, gap_mf=fill_bar - mss_bar)); continue
    e_ok = abs(float(r["entry"]) - emis["entry"]) < 1e-6
    s_ok = abs(float(r["stop"]) - emis["stop"]) < 1e-6
    t_ok = abs(float(r["target"]) - emis["target"]) < 1e-6
    d_ok = (r["direction"] == emis["direction"])
    emit_bar = len(sl) - 1                    # emission is on last bar of the slice
    k_ok = (emit_bar == mss_bar)              # emitted at k (the mss bar itself), not k+1
    sweep_ok = (emis["sweep_bar"] == sweep_bar)
    allok = e_ok and s_ok and t_ok and d_ok and k_ok
    rows.append(dict(signal_id=r["signal_id"], class_=r["class"],
                     status="MATCH-AT-K" if allok else "MISMATCH",
                     entry_ok=e_ok, stop_ok=s_ok, target_ok=t_ok, direction_ok=d_ok, k_ok=k_ok,
                     sweep_ok=sweep_ok, emit_bar=emit_bar, mss_bar=mss_bar, fill_bar=fill_bar,
                     gap_sm=mss_bar - sweep_bar, gap_mf=fill_bar - mss_bar, R=float(r["R"]),
                     entry_ref=float(r["entry"]), entry_emit=emis["entry"],
                     stop_ref=float(r["stop"]), stop_emit=emis["stop"],
                     target_ref=float(r["target"]), target_emit=emis["target"]))

out = pd.DataFrame(rows)
out.to_csv(os.path.join(OUT, "03_fast_parity.csv"), index=False)
nm = int((out["status"] == "MATCH-AT-K").sum())
nmis = int((out["status"] == "MISMATCH").sum())
nne = int((out["status"] == "NO-EMIT-AT-K").sum())
nbad = int((out["status"] == "BAD-INDEX").sum())
n_emit_k = int(out.get("k_ok", pd.Series(dtype=bool)).sum())
m = out[out["status"] == "MATCH-AT-K"]
def pf(x):
    w = x[x["R"] > 0]["R"].sum(); l = -x[x["R"] < 0]["R"].sum()
    return round(w / l, 4) if l > 0 else float("inf")
# honest fill PF of the matched (emit-at-k) population = certified 1m-truth R stream
summ = dict(n=len(out), match_at_k=nm, mismatch=nmis, no_emit=nne, bad_index=nbad,
            all_emit_at_k=(n_emit_k == nm and nm > 0),
            gap1_matched=int((m["gap_sm"] == 1).sum()), gap_ge2_matched=int((m["gap_sm"] >= 2).sum()),
            honest_fill=dict(n=len(m), sumR=round(float(m["R"].sum()), 3), PF=pf(m),
                             WR=round(float((m["R"] > 0).mean()), 4)),
            sweep_match=int(out.get("sweep_ok", pd.Series(dtype=bool)).sum()))
if nmis or nne:
    bad = out[out["status"].isin(["MISMATCH", "NO-EMIT-AT-K"])]
    summ["bad_examples"] = bad.head(25).to_dict("records")
json.dump(summ, open(os.path.join(OUT, "03_fast_parity_summary.json"), "w"), indent=2, default=str)
print("\n===== FAST FULL-581 PARITY =====", flush=True)
print(json.dumps({k: v for k, v in summ.items() if k != "bad_examples"}, indent=2, default=str), flush=True)
if "bad_examples" in summ:
    print("\nBAD EXAMPLES (first 25):", flush=True)
    for b in summ["bad_examples"]:
        print(" ", {k: b.get(k) for k in ("signal_id","status","gap_sm","gap_mf","entry_ref","entry_emit","stop_ref","stop_emit","sweep_ok")}, flush=True)
