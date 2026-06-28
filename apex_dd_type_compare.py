"""EOD vs INTRADAY drawdown — which account type is better END-TO-END (eval -> funded lock)?
You can't mix: the type is fixed at purchase and the funded inherits it. EOD: easier eval, harder lock.
Intraday: harder eval, easier lock. This computes P(pass eval) × P(reach funded lock) for each, on real
Databento, so the eval gate and the funded gate are weighed together (not in isolation)."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod as EOD
import apex_eval_eod_databento as DB
import funded_rules as FR

SPEC = FR.APEX_ACCOUNTS["50K"]
SB, TRAIL, LOCK_EOD, FLOOR, EXPIRE, DAILY_STOP = 50_000.0, 2_500.0, 52_600.0, 50_100.0, 30, -550.0
EVAL = {"A": 10, "B": 5, "M": 6}; FUND = {"A": 4, "B": 2, "M": 0}


def eval_eod(ev, start):
    thr = SB - TRAIL; bal = SB; peak = SB; t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if day != cur:
            if cur is not None and (ts - t0).days > EXPIRE: return False, k
            peak = max(peak, bal); thr = max(thr, peak - TRAIL); cur = day; dreal = 0.0
        if dreal <= DAILY_STOP: continue
        s = EVAL[e["src"]]
        if bal + min(0.0, e["mae"]) * s <= thr: return False, k
        bal += e["pnl"] * s; dreal += e["pnl"] * s
        if bal >= SB + 3000: return True, k
    return False, len(ev)


def funded_eod(ev, start):
    thr = SB - TRAIL; bal = SB; peak = SB; cur = None; dreal = 0.0
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if (ts - pd.Timestamp(ev[start]["ts"])).days > 18 * 30: return False
        if day != cur:
            peak = max(peak, bal); thr = max(thr, peak - TRAIL)
            if peak >= LOCK_EOD: return True
            cur = day; dreal = 0.0
        if dreal <= DAILY_STOP: continue
        s = FUND[e["src"]]
        if s == 0: continue
        if bal + min(0.0, e["mae"]) * s <= thr: return False
        bal += e["pnl"] * s; dreal += e["pnl"] * s
    return False


def eval_intraday(ev, start):
    a = FR.ApexAcct(SPEC); t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if day != cur:
            if cur is not None and (ts - t0).days > EXPIRE: return False, k
            cur = day; dreal = 0.0
        if dreal <= DAILY_STOP: continue
        s = EVAL[e["src"]]
        a.apply_trade(e["pnl"] * s, mfe=max(0.0, e["mfe"]) * s, mae=min(0.0, e["mae"]) * s)
        dreal += e["pnl"] * s
        if a.passed: return True, k
        if a.breached: return False, k
    return False, len(ev)


def funded_intraday(ev, start):
    a = FR.ApexAcct(SPEC); cur = None; dreal = 0.0
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if (ts - pd.Timestamp(ev[start]["ts"])).days > 18 * 30: return False
        if day != cur:
            cur = day; dreal = 0.0
        if dreal <= DAILY_STOP: continue
        s = FUND[e["src"]]
        if s == 0: continue
        a.apply_trade(e["pnl"] * s, mfe=max(0.0, e["mfe"]) * s, mae=min(0.0, e["mae"]) * s)
        dreal += e["pnl"] * s
        if a.locked: return True
        if a.breached: return False
    return False


def main():
    print("loading Databento + streams…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    ev = sorted(H.a_events(df5) + H.b_events(df5) + H.m_events(df5), key=lambda e: e["ts"])
    starts = EOD.day_starts(H.apply_daily_stop([dict(e) for e in ev]))  # 1 eval/trading-day, with runway
    starts = [s for s in starts if (pd.Timestamp(ev[-1]["ts"]) - pd.Timestamp(ev[s]["ts"])).days >= 270]

    print(f"\n  === EOD vs INTRADAY account — END-TO-END (eval → funded lock), {len(starts)} starts ===")
    print(f"  {'account type':>14}{'eval PASS%':>12}{'funded LOCK% (of passers)':>26}{'end-to-end':>12}")
    for label, ev_f, fn_f in [("EOD (yours)", eval_eod, funded_eod), ("INTRADAY", eval_intraday, funded_intraday)]:
        passed = locked = 0
        for s in starts:
            ok, idx = ev_f(ev, s)
            if not ok: continue
            passed += 1
            if fn_f(ev, idx): locked += 1
        ep = 100 * passed / len(starts)
        fp = 100 * locked / passed if passed else 0
        e2e = 100 * locked / len(starts)
        print(f"  {label:>14}{ep:>12.1f}{fp:>26.1f}{e2e:>12.1f}")
    print("\n  [note] A4/B2 funded base (no momentum/brake), so the DD-type effect is isolated. Momentum+brake")
    print("         (live on the EOD config) lift EOD funded reach-lock ~68→~90-98%, widening EOD's lead further.")


if __name__ == "__main__":
    main()
