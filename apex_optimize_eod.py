"""HIGHEST-PROBABILITY sizing — EOD rule + real Databento, for BOTH eval (max PASS%) and
funded grind-to-lock (max reach-lock%). Generates streams once, sweeps sizings."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod as EOD
import apex_eval_eod_databento as DB
import funded_rules as FR

SPEC = FR.APEX_ACCOUNTS["50K"]
START, TRAIL, LOCK_EOD, FLOOR = 50_000.0, 2_500.0, 52_600.0, 50_100.0
HORIZON_DAYS, DAILY_STOP = 18 * 30, -550.0

EVAL_GRID = [(10,5,6),(10,5,0),(8,4,5),(8,4,0),(12,6,7),(10,4,6),(10,6,6),(6,3,4),
             (8,5,6),(9,5,6),(11,5,6),(10,5,4),(10,5,8),(8,6,6),(7,4,5),(9,4,5),(8,5,5)]
FUND_GRID = [(4,2),(3,2),(5,3),(3,1),(5,2),(4,3),(2,2),(6,3),(4,1),(2,1),(6,2),(3,3),(7,3)]


def reach_lock(ev, start, pa, pb):
    thr = START - TRAIL; bal = START; peak = START
    t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0; sc = {"A": pa, "B": pb}
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if (ts - t0).days > HORIZON_DAYS:
            return "NOLOCK"
        if cur is None:
            cur = day
        if day != cur:
            peak = max(peak, bal)
            if peak >= LOCK_EOD:
                return "LOCK"
            thr = max(thr, peak - TRAIL); cur = day; dreal = 0.0
        if dreal <= DAILY_STOP:
            continue
        s = sc.get(e["src"], 0)
        if s == 0:
            continue
        if bal + min(0.0, e["mae"]) * s <= thr:
            return "BUST"
        bal += e["pnl"] * s; dreal += e["pnl"] * s
    return "NOLOCK"


def main():
    print("loading Databento + building streams (one-time)…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    A, B, M = H.a_events(df5), H.b_events(df5), H.m_events(df5)
    base_all = A + B + M
    base_ab = sorted(A + B, key=lambda e: e["ts"])
    print(f"  A={len(A)} B={len(B)} mm={len(M)}", flush=True)

    # ---- EVAL: maximise PASS% (EOD, Databento) ----
    print(f"\n  ===== EVAL — highest PASS% (Apex 50K EOD, real Databento, 30-day clock) =====")
    print(f"  {'A/B/mm':>10}{'MNQ':>5}{'PASS%':>8}{'BUST%':>7}{'EXP%':>6}{'med':>5}")
    erows = []
    for (a, b, m) in EVAL_GRID:
        sc = {"A": a, "B": b, "M": m}
        ev = [dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*sc[e["src"]],
                   mfe=e["mfe"]*sc[e["src"]], mae=e["mae"]*sc[e["src"]]) for e in base_all if sc[e["src"]] > 0]
        ev = H.apply_daily_stop(ev)
        st = EOD.day_starts(ev)
        p, bu, x, md = EOD.summarize([EOD.eval_eod(ev, s, SPEC) for s in st])
        erows.append((a, b, m, p, bu, x, md))
    for (a, b, m, p, bu, x, md) in sorted(erows, key=lambda r: -r[3]):
        star = " <-DEPLOYED" if (a, b, m) == (10, 5, 6) else ""
        print(f"  {f'{a}/{b}/{m}':>10}{a+b+m:>5}{p:>8.1f}{bu:>7.1f}{x:>6.1f}{md or 0:>5}{star}")
    be = max(erows, key=lambda r: r[3])
    print(f"  -> best eval PASS%: A{be[0]}/B{be[1]}/mm{be[2]} = {be[3]:.1f}%")

    # ---- FUNDED: maximise P(reach lock) (EOD, Databento) ----
    print(f"\n  ===== FUNDED grind-to-lock — highest P(reach lock) (EOD, real Databento) =====")
    print(f"  {'A/B(pre)':>10}{'MNQ':>5}{'LOCK%':>8}{'BUST%':>7}{'noLock%':>9}{'medDays':>9}")
    last = pd.Timestamp(base_ab[-1]["ts"]); seen, fstarts = set(), []
    for i, e in enumerate(base_ab):
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - pd.Timestamp(e["ts"])).days >= 270:
            fstarts.append(i)
    frows = []
    for (pa, pb) in FUND_GRID:
        res = [reach_lock(base_ab, s, pa, pb) for s in fstarts]
        n = len(res)
        lk = 100*sum(1 for r in res if r == "LOCK")/n
        bu = 100*sum(1 for r in res if r == "BUST")/n
        nl = 100*sum(1 for r in res if r == "NOLOCK")/n
        frows.append((pa, pb, lk, bu, nl))
    for (pa, pb, lk, bu, nl) in sorted(frows, key=lambda r: -r[2]):
        star = " <-DEPLOYED" if (pa, pb) == (4, 2) else ""
        print(f"  {f'{pa}/{pb}':>10}{pa+pb:>5}{lk:>8.1f}{bu:>7.1f}{nl:>9.1f}{'':>9}{star}")
    bf = max(frows, key=lambda r: r[2])
    print(f"  -> best funded reach-lock: A{bf[0]}/B{bf[1]} = {bf[2]:.1f}%")
    print("\n  [note] EOD + real Databento. 'highest probability' = max PASS / max reach-lock (NOT max throughput/EV).")


if __name__ == "__main__":
    main()
