"""3-month WEEKLY-EVAL pipeline snapshot on the CURRENT model (1RR), real Databento.
Buy one Apex 50K eval each week for the last ~13 weeks; run each through eval (A10/B5/mm6, EOD, momentum
ON) -> if PASS, funded (PRE A4/B2 -> POST A6/B3, momentum OFF, monthly payouts). Report where EACH cohort
is NOW (as of the data end 2026-06-22) + totals: funded accounts, payouts banked, blown accounts."""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
import exit_model_validate as V
import apex_eval_deployed as H
import apex_eval_eod as EOD
import apex_funded_eod_databento as F
import strategy_engine_profileA as E
import config, funded_rules
T = pd.Timestamp; NY = "America/New_York"
SPEC = funded_rules.APEX_ACCOUNTS["50K"]
EVAL = {"A": 10, "B": 5, "M": 6}


def ab_stream():
    A = V.a_variant(feats, fi, "single1")
    ev = [dict(ts=T(t["ts"]), src="A", pnl=t["R"] * t["risk_usd"], mae=min(0.0, t["mae_r"]) * t["risk_usd"]) for t in A]
    for t in Bsim:
        R = t["R"]["single1"]; gp = R * (t["risk_usd"] / V.DPP)
        ev.append(dict(ts=T(t["ts"]), src="B", pnl=(gp - V.B_COST) * V.DPP, mae=min(0.0, t["mae_pts"]["single1"]) * V.DPP))
    return ev


def scale(ev, sz):
    return H.apply_daily_stop([dict(ts=e["ts"], src=e["src"], pnl=e["pnl"] * sz[e["src"]], mae=e["mae"] * sz[e["src"]]) for e in ev])


def first_idx(stream, ts):
    for i, e in enumerate(stream):
        if e["ts"] >= ts:
            return i
    return None


print("loading real Databento…", flush=True)
df5 = F.DB.load_databento_5m()
H.A_SIZE = H.B_SIZE = H.M_SIZE = 1
eng = E.ProfileAEngine(config.STRAT); eng.buf = df5; feats = eng._features(); fi = feats.index
Bsim = V.b_sim(df5)
ab = ab_stream()
Mev = [dict(ts=T(e["ts"]), src="M", pnl=e["pnl"], mae=e["mae"]) for e in H.m_events(df5)]
eval_stream = sorted(ab + Mev, key=lambda x: x["ts"])           # momentum ON for eval
funded_stream = sorted(ab, key=lambda x: x["ts"])              # momentum OFF for funded
data_end = eval_stream[-1]["ts"]

starts = pd.date_range(end=data_end.tz_convert(NY).normalize(), periods=13, freq="7D")
print(f"  data ends {data_end.tz_convert(NY).date()} (='now') · current model = SINGLE_1R (1RR) · 13 weekly evals\n")
print(f"  {'cohort (Mon)':>13} {'elapsed':>7} | {'eval':>16} | {'CURRENT STATE':>28} {'payout':>9}")
print("  " + "-" * 90)

funded = active = fbust = ebust = eexp = eprog = 0
total_pay = 0.0
for c in starts:
    cts = c if c.tz is not None else c.tz_localize(NY)
    elapsed = (data_end - cts).days
    si = first_idx(eval_stream, cts)
    outcome, days = EOD.eval_eod(scale(eval_stream[si:], EVAL), 0, SPEC)
    ev_desc = {"PASS": f"PASS d{days}", "BUST": f"BUST d{days}", "EXPIRE": "expired 30d",
               "INCOMPLETE": "running"}[outcome]
    pay = 0.0
    if outcome == "PASS":
        funded += 1
        fts = cts + pd.Timedelta(days=int(days))
        fj = first_idx(funded_stream, fts)
        if fj is None:
            state = "FUNDED just activated"; active += 1
        else:
            o = F.lifecycle(funded_stream, fj); pay = o["payout"]; total_pay += pay
            if o["bust"] == "prelock":
                state = "✗ FUNDED BLOWN (pre-lock)"; fbust += 1
            elif o["bust"] == "postlock":
                state = "✗ FUNDED BLOWN (post-lock)"; fbust += 1
            elif o["locked"]:
                state = "● FUNDED LOCKED (active)"; active += 1
            else:
                state = "● FUNDED grinding→lock (active)"; active += 1
    elif outcome == "BUST":
        state = "✗ EVAL BLOWN"; ebust += 1
    elif outcome == "EXPIRE":
        state = "✗ EVAL EXPIRED (no pass 30d)"; eexp += 1
    else:
        state = "◌ EVAL in progress"; eprog += 1
    print(f"  {str(cts.date()):>13} {elapsed:>5}d | {ev_desc:>16} | {state:>28} {('$'+format(pay,',.0f')) if pay else '—':>9}")

print("  " + "-" * 90)
print(f"\n  ===== SNAPSHOT as of {data_end.tz_convert(NY).date()} (13 weekly evals bought) =====")
print(f"  reached FUNDED       : {funded}   (currently active {active}, blown {fbust})")
print(f"  still in EVAL        : {eprog} running · {ebust} blown · {eexp} expired")
print(f"  TOTAL PAYOUTS banked : ${total_pay:,.0f}")
print(f"  blown accounts       : {ebust + fbust}  ({ebust} eval + {fbust} funded)")
print(f"\n  [current model SINGLE_1R · eval A10/B5/mm6 momentum ON · funded A4/B2->A6/B3 momentum OFF · EOD rule]")
