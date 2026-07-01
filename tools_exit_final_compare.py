"""DEFINITIVE gate before promoting 1RR to live default: EXIT3 (partial) vs SINGLE_1R on the BUSINESS
metrics — eval pass-rate AND funded E[payout] — at deployed sizing, real Databento ~5y, EOD rule.
Both A and B use the same exit (coherent). Momentum identical across both (exit-independent)."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import exit_model_validate as V
import apex_eval_deployed as H
import apex_eval_eod as EOD
import apex_funded_eod_databento as F
import strategy_engine_profileA as E
import config
T = pd.Timestamp
SPEC = __import__("funded_rules").APEX_ACCOUNTS["50K"]
EVAL = {"A": 10, "B": 5, "M": 6}
PRE = {"A": 4, "B": 2, "M": 2}; POST = {"A": 6, "B": 3, "M": 6}


def stream(variant):                                 # size-1 events, BOTH A and B at this exit + momentum
    A = V.a_variant(feats, fi, variant)
    ev = [dict(ts=t["ts"], src="A", pnl=t["R"] * t["risk_usd"], mae=min(0.0, t["mae_r"]) * t["risk_usd"]) for t in A]
    for t in Bsim:
        R = t["R"][variant]; gp = R * (t["risk_usd"] / V.DPP)
        ev.append(dict(ts=t["ts"], src="B", pnl=(gp - V.B_COST) * V.DPP, mae=min(0.0, t["mae_pts"][variant]) * V.DPP))
    for e in Mm:
        ev.append(dict(ts=e["ts"], src="M", pnl=e["pnl"], mae=min(0.0, e["mae"])))
    return sorted(ev, key=lambda x: T(x["ts"]))


def scale(ev, sz):
    return H.apply_daily_stop([dict(ts=e["ts"], src=e["src"], pnl=e["pnl"] * sz[e["src"]], mae=e["mae"] * sz[e["src"]]) for e in ev])


def funded_life(ev, start):
    thr = F.START - F.TRAIL; bal = F.START; peak = F.START; locked = False; d2l = None
    payout = 0.0; npay = 0; t0 = T(ev[start]["ts"]); cur = None; dreal = 0.0; cmonth = None; last = t0
    for k in range(start, len(ev)):
        e = ev[k]; ts = T(e["ts"]); day = ts.normalize(); last = ts
        if (ts - t0).days > F.HORIZON_DAYS:
            break
        if cur is None:
            cur = day
        if day != cur:
            peak = max(peak, bal)
            if not locked:
                thr = max(thr, peak - F.TRAIL)
                if peak >= F.LOCK_EOD:
                    thr = F.FLOOR; locked = True; d2l = (ts - t0).days
            cur = day; dreal = 0.0
        m = (ts.year, ts.month)
        if cmonth is None:
            cmonth = m
        if m != cmonth:
            if locked and bal > F.SAFETY:
                cap = F.CAP_FIRST if npay < F.N_CAPPED else F.CAP_LATER
                w = min(bal - F.SAFETY, cap)
                if w >= F.MIN_PAYOUT:
                    bal -= w; payout += w; npay += 1
            cmonth = m
        if dreal <= F.DAILY_STOP:
            continue
        sc = (POST if locked else PRE).get(e["src"], 0)
        if sc == 0:
            continue
        if bal + min(0.0, e["mae"]) * sc <= thr:
            return dict(locked=locked, d2l=d2l, payout=payout, months=max(1e-6, (ts - t0).days) / 30.0)
        bal += e["pnl"] * sc; dreal += e["pnl"] * sc
    return dict(locked=locked, d2l=d2l, payout=payout, months=max(1e-6, (last - t0).days) / 30.0)


def starts(ev):
    seen, st = set(), []
    for i, e in enumerate(ev):
        d = T(e["ts"]).normalize()
        if d not in seen:
            seen.add(d); st.append(i)
    return st


print("loading real Databento…", flush=True)
df5 = F.DB.load_databento_5m()
H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
eng = E.ProfileAEngine(config.STRAT); eng.buf = df5; feats = eng._features(); fi = feats.index
Bsim = V.b_sim(df5); Mm = H.m_events(df5)
lab = {"incumbent": "EXIT3 (partial, current default)", "single1": "SINGLE_1R (1RR)"}
print(f"  window {df5.index.min().date()} -> {df5.index.max().date()}\n")
print(f"  {'exit model':>32} | {'EVAL pass%':>10} {'bust%':>6} {'exp%':>5} {'med d':>6} | {'FUND P(lock)':>12} {'E[pay|start]':>12} {'income/mo':>10}")
print("  " + "-" * 108)
for var in ("incumbent", "single1"):
    ev = stream(var)
    evs = scale(ev, EVAL); ss = EOD.day_starts(evs)
    p, b, x, m = EOD.summarize([EOD.eval_eod(evs, s, SPEC) for s in ss])
    out = [funded_life(ev, s) for s in starts(ev)]
    lk = [o for o in out if o["locked"]]; plock = len(lk) / len(out)
    mo = np.mean([o["months"] for o in lk]) if lk else 1e-6
    pay_all = np.mean([o["payout"] for o in out]); inc = (np.mean([o["payout"] for o in lk]) / mo) if lk else 0
    print(f"  {lab[var]:>32} | {p:>9.1f}% {b:>5.1f}% {x:>4.1f}% {str(m):>6} | {100*plock:>11.1f}% ${pay_all:>10,.0f} ${inc:>8,.0f}")
print("\n  [deployed eval A10/B5/mm6 · funded PRE A4/B2/mm2 POST A6/B3/mm6 · EOD rule · same momentum both rows]")
