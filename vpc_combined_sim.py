"""
Combined A + VPC through BOTH stages — does VPC EARN a spot as a diversifier layered on Profile A?
Measured as A-ALONE vs A+VPC (the delta is the answer; absolute levels are harness-approximate).

EVAL  : apex_eval_eod.eval_eod (Apex 50K, EOD-drawdown, $550 stop, 30d clock, rolling starts).
FUNDED: local lifecycle mirroring apex_funded_eod_databento (18mo, lock@EOD $52.6k->floor $50.1k,
        monthly payout sweeps) with an added constant-size VPC 'V' leg (B OFF, momentum OFF).
Real Databento for both legs. A stream from H.a_events (unit); VPC from vpc_apex_eval_sim.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB
import apex_eval_eod as AE
import funded_rules as FR
import vpc_apex_eval_sim as VS
import nq_vwap_pullback as v

DPP = 2.0
SPEC = FR.APEX_ACCOUNTS["50K"]
# funded constants (from apex_funded_eod_databento)
START, TRAIL, FLOOR, LOCK_EOD = 50_000.0, 2_500.0, 50_100.0, 52_600.0
SAFETY, CAP_FIRST, CAP_LATER, N_CAPPED, MIN_PAYOUT = 52_100.0, 2_000.0, 4_000.0, 5, 500.0
HORIZON_DAYS, DAILY_STOP = 18 * 30, -550.0


def vpc_unit_events():
    feats = v.features(VS.real_rth_5m())
    feats = feats[feats.date >= pd.Timestamp("2022-01-01", tz=VS.NY)]
    tr = VS.vpc_trades_rich(feats)
    return [dict(ts=pd.Timestamp(r.ts), src="V", pnl=r.pnl_pts*DPP,
                 mfe=max(0.0, r.mfe_pts)*DPP, mae=min(0.0, r.mae_pts)*DPP) for r in tr.itertuples()]


def scale_ev(ev, mult):
    return [dict(ts=e["ts"], src=e["src"], pnl=e["pnl"]*mult, mfe=e["mfe"]*mult, mae=e["mae"]*mult) for e in ev]


# ---------- EVAL ----------
def eval_run(events):
    ev = sorted(events, key=lambda e: e["ts"])
    starts = AE.day_starts(ev)
    p, b, x, md = AE.summarize([AE.eval_eod(ev, s, SPEC) for s in starts])
    return p, b, x, md, len(starts)


# ---------- FUNDED (A + optional V; B off) ----------
def lifecycle(ev, start_ts, scale):
    # start from the first event on/after the account start date; clock measured from start_ts
    start = next((i for i, e in enumerate(ev) if pd.Timestamp(e["ts"]) >= start_ts), None)
    if start is None:
        return dict(locked=False, d2l=None, payout=0.0, bust=None, months=HORIZON_DAYS/30.0)
    thr = START - TRAIL; bal = START; peak = START; locked = False; d2l = None
    payout = 0.0; npay = 0; t0 = pd.Timestamp(start_ts); cur = None; dreal = 0.0; cmonth = None; last = t0
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize(); last = ts
        if (ts - t0).days > HORIZON_DAYS: break
        if cur is None: cur = day
        if day != cur:
            peak = max(peak, bal)
            if not locked:
                thr = max(thr, peak - TRAIL)
                if peak >= LOCK_EOD: thr = FLOOR; locked = True; d2l = (ts - t0).days
            cur = day; dreal = 0.0
        m = (ts.year, ts.month)
        if cmonth is None: cmonth = m
        if m != cmonth:
            if locked and bal > SAFETY:
                cap = CAP_FIRST if npay < N_CAPPED else CAP_LATER
                w = min(bal - SAFETY, cap)
                if w >= MIN_PAYOUT: bal -= w; payout += w; npay += 1
            cmonth = m
        if dreal <= DAILY_STOP: continue
        sc = scale[e["src"]]["post" if locked else "pre"] if e["src"] == "A" else scale[e["src"]]["const"]
        if sc == 0: continue
        if bal + min(0.0, e["mae"]) * sc <= thr:
            return dict(locked=locked, d2l=d2l, payout=payout, bust=("post" if locked else "pre"),
                        months=max(1e-6, (ts - t0).days)/30.0)
        bal += e["pnl"]*sc; dreal += e["pnl"]*sc
    return dict(locked=locked, d2l=d2l, payout=payout, bust=None, months=max(1e-6, (last - t0).days)/30.0)


def funded_run(events, scale, start_dates):
    ev = sorted(events, key=lambda e: e["ts"])
    out = [lifecycle(ev, s, scale) for s in start_dates]
    n = len(out); locked = [o for o in out if o["locked"]]
    bpre = sum(1 for o in out if o["bust"] == "pre"); bpost = sum(1 for o in out if o["bust"] == "post")
    d2l = [o["d2l"] for o in locked if o["d2l"] is not None]
    pay_all = [o["payout"] for o in out]; pay_lock = [o["payout"] for o in locked]
    mo_lock = np.mean([o["months"] for o in locked]) if locked else 0.0
    pctile = lambda a, q: (float(np.percentile(a, q)) if a else 0.0)
    return dict(n=n, nlock=len(locked), plock=100*len(locked)/n, bpre=100*bpre/n, bpost=100*bpost/n,
                surv=100*(n-bpre-bpost)/n,
                med_d2l=(int(np.median(d2l)) if d2l else None),
                mean_d2l=(round(float(np.mean(d2l)), 0) if d2l else None),
                epay_all=float(np.mean(pay_all)), epay_lock=(float(np.mean(pay_lock)) if pay_lock else 0.0),
                pay_p25=pctile(pay_all, 25), pay_med=pctile(pay_all, 50), pay_p75=pctile(pay_all, 75),
                pay_p95=pctile(pay_all, 95), pay_max=(max(pay_all) if pay_all else 0.0),
                income_mo=(np.mean(pay_lock)/mo_lock if mo_lock else 0.0), mo_lock=mo_lock,
                pct_any_payout=100*sum(1 for p in pay_all if p > 0)/n)


def main():
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    A = [e for e in H.a_events(df5)]                 # unit A ($/1MNQ)
    V = vpc_unit_events()                            # unit VPC ($/1MNQ)
    print(f"unit streams: A={len(A)} (net ${sum(e['pnl'] for e in A):,.0f})  "
          f"VPC={len(V)} (net ${sum(e['pnl'] for e in V):,.0f})\n")

    # ---------------- EVAL ----------------
    print("=== EVAL (Apex 50K, EOD, 30d) — A size chosen to bracket certified ~58% ===")
    print(f"  {'config':>22} | {'PASS%':>6} {'BUST%':>6} {'EXP%':>5} {'med':>4} {'nStarts':>7}")
    for Sa in [5, 6, 8]:
        p, b, x, md, ns = eval_run(scale_ev(A, Sa))
        print(f"  {'A@'+str(Sa)+' ALONE':>22} | {p:>6.1f} {b:>6.1f} {x:>5.1f} {str(md):>4} {ns:>7}")
        for Sv in [2, 3, 4]:
            p2, b2, x2, md2, _ = eval_run(scale_ev(A, Sa) + scale_ev(V, Sv))
            print(f"  {'A@'+str(Sa)+' + VPC@'+str(Sv):>22} | {p2:>6.1f} {b2:>6.1f} {x2:>5.1f} {str(md2):>4}   Δpass={p2-p:+.1f}")
    print("  [ref] Profile A certified: PASS 58.2 / BUST 29.1 / EXP 12.7")

    # ---------------- FUNDED ----------------
    print("\n=== FUNDED (Apex 50K · EOD drawdown · 18mo horizon · B OFF · momentum OFF) ===")
    # shared account calendar: every distinct A trading day with >=270d runway (same starts for ALL configs)
    aev = sorted(A, key=lambda e: e["ts"]); lastA = pd.Timestamp(aev[-1]["ts"])
    seen, start_dates = set(), []
    for e in aev:
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen: continue
        seen.add(d)
        if (lastA - pd.Timestamp(e["ts"])).days >= 270: start_dates.append(d)
    base_scale = {"A": {"pre": 4, "post": 6}, "V": {"const": 0}}
    runs = [("A4->6 ALONE", funded_run(A, base_scale, start_dates))]
    for Sv in [1, 2, 3]:
        runs.append((f"A4->6 + VPC@{Sv}", funded_run(A + V, {"A": {"pre": 4, "post": 6}, "V": {"const": Sv}}, start_dates)))
    rb = runs[0][1]
    print(f"  accounts simulated: {rb['n']}   (rolling 1-start/trading-day, ≥270d runway)\n")
    hdr = ["metric"] + [name for name, _ in runs]
    rows = [
        ("P(reach lock) %",      [f"{r['plock']:.1f}" for _, r in runs]),
        ("  accounts locked",    [f"{r['nlock']}" for _, r in runs]),
        ("bust BEFORE lock %",   [f"{r['bpre']:.1f}" for _, r in runs]),
        ("bust AFTER lock %",    [f"{r['bpost']:.1f}" for _, r in runs]),
        ("survived horizon %",   [f"{r['surv']:.1f}" for _, r in runs]),
        ("median days-to-lock",  [f"{r['med_d2l']}" for _, r in runs]),
        ("mean days-to-lock",    [f"{r['mean_d2l']}" for _, r in runs]),
        ("E[payout | acct] $",   [f"{r['epay_all']:,.0f}" for _, r in runs]),
        ("E[payout | locked] $", [f"{r['epay_lock']:,.0f}" for _, r in runs]),
        ("income $/mo (locked)", [f"{r['income_mo']:,.0f}" for _, r in runs]),
        ("accts w/ any payout %",[f"{r['pct_any_payout']:.1f}" for _, r in runs]),
        ("payout p50 $",         [f"{r['pay_med']:,.0f}" for _, r in runs]),
        ("payout p75 $",         [f"{r['pay_p75']:,.0f}" for _, r in runs]),
        ("payout p95 $",         [f"{r['pay_p95']:,.0f}" for _, r in runs]),
        ("payout max $",         [f"{r['pay_max']:,.0f}" for _, r in runs]),
    ]
    w0 = 22; wc = 15
    print("  " + "metric".ljust(w0) + "".join(name.rjust(wc) for name, _ in runs))
    print("  " + "-" * (w0 + wc * len(runs)))
    for label, vals in rows:
        print("  " + label.ljust(w0) + "".join(v.rjust(wc) for v in vals))
    print("\n  Δ vs A-alone:")
    for name, r in runs[1:]:
        print(f"    {name:>16}: Δlock {r['plock']-rb['plock']:+.1f}pp | Δbust-pre {r['bpre']-rb['bpre']:+.1f}pp | "
              f"Δd2l {(r['med_d2l']-rb['med_d2l']):+d}d | ΔE[payout] ${r['epay_all']-rb['epay_all']:+,.0f}")


if __name__ == "__main__":
    main()
