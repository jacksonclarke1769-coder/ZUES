"""SPRAY-ECONOMICS REFRESH — end-to-end business run-rate under the OPTIMIZED funded stage (honest sim, 2026-07-13).

RE-COMPUTES report-04's spray run-rate with the report-05 OPTIMIZED funded playbook (cushion-aware
cap<=3 small sizing, withdraw-to-floor), using the SAME methodology so the comparison is apples-to-apples,
AND adds the Apex account-CAP renewal model that report-04 omitted (which the accumulation of long-lived,
bust~0% optimized accounts makes binding).

RESEARCH / SIM measurement ONLY. READ-ONLY on bot strategy code (imports only). Writes confined to
research/passrate_opt/ + reports/passrate_opt/. NOTHING ARMED. LIVE HOLD remains in force.

FOUNDATION — reuses certified machinery BY IMPORT, re-models NOTHING:
  * research/passrate_opt/funded_stage_opt.py (G) -> build_vpc, build_level_matrix, monthly_starts,
    run_pa_diag, fixed_size, cushion_size  (the certified report-05 funded-PA engine; payout RULES
    unchanged). The OPTIMIZED policy = cush_3band_XS_S_M exactly as report-05 recommends.
  * report-04 run-rate FORMULA reproduced verbatim (monthly_runrate) for the apples-to-apples leg.

ABSOLUTE HONESTY: every Apex rule is help-center-derived, UNVERIFIED vs a live contract. Eval front-end
is FROZEN (VPC 50K AGGRESSIVE $2000/cap10): pass 37.9% rolling / 41.9% Monday-cohort (report-04 recomputed).
Apex concurrent-account CAP ~20 is UNVERIFIED help-center-derived. SIM only; funded fills at size unproven.
"""
import os, sys, json, hashlib, warnings, math
warnings.filterwarnings("ignore")
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import funded_stage_opt as G   # report-05 certified funded engine (imports F+H internally)

# ---- FROZEN EVAL FRONT-END (report-04 recomputed; VPC 50K AGGRESSIVE $2000/cap10) ----------------
PASS_ROLLING = 0.379        # full-window rolling Apex-clock starts
PASS_MONDAY  = 0.419        # recent-regime Monday cohorts (past 24mo, N=93)
EVAL_FEE_PROMO = 24.50      # operator-anchored recurring promo (UNVERIFIED)
EVAL_FEE_LIST  = 137.0      # ~50K list price (UNVERIFIED)
ACTIVATION     = 130.0      # one-time PA activation (UNVERIFIED)
EVALS_PER_MONTH = 52.0 / 12.0   # one eval/week ~ 4.33/mo

# ---- APEX ACCOUNT CAP (concurrent funded PAs) — UNVERIFIED help-center-derived ------------------
ACCOUNT_CAP_PRIMARY = 20
ACCOUNT_CAPS = [10, 20, 30]   # sensitivity band around the unverified ~20


def report04_runrate(pass_p, e_payout, fee, activation=ACTIVATION):
    """report-04 formula verbatim: evals/mo * (pass*(E[payout]-activation) - fee). UNCAPPED flow."""
    return round(EVALS_PER_MONTH * (pass_p * (e_payout - activation) - fee))


def per_pa_results(dates, mats, size_fn, starts, **kw):
    """Collect per-PA (paid, life_months, outcome) from the certified run_pa_diag."""
    res = [G.run_pa_diag(dates, mats, s, size_fn, **kw) for s in starts]
    paid = np.array([r["paid"] for r in res], float)
    life = np.array([r["months"] for r in res], float)
    outc = [r["outcome"] for r in res]
    n = len(res)
    return dict(
        n=n, paid=paid, life=life,
        e_paid_mean=round(float(paid.mean())), e_paid_median=round(float(np.median(paid))),
        life_mean=round(float(life.mean()), 1), life_median=round(float(np.median(life)), 1),
        bust_pct=round(100 * outc.count("BUST") / n, 1),
        closed_max_pct=round(100 * outc.count("CLOSED_MAX") / n, 1),
        data_end_pct=round(100 * outc.count("DATA_END") / n, 1),
        zero_pct=round(100 * float((paid == 0).mean()), 1),
    )


