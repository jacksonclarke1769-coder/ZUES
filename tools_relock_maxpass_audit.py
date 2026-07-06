"""tools_relock_maxpass_audit.py — RE-LOCK cycle, MAX-PASS WATCH-ROW MINI-AUDIT.

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing (no live/config/engine file touched).
Pure execution of pinned formulas over PRIOR-ART machinery — no new modeling choices beyond the
explicit assumption notes below (each one called out, not hidden).

TASK: compare the two DEC-relock finalist rows already surfaced in
`reports/a_vpc_portfolio_optimisation/` (09_frontier_report.md / 07_top_cell_stress.md
config F02=S3 / F08=S5):
  WATCH    = A@900/6 + VPC@700/3  -> 39.3/19.6/41.1 pass/bust/exp, flip 0.076R
  BALANCED = A@900/6 + VPC@600/3  -> 37.4/18.0/44.6 pass/bust/exp, flip 0.068R
Both use the SAME A leg (budget 900, cap 6); they differ ONLY in the VPC leg's budget
(700 vs 600, same cap=3). Everything below is a mechanical audit of that one difference.

STREAMS (pinned exactly, reused not reimplemented):
  A   = `tools_sim_parity_check.load_rows()`, 2022+ window (`tools_salvage_vpc_reeval.a_rows_2022`).
        Canary: n=583, PF=1.3606000676571652 (VR.A_HONEST_N/A_HONEST_PF).
  VPC = the 1m-truth re-walked VPC stream (`tools_vpc_1m_truth.vpc_1m_truth_trades` +
        `.build_new_vpc_rows`). Canary: n=408, PF(pts)=1.318.
  Both loaded via `tools_opt_finalist_stress.load_a_stream()` / `.load_vpc_stream()` VERBATIM
  (same functions Wave 2 already used to produce the two pinned rows this audit reproduces) —
  this also inherits that file's TZ normalization EXACTLY (`_localize`: a naive VPC `ts` is treated
  AS ALREADY NY wall-clock, `tz_localize(NY)` directly, no UTC conversion — the convention three
  separate lanes in this repo already share; copied, not re-derived).

CANARY (mandatory, run first; STOP on >0.3pp miss on any of pass/bust/exp, either row): reproduce
BOTH pinned rows exactly from the pinned funnel — `tools_account_size_research.build_events` +
`.day_rows(STOP_PINNED=550, DLL_PINNED=1000)` (via `tools_salvage_vpc_reeval.ASR`/`STOP_PINNED`/
`DLL_PINNED`), `VR.run_cell` for eligible-start/(status,ndays,year) tuples.

NEW LOGIC (self-verified extension, not prior art — called out, not hidden):
  - Per-year E$: `pass_count_y * 8000 - eligible_starts_y * 131` (pinned verbatim per task spec;
    same $8k/$131 constants `tools_opt_sizing_grid.py`'s `e_dollar`/`FEE_PER_ATTEMPT` already use).
  - Ex-2025 aggregate: results are already year-tagged by `VR.run_cell` (day-level year of the
    START date); "excluding 2025" = filter that tag, no re-walk of the day sequence (mechanically
    identical to re-running the funnel restricted to those starts, since every start's outcome is
    independent of which OTHER starts are reported).
  - Worst-start-month: reuses `tools_opt_finalist_stress.start_month_breakdown` verbatim (buckets
    by literal "YYYY-MM" of the start date — the same convention that file's own 08 report already
    uses for `best_start_month`/`worst_start_month`; "calendar month" in the task brief is read as
    this existing convention, not a 12-bucket Jan-Dec pool, to stay consistent with prior art).
  - Stress slippage grid {0.02, 0.046, 0.068, 0.076}R: `tools_salvage_stress.dmg_slip` applied
    uniformly to both legs (same "family (a)" damage every stress lane in this repo already uses).
  - PAIRED bootstrap: both rows share the identical A leg and an (empirically verified below) IDENTICAL
    start-date sequence (VPC budget only changes per-trade contract count `q`, never which VPC trades
    are kept at cap=3 for either budget in this stream — verified: kept-trade counts equal, checked
    below), so outcomes are paired by START DATE (not by array position, to be robust to the
    unverified case) and resampled with the SAME random index draw per iteration (seed 42, n=1000) —
    this yields a genuine per-resample DIFFERENCE distribution, not two independent CIs.
  - VPC-budget-delta mechanics: `q = min(cap, floor(budget // risk_usd))` is deterministic, so the
    three risk_usd BANDS where q700 != q600 (cap=3 both) fall out of the floor-division algebra
    itself (not an invented bin): risk_usd in (200,233.33] (q 2->3), (300,350] (q 1->2), (600,700]
    (q 0->1, i.e. VPC trades ADDED entirely at 700 that don't exist in the 600 kept-set). Each band's
    trade count, risk_usd range, and aggregate raw R are reported; first-order $ delta from sizing
    alone = sum((q700-q600) * R * risk_usd) over the affected trades (does not re-walk day-level
    stop/DLL clamps — flagged, not hidden).

VERDICT (mechanical, per task spec) — WATCH row PROMOTABLE only if ALL FOUR legs hold:
  (1) ex-2025 pass_pct advantage (watch - balanced) >= +1.5pp
  (2) P(watch pass% > balanced pass%) in the paired bootstrap >= 0.80
  (3) no single year contributes >50% of the total POSITIVE per-year E$ advantage (same
      "concentration" mechanism `tools_opt_finalist_stress.one_regime_flag` already uses, applied to
      E$ instead of pass_pct per this task's own wording; N/A if total positive advantage <= 0 ->
      treated as satisfying the bar, nothing to concentrate)
  (4) stress margin (pass_pct - bust_pct) >= balanced's margin at EVERY one of the 4 tested slippage
      points
Otherwise WATCHLIST. Legs reported individually; verdict is the mechanical AND, no judgment.

FIREWALL: sha256 of `tools_salvage_stress.FIREWALL_FILES` (config_eval_locked.py,
config_funded_locked.py, config_defaults.py, auto_safety.py) taken before load and again right
before the report is written. Any mismatch -> STOP, no report written.

Outputs (new, this run only):
  reports/relock_dec_funded_rerun/06_max_pass_watch_row_audit.csv / .md

No recommendation language. No commits.
"""
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tools_salvage_vpc_reeval as VR          # A/VPC row loaders, ASR funnel, event_pf, run_cell, DPP
import tools_opt_finalist_stress as FS         # load_a_stream/load_vpc_stream (+ _localize TZ convention),
                                                # funnel, margin, start_month_breakdown, bootstrap_pass_pct
