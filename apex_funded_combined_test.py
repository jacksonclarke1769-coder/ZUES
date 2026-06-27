"""Do the two grind levers STACK? smaller A/B size (A3/B2) + grind momentum (mm2), -> A6/B3/mm6 post-lock.
EOD + Databento. Reports lock%, median days-to-lock (speed), income, E[payout]."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB
import apex_funded_momentum_test as MT

S, TR, LK, FL = MT.START, MT.TRAIL, MT.LOCK_EOD, MT.FLOOR
SAFE, CF, CL, NC, MINP = MT.SAFETY, MT.CAP_FIRST, MT.CAP_LATER, MT.N_CAPPED, MT.MIN_PAYOUT
HOR, DS = MT.HORIZON_DAYS, MT.DAILY_STOP


def life(ev, start, pre, post):
    thr = S - TR; bal = S; peak = S; locked = False; d2l = None
    payout = 0.0; npay = 0; t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0; cmonth = None; last = t0
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize(); last = ts
        if (ts - t0).days > HOR:
            break
        if cur is None:
            cur = day
        if day != cur:
            peak = max(peak, bal)
            if not locked:
                if peak >= LK:
                    thr = FL; locked = True; d2l = (ts - t0).days
                else:
                    thr = max(thr, peak - TR)
            cur = day; dreal = 0.0
        m = (ts.year, ts.month)
        if cmonth is None:
            cmonth = m
        if m != cmonth:
            if locked and bal > SAFE:
                cap = CF if npay < NC else CL
                w = min(bal - SAFE, cap)
                if w >= MINP:
                    bal -= w; payout += w; npay += 1
            cmonth = m
        if dreal <= DS:
            continue
        s = (post if locked else pre).get(e["src"], 0)
        if s == 0:
            continue
        if bal + min(0.0, e["mae"]) * s <= thr:
            return dict(locked=locked, d2l=d2l, payout=payout)
        bal += e["pnl"] * s; dreal += e["pnl"] * s
    return dict(locked=locked, d2l=d2l, payout=payout)


def ev_metrics(ev, fst, pre, post):
    out = [life(ev, s, pre, post) for s in fst]
    n = len(out); lk = [o for o in out if o["locked"]]
    p_lock = 100 * len(lk) / n
    d2l = [o["d2l"] for o in lk if o["d2l"] is not None]
    pay_all = np.mean([o["payout"] for o in out])
    return p_lock, (int(np.median(d2l)) if d2l else None), pay_all


def main():
    print("loading Databento + A/B/Momentum…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    ev = sorted(H.a_events(df5) + H.b_events(df5) + H.m_events(df5), key=lambda e: e["ts"])
    last = pd.Timestamp(ev[-1]["ts"]); seen, fst = set(), []
    for i, e in enumerate(ev):
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - pd.Timestamp(e["ts"])).days >= 270:
            fst.append(i)

    POST6 = {"A": 6, "B": 3, "M": 6}
    configs = [
        ("A4/B2 mm0  -> A6/B3 mm0  (deployed)",   {"A": 4, "B": 2, "M": 0}, {"A": 6, "B": 3, "M": 0}),
        ("A4/B2 mm2  -> A6/B3 mm6  (mm-opt)",      {"A": 4, "B": 2, "M": 2}, POST6),
        ("A3/B2 mm0  -> A6/B3 mm6  (size lever)",  {"A": 3, "B": 2, "M": 0}, POST6),
        ("A3/B2 mm2  -> A6/B3 mm6  (COMBINED)",    {"A": 3, "B": 2, "M": 2}, POST6),
        ("A2/B1 mm2  -> A6/B3 mm6  (small+mm)",    {"A": 2, "B": 1, "M": 2}, POST6),
    ]
    print(f"\n  ===== do the grind levers STACK? (EOD + Databento) =====")
    print(f"  {'grind -> post':<38}{'lock%':>7}{'medLockDays':>13}{'E[payout]':>12}")
    for lbl, pre, post in configs:
        lk, md, pay = ev_metrics(ev, fst, pre, post)
        print(f"  {lbl:<38}{lk:>7.1f}{(md or 0):>13}{pay:>12,.0f}")
    print("\n  [note] EOD + Databento; momentum daily-aggregate proxy. Speed cost shows in medLockDays.")


if __name__ == "__main__":
    main()