def cap_steady_state(pol, cap, pass_p, fee, activation=ACTIVATION):
    """Renewal-reward steady state under a concurrent-account CAP.
    Fleet gross $/mo = cap * E[paid]/E[life]  (renewal-reward: long-run reward rate = E[R]/E[cycle]).
    Replacement throughput = cap/E[life] accounts closing & refilled per month.
    Cost/mo = throughput * ((1/pass)*fee + activation)."""
    Lp, Ep_mean, Ep_med = pol["life_mean"], pol["e_paid_mean"], pol["e_paid_median"]
    rate_slot_mean = Ep_mean / Lp                     # $/mo earned per held account (censoring-robust)
    rate_slot_med  = Ep_med / Lp                      # median-scenario band (rough; renewal rate is ratio-of-means)
    gross_mean = cap * rate_slot_mean
    gross_med  = cap * rate_slot_med
    throughput = cap / Lp                             # accounts/mo closing (bust or ladder-cap)
    cost_per_funded = (1.0 / pass_p) * fee + activation
    cost_mo = throughput * cost_per_funded
    # per-PA monthly rate distribution (only over accounts with life>0), for a cross-check
    with np.errstate(divide="ignore", invalid="ignore"):
        pr = pol["paid"] / np.where(pol["life"] > 0, pol["life"], np.nan)
    pr = pr[~np.isnan(pr)]
    return dict(
        cap=cap, rate_slot_mean=round(rate_slot_mean, 1), rate_slot_median=round(rate_slot_med, 1),
        gross_mo_mean=round(gross_mean), gross_mo_median=round(gross_med),
        throughput_per_mo=round(throughput, 3), cost_per_funded=round(cost_per_funded, 1),
        cost_mo=round(cost_mo), net_mo_mean=round(gross_mean - cost_mo),
        net_mo_median=round(gross_med - cost_mo),
        xcheck_mean_of_perpa_rate=round(float(np.mean(pr)), 1),
        xcheck_median_of_perpa_rate=round(float(np.median(pr)), 1),
    )


def ramp(cap, pass_p, life_mean):
    """Accumulation to the cap. Creation rate c = pass*evals/mo. Unconstrained equilibrium N*=c*L.
    N(t)=c*L*(1-exp(-t/L)) until it reaches cap; time-to-cap t*=-L*ln(1-cap/(c*L)) if c*L>cap."""
    c = pass_p * EVALS_PER_MONTH
    L = life_mean
    Nstar = c * L
    if Nstar <= cap:
        # never saturates: equilibrium below cap
        t_to_90 = -L * math.log(0.10)  # time to reach 90% of N*
        return dict(creation_per_mo=round(c, 3), equilibrium_N=round(Nstar, 1), saturates=False,
                    months_to_cap=None, months_to_90pct_equilib=round(t_to_90, 1),
                    note="creation*life < cap: fleet never fills the cap; equilibrium below cap")
    t_cap = -L * math.log(1.0 - cap / Nstar)
    return dict(creation_per_mo=round(c, 3), equilibrium_N=round(Nstar, 1), saturates=True,
                months_to_cap=round(t_cap, 1),
                note="creation*life > cap: fleet fills to cap then throttles to replacement only")


