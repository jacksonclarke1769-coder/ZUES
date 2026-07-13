"""FUNDED-STAGE THROUGHPUT OPTIMIZER — Apex 50K, VPC edge FROZEN (honest sim, 2026-07-13).

OBJECTIVE (a THROUGHPUT problem, not a per-account problem): the Apex 4.0 ladder caps lifetime payout
per PA at ~$13k (6 rungs then the PA CLOSES) AND a ~20 concurrent-funded-account cap bounds the fleet.
So the business objective = MAXIMIZE SUSTAINABLE $/ACCOUNT-SLOT/MONTH at the ~20 cap, SUBJECT TO a
SURVIVAL constraint (positive median payout in EVERY calendar year, especially 2023 — the fair-weather
test). Reframe: collect the $13k ladder FAST and turn the slot over (short life, high turnover), NOT baby
one account for 31 months.

Two prior bracket points (reports 05/06):
  * cushion-brake cap<=3   -> ~$90/slot-mo, bust ~0%, survives every year  (per-account-optimal, TOO SLOW)
  * pre-opt $400/cap2 fast -> ~$176/slot-mo BUT the correlation-1 fleet WIPES in 2023 (uninvestable)
The target is the FASTEST funded sizing that still SURVIVES.

METRIC per config (censoring-robust): slot_rate = E[paid]/E[life] = sum(paid)/sum(months) (ratio-of-means;
numerator+denominator right-truncate together at the data window, so the rate is robust where the lifetime
totals are not). NET of refund cost: net_slot = slot_rate - cost_per_funded/E[life] (each account death
refills the slot at cost_per_funded). Fleet $/mo = cap * net_slot. SURVIVAL: per-year median payout > 0 in
every start-year; bust% reported; worst-year median reported. REJECT any config that wipes in a bad year.

RESEARCH / SIM ONLY. READ-ONLY on bot strategy code (imports only). Writes confined to
research/passrate_opt/ + reports/passrate_opt/. NOTHING ARMED. LIVE HOLD in force.

FOUNDATION — reuses certified machinery BY IMPORT, re-models NOTHING of the strategy/fills/payout-rules:
  * research/passrate_opt/funded_stage_opt.py (G) -> build_vpc, build_level_matrix, days_for,
    monthly_starts, run_pa_diag, fixed_size, cushion_size  (report-05 certified funded engine; itself
    imports F=honest_eval_engines + H=tools_account_size_research). Payout RULES UNCHANGED.
  * report-06 cost/renewal model reproduced verbatim (cost_per_funded, cap steady state).

ABSOLUTE HONESTY: every Apex 50K rule is help-center-derived, UNVERIFIED vs a live contract. The ~20
account cap is UNVERIFIED and is the hinge of the fleet $/mo. SIM only; funded fills at size unproven live.
"""
import os, sys, json, hashlib, warnings
warnings.filterwarnings("ignore")
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import funded_stage_opt as G   # report-05 certified funded engine (imports F+H internally)

# ---- refund/renewal cost inputs (report-06 verbatim; UNVERIFIED) --------------------------------
PASS_MONDAY = 0.419         # frozen eval pass (VPC 50K AGGRESSIVE $2000/cap10), Monday cohort
PASS_ROLLING = 0.379
EVAL_FEE_PROMO = 24.50      # recurring promo eval fee (UNVERIFIED)
ACTIVATION = 130.0          # one-time PA activation (UNVERIFIED)
ACCOUNT_CAP = 20            # concurrent funded PAs (UNVERIFIED — hinge of fleet $/mo)
COST_PER_FUNDED = (1.0 / PASS_MONDAY) * EVAL_FEE_PROMO + ACTIVATION   # ~$188.5 to stand up a fresh funded PA

# ---- custom fine-grained size levels for cushion bands (budget $/ct-risk, cap contracts) --------
FAST_LEVELS = {
    "c1": (400, 1), "c2": (550, 2), "c3": (700, 3), "c4": (1000, 4),
    "c5": (1300, 5), "c6": (1600, 6), "c8": (2000, 8),
}

# static sweep grid (task: budget 400->2000, cap 2->8)
STATIC_BUDGETS = [400, 550, 700, 900, 1100, 1400, 1700, 2000]
STATIC_CAPS = [2, 3, 4, 5, 6, 8]


