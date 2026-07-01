"""ROBUSTNESS GATE for the Thu-1.5x post-lock size-up before it goes in the funded config.
Per cohort-START-year: E[payout|started] and post-lock bust%, flat vs Thu 1.5x. If Thu 1.5x beats flat
in most years (not one lucky Thursday run), it's structural and safe to commit. Funded lifecycle, real
Databento ~5y, POST-lock only (pre-lock flat), incumbent (partial) exit."""
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
PRE = {"A": 4, "B": 2, "M": 2}; POST = {"A": 6, "B": 3, "M": 6}
FLAT = {i: 1.0 for i in range(5)}; THU = {0: 1.0, 1: 1.0, 2: 1.0, 3: 1.5, 4: 1.0}


def funded_life(ev, start, post_mult):
    thr = F.START - F.TRAIL; bal = F.START; peak = F.START; locked = False
    payout = 0.0; npay = 0; t0 = T(ev[start]["ts"]); cur = None; dreal = 0.0; cmonth = None; last = t0; bpost = False
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
                    thr = F.FLOOR; locked = True
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
                bpost = True
            return dict(y=t0.year, locked=locked, payout=payout, bpost=bpost)
        bal += e["pnl"] * sc; dreal += e["pnl"] * sc
    return dict(y=t0.year, locked=locked, payout=payout, bpost=bpost)


print("loading real Databento…", flush=True)
df5 = F.DB.load_databento_5m()
H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
eng = E.ProfileAEngine(config.STRAT); eng.buf = df5; feats = eng._features(); fi = feats.index
Bsim = V.b_sim(df5); Mm = H.m_events(df5)
A = V.a_variant(feats, fi, "incumbent")
ev = [dict(ts=t["ts"], src="A", pnl=t["R"] * t["risk_usd"], mae=min(0.0, t["mae_r"]) * t["risk_usd"]) for t in A]
for t in Bsim:
    R = t["R"]["incumbent"]; gp = R * (t["risk_usd"] / V.DPP)
    ev.append(dict(ts=t["ts"], src="B", pnl=(gp - V.B_COST) * V.DPP, mae=min(0.0, t["mae_pts"]["incumbent"]) * V.DPP))
for e in Mm:
    ev.append(dict(ts=e["ts"], src="M", pnl=e["pnl"], mae=min(0.0, e["mae"])))
ev.sort(key=lambda x: T(x["ts"]))
seen, st = set(), []
for i, e in enumerate(ev):
    d = T(e["ts"]).normalize()
    if d not in seen:
        seen.add(d); st.append(i)

flat = [funded_life(ev, s, FLAT) for s in st]
thu = [funded_life(ev, s, THU) for s in st]
yrs = sorted({o["y"] for o in flat})
print(f"  window {df5.index.min().date()} -> {df5.index.max().date()} · {len(st)} cohorts · POST-lock Thu 1.5x\n")
print(f"  cohort | {'flat E[pay|start]':>17} {'Thu1.5 E[pay|start]':>19} {'Δ$':>8} {'Δ%':>6} | {'flat bustP':>10} {'Thu bustP':>9}")
print("  " + "-" * 92)
wins = 0
for y in yrs:
    f = [o for o in flat if o["y"] == y]; th = [o for o in thu if o["y"] == y]
    fp = np.mean([o["payout"] for o in f]); tp = np.mean([o["payout"] for o in th])
    fb = 100 * np.mean([o["bpost"] for o in f]); tb = 100 * np.mean([o["bpost"] for o in th])
    d = tp - fp; dp = 100 * d / fp if fp else 0
    if tp >= fp:
        wins += 1
    print(f"  {y:>6} | ${fp:>15,.0f} ${tp:>17,.0f} {d:>+8,.0f} {dp:>+5.1f}% | {fb:>9.1f}% {tb:>8.1f}%")
print("  " + "-" * 92)
FP = np.mean([o["payout"] for o in flat]); TP = np.mean([o["payout"] for o in thu])
print(f"  {'ALL':>6} | ${FP:>15,.0f} ${TP:>17,.0f} {TP-FP:>+8,.0f} {100*(TP-FP)/FP:>+5.1f}% |"
      f"  Thu beats flat in {wins}/{len(yrs)} cohort-years")
print("\n  [E[pay|started] over the full funded lifecycle · Thu 1.5x applied POST-lock only · pre-lock flat]")
