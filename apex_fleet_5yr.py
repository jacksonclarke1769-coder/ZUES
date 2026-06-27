"""5 YEARS, real Databento: weekly funded-account buys, capped at Apex's 20 simultaneous PA accounts
(buy only when a slot is free; busts free slots). Tracks busts, active-at-end, payouts, and money spent
on EVALS (incl. the busted attempts) + ACTIVATIONS. OPTIMISED vs DEPLOYED config."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB

START, TRAIL, LOCK_EOD, FLOOR = 50_000.0, 2_500.0, 52_600.0, 50_100.0
SAFETY, CF, CL, NC, MINP = 52_100.0, 2_000.0, 4_000.0, 5, 500.0
DAILY_STOP = -550.0
# ---- cost assumptions (Apex 50K; verify vs current pricing) ----
EVAL_COST = 35.0          # per eval attempt (sale/reset price)
ACTIVATION = 130.0        # one-time PA activation per funded account
EVAL_PASS = 0.575         # eval pass rate -> attempts per funded acct = 1/pass
MAX_ACTIVE = 20           # Apex simultaneous-account cap


def life(ev, start, end_ts, pre, post, brake):
    thr = START - TRAIL; bal = START; peak = START; locked = False
    payout = 0.0; npay = 0; t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0; cmonth = None
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if ts > end_ts:
            break
        if cur is None:
            cur = day
        if day != cur:
            peak = max(peak, bal)
            if not locked:
                if peak >= LOCK_EOD:
                    thr = FLOOR; locked = True
                else:
                    thr = max(thr, peak - TRAIL)
            cur = day; dreal = 0.0
        m = (ts.year, ts.month)
        if cmonth is None:
            cmonth = m
        if m != cmonth:
            if locked and bal > SAFETY:
                cap = CF if npay < NC else CL
                w = min(bal - SAFETY, cap)
                if w >= MINP:
                    bal -= w; payout += w; npay += 1
            cmonth = m
        if dreal <= DAILY_STOP:
            continue
        s = (post if locked else pre).get(e["src"], 0)
        if s == 0:
            continue
        if brake and (bal - thr) < brake[0]:
            s *= brake[1]
        if bal + min(0.0, e["mae"]) * s <= thr:
            return dict(busted=True, bust=ts, payout=payout, locked=locked)
        bal += e["pnl"] * s; dreal += e["pnl"] * s
    return dict(busted=False, bust=None, payout=payout, locked=locked)


def fleet(ev, mondays, end, pre, post, brake, label):
    out = {}
    for mon in mondays:
        si = next((i for i, e in enumerate(ev) if pd.Timestamp(e["ts"]).normalize() >= mon), None)
        out[mon] = life(ev, si, end, pre, post, brake) if si is not None else None
    # capped buying
    active = []; bought = []
    for mon in mondays:
        active = [bd for bd in active if bd is None or bd > mon]
        if len([a for a in active]) < MAX_ACTIVE and out.get(mon):
            bought.append(out[mon]); active.append(out[mon]["bust"])
    n = len(bought)
    busted = sum(1 for a in bought if a["busted"])
    active_end = sum(1 for a in bought if a["bust"] is None or a["bust"] > end - pd.Timedelta(days=1))
    payouts = sum(a["payout"] for a in bought)
    evals = n / EVAL_PASS
    eval_spend = evals * EVAL_COST; act_spend = n * ACTIVATION
    print(f"\n  ===== {label} =====")
    print(f"  funded accounts bought (capped @{MAX_ACTIVE}): {n}   over {len(mondays)} weeks")
    print(f"  busted: {busted}    still active at end: {active_end}")
    print(f"  payouts made:        ${payouts:>11,.0f}")
    print(f"  spent on evals:      ${eval_spend:>11,.0f}   ({evals:.0f} attempts @ ${EVAL_COST:.0f}, {EVAL_PASS:.0%} pass)")
    print(f"  spent on activations:${act_spend:>11,.0f}   ({n} @ ${ACTIVATION:.0f})")
    print(f"  total spent:         ${eval_spend+act_spend:>11,.0f}")
    print(f"  NET (payouts−spend): ${payouts-eval_spend-act_spend:>11,.0f}   "
          f"·   ${(payouts-eval_spend-act_spend)/60:,.0f}/mo over 5yr")


def main():
    print("loading Databento + funded streams (one-time)…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    ev = sorted(H.a_events(df5) + H.b_events(df5) + H.m_events(df5), key=lambda e: e["ts"])
    end = pd.Timestamp(ev[-1]["ts"]).normalize()
    start = pd.Timestamp(ev[0]["ts"]).normalize()
    d = start + pd.Timedelta(days=(7 - start.weekday()) % 7)
    mondays = []
    while d <= end:
        mondays.append(d); d += pd.Timedelta(days=7)
    print(f"  window {start.date()} -> {end.date()}  ·  {len(mondays)} weekly buys, capped @{MAX_ACTIVE}", flush=True)

    fleet(ev, mondays, end, {"A": 4, "B": 2, "M": 2}, {"A": 6, "B": 3, "M": 6}, (1000, 0.5),
          "OPTIMISED  A4/B2/mm2 + cushion-brake -> A6/B3/mm6")
    fleet(ev, mondays, end, {"A": 4, "B": 2, "M": 0}, {"A": 6, "B": 3, "M": 0}, None,
          "DEPLOYED  A4/B2 mm0 -> A6/B3 mm0")
    print("\n  [note] real Databento 5yr; EOD drawdown; 20-acct cap; costs are assumptions (verify vs Apex).")
    print("         correlated edge -> busts CLUSTER in bad regimes (not independent).")


if __name__ == "__main__":
    main()
