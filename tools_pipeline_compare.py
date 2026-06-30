"""FULL PIPELINE: live bot (partial) vs single@1R vs single@1.5R — eval + funded, every stage + timing.
Reuses the validated harnesses; swaps only the Profile-A exit (B + sizing held constant). EOD rule,
real Databento ~5y. Eval = A10/B5/mm6. Funded = A4/B2 grind -> A6/B3 post-lock, 18mo, momentum OFF
(matches the validated funded baseline; incumbent reproduces 57.5%/68.2%/$12.3k)."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import exit_model_validate as V
import apex_eval_eod as EOD
import apex_funded_eod_databento as F
import apex_eval_deployed as H
import funded_rules as FR
import strategy_engine_profileA as E
import config

SPEC = FR.APEX_ACCOUNTS["50K"]
T = pd.Timestamp


def funded_life(ev, start):
    """Mirror of F.lifecycle + days-to-first-payout (d2fp)."""
    thr = F.START - F.TRAIL; bal = F.START; peak = F.START; locked = False; d2l = None; d2fp = None
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
                    if d2fp is None:
                        d2fp = (ts - t0).days
            cmonth = m
        if dreal <= F.DAILY_STOP:
            continue
        sc = (F.POST if locked else F.PRE)[e["src"]]
        if bal + min(0.0, e["mae"]) * sc <= thr:
            return dict(locked=locked, d2l=d2l, d2fp=d2fp, payout=payout, months=max(1e-6, (ts - t0).days) / 30.0)
        bal += e["pnl"] * sc; dreal += e["pnl"] * sc
    return dict(locked=locked, d2l=d2l, d2fp=d2fp, payout=payout, months=max(1e-6, (last - t0).days) / 30.0)


print("loading real Databento…", flush=True)
df5 = F.DB.load_databento_5m()
H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
feats = eng._features(); fi = feats.index
Bf = H.b_events(df5); Mm = H.m_events(df5)   # Bf = event-format B for the funded lifecycle
Bsim = V.b_sim(df5)                          # Bsim = R-keyed B for V.build_events (eval)
variants = ["incumbent", "single1", "single15"]
lab = {"incumbent": "LIVE BOT", "single1": "single@1R", "single15": "single@1.5R"}
Avar = {v: V.a_variant(feats, fi, v) for v in variants}


def funded_starts(ev):
    last = T(ev[-1]["ts"]); seen, st = set(), []
    for i, e in enumerate(ev):
        d = T(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - T(e["ts"])).days >= 270:
            st.append(i)
    return st


print("\n================  EVAL  (A10/B5/mm6 · EOD · 30-day clock)  ================")
print(f"  {'exit':>12} | {'pass%':>6} {'expire%':>7} | {'med days':>8} {'mean':>5} | {'totR':>6} {'A_maxDD':>8}")
print("  " + "-" * 66)
ev_eval = {}
for v in variants:
    ev = V.build_events(Avar, Bsim, Mm, v)
    st = EOD.day_starts(ev)
    res = [EOD.eval_eod(ev, s, SPEC) for s in st]
    n = len(res); pas = [d for o, d in res if o == "PASS"]; exp = sum(1 for o, d in res if o == "EXPIRE")
    tr = V.total_R(ev); add = V.a_maxdd_R(Avar, v)
    ev_eval[v] = dict(passpct=100*len(pas)/n, exp=100*exp/n, med=int(np.median(pas)), mean=np.mean(pas), totR=tr, add=add)
    e = ev_eval[v]
    print(f"  {lab[v]:>12} | {e['passpct']:6.1f} {e['exp']:7.1f} | {e['med']:8} {e['mean']:5.1f} | {tr:6.0f} {add:8.1f}")

print("\n================  FUNDED  (A4/B2 grind -> A6/B3 post-lock · 18mo · mm OFF)  ================")
print(f"  {'exit':>12} | {'reach-lock%':>11} {'med d->lock':>11} {'med d->1st pay':>14} | {'$/mo locked':>11} {'E[pay/acct]':>11}")
print("  " + "-" * 80)
fd = {}
for v in variants:
    Aev = [dict(ts=t["ts"], src="A", pnl=t["R"]*t["risk_usd"], mae=min(0.0, t["mae_r"])*t["risk_usd"]) for t in Avar[v]]
    ev = sorted(Aev + Bf, key=lambda e: T(e["ts"]))
    out = [funded_life(ev, s) for s in funded_starts(ev)]
    n = len(out); lk = [o for o in out if o["locked"]]
    d2l = [o["d2l"] for o in lk if o["d2l"] is not None]
    d2fp = [o["d2fp"] for o in out if o["d2fp"] is not None]
    epay = np.mean([o["payout"] for o in out])
    epl = np.mean([o["payout"] for o in lk]) if lk else 0.0
    mol = np.mean([o["months"] for o in lk]) if lk else 0.0
    fd[v] = dict(lock=100*len(lk)/n, d2l=int(np.median(d2l)) if d2l else 0,
                 d2fp=int(np.median(d2fp)) if d2fp else 0, mo=epl/mol if mol else 0, epay=epay)
    f = fd[v]
    print(f"  {lab[v]:>12} | {f['lock']:11.1f} {f['d2l']:11} {f['d2fp']:14} | ${f['mo']:10,.0f} ${f['epay']:10,.0f}")

print("\n================  END-TO-END TIMELINE (median, cumulative from eval start)  ================")
print(f"  {'exit':>12} | {'eval pass':>9} -> {'funded lock(P2)':>15} -> {'first payout':>12}")
for v in variants:
    e = ev_eval[v]; f = fd[v]
    t_pass = e['med']; t_lock = t_pass + f['d2l']; t_pay = t_pass + f['d2fp']
    print(f"  {lab[v]:>12} | {t_pass:>6}d   -> {t_lock:>12}d    -> {t_pay:>9}d")
print("\n  (timeline chains eval days-to-pass + funded days-to-lock / days-to-first-payout; mm OFF; single 5y path)")
