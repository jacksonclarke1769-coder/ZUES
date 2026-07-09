"""5-YEAR MULTI-FIRM PROP FLEET SIM (operator 2026-07-04).

Rules requested:
  * ONE eval open at a time, a new eval started ~weekly (serial pipeline).
  * Passes mint a FUNDED account. Route to APEX until 20 Apex funded are LIVE; overflow -> other
    firms round-robin (MFFU, Topstep, Tradeify) per the certified firm list.
  * Apex/Topstep/Tradeify funded = 6-payout ladder then the account CLOSES (a new eval refills it).
  * MFFU funded = UNCAPPED continuing (~$/mo), stays open (per Prop Firms & Economics §5).
  * Real Databento data. Frozen machine (A/Exit#3/D1c, 1m-truth) UNCHANGED. No strategy edits.

Engines reused (certified): eval_eod() [Apex EOD rule, $550 stop baked in], daily_series()+run_pa
logic [Apex 6-payout ladder, ~$12.65k/A4]. Eval difficulty uses the Apex engine for EVERY firm =
CONSERVATIVE for non-Apex (they certify EASIER: Topstep 65.1 / MFFU 67.3 / Tradeify 68.1 vs Apex 58.2).
"""
import os, sys, warnings, json
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import strategy_engine_profileA as E
import config, run_d1c_real as RD, apex_eval_eod_databento as DB
import funded_rules as FR
from tools_1m_truth_recert import M1Map
from tools_phase3_config_sweep import a_streams_d1c
from apex_funded_40 import (daily_series, START as F_START, TRAIL, LOCK_EOD, PAYOUT_FLOOR,
                            MIN_REQ, LADDER, DLL, DAILY_STOP, QUAL_DAY, QUAL_N, CONSISTENCY,
                            PAYOUT_EVERY_D)

SPEC = FR.APEX_ACCOUNTS["50K"]           # start 50k, trailing 2500, target 3000
EVAL_BUDGET, EVAL_MAXCT = 1_200.0, 10
EVAL_FEE = 50.0                          # ~$45-50/eval (Apex coupon); others similar order
MFFU_PER_MONTH = 790.0                   # uncapped continuing (~$12.65k/16mo Apex-equiv; vault ~$700/mo)
OTHER_FIRMS = ["MFFU", "Topstep", "Tradeify"]

# ---------------------------------------------------------------- load frozen stream
print("loading frozen A/Exit#3/D1c stream (1m-truth)…", flush=True)
d1_tz = RD.load_1m(); d1 = d1_tz.copy()
if d1.index.tz is not None: d1.index = d1_tz.index.tz_localize(None)
df5 = DB.load_databento_5m(); mp = M1Map(d1, df5)
eng = E.ProfileAEngine(config.STRAT); eng.buf = df5
rows = a_streams_d1c(eng._features(), mp, d1_tz)["exit3"][0]