import tools_salvage_stress as ST              # FIREWALL_FILES, sha_of, dmg_slip

NY = "America/New_York"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "reports", "relock_dec_funded_rerun")
FIREWALL_FILES = ST.FIREWALL_FILES

WATCH = dict(a_budget=900, a_cap=6, v_budget=700, v_cap=3, label="WATCH A900/6+VPC700/3")
BALANCED = dict(a_budget=900, a_cap=6, v_budget=600, v_cap=3, label="BALANCED A900/6+VPC600/3")
CANARY_WATCH = dict(pass_pct=39.3, bust_pct=19.6, exp_pct=41.1)
CANARY_BALANCED = dict(pass_pct=37.4, bust_pct=18.0, exp_pct=44.6)
TOL_PP = 0.3

SLIP_GRID = [0.02, 0.046, 0.068, 0.076]
FEE_PER_ATTEMPT = 131.0
PASS_AMT = 8000.0
BOOT_N = 1000
BOOT_SEED = 42
YEARS = [2022, 2023, 2024, 2025, 2026]

# floor-division sizing bands where q@700 != q@600 (cap=3 both) — see module docstring
VPC_BUDGET_BANDS = [
    ("q 2->3", 200.0, 700.0 / 3.0, 2, 3),
    ("q 1->2", 300.0, 350.0, 1, 2),
    ("q 0->1 (added)", 600.0, 700.0, 0, 1),
]


# ==================================================================================================
# stream loading + row-level funnel
# ==================================================================================================
def load_streams():
    a_full, a2022, a_ok = FS.load_a_stream()
    v_rows, df1m, feats, d1rth, v_ok = FS.load_vpc_stream()
    ok = a_ok and v_ok
    print(f"A stream: n={len(a2022)} (2022+)  |  VPC stream: n={len(v_rows)} (1m-truth)  "
          f"-> stream canaries {'PASS' if ok else 'FAIL'}", flush=True)
    return a2022, v_rows, ok


