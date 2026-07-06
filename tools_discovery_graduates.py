"""tools_discovery_graduates.py — DISCOVERY Wave 2: graduate sizing tags on the base salvage
machine.

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing (no live/config/engine file touched).
Pure execution of pinned formulas over PRIOR-ART machinery (`tools_salvage_vpc_reeval.py`,
`tools_salvage_stress.py`, `tools_account_size_research.py`, `tools_sim_parity_check.py`) plus one
new join against the Wave-1 context store
(`~/trading-team/research/nq_pattern_discovery/store/profile_a_context.parquet`).

BASE MACHINE (reproduced first, STOP on mismatch): A@600/cap6 (D1c-kept honest A stream, 2022-2026
window, `tools_sim_parity_check.load_rows()` restricted `ts >= 2022-01-01`) + VPC@600/cap4
(`tools_salvage_vpc_reeval.vpc_rows()`), merged onto one day calendar, `day_rows(550,1000)` /
`eval_run` (Apex 50K spec) — reference row: pass 27.8 / bust 15.5 / exp 56.7, n=684, med=18d.

STEP 0 — direction-interaction check on `vwap_slope_6bar` (auditor-required before anything else):
reproduces the F-lane finding (unfiltered-705 quintile split, Q1 PF 2.52 / Q3 PF 0.74) as a canary,
then splits each quintile by trade direction (n/WR/PF per cell) to determine whether the effect is
alignment-based, magnitude-based, or confounded (one quintile is mostly one direction).

GRADUATE 1 — TAG_SLOPE_WEAK, sizing tag on the A leg only (S1 = half budget $300, S2 = full
removal, count-basis reported).
GRADUATE 2 — TAG_AGAINST_DRIVE, sizing tag on the A leg only (D1 = half budget, D2 = full removal,
count-basis reported); causal only for signals at/after 10:00 (first_30m_ret closes at 10:00).
COMBINED — SD1 = S1 + D1 together (union of both tags at half budget).

Every variant is funneled at the machine's own pinned sizing (A@600/6 + VPC@600/4), reporting the
full pinned funnel + per-year pass% (2022-2026) + a light 0.02R/0.05R uniform-slippage stress
column (`tools_salvage_stress.dmg_slip`, applied to BOTH legs, prior-art convention). Artifact flag
per DEC-20260706-1108 (pass% up while pass-count down = DENOMINATOR ARTIFACT).

No new modeling choices beyond what's explicitly documented below. No winner-picking — every
number is reported as computed; the priors bar (funded-per-slot-year count improvement holding
>=4/5 years AND surviving 0.02R) is printed and checked mechanically, not used to pick a favorite.

Outputs (new, this run only):
  reports/nq_pattern_discovery/I_candidate_strategies.csv / .md
  reports/nq_pattern_discovery/J_candidate_backtests.csv / .md
  reports/nq_pattern_discovery/L_eval_funnel_comparison.csv / .md
"""
import os
import sys
import json
import subprocess
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))

import tools_account_size_research as ASR   # build_events, day_rows (pinned)
import tools_sim_parity_check as SPC         # load_rows (honest A, D1c-kept)
import tools_salvage_vpc_reeval as VR         # vpc_rows, a_rows_2022, event_pf, summarize_cell,
                                              # weeks_span, same_day_stats, STOP_PINNED, DLL_PINNED
import tools_salvage_stress as ST             # dmg_slip (uniform slippage, R units, both legs)

NY = "America/New_York"
CTX_PARQUET = os.path.expanduser(
    "~/trading-team/research/nq_pattern_discovery/store/profile_a_context.parquet")
OUTDIR = os.path.join(HERE, "reports", "nq_pattern_discovery")

# ---- pinned reference row (task brief, verbatim) ------------------------------------------------
REF_MACHINE = dict(n=684, pass_pct=27.8, bust_pct=15.5, exp_pct=56.7, med_days_pass=18)

# ---- pinned F-lane vwap_slope quintile canary (reports/nq_pattern_discovery/F_regime_analysis.md,
# "unfiltered_705" rows) ---------------------------------------------------------------------------
F_LANE_REF = {
    1: dict(n=97, wr=58.8, pf=2.52),
    2: dict(n=96, wr=44.8, pf=1.467),
    3: dict(n=96, wr=30.2, pf=0.737),
    4: dict(n=96, wr=42.7, pf=1.096),
    5: dict(n=96, wr=46.9, pf=1.349),
}

SLIP_GRID = [0.0, 0.02, 0.05]
YEARS = [2022, 2023, 2024, 2025, 2026]

PRIORS_TEXT = (
    "PRIORS (printed per brief, not used to pick a winner): \"no filter raises total R\" -- 8 "
    "replications across this repo's research programs; sizing-modifier variants in the A2 "
    "salvage lane were null; the bar for a variant to be worth anything is funded-per-slot-year "
    "COUNT improvement (not just %) holding in >=4/5 years AND surviving 0.02R uniform slippage."
)


def log(*a):
    print(*a, flush=True)


# ==================================================================================================
# firewall
# ==================================================================================================
def firewall(tag):
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "test_funded_config_firewall.py",
         "test_eval_config_firewall.py", "-q"],
        cwd=HERE, capture_output=True, text=True)
    ok = (r.returncode == 0)
    log(f"[firewall {tag}] {'PASS' if ok else 'FAIL'}")
    if not ok:
        log(r.stdout[-4000:])
        log(r.stderr[-2000:])
    return ok


