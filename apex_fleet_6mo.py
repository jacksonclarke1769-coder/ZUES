"""LAST 6 MONTHS, real Databento: buy 1 funded account every Monday, run each to the data end.
Track per-account lock/payout/bust and the fleet totals (payouts, busts, survivors at the end).
Shows DEPLOYED (A4/B2 mm0, no brake) vs OPTIMISED (A4/B2/mm2 grind + cushion brake -> A6/B3/mm6)."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import apex_eval_deployed as H
import apex_eval_eod_databento as DB

START, TRAIL, LOCK_EOD, FLOOR = 50_000.0, 2_500.0, 52_600.0, 50_100.0
SAFETY, CF, CL, NC, MINP = 52_100.0, 2_000.0, 4_000.0, 5, 500.0
DAILY_STOP = -550.0


def life(ev, start, end_ts, pre, post, brake):
    thr = START - TRAIL; bal = START; peak = START; locked = False; d2l = None
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
                    thr = FLOOR; locked = True; d2l = (ts - t0).days
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
            return dict(busted=True, locked=locked, d2l=d2l, payout=payout)
        bal += e["pnl"] * s; dreal += e["pnl"] * s
    return dict(busted=False, locked=locked, d2l=d2l, payout=payout)


def run_fleet(ev, mondays, pre, post, brake, label, ledger=False):
    accts = []
    for mon in mondays:
        si = next((i for i, e in enumerate(ev) if pd.Timestamp(e["ts"]).normalize() >= mon), None)
        if si is None:
            continue
        r = life(ev, si, ev[-1]["ts"], pre, post, brake); r["start"] = mon
        accts.append(r)
    n = len(accts)
    bust = sum(1 for a in accts if a["busted"])
    locked_alive = sum(1 for a in accts if not a["busted"] and a["locked"])
    grind_alive = sum(1 for a in accts if not a["busted"] and not a["locked"])
    paid = sum(a["payout"] for a in accts)
    print(f"\n  ===== {label} =====")
    if ledger:
        print(f"  {'started':>11}{'outcome':>26}{'payout':>10}")
        for a in accts:
            st = ("BUSTED" if a["busted"] else ("LOCKED · paying" if a["locked"] else "grinding (not yet locked)"))
            extra = f"  lock@{a['d2l']}d" if a["locked"] else ""
            print(f"  {str(a['start'].date()):>11}{st + extra:>26}${a['payout']:>9,.0f}")
    print(f"  accounts bought: {n}   busted: {bust}   alive: {n-bust}  "
          f"(locked·paying {locked_alive} + grinding {grind_alive})")
    print(f"  total payouts collected: ${paid:,.0f}   ·   avg ${paid/n:,.0f}/account")
    return n, bust, locked_alive, grind_alive, paid


def main():
    print("loading Databento + funded streams…", flush=True)
    df5 = DB.load_databento_5m()
    H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
    ev = sorted(H.a_events(df5) + H.b_events(df5) + H.m_events(df5), key=lambda e: e["ts"])
    end = pd.Timestamp(ev[-1]["ts"]).normalize()
    win_start = end - pd.Timedelta(days=182)
    # Mondays in the last 6 months
    d = win_start + pd.Timedelta(days=(7 - win_start.weekday()) % 7)
    mondays = []
    while d <= end:
        mondays.append(d); d += pd.Timedelta(days=7)
    print(f"  window {win_start.date()} -> {end.date()}  ·  {len(mondays)} weekly buys", flush=True)

    run_fleet(ev, mondays, {"A": 4, "B": 2, "M": 2}, {"A": 6, "B": 3, "M": 6}, (1000, 0.5),
              "OPTIMISED  A4/B2/mm2 + cushion-brake -> A6/B3/mm6", ledger=True)
    run_fleet(ev, mondays, {"A": 4, "B": 2, "M": 0}, {"A": 6, "B": 3, "M": 0}, None,
              "DEPLOYED  A4/B2 mm0 -> A6/B3 mm0 (current config)")
    print("\n  [note] real Databento; EOD drawdown; each account runs from its Monday to the data end")
    print("         (late buys haven't had time to lock). Assumes 1 funded acct obtained per week.")


if __name__ == "__main__":
    main()
