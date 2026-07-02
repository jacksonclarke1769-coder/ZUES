"""FLEET BACKTEST — last 12 months, one new Apex 50K EOD eval per week, 20-account cap.

RESEARCH ONLY. Real Databento data; the locked ZEUS machine's own 1m-truth stream (A-only Exit#3 +
D1c). Every account trades the SAME signals (correlation 1 — reality of a copier fleet): outcomes
differ only by start date and phase. Eval budget $1,600 (locked), funded budget $640 (the certified
40% fraction). DLL-honest day model ($1k cut). Apex 4.0: eval 3k target/2.5k trail/30d clock;
PA ladder 1.5/1.5/2/2.5/2.5/3k (6 payouts -> closed), 50% consistency since last payout, 5x$250
qualifying days, min-request $52.6k, withdraw floor $52.1k. Fees: $45/mo eval sub, $130 PA activation.
Slot rule: active accounts (evals + PAs) <= 20; a new eval starts each Monday only if a slot is free.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
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
from tools_account_size_research import build_events, day_rows

START_BAL, TRAIL, TARGET = 50_000.0, 2_500.0, 3_000.0
LOCK_AT = START_BAL + 100.0
LADDER = [1_500.0, 1_500.0, 2_000.0, 2_500.0, 2_500.0, 3_000.0]
MIN_REQ, FLOOR = 52_600.0, 52_100.0
EVAL_BUDGET, FUND_BUDGET = 1_600.0, 640.0
STOP, DLL = 550.0, 1_000.0
CAP, EXPIRE_D = 20, 30
EVAL_FEE_MO, PA_FEE = 45.0, 130.0


class Acct:
    _n = 0

    def __init__(self, day):
        Acct._n += 1
        self.id = Acct._n
        self.phase = "EVAL"
        self.t0 = day
        self.bal, self.peak, self.locked = START_BAL, START_BAL, False
        self.thr = START_BAL - TRAIL
        self.ladder_i, self.paid = 0, 0.0
        self.since = dict(profit=0.0, maxd=0.0, qual=0)
        self.last_sweep = day
        self.fees = EVAL_FEE_MO
        self.status = "ACTIVE"

    def step(self, day, real, trough):
        """One trading day. Returns True if the account is finished (slot freed)."""
        if self.phase == "EVAL" and (day - self.t0).days > EXPIRE_D:
            self.status = "EXPIRED"; return True
        if self.bal + min(0.0, trough) <= self.thr:
            self.status = "BUST_" + self.phase; return True
        self.bal += real
        if self.phase == "FUNDED":
            self.since["profit"] += real
            self.since["maxd"] = max(self.since["maxd"], real)
            if real >= 250.0:
                self.since["qual"] += 1
        self.peak = max(self.peak, self.bal)
        if not self.locked:
            self.thr = max(self.thr, self.peak - TRAIL)
            if self.peak - TRAIL >= LOCK_AT:
                self.thr = LOCK_AT; self.locked = True
        if self.bal <= self.thr:
            self.status = "BUST_" + self.phase; return True
        if self.phase == "EVAL":
            if self.bal >= START_BAL + TARGET:                 # PASS -> becomes a PA next day
                self.phase = "FUNDED"
                self.fees += PA_FEE
                self.bal, self.peak, self.locked = START_BAL, START_BAL, False
                self.thr = START_BAL - TRAIL
                self.t0 = day; self.last_sweep = day
            return False
        # FUNDED payout sweep
        if (day - self.last_sweep).days >= 30:
            self.last_sweep = day
            ok = (self.bal >= MIN_REQ and self.since["qual"] >= 5 and self.since["profit"] > 0
                  and self.since["maxd"] < 0.5 * self.since["profit"])
            if ok:
                amt = min(LADDER[self.ladder_i], self.bal - FLOOR)
                if amt > 0:
                    self.bal -= amt; self.paid += amt; self.ladder_i += 1
                    self.since = dict(profit=0.0, maxd=0.0, qual=0)
                    if self.ladder_i >= len(LADDER):
                        self.status = "CLOSED_MAX"; return True
        return False


def main():
    print("loading locked-machine stream…", flush=True)
    d1_tz = RD.load_1m(); d1 = d1_tz.copy(); d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
    rows = a_streams_d1c(eng._features(), mp, d1_tz)["exit3"][0]

    ev_days = {d: (r, t) for d, r, t in day_rows(build_events(rows, EVAL_BUDGET, 60), STOP, DLL)}
    fu_days = {d: (r, t) for d, r, t in day_rows(build_events(rows, FUND_BUDGET, 60), STOP, DLL)}

    end = max(ev_days)
    start = end - pd.Timedelta(days=365)
    cal = pd.date_range(start, end, freq="B", tz=str(end.tz))
    print(f"window {start.date()} -> {end.date()} · trading days w/ signals: "
          f"{sum(1 for d in cal if d in ev_days)}", flush=True)

    active, done = [], []
    started = 0
    monthly_fees = 0.0
    for day in cal:
        if day.weekday() == 0 and len(active) < CAP:            # Monday: start an eval if slot free
            active.append(Acct(day)); started += 1
        for a in list(active):
            a.fees += 0.0
            key = day
            series = ev_days if a.phase == "EVAL" else fu_days
            if key not in series:
                # still charge eval clock via dates; nothing to mark today
                if a.phase == "EVAL" and (day - a.t0).days > EXPIRE_D:
                    a.status = "EXPIRED"; active.remove(a); done.append(a)
                continue
            real, trough = series[key]
            if a.step(day, real, trough):
                active.remove(a); done.append(a)
        # monthly eval subscription fees for active evals
        if day.day == 1:
            monthly_fees += EVAL_FEE_MO * sum(1 for a in active if a.phase == "EVAL")

    allacc = done + active
    passed = [a for a in allacc if a.phase == "FUNDED" or a.status in ("CLOSED_MAX", "BUST_FUNDED")]
    ev_bust = [a for a in done if a.status == "BUST_EVAL"]
    expired = [a for a in done if a.status == "EXPIRED"]
    in_eval = [a for a in active if a.phase == "EVAL"]
    funded_live = [a for a in active if a.phase == "FUNDED"]
    fu_bust = [a for a in done if a.status == "BUST_FUNDED"]
    closed = [a for a in done if a.status == "CLOSED_MAX"]
    gross = sum(a.paid for a in allacc)
    fees = sum(a.fees for a in allacc) + monthly_fees

    print(f"\n=== FLEET, {start.date()} -> {end.date()} · locked machine · $1,600 eval/$640 funded ===")
    print(f"  evals started:        {started}  (weekly Mondays, {CAP}-account cap)")
    print(f"  PASSED -> funded:     {len(passed)}")
    print(f"  eval BUSTED:          {len(ev_bust)}")
    print(f"  eval EXPIRED (30d):   {len(expired)}")
    print(f"  still IN EVAL at end: {len(in_eval)}")
    print(f"  funded ACTIVE at end: {len(funded_live)}  (payouts so far included below)")
    print(f"  funded BUSTED:        {len(fu_bust)}  (after paying ${sum(a.paid for a in fu_bust):,.0f})")
    print(f"  funded LADDER-CLOSED: {len(closed)}")
    print(f"  --------------------------------------------")
    print(f"  GROSS PAYOUTS:        ${gross:,.0f}")
    print(f"  fees (subs+PA):       ${fees:,.0f}")
    print(f"  NET:                  ${gross - fees:,.0f}")
    per = sorted((a.paid for a in allacc if a.paid > 0), reverse=True)
    print(f"  paying accounts: {len(per)} · payouts/acct: {per[:8]}{'…' if len(per) > 8 else ''}")
    if funded_live:
        cush = [f"{a.bal - a.thr:,.0f}" for a in funded_live[:8]]
        print(f"  live funded cushions ($ above threshold): {cush}{'…' if len(funded_live) > 8 else ''}")


if __name__ == "__main__":
    main()