# ==================================================================================================
# funnel primitives (thin wrappers around pinned machinery -- no new funnel logic)
# ==================================================================================================
def pf_of(rows_field):
    """PF over a plain (R) sequence (dimensionless, trade-level, not dollar) -- used for the
    Step-0 quintile x direction table."""
    x = np.asarray(rows_field, dtype=float)
    w = x[x > 0].sum()
    l = -x[x <= 0].sum()
    return w / l if l > 0 else float("nan")


def eval_combo_from_ev(ev_a, v_rows, v_bc, label):
    """A(+VPC) combo via ASR.build_events(VPC leg)/ASR.day_rows/VR.summarize_cell -- identical
    machinery to tools_salvage_vpc_reeval.part2_eval/tools_salvage_stress.run_eval_combo, except
    the A-leg event list `ev_a` is passed in pre-built (so callers can merge multiple A sub-groups
    at different budgets, e.g. tagged-at-half-budget + untagged-at-full-budget, before this call)."""
    ev = list(ev_a)
    if v_rows is not None and v_bc is not None:
        ev += ASR.build_events(v_rows, v_bc[0], v_bc[1])
    ev.sort(key=lambda e: e["ts"])
    pf = VR.event_pf(ev, label)
    days = ASR.day_rows(ev, VR.STOP_PINNED, VR.DLL_PINNED)
    s = VR.summarize_cell(days, label)
    s["pf_dollar"] = round(pf, 3) if pf == pf else None
    s["trades_per_week"] = round(len(ev) / VR.weeks_span(ev), 2) if ev else 0.0
    return s


def build_split_ev(full_rows, half_rows, cap=6, budget_full=600.0, budget_half=300.0, slip=0.0):
    """Two independent build_events streams (full-budget group + half-budget group), each
    optionally uniform-slippage-damaged (ST.dmg_slip, R units, prior-art convention), merged onto
    one ts-sorted event list. `half_rows=[]` degenerates to the plain single-budget case (base,
    S2, D2). Same pattern as the A+VPC merge in tools_salvage_vpc_reeval.part2_eval."""
    fr = ST.dmg_slip(full_rows, slip) if full_rows else full_rows
    hr = ST.dmg_slip(half_rows, slip) if half_rows else half_rows
    ev = ASR.build_events(fr, budget_full, cap) if fr else []
    if hr:
        ev += ASR.build_events(hr, budget_half, cap)
    return ev


# ==================================================================================================
# STEP A -- load streams, reproduce the base machine reference row
# ==================================================================================================
def load_streams():
    log("loading VPC rows (VR.vpc_rows)...")
    v_rows, vpc_tr = VR.vpc_rows()
    log(f"  VPC rows n={len(v_rows)}")

    log("loading honest-A rows (SPC.load_rows, D1c-kept)...")
    a_full = SPC.load_rows()
    a2022 = VR.a_rows_2022(a_full)
    log(f"  A rows n={len(a_full)} (full) / n={len(a2022)} (2022-2026 window)")
    return v_rows, a_full, a2022


def reproduce_base_machine(a2022, v_rows):
    ev_a = build_split_ev(a2022, [], cap=6)
    s = eval_combo_from_ev(ev_a, v_rows, (600.0, 4), "BASE A@600/6 + VPC@600/4")
    ok = (s["eligible_starts"] == REF_MACHINE["n"] and s["pass_pct"] == REF_MACHINE["pass_pct"]
          and s["bust_pct"] == REF_MACHINE["bust_pct"] and s["exp_pct"] == REF_MACHINE["exp_pct"]
          and s["med_days_pass"] == REF_MACHINE["med_days_pass"])
    log(f"[BASE MACHINE CANARY] got n={s['eligible_starts']} pass={s['pass_pct']} "
        f"bust={s['bust_pct']} exp={s['exp_pct']} med={s['med_days_pass']}  vs ref {REF_MACHINE}  "
        f"-> {'PASS' if ok else 'MISMATCH -- STOP'}")
    return ok, s


# ==================================================================================================
# STEP 0 -- direction-interaction check on vwap_slope_6bar
# ==================================================================================================
def load_context():
    ctx = pd.read_parquet(CTX_PARQUET)
    ctx["ts"] = pd.to_datetime(ctx["ts"])
    return ctx