# eval events at $1,200 size-to-risk / max 10 ct (Apex 50K)
ev = []
for t in rows:
    q = min(EVAL_MAXCT, int(EVAL_BUDGET // t["risk_usd"]))
    if q < 1: continue
    ev.append(dict(ts=pd.Timestamp(t["ts"]), pnl=t["R"] * t["risk_usd"] * q,
                   mae=min(0.0, t["mae_r"]) * t["risk_usd"] * q))
ev.sort(key=lambda e: e["ts"])
EXPIRE_DAYS = 30
D0, DN = ev[0]["ts"], ev[-1]["ts"]
print(f"  {len(ev)} eval trade-events, {D0.date()} -> {DN.date()}")

# funded day-series (A4, certified ~$12.65k), shared real path
fdays = daily_series(rows, 4)            # [(date, real$, trough$)]
fdates = [d for d, _, _ in fdays]


def eval_eod(ev, start, spec):           # certified Apex EOD eval ($550 stop inside)
    sb, tr, tg = spec["start"], spec["trailing"], spec["target"]
    lock = sb + 100.0
    thr = sb - tr; bal = sb; peak_eod = sb; locked = False
    t0 = pd.Timestamp(ev[start]["ts"]); cur = None; dreal = 0.0
    for i in range(start, len(ev)):
        e = ev[i]; ts = pd.Timestamp(e["ts"]); day = ts.normalize()
        if (ts - t0).days > EXPIRE_DAYS:
            return "EXPIRE", EXPIRE_DAYS, ts
        if cur is None: cur = day
        if day != cur:
            peak_eod = max(peak_eod, bal)
            if not locked:
                thr = max(thr, peak_eod - tr)
                if peak_eod - tr >= lock: thr = lock; locked = True
            cur = day; dreal = 0.0
        if dreal <= DAILY_STOP: continue
        if bal + min(0.0, e["mae"]) <= thr:
            return "BUST", (ts - t0).days, ts
        bal += e["pnl"]; dreal += e["pnl"]
        if bal >= sb + tg:
            return "PASS", (ts - t0).days, ts
    return "INCOMPLETE", None, ts


def run_pa_dated(start_i):
    """Apex 6-payout ladder from fdays[start_i:]. Returns (outcome, close_date, [(date,amt)...])."""
    bal, peak_eod, locked = F_START, F_START, False
    thr = F_START - TRAIL; ladder_i = 0
    since = dict(profit=0.0, maxday=0.0, qual=0)
    t0 = fdays[start_i][0]; last_sweep = t0; payouts = []
    for i in range(start_i, len(fdays)):
        d, real, trough = fdays[i]
        if bal + min(0.0, trough) <= thr:
            return "BUST", d, payouts
        bal += real; since["profit"] += real
        since["maxday"] = max(since["maxday"], real)
        if real >= QUAL_DAY: since["qual"] += 1
        peak_eod = max(peak_eod, bal)
        if not locked:
            thr = max(thr, peak_eod - TRAIL)
            if peak_eod >= LOCK_EOD: thr = F_START + 100.0; locked = True
        if bal <= thr:
            return "BUST", d, payouts
        if (d - last_sweep).days >= PAYOUT_EVERY_D:
            last_sweep = d
            if (bal >= MIN_REQ and since["qual"] >= QUAL_N and since["profit"] > 0
                    and since["maxday"] < CONSISTENCY * since["profit"]):
                amt = min(LADDER[ladder_i], bal - PAYOUT_FLOOR)
                if amt > 0:
                    bal -= amt; payouts.append((d, amt)); ladder_i += 1
                    since = dict(profit=0.0, maxday=0.0, qual=0)
                    if ladder_i >= len(LADDER):
                        return "CLOSED_MAX", d, payouts
    return "OPEN_ATEND", fdays[-1][0], payouts


def run_mffu_dated(start_i):
    """Uncapped: pay MFFU_PER_MONTH each ~PAYOUT_EVERY_D from pass to data end; stays open."""
    payouts = []; t0 = fdays[start_i][0]; last = t0
    for i in range(start_i, len(fdays)):
        d = fdays[i][0]
        if (d - last).days >= PAYOUT_EVERY_D:
            last = d; payouts.append((d, MFFU_PER_MONTH))
    return "OPEN_UNCAPPED", fdays[-1][0], payouts


def fidx_after(date):
    for i, d in enumerate(fdates):
        if d >= pd.Timestamp(date).normalize(): return i
    return None

def evidx_after(date):
    for i, e in enumerate(ev):
        if e["ts"] >= pd.Timestamp(date): return i
    return None

# ---------------------------------------------------------------- weekly serial eval pipeline
first_mon = (D0 - pd.Timedelta(days=D0.weekday())).normalize()   # Monday of first week
cur = first_mon
attempts = []           # (firm, start, outcome, days)
funded = []             # dict(firm, open, close, outcome, payouts[list], total)
n_eval_by_firm = {f: 0 for f in ["Apex"] + OTHER_FIRMS}
rr = 0                  # round-robin pointer for other firms

def live_apex(atdate):
    return sum(1 for a in funded if a["firm"] == "Apex" and a["open"] <= atdate
               and (a["close"] is None or a["close"] > atdate) and a["outcome"] != "BUST")

# WEEKLY DRIP: start exactly 1 new eval every Monday; evals overlap (each runs its 30d course).
week = first_mon
while week <= DN:
    si = evidx_after(week)
    if si is None: break
    start_ts = ev[si]["ts"]
    # route: Apex until 20 live, else round-robin others
    if live_apex(start_ts) < 20:
        firm = "Apex"
    else:
        firm = OTHER_FIRMS[rr % len(OTHER_FIRMS)]; rr += 1
    outcome, days, end_ts = eval_eod(ev, si, SPEC)
    n_eval_by_firm[firm] += 1
    attempts.append((firm, start_ts, outcome, days))
    if outcome == "PASS":
        fi = fidx_after(end_ts)
        if fi is not None:
            if firm == "MFFU":
                oc, cl, po = run_mffu_dated(fi)
            else:
                oc, cl, po = run_pa_dated(fi)
            funded.append(dict(firm=firm, open=pd.Timestamp(end_ts), close=pd.Timestamp(cl),
                               outcome=oc, payouts=po, total=sum(a for _, a in po)))
    week = week + pd.Timedelta(days=7)

# ---------------------------------------------------------------- aggregate
def year_of(ts): return pd.Timestamp(ts).year
years = sorted({year_of(D0) + k for k in range(year_of(DN) - year_of(D0) + 1)})

total_payout = sum(a["total"] for a in funded)
total_fees = sum(n_eval_by_firm.values()) * EVAL_FEE
net = total_payout - total_fees

by_firm = {}
for fm in ["Apex"] + OTHER_FIRMS:
    accts = [a for a in funded if a["firm"] == fm]
    ev_n = n_eval_by_firm[fm]
    passes = sum(1 for a in attempts if a[0] == fm and a[2] == "PASS")
    busts = sum(1 for a in attempts if a[0] == fm and a[2] == "BUST")
    exps = sum(1 for a in attempts if a[0] == fm and a[2] == "EXPIRE")
    closed = sum(1 for a in accts if a["outcome"] == "CLOSED_MAX")
    fbust = sum(1 for a in accts if a["outcome"] == "BUST")
    still = sum(1 for a in accts if a["outcome"] in ("OPEN_ATEND", "OPEN_UNCAPPED"))
    pay = sum(a["total"] for a in accts)
    by_firm[fm] = dict(evals=ev_n, eval_pass=passes, eval_bust=busts, eval_expire=exps,
                       funded_opened=len(accts), funded_closed6=closed, funded_bust=fbust,
                       funded_open_atend=still, payout=round(pay), fees=round(ev_n * EVAL_FEE),
                       net=round(pay - ev_n * EVAL_FEE))

# year-by-year realized payouts (all firms)
yr_pay = {y: 0.0 for y in years}
for a in funded:
    for d, amt in a["payouts"]:
        yr_pay[pd.Timestamp(d).year] += amt

# eval funnel overall
oc_ct = {k: sum(1 for a in attempts if a[2] == k) for k in ["PASS", "BUST", "EXPIRE", "INCOMPLETE"]}

print("\n================ EVAL PIPELINE (serial, ~1/week, real Apex-difficulty engine) ================")
print(f"  total eval attempts = {len(attempts)}   "
      f"PASS {oc_ct['PASS']} ({100*oc_ct['PASS']/len(attempts):.1f}%)  "
      f"BUST {oc_ct['BUST']} ({100*oc_ct['BUST']/len(attempts):.1f}%)  "
      f"EXPIRE {oc_ct['EXPIRE']} ({100*oc_ct['EXPIRE']/len(attempts):.1f}%)")
print(f"  total funded accounts opened = {len(funded)}")

print("\n================ PER FIRM ================")
hdr = f"{'firm':>9}{'evals':>7}{'passed':>8}{'busted':>8}{'expired':>8}{'funded':>8}{'6-pay done':>11}{'fund bust':>10}{'open@end':>9}{'payout$':>11}{'net$':>11}"
print(hdr)
for fm in ["Apex"] + OTHER_FIRMS:
    b = by_firm[fm]
    print(f"{fm:>9}{b['evals']:>7}{b['eval_pass']:>8}{b['eval_bust']:>8}{b['eval_expire']:>8}"
          f"{b['funded_opened']:>8}{b['funded_closed6']:>11}{b['funded_bust']:>10}"
          f"{b['funded_open_atend']:>9}{b['payout']:>11,}{b['net']:>11,}")

print("\n================ YEAR BY YEAR (realized payouts, all firms) ================")
run = 0
print(f"{'year':>6}{'payouts$':>13}{'cumulative$':>14}")
for y in years:
    run += yr_pay[y]
    print(f"{y:>6}{yr_pay[y]:>+13,.0f}{run:>14,.0f}")

print("\n================ TOTALS ================")
print(f"  gross payouts (all firms, all accounts) = {total_payout:,.0f}")
print(f"  eval fees paid ({sum(n_eval_by_firm.values())} evals x ${EVAL_FEE:.0f}) = {total_fees:,.0f}")
print(f"  NET PROFIT (5 years) = {net:,.0f}")

json.dump(dict(attempts=len(attempts), funnel=oc_ct, by_firm=by_firm, year=yr_pay,
               total_payout=total_payout, fees=total_fees, net=net,
               funded_detail=[dict(firm=a["firm"], open=str(a["open"].date()),
                                   close=str(a["close"].date()), outcome=a["outcome"],
                                   n_payouts=len(a["payouts"]), total=round(a["total"]))
                              for a in funded]),
          open("reports/_fleet_5yr.json", "w"), indent=1, default=str)
print("\nwrote reports/_fleet_5yr.json")
