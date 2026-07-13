"""RULE-OUT-2023 / MAX-PROFIT — Apex 50K funded, VPC edge FROZEN (honest sim, 2026-07-13).

QUESTION (operator): "exclude 2023 and maximize funded profit." Is that REAL (a detectable,
avoidable regime) or a FAIR-WEATHER BET (a wager that 2023 won't recur)? Three parts, in order:
  1. DIAGNOSE 2023  — day-level P&L / drawdown / follow-through vs 2022/24/25.
  2. DETECTABILITY  — a CAUSAL equity-curve / vol stand-down that shrinks-or-halts VPC when the
                      strategy is bleeding. REAL iff: (a) causal, (b) cuts 2023 damage, (c) keeps
                      most 2022/24/25 profit, (d) ONE simple rule (not 5 params dodging one event).
  3. MAX PROFIT ex-2023 — funded sizing maximizing $/slot-month over {2022,2024,2025}, and — never
                      hidden — what that EXACT sizing does IN 2023 (median, bust%, wipe).

RESEARCH / SIM ONLY. READ-ONLY on bot strategy code (imports only). Writes confined to
research/passrate_opt/ + reports/passrate_opt/. NOTHING ARMED. LIVE HOLD in force.

REUSES CERTIFIED MACHINERY BY IMPORT, re-models NOTHING:
  * funded_stage_opt (G)  -> build_vpc, days_for, run_pa_diag, cushion_size, fixed_size, monthly_starts
                              (report-05 certified funded engine; imports F=honest_eval_engines + H).
  * funded_throughput_opt (T) -> metrics(), COST_PER_FUNDED, build_fast_matrix, FAST_LEVELS, ACCOUNT_CAP.
Payout RULES unchanged. The stand-down is applied ONLY through size_fn + an added zero-P&L "HALT"
level in the mats dict; run_pa_diag itself is untouched (it just reads mats[lvl][i]).

The stand-down SIGNAL is the strategy's equity curve at a FIXED 1-contract reference size — exogenous
to the account's dynamic sizing, identical across all accounts, and read only through day i-1. Hence
fully CAUSAL and a single rule (K, threshold).

ABSOLUTE HONESTY: every Apex 50K rule is help-center-derived, UNVERIFIED vs a live contract. Single-year
regime filters risk overfitting ONE event (2023) — the filter is held to sane behaviour in ALL years.
"""
import os, sys, json, hashlib, warnings, collections
warnings.filterwarnings("ignore")
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import funded_stage_opt as G
import funded_throughput_opt as T

GOOD_YEARS = (2022, 2024, 2025)
BAD_YEAR = 2023


# =================================================================================================
def day_level_diag(vpc):
    """Part 1: characterize each calendar year at the 1ct reference AND the cap-2 funded reference."""
    out = {}
    for tag, (bud, cap) in {"ref_1ct": (400, 1), "funded_cap2": (400, 2)}.items():
        d = G.days_for(vpc, bud, cap)
        yr = collections.defaultdict(list)
        for dt, real, trough in d:
            yr[dt.year].append((dt, real, trough))
        peryr = {}
        for y in sorted(yr):
            rows = yr[y]
            a = np.array([r[1] for r in rows]); tr = np.array([r[2] for r in rows])
            eq = np.cumsum(a); peak = np.maximum.accumulate(eq); dd = eq - peak
            wins = a[a > 0]; losses = a[a <= 0]
            # longest consecutive-drawdown run length (days below trailing peak)
            below = dd < 0; run = mx = 0
            for b in below:
                run = run + 1 if b else 0; mx = max(mx, run)
            # worst rolling 20-day P&L window (the sustained-bleed metric)
            k = 20; roll = [a[i:i + k].sum() for i in range(0, max(1, len(a) - k + 1))]
            peryr[y] = dict(
                n_days=len(a), sum_pnl=round(float(a.sum())), mean_day=round(float(a.mean()), 1),
                win_rate=round(100 * float((a > 0).mean()), 1),
                avg_win=round(float(wins.mean())) if len(wins) else 0,
                avg_loss=round(float(losses.mean())) if len(losses) else 0,
                gl_ratio=round(float(-wins.mean() / losses.mean()), 2) if len(losses) and losses.mean() else None,
                max_intrayr_dd=round(float(dd.min())), longest_dd_run_days=int(mx),
                worst_20d_window=round(float(min(roll))), worst_trough_day=round(float(tr.min())),
            )
        # monthly matrix (funded_cap2 only, to expose the bleed cluster)
        monthly = None
        if tag == "funded_cap2":
            mo = collections.defaultdict(float)
            for dt, real, trough in d:
                mo[(dt.year, dt.month)] += real
            monthly = {f"{y}-{m:02d}": round(v) for (y, m), v in sorted(mo.items())}
        out[tag] = dict(per_year=peryr, monthly=monthly, trail_threshold=G.TRAIL,
                        note=("max_intrayr_dd vs the $%d trailing threshold is the wipe test; "
                              "worst_20d_window measures the sustained-bleed depth" % G.TRAIL))
    return out


