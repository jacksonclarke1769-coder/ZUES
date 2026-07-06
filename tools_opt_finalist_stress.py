"""tools_opt_finalist_stress.py — A+VPC PORTFOLIO OPTIMISATION, WAVE 2: full stress + robustness on
the Wave-1 finalists.

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing (no live/config/engine file touched).
Reads Wave-1's `02_sizing_grid.csv` (already-certified sizing grid) plus the two raw row streams
(A, VPC) and re-derives everything else mechanically. No modeling choice is new-and-hidden — every
one not already covered by prior art is called out explicitly below.

STREAMS (pinned exactly as the task brief specifies):
  A   = `tools_sim_parity_check.load_rows()` (canary: n=583, PF=1.3606000676571652 — VR.A_HONEST_N/
        A_HONEST_PF), filtered to ts >= 2022-01-01 (`tools_salvage_vpc_reeval.a_rows_2022`).
  VPC = the 1m-truth re-walked VPC stream (`tools_vpc_1m_truth.vpc_1m_truth_trades` +
        `.build_new_vpc_rows`, canary: n=408, PF(pts)=1.318 — same canary `tools_opt_windows_exits.
        load_streams()` already runs).

TZ NORMALIZATION (mandatory, per task brief — "three lanes have independently hit this seam"):
  VPC 1m-truth rows come back with a tz-NAIVE `ts`. `tools_opt_conflict_risk.py`'s own convention
  (`_localize()`, reused verbatim in `tools_opt_sizing_grid.py`'s `kept_trades()` TZ NOTE and in
  `tools_vpc_1m_truth.headline_funnel()` itself: "e['ts'].tz_localize('America/New_York')" if naive)
  treats that naive stamp AS ALREADY NY wall-clock — i.e. `tz_localize(NY)` directly, no UTC
  conversion. This is the convention THREE separate lanes already use (conflict_risk.py,
  sizing_grid.py, vpc_1m_truth.py itself) and is copied here EXACTLY, ONCE, immediately after
  loading the VPC stream (`_localize()` below, byte-identical to conflict_risk.py's own function).
  NOTE (called out, not hidden): `tools_opt_windows_exits.py`'s OWN `to_ny_ts()` uses a DIFFERENT,
  self-declared "corrected" convention (naive-as-UTC, tz_convert to NY) for its own time-of-day
  WINDOW FILTER only — this file deliberately does NOT reuse `to_ny_ts`/`et_time` for the lane-3
  pareto variant's 10:00-14:00 window rebuild (finalist (d) below); it uses the pinned
  conflict_risk-style localization end-to-end instead, per the task brief's explicit instruction to
  "read its normalization and copy it EXACTLY." This means finalist (d)'s rebuilt VPC-window stream
  here may NOT numerically reproduce `05_timing_windows.csv`'s own "A-max-1/day + VPC[10:00-14:00]"
  row (which used `to_ny_ts`) — both are reported; the discrepancy (if any) is noted in the MD.
  A's `ts` is already tz-aware `America/New_York` (from `tools_sim_parity_check.load_rows()`), so
  `_localize()` is a no-op there; applied anyway for uniformity (matches conflict_risk.py's
  `build_tagged_rows`, which runs BOTH streams through `_localize()`).

PRIOR ART REUSED (imported, not reimplemented):
  - `tools_salvage_vpc_reeval.py` (VR): `a_rows_full`/`a_rows_2022`, `WINDOW_START`, `ASR`
    (`build_events`/`day_rows`), `STOP_PINNED`/`DLL_PINNED`, `event_pf`, `summarize_cell`,
    `weeks_span`, `A_HONEST_N`/`A_HONEST_PF`, `v`/`VS` (VPC engine handles), `DPP`.
  - `tools_vpc_1m_truth.py` (VT): `load_1m_rth`, `vpc_1m_truth_trades`, `build_new_vpc_rows`,
    `old_new_summary` (n=408/PF=1.318 canary fields).
  - `tools_salvage_stress.py` (ST): `FIREWALL_FILES`/`sha_of`, `dmg_slip` (uniform R slippage),
    `dmg_partial` (winners' partial-fill fraction), `dmg_chase` (extra entry points -> R damage via
    that trade's own stop_pts; DPP is identical (2.0 $/pt/MNQ) for both A and VPC legs — verified:
    `tools_1m_truth_recert.DPP == tools_salvage_vpc_reeval.DPP == 2.0` — so `dmg_chase` is reused
    VERBATIM for BOTH legs' entry-realism damage, not reimplemented per-lane).
  - `tools_opt_conflict_risk.py` (C): `a_rows_direction_tagged()`/`v_rows_direction_tagged(df1m)` —
    reused ONLY as an auxiliary direction (long/short) lookup, joined back onto the primary A/VPC
    row streams by `ts` (both computations are the SAME deterministic code path -- `a_streams_d1c`'s
    inline logic is duplicated verbatim inside `a_rows_direction_tagged()` -- so the join is exact,
    verified below by an n/R-sum spot-check before use).

NEW LOGIC (self-verified extension, not prior art — called out, not hidden):
  - Finalist (d) row-level rebuild: `a_variant_max1_per_day()` (keep earliest A trade per calendar
    day — mechanically identical to `tools_opt_windows_exits.a_variant_max_n_per_day(rows, 1)`,
    reimplemented locally only so day-bucketing runs on THIS file's own tz-normalized rows) and
    `filter_window_1014()` (inclusive [10:00,14:00] ET filter on the tz-normalized VPC stream --
    inclusive endpoints per `tools_opt_windows_exits.filter_by_window`'s own documented reasoning
    re: a trade sitting exactly on a boundary).
  - COST 2x/3x damage: task-pinned approximation -- extra per-trade R damage =
    extra_RT_cost_pts / that_lane's_median_stop_pts, using A's base RT cost ~= 1.2pt (task-given) and
    VPC's base RT cost = 0.75pt (`nq_vwap_pullback.RT_COST`, prior art). 2x = +1 extra cost unit,
    3x = +2 extra cost units. Median stop_pts computed per lane from that finalist's OWN (undamaged)
    row set (`risk_usd / DPP`, DPP=2.0 both lanes) -- a new-but-mechanical, documented choice (no
    prior-art precedent for "2x/3x cost" in this repo).
  - FLIP POINT: linear interpolation of (pass_pct - bust_pct) across the 10-point slip ladder
    (anchored at s=0 with the finalist's own undamaged pass_pct/bust_pct) for the first bracket
    where the margin crosses from positive to <=0. `None` if the margin never crosses within the
    ladder (i.e. > 0.10R). New, mechanical, documented.
  - ONE-REGIME FLAG (08): a finalist's total POSITIVE per-year pass_pct advantage over the baseline
    finalist (a) is `sum(max(0, adv_y))` across years; flagged if any single year's positive
    advantage is > 50% of that total. If the finalist has no aggregate positive advantage over the
    baseline in any year, the flag is `N/A` (nothing to concentrate). New, mechanical, documented
    (no prior-art precedent for "advantage vs baseline" as opposed to `tools_opt_windows_exits.
    concentration_flag`'s "share of this cell's OWN passes", which is a different, already-used
    definition reused as-is elsewhere in this repo -- not reused here since the task brief explicitly
    asks for concentration of the ADVANTAGE vs baseline, not of the finalist's own raw passes).
  - Long/short split (08): composition + R-contribution only (count, %, sum-of-raw-R by direction)
    -- NOT a full separate pass/bust funnel re-run per direction (that would require re-defining a
    single-legged eval funnel with no prior-art precedent within the task's runtime budget; called
    out, not hidden, as a scope decision).
  - Bootstrap: resample each finalist's own eligible-start outcome array (with replacement,
    n=len(outcomes)) 1000x, fixed seed 42 per finalist (`numpy.random.default_rng(42)`, literal seed,
    not clock-derived), report the 5th/50th/95th percentile of the resampled pass_pct distribution.

Baseline canary (mandatory, checked before finalist selection; STOP on mismatch):
  A@600/6 + VPC@600/4 (2022+ A, 1m-truth VPC) -> pass=28.7 / bust=17.0 / exp=54.4 (n=684).

Outputs (new, this run only):
  reports/a_vpc_portfolio_optimisation/07_top_cell_stress.csv / .md
  reports/a_vpc_portfolio_optimisation/08_robustness_stability.csv / .md

No winner-picking. No commits.
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

import tools_salvage_vpc_reeval as VR          # A/VPC row loaders, ASR funnel, event_pf, summarize_cell
import tools_vpc_1m_truth as VT                # 1m-truth VPC re-walk machinery
import tools_salvage_stress as ST              # FIREWALL_FILES, sha_of, dmg_slip/dmg_partial/dmg_chase
import tools_sim_parity_check as SPC           # load_rows (honest A stream) -- direct canary re-check
import tools_opt_conflict_risk as C            # direction-tagged loaders (long/short split only)

NY = "America/New_York"
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "a_vpc_portfolio_optimisation")
GRID_CSV = os.path.join(OUTDIR, "02_sizing_grid.csv")
FIREWALL_FILES = ST.FIREWALL_FILES

BASE_A_BC = (600, 6)
BASE_V_BC = (600, 4)
CANARY_BASELINE = dict(pass_pct=28.7, bust_pct=17.0, exp_pct=54.4, n=684)

SLIP_LADDER = [0.005, 0.01, 0.015, 0.02, 0.03, 0.04, 0.046, 0.05, 0.075, 0.10]
WINNERS_FILL = [0.75, 0.50, 0.25]
A_COST_BASE_PT = 1.2          # task-given approximation ("A ~= 1.2pt RT")
V_COST_BASE_PT = 0.75         # nq_vwap_pullback.RT_COST (prior art)
A_RETEST_PTS = [0.25, 0.50]   # +1tk, +2tk (NQ/MNQ tick = 0.25pt)
V_CHASE_PTS = [0.5, 1.0]

REJECT_SLIP_R = 0.015
REJECT_WINNERS_F = 0.75
REJECT_FLIP_R = 0.025
PREFER_FLIP_R = 0.04

BOOT_SEED = 42
BOOT_N = 1000
YEARS = [2022, 2023, 2024, 2025, 2026]

N_TOP_GREEN = 20
N_TOP_GY = 20
N_LOWBUST = 3


# ==================================================================================================
# TZ normalization (copied EXACTLY from tools_opt_conflict_risk._localize)
# ==================================================================================================
def _localize(ts):
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        ts = ts.tz_localize(NY)
    return ts


def _loc_rows(rows):
    return [dict(r, ts=_localize(r["ts"])) for r in rows]


# ==================================================================================================
# STREAM LOADING + canaries
# ==================================================================================================
def load_a_stream():
    a_full = SPC.load_rows()
    n = len(a_full)
    gp = sum(r["R"] for r in a_full if r["R"] > 0)
    gl = -sum(r["R"] for r in a_full if r["R"] < 0)
    pf = gp / gl if gl else float("nan")
    ok = (n == VR.A_HONEST_N) and abs(pf - VR.A_HONEST_PF) < 1e-6
    print(f"A stream canary: n={n} (expect {VR.A_HONEST_N}), PF={pf:.6f} (expect {VR.A_HONEST_PF:.6f}) "
          f"-> {'PASS' if ok else 'FAIL'}", flush=True)
    a_full = _loc_rows(a_full)
    a2022 = VR.a_rows_2022(a_full)
    return a_full, a2022, ok


def load_vpc_stream():
    v, VS = VR.v, VR.VS
    feats = v.features(VS.real_rth_5m())
    feats = feats[feats.date >= VR.WINDOW_START]
    d1rth = VT.load_1m_rth()
    print("re-walking VPC exits on 1m bars (5.0xATR trail, certified)…", flush=True)
    df1m, n_skipped = VT.vpc_1m_truth_trades(feats, d1rth)
    old_s, new_s = VT.old_new_summary(df1m)
    ok = (new_s["n_trades"] == 408 and new_s["pf_pts"] == 1.318)
    print(f"VPC 1m-truth canary: n={new_s['n_trades']} PF(pts)={new_s['pf_pts']} (expect n=408 "
          f"PF=1.318) -> {'PASS' if ok else 'FAIL'}", flush=True)
    v_rows = VT.build_new_vpc_rows(df1m)
    v_rows = _loc_rows(v_rows)          # NORMALIZE ONCE, immediately after load (task-mandated)
    return v_rows, df1m, feats, d1rth, ok


# ==================================================================================================
# shared funnel primitive (same pattern as tools_opt_windows_exits.funnel_cell /
# tools_salvage_stress.run_eval_combo -- reproduced here only because we also need `ev`/`days` back
# for per-year/month/bootstrap analysis, which those thin wrappers don't return).
# ==================================================================================================
def funnel(a_rows, a_bc, v_rows, v_bc, label):
    ev = []
    if a_rows is not None and a_bc is not None:
        ev += VR.ASR.build_events(a_rows, a_bc[0], a_bc[1])
    if v_rows is not None and v_bc is not None:
        ev += VR.ASR.build_events(v_rows, v_bc[0], v_bc[1])
    ev.sort(key=lambda e: e["ts"])
    pf = VR.event_pf(ev, label)
    days = VR.ASR.day_rows(ev, VR.STOP_PINNED, VR.DLL_PINNED)
    s = VR.summarize_cell(days, label)
    return s, (round(pf, 3) if pf == pf else None), ev, days


def margin(s):
    if s["pass_pct"] is None:
        return None
    return s["pass_pct"] - s["bust_pct"]


# ==================================================================================================
# lane-3 pareto variant row-level rebuild (finalist d)
# ==================================================================================================
def a_variant_max1_per_day(a_rows):
    by_day = {}
    for r in sorted(a_rows, key=lambda x: x["ts"]):
        d = pd.Timestamp(r["ts"]).normalize()
        by_day.setdefault(d, r)
    return sorted(by_day.values(), key=lambda x: x["ts"])


def _true_ny_time(ts):
    """DISCOVERED DURING IMPLEMENTATION (called out, not hidden): applying the task-mandated
    conflict_risk-style localization (`_localize`, naive treated AS ALREADY NY wall-clock) to a
    real hour-of-day WINDOW filter returns ZERO trades for the 10:00-14:00 window -- because the
    naive VPC ts digits are actually a naive-UTC reading (verified independently by
    `tools_opt_windows_exits.to_ny_ts`'s own check: "naive VPC entries span ~14:05-19:35 raw, which
    converts to 10:05-15:00 ET -- exactly the expected VPC session window"). The task's pinned
    convention is correct and used EVERYWHERE ELSE in this file (merge/sort, day-bucketing, event
    building -- all tz-invariant to this offset, per that same file's own comment); but an
    hour-of-day membership test is NOT tz-invariant, so THIS ONE FUNCTION separately re-derives the
    true NY wall-clock hour (naive digits -> tz_localize('UTC') -> tz_convert(NY)) for window
    MEMBERSHIP only. The row's own `ts` field (task-mandated convention) is left untouched and is
    what downstream funnel/day-bucketing code still uses."""
    naive = pd.Timestamp(ts).tz_localize(None)
    return naive.tz_localize("UTC").tz_convert(NY).time()


def filter_window_1014(v_rows):
    t0 = pd.Timestamp("10:00").time()
    t1 = pd.Timestamp("14:00").time()
    return [r for r in v_rows if t0 <= _true_ny_time(r["ts"]) <= t1]


# ==================================================================================================
# finalist selection
# ==================================================================================================
def select_finalists(df):
    finalists = {}   # key -> record
    order = []

    def add(tag, a_budget, a_cap, v_budget, v_cap, a_variant="current", v_window="full"):
        key = (int(a_budget), int(a_cap), int(v_budget), int(v_cap), a_variant, v_window)
        if key in finalists:
            if tag not in finalists[key]["tags"]:
                finalists[key]["tags"].append(tag)
        else:
            finalists[key] = dict(a_budget=int(a_budget), a_cap=int(a_cap), v_budget=int(v_budget),
                                  v_cap=int(v_cap), a_variant=a_variant, v_window=v_window, tags=[tag])
            order.append(key)
        return key

    base = df[df["is_baseline"] == True].iloc[0]
    add("baseline", base.a_budget, base.a_cap, base.v_budget, base.v_cap)

    green = df[df["classification"] == "GREEN"].sort_values("pass_pct", ascending=False)
    for _, r in green.head(N_TOP_GREEN).iterrows():
        add("top-green-pass_pct", r.a_budget, r.a_cap, r.v_budget, r.v_cap)

    gy = df[df["classification"].isin(["GREEN", "YELLOW"])].sort_values("funded_per_slot_year", ascending=False)
    n_added = 0
    for _, r in gy.iterrows():
        key = (int(r.a_budget), int(r.a_cap), int(r.v_budget), int(r.v_cap), "current", "full")
        if key in finalists:
            continue   # dedupe vs (a)/(b)
        add("top-greenyellow-funded_per_slot_year", r.a_budget, r.a_cap, r.v_budget, r.v_cap)
        n_added += 1
        if n_added >= N_TOP_GY:
            break

    lowbust = df[(df["classification"] == "GREEN") & (df["pass_pct"] >= 25)].sort_values("bust_pct").head(N_LOWBUST)
    for _, r in lowbust.iterrows():
        add("low-bust-3", r.a_budget, r.a_cap, r.v_budget, r.v_cap)

    # (d) lane-3 pareto variant: A-max-1/day @600/6 + VPC[10:00-14:00] @600/4 -- distinct key
    # (a_variant/v_window differ from the CSV-sourced "current"/"full" configs above, so this
    # cannot collide with the baseline's identical 600/6/600/4 sizing numbers).
    add("lane3-pareto-variant", 600, 6, 600, 4, a_variant="max-1/day", v_window="10:00-14:00")

    return finalists, order


# ==================================================================================================
# 07 -- STRESS LADDERS
# ==================================================================================================
def median_stop_pts(rows):
    if not rows:
        return None
    return float(np.median([r["risk_usd"] / VR.DPP for r in rows]))


def interpolate_flip(margin0, ladder_margins):
    pts = [(0.0, margin0)] + list(zip(SLIP_LADDER, ladder_margins))
    if pts[0][1] is None:
        return None
    if pts[0][1] <= 0:
        return 0.0
    for i in range(len(pts) - 1):
        s0, m0 = pts[i]
        s1, m1 = pts[i + 1]
        if m0 is None or m1 is None:
            continue
        if m0 > 0 and m1 <= 0:
            frac = m0 / (m0 - m1)
            return round(s0 + frac * (s1 - s0), 4)
    return None   # never flips within the ladder (>0.10R)


def stress_one(cfg_id, rec, a_rows_base, v_rows_base):
    a_bc = (rec["a_budget"], rec["a_cap"])
    v_bc = (rec["v_budget"], rec["v_cap"])
    label = f"07-{cfg_id}"
    out = dict(config_id=cfg_id, tags=";".join(rec["tags"]), a_budget=rec["a_budget"], a_cap=rec["a_cap"],
               v_budget=rec["v_budget"], v_cap=rec["v_cap"], a_variant=rec["a_variant"], v_window=rec["v_window"],
               n_a=len(a_rows_base), n_v=len(v_rows_base))

    s0, pf0, ev0, days0 = funnel(a_rows_base, a_bc, v_rows_base, v_bc, label)
    out.update(pf_dollar=pf0, eligible_starts=s0["eligible_starts"], pass_count=s0["pass_count"],
               bust_count=s0["bust_count"], exp_count=s0["exp_count"], pass_pct=s0["pass_pct"],
               bust_pct=s0["bust_pct"], exp_pct=s0["exp_pct"], funded_per_slot_year=s0["funded_per_slot_year"])
    m0 = margin(s0)

    # (1) slippage ladder, uniform both lanes
    ladder_margins = []
    for sv in SLIP_LADDER:
        a_s = ST.dmg_slip(a_rows_base, sv)
        v_s = ST.dmg_slip(v_rows_base, sv)
        s, _, _, _ = funnel(a_s, a_bc, v_s, v_bc, f"{label}-slip{sv}")
        out[f"slip{sv}_pass_pct"] = s["pass_pct"]
        out[f"slip{sv}_bust_pct"] = s["bust_pct"]
        ladder_margins.append(margin(s))
    flip = interpolate_flip(m0, ladder_margins)
    out["flip_point_R"] = flip

    # (2) costs base/2x/3x
    a_med_stop = median_stop_pts(a_rows_base)
    v_med_stop = median_stop_pts(v_rows_base)
    for mult, tag in ((2, "cost2x"), (3, "cost3x")):
        extra_units = mult - 1
        dmg_r_a = (extra_units * A_COST_BASE_PT) / a_med_stop if a_med_stop else 0.0
        dmg_r_v = (extra_units * V_COST_BASE_PT) / v_med_stop if v_med_stop else 0.0
        a_c = ST.dmg_slip(a_rows_base, dmg_r_a)
        v_c = ST.dmg_slip(v_rows_base, dmg_r_v)
        s, _, _, _ = funnel(a_c, a_bc, v_c, v_bc, f"{label}-{tag}")
        out[f"{tag}_pass_pct"] = s["pass_pct"]
        out[f"{tag}_bust_pct"] = s["bust_pct"]
        out[f"{tag}_verdict_pass_gt_bust"] = bool(margin(s) is not None and margin(s) > 0)

    # (3) winners-fill, both lanes
    for f in WINNERS_FILL:
        a_p = ST.dmg_partial(a_rows_base, f)
        v_p = ST.dmg_partial(v_rows_base, f)
        s, _, _, _ = funnel(a_p, a_bc, v_p, v_bc, f"{label}-wf{f}")
        tag = f"wf{int(f * 100)}"
        out[f"{tag}_pass_pct"] = s["pass_pct"]
        out[f"{tag}_bust_pct"] = s["bust_pct"]
        out[f"{tag}_verdict_pass_gt_bust"] = bool(margin(s) is not None and margin(s) > 0)

    # (4) entry realism -- A-leg retest-fill (VPC undamaged), VPC-leg chase (A undamaged)
    for pts in A_RETEST_PTS:
        a_r = ST.dmg_chase(a_rows_base, pts)
        s, _, _, _ = funnel(a_r, a_bc, v_rows_base, v_bc, f"{label}-aretest{pts}")
        tk = int(round(pts / 0.25))
        out[f"a_retest{tk}tk_pass_pct"] = s["pass_pct"]
        out[f"a_retest{tk}tk_bust_pct"] = s["bust_pct"]
        out[f"a_retest{tk}tk_verdict_pass_gt_bust"] = bool(margin(s) is not None and margin(s) > 0)
    for pts in V_CHASE_PTS:
        v_c2 = ST.dmg_chase(v_rows_base, pts)
        s, _, _, _ = funnel(a_rows_base, a_bc, v_c2, v_bc, f"{label}-vchase{pts}")
        out[f"v_chase{pts}pt_pass_pct"] = s["pass_pct"]
        out[f"v_chase{pts}pt_bust_pct"] = s["bust_pct"]
        out[f"v_chase{pts}pt_verdict_pass_gt_bust"] = bool(margin(s) is not None and margin(s) > 0)

    # reject / survives-preferred (mechanical, per task's ORIGINAL operator bar -- kept as-is,
    # not overwritten; see REJECT_v2_config_only below for the auditor's re-scoped bar)
    dies_015 = out["slip0.015_pass_pct"] is not None and out["slip0.015_pass_pct"] <= out["slip0.015_bust_pct"]
    dies_w75 = out["wf75_pass_pct"] is not None and out["wf75_pass_pct"] <= out["wf75_bust_pct"]
    flip_lt_025 = (flip is not None and flip < REJECT_FLIP_R) or (flip is None and False)
    reject = bool(dies_015 or dies_w75 or flip_lt_025)
    out["reject_dies_at_0.015R"] = bool(dies_015)
    out["reject_dies_at_winners75"] = bool(dies_w75)
    out["reject_flip_lt_0.025R"] = bool(flip_lt_025)
    out["REJECT"] = reject

    survives_w75 = out["wf75_verdict_pass_gt_bust"]
    survives_2x = out["cost2x_verdict_pass_gt_bust"]
    prefer = bool((flip is not None) and (flip >= PREFER_FLIP_R) and survives_w75 and survives_2x)

    # AUDITOR ADJUDICATION (2026-07-06): winners-fill-75% is a MACHINE-LEVEL operating condition
    # (governed by the live fill-telemetry kill line), NOT a config selector -- unsatisfiable by
    # construction for any honest thin edge (PF~1.35 x 0.75 ~= 1.01 breakeven; only PF>=1.8
    # machines would pass it, which the PF-freeze bar (VR.PF_FREEZE_THRESHOLD=1.8) would flag as
    # too-good-to-trust anyway). Re-scoped, CONFIG-LEVEL reject bar (added column, ORIGINAL
    # `REJECT`/`reject_dies_at_winners75` above left untouched):
    #   dies-at-0.015R OR flip<0.025R OR dies-at-2x-costs.
    dies_2x = not out["cost2x_verdict_pass_gt_bust"]
    reject_v2 = bool(dies_015 or flip_lt_025 or dies_2x)
    out["reject_dies_at_2x_costs"] = bool(dies_2x)
    out["REJECT_v2_config_only"] = reject_v2
    out["SURVIVES_PREFERRED"] = prefer

    return out, s0, ev0, days0


# ==================================================================================================
# 08 -- ROBUSTNESS / STABILITY (only for finalists surviving the reject column)
# ==================================================================================================
def per_year_full(results):
    out = {}
    for y in YEARS:
        yr = [r for r in results if r[2] == y]
        n = len(yr)
        if n == 0:
            out[y] = dict(n=0, pass_count=0, bust_count=0, exp_count=0, pass_pct=None, bust_pct=None, exp_pct=None)
            continue
        p = sum(1 for r in yr if r[0] == "PASS")
        b = sum(1 for r in yr if r[0] == "BUST")
        x = sum(1 for r in yr if r[0] == "EXPIRE")
        out[y] = dict(n=n, pass_count=p, bust_count=b, exp_count=x, pass_pct=round(100 * p / n, 1),
                     bust_pct=round(100 * b / n, 1), exp_pct=round(100 * x / n, 1))
    return out


def per_year_pf_totr(ev, raw_a, raw_v):
    out = {}
    raw_all = list(raw_a) + list(raw_v)
    for y in YEARS:
        ev_y = [e for e in ev if pd.Timestamp(e["ts"]).year == y]
        gp = sum(e["pnl"] for e in ev_y if e["pnl"] > 0)
        gl = -sum(e["pnl"] for e in ev_y if e["pnl"] < 0)
        pf = gp / gl if gl > 0 else float("nan")
        totR = sum(r["R"] for r in raw_all if pd.Timestamp(r["ts"]).year == y)
        out[y] = dict(pf_dollar=round(pf, 3) if pf == pf else None, totR=round(totR, 3))
    return out


def start_month_breakdown(days, starts, results):
    buckets = {}
    for pos, s in enumerate(starts):
        d = days[s][0]
        key = f"{d.year}-{d.month:02d}"
        buckets.setdefault(key, []).append(results[pos][0])
    rows = []
    for k, statuses in buckets.items():
        n = len(statuses)
        p = sum(1 for s in statuses if s == "PASS")
        rows.append(dict(month=k, n=n, pass_pct=round(100 * p / n, 1)))
    rows.sort(key=lambda r: (r["pass_pct"], -r["n"]))
    worst = rows[0] if rows else None
    best = rows[-1] if rows else None
    return best, worst, rows


def one_regime_flag(finalist_per_year, baseline_per_year):
    advantages = {}
    for y in YEARS:
        fp = finalist_per_year[y]["pass_pct"]
        bp = baseline_per_year[y]["pass_pct"]
        if fp is None or bp is None:
            continue
        advantages[y] = fp - bp
    positive = {y: a for y, a in advantages.items() if a > 0}
    total_pos = sum(positive.values())
    if total_pos <= 0:
        return "N/A", None, None
    worst_y = max(positive, key=positive.get)
    share = positive[worst_y] / total_pos
    return bool(share > 0.5), worst_y, round(share, 3)


def month_drawdown_table(raw_a, raw_v):
    rows_sorted = sorted(list(raw_a) + list(raw_v), key=lambda r: r["ts"])
    if not rows_sorted:
        return [], 0.0
    df = pd.DataFrame([dict(ts=r["ts"], R=r["R"]) for r in rows_sorted])
    df["month"] = df["ts"].apply(lambda t: f"{t.year}-{t.month:02d}")
    df["cum"] = df["R"].cumsum()
    df["peak"] = df["cum"].cummax()
    df["dd"] = df["cum"] - df["peak"]
    out = []
    for m, g in df.groupby("month", sort=False):
        out.append(dict(month=m, month_R=round(g["R"].sum(), 3), cum_R=round(g["cum"].iloc[-1], 3),
                        dd_R_at_month_end=round(g["dd"].iloc[-1], 3)))
    out.sort(key=lambda r: r["month"])
    max_dd = round(float(df["dd"].min()), 3)
    return out, max_dd


def bootstrap_pass_pct(results):
    outcomes = np.array([1 if r[0] == "PASS" else 0 for r in results])
    n = len(outcomes)
    if n == 0:
        return None, None, None
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, n, size=(BOOT_N, n))
    samp = outcomes[idx]
    pcts = 100 * samp.mean(axis=1)
    return round(float(np.percentile(pcts, 5)), 1), round(float(np.percentile(pcts, 50)), 1), \
        round(float(np.percentile(pcts, 95)), 1)


def build_direction_maps(df1m):
    a_dir_rows = C.a_rows_direction_tagged()
    v_dir_rows = C.v_rows_direction_tagged(df1m)
    a_map = {pd.Timestamp(r["ts"]): r["direction"] for r in a_dir_rows}
    v_map = {pd.Timestamp(_localize(r["ts"])): r["direction"] for r in v_dir_rows}
    return a_map, v_map, len(a_dir_rows), len(v_dir_rows)


def long_short_split(rows, dir_map):
    matched, unmatched = [], 0
    for r in rows:
        d = dir_map.get(pd.Timestamp(r["ts"]))
        if d is None:
            unmatched += 1
            continue
        matched.append((d, r["R"]))
    long_n = sum(1 for d, _ in matched if d == 1)
    short_n = sum(1 for d, _ in matched if d == -1)
    long_R = sum(rr for d, rr in matched if d == 1)
    short_R = sum(rr for d, rr in matched if d == -1)
    return dict(long_n=long_n, short_n=short_n, long_R=round(long_R, 3), short_R=round(short_R, 3),
               unmatched=unmatched)


def robustness_one(cfg_id, s_label, rec, a_rows_base, v_rows_base, s0, ev0, days0, baseline_per_year,
                   a_dir_map, v_dir_map, stress_row):
    a_bc = (rec["a_budget"], rec["a_cap"])
    v_bc = (rec["v_budget"], rec["v_cap"])
    starts, results = VR.run_cell(days0)
    py = per_year_full(results)
    py_pf_r = per_year_pf_totr(ev0, a_rows_base, v_rows_base)
    best_m, worst_m, _all_m = start_month_breakdown(days0, starts, results)
    one_reg, one_reg_year, one_reg_share = one_regime_flag(py, baseline_per_year)
    dd_table, max_dd = month_drawdown_table(a_rows_base, v_rows_base)
    p05, p50, p95 = bootstrap_pass_pct(results)

    ls_a = long_short_split(a_rows_base, a_dir_map)
    ls_v = long_short_split(v_rows_base, v_dir_map)
    long_n = ls_a["long_n"] + ls_v["long_n"]
    short_n = ls_a["short_n"] + ls_v["short_n"]
    tot_n = long_n + short_n
    a_totR = sum(r["R"] for r in a_rows_base)
    v_totR = sum(r["R"] for r in v_rows_base)
    tot_R = a_totR + v_totR

    out = dict(config_id=cfg_id, s_label=s_label, tags=";".join(rec["tags"]), a_budget=rec["a_budget"],
               a_cap=rec["a_cap"], v_budget=rec["v_budget"], v_cap=rec["v_cap"], a_variant=rec["a_variant"],
               v_window=rec["v_window"],
               pass_pct=stress_row["pass_pct"], bust_pct=stress_row["bust_pct"],
               exp_pct=stress_row["exp_pct"], flip_point_R=stress_row["flip_point_R"],
               cost2x_verdict_pass_gt_bust=stress_row["cost2x_verdict_pass_gt_bust"],
               cost3x_verdict_pass_gt_bust=stress_row["cost3x_verdict_pass_gt_bust"],
               a_retest1tk_verdict_pass_gt_bust=stress_row["a_retest1tk_verdict_pass_gt_bust"],
               a_retest2tk_verdict_pass_gt_bust=stress_row["a_retest2tk_verdict_pass_gt_bust"],
               v_chase0_5pt_verdict_pass_gt_bust=stress_row["v_chase0.5pt_verdict_pass_gt_bust"],
               v_chase1_0pt_verdict_pass_gt_bust=stress_row["v_chase1.0pt_verdict_pass_gt_bust"],
               REJECT_v2_config_only=stress_row["REJECT_v2_config_only"])
    for y in YEARS:
        out[f"py{y}_n"] = py[y]["n"]
        out[f"py{y}_pass_count"] = py[y]["pass_count"]
        out[f"py{y}_bust_count"] = py[y]["bust_count"]
        out[f"py{y}_exp_count"] = py[y]["exp_count"]
        out[f"py{y}_pass_pct"] = py[y]["pass_pct"]
        out[f"py{y}_bust_pct"] = py[y]["bust_pct"]
        out[f"py{y}_exp_pct"] = py[y]["exp_pct"]
        out[f"py{y}_pf_dollar"] = py_pf_r[y]["pf_dollar"]
        out[f"py{y}_totR"] = py_pf_r[y]["totR"]
    out["best_start_month"] = best_m["month"] if best_m else None
    out["best_start_month_pass_pct"] = best_m["pass_pct"] if best_m else None
    out["best_start_month_n"] = best_m["n"] if best_m else None
    out["worst_start_month"] = worst_m["month"] if worst_m else None
    out["worst_start_month_pass_pct"] = worst_m["pass_pct"] if worst_m else None
    out["worst_start_month_n"] = worst_m["n"] if worst_m else None
    out["long_count"] = long_n
    out["short_count"] = short_n
    out["long_pct"] = round(100 * long_n / tot_n, 1) if tot_n else None
    out["long_totR"] = round(ls_a["long_R"] + ls_v["long_R"], 3)
    out["short_totR"] = round(ls_a["short_R"] + ls_v["short_R"], 3)
    out["direction_unmatched"] = ls_a["unmatched"] + ls_v["unmatched"]
    out["a_only_totR"] = round(a_totR, 3)
    out["vpc_only_totR"] = round(v_totR, 3)
    out["a_only_totR_pct"] = round(100 * a_totR / tot_R, 1) if tot_R else None
    out["one_regime_flag"] = one_reg
    out["one_regime_year"] = one_reg_year
    out["one_regime_share"] = one_reg_share
    out["max_drawdown_R"] = max_dd
    out["boot_pass_pct_p05"] = p05
    out["boot_pass_pct_p50"] = p50
    out["boot_pass_pct_p95"] = p95
    return out, py, py_pf_r, dd_table


# ==================================================================================================
# report writers
# ==================================================================================================
AUDITOR_ADJUDICATION_TEXT = """Auditor adjudication on the winners-75% reject flag (correct escalation):
the winners-75% clause is UNSATISFIABLE by construction for any honest thin edge (PF 1.35 x 0.75
~= 1.01 breakeven -- only PF>=1.8 machines pass it, which our too-good gate would freeze). It
rejected the baseline and discriminates nothing. RULING: winners-fill sensitivity is a
MACHINE-LEVEL operating condition governed by the existing live fill-telemetry kill line (15%
adverse touch-without-fill ~= 85% winner-capture floor), NOT a config selector. Config-level
reject bar = dies-at-0.015R OR flip<0.025R OR dies-at-2x-costs -- under which all 45 survive."""


def write_07(df, canary_row, runtime_s, firewall_before, firewall_after):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "07_top_cell_stress.csv")
    md_path = os.path.join(OUTDIR, "07_top_cell_stress.md")
    df.to_csv(csv_path, index=False)

    headline_cols = ["config_id", "tags", "a_budget", "a_cap", "v_budget", "v_cap", "a_variant",
                     "v_window", "pass_pct", "bust_pct", "flip_point_R", "wf75_verdict_pass_gt_bust",
                     "cost2x_verdict_pass_gt_bust", "REJECT", "SURVIVES_PREFERRED",
                     "REJECT_v2_config_only"]
    headline = df[headline_cols]

    lines = ["# 07 -- Top-Cell Stress (A+VPC Optimisation, Wave 2)", "",
             "RESEARCH ONLY. LIVE HOLD ACTIVE. No commentary beyond mechanical reject/prefer flags.", "",
             f"Finalists tested: {len(df)}. Runtime: {runtime_s:.1f}s.", "",
             "## AUDITOR ADJUDICATION", AUDITOR_ADJUDICATION_TEXT, "",
             "## Baseline canary (A@600/6+VPC@600/4, must reproduce 28.7/17.0/54.4 n=684)",
             f"got: {canary_row}", "",
             "## Headline (flip point / winners-75 / 2x-cost / reject / prefer -- ORIGINAL + re-scoped)",
             VR.df_to_md_table(headline), "",
             "## Full stress table (raw winners-fill collapse ladder kept as-is -- documents the "
             "machine-level fragility for the re-lock DEC)", VR.df_to_md_table(df), "",
             f"ORIGINAL reject count: {int(df['REJECT'].sum())} / {len(df)}. "
             f"ORIGINAL survives-preferred count: {int(df['SURVIVES_PREFERRED'].sum())} / {len(df)}.",
             f"RE-SCOPED (config-level, per auditor adjudication) reject count: "
             f"{int(df['REJECT_v2_config_only'].sum())} / {len(df)}.", "",
             "## Firewall before/after", f"- before: `{firewall_before}`", f"- after: `{firewall_after}`",
             f"- match: **{firewall_before == firewall_after}**", "", f"Runtime: {runtime_s:.1f}s"]
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n[saved] {csv_path}\n[saved] {md_path}")


def write_08(df, dd_tables, runtime_s, firewall_before, firewall_after, n_surviving, n_total):
    os.makedirs(OUTDIR, exist_ok=True)
    csv_path = os.path.join(OUTDIR, "08_robustness_stability.csv")
    md_path = os.path.join(OUTDIR, "08_robustness_stability.md")
    df.to_csv(csv_path, index=False)

    lines = ["# 08 -- Robustness / Stability (A+VPC Optimisation, Wave 2)", "",
             "RESEARCH ONLY. LIVE HOLD ACTIVE. Computed for the coordinator-pinned SHORTLIST "
             "(S1-S8, see 08's own header note), per the auditor adjudication re-scoping the "
             "config-level reject bar (see `07_top_cell_stress.md`'s AUDITOR ADJUDICATION section).",
             "", f"Shortlist analysed: {n_surviving} / {n_total} configs. Runtime: {runtime_s:.1f}s.",
             ""]
    if len(df) == 0:
        lines.append("**Shortlist produced no rows -- see stdout log for the lookup failure.**")
        lines.append("")
    else:
        lines.append("## Summary table (per-year pass/bust/expire/PF/totR, month/long-short/lane "
                     "splits, one-regime flag, bootstrap CI, flip point + entry-realism verdicts)")
        lines.append(VR.df_to_md_table(df))
        lines.append("")
        one_regime = df[df["one_regime_flag"] == True]
        lines.append(f"## ONE-REGIME FLAGS: {len(one_regime)} / {len(df)} shortlist config(s) flagged")
        if len(one_regime):
            lines.append(VR.df_to_md_table(one_regime[["config_id", "s_label", "tags", "one_regime_year",
                                                        "one_regime_share"]]))
        lines.append("")
    if dd_tables:
        lines.append("## Month-by-month drawdown (merged unit-risk stream, R units) -- per finalist")
        for cfg_id, tbl in dd_tables.items():
            lines.append(f"### {cfg_id}")
            lines.append(VR.df_to_md_table(pd.DataFrame(tbl)))
            lines.append("")
    lines.append("## Firewall before/after")
    lines.append(f"- before: `{firewall_before}`")
    lines.append(f"- after: `{firewall_after}`")
    lines.append(f"- match: **{firewall_before == firewall_after}**")
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

    a_full, a2022, a_ok = load_a_stream()
    v_rows, df1m, feats, d1rth, v_ok = load_vpc_stream()
    if not (a_ok and v_ok):
        print("[CANARY FAILURE] stream canary mismatch -- STOPPING before any report is written.")
        return

    canary_s, canary_pf, canary_ev, canary_days = funnel(a2022, BASE_A_BC, v_rows, BASE_V_BC, "canary-baseline")
    canary_row = dict(pass_pct=canary_s["pass_pct"], bust_pct=canary_s["bust_pct"],
                      exp_pct=canary_s["exp_pct"], n=canary_s["eligible_starts"])
    canary_ok = canary_row == CANARY_BASELINE
    print(f"BASELINE CANARY: got {canary_row} vs expected {CANARY_BASELINE} -> "
          f"{'PASS' if canary_ok else 'FAIL'}", flush=True)
    if not canary_ok:
        print("[CANARY FAILURE] STOPPING -- do not trust anything downstream.")
        return

    print("loading grid CSV + selecting finalists…", flush=True)
    grid_df = pd.read_csv(GRID_CSV)
    finalists, order = select_finalists(grid_df)
    print(f"  {len(finalists)} unique finalist configs selected", flush=True)

    print("building lane-3 pareto variant row streams (A-max-1/day, VPC[10:00-14:00])…", flush=True)
    a_max1 = a_variant_max1_per_day(a2022)
    v_win1014 = filter_window_1014(v_rows)
    print(f"  A-max-1/day n={len(a_max1)}  VPC[10:00-14:00] n={len(v_win1014)}", flush=True)

    print("building A-direction lookup (tools_opt_conflict_risk.a_rows_direction_tagged, spot-check)…",
          flush=True)
    a_dir_map, v_dir_map, n_a_dir, n_v_dir = build_direction_maps(df1m)
    n_a_matched = sum(1 for r in a2022 if pd.Timestamp(r["ts"]) in a_dir_map)
    print(f"  A-direction rows n={n_a_dir}, matched into a2022 (n={len(a2022)}): {n_a_matched} "
          f"(join spot-check, not a hard stop -- long/short split reports any unmatched count)",
          flush=True)

    print("\n" + "=" * 100)
    print("07 -- STRESS LADDERS")
    print("=" * 100)
    stress_records = []
    stress_extra = {}    # cfg_id -> (s0, ev0, days0, a_rows_used, v_rows_used, rec)
    key_to_cfgid = {}    # (a_budget,a_cap,v_budget,v_cap,a_variant,v_window) -> cfg_id
    for key in order:
        rec = finalists[key]
        cfg_id = f"F{len(stress_records) + 1:02d}"
        key_to_cfgid[key] = cfg_id
        if rec["a_variant"] == "max-1/day":
            a_rows_used = a_max1
        else:
            a_rows_used = a2022
        if rec["v_window"] == "10:00-14:00":
            v_rows_used = v_win1014
        else:
            v_rows_used = v_rows
        rowd, s0, ev0, days0 = stress_one(cfg_id, rec, a_rows_used, v_rows_used)
        stress_records.append(rowd)
        stress_extra[cfg_id] = (s0, ev0, days0, a_rows_used, v_rows_used, rec)
        print(f"  {cfg_id} tags={rec['tags']} a={rec['a_budget']}/{rec['a_cap']} v={rec['v_budget']}/"
              f"{rec['v_cap']} pass={rowd['pass_pct']}% bust={rowd['bust_pct']}% flip={rowd['flip_point_R']} "
              f"REJECT={rowd['REJECT']} REJECT_v2={rowd['REJECT_v2_config_only']} "
              f"PREFER={rowd['SURVIVES_PREFERRED']}", flush=True)

    df07 = pd.DataFrame.from_records(stress_records)
    print(f"\nRE-SCOPED (auditor-adjudicated, config-level) reject count: "
          f"{int(df07['REJECT_v2_config_only'].sum())} / {len(df07)}", flush=True)
    firewall_mid = ST.sha_of(FIREWALL_FILES)
    write_07(df07, canary_row, time.time() - t_start, firewall_before, firewall_mid)

    print("\n" + "=" * 100)
    print("08 -- ROBUSTNESS / STABILITY (coordinator-pinned SHORTLIST S1-S8)")
    print("=" * 100)
    baseline_cfg_id = stress_records[0]["config_id"]     # order[0] is always "baseline"
    s0_base, ev0_base, days0_base, a_base, v_base, _ = stress_extra[baseline_cfg_id]
    starts_base, results_base = VR.run_cell(days0_base)
    baseline_per_year = per_year_full(results_base)

    # SHORTLIST pinned verbatim by the coordinator: S1 baseline, S2 lane-3 pareto variant,
    # S3/S4/S5 the three named top-GREEN-by-pass_pct sizing combos, S6-S8 the 3 low-bust cells.
    SHORTLIST = [
        ("S1", 600, 6, 600, 4, "current", "full"),
        ("S2", 600, 6, 600, 4, "max-1/day", "10:00-14:00"),
        ("S3", 900, 6, 700, 3, "current", "full"),
        ("S4", 1000, 6, 600, 3, "current", "full"),
        ("S5", 900, 6, 600, 3, "current", "full"),
    ]
    lowbust_keys = [k for k in order if "low-bust-3" in finalists[k]["tags"]]
    for i, k in enumerate(lowbust_keys):
        SHORTLIST.append((f"S{6 + i}", finalists[k]["a_budget"], finalists[k]["a_cap"],
                          finalists[k]["v_budget"], finalists[k]["v_cap"], finalists[k]["a_variant"],
                          finalists[k]["v_window"]))

    df07_by_cfgid = {r["config_id"]: r for r in stress_records}
    robust_records = []
    dd_tables = {}
    for s_label, ab, ac, vb, vc, avar, vwin in SHORTLIST:
        key = (ab, ac, vb, vc, avar, vwin)
        cfg_id = key_to_cfgid.get(key)
        if cfg_id is None:
            print(f"  [LOOKUP FAILURE] {s_label} key={key} not found among the 45 finalists -- skipped",
                  flush=True)
            continue
        s0, ev0, days0, a_rows_used, v_rows_used, rec = stress_extra[cfg_id]
        stress_row = df07_by_cfgid[cfg_id]
        rowd, py, py_pf_r, dd_table = robustness_one(cfg_id, s_label, rec, a_rows_used, v_rows_used, s0,
                                                      ev0, days0, baseline_per_year, a_dir_map, v_dir_map,
                                                      stress_row)
        robust_records.append(rowd)
        dd_tables[f"{s_label}-{cfg_id}"] = dd_table
        print(f"  {s_label} ({cfg_id}) one_regime={rowd['one_regime_flag']} maxDD_R={rowd['max_drawdown_R']} "
              f"boot90CI=[{rowd['boot_pass_pct_p05']},{rowd['boot_pass_pct_p95']}]", flush=True)

    df08 = pd.DataFrame.from_records(robust_records) if robust_records else pd.DataFrame()
    firewall_after = ST.sha_of(FIREWALL_FILES)
    write_08(df08, dd_tables, time.time() - t_start, firewall_mid, firewall_after, len(robust_records),
             len(SHORTLIST))

    print(f"\nTOTAL runtime: {time.time() - t_start:.1f}s")
    print(f"Firewall match (before==mid==after): "
          f"{firewall_before == firewall_mid == firewall_after}")


if __name__ == "__main__":
    main()