def row_funnel(a2022, v_rows, cfg):
    s, pf, ev, days = FS.funnel(a2022, (cfg["a_budget"], cfg["a_cap"]),
                                v_rows, (cfg["v_budget"], cfg["v_cap"]), cfg["label"])
    starts, results = VR.run_cell(days)
    return dict(s=s, pf=pf, ev=ev, days=days, starts=starts, results=results)


def canary_check(cfg, s, expect):
    got = dict(pass_pct=s["pass_pct"], bust_pct=s["bust_pct"], exp_pct=s["exp_pct"])
    ok = all(abs(got[k] - expect[k]) <= TOL_PP for k in ("pass_pct", "bust_pct", "exp_pct"))
    print(f"CANARY [{cfg['label']}]: got {got} n={s['eligible_starts']} vs expected {expect} "
          f"-> {'PASS' if ok else 'FAIL'}", flush=True)
    return ok


# ==================================================================================================
# (1) per-year pass/bust/expire + E$
# ==================================================================================================
def per_year_e(results):
    rows = []
    for y in YEARS:
        yr = [r for r in results if r[2] == y]
        n = len(yr)
        if n == 0:
            rows.append(dict(year=y, n=0, pass_count=0, bust_count=0, exp_count=0,
                             pass_pct=None, bust_pct=None, exp_pct=None, e_dollar=None))
            continue
        p = sum(1 for r in yr if r[0] == "PASS")
        b = sum(1 for r in yr if r[0] == "BUST")
        x = sum(1 for r in yr if r[0] == "EXPIRE")
        e_dollar = p * PASS_AMT - n * FEE_PER_ATTEMPT
        rows.append(dict(year=y, n=n, pass_count=p, bust_count=b, exp_count=x,
                         pass_pct=round(100 * p / n, 1), bust_pct=round(100 * b / n, 1),
                         exp_pct=round(100 * x / n, 1), e_dollar=round(e_dollar, 0)))
    return rows


# ==================================================================================================
# (2) EXCLUDING-2025 aggregate
# ==================================================================================================
def ex2025_stats(results):
    sub = [r for r in results if r[2] != 2025]
    n = len(sub)
    if n == 0:
        return dict(n=0, pass_count=0, bust_count=0, exp_count=0, pass_pct=None, bust_pct=None, exp_pct=None)
    p = sum(1 for r in sub if r[0] == "PASS")
    b = sum(1 for r in sub if r[0] == "BUST")
    x = sum(1 for r in sub if r[0] == "EXPIRE")
    return dict(n=n, pass_count=p, bust_count=b, exp_count=x,
               pass_pct=round(100 * p / n, 1), bust_pct=round(100 * b / n, 1), exp_pct=round(100 * x / n, 1))


# ==================================================================================================
# (3) worst-start-month
# ==================================================================================================
def worst3_months(days, starts, results):
    _best, _worst, all_rows = FS.start_month_breakdown(days, starts, results)
    worst3 = all_rows[:3]     # start_month_breakdown already sorts ascending by pass_pct
    return worst3, {r["month"]: r for r in all_rows}


# ==================================================================================================
# (4) stress side-by-side
# ==================================================================================================
def stress_row(a2022, v_rows, cfg, slip):
    a_s = ST.dmg_slip(a2022, slip)
    v_s = ST.dmg_slip(v_rows, slip)
    s, _pf, _ev, _days = FS.funnel(a_s, (cfg["a_budget"], cfg["a_cap"]),
                                    v_s, (cfg["v_budget"], cfg["v_cap"]), f"{cfg['label']}-slip{slip}")
    m = FS.margin(s)
    return dict(slip=slip, pass_pct=s["pass_pct"], bust_pct=s["bust_pct"], margin=m)


# ==================================================================================================
# (5) paired bootstrap (watch minus balanced, per resample)
# ==================================================================================================
def outcome_by_date(days, starts, results):
    return {days[s][0]: (1 if r[0] == "PASS" else 0) for s, r in zip(starts, results)}


