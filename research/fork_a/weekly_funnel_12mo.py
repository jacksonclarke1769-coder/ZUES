"""WEEKLY-START FULL FUNNEL — last 12 months of real data (operator request 2026-07-17).

Start one Apex 50K account per WEEK over the final 12 months of the certified stream.
Chain: eval (locked machine, $1,200/cap-10, $550 stop, $1k DLL, 30d clock)
  -> on PASS, funded PA opens the next trading day (certified funded fraction:
     budget $480 = 0.4 x eval, the A4/A10 convention)
  -> funded runs the certified Apex 4.0 ladder (6 payouts, 50% consistency-since-last-payout,
     5 x $250 qualifying days, 30d spacing, safety-net floor) until bust / ladder-complete /
     DATA END (censored — funded lifetimes are ~16mo, so most funded runs are censored).

REUSES the certified functions by import: build_events, day_rows, eval_run (verbatim), and a
start-parameterized copy of funded_paid's inner loop (logic byte-identical; only the start index
and per-run reporting differ). Read-only research; writes only reports/fork_a/06_weekly_funnel.json.
"""
import os, sys, json, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))

import strategy_engine_profileA as E
import config
import run_d1c_real as RD
import apex_eval_eod_databento as DB
from tools_1m_truth_recert import M1Map
from tools_phase3_config_sweep import a_streams_d1c
from tools_account_size_research import build_events, day_rows, eval_run, SPECS

SPEC = SPECS["50K"]
EVAL_BUDGET, EVAL_QTY = 1_200, 10          # locked machine (cap-10 re-lock DEC-20260705-1102)
FUND_BUDGET, FUND_QTY = 480, 10            # certified funded fraction 0.4x (A4/A10)


def funded_run_from(days, s0, spec):
    """Start-parameterized copy of tools_account_size_research.funded_paid's inner loop.
    Returns (paid $, n_payouts, outcome, days_alive). Logic identical; reporting added."""
    sb, tr = spec["start"], spec["trail"]
    ladder = spec["ladder"]
    min_req, floor = sb + tr + 100.0, sb + tr - 400.0
    thr, bal, peak, locked = sb - tr, sb, sb, False
    li, paid = 0, 0.0
    since = dict(profit=0.0, maxd=0.0, qual=0)
    last = days[s0][0]
    for i in range(s0, len(days)):
        d, real, trough = days[i]
        if bal + min(0.0, trough) <= thr:
            return paid, li, "BUST", (d - days[s0][0]).days
        bal += real
        since["profit"] += real; since["maxd"] = max(since["maxd"], real)
        if real >= 250.0:
            since["qual"] += 1
        peak = max(peak, bal)
        if not locked:
            thr = max(thr, peak - tr)
            if peak - tr >= sb + 100.0:
                thr = sb + 100.0; locked = True
        if bal <= thr:
            return paid, li, "BUST", (d - days[s0][0]).days
        if (d - last).days >= 30:
            last = d
            if (bal >= min_req and since["qual"] >= 5 and since["profit"] > 0
                    and since["maxd"] < 0.5 * since["profit"]):
                amt = min(ladder[li], bal - floor)
                if amt > 0:
                    bal -= amt; paid += amt; li += 1
                    since = dict(profit=0.0, maxd=0.0, qual=0)
                    if li >= len(ladder):
                        return paid, li, "LADDER_COMPLETE", (d - days[s0][0]).days
    return paid, li, "CENSORED_DATA_END", (days[-1][0] - days[s0][0]).days


def main():
    print("loading frames + locked A stream (exit3 + D1c, 1m truth)…", flush=True)
    d1_tz = RD.load_1m(); d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    rows = a_streams_d1c(eng._features(), mp, d1_tz)["exit3"][0]
    print(f"stream rows: {len(rows)}", flush=True)

    ev_e = build_events(rows, EVAL_BUDGET, EVAL_QTY)
    ev_f = build_events(rows, FUND_BUDGET, FUND_QTY)
    days_e = day_rows(ev_e, SPEC["stop"], SPEC["dll"])
    days_f = day_rows(ev_f, SPEC["stop"], SPEC["dll"])
    data_end = days_e[-1][0]
    window_start = data_end - pd.Timedelta(days=365)
    print(f"window: {window_start.date()} -> {data_end.date()}", flush=True)

    # weekly eval starts inside the window
    starts, last_d = [], None
    for i, (d, _, _) in enumerate(days_e):
        if d < window_start:
            continue
        if last_d is None or (d - last_d).days >= 7:
            starts.append(i); last_d = d
    print(f"weekly starts: {len(starts)}", flush=True)

    accounts = []
    for s0 in starts:
        d0 = days_e[s0][0]
        outcome, dur = eval_run(days_e, s0, SPEC)
        acct = dict(start=str(d0.date()), eval=outcome, eval_days=dur,
                    paid=0.0, payouts=0, funded="", funded_days=None)
        if outcome == "PASS":
            pass_date = d0 + pd.Timedelta(days=dur)
            f0 = next((j for j, (fd, _, _) in enumerate(days_f) if fd > pass_date), None)
            if f0 is not None:
                paid, n_po, f_out, f_days = funded_run_from(days_f, f0, SPEC)
                acct.update(paid=paid, payouts=n_po, funded=f_out, funded_days=f_days)
            else:
                acct["funded"] = "NO_DATA_AFTER_PASS"
        accounts.append(acct)

    df = pd.DataFrame(accounts)
    n = len(df)
    print("\n================ WEEKLY FUNNEL — LAST 12 MONTHS ================")
    print(df.to_string(index=False))
    print("\n--- summary ---")
    print("eval outcomes:", df["eval"].value_counts().to_dict())
    passers = df[df["eval"] == "PASS"]
    got_paid = passers[passers.payouts > 0]
    print(f"passed: {len(passers)}/{n} | funded accts with >=1 payout: {len(got_paid)} "
          f"| total payouts collected by data end: ${df.paid.sum():,.0f} "
          f"| total payout count: {int(df.payouts.sum())}")
    print("funded outcomes:", passers["funded"].value_counts().to_dict())
    json.dump(dict(window=[str(window_start.date()), str(data_end.date())],
                   accounts=accounts,
                   summary=dict(n=n, eval=df["eval"].value_counts().to_dict(),
                                passed=int(len(passers)), paid_accts=int(len(got_paid)),
                                total_paid=float(df.paid.sum()),
                                total_payouts=int(df.payouts.sum()))),
              open(os.path.expanduser(
                  "~/trading-team/bot/nq-liq-bot/reports/fork_a/06_weekly_funnel.json"), "w"),
              indent=1)
    print("written: reports/fork_a/06_weekly_funnel.json")


if __name__ == "__main__":
    main()