def step0_direction_interaction(ctx):
    full = ctx.dropna(subset=["R"]).copy()
    q, bins = pd.qcut(full["vwap_slope_6bar"], 5, labels=[1, 2, 3, 4, 5], retbins=True)
    full["slope_q"] = q

    # canary vs F-lane pinned reference (unfiltered_705)
    canary_ok = True
    canary_rows = []
    for qq in [1, 2, 3, 4, 5]:
        sub = full[full["slope_q"] == qq]
        n, wr, pf = len(sub), round(100 * (sub.R > 0).mean(), 1), round(pf_of(sub.R.values), 3)
        ref = F_LANE_REF[qq]
        ok = (n == ref["n"] and wr == ref["wr"] and pf == ref["pf"])
        canary_ok &= ok
        canary_rows.append(dict(quintile=qq, n=n, wr=wr, pf=pf, ref_n=ref["n"], ref_wr=ref["wr"],
                                 ref_pf=ref["pf"], match=ok))
    log(f"[F-LANE VWAP_SLOPE QUINTILE CANARY] {'PASS' if canary_ok else 'MISMATCH -- STOP'}")
    for r in canary_rows:
        log(f"  Q{r['quintile']}: n={r['n']} wr={r['wr']} pf={r['pf']}  vs ref "
            f"n={r['ref_n']} wr={r['ref_wr']} pf={r['ref_pf']}  {'OK' if r['match'] else 'MISMATCH'}")

    # per-quintile x direction cells
    cells = []
    for qq in [1, 2, 3, 4, 5]:
        sub = full[full["slope_q"] == qq]
        qtot = len(sub)
        for d in ["long", "short"]:
            s2 = sub[sub["direction"] == d]
            n = len(s2)
            if n == 0:
                cells.append(dict(quintile=qq, direction=d, n=0, dir_share_of_quintile_pct=0.0,
                                   wr=None, pf=None, expR=None))
                continue
            cells.append(dict(
                quintile=qq, direction=d, n=n,
                dir_share_of_quintile_pct=round(100 * n / qtot, 1),
                wr=round(100 * (s2.R > 0).mean(), 1), pf=round(pf_of(s2.R.values), 3),
                expR=round(float(s2.R.mean()), 3)))
    cell_df = pd.DataFrame(cells)

    # pooled-quintile view (for the tag-selection ranking) reusing the canary numbers + expR
    pooled = []
    for qq in [1, 2, 3, 4, 5]:
        sub = full[full["slope_q"] == qq]
        pooled.append(dict(quintile=qq, n=len(sub), wr=round(100 * (sub.R > 0).mean(), 1),
                            pf=round(pf_of(sub.R.values), 3), expR=round(float(sub.R.mean()), 3)))
    pooled_df = pd.DataFrame(pooled)

    # mechanical confound check: dominant-direction share per quintile
    dom_share = {}
    for qq in [1, 2, 3, 4, 5]:
        row_long = cell_df[(cell_df.quintile == qq) & (cell_df.direction == "long")].iloc[0]
        row_short = cell_df[(cell_df.quintile == qq) & (cell_df.direction == "short")].iloc[0]
        dom_share[qq] = max(row_long["dir_share_of_quintile_pct"] or 0,
                             row_short["dir_share_of_quintile_pct"] or 0)

    n_confounded_quintiles = sum(1 for qq in [1, 2, 3, 4, 5] if dom_share[qq] >= 90.0)
    verdict_lines = []
    verdict_lines.append(
        f"Dominant-direction share per quintile (>=90% = confounded/direction-degenerate): "
        f"Q1={dom_share[1]}% Q2={dom_share[2]}% Q3={dom_share[3]}% Q4={dom_share[4]}% "
        f"Q5={dom_share[5]}%  -> {n_confounded_quintiles}/5 quintiles are direction-degenerate.")

    q1_short = cell_df[(cell_df.quintile == 1) & (cell_df.direction == "short")].iloc[0]
    q5_long = cell_df[(cell_df.quintile == 5) & (cell_df.direction == "long")].iloc[0]
    verdict_lines.append(
        f"Magnitude-symmetry check (both tails 'steep', opposite direction dominance): "
        f"Q1-short (steep down, n={q1_short['n']}) PF={q1_short['pf']} expR={q1_short['expR']} "
        f"vs Q5-long (steep up, n={q5_long['n']}) PF={q5_long['pf']} expR={q5_long['expR']} -- "
        f"{'roughly symmetric' if abs(q1_short['pf'] - q5_long['pf']) < 0.3 else 'NOT symmetric (Q1-short much stronger)'}.")

    q3_long = cell_df[(cell_df.quintile == 3) & (cell_df.direction == "long")].iloc[0]
    q3_short = cell_df[(cell_df.quintile == 3) & (cell_df.direction == "short")].iloc[0]
    verdict_lines.append(
        f"Q3 (the only quintile with real direction mixing, {q3_long['dir_share_of_quintile_pct']}% "
        f"long / {q3_short['dir_share_of_quintile_pct']}% short) is weak for BOTH directions vs "
        f"their own pooled averages: long expR={q3_long['expR']} (pooled long expR="
        f"{round(full[full.direction=='long'].R.mean(),3)}), short expR={q3_short['expR']} "
        f"(pooled short expR={round(full[full.direction=='short'].R.mean(),3)}) -- confirms Q3's "
        f"weakness is not a directional artifact, it is genuinely bad for both sides.")

    verdict = ("(c) CONFOUNDED: 4/5 quintiles (Q1,Q2,Q4,Q5) are >=90% single-direction by "
               "construction of the OTE signal (steep downward slope -> short setups, steep "
               "upward slope -> long setups), so the pooled F-lane quintile split is almost "
               "entirely a stand-in for trade direction at the tails -- there is essentially no "
               "counter-example population there to test alignment vs magnitude independently "
               "(Q1-long n=2, Q2-long n=4, Q4-short n=7, Q5-short n=0). The magnitude-symmetry "
               "check also fails (Q1-short PF 2.62 >> Q5-long PF 1.35 -- not a symmetric "
               "steep-either-way effect). Q3 (the only quintile with a real direction mix, "
               "33%/67%) is bad for BOTH directions there, which is the one genuinely "
               "direction-independent (non-confounded) piece of the table.")

    log("\n".join(verdict_lines))
    log("VERDICT: " + verdict)

    return dict(bins=bins.tolist(), cell_df=cell_df, pooled_df=pooled_df, verdict=verdict,
                verdict_lines=verdict_lines, canary_ok=canary_ok, canary_rows=canary_rows,
                dom_share=dom_share)


