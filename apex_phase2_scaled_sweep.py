"""PHASE 2 (post-lock) income optimisation. Reuses the EXACT validated funded lifecycle from
apex_funded_eod_databento.py (EOD rule + REAL Databento via H.a/b/m_events), but parametrises POST
A/B/M and tracks bust-AFTER-lock so we can quantify E[payout|locked] and bust-after-lock% per candidate.

Key structural fact: P(reach lock) depends ONLY on the PRE (grind) phase (lock is decided on the path
before any POST sizing fires), so we hold PRE = deployed A4/B2/M0 fixed and sweep POST. lock% is therefore
invariant across POST candidates; the trade-off is income (E[payout]) vs bust-after-lock on the locked cohort.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB

# constants COPIED VERBATIM from apex_funded_eod_databento.py (no re-derivation)
START, TRAIL, FLOOR, LOCK_EOD = 50_000.0, 2_500.0, 50_100.0, 52_600.0
SAFETY, CAP_FIRST, CAP_LATER, N_CAPPED, MIN_PAYOUT = 52_100.0, 2_000.0, 4_000.0, 5, 500.0
HORIZON_DAYS, DAILY_STOP = 18 * 30, -550.0
PRE = {"A": 4, "B": 2, "M": 0}                 # deployed Phase-1 grind (FROZEN here)


def lifecycle(ev, start, pre, post):
    """EXACT body of apex_funded_eod_databento.lifecycle(), parametrised by pre/post and
    returning bust-after-lock. .get(src,0) lets M be absent/zero."""
    thr = START - TRAIL; bal = START; peak = START; locked = False; d2l = None
    payout = 0.0; npay = 0; t0 = pd.Timestamp(ev[start]["ts"])
    cur = None; dreal = 0.0; cmonth = None; last = t0
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize(); last = ts
        if (ts - t0).days > HORIZON_DAYS:
            break
        if cur is None:
            cur = day
        if day != cur:
            peak = max(peak, bal)
            if not locked:
                thr = max(thr, peak - TRAIL)
                if peak >= LOCK_EOD:
                    thr = FLOOR; locked = True; d2l = (ts - t0).days
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
        sc = (post if locked else pre).get(e["src"], 0)
        if sc == 0:
            continue
        if bal + min(0.0, e["mae"]) * sc <= thr:
            return dict(locked=locked, payout=payout,
                        bust=("postlock" if locked else "prelock"),
                        months=max(1e-6, (ts - t0).days) / 30.0)
        bal += e["pnl"] * sc; dreal += e["pnl"] * sc
    return dict(locked=locked, payout=payout, bust=None,
                months=max(1e-6, (last - t0).days) / 30.0)


def evaluate(ev, fst, pre, post):
    out = [lifecycle(ev, s, pre, post) for s in fst]
    n = len(out)
    lk = [o for o in out if o["locked"]]
    nlk = len(lk)
    p_lock = 100 * nlk / n
    bust_post = sum(1 for o in out if o["bust"] == "postlock")
    # bust-after-lock as a share of the LOCKED cohort (the cohort actually exposed to POST sizing)
    bust_post_of_locked = 100 * bust_post / nlk if nlk else 0.0
    pay_all = np.mean([o["payout"] for o in out])
    pay_lk = np.mean([o["payout"] for o in lk]) if lk else 0.0
    mo = np.mean([o["months"] for o in lk]) if lk else 0.0
    inc = pay_lk / mo if mo else 0.0
    return dict(p_lock=p_lock, bust_post_locked=bust_post_of_locked, n_bust_post=bust_post,
                inc=inc, pay_lk=pay_lk, pay_all=pay_all, n=n, nlk=nlk)


def main():
    print("loading real Databento 5m + A/B/Momentum streams…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    ev = sorted(H.a_events(df5) + H.b_events(df5) + H.m_events(df5), key=lambda e: e["ts"])
    print(f"  bars {df5.index.min().date()}..{df5.index.max().date()}  unit events {len(ev)}", flush=True)

    last = pd.Timestamp(ev[-1]["ts"]); seen, fst = set(), []
    for i, e in enumerate(ev):
        d = pd.Timestamp(e["ts"]).normalize()
        if d in seen:
            continue
        seen.add(d)
        if (last - pd.Timestamp(e["ts"])).days >= 270:
            fst.append(i)
    print(f"  funded-start cohorts: {len(fst)}\n")

    # ---- baseline + grid of POST candidates (PRE frozen A4/B2/M0) ----
    cands = [
        ("A6/B3/mm0  (funded_eod base)",  {"A": 6, "B": 3, "M": 0}),
        ("A6/B3/mm6  (DEPLOYED Phase2)",  {"A": 6, "B": 3, "M": 6}),
        ("A6/B3/mm8",                     {"A": 6, "B": 3, "M": 8}),
        ("A8/B4/mm6",                     {"A": 8, "B": 4, "M": 6}),
        ("A8/B4/mm8",                     {"A": 8, "B": 4, "M": 8}),
        ("A10/B5/mm6",                    {"A": 10, "B": 5, "M": 6}),
        ("A10/B5/mm8",                    {"A": 10, "B": 5, "M": 8}),
        ("A10/B5/mm10",                   {"A": 10, "B": 5, "M": 10}),
        ("A12/B6/mm6",                    {"A": 12, "B": 6, "M": 6}),
        ("A12/B6/mm8",                    {"A": 12, "B": 6, "M": 8}),
        ("A8/B4/mm0",                     {"A": 8, "B": 4, "M": 0}),
        ("A10/B5/mm0",                    {"A": 10, "B": 5, "M": 0}),
        ("A12/B6/mm0",                    {"A": 12, "B": 6, "M": 0}),
        ("A14/B7/mm8",                    {"A": 14, "B": 7, "M": 8}),
    ]
    print(f"  PRE (grind) frozen = A4/B2/mm0   ·   EOD rule · REAL Databento · {HORIZON_DAYS//30}mo horizon")
    print(f"  {'POST config':<30}{'lock%':>7}{'bustAFTERlock%':>16}{'(n)':>6}{'inc/mo':>10}{'E[pay|lk]':>11}{'E[pay|fund]':>13}")
    print("  " + "-" * 96)
    rows = []
    for label, post in cands:
        r = evaluate(ev, fst, PRE, post)
        rows.append((label, post, r))
        star = "  <-DEPLOYED" if "DEPLOYED" in label else ""
        print(f"  {label:<30}{r['p_lock']:>7.1f}{r['bust_post_locked']:>14.1f}  "
              f"{r['n_bust_post']:>4}/{r['nlk']:<3}{r['inc']:>9,.0f}{r['pay_lk']:>11,.0f}{r['pay_all']:>13,.0f}{star}")

    # rank by E[payout|funded] among configs with bust-after-lock(of locked) <= 8%
    print("\n  ===== ranked by E[payout|funded] (acceptable-risk filter: bust-after-lock<=8% of locked) =====")
    ok = [r for r in rows if r[2]["bust_post_locked"] <= 8.0]
    ok.sort(key=lambda r: -r[2]["pay_all"])
    for label, post, r in ok[:6]:
        print(f"    {label:<30} E[pay|fund] ${r['pay_all']:>7,.0f}  bustAL {r['bust_post_locked']:4.1f}%  inc ${r['inc']:,.0f}/mo")

    dep = next(r for r in rows if "DEPLOYED" in r[0])
    base = next(r for r in rows if "funded_eod base" in r[0])
    print(f"\n  DEPLOYED A6/B3/mm6 : E[pay|fund] ${dep[2]['pay_all']:,.0f}  ·  bust-after-lock {dep[2]['bust_post_locked']:.1f}% of locked  ·  inc ${dep[2]['inc']:,.0f}/mo")
    print(f"  base A6/B3/mm0     : E[pay|fund] ${base[2]['pay_all']:,.0f}  ·  bust-after-lock {base[2]['bust_post_locked']:.1f}% of locked  ·  inc ${base[2]['inc']:,.0f}/mo")
    print("\n  [note] lock% is invariant to POST (lock decided in PRE phase). EOD + Databento per-trade proxy.")


if __name__ == "__main__":
    main()
