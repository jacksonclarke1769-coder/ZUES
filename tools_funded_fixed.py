"""CORRECTED funded comparison: live bot (A+B partial) vs single@1R (A+B), momentum OFF and ON.
Fixes the earlier B-held-constant bug — here BOTH Profile A AND B use the variant's exit (coherent
with the eval comparison), and momentum is run at the deployed funded sizing (mm2 grind / mm6 post-lock).
Real Databento ~5y, Apex 50K funded EOD lifecycle. Incumbent reproduces the validated baseline."""
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


def funded_life(ev, start, PRE, POST):
    """F.lifecycle, parametrised by PRE/POST sizing dicts that may include 'M' (momentum)."""
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


print("loading real Databento…", flush=True)
df5 = F.DB.load_databento_5m()
H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
eng = E.ProfileAEngine(config.STRAT); eng.buf = df5; feats = eng._features(); fi = feats.index
Bsim = V.b_sim(df5); Mm = H.m_events(df5)
variants = ["incumbent", "single1"]
lab = {"incumbent": "LIVE BOT (A+B partial)", "single1": "single@1R (A+B)"}


def build(variant):                                  # size-1 events, BOTH A and B at this exit + momentum
    A = V.a_variant(feats, fi, variant)
    ev = [dict(ts=t["ts"], src="A", pnl=t["R"] * t["risk_usd"], mae=min(0.0, t["mae_r"]) * t["risk_usd"]) for t in A]
    for t in Bsim:
        R = t["R"][variant]; gp = R * (t["risk_usd"] / V.DPP)
        ev.append(dict(ts=t["ts"], src="B", pnl=(gp - V.B_COST) * V.DPP, mae=min(0.0, t["mae_pts"][variant]) * V.DPP))
    for e in Mm:
        ev.append(dict(ts=e["ts"], src="M", pnl=e["pnl"], mae=min(0.0, e["mae"])))
    return sorted(ev, key=lambda x: T(x["ts"]))


def starts(ev):
    last = T(ev[-1]["ts"]); seen, st = set(), []
    for i, e in enumerate(ev):
        d = T(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - T(e["ts"])).days >= 270:
            st.append(i)
    return st


evs = {v: build(v) for v in variants}
CONFIGS = [("momentum OFF", dict(A=4, B=2, M=0), dict(A=6, B=3, M=0)),
           ("momentum ON (deployed mm2->mm6)", dict(A=4, B=2, M=2), dict(A=6, B=3, M=6))]

print("\n  CORRECTED FUNDED — both A&B at the variant's exit · Apex 50K EOD · 18mo · real Databento")
for cname, PRE, POST in CONFIGS:
    print(f"\n  === {cname} ===")
    print(f"  {'exit':>22} | {'reach-lock%':>11} {'med d->lock':>11} | {'$/mo locked':>11} {'E[pay/acct]':>11}")
    for v in variants:
        ev = evs[v]
        out = [funded_life(ev, s, PRE, POST) for s in starts(ev)]
        n = len(out); lk = [o for o in out if o["locked"]]
        d2l = [o["d2l"] for o in lk if o["d2l"] is not None]
        epay = np.mean([o["payout"] for o in out])
        epl = np.mean([o["payout"] for o in lk]) if lk else 0.0
        mol = np.mean([o["months"] for o in lk]) if lk else 0.0
        print(f"  {lab[v]:>22} | {100*len(lk)/n:11.1f} {int(np.median(d2l)) if d2l else 0:11} | "
              f"${epl/mol if mol else 0:10,.0f} ${epay:10,.0f}")
print("\n  (FIX: B now uses each variant's exit too — earlier funded run held B at single-1.5R and swapped only A.)")
