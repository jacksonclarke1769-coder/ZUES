"""LAST 6 MONTHS, real Databento — build a fleet of 20 funded accounts (Apex cap) then maintain it.
Rule: each week, buy an eval for every OPEN slot (toward 20 funded running); a passed eval becomes a
funded account (A4/B2/mm2 -> A6/B3/mm6 + P3 brake); once 20 are running we only rebuy when one busts.
Reports payouts, money spent on evals/activations, blown evals, blown funded accounts, time to 1st payout."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB

SB, TRAIL, LOCK_EOD, FLOOR, EXPIRE, DAILY_STOP = 50_000.0, 2_500.0, 52_600.0, 50_100.0, 30, -550.0
SAFETY, CF, CL, NC, MINP = 52_100.0, 2_000.0, 4_000.0, 5, 500.0
DD_ALLOW, BR_ON, BR_OFF = 2_000.0, 0.40, 0.60
EVAL_COST, ACTIVATION, MAX_ACCTS = 45.0, 130.0, 20
EVAL = {"A": 10, "B": 5, "M": 6}; PRE = {"A": 4, "B": 2, "M": 2}; POST = {"A": 6, "B": 3, "M": 6}


def run_eval(ev, start):
    thr = SB - TRAIL; bal = SB; peak = SB; t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if day != cur:
            if cur is not None and (ts - t0).days > EXPIRE: return "BLOWN", k
            peak = max(peak, bal); thr = max(thr, peak - TRAIL); cur = day; dreal = 0.0
        if dreal <= DAILY_STOP: continue
        s = EVAL[e["src"]]
        if bal + min(0.0, e["mae"]) * s <= thr: return "BLOWN", k
        bal += e["pnl"] * s; dreal += e["pnl"] * s
        if bal >= SB + 3000: return "PASS", k
    return "INCOMPLETE", len(ev) - 1


def run_funded(ev, start):
    """Returns (busted, free_idx, payout$, n_payouts, first_payout_idx)."""
    thr = SB - TRAIL; bal = SB; peak = SB; locked = False; braked = False
    payout = 0.0; npay = 0; first_pay = None; cur = None; dreal = 0.0; cmonth = None
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if day != cur:
            peak = max(peak, bal)
            if not locked:
                thr = max(thr, peak - TRAIL)
                if peak >= LOCK_EOD: thr = FLOOR; locked = True
            cur = day; dreal = 0.0
        m = (ts.year, ts.month)
        if cmonth is None: cmonth = m
        if m != cmonth:
            if locked and bal > SAFETY:
                cap = CF if npay < NC else CL
                w = min(bal - SAFETY, cap)
                if w >= MINP:
                    bal -= w; payout += w; npay += 1
                    if first_pay is None: first_pay = k
            cmonth = m
        cushion = bal - thr
        if cushion < BR_ON * DD_ALLOW: braked = True
        elif cushion >= BR_OFF * DD_ALLOW: braked = False
        if dreal <= DAILY_STOP: continue
        base = POST if locked else PRE
        a, b, mm = base["A"], base["B"], base["M"]
        if braked: a, b, mm = max(a // 2, 1), 0, 0
        s = {"A": a, "B": b, "M": mm}[e["src"]]
        if s == 0: continue
        if bal + min(0.0, e["mae"]) * s <= thr:
            return True, k, payout, npay, first_pay
        bal += e["pnl"] * s; dreal += e["pnl"] * s
    return False, len(ev) - 1, payout, npay, first_pay


def main():
    print("loading Databento + streams…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    ev = sorted(H.a_events(df5) + H.b_events(df5) + H.m_events(df5), key=lambda e: e["ts"])
    end = pd.Timestamp(ev[-1]["ts"]).normalize(); win = end - pd.Timedelta(days=182)
    d = win + pd.Timedelta(days=(7 - win.weekday()) % 7)
    mondays = []
    while d <= end:
        mondays.append(d); d += pd.Timedelta(days=7)
    t0 = pd.Timestamp(mondays[0])
    print(f"  window {win.date()} -> {end.date()} · {len(mondays)} weeks · cap {MAX_ACCTS} accts", flush=True)

    # EVALS_PER_WEEK evals bought per week, STAGGERED within the week (decorrelate starts); ramp toward 20.
    EVALS_PER_WEEK = 2
    OFFSETS = {1: [0], 2: [0, 3], 3: [0, 2, 4]}[EVALS_PER_WEEK]
    pipeline = []                           # list of (free_idx, is_funded) currently occupying a slot
    evals = blown_evals = inprog_evals = funded_made = funded_bust = npayouts = 0
    payout_total = 0.0; first_payout_idx = None; reached20_week = None
    last_idx = len(ev) - 1
    for wi, mon in enumerate(mondays):
        for off in OFFSETS:
            target = (pd.Timestamp(mon) + pd.Timedelta(days=off)).normalize()
            bi = next((i for i in range(len(ev)) if pd.Timestamp(ev[i]["ts"]).normalize() >= target), None)
            if bi is None: continue
            pipeline = [(fi, fn) for (fi, fn) in pipeline if fi > bi]
            if len(pipeline) >= MAX_ACCTS: continue
            if (pd.Timestamp(ev[last_idx]["ts"]) - pd.Timestamp(ev[bi]["ts"])).days < EXPIRE: continue
            evals += 1
            res, eidx = run_eval(ev, bi)
            if res == "PASS":
                bust, fidx, pay, np_, fp = run_funded(ev, eidx)
                funded_made += 1; payout_total += pay; npayouts += np_
                if bust: funded_bust += 1
                pipeline.append((fidx, True))
                if fp is not None and (first_payout_idx is None or fp < first_payout_idx):
                    first_payout_idx = fp
            elif res == "BLOWN":
                blown_evals += 1; pipeline.append((eidx, False))
            else:
                inprog_evals += 1; pipeline.append((last_idx + 1, False))
        si = next((i for i, e in enumerate(ev) if pd.Timestamp(e["ts"]).normalize() >= pd.Timestamp(mon)), 0)
        active_funded = sum(1 for (fi, fn) in pipeline if fn and fi > si)
        if active_funded >= MAX_ACCTS and reached20_week is None:
            reached20_week = wi

    eval_spend = evals * EVAL_COST; act_spend = funded_made * ACTIVATION
    resolved = blown_evals + funded_made
    print(f"\n================ 6-MONTH FLEET BUILD (ramp to {MAX_ACCTS}, replace on bust) ================")
    print(f"  evals bought          : {evals}   (resolved {resolved}: {funded_made} passed / {blown_evals} BLOWN"
          f" = {100*funded_made/max(1,resolved):.0f}% pass" + (f"; {inprog_evals} still running)" if inprog_evals else ")"))
    print(f"  funded accounts made  : {funded_made}     ·  BLOWN funded accounts: {funded_bust}")
    print(f"  reached {MAX_ACCTS} accounts    : " + (f"week {reached20_week+1}" if reached20_week is not None else "not within 6mo"))
    print(f"  PAYOUTS               : {npayouts}  worth  ${payout_total:,.0f}")
    if first_payout_idx is not None:
        d2p = (pd.Timestamp(ev[first_payout_idx]["ts"]) - t0).days
        print(f"  TIME TO FIRST PAYOUT  : {d2p} days (~{d2p/7:.0f} weeks) from the first eval bought")
    else:
        print(f"  TIME TO FIRST PAYOUT  : none in the 6-month window")
    print(f"\n  spend: evals {evals}×${EVAL_COST:.0f}=${eval_spend:,.0f}  +  activations {funded_made}×${ACTIVATION:.0f}=${act_spend:,.0f}  =  ${eval_spend+act_spend:,.0f}")
    print(f"  TAKE-HOME (payouts − spend): ${payout_total - eval_spend - act_spend:,.0f}")
    print(f"\n  [note] ONE real-data path on a favorable recent window (passes ~71% vs 57% avg); momentum+brake")
    print(f"         funded config is paper-validated not live-proven; no execution friction. Budget ~half realistic.")


if __name__ == "__main__":
    main()
