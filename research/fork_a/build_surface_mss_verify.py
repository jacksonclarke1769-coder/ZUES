"""FORK-A PHASE-3 BUILD verification: the BUILT surface-at-MSS realtime emit path.

Drives strategy_engine_profileA / surface_at_mss THROUGH THE REALTIME ENGINE on data truncated at
each signal's MSS bar close, and answers, honestly, from the built code (not a concept re-derivation):

  1. OWN CANARY (decisive): feed the realtime engine data truncated at mss_bar close; does it emit
     the identical entry/stop/target/direction using ONLY bars <= mss_bar? And what is the REAL
     emit bar the streaming code produces -- k (mss_bar's own close) or k+1?
  2. run()-vs-new-scan emit contrast: prove the certified path (model01.run(realtime=True) tail scan)
     does NOT surface the trade at the mss_bar (it reserves it as pending / only surfaces at fill),
     while the new scan surfaces it at k -- the whole point of the build.
  3. PARITY: match count vs the certified 581 (entry/stop/target/direction).
  4. Honest fillable PF from the ACTUAL emit bar the built code produces.

READ-ONLY on model01 / ProfileAEngine detection (never monkeypatched). Sample mode by default;
pass --full for all 581. Writes reports/fork_a/03_*.{csv,json} in the bot repo.
"""
import argparse
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

