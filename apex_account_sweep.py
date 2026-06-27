"""Does a BIGGER Apex account pass the eval higher? 50K/100K/150K under EOD + Databento.
Each account needs proportionally bigger sizing to hit its (bigger) target inside 30 days; its trail
scales sub-linearly (worse target/trail ratio) BUT its floor locks earlier in the grind (bust-proofs the
back half). Net is non-obvious -> sweep each account's sizing and report the best achievable pass rate."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB
import funded_rules as FR

EXPIRE = 30
ACCTS = {"50K": FR.APEX_ACCOUNTS["50K"], "100K": FR.APEX_ACCOUNTS["100K"], "150K": FR.APEX_ACCOUNTS["150K"]}
SCALES = [1.0, 1.5, 2.0, 2.5, 3.0]


def eval_acct(ev, start, sizing, sb, trail, target, daily_stop):
    thr = sb - trail; bal = sb; peak = sb; locked = False; lock_lvl = sb + 100.0
    t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0
    for i in range(start, len(ev)):
        e = ev[i]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if day != cur:
            if cur is not None:
                if (ts - t0).days > EXPIRE:
                    return "EXPIRE"
                peak = max(peak, bal)
                if not locked:
                    thr = max(thr, peak - trail)
                    if peak - trail >= lock_lvl:
                        thr = lock_lvl; locked = True
            cur = day; dreal = 0.0
        if dreal <= daily_stop:
            continue
        s = sizing.get(e["src"], 0)
        if s == 0:
            continue
        if bal + min(0.0, e["mae"]) * s <= thr:
            return "BUST"
        bal += e["pnl"] * s; dreal += e["pnl"] * s
        if bal >= sb + target:
            return "PASS"
    return "INCOMPLETE"


def main():
    print("loading Databento + streams…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    ev = sorted(H.a_events(df5) + H.b_events(df5) + H.m_events(df5), key=lambda e: e["ts"])
    seen, st = set(), []; last = pd.Timestamp(ev[-1]["ts"])
    for i, e in enumerate(ev):
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - pd.Timestamp(e["ts"])).days > EXPIRE:
            st.append(i)

    print(f"\n  === ACCOUNT-SIZE eval sweep (EOD + Databento; sizing scaled k×(A10/B5/mm6), stop −$550×k) ===")
    print(f"  {'acct':>6}{'trail/target':>15}{'  best sizing (MNQ)':>22}{'PASS%':>8}{'BUST%':>8}{'EXP%':>7}")
    for name, spec in ACCTS.items():
        sb, tr, tg = spec["start"], spec["trailing"], spec["target"]
        best = None
        for k in SCALES:
            a, b, m = round(10*k), round(5*k), round(6*k)
            sizing = {"A": a, "B": b, "M": m}
            ds = -550.0 * k
            res = [eval_acct(ev, s, sizing, sb, tr, tg, ds) for s in st]
            n = len(res)
            p = 100*sum(1 for r in res if r == "PASS")/n
            bu = 100*sum(1 for r in res if r == "BUST")/n
            x = 100*sum(1 for r in res if r == "EXPIRE")/n
            if best is None or p > best[0]:
                best = (p, bu, x, a, b, m)
        p, bu, x, a, b, m = best
        print(f"  {name:>6}{f'${tr/1000:.1f}k/${tg/1000:.0f}k':>15}{f'A{a}/B{b}/mm{m} = {a+b+m}':>22}{p:>8.1f}{bu:>8.1f}{x:>7.1f}")
    print("\n  [note] EOD + Databento. each account's BEST-of-sweep sizing shown. floor-lock modelled (helps bigger accts).")


if __name__ == "__main__":
    main()