# =================================================================================================
def per_year_median(dates, starts, res):
    yr = {}
    for s, r in zip(starts, res):
        yr.setdefault(int(dates[s].year), []).append(r["paid"])
    return {y: round(float(np.median(v))) for y, v in sorted(yr.items())}


def metrics(dates, starts, res):
    """Throughput + survival metrics from a list of run_pa_diag results."""
    paid = np.array([r["paid"] for r in res], float)
    life = np.array([r["months"] for r in res], float)
    npay = np.array([r["n_payouts"] for r in res], float)
    outc = [r["outcome"] for r in res]
    n = len(res)
    e_paid_mean = float(paid.mean())
    life_mean = float(life.mean())
    # censoring-robust slot rate = sum(paid)/sum(months) = mean(paid)/mean(life)
    slot_gross = e_paid_mean / life_mean if life_mean > 0 else 0.0
    net_slot = slot_gross - COST_PER_FUNDED / life_mean if life_mean > 0 else 0.0
    pym = per_year_median(dates, starts, res)
    worst_year = min(pym.values())
    # time-to-collect-ladder (months) among accounts that reached CLOSED_MAX
    close_life = [r["months"] for r in res if r["outcome"] == "CLOSED_MAX"]
    # data_end censoring share (higher => rate more trustworthy when LOWER)
    data_end_pct = 100 * outc.count("DATA_END") / n
    return dict(
        n=n,
        e_paid_mean=round(e_paid_mean), e_paid_median=round(float(np.median(paid))),
        life_mean=round(life_mean, 1), life_median=round(float(np.median(life)), 1),
        slot_gross=round(slot_gross, 1), net_slot=round(net_slot, 1),
        fleet_net_mo=round(ACCOUNT_CAP * net_slot),
        fleet_gross_mo=round(ACCOUNT_CAP * slot_gross),
        bust_pct=round(100 * outc.count("BUST") / n, 1),
        closed_max_pct=round(100 * outc.count("CLOSED_MAX") / n, 1),
        data_end_pct=round(data_end_pct, 1),
        zero_pct=round(100 * float((paid == 0).mean()), 1),
        e_n_payouts=round(float(npay.mean()), 2),
        per_year_median=pym, worst_year_median=worst_year,
        survives=(worst_year > 0),
        time_to_close_median_mo=round(float(np.median(close_life)), 1) if close_life else None,
        n_closed=len(close_life),
    )


def run_static(vpc, budget, cap, runway=G.RUNWAY_DAYS):
    d = G.days_for(vpc, budget, cap)
    m = {"_s": [(x[1], x[2]) for x in d]}
    dts = [x[0] for x in d]
    st = [i for i, dd in enumerate(dts)
          if (dts[-1] - dd).days >= runway and (i == 0 or dts[i - 1].month != dd.month)]
    res = [G.run_pa_diag(dts, m, s, G.fixed_size("_s")) for s in st]
    return dts, st, res


def build_fast_matrix(vpc, levels=FAST_LEVELS, runway=G.RUNWAY_DAYS):
    mats, dates = {}, None
    for k, (b, c) in levels.items():
        d = G.days_for(vpc, b, c)
        if dates is None:
            dates = [x[0] for x in d]
        else:
            assert [x[0] for x in d] == dates, f"date misalign {k}"
        mats[k] = [(x[1], x[2]) for x in d]
    starts = [i for i, dd in enumerate(dates)
              if (dates[-1] - dd).days >= runway and (i == 0 or dates[i - 1].month != dd.month)]
    return dates, mats, starts