def paired_bootstrap(watch_res, bal_res):
    common = sorted(set(watch_res) & set(bal_res))
    n_common = len(common)
    n_watch, n_bal = len(watch_res), len(bal_res)
    w = np.array([watch_res[d] for d in common])
    b = np.array([bal_res[d] for d in common])
    n = len(common)
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, n, size=(BOOT_N, n))
    w_s = w[idx]; b_s = b[idx]
    pw = 100 * w_s.mean(axis=1)
    pb = 100 * b_s.mean(axis=1)
    diff = pw - pb
    p_watch_gt = float(np.mean(diff > 0))
    return dict(n_common=n_common, n_watch=n_watch, n_bal=n_bal,
               watch_p05=round(float(np.percentile(pw, 5)), 1), watch_p50=round(float(np.percentile(pw, 50)), 1),
               watch_p95=round(float(np.percentile(pw, 95)), 1),
               bal_p05=round(float(np.percentile(pb, 5)), 1), bal_p50=round(float(np.percentile(pb, 50)), 1),
               bal_p95=round(float(np.percentile(pb, 95)), 1),
               diff_p05=round(float(np.percentile(diff, 5)), 2), diff_p50=round(float(np.percentile(diff, 50)), 2),
               diff_p95=round(float(np.percentile(diff, 95)), 2), p_watch_gt_balanced=round(p_watch_gt, 3))


# ==================================================================================================
# (6) VPC-budget-delta mechanics (700 vs 600, cap 3 both)
# ==================================================================================================
def vpc_budget_delta(v_rows):
    bands = []
    for tag, lo, hi, q_lo, q_hi in VPC_BUDGET_BANDS:
        # risk_usd IS already in $ terms; band edges (lo, hi] are budget-dollar thresholds directly.
        band_rows = [r for r in v_rows if lo < r["risk_usd"] <= hi]
        n = len(band_rows)
        if n == 0:
            bands.append(dict(band=tag, risk_usd_lo=lo, risk_usd_hi=round(hi, 2), n=0,
                              stop_pts_min=None, stop_pts_max=None, agg_R=0.0, agg_dollar_delta=0.0))
            continue
        stop_pts = [r["risk_usd"] / VR.DPP for r in band_rows]
        agg_R = sum(r["R"] for r in band_rows)
        dq = q_hi - q_lo
        agg_dollar_delta = sum(dq * r["R"] * r["risk_usd"] for r in band_rows)
        bands.append(dict(band=tag, risk_usd_lo=lo, risk_usd_hi=round(hi, 2), n=n,
                          stop_pts_min=round(min(stop_pts), 2), stop_pts_max=round(max(stop_pts), 2),
                          agg_R=round(agg_R, 3), agg_dollar_delta=round(agg_dollar_delta, 2)))
    n_kept_600 = sum(1 for r in v_rows if r["risk_usd"] <= 600.0)
    n_kept_700 = sum(1 for r in v_rows if r["risk_usd"] <= 700.0)
    return bands, n_kept_600, n_kept_700


# ==================================================================================================
# verdict legs
# ==================================================================================================
def verdict_legs(ex2025_w, ex2025_b, py_w, py_b, boot, stress_w, stress_b):
    leg1_delta = None
    leg1 = False
    if ex2025_w["pass_pct"] is not None and ex2025_b["pass_pct"] is not None:
        leg1_delta = round(ex2025_w["pass_pct"] - ex2025_b["pass_pct"], 2)
        leg1 = leg1_delta >= 1.5

    leg2 = boot["p_watch_gt_balanced"] >= 0.80

    adv = {}
    for rw, rb in zip(py_w, py_b):
        if rw["e_dollar"] is None or rb["e_dollar"] is None:
            continue
        adv[rw["year"]] = rw["e_dollar"] - rb["e_dollar"]
    positive = {y: a for y, a in adv.items() if a > 0}
    total_pos = sum(positive.values())
    if total_pos <= 0:
        leg3 = True
        leg3_detail = "N/A — no positive aggregate E$ advantage to concentrate"
    else:
        worst_y = max(positive, key=positive.get)
        share = positive[worst_y] / total_pos
        leg3 = share <= 0.50
        leg3_detail = f"worst year={worst_y} share={round(share, 3)} of total positive advantage ${round(total_pos, 0)}"

    leg4 = all(sw["margin"] is not None and sb["margin"] is not None and sw["margin"] >= sb["margin"]
              for sw, sb in zip(stress_w, stress_b))

    overall = leg1 and leg2 and leg3 and leg4
    return dict(leg1_ex2025_advantage_ge_1_5pp=leg1, leg1_delta_pp=leg1_delta,
               leg2_p_watch_gt_balanced_ge_080=leg2, leg2_value=boot["p_watch_gt_balanced"],
               leg3_no_year_gt_50pct_of_e_advantage=leg3, leg3_detail=leg3_detail,
               leg4_stress_margin_ge_balanced_all_points=leg4,
               verdict="PROMOTABLE" if overall else "WATCHLIST")


