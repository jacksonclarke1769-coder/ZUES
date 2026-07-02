"""APEX 4.0 FUNDED PAYOUT MODEL — 1m-truth A-only stream, ladder-capped payouts (audit G, 2026-07-02).

Replaces the pre-4.0 funded sims (apex_funded_*.py) whose $2k/$4k-forever payout model exceeded the
real 4.0 lifetime ceiling. 4.0 rules modeled here (help-center-derived — VERIFY against the live
contract before relying on the $ numbers):
  * 50K EOD PA: trailing $2,500 set at daily close, ratchets on EOD-balance highs, locks at
    start+$100 once EOD balance >= $52,600; intraday equity below threshold still liquidates.
  * Native $1,000 daily loss limit (EOD product): day is CUT (positions closed) when combined
    intraday open loss reaches -$1k — modeled as clamping that day's realized at -$1,000 when the
    day's marked trough <= -$1k (conservative approximation on top of the bot's own $550 stop,
    which usually binds first).
  * Payout eligibility per request: balance >= $52,600; >= 5 qualifying days (>= +$250 net) since
    last payout; 50% consistency since last payout (no single day >= 50% of the profit accumulated
    since the last payout); withdraw down to no lower than $52,100.
  * Ladder caps: $1.5k, $1.5k, $2k, $2.5k, $2.5k, $3k — SIX payouts max (~$13k), then the PA CLOSES.
Stream: A-only Exit#3 + D1c, 1m-truth fills (the Phase-3 selected machine), size-to-risk budget
scaled to the funded A size (budget = $160 x A-contracts, i.e. the eval's $1,600 at A10).
"""
import os, sys, warnings, json; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strategy_engine_profileA as E
import config
import run_d1c_real as RD
import apex_eval_eod_databento as DB
from tools_1m_truth_recert import M1Map
from tools_phase3_config_sweep import a_streams_d1c

NY = "America/New_York"
START, TRAIL, LOCK_EOD, PAYOUT_FLOOR, MIN_REQ = 50_000.0, 2_500.0, 52_600.0, 52_100.0, 52_600.0
LADDER = [1_500.0, 1_500.0, 2_000.0, 2_500.0, 2_500.0, 3_000.0]      # 6 payouts then PA closes
DLL = -1_000.0
DAILY_STOP = -550.0
QUAL_DAY, QUAL_N, CONSISTENCY = 250.0, 5, 0.50
PAYOUT_EVERY_D = 30            # attempt a payout sweep every ~month once eligible


