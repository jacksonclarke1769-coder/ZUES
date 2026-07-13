"""50K AGGRESSIVE VPC — Apex-50K eval started EVERY MONDAY over the past 24 months.
Reuses the CERTIFIED engine by import (research/passrate_opt/vpc_firm_sizing.py -> honest_eval_engines
+ tools_account_size_research). No re-modeling. Config = the '50K aggressive' cell: budget $2000 / cap 10.
Honest censoring: a Monday start within 30 days of data-end cannot truly EXPIRE (not enough forward
data) -> relabelled CENSORED, never counted as a fail."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
import pandas as pd
import vpc_firm_sizing as S          # the certified sweep harness (eval_one, FIRMS, START, TARGET)
import honest_eval_engines as F      # VPC builders + Databento loader
import tools_account_size_research as H

BUDGET, CAP = 2000, 10               # the 50K AGGRESSIVE config
FIRM = dict(S.FIRMS["Apex50K"]); FIRM["_name"] = "Apex50K"
ARES_STOP = S.ARES_STOP

def build_days(budget, cap):
    df5 = F.databento_5m_rth()
    feats = F.v.features(df5); feats = feats[feats.date >= F.START_DATE]
    vpc = F.vpc_trades_rich(feats)
    S.DATA_END = df5.index.max()
    ev = F.vpc_events_risk(vpc, budget=budget, cap=cap)
    days = H.day_rows(ev, ARES_STOP, FIRM["dll"])
    return days, df5.index.max(), len(vpc)

def eval_censor(days, s0, firm, data_end):
    """eval_one + honest censoring for starts within `expire` days of data-end."""
    out, dd = S.eval_one(days, s0, firm)
    if out == "EXPIRE":
        elapsed_avail = (data_end - days[s0][0]).days
        if elapsed_avail < firm["expire_days"]:      # couldn't have truly expired -> undetermined
            return "CENSORED", elapsed_avail
    return out, dd

def main():
    can_days, data_end, ntr = build_days(600, 3)
    # fidelity canary at $600/cap3 (rolling every-start) must reproduce 12.6/3.6/83.8
    c = S.run_cell(F.vpc_trades_rich(F.v.features(F.databento_5m_rth()).pipe(lambda x: x[x.date>=F.START_DATE])), FIRM, 600, 3)
    print(f"[CANARY] Apex50K $600/cap3 rolling -> pass {c['pass_pct']} bust {c['bust_pct']} exp {c['exp_pct']} med {c['med_days']}d (target 12.6/3.6/83.8/19)")

    days, data_end, ntr = build_days(BUDGET, CAP)
    print(f"[data] VPC trades={ntr}  data_end={data_end.date()}  aggressive cfg=${BUDGET}/cap{CAP}")

    # --- enumerate Mondays over the PAST 24 MONTHS, snapping holidays forward to next trading day ---
    day_dates = [d[0] for d in days]
    start_win = data_end - pd.DateOffset(months=24)
    mondays = pd.date_range(start=start_win.normalize(), end=data_end.normalize(), freq="W-MON", tz=data_end.tz)
    cohorts = []
    used = set()
    for M in mondays:
        # first trading day on/after this Monday
        idx = next((i for i, d in enumerate(day_dates) if d >= M), None)
        if idx is None or idx in used:
            continue
        # only accept if the snapped trading day is within the same week (<=4 days after Monday)
        if (day_dates[idx].normalize() - M).days > 4:
            continue
        used.add(idx)
        out, dd = eval_censor(days, idx, FIRM, data_end)
        cohorts.append((M.date(), day_dates[idx].date(), out, dd))

    n = len(cohorts)
    npass = sum(1 for c in cohorts if c[2] == "PASS")
    nbust = sum(1 for c in cohorts if c[2] == "BUST")
    nexp  = sum(1 for c in cohorts if c[2] == "EXPIRE")
    ncen  = sum(1 for c in cohorts if c[2] == "CENSORED")
    resolved = npass + nbust + nexp
    pass_days = sorted(c[3] for c in cohorts if c[2] == "PASS")
    med_pass = pass_days[len(pass_days)//2] if pass_days else None

    print(f"\n=== 50K AGGRESSIVE VPC · Apex-50K · eval started every Monday · past 24 months ===")
    print(f"cohorts (Mondays)      : {n}")
    print(f"PASS                   : {npass}  ({100*npass/n:.1f}% of all, {100*npass/resolved:.1f}% of resolved)")
    print(f"BUST                   : {nbust}  ({100*nbust/n:.1f}% of all, {100*nbust/resolved:.1f}% of resolved)")
    print(f"EXPIRE (30d, no pass)  : {nexp}  ({100*nexp/n:.1f}%)")
    print(f"CENSORED (data cutoff) : {ncen}  ({100*ncen/n:.1f}%)  <- recent Mondays, undetermined")
    print(f"median days to PASS    : {med_pass}")
    print(f"\n{'Monday':>12} {'startDay':>12} {'outcome':>9} {'days':>5}")
    for M, sd, out, dd in cohorts:
        print(f"{str(M):>12} {str(sd):>12} {out:>9} {dd:>5}")

if __name__ == "__main__":
    main()