# =================================================================================================
def main():
    print("building VPC stream (reused report-05 G machinery)…", flush=True)
    vpc = G.build_vpc()
    # baseline matrix (report-05 LEVELS) for the two bracket canaries + brake band
    dates, mats, starts = G.build_level_matrix(vpc), None, None
    dates, mats = dates  # build_level_matrix returns (dates, mats)
    starts = G.monthly_starts(dates)

    out = dict(meta=dict(generated="2026-07-13", n_days=len(dates),
                         window=f"{dates[0].date()}->{dates[-1].date()}", n_starts=len(starts),
                         runway_days=G.RUNWAY_DAYS, ares_stop=G.ARES_STOP,
                         account_cap=ACCOUNT_CAP, cost_per_funded=round(COST_PER_FUNDED, 1),
                         pass_monday=PASS_MONDAY, eval_fee_promo=EVAL_FEE_PROMO, activation=ACTIVATION,
                         metric=("net_slot = E[paid]/E[life] - cost_per_funded/E[life]; "
                                 "fleet_net_mo = cap*net_slot; SURVIVAL = per-year median>0 all years"),
                         confidence="ALL Apex 50K rules help-center-derived, UNVERIFIED vs live contract"))

    # ---- CANARY 1: report-05 baseline $400/cap2 (bracket B, fast/fair-weather) ----
    base_res = [G.run_pa_diag(dates, mats, s, G.fixed_size("S")) for s in starts]
    canary_base = metrics(dates, starts, base_res)
    print(f"[CANARY base S(400/cap2)] mean ${canary_base['e_paid_mean']} med ${canary_base['e_paid_median']} "
          f"bust {canary_base['bust_pct']}% closed_max {canary_base['closed_max_pct']}% life {canary_base['life_mean']}mo "
          f"(target 2893/1500/53.3/4.4/16.4)", flush=True)

    # ---- CANARY 2: report-05 recommended cushion-brake cap<=3 (bracket A, slow/survives) ----
    brake = G.cushion_size([(0, "XS"), (2500, "S"), (5000, "M")])
    brake_res = [G.run_pa_diag(dates, mats, s, brake) for s in starts]
    canary_brake = metrics(dates, starts, brake_res)
    print(f"[CANARY brake cush3band] mean ${canary_brake['e_paid_mean']} med ${canary_brake['e_paid_median']} "
          f"bust {canary_brake['bust_pct']}% life {canary_brake['life_mean']}mo slot ${canary_brake['slot_gross']} "
          f"net_slot ${canary_brake['net_slot']} fleet ${canary_brake['fleet_net_mo']} (target 2842/2362/0/31.5, ~$90 slot)",
          flush=True)
    out["bracket_A_cushion_brake"] = canary_brake
    out["bracket_B_preopt_400cap2"] = canary_base

    # ---- SEARCH 1: STATIC sizing sweep (budget 400->2000 x cap 2->8) ----
    static = []
    for b in STATIC_BUDGETS:
        for c in STATIC_CAPS:
            dts, st, res = run_static(vpc, b, c)
            mk = metrics(dts, st, res)
            static.append(dict(budget=b, cap=c, **mk))
    out["search1_static"] = static
    print("\n[SEARCH1 static] budget/cap -> net_slot$/mo | fleet$/mo | bust% | worst-yr-med | survives")
    for r in sorted(static, key=lambda x: x["net_slot"], reverse=True)[:12]:
        print(f"  {r['budget']:>4}/c{r['cap']}: net ${r['net_slot']:>6} fleet ${r['fleet_net_mo']:>6} "
              f"bust {r['bust_pct']:>4}% worstYr ${r['worst_year_median']:>5} surv={r['survives']} "
              f"life {r['life_mean']}mo close {r['closed_max_pct']}%", flush=True)

    # ---- SEARCH 2: DYNAMIC cushion bands (conservative brake -> faster) ----
    fdates, fmats, fstarts = build_fast_matrix(vpc)
    band_variants = {
        "brake_cap3_baseline": [(0, "c1"), (2500, "c2"), (5000, "c3")],
        "band_cap4_mild":      [(0, "c1"), (2000, "c2"), (4000, "c3"), (6500, "c4")],
        "band_cap4_floor2":    [(0, "c2"), (2500, "c3"), (5000, "c4")],
        "band_cap5_floor2":    [(0, "c2"), (3000, "c3"), (6000, "c5")],
        "band_cap6_fast":      [(0, "c2"), (2500, "c3"), (5000, "c4"), (8000, "c6")],
        "band_cap6_floor3":    [(0, "c3"), (3000, "c4"), (6500, "c6")],
        "aggro_cap8":          [(0, "c2"), (2500, "c4"), (5000, "c6"), (8000, "c8")],
        "aggro_cap8_floor3":   [(0, "c3"), (3000, "c5"), (7000, "c8")],
    }
    dyn = {}
    for name, bands in band_variants.items():
        res = [G.run_pa_diag(fdates, fmats, s, G.cushion_size(bands)) for s in fstarts]
        dyn[name] = dict(bands=bands, **metrics(fdates, fstarts, res))
    out["search2_dynamic_cushion"] = dyn
    print("\n[SEARCH2 dynamic cushion] name -> net_slot | fleet | bust% | worst-yr | survives")
    for name, r in sorted(dyn.items(), key=lambda kv: kv[1]["net_slot"], reverse=True):
        print(f"  {name:22} net ${r['net_slot']:>6} fleet ${r['fleet_net_mo']:>6} bust {r['bust_pct']:>4}% "
              f"worstYr ${r['worst_year_median']:>5} surv={r['survives']} life {r['life_mean']}mo "
              f"close {r['closed_max_pct']}%", flush=True)

    # ---- SEARCH 3: COLLECT-AND-CLOSE posture (time-to-collect ladder vs bust, static configs) ----
    cac = []
    for r in static:
        cac.append(dict(budget=r["budget"], cap=r["cap"], closed_max_pct=r["closed_max_pct"],
                        time_to_close_median_mo=r["time_to_close_median_mo"], bust_pct=r["bust_pct"],
                        e_n_payouts=r["e_n_payouts"], net_slot=r["net_slot"], survives=r["survives"]))
    out["search3_collect_and_close"] = cac

    # ---- SEARCH 2b: escalate-ONLY-when-VERY-FAT bands (probe the sizing frontier ceiling) ----
    #   thesis test: since withdraw-to-floor keeps cushion thin, only escalate deep in profit where
    #   2023-style thin-cushion years never trigger it. Does ANY beat the cap<=3 brake AND survive?
    fat_variants = {
        "brake_cap2_only":     [(0, "c1"), (3000, "c2")],
        "brake_cap3_hi_trig":  [(0, "c1"), (4000, "c2"), (9000, "c3")],
        "fat_cap4_at_10k":     [(0, "c1"), (2500, "c2"), (5000, "c3"), (10000, "c4")],
        "fat_cap5_at_12k":     [(0, "c1"), (3000, "c2"), (6000, "c3"), (12000, "c5")],
    }
    fatd = {}
    for name, bands in fat_variants.items():
        res = [G.run_pa_diag(fdates, fmats, s, G.cushion_size(bands)) for s in fstarts]
        fatd[name] = dict(bands=bands, **metrics(fdates, fstarts, res))
    out["search2b_escalate_when_fat"] = fatd
    print("\n[SEARCH2b escalate-only-when-fat]")
    for name, r in sorted(fatd.items(), key=lambda kv: kv[1]["net_slot"], reverse=True):
        print(f"  {name:20} net ${r['net_slot']:>6} bust {r['bust_pct']:>4}% worstYr ${r['worst_year_median']:>5} "
              f"surv={r['survives']} life {r['life_mean']}mo", flush=True)

    # ---- SEARCH 4: BANKING CADENCE as the survival-safe throughput lever (collect ladder sooner) ----
    #   faster banking cannot raise bust (it only removes stranded balance sooner) but it collects the
    #   $13k ladder faster -> CLOSED_MAX sooner -> shorter life -> higher turnover. Gated on the (UNVERIFIED)
    #   true Apex minimum payout interval. Applied to the two SURVIVING sizings: cap<=3 brake and cap1-flat.
    brake3_bands = [(0, "c1"), (2500, "c2"), (5000, "c3")]
    brake2_bands = [(0, "c1"), (3000, "c2")]
    cad_pols = {"brake_cap2": G.cushion_size(brake2_bands), "brake_cap3": G.cushion_size(brake3_bands),
                "cap1_flat": G.fixed_size("c1")}
    cad = {k: {} for k in cad_pols}
    for cd in (30, 21, 14, 7):
        for pol, fn in cad_pols.items():
            res = [G.run_pa_diag(fdates, fmats, s, fn, cadence=cd) for s in fstarts]
            cad[pol][f"cad{cd}"] = metrics(fdates, fstarts, res)
    out["search4_cadence_throughput"] = cad
    print("\n[SEARCH4 cadence throughput lever]  policy/cadence -> net_slot | fleet | closed_max% | ttc mo | worstYr | surv")
    for pol in cad_pols:
        for cd in (30, 21, 14, 7):
            r = cad[pol][f"cad{cd}"]
            print(f"  {pol:11} cad{cd:>2}: net ${r['net_slot']:>6} fleet ${r['fleet_net_mo']:>6} "
                  f"close {r['closed_max_pct']:>4}% ttc {str(r['time_to_close_median_mo']):>5} "
                  f"worstYr ${r['worst_year_median']:>5} surv={r['survives']}", flush=True)

    # ---- WINNER selection: max net_slot among SURVIVORS (per-year median>0 every year) ----
    #   two winners: VERIFIED-cadence (30d) best, and UNVERIFIED faster-cadence upside best (flagged).
    pool_verified, pool_all = [], []
    def add(kind, label, r, verified):
        rec = dict(kind=kind, label=label, **r)
        pool_all.append(rec)
        if verified:
            pool_verified.append(rec)
    for r in static:      add("static", f"{r['budget']}/cap{r['cap']}", r, True)
    for n, r in dyn.items():   add("dynamic", n, r, True)
    for n, r in fatd.items():  add("dynamic_fat", n, r, True)
    for pol in cad:
        for cd, r in cad[pol].items():
            add(f"cadence_{pol}", f"{pol}_{cd}", r, cd == "cad30")   # only 30d is the verified rule
    surv_verified = [r for r in pool_verified if r["survives"]]
    surv_all = [r for r in pool_all if r["survives"]]
    winner = sorted(surv_verified, key=lambda r: r["net_slot"], reverse=True)[0]
    winner_unverified = sorted(surv_all, key=lambda r: r["net_slot"], reverse=True)[0]
    out["winner_unverified_cadence_upside"] = {k: winner_unverified.get(k) for k in
        ("kind", "label", "net_slot", "fleet_net_mo", "bust_pct", "worst_year_median", "per_year_median")}
    raw = sorted(pool_all, key=lambda r: r["net_slot"], reverse=True)[0]
    out["winner_survivor"] = {k: winner[k] for k in
        ("kind", "label", "net_slot", "fleet_net_mo", "slot_gross", "e_paid_mean", "e_paid_median",
         "life_mean", "bust_pct", "closed_max_pct", "data_end_pct", "per_year_median",
         "worst_year_median", "time_to_close_median_mo", "e_n_payouts")}
    out["raw_fast_rejected"] = {k: raw[k] for k in
        ("kind", "label", "net_slot", "fleet_net_mo", "bust_pct", "per_year_median",
         "worst_year_median", "survives")}
    print(f"\n[WINNER survivor] {winner['kind']} {winner['label']}: net_slot ${winner['net_slot']}/mo "
          f"fleet ${winner['fleet_net_mo']}/mo bust {winner['bust_pct']}% worstYr ${winner['worst_year_median']} "
          f"PYmed {winner['per_year_median']} ttc {winner['time_to_close_median_mo']}mo", flush=True)
    print(f"[raw-fast REJECTED] {raw['kind']} {raw['label']}: net_slot ${raw['net_slot']} "
          f"worstYr ${raw['worst_year_median']} survives={raw['survives']}", flush=True)

    # ---- 2026 SURVIVAL robustness: shorter runway to include 2026 starts (flagged: more censored) ----
    #   winner is the cap-2 brake band [(0,c1),(3000,c2)] (verified-cadence 30d). Re-run at short runways.
    all_bands = {**band_variants, **fat_variants, "brake_cap2_only": [(0, "c1"), (3000, "c2")],
                 "brake_cap3": [(0, "c1"), (2500, "c2"), (5000, "c3")]}
    win_band = all_bands.get(winner["label"], [(0, "c1"), (3000, "c2")])
    r2026 = {}
    for rw in (180, 150, 120):
        d2, m2, s2 = build_fast_matrix(vpc, runway=rw)
        res = [G.run_pa_diag(d2, m2, s, G.cushion_size(win_band)) for s in s2]
        mk = metrics(d2, s2, res)
        r2026[f"runway{rw}"] = dict(n=mk["n"], per_year_median=mk["per_year_median"],
                                    worst_year_median=mk["worst_year_median"], survives=mk["survives"],
                                    bust_pct=mk["bust_pct"], net_slot=mk["net_slot"])
    out["winner_2026_runway_sensitivity"] = r2026
    print(f"\n[2026 runway-sensitivity of winner] {json.dumps(r2026, default=str)}", flush=True)

    # ---- determinism ----
    md5 = hashlib.md5(json.dumps(out, sort_keys=True, default=str).encode()).hexdigest()
    out["meta"]["determinism_md5"] = md5
    dest = os.path.join(REPO, "reports", "passrate_opt", "07_funded_throughput_optimum.json")
    with open(dest, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(f"\n[saved] {dest}  md5={md5}", flush=True)
    return out


if __name__ == "__main__":
    main()
