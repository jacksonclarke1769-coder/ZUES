"""Does the continuation (Momentum) lane help or hurt ONCE FUNDED? It's currently mm=0 on funded as a
conservative default ('off until separately validated'). This validates it: funded lifecycle (EOD +
Databento) with momentum OFF vs POST-LOCK-ONLY vs BOTH phases. Hypothesis: momentum hurts the grind
(stresses the still-live trail) but helps income post-lock (floor locked at $50,100, variance is safe)."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB

START, TRAIL, LOCK_EOD, FLOOR = 50_000.0, 2_500.0, 52_600.0, 50_100.0
SAFETY, CAP_FIRST, CAP_LATER, N_CAPPED, MIN_PAYOUT = 52_100.0, 2_000.0, 4_000.0, 5, 500.0
HORIZON_DAYS, DAILY_STOP = 18 * 30, -550.0


def life(ev, start, pre, post):
    thr = START - TRAIL; bal = START; peak = START; locked = False; d2l = None
    payout = 0.0; npay = 0; t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0; cmonth = None
    last = t0
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize(); last = ts
        if (ts - t0).days > HORIZON_DAYS:
            break
        if cur is None:
            cur = day
        if day != cur:
            peak = max(peak, bal)
            if not locked:
                if peak >= LOCK_EOD:
                    thr = FLOOR; locked = True; d2l = (ts - t0).days
                else:
                    thr = max(thr, peak - TRAIL)
            cur = day; dreal = 0.0
        m = (ts.year, ts.month)
        if cmonth is None:
            cmonth = m
        if m != cmonth:
            if locked and bal > SAFETY:
                cap = CAP_FIRST if npay < N_CAPPED else CAP_LATER
                w = min(bal - SAFETY, cap)
                if w >= MIN_PAYOUT:
                    bal -= w; payout += w; npay += 1
            cmonth = m
        if dreal <= DAILY_STOP:
            continue
        s = (post if locked else pre).get(e["src"], 0)
        if s == 0:
            continue
        if bal + min(0.0, e["mae"]) * s <= thr:
            return dict(locked=locked, payout=payout, months=max(1e-6, (ts - t0).days) / 30.0)
        bal += e["pnl"] * s; dreal += e["pnl"] * s
    return dict(locked=locked, payout=payout, months=max(1e-6, (last - t0).days) / 30.0)


def run(ev, fst, label, pre, post):
    out = [life(ev, s, pre, post) for s in fst]
    n = len(out); lk = [o for o in out if o["locked"]]
    p_lock = 100 * len(lk) / n
    pay_all = np.mean([o["payout"] for o in out])
    pay_lk = np.mean([o["payout"] for o in lk]) if lk else 0.0
    mo = np.mean([o["months"] for o in lk]) if lk else 0.0
    inc = pay_lk / mo if mo else 0.0
    print(f"  {label:<28} lock {p_lock:5.1f}%   income/locked ${inc:>6,.0f}/mo   "
          f"E[payout|funded] ${pay_all:>7,.0f}")
    return p_lock, inc, pay_all


def main():
    print("loading Databento + A/B/Momentum streams…", flush=True)
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

    print(f"\n  ===== Does Momentum (continuation) help ONCE FUNDED? (EOD + Databento) =====")
    print(f"  grind A4/B2 -> A6/B3 post-lock; momentum sized ~proportional (pre mm3 / post mm4)\n")
    run(ev, fst, "OFF (current funded config)", {"A": 4, "B": 2, "M": 0}, {"A": 6, "B": 3, "M": 0})
    run(ev, fst, "POST-LOCK only (mm4)",        {"A": 4, "B": 2, "M": 0}, {"A": 6, "B": 3, "M": 4})
    run(ev, fst, "BOTH phases (mm3 / mm4)",     {"A": 4, "B": 2, "M": 3}, {"A": 6, "B": 3, "M": 4})
    print("\n  [note] EOD + Databento. momentum modelled as daily-aggregate events. floor locks at $50,100.")


if __name__ == "__main__":
    main()