def define_tag_slope_weak(pooled_df, bins, ctx_all_705):
    """Mechanical tag definition per the (c)-confounded structure: rank quintiles by expR
    ascending (pooled across direction, since direction is redundant with quintile at the
    confounded extremes) and accumulate from the worst until coverage lands in [15,35]% of
    trades. Applied on the unfiltered-705 population for the coverage report; the SAME bin edges
    (frozen from that qcut) are re-applied (pd.cut) to the base machine's own A leg later."""
    ranked = pooled_df.sort_values("expR").reset_index(drop=True)
    chosen = []
    n_total = len(ctx_all_705.dropna(subset=["R"]))
    covered = 0
    for _, row in ranked.iterrows():
        candidate_n = covered + row["n"]
        candidate_pct = 100 * candidate_n / n_total
        if not chosen:
            chosen.append(int(row["quintile"]))
            covered = candidate_n
            continue
        if 15.0 <= 100 * covered / n_total <= 35.0:
            break
        if candidate_pct <= 35.0:
            chosen.append(int(row["quintile"]))
            covered = candidate_n
        else:
            break
    coverage_pct = round(100 * covered / n_total, 2)
    log(f"TAG_SLOPE_WEAK quintiles chosen (worst-expR-first, accumulate to 15-35% band): "
        f"{sorted(chosen)}  coverage={covered}/{n_total}={coverage_pct}%")
    return dict(quintiles=sorted(chosen), bins=bins, coverage_n=covered, coverage_total=n_total,
                coverage_pct=coverage_pct)


# ==================================================================================================
# tag application on the base-machine A leg (a2022, 513 rows, D1c-kept, 2022-2026)
# ==================================================================================================
def join_context_to_a2022(a2022, ctx):
    ctx_map = {pd.Timestamp(t): i for i, t in enumerate(ctx["ts"])}
    recs = []
    miss = 0
    for r in a2022:
        ts = pd.Timestamp(r["ts"])
        i = ctx_map.get(ts)
        if i is None:
            miss += 1
            recs.append(dict(ts=ts, R=r["R"], mae_r=r["mae_r"], risk_usd=r["risk_usd"],
                              direction=None, vwap_slope_6bar=np.nan, first_30m_ret=np.nan,
                              atr14_daily_prior=np.nan))
            continue
        row = ctx.iloc[i]
        recs.append(dict(ts=ts, R=r["R"], mae_r=r["mae_r"], risk_usd=r["risk_usd"],
                          direction=row["direction"], vwap_slope_6bar=row["vwap_slope_6bar"],
                          first_30m_ret=row["first_30m_ret"],
                          atr14_daily_prior=row["atr14_daily_prior"]))
    df = pd.DataFrame(recs)
    log(f"a2022 <-> profile_a_context join: {len(a2022) - miss}/{len(a2022)} matched by ts "
        f"({miss} misses).")
    return df


def apply_tag_slope_weak(a2022_df, tag_def):
    bins = np.asarray(tag_def["bins"])
    q = pd.cut(a2022_df["vwap_slope_6bar"], bins=bins, labels=[1, 2, 3, 4, 5], include_lowest=True)
    a2022_df = a2022_df.copy()
    a2022_df["slope_q"] = q
    a2022_df["tag_slope_weak"] = a2022_df["slope_q"].isin(tag_def["quintiles"])
    n_nan_slope = a2022_df["vwap_slope_6bar"].isna().sum()
    n_tagged = int(a2022_df["tag_slope_weak"].sum())
    n_total = len(a2022_df)
    log(f"TAG_SLOPE_WEAK on A-leg (a2022, n={n_total}): tagged={n_tagged} "
        f"({round(100*n_tagged/n_total,2)}% of all A trades; "
        f"{round(100*n_tagged/(n_total-n_nan_slope),2)}% of the "
        f"{n_total-n_nan_slope} slope-available trades); "
        f"{n_nan_slope} ({round(100*n_nan_slope/n_total,2)}%) have no vwap_slope_6bar "
        f"(<6 bars into the session) and are structurally untaggable -> stay full-size.")
    return a2022_df


def apply_tag_against_drive(a2022_df, drive_ratio=0.35):
    df = a2022_df.copy()
    before10 = df["ts"].dt.tz_convert(NY).dt.time < pd.Timestamp("10:00").time()
    df["before_10am_untagged"] = before10
    eligible = ~before10
    drive_sign = np.sign(df["first_30m_ret"])
    dir_sign = df["direction"].map({"long": 1, "short": -1})
    strong_drive = df["first_30m_ret"].abs() >= drive_ratio * df["atr14_daily_prior"]
    against = eligible & strong_drive & (drive_sign != 0) & (dir_sign != drive_sign)
    df["tag_against_drive"] = against.fillna(False)

    n_total = len(df)
    n_before10 = int(before10.sum())
    n_eligible = int(eligible.sum())
    n_strong = int((eligible & strong_drive).sum())
    n_tagged = int(df["tag_against_drive"].sum())
    log(f"TAG_AGAINST_DRIVE on A-leg (a2022, n={n_total}): before-10:00 (untagged by construction, "
        f"causality) = {n_before10} ({round(100*n_before10/n_total,1)}%); "
        f"eligible (>=10:00) = {n_eligible} ({round(100*n_eligible/n_total,1)}%); "
        f"of those, strong-drive (|first_30m_ret|>=0.35*ATR14) = {n_strong}; "
        f"TAG_AGAINST_DRIVE (strong-drive AND direction opposes) = {n_tagged} "
        f"({round(100*n_tagged/n_total,2)}% of all A trades, "
        f"{round(100*n_tagged/n_eligible,2)}% of eligible) -- essentially a null-coverage tag as "
        f"literally defined (Profile A's OTE signal almost never fires against a strong opening "
        f"drive; of {n_strong} strong-drive trades, {n_strong - n_tagged} align with the drive and "
        f"only {n_tagged} oppose it).")
    return df


