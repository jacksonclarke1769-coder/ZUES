"""VPC SPRAY-ECONOMICS — Apex 25K vs 50K, cost side AND payout side (honest sim, 2026-07-13).

RESEARCH / SIM measurement ONLY. READ-ONLY on bot strategy code (imports only). Writes confined to
research/passrate_opt/ + reports/passrate_opt/. NOTHING ARMED. LIVE HOLD remains in force.

FOUNDATION — reuses the certified machinery BY IMPORT, re-models NOTHING of the strategy or fills:
  * research/fork_b/honest_eval_engines.py (F) -> databento_5m_rth, v.features, vpc_trades_rich,
    vpc_events_risk  (the honest VPC signal/fill + risk-sizing event stream)
  * tools_account_size_research (H)            -> day_rows (ARES $550 stop + tier DLL flatten)
  * research/passrate_opt/vpc_firm_sizing (S)  -> eval_one/run_cell (certified eval rule) for pass%
The ONLY new code here is `run_pa` — a PARAMETRIZED, faithful reproduction of the funded-PA payout
mechanics in apex_funded_40.py:74-113 (run_pa). The payout RULES are unchanged; only the tier
constants and the fed trade stream differ.

ABSOLUTE HONESTY: every Apex rule below is help-center-derived, NOT read off a live contract
(evidence/apex_terms/apex_terms.yaml: confidence UNVERIFIED, source PENDING). Multi-source web
help-center pages (2026) corroborate the 50K ladder [1.5/1.5/2/2.5/2.5/3]k=$13k and $250 qual-day,
and give the 25K ladder as a FLAT $1,000 x6 = $6,000 with a $100 qual-day and $500 min withdrawal.
These are used as PRIMARY inputs (better-sourced than a pure scale-guess) but remain UNVERIFIED vs a
live contract. The task's naive x0.5 scale-guess ladder is carried as a payout SENSITIVITY.
"""
import os, sys, json, hashlib, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "research", "fork_b"))
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
import honest_eval_engines as F
import tools_account_size_research as H
import vpc_firm_sizing as S

NY = "America/New_York"
ARES_STOP = 550.0                       # per task: day_rows(ev, 550.0, DLL_tier) for BOTH tiers
RUNWAY_DAYS = 274                       # >= 9 months of forward runway for a funded-PA start
QUAL_N, CONSISTENCY, PAYOUT_EVERY_D = 5, 0.50, 30

# ---- TIER PAYOUT CONSTANTS (help-center-derived; UNVERIFIED vs live contract) -------------------
TIERS = {
    "50K": dict(start=50_000.0, trail=2_500.0, floor=52_100.0, min_req=52_600.0, dll=1_000.0,
                ladder=[1_500., 1_500., 2_000., 2_500., 2_500., 3_000.], qual_day=250.0,
                # web-corroborated (multi-source 2026 help-center) -> repo pins match exactly
                ladder_conf="help-center-corroborated (multi-source)"),
    "25K": dict(start=25_000.0, trail=1_500.0, floor=26_100.0, min_req=26_600.0, dll=500.0,
                ladder=[1_000., 1_000., 1_000., 1_000., 1_000., 1_000.], qual_day=100.0,
                # web help-center: flat $1,000 x6 = $6,000, $100 qual-day, $500 min withdrawal
                ladder_conf="help-center-derived (single-strength); PRIMARY over pure scale-guess"),
}
# 25K ladder SENSITIVITY variants (the single weakest input) ----------------------------------
LADDER_25K_VARIANTS = {
    "web_flat_6000":   ([1_000., 1_000., 1_000., 1_000., 1_000., 1_000.], 100.0),   # PRIMARY
    "task_scaled_6500":([750., 750., 1_000., 1_250., 1_250., 1_500.], 250.0),        # naive x0.5, qual 250
    "task_scaled_q100":([750., 750., 1_000., 1_250., 1_250., 1_500.], 100.0),        # scaled ladder, real qual
    "flat_6000_q250":  ([1_000., 1_000., 1_000., 1_000., 1_000., 1_000.], 250.0),    # flat ladder, naive qual
}