# =================================================================================================
def ref_equity_signal(vpc, ref_budget=400, ref_cap=1):
    """Causal stand-down SIGNAL from the strategy's own 1ct equity curve (exogenous to account sizing).
    Returns (dates, pnl_1ct[]) aligned to the level matrix dates."""
    d = G.days_for(vpc, ref_budget, ref_cap)
    dates = [x[0] for x in d]
    pnl = np.array([x[1] for x in d], float)
    return dates, pnl


def standdown_flags(pnl, K, thresh, mode="trailK"):
    """Causal boolean stand-down flag per day i, using ONLY days < i (strictly causal).
    mode 'trailK'    : trailing K-day realized P&L (ending i-1) < thresh  -> stand down.
    mode 'drawdown'  : equity drawdown from trailing peak (through i-1) < thresh (thresh<0) -> stand down.
    """
    n = len(pnl); flags = np.zeros(n, bool)
    cum = np.concatenate([[0.0], np.cumsum(pnl)])   # cum[j] = sum(pnl[:j]); prefix, causal
    for i in range(n):
        if i < 2:
            continue
        if mode == "trailK":
            j0 = max(0, i - K)
            val = cum[i] - cum[j0]                    # sum(pnl[j0:i]) = strictly days < i
            flags[i] = val < thresh
        else:  # drawdown: peak of cum[:i+1] up to index i (=through day i-1 realized) minus current
            peak = cum[:i + 1].max()
            flags[i] = (cum[i] - peak) < thresh
    return flags


def standdown_size(base_fn, flags, halt_level="HALT"):
    """Wrap a base size_fn: when the causal stand-down flag fires for day i, return halt_level
    (a zero-P&L day) or a shrink level; else the base sizing decision."""
    def fn(bal, thr, li, locked, i):
        if flags[i]:
            return halt_level
        return base_fn(bal, thr, li, locked, i)
    return fn


# =================================================================================================
def subset_by_year(dates, starts, res, years):
    """Filter (starts,res) to those whose START-YEAR is in `years`."""
    keep = [(s, r) for s, r in zip(starts, res) if dates[s].year in years]
    if not keep:
        return [], []
    ss, rr = zip(*keep)
    return list(ss), list(rr)


def year_metrics(dates, starts, res, years):
    ss, rr = subset_by_year(dates, starts, res, years)
    if not ss:
        return None
    return T.metrics(dates, ss, rr)


def net_slot_years(dates, starts, res, years):
    """net_slot (E[paid]/E[life] - cost/E[life]) computed over the given start-year subset."""
    m = year_metrics(dates, starts, res, years)
    return m["net_slot"] if m else None


