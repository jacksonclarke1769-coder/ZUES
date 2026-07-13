"""PER-ACCOUNT FUNDED INCOME by ACCOUNT TIER — Apex 50K/100K/150K, VPC edge FROZEN (honest sim, 2026-07-13).

QUESTION (operator): can VPC reach $500-1,000/MONTH PER FUNDED ACCOUNT on Apex, and at what tier + risk?
Hypothesis: a 50K's $2,500 trailing DD physically caps size (report-07: survivable ~$98/slot-mo, fair-
weather ~$216/slot-mo but WIPED in 2023). Only a BIGGER account (bigger DD -> bigger size + bigger ladder)
could physically reach $500-1k/mo. This harness tests that across tiers at TWO risk postures.

POSTURE A = SURVIVAL-OPTIMAL: highest net $/slot-month among configs with per-year median payout > 0 in
            EVERY start-year (incl 2023). bust ~0. (the investable rate)
POSTURE B = FAIR-WEATHER MAX: highest net $/slot-month IGNORING survival; its bust% + its 2023/worst-year
            median are reported so the wipe risk is explicit. (the illusion)

METRIC (censoring-robust, IDENTICAL to report-07): slot_gross = E[paid]/E[life] = sum(paid)/sum(months);
net_slot = slot_gross - cost_per_funded/E[life]; fleet_net = cap * net_slot. Survival = per-year median>0.

RESEARCH / SIM ONLY. READ-ONLY on bot strategy code (imports only). Writes confined to
research/passrate_opt/ + reports/passrate_opt/. NOTHING ARMED. LIVE HOLD in force.

FOUNDATION — reuses certified machinery BY IMPORT, re-models NOTHING:
  * research/passrate_opt/funded_stage_opt.py (G) = report-05 certified funded engine (build_vpc,
    days_for, monthly_starts, run_pa_diag, fixed_size, cushion_size; imports F=honest_eval_engines +
    H=tools_account_size_research day-collapse). Payout RULES unchanged.
  * report-07 throughput metric (net_slot/fleet) reproduced verbatim.
  * PER-TIER Apex constants taken from tools_account_size_research.SPECS (the canonical per-tier source in
    the codebase). The tier layer only MONKEYPATCHES G's module globals (START/TRAIL/FLOOR/MIN_REQ/LOCK_EOD/
    DLL/ARES_STOP) + passes the tier ladder to run_pa_diag. No eval/payout logic re-implemented.

ABSOLUTE HONESTY — the UNVERIFIED inputs (flagged in every output):
  * ALL Apex rules help-center-derived, no live contract.
  * 100K/150K ladders are ESTIMATES (SPECS docstring: 100K ~$17k / 150K ~$21.5k lifetime; endpoints
    documented, intermediate steps estimated monotone). The task's brief guessed ~$26k/~$39k (naive linear
    scaling) — we use the codebase SPECS ($17k/$21.5k) as the certified machinery and FLAG both.
  * Tier DD/DLL disagree across sources: SPECS(150K trail 4000, DLL 2000) vs report-03 table(150K trail
    5000, DLL 3000) vs funded_rules(150K trailing 5000). We use SPECS (what report-05/07 machinery uses;
    its 50K matches G exactly) and FLAG the conflict.
  * Size HEADROOM per tier scaled by the trailing-DD ratio f=trail/2500 (50K 1.0 / 100K 1.2 / 150K 1.6) —
    the DD is the hard bust cap. DLL/ARES give ~2x daily headroom; we use the tighter trail ratio (flagged).
  * Cost-to-obtain per tier: pass rate report-03 aggressive (50K .38 / 100K .22 / 150K .14); eval fee promo
    ~$25/$50/$85 (FLAGGED); activation $130 held (may scale, FLAGGED). cost_per_funded=(1/pass)*fee+activ.
"""
import os, sys, json, hashlib, warnings
warnings.filterwarnings("ignore")
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import funded_stage_opt as G          # report-05 certified funded engine (imports F+H internally)
import tools_account_size_research as SR   # canonical per-tier Apex SPECS (via G's sys.path)

ACCOUNT_CAP = 20                       # concurrent funded PAs (UNVERIFIED — hinge of fleet $/mo)
ACTIVATION = 130.0                     # one-time PA activation (UNVERIFIED; held across tiers, may scale)

# ---- per-tier cost-to-obtain inputs (report-03 aggressive pass% + promo fee ladder; FLAGGED) -----
TIER_COST = {
    "50K":  dict(pass_rate=0.38, eval_fee=25.0),
    "100K": dict(pass_rate=0.22, eval_fee=50.0),
    "150K": dict(pass_rate=0.14, eval_fee=85.0),
}