# ---- COST-SIDE INPUTS (flag every one) ----------------------------------------------------------
EVAL_FEE_PROMO = 24.50                  # operator-anchored recurring promo price (UNVERIFIED)
EVAL_FEE_LIST = {"25K": 107.0, "50K": 137.0}   # ~list price scenario (UNVERIFIED, approximate)
ACTIVATION = 130.0                      # one-time PA activation, per funded PA (UNVERIFIED ~$130)
EVALS_PER_MONTH = 52.0 / 12.0           # one Monday eval/week ~ 4.33/mo


# =================================================================================================
def build_days(budget, cap, dll):
    """VPC day-collapsed (date, realized$, trough$) at a funded size, tier DLL applied. Reuses F+H."""
    feats = F.v.features(F.databento_5m_rth()); feats = feats[feats.date >= F.START_DATE]
    vpc = F.vpc_trades_rich(feats)
    ev = F.vpc_events_risk(vpc, budget=budget, cap=cap)
    return H.day_rows(ev, ARES_STOP, dll), vpc


def run_pa(days, start_i, T, ladder=None, qual_day=None):
    """One funded-PA life from days[start_i:]. FAITHFUL parametrization of apex_funded_40.run_pa
    (:74-113). Returns (outcome, months, paid_total, n_payouts). DLL already applied in `days`."""
    START, TRAIL = T["start"], T["trail"]
    FLOOR, MIN_REQ = T["floor"], T["min_req"]
    LADDER = ladder if ladder is not None else T["ladder"]
    QUAL_DAY = qual_day if qual_day is not None else T["qual_day"]
    LOCK_EOD = MIN_REQ                                   # = start + trail + 100 (peak-lock trigger)
    bal, peak_eod, locked = START, START, False
    thr = START - TRAIL
    paid, ladder_i = 0.0, 0
    since = dict(profit=0.0, maxday=0.0, qual=0)
    t0 = days[start_i][0]; last_sweep = t0
    for i in range(start_i, len(days)):
        d, real, trough = days[i]
        if bal + min(0.0, trough) <= thr:               # intraday marked-trough liquidation
            return "BUST", (d - t0).days / 30.4, paid, ladder_i
        bal += real
        since["profit"] += real
        since["maxday"] = max(since["maxday"], real)
        if real >= QUAL_DAY:
            since["qual"] += 1
        peak_eod = max(peak_eod, bal)                   # EOD ratchet
        if not locked:
            thr = max(thr, peak_eod - TRAIL)
            if peak_eod >= LOCK_EOD:
                thr = START + 100.0; locked = True
        if bal <= thr:
            return "BUST", (d - t0).days / 30.4, paid, ladder_i
        if (d - last_sweep).days >= PAYOUT_EVERY_D:      # ~monthly payout sweep
            last_sweep = d
            eligible = (bal >= MIN_REQ and since["qual"] >= QUAL_N
                        and (since["profit"] > 0 and since["maxday"] < CONSISTENCY * since["profit"]))
            if eligible:
                amt = min(LADDER[ladder_i], bal - FLOOR)
                if amt > 0:
                    bal -= amt; paid += amt; ladder_i += 1
                    since = dict(profit=0.0, maxday=0.0, qual=0)
                    if ladder_i >= len(LADDER):
                        return "CLOSED_MAX", (d - t0).days / 30.4, paid, ladder_i
    return "DATA_END", (days[-1][0] - t0).days / 30.4, paid, ladder_i


def monthly_starts(days):
    """Rolling first-of-month starts with >= RUNWAY_DAYS (~9mo) of forward data."""
    last = days[-1][0]
    return [i for i, (d, _, _) in enumerate(days)
            if (last - d).days >= RUNWAY_DAYS and (i == 0 or days[i - 1][0].month != d.month)]