# =================================================================================================
def main():
    print("building VPC (reused G machinery)…", flush=True)
    vpc = G.build_vpc()

    out = dict(meta=dict(generated="2026-07-13",
                         account_cap=T.ACCOUNT_CAP, cost_per_funded=round(T.COST_PER_FUNDED, 1),
                         good_years=list(GOOD_YEARS), bad_year=BAD_YEAR,
                         metric=("net_slot=E[paid]/E[life]-cost/E[life]; per-year by START-year; "
                                 "stand-down signal = causal trailing-K 1ct strategy equity"),
                         confidence="ALL Apex 50K rules help-center-derived, UNVERIFIED vs live contract"))

    # ---- PART 1: DIAGNOSE 2023 ----
    out["part1_diagnosis"] = day_level_diag(vpc)
    d23 = out["part1_diagnosis"]["funded_cap2"]["per_year"][BAD_YEAR]
    print(f"[P1] 2023 cap2: sum${d23['sum_pnl']} maxDD${d23['max_intrayr_dd']} (vs trail ${G.TRAIL}) "
          f"worst20d${d23['worst_20d_window']} gl{d23['gl_ratio']} win{d23['win_rate']}%", flush=True)

    # ---- shared matrices ----
    fdates, fmats, fstarts = T.build_fast_matrix(vpc)            # c1..c8 fast levels + aligned starts
    fmats = dict(fmats); fmats["HALT"] = [(0.0, 0.0)] * len(fdates)   # zero-P&L stand-down day
    sig_dates, sig_pnl = ref_equity_signal(vpc)
    assert sig_dates == fdates, "signal/matrix date misalign"

    # CANARY: reproduce report-07 bracket A (cushion-brake cap<=3) + bracket B ($400/cap2 fast) ----
    #   built on the report-05 LEVELS matrix (same as report-07 canary) for bit-parity.
    bdates, bmats = G.build_level_matrix(vpc); bstarts = G.monthly_starts(bdates)
    resA = [G.run_pa_diag(bdates, bmats, s, G.cushion_size([(0, "XS"), (2500, "S"), (5000, "M")])) for s in bstarts]
    resB = [G.run_pa_diag(bdates, bmats, s, G.fixed_size("S")) for s in bstarts]
    mA, mB = T.metrics(bdates, bstarts, resA), T.metrics(bdates, bstarts, resB)
    out["canary"] = dict(
        bracket_A_cushion_brake=dict(net_slot=mA["net_slot"], fleet=mA["fleet_net_mo"], bust=mA["bust_pct"],
                                     per_year_median=mA["per_year_median"], target="net $84.1 fleet $1683"),
        bracket_B_400cap2=dict(net_slot=mB["net_slot"], fleet=mB["fleet_net_mo"], bust=mB["bust_pct"],
                               per_year_median=mB["per_year_median"], target="net $164.9 fleet $3298 2023=$0"))
    print(f"[CANARY] A net ${mA['net_slot']} fleet ${mA['fleet_net_mo']} (t $84.1/$1683) | "
          f"B net ${mB['net_slot']} fleet ${mB['fleet_net_mo']} 2023med ${mB['per_year_median'].get(2023)} "
          f"(t $164.9/$3298/$0)", flush=True)

    # base (unfiltered) fast configs to attack: the $0-in-2023 traps ----
    base_configs = {
        "c2_static":  G.fixed_size("c2"),                                   # $400/cap2 fast (bracket B-like)
        "c3_static":  G.fixed_size("c3"),
        "band_cap4":  G.cushion_size([(0, "c1"), (2000, "c2"), (4000, "c3"), (6500, "c4")]),
        "band_cap2_brake": G.cushion_size([(0, "c1"), (3000, "c2")]),       # report-07 WINNER (survivor)
    }
    def eval_fn(fn):
        res = [G.run_pa_diag(fdates, fmats, s, fn) for s in fstarts]
        m = T.metrics(fdates, fstarts, res)
        pyn = {y: net_slot_years(fdates, fstarts, res, (y,)) for y in sorted(set(fdates[s].year for s in fstarts))}
        return res, m, pyn

    out["part2_baselines"] = {}
    base_res = {}
    for name, fn in base_configs.items():
        res, m, pyn = eval_fn(fn)
        base_res[name] = res
        out["part2_baselines"][name] = dict(
            net_slot=m["net_slot"], fleet=m["fleet_net_mo"], bust=m["bust_pct"],
            per_year_median=m["per_year_median"], per_year_netslot=pyn,
            net_good=net_slot_years(fdates, fstarts, res, GOOD_YEARS),
            net_2023=net_slot_years(fdates, fstarts, res, (2023,)),
            med_2023=(year_metrics(fdates, fstarts, res, (2023,)) or {}).get("e_paid_median"))
        print(f"[P2 base {name:16}] net ${m['net_slot']:>6} 2023med ${m['per_year_median'].get(2023):>5} "
              f"bust {m['bust_pct']}%", flush=True)

    # ---- PART 2: DETECTABILITY — causal equity-curve stand-down FILTER ----
    #   ONE rule: trailing-K 1ct strategy P&L < threshold -> HALT that day (also test shrink-to-c1).
    #   Small, principled grid (NOT fit to dodge 2023): K in {10,20,30}, thresh scaled to the edge.
    filt = {}
    for K in (10, 20, 30):
        for thresh in (0.0, -300.0, -600.0):
            flags = standdown_flags(sig_pnl, K, thresh, mode="trailK")
            dd_pct = round(100 * float(flags.mean()), 1)
            for tgt in ("c2_static", "band_cap2_brake"):
                fn = standdown_size(base_configs[tgt], flags, halt_level="HALT")
                res, m, pyn = eval_fn(fn)
                key = f"trailK{K}_thr{int(thresh)}_on_{tgt}"
                filt[key] = dict(K=K, thresh=thresh, target=tgt, halt_days_pct=dd_pct,
                                 net_slot=m["net_slot"], fleet=m["fleet_net_mo"], bust=m["bust_pct"],
                                 per_year_median=m["per_year_median"], per_year_netslot=pyn,
                                 net_good=net_slot_years(fdates, fstarts, res, GOOD_YEARS),
                                 net_2023=net_slot_years(fdates, fstarts, res, (2023,)),
                                 med_2023=(year_metrics(fdates, fstarts, res, (2023,)) or {}).get("e_paid_median"))
    # drawdown-mode variant (single sane setting) as robustness
    for thr in (-1500.0, -2500.0):
        flags = standdown_flags(sig_pnl, 0, thr, mode="drawdown")
        for tgt in ("c2_static",):
            fn = standdown_size(base_configs[tgt], flags, halt_level="HALT")
            res, m, pyn = eval_fn(fn)
            key = f"dd_thr{int(thr)}_on_{tgt}"
            filt[key] = dict(mode="drawdown", thresh=thr, target=tgt,
                             halt_days_pct=round(100 * float(flags.mean()), 1),
                             net_slot=m["net_slot"], fleet=m["fleet_net_mo"], bust=m["bust_pct"],
                             per_year_median=m["per_year_median"], per_year_netslot=pyn,
                             net_good=net_slot_years(fdates, fstarts, res, GOOD_YEARS),
                             net_2023=net_slot_years(fdates, fstarts, res, (2023,)),
                             med_2023=(year_metrics(fdates, fstarts, res, (2023,)) or {}).get("e_paid_median"))
    # shrink-to-c1 variant (de-risk not halt) on the best-looking K
    flags = standdown_flags(sig_pnl, 20, -300.0, mode="trailK")
    fn = standdown_size(base_configs["c2_static"], flags, halt_level="c1")
    res, m, pyn = eval_fn(fn)
    filt["trailK20_thr-300_SHRINKc1_on_c2_static"] = dict(
        K=20, thresh=-300.0, target="c2_static", halt_mode="shrink_c1",
        halt_days_pct=round(100 * float(flags.mean()), 1),
        net_slot=m["net_slot"], fleet=m["fleet_net_mo"], bust=m["bust_pct"],
        per_year_median=m["per_year_median"], per_year_netslot=pyn,
        net_good=net_slot_years(fdates, fstarts, res, GOOD_YEARS),
        net_2023=net_slot_years(fdates, fstarts, res, (2023,)),
        med_2023=(year_metrics(fdates, fstarts, res, (2023,)) or {}).get("e_paid_median"))
    out["part2_filter_grid"] = filt

    # verdict on the filter: does ANY causal filter turn a $0-2023 trap into 2023>0 while keeping
    #   >=70% of good-year net_slot? (REAL). Compare each filter vs its unfiltered base.
    filt_verdict = []
    for key, r in filt.items():
        tgt = r["target"]; b = out["part2_baselines"][tgt]
        keep_good = (r["net_good"] / b["net_good"]) if b["net_good"] else None
        fixes_2023 = (b["per_year_median"].get(2023, 0) == 0) and (r["per_year_median"].get(2023, 0) > 0)
        filt_verdict.append(dict(key=key, base=tgt, base_2023med=b["per_year_median"].get(2023),
                                 filt_2023med=r["per_year_median"].get(2023),
                                 base_net_good=b["net_good"], filt_net_good=r["net_good"],
                                 keep_good_frac=round(keep_good, 3) if keep_good is not None else None,
                                 fixes_2023=fixes_2023,
                                 REAL=(fixes_2023 and keep_good is not None and keep_good >= 0.70)))
    out["part2_filter_verdict"] = sorted(filt_verdict, key=lambda x: (-(x["keep_good_frac"] or 0)))
    n_real = sum(1 for v in filt_verdict if v["REAL"])
    print(f"[P2] filters that FIX 2023 AND keep >=70% good-year net: {n_real}/{len(filt_verdict)}", flush=True)

    # ---- PART 3: MAX PROFIT ex-2023 (over {2022,2024,2025}) + its TRUE 2023 cost ----
    #   static budget/cap sweep AND dynamic bands; rank by net_slot over GOOD_YEARS only.
    cands = []
    for b in T.STATIC_BUDGETS:
        for c in T.STATIC_CAPS:
            dts, st, res = T.run_static(vpc, b, c)
            ng = net_slot_years(dts, st, res, GOOD_YEARS)
            m23 = year_metrics(dts, st, res, (2023,))
            mall = T.metrics(dts, st, res)
            cands.append(dict(kind="static", label=f"{b}/cap{c}", net_good=ng,
                              fleet_good=round(T.ACCOUNT_CAP * ng) if ng else None,
                              net_all=mall["net_slot"], med_2023=m23["e_paid_median"] if m23 else None,
                              bust_2023=m23["bust_pct"] if m23 else None,
                              zero_2023=m23["zero_pct"] if m23 else None,
                              per_year_median=mall["per_year_median"]))
    for name, fn in base_configs.items():
        res = [G.run_pa_diag(fdates, fmats, s, fn) for s in fstarts]
        ng = net_slot_years(fdates, fstarts, res, GOOD_YEARS)
        m23 = year_metrics(fdates, fstarts, res, (2023,)); mall = T.metrics(fdates, fstarts, res)
        cands.append(dict(kind="dynamic", label=name, net_good=ng,
                          fleet_good=round(T.ACCOUNT_CAP * ng) if ng else None, net_all=mall["net_slot"],
                          med_2023=m23["e_paid_median"] if m23 else None,
                          bust_2023=m23["bust_pct"] if m23 else None,
                          zero_2023=m23["zero_pct"] if m23 else None,
                          per_year_median=mall["per_year_median"]))
    cands = [c for c in cands if c["net_good"] is not None]
    cands.sort(key=lambda x: x["net_good"], reverse=True)
    out["part3_maxprofit_ex2023"] = cands
    top = cands[0]
    out["part3_top"] = top
    print(f"\n[P3] MAX ex-2023: {top['kind']} {top['label']} net_good ${top['net_good']} "
          f"fleet ${top['fleet_good']} | BUT 2023: med ${top['med_2023']} bust {top['bust_2023']}% "
          f"zero {top['zero_2023']}%", flush=True)

    # ---- determinism ----
    md5 = hashlib.md5(json.dumps(out, sort_keys=True, default=str).encode()).hexdigest()
    out["meta"]["determinism_md5"] = md5
    dest = os.path.join(REPO, "reports", "passrate_opt", "09_rule_out_2023_maxprofit.json")
    with open(dest, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(f"\n[saved] {dest}  md5={md5}", flush=True)
    return out


if __name__ == "__main__":
    main()
