"""Day-of-week SIZE-UP on a LOCKED FUNDED account — where the Thursday edge might finally pay.
Post-lock a bust is no longer terminal (banked payouts are kept, $1k DLL caps the day), so the eval's
tail penalty flips friendlier. Applies the DOW multiplier ONLY post-lock (income phase); pre-lock grind
stays flat, so P(lock) is constant and we measure the pure income effect. Deployed funded: PRE A4/B2/mm2,
POST A6/B3/mm6, partial (incumbent) exit, real Databento ~5y, Apex 50K EOD lifecycle."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import exit_model_validate as V
import apex_funded_eod_databento as F
import apex_eval_deployed as H
import strategy_engine_profileA as E
import config
T = pd.Timestamp
PRE = {"A": 4, "B": 2, "M": 2}
POST = {"A": 6, "B": 3, "M": 6}
SCHEMES = {
    "flat (baseline)":   {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0},
    "Thu 1.5x":          {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.5, 4: 1.0},
    "Thu 2x":            {0: 1.0, 1: 1.0, 2: 1.0, 3: 2.0, 4: 1.0},
    "Thu 2x + Tue 1.5x": {0: 1.0, 1: 1.5, 2: 1.0, 3: 2.0, 4: 1.0},
}


def funded_life(ev, start, post_mult):
    thr = F.START - F.TRAIL; bal = F.START; peak = F.START; locked = False; d2l = None
    payout = 0.0; npay = 0; t0 = T(ev[start]["ts"]); cur = None; dreal = 0.0; cmonth = None; last = t0
    bust_post = False
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
        if locked:
            sc *= post_mult.get(ts.dayofweek, 1.0)
        if sc == 0:
            continue
        if bal + min(0.0, e["mae"]) * sc <= thr:
            if locked:
                bust_post = True
            return dict(locked=locked, d2l=d2l, payout=payout, bust_post=bust_post,
                        months=max(1e-6, (ts - t0).days) / 30.0)
        bal += e["pnl"] * sc; dreal += e["pnl"] * sc
    return dict(locked=locked, d2l=d2l, payout=payout, bust_post=bust_post,
                months=max(1e-6, (last - t0).days) / 30.0)


def build():
    A = V.a_variant(feats, fi, "incumbent")
    ev = [dict(ts=t["ts"], src="A", pnl=t["R"] * t["risk_usd"], mae=min(0.0, t["mae_r"]) * t["risk_usd"]) for t in A]
    for t in Bsim:
        R = t["R"]["incumbent"]; gp = R * (t["risk_usd"] / V.DPP)
        ev.append(dict(ts=t["ts"], src="B", pnl=(gp - V.B_COST) * V.DPP, mae=min(0.0, t["mae_pts"]["incumbent"]) * V.DPP))
    for e in Mm:
        ev.append(dict(ts=e["ts"], src="M", pnl=e["pnl"], mae=min(0.0, e["mae"])))
    return sorted(ev, key=lambda x: T(x["ts"]))


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
ev = build(); st = starts(ev)
print(f"  window {df5.index.min().date()} -> {df5.index.max().date()} · funded PRE A4/B2/mm2 POST A6/B3/mm6 · {len(st)} cohorts\n")
print(f"  {'scheme':>18} | {'P(lock)':>7} {'bustPost':>8} | {'income/mo':>10} {'E[pay|lock]':>11} {'E[pay|start]':>12} | {'max MNQ':>7}")
print("  " + "-" * 92)
for name, mult in SCHEMES.items():
    out = [funded_life(ev, s, mult) for s in st]
    n = len(out); lk = [o for o in out if o["locked"]]
    p_lock = len(lk) / n
    bpost = 100 * sum(1 for o in out if o["bust_post"]) / n
    mo = np.mean([o["months"] for o in lk]) if lk else 1e-6
    pay_lock = np.mean([o["payout"] for o in lk]) if lk else 0.0
    pay_all = np.mean([o["payout"] for o in out])
    maxsz = int(max(sum(POST[k] * mult[dw] for k in POST) for dw in range(5)))
    print(f"  {name:>18} | {100*p_lock:>6.1f}% {bpost:>7.1f}% | ${pay_lock/mo:>8,.0f} ${pay_lock:>10,.0f} ${pay_all:>11,.0f} | {maxsz:>7}")
print("\n  [DOW size-up applied POST-LOCK only · income/mo & E[payout] over the funded lifecycle · Apex cap 60 MNQ]")
print("  [bustPost = busted AFTER lock (keeps banked payouts, not terminal) · P(lock) constant by design]")