def payout_stats(days, T, ladder=None, qual_day=None):
    starts = monthly_starts(days)
    res = [run_pa(days, s, T, ladder, qual_day) for s in starts]
    n = len(res)
    paids = np.array([r[2] for r in res]); months = np.array([r[1] for r in res])
    npay = np.array([r[3] for r in res])
    stat = dict(
        n_starts=n,
        bust_pct=round(100 * sum(1 for r in res if r[0] == "BUST") / n, 1),
        closed_max_pct=round(100 * sum(1 for r in res if r[0] == "CLOSED_MAX") / n, 1),
        data_end_pct=round(100 * sum(1 for r in res if r[0] == "DATA_END") / n, 1),
        zero_payout_pct=round(100 * float((paids == 0).mean()), 1),
        e_paid_mean=round(float(paids.mean())),
        e_paid_median=round(float(np.median(paids))),
        e_paid_p25=round(float(np.percentile(paids, 25))),
        e_paid_p75=round(float(np.percentile(paids, 75))),
        e_n_payouts=round(float(npay.mean()), 2),
        mean_life_months=round(float(months.mean()), 1),
        median_life_months=round(float(np.median(months)), 1),
    )
    # per-year (by START year)
    yr = {}
    for s, r in zip(starts, res):
        y = int(days[s][0].year)
        yr.setdefault(y, []).append(r)
    stat["per_year"] = {y: dict(n=len(v),
                                e_paid_mean=round(float(np.mean([x[2] for x in v]))),
                                bust_pct=round(100 * sum(1 for x in v if x[0] == "BUST") / len(v), 1),
                                closed_max_pct=round(100 * sum(1 for x in v if x[0] == "CLOSED_MAX") / len(v), 1))
                        for y, v in sorted(yr.items())}
    return stat


# ---- COST SIDE: recompute pass rates (full-window + recent-regime Monday cohorts) ---------------
def firm_for(tier):
    if tier == "50K":
        S.START, S.TARGET = 50_000.0, 3_000.0
        return dict(dd_type="trail", dd=2_500.0, dll=1_000.0, expire_days=30, consistency=None,
                    min_days=1, _name="Apex50K")
    S.START, S.TARGET = 25_000.0, 1_500.0
    return dict(dd_type="trail", dd=1_500.0, dll=500.0, expire_days=30, consistency=None,
                min_days=1, _name="Apex25K")


def full_window_pass(tier, budget, cap):
    firm = firm_for(tier)
    feats = F.v.features(F.databento_5m_rth()); feats = feats[feats.date >= F.START_DATE]
    vpc = F.vpc_trades_rich(feats)
    c = S.run_cell(vpc, firm, budget, cap)
    return c


def recent_regime_pass(tier, budget, cap, months_back=24):
    """Apex eval started every Monday over the past `months_back` months; honest censoring for
    starts within 30d of data-end. Mirrors vpc_monday_cohorts.py methodology."""
    firm = firm_for(tier)
    feats = F.v.features(F.databento_5m_rth()); feats = feats[feats.date >= F.START_DATE]
    vpc = F.vpc_trades_rich(feats)
    ev = F.vpc_events_risk(vpc, budget=budget, cap=cap)
    ev = sorted([dict(ts=e["ts"], pnl=e["pnl"], mae=e["mae"]) for e in ev], key=lambda e: e["ts"])
    days = H.day_rows(ev, ARES_STOP, firm["dll"])
    data_end = F.databento_5m_rth().index.max()
    day_dates = [d[0] for d in days]
    start_win = data_end - pd.DateOffset(months=months_back)
    mondays = pd.date_range(start=start_win.normalize(), end=data_end.normalize(), freq="W-MON",
                            tz=data_end.tz)
    npass = nbust = nexp = ncen = 0; used = set()
    for M in mondays:
        idx = next((i for i, d in enumerate(day_dates) if d >= M), None)
        if idx is None or idx in used:
            continue
        if (day_dates[idx].normalize() - M).days > 4:
            continue
        used.add(idx)
        out, dd = S.eval_one(days, idx, firm)
        if out == "EXPIRE" and (data_end - day_dates[idx]).days < firm["expire_days"]:
            out = "CENSORED"
        if out == "PASS": npass += 1
        elif out == "BUST": nbust += 1
        elif out == "EXPIRE": nexp += 1
        else: ncen += 1
    n = npass + nbust + nexp + ncen
    resolved = npass + nbust + nexp
    return dict(n_cohorts=n, resolved=resolved, censored=ncen,
                pass_pct_all=round(100 * npass / n, 1) if n else None,
                pass_pct_resolved=round(100 * npass / resolved, 1) if resolved else None,
                bust_pct_all=round(100 * nbust / n, 1) if n else None,
                expire_pct_all=round(100 * nexp / n, 1) if n else None)


# =================================================================================================
def cost_per_funded(pass_pct, fee, activation=ACTIVATION):
    if not pass_pct:
        return None
    p = pass_pct / 100.0
    return round((1.0 / p) * fee + activation, 1)


def breakeven_pass(e_payout, fee, activation=ACTIVATION):
    """p s.t. E[payout] = (1/p)*fee + activation  ->  p = fee / (E[payout] - activation)."""
    denom = e_payout - activation
    if denom <= 0:
        return None
    return round(100 * fee / denom, 1)