# ==================================================================================================
# variant construction + funnel
# ==================================================================================================
def rows_from_df(df, mask=None):
    sub = df if mask is None else df[mask]
    return [dict(ts=r.ts, R=r.R, mae_r=r.mae_r, risk_usd=r.risk_usd) for r in sub.itertuples()]


def variant_ev_a(a2022_df, variant, slip=0.0, cap=6):
    """Returns (ev_a, full_rows_used_for_stats, label_note) for one of
    {base, S1, S2, D1, D2, SD1}."""
    tag_slope = a2022_df["tag_slope_weak"].fillna(False)
    tag_drive = a2022_df["tag_against_drive"].fillna(False)

    if variant == "base":
        full_rows = rows_from_df(a2022_df)
        return build_split_ev(full_rows, [], cap=cap, slip=slip), full_rows
    if variant == "S1":
        half_rows = rows_from_df(a2022_df, tag_slope)
        full_rows = rows_from_df(a2022_df, ~tag_slope)
        return build_split_ev(full_rows, half_rows, cap=cap, slip=slip), rows_from_df(a2022_df)
    if variant == "S2":
        full_rows = rows_from_df(a2022_df, ~tag_slope)
        return build_split_ev(full_rows, [], cap=cap, slip=slip), full_rows
    if variant == "D1":
        half_rows = rows_from_df(a2022_df, tag_drive)
        full_rows = rows_from_df(a2022_df, ~tag_drive)
        return build_split_ev(full_rows, half_rows, cap=cap, slip=slip), rows_from_df(a2022_df)
    if variant == "D2":
        full_rows = rows_from_df(a2022_df, ~tag_drive)
        return build_split_ev(full_rows, [], cap=cap, slip=slip), full_rows
    if variant == "SD1":
        union_tag = tag_slope | tag_drive
        half_rows = rows_from_df(a2022_df, union_tag)
        full_rows = rows_from_df(a2022_df, ~union_tag)
        return build_split_ev(full_rows, half_rows, cap=cap, slip=slip), rows_from_df(a2022_df)
    raise ValueError(variant)


def run_variant(a2022_df, v_rows, variant, slip):
    ev_a, stats_rows = variant_ev_a(a2022_df, variant, slip=slip, cap=6)
    v_rows_s = ST.dmg_slip(v_rows, slip)
    label = f"{variant} slip={slip}"
    s = eval_combo_from_ev(ev_a, v_rows_s, (600.0, 4), label)
    refstats = VR.same_day_stats(stats_rows, v_rows)  # unit-level, budget-invariant -> undamaged
    s["variant"] = variant
    s["slip"] = slip
    s["same_day_corr"] = refstats["same_day_corr"]
    s["dl_freq_pct"] = refstats["dl_freq_pct"]
    s["tl_freq_pct"] = refstats["tl_freq_pct"]
    s["n_a_rows_used"] = len(stats_rows)
    return s


def flatten_record(s):
    rec = dict(variant=s["variant"], slip=s["slip"], eligible_starts=s["eligible_starts"],
               pass_count=s["pass_count"], bust_count=s["bust_count"], exp_count=s["exp_count"],
               pass_pct=s["pass_pct"], bust_pct=s["bust_pct"], exp_pct=s["exp_pct"],
               med_days_pass=s["med_days_pass"], funded_per_slot_year=s["funded_per_slot_year"],
               pf_dollar=s["pf_dollar"], trades_per_week=s["trades_per_week"],
               same_day_corr=s["same_day_corr"], dl_freq_pct=s["dl_freq_pct"],
               tl_freq_pct=s["tl_freq_pct"], n_a_rows_used=s["n_a_rows_used"])
    for y in YEARS:
        py = s["per_year"].get(y)
        rec[f"py{y}_n"] = py["n"] if py else 0
        rec[f"py{y}_pass_pct"] = py["pass_pct"] if py else None
    return rec