# ---- static sizing sweep (budgets scaled by DD ratio f; caps 2..8) --------------------------------
BASE_BUDGETS = [400, 550, 700, 900, 1100, 1400, 1700, 2000]
STATIC_CAPS = [2, 3, 4, 5, 6, 8]
# fine-grained cushion-band levels (budget scaled by f at build time)
BASE_LEVELS = {"c1": (400, 1), "c2": (550, 2), "c3": (700, 3), "c4": (1000, 4),
               "c5": (1300, 5), "c6": (1600, 6), "c8": (2000, 8)}


def tier_constants(name):
    """Derive the full 50K-style funded rule set for a tier from SPECS (floor/min_req/lock same formula)."""
    s = SR.SPECS[name]
    start, trail = s["start"], s["trail"]
    return dict(START=start, TRAIL=trail, DLL=s["dll"], ARES_STOP=s["stop"],
                FLOOR=start + trail - 400.0, MIN_REQ=start + trail + 100.0,
                LOCK_EOD=start + trail + 100.0, LADDER=[float(x) for x in s["ladder"]],
                target=s["target"], ladder_lifetime=float(sum(s["ladder"])),
                f=trail / 2500.0)


def patch_tier(c):
    """Monkeypatch G's module globals so the reused run_pa_diag/days_for run under this tier's rules."""
    G.START, G.TRAIL, G.FLOOR = c["START"], c["TRAIL"], c["FLOOR"]
    G.MIN_REQ, G.LOCK_EOD, G.DLL = c["MIN_REQ"], c["LOCK_EOD"], c["DLL"]
    G.ARES_STOP = c["ARES_STOP"]


def cost_per_funded(name):
    tc = TIER_COST[name]
    return (1.0 / tc["pass_rate"]) * tc["eval_fee"] + ACTIVATION


# =================================================================================================
def metrics(dates, starts, res, cpf, ladder):
    paid = np.array([r["paid"] for r in res], float)
    life = np.array([r["months"] for r in res], float)
    outc = [r["outcome"] for r in res]
    n = len(res)
    life_mean = float(life.mean())
    slot_gross = float(paid.mean()) / life_mean if life_mean > 0 else 0.0
    net_slot = slot_gross - cpf / life_mean if life_mean > 0 else 0.0
    yr = {}
    for s, r in zip(starts, res):
        yr.setdefault(int(dates[s].year), []).append(r["paid"])
    pym = {y: round(float(np.median(v))) for y, v in sorted(yr.items())}
    worst = min(pym.values())
    return dict(n=n, e_paid_mean=round(float(paid.mean())), life_mean=round(life_mean, 1),
                slot_gross=round(slot_gross, 1), net_slot=round(net_slot, 1),
                fleet_net_mo=round(ACCOUNT_CAP * net_slot), fleet_gross_mo=round(ACCOUNT_CAP * slot_gross),
                bust_pct=round(100 * outc.count("BUST") / n, 1),
                closed_max_pct=round(100 * outc.count("CLOSED_MAX") / n, 1),
                per_year_median=pym, y2023=pym.get(2023), worst_year_median=worst,
                survives=(worst > 0))


def run_static(vpc, budget, cap, ladder, cpf, runway=G.RUNWAY_DAYS):
    d = G.days_for(vpc, budget, cap)               # uses patched G.DLL / G.ARES_STOP
    m = {"_s": [(x[1], x[2]) for x in d]}
    dts = [x[0] for x in d]
    st = [i for i, dd in enumerate(dts)
          if (dts[-1] - dd).days >= runway and (i == 0 or dts[i - 1].month != dd.month)]
    res = [G.run_pa_diag(dts, m, s, G.fixed_size("_s"), ladder=ladder) for s in st]
    return metrics(dts, st, res, cpf, ladder)


def build_band_matrix(vpc, f, runway=G.RUNWAY_DAYS):
    mats, dates = {}, None
    levels = {k: (round(b * f), c) for k, (b, c) in BASE_LEVELS.items()}
    for k, (b, c) in levels.items():
        d = G.days_for(vpc, b, c)
        if dates is None:
            dates = [x[0] for x in d]
        else:
            assert [x[0] for x in d] == dates, f"date misalign {k}"
        mats[k] = [(x[1], x[2]) for x in d]
    starts = [i for i, dd in enumerate(dates)
              if (dates[-1] - dd).days >= runway and (i == 0 or dates[i - 1].month != dd.month)]
    return dates, mats, starts, levels