def monthly_runrate(pass_pct, e_payout, fee, activation=ACTIVATION):
    """Steady-state Monday-spray monthly $: evals/mo * (pass * (E[payout]-activation) - fee)."""
    if pass_pct is None:
        return None
    p = pass_pct / 100.0
    return round(EVALS_PER_MONTH * (p * (e_payout - activation) - fee))


def main():
    print("building VPC stream + sweeping funded sizes per tier (reused F/H/S machinery)…", flush=True)
    out = dict(meta=dict(generated="2026-07-13", ares_stop=ARES_STOP, runway_days=RUNWAY_DAYS,
                         eval_fee_promo=EVAL_FEE_PROMO, eval_fee_list=EVAL_FEE_LIST,
                         activation=ACTIVATION, evals_per_month=round(EVALS_PER_MONTH, 3),
                         confidence="ALL Apex rules help-center-derived, UNVERIFIED vs live contract"))

    # ---- CANARY: reuse S.run_cell for the established 50K $600/cap3 baseline (12.6/3.6/83.8) ----
    firm50 = firm_for("50K")
    feats = F.v.features(F.databento_5m_rth()); feats = feats[feats.date >= F.START_DATE]
    vpc = F.vpc_trades_rich(feats)
    can = S.run_cell(vpc, firm50, 600, 3)
    out["canary_50k_600_cap3"] = dict(pass_pct=can["pass_pct"], bust_pct=can["bust_pct"],
                                      exp_pct=can["exp_pct"], med=can["med_days"],
                                      target="12.6/3.6/83.8/19")
    print(f"[CANARY] 50K $600/cap3 -> {can['pass_pct']}/{can['bust_pct']}/{can['exp_pct']}/{can['med_days']}d "
          f"(target 12.6/3.6/83.8/19)", flush=True)

    # ---- FUNDED SIZE SWEEP (survival) ----
    FUND_BUDGETS, FUND_CAPS = [400, 550, 700, 900, 1200], [2, 3, 4]
    out["funded_sweep"] = {}
    picks = {}
    for tier in ("50K", "25K"):
        T = TIERS[tier]
        rows = []
        for b in FUND_BUDGETS:
            for c in FUND_CAPS:
                days, _ = build_days(b, c, T["dll"])
                st = payout_stats(days, T)
                st.update(budget=b, cap=c)
                rows.append(st)
        out["funded_sweep"][tier] = rows
        # PICK: conservative survival — lowest bust among cells with e_paid_mean within 15% of the
        # cell-max, tie-break higher e_paid_mean. (Report the rule; never silently cherry-pick.)
        emax = max(r["e_paid_mean"] for r in rows)
        cand = [r for r in rows if r["e_paid_mean"] >= 0.85 * emax]
        pick = sorted(cand, key=lambda r: (r["bust_pct"], -r["e_paid_mean"]))[0]
        picks[tier] = pick
        print(f"[{tier}] funded pick ${pick['budget']}/cap{pick['cap']}: bust {pick['bust_pct']}% "
              f"closed_max {pick['closed_max_pct']}% E[paid] mean ${pick['e_paid_mean']} "
              f"med ${pick['e_paid_median']} E[#pay] {pick['e_n_payouts']} life {pick['mean_life_months']}mo",
              flush=True)
    out["funded_pick"] = {t: dict(budget=p["budget"], cap=p["cap"]) for t, p in picks.items()}

    # ---- 25K LADDER SENSITIVITY (single weakest input) at the 25K funded pick ----
    T25 = TIERS["25K"]; p25 = picks["25K"]
    days25, _ = build_days(p25["budget"], p25["cap"], T25["dll"])
    out["ladder_25k_sensitivity"] = {}
    for name, (lad, qd) in LADDER_25K_VARIANTS.items():
        st = payout_stats(days25, T25, ladder=lad, qual_day=qd)
        out["ladder_25k_sensitivity"][name] = dict(ladder=lad, qual_day=qd,
                                                    e_paid_mean=st["e_paid_mean"],
                                                    e_paid_median=st["e_paid_median"],
                                                    bust_pct=st["bust_pct"],
                                                    closed_max_pct=st["closed_max_pct"],
                                                    zero_payout_pct=st["zero_payout_pct"],
                                                    e_n_payouts=st["e_n_payouts"])
        print(f"[25K ladder {name}] E[paid] mean ${st['e_paid_mean']} med ${st['e_paid_median']} "
              f"bust {st['bust_pct']}% closed_max {st['closed_max_pct']}%", flush=True)

    # ---- FULL PAYOUT STATS at the pick, PRIMARY ladders ----
    out["payout"] = {}
    for tier in ("50K", "25K"):
        T = TIERS[tier]; pk = picks[tier]
        days, _ = build_days(pk["budget"], pk["cap"], T["dll"])
        out["payout"][tier] = payout_stats(days, T)

    # ---- COST SIDE: recompute pass rates for the cited eval configs ----
    EVAL_CFGS = {
        "25K_balanced_1200_cap3": ("25K", 1200, 3),
        "50K_best_1500_cap4":     ("50K", 1500, 4),
        "50K_aggressive_2000_cap10": ("50K", 2000, 10),
    }
    out["eval_passrates"] = {}
    for name, (tier, b, c) in EVAL_CFGS.items():
        fw = full_window_pass(tier, b, c)
        rr = recent_regime_pass(tier, b, c)
        out["eval_passrates"][name] = dict(tier=tier, budget=b, cap=c,
                                           full_window=dict(pass_pct=fw["pass_pct"], bust_pct=fw["bust_pct"],
                                                            exp_pct=fw["exp_pct"], med_days=fw["med_days"],
                                                            n_starts=fw["n_starts"], trades_per_wk=fw["trades_per_wk"]),
                                           recent_regime=rr)
        print(f"[PASS {name}] full {fw['pass_pct']}% / recent {rr['pass_pct_all']}% "
              f"(resolved {rr['pass_pct_resolved']}%)", flush=True)

    # ---- SYNTHESIS: head-to-head economics ----
    # 25K uses balanced eval cfg; 50K reported for BOTH best (1500/cap4) and aggressive (2000/cap10).
    synth = {}
    def econ(tier, eval_key, fee_kind):
        pk_pay = out["payout"][tier]
        ep_mean, ep_med = pk_pay["e_paid_mean"], pk_pay["e_paid_median"]
        pr = out["eval_passrates"][eval_key]
        fw_pass = pr["full_window"]["pass_pct"]
        rr_pass = pr["recent_regime"]["pass_pct_all"]
        fee = EVAL_FEE_PROMO if fee_kind == "promo" else EVAL_FEE_LIST[tier]
        return dict(
            tier=tier, eval_cfg=eval_key, fee_kind=fee_kind, fee=fee,
            e_payout_mean=ep_mean, e_payout_median=ep_med,
            full_pass=fw_pass, recent_pass=rr_pass,
            cost_per_funded_full=cost_per_funded(fw_pass, fee),
            cost_per_funded_recent=cost_per_funded(rr_pass, fee),
            net_mean_full=round(ep_mean - (cost_per_funded(fw_pass, fee) or 0)),
            net_median_full=round(ep_med - (cost_per_funded(fw_pass, fee) or 0)),
            net_mean_recent=round(ep_mean - (cost_per_funded(rr_pass, fee) or 0)),
            breakeven_pass_mean=breakeven_pass(ep_mean, fee),
            breakeven_pass_median=breakeven_pass(ep_med, fee),
            runrate_mo_full_mean=monthly_runrate(fw_pass, ep_mean, fee),
            runrate_mo_recent_mean=monthly_runrate(rr_pass, ep_mean, fee),
            runrate_mo_recent_median=monthly_runrate(rr_pass, ep_med, fee),
        )
    for fee_kind in ("promo", "list"):
        synth[fee_kind] = dict(
            _25K_balanced=econ("25K", "25K_balanced_1200_cap3", fee_kind),
            _50K_best=econ("50K", "50K_best_1500_cap4", fee_kind),
            _50K_aggressive=econ("50K", "50K_aggressive_2000_cap10", fee_kind),
        )
    out["synthesis"] = synth

    md5 = hashlib.md5(json.dumps(out, sort_keys=True, default=str).encode()).hexdigest()
    out["meta"]["determinism_md5"] = md5
    dest = os.path.join(REPO, "reports", "passrate_opt", "04_spray_economics.json")
    with open(dest, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(f"\n[saved] {dest}  md5={md5}", flush=True)
    return out


if __name__ == "__main__":
    main()