def daily_series(rows, a_size, budget_per_ct=160.0):
    """(date -> realized $, marked-trough $) at funded size with size-to-risk + $550 stop + $1k DLL."""
    budget = budget_per_ct * a_size
    ev = []
    for t in rows:
        risk1 = t["risk_usd"]
        q = min(a_size, int(budget // risk1))
        if q < 1:
            continue
        ev.append((pd.Timestamp(t["ts"]), t["R"] * risk1 * q, min(0.0, t["mae_r"]) * risk1 * q))
    ev.sort(key=lambda x: x[0])
    days = {}
    for ts, pnl, mae in ev:
        d = ts.normalize()
        rec = days.setdefault(d, dict(real=0.0, trough=0.0, stopped=False))
        if rec["stopped"]:
            continue                                   # bot's $550 stop already hit -> no later entries
        rec["trough"] = min(rec["trough"], rec["real"] + mae)
        rec["real"] += pnl
        if rec["real"] <= DAILY_STOP:
            rec["stopped"] = True
    out = []
    for d in sorted(days):
        r = days[d]
        real, trough = r["real"], r["trough"]
        if trough <= DLL:                              # Apex DLL cuts the day mid-flight
            real = max(real, DLL) if real < DLL else real
            real = DLL if real < DLL else real         # realized can't finish below the DLL cut
        out.append((d, real, trough))
    return out


def run_pa(days, start_i):
    """One funded-PA life from days[start_i:]. Returns (outcome, months, paid_total, n_payouts)."""
    bal, peak_eod, locked = START, START, False
    thr = START - TRAIL
    paid, ladder_i = 0.0, 0
    since = dict(profit=0.0, maxday=0.0, qual=0)       # accumulators since last payout
    t0 = days[start_i][0]
    last_sweep = t0
    for i in range(start_i, len(days)):
        d, real, trough = days[i]
        # intraday liquidation vs the day's FIXED threshold
        if bal + min(0.0, trough) <= thr:
            return "BUST", (d - t0).days / 30.4, paid, ladder_i
        bal += real
        since["profit"] += real
        since["maxday"] = max(since["maxday"], real)
        if real >= QUAL_DAY:
            since["qual"] += 1
        # EOD ratchet
        peak_eod = max(peak_eod, bal)
        if not locked:
            thr = max(thr, peak_eod - TRAIL)
            if peak_eod >= LOCK_EOD:
                thr = START + 100.0; locked = True
        if bal <= thr:
            return "BUST", (d - t0).days / 30.4, paid, ladder_i
        # payout sweep
        if (d - last_sweep).days >= PAYOUT_EVERY_D:
            last_sweep = d
            eligible = (bal >= MIN_REQ and since["qual"] >= QUAL_N
                        and (since["profit"] > 0 and since["maxday"] < CONSISTENCY * since["profit"]))
            if eligible:
                amt = min(LADDER[ladder_i], bal - PAYOUT_FLOOR)
                if amt > 0:
                    bal -= amt; paid += amt; ladder_i += 1
                    since = dict(profit=0.0, maxday=0.0, qual=0)
                    if ladder_i >= len(LADDER):
                        return "CLOSED_MAX", (d - t0).days / 30.4, paid, ladder_i
    return "DATA_END", (days[-1][0] - t0).days / 30.4, paid, ladder_i


def main():
    print("loading frames + A stream (exit3 + D1c, 1m truth)…", flush=True)
    d1_tz = RD.load_1m(); d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    A = a_streams_d1c(eng._features(), mp, d1_tz)
    rows = A["exit3"][0]

    results = {}
    print(f"\n{'size':>5}{'lock-ish%':>10}{'bust%':>7}{'closed-max%':>12}{'E[paid]$':>10}"
          f"{'med paid$':>10}{'med months':>11}", flush=True)
    for a_size in (3, 4, 5, 6):
        days = daily_series(rows, a_size)
        # rolling monthly starts with >=12 months of runway
        starts = [i for i, (d, _, _) in enumerate(days)
                  if (days[-1][0] - d).days >= 365 and (i == 0 or days[i-1][0].month != d.month)]
        res = [run_pa(days, s) for s in starts]
        n = len(res)
        bust = 100 * sum(1 for r in res if r[0] == "BUST") / n
        closed = 100 * sum(1 for r in res if r[0] == "CLOSED_MAX") / n
        anypaid = 100 * sum(1 for r in res if r[2] > 0) / n
        epaid = np.mean([r[2] for r in res])
        medpaid = np.median([r[2] for r in res])
        medm = np.median([r[1] for r in res])
        results[f"A{a_size}"] = dict(n=n, bust=round(bust, 1), closed_max=round(closed, 1),
                                     any_payout=round(anypaid, 1), e_paid=round(float(epaid)),
                                     med_paid=round(float(medpaid)), med_months=round(float(medm), 1))
        print(f"  A{a_size:>3}{anypaid:>9.1f}%{bust:>6.1f}%{closed:>11.1f}%{epaid:>10,.0f}"
              f"{medpaid:>10,.0f}{medm:>11.1f}", flush=True)

    with open("reports/apex_funded_40_2026-07-02.json", "w") as f:
        json.dump(dict(rules="Apex 4.0 EOD 50K (ladder 6 payouts ~$13k cap, 50% consistency, "
                             "5x$250 qual days, $1k DLL) — VERIFY vs live contract",
                       stream="A-only exit3+D1c 1m-truth, size-to-risk $160/ct",
                       results=results), f, indent=1)
    print("\n[saved] reports/apex_funded_40_2026-07-02.json — old funded E[payout] figures "
          "($22.1k/$19.4k) remain INVALID; these ladder-capped numbers supersede.", flush=True)


if __name__ == "__main__":
    main()