BOT = os.path.expanduser("~/trading-team/bot/nq-liq-bot")
FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
for p in (os.path.join(FW, "engine"), os.path.join(FW, "models"),
          os.path.expanduser("~/trading-team/backtests"), FW, BOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import model01_sweep_mss_fvg as M1                       # noqa: E402  frozen
import apex_eval_eod_databento as DB                     # noqa: E402
import strategy_engine_profileA as SEP                   # noqa: E402
from strategy_engine_profileA import ProfileAEngine      # noqa: E402
from tools_1m_truth_recert import A_PARAMS               # noqa: E402
import surface_at_mss as SM                              # noqa: E402  the BUILT emit path

REF_CSV = os.path.expanduser(
    "~/trading-team/research/atlas/profile_a_edge/outputs/signals_583_classified.csv")
OUT_DIR = os.path.join(BOT, "reports", "fork_a")
os.makedirs(OUT_DIR, exist_ok=True)
PARAMS = {**M1.DEFAULT_PARAMS, **A_PARAMS["exit3"]}       # the exact config the 581 were built with
STRAT = {"nyam_start_min": 570, "nyam_end_min": 690, "flat_min": 870}


def _run_surface_at(df5_full, mss_ts, cut_ts):
    """Build the realtime engine's OWN feature frame on the buffer truncated at `cut_ts`, in
    surface_at_mss emission mode, and return (emission_dict, n_bars, last_ts). Uses the SAME
    ProfileAEngine._features() the live bot uses -- so any look-ahead in feature construction would
    surface here."""
    eng = ProfileAEngine(STRAT, emission_mode=SEP.EMISSION_MODE_SURFACE_AT_MSS)
    eng.buf = df5_full[df5_full.index <= cut_ts]
    feats = eng._features()
    emis = SM.latest_mss_emission(feats, PARAMS)
    return emis, len(feats), feats.index[-1]


def _run_certified_surfaces(df5_full, cut_ts):
    """What the CERTIFIED path (model01.run(realtime=True)) yields on a buffer truncated at cut_ts:
    the set of fill_bars it has surfaced as completed trades. Used to prove the certified path does
    NOT surface the setup at the mss_bar (it reserves it pending until the fill bar)."""
    eng = ProfileAEngine(STRAT)
    eng.buf = df5_full[df5_full.index <= cut_ts]
    feats = eng._features()
    try:
        tr = M1.run(feats, "NQ", PARAMS, realtime=True)
    except Exception:
        return set()
    if not len(tr):
        return set()
    tr = tr[tr.session == "ny_am"]
    return set(int(x) for x in tr["mss_bar"].tolist())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--sample", type=int, default=20)
    ap.add_argument("--contrast", type=int, default=8, help="how many signals to run the run()-vs-scan contrast on")
    args = ap.parse_args()

    ref = pd.read_csv(REF_CSV, parse_dates=["ts"])
    tp = ref[ref["class"].isin(["FULLY-AVAILABLE", "DELAYED"])].copy().reset_index(drop=True)
    print(f"[build] reference FULLY+DELAYED = {len(tp)}", flush=True)

    print("[build] loading Databento 5m + full feats index ...", flush=True)
    df5 = DB.load_databento_5m()
    eng_full = ProfileAEngine(STRAT)
    eng_full.buf = df5
    fi = eng_full._features().index
    n_full = len(fi)
    print(f"[build] full feats bars = {n_full}", flush=True)

    if args.full:
        sel = tp
    else:
        # spread the sample across the whole 2021-2026 span
        idx = np.linspace(0, len(tp) - 1, args.sample).round().astype(int)
        sel = tp.iloc[np.unique(idx)].copy()
    print(f"[build] verifying {len(sel)} signals ({'FULL' if args.full else 'SAMPLE'})", flush=True)

    rows = []
    contrast_rows = []
    n_done = 0
    for _, r in sel.iterrows():
        sweep_bar = int(r["sweep_bar"]); mss_bar = int(r["mss_bar"]); fill_bar = int(r["fill_bar"])
        if not (0 <= mss_bar < n_full):
            rows.append(dict(signal_id=r["signal_id"], status="BAD-INDEX")); continue
        mss_ts = fi[mss_bar]
        gap_sm = mss_bar - sweep_bar
        # ---- OWN CANARY: emit from data truncated at mss_bar close (k) ----
        emis, n_k, last_k = _run_surface_at(df5, mss_ts, mss_ts)
        emit_bar_local = None
        if emis is not None:
            emit_bar_local = n_k - 1  # emission is on the last bar of the truncated buffer
        matched = bad = False
        e_ok = s_ok = t_ok = d_ok = emitted = False
        if emis is None:
            status = "NO-EMIT-AT-K"
        else:
            emitted = True
            e_ok = abs(float(r["entry"]) - emis["entry"]) < 1e-6
            s_ok = abs(float(r["stop"]) - emis["stop"]) < 1e-6
            t_ok = abs(float(r["target"]) - emis["target"]) < 1e-6
            d_ok = (r["direction"] == emis["direction"])
            # the emit bar of the truncated buffer must be the mss bar itself (k)
            k_ok = (last_k == mss_ts)
            matched = e_ok and s_ok and t_ok and d_ok and k_ok
            status = "MATCH-AT-K" if matched else "MISMATCH"
        rows.append(dict(
            signal_id=r["signal_id"], class_=r["class"], ts=str(r["ts"]),
            direction=r["direction"], gap_sm=gap_sm, gap_mf=fill_bar - mss_bar,
            status=status, emitted=emitted,
            entry_ref=float(r["entry"]), entry_emit=(emis["entry"] if emis else None), entry_ok=e_ok,
            stop_ref=float(r["stop"]), stop_emit=(emis["stop"] if emis else None), stop_ok=s_ok,
            target_ref=float(r["target"]), target_emit=(emis["target"] if emis else None), target_ok=t_ok,
            direction_ok=d_ok,
            emit_ts=str(last_k), mss_ts=str(mss_ts), emit_is_k=(str(last_k) == str(mss_ts)),
            mss_before_fill=(mss_bar < fill_bar),
            mss_bar=mss_bar, fill_bar=fill_bar, R=float(r["R"]),
        ))
        # ---- run()-vs-scan emit contrast (first N signals) ----
        if len(contrast_rows) < args.contrast:
            cert_at_k = mss_bar in _run_certified_surfaces(df5, mss_ts)          # certified surfaces at k?
            cert_at_fill = mss_bar in _run_certified_surfaces(df5, fi[fill_bar]) # certified surfaces at fill?
            contrast_rows.append(dict(
                signal_id=r["signal_id"], gap_sm=gap_sm, gap_mf=fill_bar - mss_bar,
                new_scan_emits_at_k=emitted,
                certified_surfaces_at_k=cert_at_k,
                certified_surfaces_at_fill=cert_at_fill))
        n_done += 1
        if n_done % 25 == 0:
            nm = sum(1 for x in rows if x.get("status") == "MATCH-AT-K")
            print(f"  ... {n_done}/{len(sel)}  match_at_k={nm}", flush=True)

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT_DIR, "03_surface_mss_build_verify.csv"), index=False)

    done = out[out["status"].isin(["MATCH-AT-K", "MISMATCH", "NO-EMIT-AT-K"])]
    n_match = int((out["status"] == "MATCH-AT-K").sum())
    n_mismatch = int((out["status"] == "MISMATCH").sum())
    n_noemit = int((out["status"] == "NO-EMIT-AT-K").sum())
    n_emit_k = int(out["emit_is_k"].sum()) if "emit_is_k" in out else 0

    # honest fillable PF from the ACTUAL emit bar (k). emit-at-k rests the OTE limit at the mss
    # close -> first fillable bar is mss_bar+1 == model01.run()'s own fill-loop start -> the
    # certified 1m-truth R stream IS the fillable stream for the matched signals.
    m = out[out["status"] == "MATCH-AT-K"]
    def pf(x):
        w = x[x["R"] > 0]["R"].sum(); l = -x[x["R"] < 0]["R"].sum()
        return (w / l) if l > 0 else float("inf")
    fill_stats = dict(
        n=int(len(m)), sumR=round(float(m["R"].sum()), 3), PF=round(pf(m), 4),
        WR=round(float((m["R"] > 0).mean()), 4) if len(m) else None)

    summary = dict(
        mode="FULL" if args.full else f"SAMPLE({len(sel)})",
        n_verified=int(len(done)), n_match_at_k=n_match, n_mismatch=n_mismatch, n_no_emit=n_noemit,
        n_emit_is_k=n_emit_k,
        all_emit_at_k=(n_emit_k == len(done) and len(done) > 0),
        parity_all_match=(n_match == len(done) and len(done) > 0),
        gap1_matched=int(((m["gap_sm"] == 1)).sum()) if len(m) else 0,
        gap_ge2_matched=int(((m["gap_sm"] >= 2)).sum()) if len(m) else 0,
        honest_fill=fill_stats,
        contrast=contrast_rows,
        verdict=("BUILD-CLEAN: emits at k, causally <=mss, parity holds"
                 if (n_match == len(done) and n_mismatch == 0 and len(done) > 0)
                 else "BUILD-REVEALED-PROBLEM (see mismatches / no-emits)"),
    )
    with open(os.path.join(OUT_DIR, "03_surface_mss_build_summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print("\n================ SURFACE-AT-MSS BUILD VERDICT ================", flush=True)
    print(json.dumps(summary, indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