# ==================================================================================================
# report
# ==================================================================================================
def write_report(canary_ok, s_w, s_b, py_w, py_b, ex2025_w, ex2025_b, worst_w, worst_b, allm_w, allm_b,
                 stress_w, stress_b, boot, bands, n_kept_600, n_kept_700, verdict, runtime_s,
                 firewall_before, firewall_after):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "06_max_pass_watch_row_audit.csv")
    md_path = os.path.join(OUTDIR, "06_max_pass_watch_row_audit.md")

    py_df = pd.DataFrame.from_records(
        [dict(row="WATCH", **r) for r in py_w] + [dict(row="BALANCED", **r) for r in py_b])
    py_df.to_csv(csv_path, index=False)

    lines = []
    lines.append("# 06 — Max-Pass Watch-Row Mini-Audit (RE-LOCK cycle)")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing. No recommendation "
                 "language, no commits — mechanical verdict legs only, per task spec.")
    lines.append("")
    lines.append(f"WATCH    = {WATCH['label']}  (pinned: {CANARY_WATCH})")
    lines.append(f"BALANCED = {BALANCED['label']}  (pinned: {CANARY_BALANCED})")
    lines.append("")
    lines.append("## Canary — reproduce both pinned rows exactly (tolerance 0.3pp)")
    lines.append("")
    lines.append(f"- WATCH:    got pass={s_w['s']['pass_pct']} bust={s_w['s']['bust_pct']} "
                 f"exp={s_w['s']['exp_pct']} n={s_w['s']['eligible_starts']} vs {CANARY_WATCH}")
    lines.append(f"- BALANCED: got pass={s_b['s']['pass_pct']} bust={s_b['s']['bust_pct']} "
                 f"exp={s_b['s']['exp_pct']} n={s_b['s']['eligible_starts']} vs {CANARY_BALANCED}")
    lines.append(f"- CANARY GATE: **{'PASS' if canary_ok else 'FAIL — STOPPED, rest of this report not trustworthy'}**")
    lines.append("")

    if not canary_ok:
        lines.append("**[ABORT] canary mismatch — no further sections computed.**")
        with open(md_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        print(f"\n[saved] {md_path}")
        return

    lines.append("## (1) Per-year pass/bust/expire + E$ (side-by-side)")
    lines.append("")
    lines.append("| row | year | n | pass_count | bust_count | exp_count | pass% | bust% | exp% | E$ |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for tag, rows in (("WATCH", py_w), ("BALANCED", py_b)):
        for r in rows:
            lines.append(f"| {tag} | {r['year']} | {r['n']} | {r['pass_count']} | {r['bust_count']} | "
                         f"{r['exp_count']} | {r['pass_pct']} | {r['bust_pct']} | {r['exp_pct']} | {r['e_dollar']} |")
    lines.append("")

    lines.append("## (2) EXCLUDING-2025 aggregate")
    lines.append("")
    lines.append(f"- WATCH ex-2025:    {ex2025_w}")
    lines.append(f"- BALANCED ex-2025: {ex2025_b}")
    adv = (None if ex2025_w["pass_pct"] is None or ex2025_b["pass_pct"] is None
          else round(ex2025_w["pass_pct"] - ex2025_b["pass_pct"], 2))
    lines.append(f"- watch advantage over balanced (ex-2025, pass pp): **{adv}**")
    lines.append("")

    lines.append("## (3) Worst-start-month analysis (3 worst months per row, by pass%)")
    lines.append("")
    lines.append("| row | month | n | pass% |")
    lines.append("| --- | --- | --- | --- |")
    for r in worst_w:
        lines.append(f"| WATCH | {r['month']} | {r['n']} | {r['pass_pct']} |")
    for r in worst_b:
        lines.append(f"| BALANCED | {r['month']} | {r['n']} | {r['pass_pct']} |")
    lines.append("")
    lines.append("Does the watch row's advantage survive in those months (watch pass% vs balanced "
                 "pass% in the SAME month, for every month appearing in either row's worst-3)?")
    lines.append("")
    lines.append("| month | watch_pass% | balanced_pass% | watch_minus_balanced |")
    lines.append("| --- | --- | --- | --- |")
    months_union = sorted({r["month"] for r in worst_w} | {r["month"] for r in worst_b})
    for m in months_union:
        wp = allm_w.get(m, {}).get("pass_pct")
        bp = allm_b.get(m, {}).get("pass_pct")
        d = None if wp is None or bp is None else round(wp - bp, 1)
        lines.append(f"| {m} | {wp} | {bp} | {d} |")
    lines.append("")

    lines.append("## (4) Stress side-by-side — slippage {0.02, 0.046, 0.068, 0.076}R")
    lines.append("")
    lines.append("| row | slip(R) | pass% | bust% | margin(pass-bust) |")
    lines.append("| --- | --- | --- | --- | --- |")
    for r in stress_w:
        lines.append(f"| WATCH | {r['slip']} | {r['pass_pct']} | {r['bust_pct']} | {r['margin']} |")
    for r in stress_b:
        lines.append(f"| BALANCED | {r['slip']} | {r['pass_pct']} | {r['bust_pct']} | {r['margin']} |")
    lines.append("")

    lines.append("## (5) Paired bootstrap (1000x, seed=42) — pass% 90% CI + watch-minus-balanced difference")
    lines.append("")
    lines.append(f"- common start-dates paired: {boot['n_common']} (watch eligible_starts={boot['n_watch']}, "
                 f"balanced eligible_starts={boot['n_bal']})")
    lines.append(f"- WATCH pass% 90% CI:    [{boot['watch_p05']}, {boot['watch_p95']}]  (median {boot['watch_p50']})")
    lines.append(f"- BALANCED pass% 90% CI: [{boot['bal_p05']}, {boot['bal_p95']}]  (median {boot['bal_p50']})")
    lines.append(f"- DIFFERENCE (watch - balanced) 90% CI: [{boot['diff_p05']}, {boot['diff_p95']}]  "
                 f"(median {boot['diff_p50']})")
    lines.append(f"- P(watch pass% > balanced pass%) per resample: **{boot['p_watch_gt_balanced']}**")
    lines.append("")

    lines.append("## (6) VPC-budget delta mechanics (700 vs 600, cap=3 both) — what changes mechanically")
    lines.append("")
    lines.append(f"- VPC trades kept at budget<=600: n={n_kept_600}; at budget<=700: n={n_kept_700} "
                 "(kept-set membership; q<1 dropped)")
    lines.append("")
    lines.append("| band (q@600 -> q@700) | risk_usd range | n trades | stop_pts range | agg raw R | "
                 "agg $ delta from sizing alone (first-order) |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for b in bands:
        lines.append(f"| {b['band']} | ({b['risk_usd_lo']}, {b['risk_usd_hi']}] | {b['n']} | "
                     f"{b['stop_pts_min']}-{b['stop_pts_max']} | {b['agg_R']} | {b['agg_dollar_delta']} |")
    lines.append("")
    lines.append("(first-order $ delta = sum((q@700 - q@600) * R * risk_usd) over the affected trades; "
                 "does not re-walk day-level $550 stop / $1,000 DLL clamps — flagged, not hidden.)")
    lines.append("")

    lines.append("## VERDICT (mechanical, auditor adjudicates)")
    lines.append("")
    lines.append(f"- leg1 (ex-2025 pass advantage >= +1.5pp): **{verdict['leg1_ex2025_advantage_ge_1_5pp']}** "
                 f"(delta={verdict['leg1_delta_pp']}pp)")
    lines.append(f"- leg2 (P(watch>balanced) >= 0.80): **{verdict['leg2_p_watch_gt_balanced_ge_080']}** "
                 f"(value={verdict['leg2_value']})")
    lines.append(f"- leg3 (no single year >50% of E$ advantage): **{verdict['leg3_no_year_gt_50pct_of_e_advantage']}** "
                 f"({verdict['leg3_detail']})")
    lines.append(f"- leg4 (stress margin >= balanced at every tested point): "
                 f"**{verdict['leg4_stress_margin_ge_balanced_all_points']}**")
    lines.append("")
    lines.append(f"## VERDICT: **{verdict['verdict']}**")
    lines.append("")

    lines.append("## Firewall before/after")
    lines.append("")
    for fn in FIREWALL_FILES:
        b_, a_ = firewall_before.get(fn), firewall_after.get(fn)
        lines.append(f"- `{fn}`: {'UNCHANGED' if b_ == a_ else '**CHANGED**'}")
    lines.append("")
    lines.append(f"Runtime: {runtime_s:.1f}s")

    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[saved] {csv_path}\n[saved] {md_path}")


# ==================================================================================================
def main():
    t_start = time.time()
    firewall_before = ST.sha_of(FIREWALL_FILES)
    print(f"firewall before: {firewall_before}", flush=True)

    a2022, v_rows, streams_ok = load_streams()
    if not streams_ok:
        print("[ABORT] stream canary mismatch — no report written.")
        return

    s_w = row_funnel(a2022, v_rows, WATCH)
    s_b = row_funnel(a2022, v_rows, BALANCED)
    canary_w = canary_check(WATCH, s_w["s"], CANARY_WATCH)
    canary_b = canary_check(BALANCED, s_b["s"], CANARY_BALANCED)
    canary_ok = canary_w and canary_b
    print(f"CANARY GATE: {'PASS' if canary_ok else 'FAIL — STOP'}", flush=True)

    if not canary_ok:
        firewall_after = ST.sha_of(FIREWALL_FILES)
        write_report(False, s_w, s_b, None, None, None, None, None, None, None, None,
                    None, None, None, None, None, None, None, time.time() - t_start,
                    firewall_before, firewall_after)
        return

    print("\n(1) per-year + E$ …", flush=True)
    py_w = per_year_e(s_w["results"])
    py_b = per_year_e(s_b["results"])

    print("(2) ex-2025 aggregate …", flush=True)
    ex2025_w = ex2025_stats(s_w["results"])
    ex2025_b = ex2025_stats(s_b["results"])

    print("(3) worst-start-month …", flush=True)
    worst_w, allm_w = worst3_months(s_w["days"], s_w["starts"], s_w["results"])
    worst_b, allm_b = worst3_months(s_b["days"], s_b["starts"], s_b["results"])

    print("(4) stress side-by-side …", flush=True)
    stress_w = [stress_row(a2022, v_rows, WATCH, s) for s in SLIP_GRID]
    stress_b = [stress_row(a2022, v_rows, BALANCED, s) for s in SLIP_GRID]

    print("(5) paired bootstrap …", flush=True)
    w_by_date = outcome_by_date(s_w["days"], s_w["starts"], s_w["results"])
    b_by_date = outcome_by_date(s_b["days"], s_b["starts"], s_b["results"])
    boot = paired_bootstrap(w_by_date, b_by_date)

    print("(6) VPC-budget delta mechanics …", flush=True)
    bands, n_kept_600, n_kept_700 = vpc_budget_delta(v_rows)

    verdict = verdict_legs(ex2025_w, ex2025_b, py_w, py_b, boot, stress_w, stress_b)
    print(f"\nVERDICT LEGS: {verdict}", flush=True)

    firewall_after = ST.sha_of(FIREWALL_FILES)
    firewall_ok = all(firewall_before[fn] == firewall_after[fn] for fn in FIREWALL_FILES)
    if not firewall_ok:
        print("[FIREWALL FAILURE] a firewalled file changed during this run — STOPPING, no report written.")
        for fn in FIREWALL_FILES:
            print(f"  {fn}: {'UNCHANGED' if firewall_before[fn] == firewall_after[fn] else 'CHANGED'}")
        return

    runtime_s = time.time() - t_start
    write_report(True, s_w, s_b, py_w, py_b, ex2025_w, ex2025_b, worst_w, worst_b, allm_w, allm_b,
                stress_w, stress_b, boot, bands, n_kept_600, n_kept_700, verdict, runtime_s,
                firewall_before, firewall_after)

    print(f"\nTOTAL runtime: {runtime_s:.1f}s")
    print(f"Firewall match: {firewall_ok}")
    print(f"VERDICT: {verdict['verdict']}")


if __name__ == "__main__":
    main()