def run_band(dates, mats, starts, bands, ladder, cpf):
    res = [G.run_pa_diag(dates, mats, s, G.cushion_size(bands), ladder=ladder) for s in starts]
    return metrics(dates, starts, res, cpf, ladder)


# =================================================================================================
def main():
    print("building VPC stream (reused report-05 G machinery)…", flush=True)
    vpc = G.build_vpc()
    out = dict(meta=dict(generated="2026-07-13", account_cap=ACCOUNT_CAP, activation=ACTIVATION,
                         metric=("net_slot = E[paid]/E[life] - cost_per_funded/E[life]; "
                                 "fleet=cap*net_slot; POSTURE_A=max net among survivors (py-median>0 all yrs), "
                                 "POSTURE_B=max net ignoring survival + its bust%/2023"),
                         tier_constant_source="tools_account_size_research.SPECS (canonical per-tier)",
                         confidence=("ALL Apex rules help-center-derived UNVERIFIED; 100K/150K ladders "
                                     "ESTIMATES ($17k/$21.5k SPECS, NOT task's ~$26k/$39k); DD/DLL disagree "
                                     "across sources (SPECS used); size headroom scaled by trail ratio f; "
                                     "cost fee ladder $25/$50/$85 promo FLAGGED, activation $130 held")),
               tiers={})

    for name in ("50K", "100K", "150K"):
        c = tier_constants(name)
        patch_tier(c)
        cpf = cost_per_funded(name)
        f = c["f"]
        print(f"\n===== TIER {name}  (DD {c['TRAIL']:.0f}, DLL {c['DLL']:.0f}, stop {c['ARES_STOP']:.0f}, "
              f"ladder ${c['ladder_lifetime']:.0f}, f={f}, cost/funded ${cpf:.0f}) =====", flush=True)

        configs = []   # each: dict(label, kind, **metrics)

        # ---- STATIC sweep (budgets scaled by f) ----
        for b0 in BASE_BUDGETS:
            b = round(b0 * f)
            for cap in STATIC_CAPS:
                mk = run_static(vpc, b, cap, c["LADDER"], cpf)
                configs.append(dict(label=f"{b}/cap{cap}", kind="static", **mk))

        # ---- DYNAMIC cushion-brake bands (cushion triggers scaled by f) ----
        dates, mats, starts, levels = build_band_matrix(vpc, f)
        t = lambda x: round(x * f)   # scale cushion trigger by DD ratio
        band_variants = {
            "brake_cap2":       [(0, "c1"), (t(3000), "c2")],
            "brake_cap3":       [(0, "c1"), (t(2500), "c2"), (t(5000), "c3")],
            "brake_cap4":       [(0, "c1"), (t(2500), "c2"), (t(5000), "c3"), (t(8000), "c4")],
            "band_cap5_fast":   [(0, "c2"), (t(3000), "c3"), (t(6000), "c5")],
            "aggro_cap8":       [(0, "c2"), (t(2500), "c4"), (t(5000), "c6"), (t(8000), "c8")],
        }
        for lbl, bands in band_variants.items():
            mk = run_band(dates, mats, starts, bands, c["LADDER"], cpf)
            configs.append(dict(label=lbl, kind="dynamic", bands=bands, **mk))

        # ---- POSTURE split ----
        #   A (SURVIVAL-OPTIMAL, task def): median>0 every year AND bust ~0% (<=5). the investable rate.
        #   A_loose: median>0 every year but ANY bust (tolerate wipes of individual accounts). middle case.
        #   B (FAIR-WEATHER MAX): max net ignoring survival; report its bust% + 2023.
        survivors_strict = [r for r in configs if r["survives"] and r["bust_pct"] <= 5.0]
        survivors_loose = [r for r in configs if r["survives"]]
        pA = max(survivors_strict, key=lambda r: r["net_slot"]) if survivors_strict else None
        pA_loose = max(survivors_loose, key=lambda r: r["net_slot"]) if survivors_loose else None
        pB = max(configs, key=lambda r: r["net_slot"])

        # ---- 50K CANARY: brake_cap2 must reproduce report-07 (gross 104.3 / with cost188.5 net 98.3) ----
        canary = None
        if name == "50K":
            bc2 = next(r for r in configs if r["label"] == "brake_cap2")
            # report-07 used cost_per_funded=188.5 (pass .419, fee 24.50) -> recompute net at that cost
            net_at_1885 = round(bc2["slot_gross"] - 188.5 / bc2["life_mean"], 1)
            canary = dict(brake_cap2_slot_gross=bc2["slot_gross"], target_gross=104.3,
                          net_at_cost188_5=net_at_1885, target_net_98_3=98.3,
                          bust_pct=bc2["bust_pct"], per_year_median=bc2["per_year_median"],
                          matches=(abs(bc2["slot_gross"] - 104.3) < 0.5 and abs(net_at_1885 - 98.3) < 0.5))
            print(f"[CANARY 50K brake_cap2] gross ${bc2['slot_gross']} (t104.3) net@188.5 ${net_at_1885} "
                  f"(t98.3) bust {bc2['bust_pct']}% PY {bc2['per_year_median']} match={canary['matches']}",
                  flush=True)

        out["tiers"][name] = dict(
            constants=dict(start=c["START"], trail=c["TRAIL"], target=c["target"], dll=c["DLL"],
                           ares_stop=c["ARES_STOP"], floor=c["FLOOR"], min_req=c["MIN_REQ"],
                           ladder=c["LADDER"], ladder_lifetime=c["ladder_lifetime"], size_headroom_f=f),
            cost=dict(pass_rate=TIER_COST[name]["pass_rate"], eval_fee=TIER_COST[name]["eval_fee"],
                      activation=ACTIVATION, cost_per_funded=round(cpf, 1),
                      cost_note="=(1/pass)*fee+activation; expected eval attempts to 1 funded = 1/pass"),
            canary=canary,
            posture_A_survival={k: pA.get(k) for k in
                ("label", "kind", "slot_gross", "net_slot", "fleet_net_mo", "bust_pct",
                 "y2023", "worst_year_median", "per_year_median", "life_mean", "e_paid_mean")} if pA else None,
            posture_A_loose_median_positive={k: pA_loose.get(k) for k in
                ("label", "kind", "slot_gross", "net_slot", "fleet_net_mo", "bust_pct",
                 "y2023", "worst_year_median", "per_year_median", "life_mean")} if pA_loose else None,
            posture_B_fairweather={k: pB.get(k) for k in
                ("label", "kind", "slot_gross", "net_slot", "fleet_net_mo", "bust_pct",
                 "y2023", "worst_year_median", "per_year_median", "survives", "life_mean")},
            all_configs=[{k: r.get(k) for k in
                ("label", "kind", "slot_gross", "net_slot", "fleet_net_mo", "bust_pct",
                 "y2023", "worst_year_median", "survives", "life_mean")} for r in
                sorted(configs, key=lambda r: r["net_slot"], reverse=True)],
        )
        if pA:
            print(f"[POSTURE A survival bust<=5] {pA['label']}: net ${pA['net_slot']}/slot-mo gross ${pA['slot_gross']} "
                  f"fleet ${pA['fleet_net_mo']} bust {pA['bust_pct']}% 2023 ${pA['y2023']} worst ${pA['worst_year_median']}",
                  flush=True)
        if pA_loose:
            print(f"[POSTURE A_loose med>0 any-bust] {pA_loose['label']}: net ${pA_loose['net_slot']}/slot-mo "
                  f"bust {pA_loose['bust_pct']}% 2023 ${pA_loose['y2023']} worst ${pA_loose['worst_year_median']}", flush=True)
        print(f"[POSTURE B fair-weather] {pB['label']}: net ${pB['net_slot']}/slot-mo gross ${pB['slot_gross']} "
              f"fleet ${pB['fleet_net_mo']} bust {pB['bust_pct']}% 2023 ${pB['y2023']} survives={pB['survives']}",
              flush=True)

    # ---- VERDICT synthesis ----
    verdict = {}
    for target in (500, 1000):
        surv_hit = [n for n in out["tiers"]
                    if out["tiers"][n]["posture_A_survival"] and
                    out["tiers"][n]["posture_A_survival"]["net_slot"] >= target]
        loose_hit = [n for n in out["tiers"]
                     if out["tiers"][n]["posture_A_loose_median_positive"] and
                     out["tiers"][n]["posture_A_loose_median_positive"]["net_slot"] >= target]
        fw_hit = [n for n in out["tiers"]
                  if out["tiers"][n]["posture_B_fairweather"]["net_slot"] >= target]
        verdict[f"${target}/mo"] = dict(survivable_bust0_tiers=surv_hit,
                                        median_positive_anybust_tiers=loose_hit, fairweather_tiers=fw_hit)
    out["verdict"] = verdict
    print(f"\n[VERDICT] {json.dumps(verdict)}", flush=True)

    md5 = hashlib.md5(json.dumps(out, sort_keys=True, default=str).encode()).hexdigest()
    out["meta"]["determinism_md5"] = md5
    dest = os.path.join(REPO, "reports", "passrate_opt", "08_per_account_income_by_tier.json")
    with open(dest, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(f"\n[saved] {dest}  md5={md5}", flush=True)
    return out


if __name__ == "__main__":
    main()
