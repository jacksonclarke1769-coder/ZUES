"""APEX FUNDED survival — EOD drawdown rule + REAL DATABENTO. Corrects apex_funded_sim.py
(which used intraday trailing + Dukascopy). PA lifecycle: start $50k, A4/B2, EOD drawdown grind to
the lock (EOD balance >= $52,600 -> floor locks at $50,100), then scale A6/B3 and draw monthly
payouts down to a $52,100 safety net. Momentum OFF on funded. Intraday DOWNSIDE still liquidates."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB         # load_databento_5m

START, TRAIL, FLOOR, LOCK_EOD = 50_000.0, 2_500.0, 50_100.0, 52_600.0
SAFETY, CAP_FIRST, CAP_LATER, N_CAPPED, MIN_PAYOUT = 52_100.0, 2_000.0, 4_000.0, 5, 500.0
HORIZON_DAYS, DAILY_STOP = 18 * 30, -550.0
PRE = {"A": 4, "B": 2}                         # phase 1 (to lock)
POST = {"A": 6, "B": 3}                        # phase 2 (post-lock)


def lifecycle(ev, start):
    thr = START - TRAIL; bal = START; peak = START; locked = False; d2l = None
    payout = 0.0; npay = 0; t0 = pd.Timestamp(ev[start]["ts"])
    cur = None; dreal = 0.0; cmonth = None; last = t0
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize(); last = ts
        if (ts - t0).days > HORIZON_DAYS:
            break
        if cur is None:
            cur = day
        if day != cur:                                   # EOD rollover: ratchet on prior CLOSE
            peak = max(peak, bal)
            if not locked:
                thr = max(thr, peak - TRAIL)
                if peak >= LOCK_EOD:
                    thr = FLOOR; locked = True; d2l = (ts - t0).days
            cur = day; dreal = 0.0
        m = (ts.year, ts.month)
        if cmonth is None:
            cmonth = m
        if m != cmonth:                                  # monthly payout sweep (post-lock)
            if locked and bal > SAFETY:
                cap = CAP_FIRST if npay < N_CAPPED else CAP_LATER
                w = min(bal - SAFETY, cap)
                if w >= MIN_PAYOUT:
                    bal -= w; payout += w; npay += 1
            cmonth = m
        if dreal <= DAILY_STOP:                           # $550 daily stop
            continue
        sc = (POST if locked else PRE)[e["src"]]
        if bal + min(0.0, e["mae"]) * sc <= thr:          # intraday downside liquidation
            return dict(locked=locked, d2l=d2l, payout=payout,
                        bust=("postlock" if locked else "prelock"), months=max(1e-6, (ts - t0).days) / 30.0)
        bal += e["pnl"] * sc; dreal += e["pnl"] * sc
    return dict(locked=locked, d2l=d2l, payout=payout, bust=None, months=max(1e-6, (last - t0).days) / 30.0)


def main():
    print("loading real Databento 5m + building A/B streams (funded = momentum OFF)…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    ev = sorted(H.a_events(df5) + H.b_events(df5), key=lambda e: e["ts"])
    print(f"  bars -> {df5.index.min().date()}..{df5.index.max().date()} · unit A+B events {len(ev)}", flush=True)

    last = pd.Timestamp(ev[-1]["ts"]); seen, starts = set(), []
    for i, e in enumerate(ev):
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - pd.Timestamp(e["ts"])).days >= 270:
            starts.append(i)
    out = [lifecycle(ev, s) for s in starts]
    n = len(out)
    locked = [o for o in out if o["locked"]]
    bust_pre = sum(1 for o in out if o["bust"] == "prelock")
    bust_post = sum(1 for o in out if o["bust"] == "postlock")
    p_lock = len(locked) / n
    d2l = [o["d2l"] for o in locked if o["d2l"] is not None]
    payout_all = np.mean([o["payout"] for o in out])
    payout_locked = np.mean([o["payout"] for o in locked]) if locked else 0.0
    mo = np.mean([o["months"] for o in locked]) if locked else 0.0

    print(f"\n================ APEX 50K FUNDED · EOD rule · REAL DATABENTO ================")
    print(f"  funded accounts simulated: {n}   ·   horizon {HORIZON_DAYS//30}mo")
    print(f"  P(reach lock)      : {100*p_lock:5.1f}%   (median {int(np.median(d2l)) if d2l else None} days)")
    print(f"  bust BEFORE lock   : {100*bust_pre/n:5.1f}%   ($0 income)")
    print(f"  bust AFTER lock    : {100*bust_post/n:5.1f}%   (kept banked payouts)")
    print(f"  survived horizon   : {100*(n-bust_pre-bust_post)/n:5.1f}%")
    print(f"  income | locked    : ${(payout_locked/mo if mo else 0):,.0f}/mo over ~{mo:.0f}mo")
    print(f"  E[payout | locked] : ${payout_locked:,.0f}")
    print(f"  E[payout | funded acct started] : ${payout_all:,.0f}")
    print(f"\n  vs prior (intraday+Dukascopy): P(lock) 82.7%, $1,742/mo, E[payout] ~$13.4k")
    print("  [note] EOD assumed for funded too (inherits eval type — confirm vs contract). Per-trade proxy.")


if __name__ == "__main__":
    main()