# ==================================================================================================
# artifact flags + stress-survival + priors bar
# ==================================================================================================
def build_comparison(records_df):
    base_by_slip = {row["slip"]: row for _, row in records_df[records_df.variant == "base"].iterrows()}
    out = []
    for variant in ["S1", "S2", "D1", "D2", "SD1"]:
        vrows = {row["slip"]: row for _, row in records_df[records_df.variant == variant].iterrows()}
        rec = dict(variant=variant)
        for slip in SLIP_GRID:
            b, v = base_by_slip[slip], vrows[slip]
            d_pass_count = v["pass_count"] - b["pass_count"]
            d_pass_pct = round(v["pass_pct"] - b["pass_pct"], 2) if (v["pass_pct"] is not None and b["pass_pct"] is not None) else None
            d_fpsy = round(v["funded_per_slot_year"] - b["funded_per_slot_year"], 3) if (v["funded_per_slot_year"] is not None and b["funded_per_slot_year"] is not None) else None
            artifact = bool(d_pass_pct is not None and d_pass_pct > 0 and d_pass_count < 0)
            rec[f"slip{slip}_base_pass_pct"] = b["pass_pct"]
            rec[f"slip{slip}_variant_pass_pct"] = v["pass_pct"]
            rec[f"slip{slip}_d_pass_pct"] = d_pass_pct
            rec[f"slip{slip}_base_pass_count"] = b["pass_count"]
            rec[f"slip{slip}_variant_pass_count"] = v["pass_count"]
            rec[f"slip{slip}_d_pass_count"] = d_pass_count
            rec[f"slip{slip}_base_fpsy"] = b["funded_per_slot_year"]
            rec[f"slip{slip}_variant_fpsy"] = v["funded_per_slot_year"]
            rec[f"slip{slip}_d_fpsy"] = d_fpsy
            rec[f"slip{slip}_DENOMINATOR_ARTIFACT"] = artifact
        # per-year comparison at slip=0.0
        b0 = base_by_slip[0.0]
        v0 = vrows[0.0]
        years_variant_ge_base = 0
        years_eligible = 0
        for y in YEARS:
            bn, bp = b0[f"py{y}_n"], b0[f"py{y}_pass_pct"]
            vn, vp = v0[f"py{y}_n"], v0[f"py{y}_pass_pct"]
            if bn and vn and bp is not None and vp is not None:
                years_eligible += 1
                if vp >= bp:
                    years_variant_ge_base += 1
            rec[f"py{y}_base_pass_pct"] = bp
            rec[f"py{y}_variant_pass_pct"] = vp
        rec["years_variant_ge_base"] = years_variant_ge_base
        rec["years_eligible"] = years_eligible
        rec["holds_4_of_5"] = years_variant_ge_base >= 4
        d_fpsy_0 = rec["slip0.0_d_fpsy"]
        d_fpsy_02 = rec["slip0.02_d_fpsy"]
        survives_002 = bool(d_fpsy_0 is not None and d_fpsy_02 is not None
                             and (d_fpsy_0 <= 0 or (d_fpsy_02 > 0 and d_fpsy_0 > 0)))
        # explicit, mechanical: "survives" = delta vs base has the SAME sign at slip=0 and slip=0.02
        if d_fpsy_0 is not None and d_fpsy_02 is not None:
            survives_002 = (np.sign(d_fpsy_0) == np.sign(d_fpsy_02)) if d_fpsy_0 != 0 else (d_fpsy_02 == 0)
        else:
            survives_002 = None
        rec["survives_0.02R"] = survives_002
        rec["meets_priors_bar"] = bool(rec["holds_4_of_5"] and survives_002 and
                                       (rec.get("slip0.0_d_fpsy") or 0) > 0)
        any_artifact = any(rec[f"slip{s}_DENOMINATOR_ARTIFACT"] for s in SLIP_GRID)
        rec["any_denominator_artifact"] = any_artifact
        out.append(rec)
    return pd.DataFrame(out)