def main():
    print("building VPC stream + funded size-level matrix (reused report-05 G machinery)…", flush=True)
    vpc = G.build_vpc()
    dates, mats = G.build_level_matrix(vpc)
    starts = G.monthly_starts(dates)

    out = dict(meta=dict(generated="2026-07-13", n_starts=len(starts),
                         window=f"{dates[0].date()}->{dates[-1].date()}",
                         pass_rolling=PASS_ROLLING, pass_monday=PASS_MONDAY,
                         eval_fee_promo=EVAL_FEE_PROMO, eval_fee_list=EVAL_FEE_LIST,
                         activation=ACTIVATION, evals_per_month=round(EVALS_PER_MONTH, 3),
                         account_cap_primary=ACCOUNT_CAP_PRIMARY, account_caps=ACCOUNT_CAPS,
                         confidence="ALL Apex rules help-center-derived, UNVERIFIED vs live contract; "
                                    "eval front-end FROZEN; SIM only; account cap UNVERIFIED"))

    # ---- POLICIES: pre-optimization baseline vs optimized (report-05 recommended) ----
    pre = per_pa_results(dates, mats, G.fixed_size("S"), starts)               # $400/cap2 baseline
    opt = per_pa_results(dates, mats,
                         G.cushion_size([(0, "XS"), (2500, "S"), (5000, "M")]), starts)  # cush_3band
    # CANARY: must reproduce report-05 exactly
    print(f"[CANARY pre  ] mean ${pre['e_paid_mean']} med ${pre['e_paid_median']} bust {pre['bust_pct']}% "
          f"life {pre['life_mean']}mo (target 2893/1500/53.3/16.4)", flush=True)
    print(f"[CANARY opt  ] mean ${opt['e_paid_mean']} med ${opt['e_paid_median']} bust {opt['bust_pct']}% "
          f"closed_max {opt['closed_max_pct']}% data_end {opt['data_end_pct']}% life {opt['life_mean']}mo "
          f"(target 2842/2362/0/0/31.5)", flush=True)
    out["canary"] = dict(pre={k: pre[k] for k in ("e_paid_mean","e_paid_median","bust_pct","life_mean")},
                         opt={k: opt[k] for k in ("e_paid_mean","e_paid_median","bust_pct","closed_max_pct",
                                                  "data_end_pct","life_mean")})
    for lab, pol in (("pre", pre), ("opt", opt)):
        out[f"policy_{lab}"] = {k: pol[k] for k in
            ("n","e_paid_mean","e_paid_median","life_mean","life_median","bust_pct","closed_max_pct",
             "data_end_pct","zero_pct")}

    # ---- LEG A: report-04 SAME-METHODOLOGY uncapped flow run-rate (apples-to-apples) ----
    legA = {}
    for lab, pol in (("pre", pre), ("opt", opt)):
        legA[lab] = {}
        for pname, pp in (("rolling", PASS_ROLLING), ("monday", PASS_MONDAY)):
            legA[lab][pname] = dict(
                runrate_mo_mean_promo=report04_runrate(pp, pol["e_paid_mean"], EVAL_FEE_PROMO),
                runrate_mo_median_promo=report04_runrate(pp, pol["e_paid_median"], EVAL_FEE_PROMO),
                runrate_mo_mean_list=report04_runrate(pp, pol["e_paid_mean"], EVAL_FEE_LIST),
                runrate_mo_median_list=report04_runrate(pp, pol["e_paid_median"], EVAL_FEE_LIST),
            )
    out["legA_report04_uncapped_flow"] = legA
    print("\n[LEG A uncapped-flow, promo, Monday pass]")
    print(f"  pre: mean ${legA['pre']['monday']['runrate_mo_mean_promo']}/mo  "
          f"median ${legA['pre']['monday']['runrate_mo_median_promo']}/mo")
    print(f"  opt: mean ${legA['opt']['monday']['runrate_mo_mean_promo']}/mo  "
          f"median ${legA['opt']['monday']['runrate_mo_median_promo']}/mo")

    # ---- LEG B: ACCOUNT-CAP renewal steady state (the honest reality report-04 omitted) ----
    legB = {"pre": {}, "opt": {}}
    ramps = {"pre": {}, "opt": {}}
    for lab, pol in (("pre", pre), ("opt", opt)):
        for cap in ACCOUNT_CAPS:
            legB[lab][f"cap{cap}"] = {}
            ramps[lab][f"cap{cap}"] = {}
            for pname, pp in (("rolling", PASS_ROLLING), ("monday", PASS_MONDAY)):
                legB[lab][f"cap{cap}"][pname] = cap_steady_state(pol, cap, pp, EVAL_FEE_PROMO)
                ramps[lab][f"cap{cap}"][pname] = ramp(cap, pp, pol["life_mean"])
    out["legB_cap_steady_state"] = legB
    out["ramp"] = ramps
    print("\n[LEG B cap=20 renewal steady state, promo, Monday pass]")
    for lab in ("pre", "opt"):
        s = legB[lab]["cap20"]["monday"]; r = ramps[lab]["cap20"]["monday"]
        print(f"  {lab}: gross mean ${s['gross_mo_mean']}/mo (median-band ${s['gross_mo_median']}) "
              f"net mean ${s['net_mo_mean']}/mo | fill-to-cap {r['months_to_cap']}mo "
              f"(equilib N*={r['equilibrium_N']}, saturates={r['saturates']})")

    # ---- determinism ----
    md5 = hashlib.md5(json.dumps(out, sort_keys=True, default=str).encode()).hexdigest()
    out["meta"]["determinism_md5"] = md5
    dest = os.path.join(REPO, "reports", "passrate_opt", "06_spray_economics_refresh_optimized.json")
    with open(dest, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(f"\n[saved] {dest}  md5={md5}", flush=True)
    return out


if __name__ == "__main__":
    main()
