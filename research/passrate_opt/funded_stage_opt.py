"""FUNDED (PA) STAGE OPTIMIZER — Apex 50K, VPC edge FROZEN (honest sim, 2026-07-13).

GOAL: maximize the MEDIAN payout per funded 50K PA (median, because ~1/3-1/2 currently pay $0) by
optimizing how we TRADE + WITHDRAW on the funded account. The VPC edge is NOT changed — only the
funded-management levers (funded size, cushion rule, withdrawal cadence, consistency handling,
de-risk trigger).

RESEARCH / SIM measurement ONLY. READ-ONLY on bot strategy code (imports only). Writes confined to
research/passrate_opt/ + reports/passrate_opt/. NOTHING ARMED. LIVE HOLD remains in force.

FOUNDATION — reuses certified machinery BY IMPORT, re-models NOTHING of the strategy/fills:
  * research/fork_b/honest_eval_engines.py (F) -> databento_5m_rth, v.features, vpc_trades_rich,
    vpc_events_risk  (honest VPC signal/fill + size-to-risk event stream)
  * tools_account_size_research (H)            -> day_rows (ARES $550 stop + Apex DLL flatten)
The ONLY new code is run_pa_diag — a FAITHFUL, instrumented+parametrized reproduction of
apex_funded_40.py:74-113 run_pa. The payout RULES are unchanged; sizing/withdrawal POLICY is
parametrized, and per-sweep block-reason diagnostics are recorded WITHOUT altering the decision path.

ABSOLUTE HONESTY: every Apex 50K rule below is help-center-derived, NOT read off a live contract
(evidence/apex_terms/apex_terms.yaml: confidence UNVERIFIED). Multi-source 2026 help-center pages
corroborate the 50K ladder [1.5/1.5/2/2.5/2.5/3]k=$13k and $250 qual-day. Still UNVERIFIED vs live.
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

# ---- 50K FUNDED RULES (help-center-derived; UNVERIFIED vs live contract) -------------------------
START, TRAIL = 50_000.0, 2_500.0
FLOOR, MIN_REQ = 52_100.0, 52_600.0        # withdraw down to no lower than FLOOR; request needs MIN_REQ
LOCK_EOD = MIN_REQ                          # peak >= 52,600 locks threshold at start+100
DLL = 1_000.0
LADDER = [1_500., 1_500., 2_000., 2_500., 2_500., 3_000.]   # 6 rungs = $13,000 then PA CLOSES
QUAL_DAY_DEFAULT = 250.0
QUAL_N, CONSISTENCY = 5, 0.50
PAYOUT_EVERY_D_DEFAULT = 30                 # ~monthly payout sweep (help-center rule)
ARES_STOP = 550.0                           # bot self-imposed daily realized stop (held constant)
RUNWAY_DAYS = 274                           # >= 9 months forward runway for a funded-PA start

# ---- discrete funded size levels (budget $/ct risk, cap contracts). min 1 ct always -> same dates -
LEVELS = {
    "XS": (300, 1), "S": (400, 2), "M": (700, 3), "L": (1100, 4), "XL": (1600, 6), "XXL": (2000, 10),
}


# =================================================================================================
def build_vpc():
    feats = F.v.features(F.databento_5m_rth()); feats = feats[feats.date >= F.START_DATE]
    return F.vpc_trades_rich(feats)


def days_for(vpc, budget, cap):
    ev = F.vpc_events_risk(vpc, budget=budget, cap=cap)
    return H.day_rows(ev, ARES_STOP, DLL)


def build_level_matrix(vpc, levels=LEVELS):
    """date-aligned {level -> [(real,trough)]}; all levels share identical dates (>=1 ct always)."""
    mats = {}
    dates = None
    for k, (b, c) in levels.items():
        d = days_for(vpc, b, c)
        if dates is None:
            dates = [x[0] for x in d]
        else:
            assert [x[0] for x in d] == dates, f"date misalign at {k}"
        mats[k] = [(x[1], x[2]) for x in d]
    return dates, mats


def monthly_starts(dates):
    last = dates[-1]
    return [i for i, d in enumerate(dates)
            if (last - d).days >= RUNWAY_DAYS and (i == 0 or dates[i - 1].month != d.month)]


# =================================================================================================
def run_pa_diag(dates, mats, start_i, size_fn, ladder=LADDER, qual_day=QUAL_DAY_DEFAULT,
                cadence=PAYOUT_EVERY_D_DEFAULT, floor_buffer=0.0):
    """One funded-PA life. FAITHFUL to apex_funded_40.run_pa; sizing via size_fn(bal,thr,ladder_i,
    locked,i)->level_key, cadence + floor_buffer parametrized, plus per-sweep block diagnostics.
    Returns dict(outcome, months, paid, n_payouts, bucket, death_months, blocks...)."""
    bal, peak_eod, locked = START, START, False
    thr = START - TRAIL
    paid, ladder_i = 0.0, 0
    since = dict(profit=0.0, maxday=0.0, qual=0)
    t0 = dates[start_i]; last_sweep = t0
    # diagnostics
    reached_sweep = False
    blk_minreq = blk_qual = blk_consistency_pure = 0
    withdraw_to = FLOOR + floor_buffer

    outcome = "DATA_END"; death = dates[-1]
    for i in range(start_i, len(dates)):
        d = dates[i]
        lvl = size_fn(bal, thr, ladder_i, locked, i)
        real, trough = mats[lvl][i]
        if bal + min(0.0, trough) <= thr:                 # intraday marked-trough liquidation
            outcome, death = "BUST", d; break
        bal += real
        since["profit"] += real
        since["maxday"] = max(since["maxday"], real)
        if real >= qual_day:
            since["qual"] += 1
        peak_eod = max(peak_eod, bal)
        if not locked:
            thr = max(thr, peak_eod - TRAIL)
            if peak_eod >= LOCK_EOD:
                thr = START + 100.0; locked = True
        if bal <= thr:
            outcome, death = "BUST", d; break
        if (d - last_sweep).days >= cadence:              # payout sweep window
            last_sweep = d
            reached_sweep = True
            ok_min = bal >= MIN_REQ
            ok_qual = since["qual"] >= QUAL_N
            ok_cons = since["profit"] > 0 and since["maxday"] < CONSISTENCY * since["profit"]
            if ok_min and ok_qual and ok_cons:
                amt = min(ladder[ladder_i], bal - withdraw_to)
                if amt > 0:
                    bal -= amt; paid += amt; ladder_i += 1
                    since = dict(profit=0.0, maxday=0.0, qual=0)
                    if ladder_i >= len(ladder):
                        outcome, death = "CLOSED_MAX", d; break
            else:                                          # record binding blocker (priority order)
                if not ok_min:
                    blk_minreq += 1
                elif not ok_qual:
                    blk_qual += 1
                else:
                    blk_consistency_pure += 1              # min+qual met, consistency alone blocked

    months = (death - t0).days / 30.4
    # terminal bucket (mutually exclusive)
    if outcome == "CLOSED_MAX":
        bucket = "e_closed_max"
    elif paid > 0:
        bucket = "partial_payout"
    elif blk_consistency_pure > 0:
        bucket = "b_consistency"
    elif blk_qual > 0:
        bucket = "c_short_qual"
    elif reached_sweep:                                    # sweeps reached, all below MIN_REQ
        bucket = "d_below_minreq"
    else:
        bucket = "a_bust_no_sweep"
    return dict(outcome=outcome, months=months, paid=paid, n_payouts=ladder_i, bucket=bucket,
                death_months=months, blk_minreq=blk_minreq, blk_qual=blk_qual,
                blk_consistency_pure=blk_consistency_pure, reached_sweep=reached_sweep)


# ---- size_fn factories ---------------------------------------------------------------------------
def fixed_size(level):
    return lambda bal, thr, li, locked, i: level


def cushion_size(bands):
    """bands = list of (cushion_threshold, level) sorted ascending; pick the highest band <= cushion.
    cushion = bal - thr (distance to liquidation)."""
    bands = sorted(bands, key=lambda x: x[0])
    def fn(bal, thr, li, locked, i):
        cush = bal - thr
        lvl = bands[0][1]
        for c, l in bands:
            if cush >= c:
                lvl = l
        return lvl
    return fn


def derisk_size(base_level, n_rungs, coast_level):
    """ride base_level until n_rungs banked, then coast at coast_level."""
    return lambda bal, thr, li, locked, i: (coast_level if li >= n_rungs else base_level)


# =================================================================================================
def summarize(dates, mats, size_fn, starts, **kw):
    res = [run_pa_diag(dates, mats, s, size_fn, **kw) for s in starts]
    paids = np.array([r["paid"] for r in res]); months = np.array([r["months"] for r in res])
    npay = np.array([r["n_payouts"] for r in res])
    buckets = [r["bucket"] for r in res]
    n = len(res)
    bcount = {b: buckets.count(b) for b in
              ("a_bust_no_sweep", "b_consistency", "c_short_qual", "d_below_minreq",
               "partial_payout", "e_closed_max")}
    death_by_bucket = {}
    for b in bcount:
        ms = [r["death_months"] for r in res if r["bucket"] == b]
        death_by_bucket[b] = round(float(np.median(ms)), 1) if ms else None
    return dict(
        n=n,
        e_paid_mean=round(float(paids.mean())),
        e_paid_median=round(float(np.median(paids))),
        e_paid_p25=round(float(np.percentile(paids, 25))),
        e_paid_p75=round(float(np.percentile(paids, 75))),
        zero_pct=round(100 * float((paids == 0).mean()), 1),
        bust_pct=round(100 * sum(1 for r in res if r["outcome"] == "BUST") / n, 1),
        closed_max_pct=round(100 * sum(1 for r in res if r["outcome"] == "CLOSED_MAX") / n, 1),
        e_n_payouts=round(float(npay.mean()), 2),
        mean_life_months=round(float(months.mean()), 1),
        median_life_months=round(float(np.median(months)), 1),
        buckets_pct={b: round(100 * c / n, 1) for b, c in bcount.items()},
        death_months_by_bucket=death_by_bucket,
        _paids=paids, _starts=starts, _res=res,
    )


def per_year_median(dates, mats, size_fn, starts, **kw):
    res = [run_pa_diag(dates, mats, s, size_fn, **kw) for s in starts]
    yr = {}
    for s, r in zip(starts, res):
        yr.setdefault(int(dates[s].year), []).append(r["paid"])
    return {y: dict(n=len(v), median=round(float(np.median(v))), mean=round(float(np.mean(v))))
            for y, v in sorted(yr.items())}


# =================================================================================================
def main():
    print("building VPC stream + size-level matrix (reused F/H machinery)…", flush=True)
    vpc = build_vpc()
    dates, mats = build_level_matrix(vpc)
    starts = monthly_starts(dates)
    out = dict(meta=dict(generated="2026-07-13", n_days=len(dates),
                         window=f"{dates[0].date()}->{dates[-1].date()}", n_starts=len(starts),
                         runway_days=RUNWAY_DAYS, ares_stop=ARES_STOP,
                         levels={k: dict(budget=v[0], cap=v[1]) for k, v in LEVELS.items()},
                         confidence="ALL Apex 50K rules help-center-derived, UNVERIFIED vs live"))

    # ---- CANARY: baseline $400/cap2 fixed (target mean 2893 / median 1500 / zero 33.3 / bust 53.3)
    base = summarize(dates, mats, fixed_size("S"), starts)
    out["canary_baseline_S_400cap2"] = {k: base[k] for k in
        ("e_paid_mean", "e_paid_median", "zero_pct", "bust_pct", "closed_max_pct",
         "e_n_payouts", "mean_life_months")}
    print(f"[CANARY] baseline S(400/cap2): mean ${base['e_paid_mean']} median ${base['e_paid_median']} "
          f"zero {base['zero_pct']}% bust {base['bust_pct']}% closed_max {base['closed_max_pct']}% "
          f"(target 2893/1500/33.3/53.3)", flush=True)

    # ---- STEP 1: DIAGNOSIS at the baseline ----
    out["step1_diagnosis_baseline"] = dict(
        buckets_pct=base["buckets_pct"], death_months_by_bucket=base["death_months_by_bucket"],
        note=("buckets partition all PAs: a=bust before any sweep, b=$0 blocked by 50% consistency "
              "(min+qual met), c=$0 short on 5x qual days, d=$0 never reached MIN_REQ at a sweep, "
              "partial=paid>0 not capped, e=CLOSED_MAX (6 rungs, success)"))
    print("\n[STEP1] baseline failure buckets:", json.dumps(base["buckets_pct"]), flush=True)
    print("[STEP1] median death months by bucket:", json.dumps(base["death_months_by_bucket"]), flush=True)

    # ---- STEP 2 / LEVER 1: STATIC sizing sweep (median-maximizing) ----
    STATIC_BUDGETS = [300, 400, 550, 700, 900, 1200, 1600, 2000]
    STATIC_CAPS = [1, 2, 3, 4, 6, 10]
    static = []
    for b in STATIC_BUDGETS:
        for c in STATIC_CAPS:
            d = days_for(vpc, b, c)
            m = {"_tmp": [(x[1], x[2]) for x in d]}
            dts = [x[0] for x in d]
            st = summarize(dts, m, fixed_size("_tmp"), monthly_starts(dts))
            static.append(dict(budget=b, cap=c, e_paid_mean=st["e_paid_mean"],
                               e_paid_median=st["e_paid_median"], zero_pct=st["zero_pct"],
                               bust_pct=st["bust_pct"], closed_max_pct=st["closed_max_pct"],
                               e_n_payouts=st["e_n_payouts"], mean_life_months=st["mean_life_months"],
                               b_consistency_pct=st["buckets_pct"]["b_consistency"]))
    out["lever1_static_sweep"] = static
    best_med = sorted(static, key=lambda r: (r["e_paid_median"], r["e_paid_mean"]), reverse=True)[0]
    best_mean = sorted(static, key=lambda r: (r["e_paid_mean"], r["e_paid_median"]), reverse=True)[0]
    out["lever1_best_median"] = best_med
    out["lever1_best_mean"] = best_mean
    print(f"\n[LEVER1] median-max static: ${best_med['budget']}/cap{best_med['cap']} -> median "
          f"${best_med['e_paid_median']} mean ${best_med['e_paid_mean']} bust {best_med['bust_pct']}%",
          flush=True)
    print(f"[LEVER1] mean-max static:   ${best_mean['budget']}/cap{best_mean['cap']} -> median "
          f"${best_mean['e_paid_median']} mean ${best_mean['e_paid_mean']}", flush=True)

    # ---- LEVER 2: cushion-aware dynamic sizing ----
    cushion_variants = {
        "cush_2band_S_M": [(0, "S"), (4000, "M")],
        "cush_3band_XS_S_M": [(0, "XS"), (2500, "S"), (5000, "M")],
        "cush_3band_S_M_L": [(0, "S"), (3500, "M"), (7000, "L")],
        "cush_brake_XS_M": [(0, "XS"), (3000, "M")],
        "cush_4band_XS_S_M_L": [(0, "XS"), (2000, "S"), (4500, "M"), (8000, "L")],
    }
    out["lever2_cushion"] = {}
    for name, bands in cushion_variants.items():
        st = summarize(dates, mats, cushion_size(bands), starts)
        out["lever2_cushion"][name] = dict(bands=bands, e_paid_mean=st["e_paid_mean"],
                                           e_paid_median=st["e_paid_median"], zero_pct=st["zero_pct"],
                                           bust_pct=st["bust_pct"], closed_max_pct=st["closed_max_pct"],
                                           mean_life_months=st["mean_life_months"])
        print(f"[LEVER2 {name}] median ${st['e_paid_median']} mean ${st['e_paid_mean']} "
              f"bust {st['bust_pct']}% life {st['mean_life_months']}mo", flush=True)

    # ---- LEVER 3: withdrawal cadence + floor buffer (aggressive-earlier banking) ----
    # applied on the median-best static size so we isolate the withdrawal lever
    bb, bc = best_med["budget"], best_med["cap"]
    dbest = days_for(vpc, bb, bc); mbest = {"_b": [(x[1], x[2]) for x in dbest]}
    dtb = [x[0] for x in dbest]; sb = monthly_starts(dtb)
    out["lever3_withdrawal"] = {}
    for cad in (30, 21, 14, 7, 1):
        for fb in (0.0, 250.0, 500.0):
            st = summarize(dtb, mbest, fixed_size("_b"), sb, cadence=cad, floor_buffer=fb)
            key = f"cad{cad}_buf{int(fb)}"
            out["lever3_withdrawal"][key] = dict(cadence=cad, floor_buffer=fb,
                                                 e_paid_mean=st["e_paid_mean"],
                                                 e_paid_median=st["e_paid_median"],
                                                 zero_pct=st["zero_pct"], bust_pct=st["bust_pct"],
                                                 closed_max_pct=st["closed_max_pct"],
                                                 e_n_payouts=st["e_n_payouts"])
        print(f"[LEVER3 cad{cad}] buf0 median ${out['lever3_withdrawal'][f'cad{cad}_buf0']['e_paid_median']} "
              f"mean ${out['lever3_withdrawal'][f'cad{cad}_buf0']['e_paid_mean']}", flush=True)

    # ---- LEVER 4: consistency management (cap effect on the pure-consistency block) ----
    out["lever4_consistency"] = []
    for c in (1, 2, 3, 4, 6, 10):
        d = days_for(vpc, 700, c); m = {"_c": [(x[1], x[2]) for x in d]}; dts = [x[0] for x in d]
        st = summarize(dts, m, fixed_size("_c"), monthly_starts(dts))
        out["lever4_consistency"].append(dict(budget=700, cap=c,
                                              b_consistency_pct=st["buckets_pct"]["b_consistency"],
                                              e_paid_median=st["e_paid_median"],
                                              e_paid_mean=st["e_paid_mean"], bust_pct=st["bust_pct"]))
        print(f"[LEVER4 cap{c}] consistency-block {st['buckets_pct']['b_consistency']}% "
              f"median ${st['e_paid_median']}", flush=True)

    # ---- LEVER 5: bank-and-de-risk (ride base to N rungs, then coast small) ----
    out["lever5_derisk"] = {}
    for base_lvl in ("M", "L", "XL"):
        for n in (1, 2, 3):
            for coast in ("XS", "S"):
                st = summarize(dates, mats, derisk_size(base_lvl, n, coast), starts)
                key = f"base{base_lvl}_bank{n}_coast{coast}"
                out["lever5_derisk"][key] = dict(base=base_lvl, n_rungs=n, coast=coast,
                                                 e_paid_mean=st["e_paid_mean"],
                                                 e_paid_median=st["e_paid_median"],
                                                 zero_pct=st["zero_pct"], bust_pct=st["bust_pct"],
                                                 closed_max_pct=st["closed_max_pct"],
                                                 mean_life_months=st["mean_life_months"])
    d5 = out["lever5_derisk"]
    best5 = sorted(d5.items(), key=lambda kv: (kv[1]["e_paid_median"], kv[1]["e_paid_mean"]),
                   reverse=True)[0]
    out["lever5_best"] = dict(key=best5[0], **best5[1])
    print(f"\n[LEVER5] best de-risk {best5[0]}: median ${best5[1]['e_paid_median']} "
          f"mean ${best5[1]['e_paid_mean']} bust {best5[1]['bust_pct']}%", flush=True)

    # ---- RECOMMENDED COMBINED POLICY (anti-overfit: no single-year concentration) ----
    # Head-to-head on MEDIAN, then a ROBUSTNESS GATE: reject any policy whose per-year median hits $0
    # (single-year concentration). Winner = highest median AMONG gate-passers, tie-break mean.
    cb = sorted(out["lever2_cushion"].items(), key=lambda kv: (kv[1]["e_paid_median"], kv[1]["e_paid_mean"]),
                reverse=True)[0]
    candidates = {
        "baseline_S_400cap2":      (dates, mats, fixed_size("S"), {}),
        f"static_medmax_{bb}x{bc}": (dtb, mbest, fixed_size("_b"), {}),
        "cap1_flat":               (dates, mats, fixed_size("XS"), {}),
        "cush_3band_XS_S_M":       (dates, mats, cushion_size([(0, "XS"), (2500, "S"), (5000, "M")]), {}),
        "cush_4band_medmax":       (dates, mats, cushion_size(cushion_variants[cb[0]]), {}),
        "cush_3band_cad14":        (dates, mats, cushion_size([(0, "XS"), (2500, "S"), (5000, "M")]),
                                    dict(cadence=14)),   # UNVERIFIED faster-cadence upside
        "derisk_best":             (dates, mats, derisk_size(best5[1]["base"], best5[1]["n_rungs"],
                                                             best5[1]["coast"]), {}),
    }
    combo = {}
    for name, spec in candidates.items():
        dts_, m_, fn_, kw_ = spec
        s_ = starts if dts_ is dates else monthly_starts(dts_)
        st = summarize(dts_, m_, fn_, s_, **kw_)
        py = per_year_median(dts_, m_, fn_, s_, **kw_)
        pym = {y: v["median"] for y, v in py.items()}
        combo[name] = dict(e_paid_mean=st["e_paid_mean"], e_paid_median=st["e_paid_median"],
                           zero_pct=st["zero_pct"], bust_pct=st["bust_pct"],
                           closed_max_pct=st["closed_max_pct"], mean_life_months=st["mean_life_months"],
                           per_year_median=pym, robust_worst_year=min(pym.values()),
                           robust_gate_pass=(min(pym.values()) > 0))
    out["recommended_candidates"] = combo
    gate = {k: v for k, v in combo.items() if v["robust_gate_pass"]}
    winner = sorted(gate.items(), key=lambda kv: (kv[1]["e_paid_median"], kv[1]["e_paid_mean"]),
                    reverse=True)[0]
    raw = sorted(combo.items(), key=lambda kv: (kv[1]["e_paid_median"], kv[1]["e_paid_mean"]),
                 reverse=True)[0]
    out["recommended_winner_robust"] = dict(name=winner[0], **winner[1])
    out["recommended_raw_medmax_rejected"] = dict(name=raw[0], **raw[1])
    print(f"\n[RECOMMENDED robust] {winner[0]}: median ${winner[1]['e_paid_median']} "
          f"mean ${winner[1]['e_paid_mean']} bust {winner[1]['bust_pct']}% PYmed {winner[1]['per_year_median']}",
          flush=True)
    print(f"[raw med-max REJECTED by gate] {raw[0]}: median ${raw[1]['e_paid_median']} "
          f"worst-year ${raw[1]['robust_worst_year']} (concentration)", flush=True)

    # ---- determinism ----
    md5 = hashlib.md5(json.dumps(out, sort_keys=True, default=str).encode()).hexdigest()
    out["meta"]["determinism_md5"] = md5
    dest = os.path.join(REPO, "reports", "passrate_opt", "05_funded_stage_optimization.json")
    with open(dest, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(f"\n[saved] {dest}  md5={md5}", flush=True)
    return out


if __name__ == "__main__":
    main()