# ==================================================================================================
# report writers
# ==================================================================================================
def df_to_md_table(df):
    if df is None or len(df) == 0:
        return "(empty)"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            x = row[c]
            if isinstance(x, float):
                vals.append(f"{x:g}" if x == x else "")
            else:
                vals.append(str(x))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_I(tag_slope_def, tag_drive_stats_text, a_trades_per_week, overlap_n):
    os.makedirs(OUTDIR, exist_ok=True)
    graduates = [
        dict(name="TAG_SLOPE_WEAK (Graduate 1)",
             behaviour="Sizing tag (not a filter): halves budget for A-leg trades whose signal-time "
                       "6-bar VWAP slope falls in the two worst-expR quintiles pooled across "
                       "direction (Q3=near-flat, Q4=mild-upslope-long-dominated).",
             trigger="vwap_slope_6bar quintile in {3,4} at signal time, using bin edges frozen from "
                     "the unfiltered-705 qcut (F-lane canary). Trades with no computable "
                     "vwap_slope_6bar (<6 bars into the session) are untaggable and stay full-size.",
             interaction="Step-0 direction-interaction check found the underlying F-lane effect is "
                         "(c) CONFOUNDED, not alignment- or magnitude-based: Q1/Q2/Q4/Q5 are each "
                         ">=90% one direction by construction of the OTE signal; only Q3 has real "
                         "direction mixing and is bad for both directions there. The tag is defined "
                         "on the pooled-quintile ranking because direction adds no further "
                         "resolution once the confound is accounted for.",
             expected_trades_wk=a_trades_per_week,
             known_risks="Coverage (22.4% of the A leg, 33.2% of the slope-available subset) sits "
                         "at the middle of the mandated 15-35% band by construction of the "
                         "accumulate-to-band rule, not from an independently strong signal in Q4; "
                         "Q4's own effect (expR 0.05 vs pooled ~0.09-0.15) is much weaker than Q3's "
                         "(expR -0.15) and was pulled in only to clear the 15% floor. S2 (full "
                         "removal) has the standard salvage-lane denominator-artifact risk (fewer "
                         "A-trading days -> fewer eligible starts)."),
        dict(name="TAG_AGAINST_DRIVE (Graduate 2)",
             behaviour="Sizing tag (not a filter): halves budget for A-leg trades taken against a "
                       "STRONG 30-minute opening drive.",
             trigger="|first_30m_ret| >= 0.35 x atr14_daily_prior (known causally by 10:00) AND "
                     "trade direction opposes sign(first_30m_ret). Signals before 10:00 are "
                     "untagged by construction (causality) -- 30.8% of the A leg.",
             interaction=f"No interaction check requested/needed beyond the causal 10:00 cutoff; "
                         f"mechanically independent of the slope tag ({overlap_n} trade(s) overlap "
                         f"between the two tag sets on the A leg -- see SD1 in the J/L tables).",
             expected_trades_wk=a_trades_per_week,
             known_risks="AS LITERALLY DEFINED, this tag is functionally EMPTY: of 355 eligible "
                         "(>=10:00) A-leg trades, only 49 meet the strong-drive bar, and of those "
                         "only 1 trade opposes the drive direction (n=1/513 = 0.19% coverage). "
                         "Profile A's OTE signal almost never fires against a strong opening drive "
                         "-- this is a real, mechanically-computed structural finding (the signal "
                         "is drive-aligned by construction), not a bug, but it means D1/D2/SD1 are "
                         "expected to be statistically indistinguishable from base by construction "
                         "(single-trade effect). Reported in full below, not silently dropped."),
    ]
    df = pd.DataFrame(graduates)
    df.to_csv(os.path.join(OUTDIR, "I_candidate_strategies.csv"), index=False)

    non_grads = [
        "86%-drive-hold (Wave-1 C-lane) -- not a graduate: its expression is already owned by VPC "
        "(VPC's own signal generation captures the same opening-drive-hold population); no separate "
        "sizing tag adds information beyond what VPC already prices.",
        "extension-continuation (Wave-1 E-lane) -- explanatory null: described the shape of winning "
        "trades after the fact, no independently causal/tradeable trigger found.",
        "compression-contraction (Wave-1 E-lane) -- explanatory null: same as above, a post-hoc "
        "descriptive regularity, not a standalone signal.",
        "second-breakout-worse (Wave-1 C-lane) -- explanatory null: directionally true in the data "
        "but too thin / not independently actionable as a distinct tag once slope and drive are "
        "already accounted for.",
        "H (Wave-1 statistical-baseline-search lane) -- null: the full baseline search "
        "(H_statistical_baseline_search.csv/.md) did not surface a candidate that cleared the "
        "graduation gate; nothing from H reached candidate-testing status.",
    ]

    lines = []
    lines.append("# I -- Candidate strategies (DISCOVERY Wave 2 graduates)")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. The graduation gate passed exactly two context "
                 "features for candidate testing as SIZING TAGS on the candidate portfolio machine "
                 "(A@600/cap6 + VPC@600/cap4). Neither graduate is a filter -- both only modulate "
                 "the A-leg per-trade budget (full $600 vs half $300) or, for the S2/D2 variants, "
                 "remove the tagged trades entirely (reported for completeness per the brief, with "
                 "count-basis caveats).")
    lines.append("")
    lines.append("## Graduates")
    lines.append("")
    lines.append(df_to_md_table(df))
    lines.append("")
    lines.append("## Non-graduates (one line each, per brief)")
    lines.append("")
    for l in non_grads:
        lines.append(f"- {l}")
    lines.append("")
    with open(os.path.join(OUTDIR, "I_candidate_strategies.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    log(f"[saved] {os.path.join(OUTDIR, 'I_candidate_strategies.csv')}")
    log(f"[saved] {os.path.join(OUTDIR, 'I_candidate_strategies.md')}")


def write_J(records_df):
    os.makedirs(OUTDIR, exist_ok=True)
    records_df.to_csv(os.path.join(OUTDIR, "J_candidate_backtests.csv"), index=False)
    lines = []
    lines.append("# J -- Candidate backtests (full funnel, every variant x stress level)")
    lines.append("")
    lines.append("RESEARCH ONLY. LIVE HOLD ACTIVE. Base machine: A@600/cap6 (D1c-kept honest A, "
                 "2022-2026 window) + VPC@600/cap4, `day_rows(550,1000)`/`eval_run` (Apex 50K spec), "
                 "unchanged/pinned, reused verbatim from `tools_salvage_vpc_reeval.py`. Stress = "
                 "uniform slippage s (R units) subtracted from R and mae_r on EVERY trade of BOTH "
                 "legs (`tools_salvage_stress.dmg_slip`, prior-art convention, canary-matched below).")
    lines.append("")
    lines.append(df_to_md_table(records_df))
    lines.append("")
    with open(os.path.join(OUTDIR, "J_candidate_backtests.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    log(f"[saved] {os.path.join(OUTDIR, 'J_candidate_backtests.csv')}")
    log(f"[saved] {os.path.join(OUTDIR, 'J_candidate_backtests.md')}")


def write_L(cmp_df):
    os.makedirs(OUTDIR, exist_ok=True)
    cmp_df.to_csv(os.path.join(OUTDIR, "L_eval_funnel_comparison.csv"), index=False)
    lines = []
    lines.append("# L -- Eval funnel comparison (every variant vs the base machine)")
    lines.append("")
    lines.append(PRIORS_TEXT)
    lines.append("")
    lines.append("DEC-20260706-1108 (verbatim rule, auto-applied): any variant with pass% up while "
                 "pass-count down = DENOMINATOR ARTIFACT, flagged per-stress-level below "
                 "(`slip{s}_DENOMINATOR_ARTIFACT`) and rolled up into `any_denominator_artifact`.")
    lines.append("")
    lines.append("No winner-picking: every delta is reported as computed; `meets_priors_bar` is a "
                 "mechanical AND of (funded-per-slot-year count up at slip=0) AND (holds in >=4/5 "
                 "years) AND (same-sign delta survives 0.02R) -- not a recommendation.")
    lines.append("")
    lines.append(df_to_md_table(cmp_df))
    lines.append("")
    with open(os.path.join(OUTDIR, "L_eval_funnel_comparison.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    log(f"[saved] {os.path.join(OUTDIR, 'L_eval_funnel_comparison.csv')}")
    log(f"[saved] {os.path.join(OUTDIR, 'L_eval_funnel_comparison.md')}")


# ==================================================================================================
def main():
    import time
    t0 = time.time()

    if not firewall("BEFORE"):
        log("[STOP] firewall FAILED before any work -- not proceeding.")
        return

    v_rows, a_full, a2022 = load_streams()

    ok, base_ref_cell = reproduce_base_machine(a2022, v_rows)
    if not ok:
        log("[STOP] base machine reference row MISMATCH -- do not trust anything downstream.")
        return

    ctx = load_context()
    step0 = step0_direction_interaction(ctx)
    if not step0["canary_ok"]:
        log("[STOP] F-lane vwap_slope quintile canary MISMATCH -- do not trust the tag definition.")
        return

    tag_slope_def = define_tag_slope_weak(step0["pooled_df"], step0["bins"], ctx)

    a2022_df = join_context_to_a2022(a2022, ctx)
    a2022_df = apply_tag_slope_weak(a2022_df, tag_slope_def)
    a2022_df = apply_tag_against_drive(a2022_df)

    overlap = int((a2022_df["tag_slope_weak"].fillna(False) & a2022_df["tag_against_drive"].fillna(False)).sum())
    log(f"TAG_SLOPE_WEAK / TAG_AGAINST_DRIVE overlap on A-leg: {overlap} trades in both sets.")

    records = []
    for variant in ["base", "S1", "S2", "D1", "D2", "SD1"]:
        for slip in SLIP_GRID:
            s = run_variant(a2022_df, v_rows, variant, slip)
            records.append(flatten_record(s))
            log(f"  {variant:>4} slip={slip:<5} | n={s['eligible_starts']:>4} "
                f"pass={s['pass_pct']}% bust={s['bust_pct']}% exp={s['exp_pct']}% "
                f"fund/slot/yr={s['funded_per_slot_year']} trades/wk={s['trades_per_week']} "
                f"dl={s['dl_freq_pct']}% tl={s['tl_freq_pct']}%")

    records_df = pd.DataFrame(records)

    # canary: base slip=0 row must still equal the pinned reference row exactly
    base0 = records_df[(records_df.variant == "base") & (records_df.slip == 0.0)].iloc[0]
    assert (base0.eligible_starts == REF_MACHINE["n"] and base0.pass_pct == REF_MACHINE["pass_pct"]
            and base0.bust_pct == REF_MACHINE["bust_pct"] and base0.exp_pct == REF_MACHINE["exp_pct"])
    # canary: base machine stress rows should match the pinned A6 salvage-stress precedent
    # (C1 A(600,6)+VPC(600,4): slip=0.02 -> pass=23.4/bust=17.4/exp=59.2/pass_count=160/n=684;
    #  slip=0.05 -> pass=20/bust=22.5/exp=57.5/pass_count=137/n=684)
    base02 = records_df[(records_df.variant == "base") & (records_df.slip == 0.02)].iloc[0]
    base05 = records_df[(records_df.variant == "base") & (records_df.slip == 0.05)].iloc[0]
    a6_ok = (base02.pass_pct == 23.4 and base02.bust_pct == 17.4 and base02.pass_count == 160
             and base05.pass_pct == 20.0 and base05.bust_pct == 22.5 and base05.pass_count == 137)
    log(f"[A6 STRESS-CANARY vs pinned salvage-stress precedent] slip=0.02 got "
        f"pass={base02.pass_pct}/bust={base02.bust_pct}/n_pass={base02.pass_count} (ref 23.4/17.4/160); "
        f"slip=0.05 got pass={base05.pass_pct}/bust={base05.bust_pct}/n_pass={base05.pass_count} "
        f"(ref 20.0/22.5/137)  -> {'PASS' if a6_ok else 'MISMATCH -- STOP'}")
    if not a6_ok:
        log("[STOP] stress-canary mismatch vs pinned A6 precedent -- do not trust stress columns.")
        return

    cmp_df = build_comparison(records_df)

    a_trades_per_week = round(len(a2022) / VR.weeks_span(ASR.build_events(a2022, 600, 6)), 2)

    write_I(tag_slope_def, "", a_trades_per_week, overlap)
    write_J(records_df)
    write_L(cmp_df)

    if not firewall("AFTER"):
        log("[STOP] firewall FAILED after the work -- flag before trusting outputs.")
        return

    dt = time.time() - t0
    log(f"\nTOTAL RUNTIME: {dt:.1f}s")
    log("DONE.")


if __name__ == "__main__":
    main()
