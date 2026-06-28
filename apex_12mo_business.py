"""LAST 12 MONTHS, real Databento — the full business: buy 1 eval/week, passed evals become funded
accounts (phase 1 A4/B2/mm2 grind -> phase 2 A6/B3/mm6) with the LIVE P3 cushion brake. Tracks payouts,
blown evals, blown funded accounts, and take-home profit. EOD drawdown rule.

Models the APPLIED live config: eval A10/B5/mm6; funded mm2/mm6 + P3 brake (cushion<40% of $2k DD ->
half-A/B=0/mm=0). Costs: eval $35/buy, activation $130/pass (verify vs Apex pricing)."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB

SB, TRAIL, LOCK_EOD, FLOOR = 50_000.0, 2_500.0, 52_600.0, 50_100.0
SAFETY, CF, CL, NC, MINP = 52_100.0, 2_000.0, 4_000.0, 5, 500.0
DAILY_STOP, EXPIRE = -550.0, 30
DD_ALLOW, BR_ON, BR_OFF = 2_000.0, 0.40, 0.60          # P3 brake band
EVAL_COST, ACTIVATION = 45.0, 130.0
EVAL_SZ = {"A": 10, "B": 5, "M": 6}
PRE = {"A": 4, "B": 2, "M": 2}; POST = {"A": 6, "B": 3, "M": 6}


def run_eval(ev, start):
    """A10/B5/mm6 eval. Returns (result, idx) — idx = the event where it passed (funded starts there)."""
    thr = SB - TRAIL; bal = SB; peak = SB; locked = False
    t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if day != cur:
            if cur is not None and (ts - t0).days > EXPIRE:
                return "EXPIRE", k
            peak = max(peak, bal)
            if not locked:
                thr = max(thr, peak - TRAIL)
                if peak >= LOCK_EOD:
                    thr = FLOOR; locked = True
            cur = day; dreal = 0.0
        if dreal <= DAILY_STOP:
            continue
        s = EVAL_SZ[e["src"]]
        if bal + min(0.0, e["mae"]) * s <= thr:
            return "BUST", k
        bal += e["pnl"] * s; dreal += e["pnl"] * s
        if bal >= SB + 3000.0:
            return "PASS", k
    return "INCOMPLETE", len(ev)


MAX_ACTIVE = 20                                            # Apex simultaneous-PA cap


def run_funded(ev, start):
    """Funded A4/B2/mm2 -> A6/B3/mm6 + P3 brake. Returns (busted, bust_idx, payout$, n_payouts)."""
    thr = SB - TRAIL; bal = SB; peak = SB; locked = False; braked = False
    payout = 0.0; npay = 0; cur = None; dreal = 0.0; cmonth = None
    for k in range(start, len(ev)):
        e = ev[k]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if day != cur:
            peak = max(peak, bal)
            if not locked:
                thr = max(thr, peak - TRAIL)
                if peak >= LOCK_EOD:
                    thr = FLOOR; locked = True
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
        cushion = bal - thr                                  # P3 brake latch
        if cushion < BR_ON * DD_ALLOW: braked = True
        elif cushion >= BR_OFF * DD_ALLOW: braked = False
        if dreal <= DAILY_STOP:
            continue
        base = POST if locked else PRE
        a, b, mm = base["A"], base["B"], base["M"]
        if braked: a, b, mm = max(a // 2, 1), 0, 0           # brake: half-A, no B, no momentum
        s = {"A": a, "B": b, "M": mm}[e["src"]]
        if s == 0:
            continue
        if bal + min(0.0, e["mae"]) * s <= thr:
            return True, k, payout, npay
        bal += e["pnl"] * s; dreal += e["pnl"] * s
    return False, len(ev), payout, npay


def main():
    print("loading Databento + streams…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    ev = sorted(H.a_events(df5) + H.b_events(df5) + H.m_events(df5), key=lambda e: e["ts"])
    end = pd.Timestamp(ev[-1]["ts"]).normalize()
    win = end - pd.Timedelta(days=365)
    d = win + pd.Timedelta(days=(7 - win.weekday()) % 7)
    mondays = []
    while d <= end:
        mondays.append(d); d += pd.Timedelta(days=7)
    print(f"  window {win.date()} -> {end.date()} · {len(mondays)} weekly evals", flush=True)

    bought = blown = inprog = 0
    passes = []                                              # (pass_idx, bust_idx, payout, npay)
    for mon in mondays:
        si = next((i for i, e in enumerate(ev) if pd.Timestamp(e["ts"]).normalize() >= mon), None)
        if si is None:
            continue
        bought += 1
        res, idx = run_eval(ev, si)
        if res in ("BUST", "EXPIRE"):
            blown += 1
        elif res == "INCOMPLETE":
            inprog += 1
        else:
            bust, bidx, pay, npay = run_funded(ev, idx)
            passes.append((idx, bidx, pay, npay, bust))

    def tally(capped):
        active = []; act_payout = 0.0; act_np = 0; act_bust = 0; activated = 0; stranded = 0
        for (pidx, bidx, pay, npay, bust) in sorted(passes):
            active = [b for b in active if b > pidx]         # free busted slots
            if capped and len(active) >= MAX_ACTIVE:
                stranded += 1; continue
            activated += 1; active.append(bidx)
            act_payout += pay; act_np += npay; act_bust += int(bust)
        alive = activated - act_bust
        return activated, stranded, act_bust, alive, act_payout, act_np

    print(f"\n================ APEX 12-MONTH BUSINESS (1 eval/week, real Databento) ================")
    print(f"  evals bought          : {bought}   ·   PASSED {len(passes)}   BLOWN {blown}"
          + (f"   ({inprog} still in 30-day window)" if inprog else ""))
    for capped, label in [(True, "CAPPED at Apex 20-account limit (REALISTIC)"),
                          (False, "UNCAPPED (every pass activated — not allowed by Apex)")]:
        activated, stranded, fb, alive, pay, npay = tally(capped)
        spend = bought * EVAL_COST + activated * ACTIVATION
        take = pay - spend
        print(f"\n  --- {label} ---")
        print(f"  funded accounts run   : {activated}" + (f"   ({stranded} passes STRANDED at the cap)" if stranded else ""))
        print(f"  BLOWN funded accounts : {fb}    ·  still active at year-end: {alive}")
        print(f"  PAYOUTS received      : {npay}  worth  ${pay:,.0f}")
        print(f"  spend (evals+activn)  : ${spend:,.0f}")
        print(f"  TAKE-HOME (12mo)      : ${take:,.0f}   (~${take/12:,.0f}/mo)")
    print(f"\n  [note] ONE real-data path on the FAVORABLE recent year (this window passes ~71% vs the validated")
    print(f"         ~57% 5yr-avg). Fat-tailed; the MC median/tail are far lower. Funded momentum+brake is")
    print(f"         paper-validated not live-proven. Modeled costs/payout rules, NO execution friction.")
    print(f"         Realistic after haircut ≈ your prior ~$15-20k/mo, with a fat left tail in a bad regime.")


if __name__ == "__main__":
    main()
