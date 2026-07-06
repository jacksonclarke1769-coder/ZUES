"""tools_a_sizing_geometry_sweep.py — A-ONLY SIZING GEOMETRY MONTE-CARLO SWEEP.

RESEARCH ONLY. LIVE HOLD ACTIVE. Pure mechanical execution of pinned formulas over the FROZEN
trade streams below — no edge/filter/exit discovery, no config/DEC/register/live edits, no
commits. Every statistical decision (grids, tolerances, formulas, thresholds) is pre-decided by
the task brief; this script computes and reports numbers/flags only — it makes NO verdict or
recommendation (the auditor writes those).

STAGE 0 — HONESTY GUARDS: asserted in `stage0_asserts()` (pandas major==2; the shared exit walker
`tools_1m_truth_recert.walk_1m` — reused verbatim via `tools_salvage_funded_exits.walk_exit3` /
`walk_fixed_r` for Exit#3 / Fixed-1.5R respectively — contains no trailing-stop path (`trail` /
`hi_since` absent from its source, unlike the separate, UNUSED `walk_trail_after_1r` variant in
`tools_salvage_funded_exits.py`) and resolves an adverse (stop) touch before any favorable
(partial/target) touch on the same bar (stop-first ordering, confirmed via source-position
assertion). Abort on any assertion failure — this is the Asian-Range PF-2.03 look-ahead-artifact
guard from `reference_lookahead_bias_check`.

STAGE 1 — FOUR FROZEN STREAMS: raw A signal params (entry/stop/model-target/fill_bar) for ALL 705
NY-AM A signals are derived exactly the way `tools_salvage_funded_exits.kept_raw_trades()` does
(same engine/feature/D1c-attach pipeline) but WITHOUT that function's `d1c_keep` filter — attaching
D1c only ADDS a `d1c_keep` column (`run_d1c_real.attach_drift`, `tr["d1c_keep"] = keep` on a full
copy) and drops no rows, so this reproduces the same risk>0/valid-fill-bar population as
`tools_1m_truth_recert.a_streams()['exit3']` pre-walk (the canonical 705-signal 'unfiltered' set).
Each of the 705 raw signals is walked at 1m truth under BOTH exits (Exit#3 via `SFE.walk_exit3`;
Fixed-1.5R via `SFE.walk_fixed_r(1.5)`, both unmodified imports that call `H1M.walk_1m` verbatim).
KEPT subset (n=583) = the raw signals whose `ts` appears in `tools_sim_parity_check.load_rows()`'s
own ts set (an explicit ts-join against that stream, as instructed) — cross-checked against the
D1c-attach's own `d1c_keep` flag for an integrity sanity print (not a gating canary).

Four surfaces = {kept, unfiltered} x {Exit3, Fixed15}. Four canaries gate progression to Stage 2
(STOP on miss, tol +/-0.3R): kept-Exit3 totR=+89.2R (n=583); kept-Fixed15 totR=+96.9R (n=583);
unfiltered-Exit3 totR=+74.7R (n=705). unfiltered-Fixed15 has no prior canary -- reported only.

STAGE 2 — GEOMETRY GRID: 36 cells/surface (cap in {2,3,4,5,6,8,10,12,15} x budget in
{700,800,900,1000}) x 4 surfaces = 144 cells, via `tools_account_size_research`'s pinned,
unmodified `build_events`/`day_rows`/`eval_run` (cap = MAX_A_QTY per cell; `day_rows(ev, 550,
1000)`; eligible starts = unique trading days with >30-day forward runway, same convention as
`ASR.main()`/`tools_salvage_funded_exits.eval_funnel`). Point estimates only; per-cell bootstrap in
Stage 3.

STAGE 3 — BLOCK BOOTSTRAP CI: a stationary (Politis-Romano) block bootstrap resampling EVAL
STARTS (not trades), with a PER-CELL mean block length L = max(15, round(that cell's own mean
eval-terminal length in trading days)) -- an explicit interpretation of the brief's "compute it;
floor at 15" applied at the cell level (documented here since the brief does not pin whether L is
per-cell or per-surface; each cell's own terminal-length distribution is the honest driver of its
own outcome-series serial dependence). 2000 paths/cell, resampling the already-computed per-start
PASS/BUST/EXPIRE label sequence (no re-simulation of the underlying trade stream). Reports the
achieved 95% CI half-width (median across cells), plus EFFECTIVE-N two ways: (a) non-overlapping
tiling = trading_day_span / mean_terminal_days; (b) integrated-autocorrelation on the ordered
per-start PASS-indicator series (rho summed up to first negative lag). The smaller of the two is
headlined per the brief.

STAGE 4 — GUARDS + FRONTIER: MIRAGE flag (baseline = kept-Exit3 @ $900/cap-6) computed across all
144 cells; the joint multiple-comparisons frontier (CI-overlap with the max-pass% cell, MIRAGE
cells excluded); the live-config (kept-Exit3 @ $900/cap-6) in/out-of-frontier check; and the
MARGINAL Delta-pass/Delta-bust per added contract (per-contract normalized across the non-uniform
cap grid), reporting the first FLIP CONTRACT per (surface, budget) column where
Delta-bust/Delta-cap >= Delta-pass/Delta-cap.

OUTPUT: reports/a_only_sizing_sweep/2026-07-07_a_sizing_geometry.{csv,md}. No verdict language.
"""
import os
import sys
import time
import inspect
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strategy_engine_profileA as E        # noqa
import model01_sweep_mss_fvg as M1          # FROZEN model, read-only import          # noqa
import config                               # noqa
import run_d1c_real as RD                   # noqa
import apex_eval_eod_databento as DB        # noqa
import tools_1m_truth_recert as H1M         # prior art, READ-ONLY (walk_1m, M1Map, A_PARAMS, DPP)
import tools_sim_parity_check as SPC        # prior art, READ-ONLY (load_rows == the ts-join source)
import tools_salvage_funded_exits as SFE    # prior art, READ-ONLY (walk_exit3/walk_fixed_r/
                                             # build_variant_rows/variant_stats)
import tools_account_size_research as ASR   # prior art, READ-ONLY (build_events/day_rows/eval_run)
import tools_salvage_stress as TSS          # prior art, READ-ONLY (dmg_slip/find_flip)

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "a_only_sizing_sweep")
os.makedirs(OUTDIR, exist_ok=True)
CSV_PATH = os.path.join(OUTDIR, "2026-07-07_a_sizing_geometry.csv")
MD_PATH = os.path.join(OUTDIR, "2026-07-07_a_sizing_geometry.md")

CAPS = [2, 3, 4, 5, 6, 8, 10, 12, 15]
BUDGETS = [700, 800, 900, 1000]
STOP_50K, DLL_50K = 550.0, 1_000.0
SPEC_50K = dict(start=50_000.0, trail=2_500.0, target=3_000.0)      # ASR.SPECS["50K"] eval-relevant
EXPIRE_DAYS = ASR.EXPIRE_DAYS                                        # 30, imported not retyped
FEE_FLAT = 131.0                                                     # E_cost_per_attempt, pinned
SLIP_LADDER = [0.0, 0.01, 0.02, 0.03, 0.05, 0.075, 0.10]             # coarse ladder, R units
N_BOOT_PATHS = 2000
BOOT_SEED = 20260707
BASELINE_KEY = ("kept_exit3", 900, 6)                                 # pinned MIRAGE/live-config ref

CANARY_TOL_R = 0.3


# =================================================================================================
# STAGE 0 — HONESTY GUARDS
# =================================================================================================
def stage0_asserts():
    assert int(pd.__version__.split(".")[0]) == 2, f"pandas major must be 2, got {pd.__version__}"

    src_walk1m = inspect.getsource(H1M.walk_1m)
    assert "trail" not in src_walk1m and "hi_since" not in src_walk1m, (
        "walk_1m (the shared exit engine reused for Exit#3 and Fixed-1.5R) must not contain a "
        "trailing-stop path")
    i_stop = src_walk1m.index("# 1) stop first")
    i_partial = src_walk1m.index("# 2) partial scale-outs")
    i_target = src_walk1m.index("# 3) final target")
    assert i_stop < i_partial < i_target, (
        "walk_1m must resolve an adverse (stop) touch before any favorable (partial/target) "
        "touch within the same bar (stop-first ordering)")

    src_exit3 = inspect.getsource(SFE.walk_exit3)
    assert "trail" not in src_exit3 and "hi_since" not in src_exit3 and "H1M.walk_1m" in src_exit3, (
        "Exit#3 wrapper must be an unmodified pass-through to walk_1m with no trailing-stop branch")

    src_fixedr = inspect.getsource(SFE.walk_fixed_r)
    assert ("trail" not in src_fixedr and "hi_since" not in src_fixedr
            and "H1M.walk_1m" in src_fixedr), (
        "Fixed-R wrapper (used here for Fixed-1.5R) must be an unmodified pass-through to walk_1m "
        "with no trailing-stop branch")

    print("[STAGE 0] honesty guards OK: pandas major==2; walk_1m has no trailing-stop path "
          "(no 'trail'/'hi_since' token); stop-first ordering confirmed by source position; "
          "Exit#3 and Fixed-1.5R wrappers are unmodified pass-throughs to walk_1m -- the trail "
          "branch (only present in the separate, unused walk_trail_after_1r variant) is "
          "unreachable for these two exits.")


# =================================================================================================
# STAGE 1 — FOUR FROZEN STREAMS + INTEGRITY CANARIES
# =================================================================================================
def build_raw_all():
    """ALL NY-AM A signals (n=705, NOT gated on d1c_keep), same row shape as
    `tools_salvage_funded_exits.kept_raw_trades()` (ts, d, entry, stop, target_model, risk,
    risk_usd, fb) plus the d1c_keep flag (for the integrity cross-check only -- KEPT membership
    below is decided by the ts-join against `tools_sim_parity_check.load_rows()`, per the brief).
    `attach_drift` only ADDS a column (`tr["d1c_keep"] = keep` on a full copy); it drops no rows,
    so this reproduces the same risk>0/valid-fill-bar population as
    `tools_1m_truth_recert.a_streams()['exit3']` pre-walk."""
    d1_tz = RD.load_1m()
    d1 = d1_tz.copy()
    d1.index = d1_tz.index.tz_localize(None)
    df5 = DB.load_databento_5m()
    mp = H1M.M1Map(d1, df5)
    eng = E.ProfileAEngine(config.STRAT)
    eng.buf = df5
    feats = eng._features()
    params = H1M.A_PARAMS["exit3"]
    tr = M1.run(feats, "NQ", params)
    tr = tr[tr.session == "ny_am"].copy()
    tr = RD.attach_drift(tr, d1_tz, feats.index)
    fi = feats.index
    n5 = len(fi)
    raw = []
    for _, t in tr.iterrows():
        risk = abs(float(t.entry) - float(t.stop))
        fb = int(t.fill_bar)
        if risk <= 0 or not (0 <= fb < n5):
            continue
        d = 1 if t.direction == "long" else -1
        raw.append(dict(ts=pd.Timestamp(fi[fb]), d=d, entry=float(t.entry), stop=float(t.stop),
                         target_model=float(t.target), risk=risk, risk_usd=risk * H1M.DPP, fb=fb,
                         d1c_keep=bool(t["d1c_keep"])))
    return raw, mp


def canary_check(label, got_n, got_totR, exp_n, exp_totR, tol=CANARY_TOL_R, report_only=False):
    if report_only:
        print(f"  CANARY {label} (no prior peg, REPORT ONLY): n={got_n} totR={got_totR:+.1f}R")
        return True
    ok = (got_n == exp_n) and (abs(got_totR - exp_totR) <= tol)
    print(f"  CANARY {label}: got n={got_n} totR={got_totR:+.1f}R  |  expect n={exp_n} "
          f"totR={exp_totR:+.1f}R (tol +/-{tol}R)  ->  {'OK' if ok else 'STOP-MISMATCH'}")
    return ok


def build_streams():
    print("\n=== STAGE 1 — building four frozen streams ===", flush=True)
    raw_all, mp = build_raw_all()
    print(f"  raw_all (all NY-AM A signals, risk>0 + valid fill bar): n={len(raw_all)}", flush=True)

    kept_stream_rows = SPC.load_rows()
    kept_ts_set = set(pd.Timestamp(t["ts"]) for t in kept_stream_rows)
    print(f"  tools_sim_parity_check.load_rows() ts set: n={len(kept_ts_set)}", flush=True)

    d1c_true_ts = set(r["ts"] for r in raw_all if r["d1c_keep"])
    join_match = (d1c_true_ts == kept_ts_set)
    print(f"  [integrity] d1c_keep-flag ts set == SPC.load_rows() ts-join set: {join_match} "
          f"(flag n={len(d1c_true_ts)}, join n={len(kept_ts_set)})", flush=True)

    kept_raw = [r for r in raw_all if r["ts"] in kept_ts_set]
    print(f"  kept_raw (ts-joined against tools_sim_parity_check.load_rows()): n={len(kept_raw)}",
          flush=True)

    unfiltered_exit3 = SFE.build_variant_rows(raw_all, mp, SFE.walk_exit3)
    unfiltered_fixed15 = SFE.build_variant_rows(raw_all, mp, SFE.walk_fixed_r(1.5))
    kept_exit3 = SFE.build_variant_rows(kept_raw, mp, SFE.walk_exit3)
    kept_fixed15 = SFE.build_variant_rows(kept_raw, mp, SFE.walk_fixed_r(1.5))

    if len(unfiltered_exit3) != len(unfiltered_fixed15):
        print(f"  [FINDING] unfiltered-Exit3 n={len(unfiltered_exit3)} != unfiltered-Fixed15 "
              f"n={len(unfiltered_fixed15)} -- the fill gate was expected to be exit-rule-"
              f"independent (entry-fill depends only on entry/direction); reporting as-is.",
              flush=True)
    if len(kept_exit3) != len(kept_fixed15):
        print(f"  [FINDING] kept-Exit3 n={len(kept_exit3)} != kept-Fixed15 n={len(kept_fixed15)} "
              f"-- same expectation as above; reporting as-is.", flush=True)

    s_kept_e3 = SFE.variant_stats(kept_exit3)
    s_kept_f15 = SFE.variant_stats(kept_fixed15)
    s_unf_e3 = SFE.variant_stats(unfiltered_exit3)
    s_unf_f15 = SFE.variant_stats(unfiltered_fixed15)

    print("\n  --- canaries (STOP on any pinned mismatch) ---", flush=True)
    ok1 = canary_check("kept-Exit3", s_kept_e3["n"], s_kept_e3["totR"], 583, 89.2)
    ok2 = canary_check("kept-Fixed1.5R", s_kept_f15["n"], s_kept_f15["totR"], 583, 96.9)
    ok3 = canary_check("unfiltered-Exit3", s_unf_e3["n"], s_unf_e3["totR"], 705, 74.7)
    canary_check("unfiltered-Fixed1.5R", s_unf_f15["n"], s_unf_f15["totR"], None, None,
                 report_only=True)
    print(f"    (sanity note only, not gated: unfiltered-Fixed15 totR={s_unf_f15['totR']:+.1f}R "
          f"vs unfiltered-Exit3's pinned +74.7R -- expected modestly above if the kept pattern "
          f"holds)", flush=True)

    canary_lines = [
        f"kept-Exit3: n={s_kept_e3['n']} totR={s_kept_e3['totR']:+.1f}R (expect n=583 totR=+89.2R)",
        f"kept-Fixed1.5R: n={s_kept_f15['n']} totR={s_kept_f15['totR']:+.1f}R "
        f"(expect n=583 totR=+96.9R)",
        f"unfiltered-Exit3: n={s_unf_e3['n']} totR={s_unf_e3['totR']:+.1f}R "
        f"(expect n=705 totR=+74.7R)",
        f"unfiltered-Fixed1.5R: n={s_unf_f15['n']} totR={s_unf_f15['totR']:+.1f}R "
        f"(no prior canary -- report only)",
        f"integrity: d1c_keep-flag ts set == SPC.load_rows() ts-join set: {join_match}",
    ]

    if not (ok1 and ok2 and ok3):
        print("\n[STAGE 1 STOP] a pinned canary mismatched -- aborting before Stage 2 sizing.",
              flush=True)
        return None, canary_lines

    surfaces = dict(kept_exit3=kept_exit3, kept_fixed15=kept_fixed15,
                     unfiltered_exit3=unfiltered_exit3, unfiltered_fixed15=unfiltered_fixed15)
    return surfaces, canary_lines


# =================================================================================================
# STAGE 2 — GEOMETRY GRID (point estimates)
# =================================================================================================
def sizing_cell(rows, budget, cap):
    """Point estimates for one (rows-surface, budget, cap) cell via ASR's pinned, unmodified
    `build_events`/`day_rows`/`eval_run`. Returns the per-start PASS/BUST/EXPIRE label array too
    (consumed by Stage 3's bootstrap -- no re-simulation there)."""
    ev = ASR.build_events(rows, budget, cap)
    days = ASR.day_rows(ev, STOP_50K, DLL_50K)
    if not days:
        return dict(eligible_starts=0, pass_pct=0.0, bust_pct=0.0, exp_pct=0.0, pass_count=0,
                     mean_terminal_days=None, funded_per_slot_year=0.0, attempts_per_pass=None,
                     fee_per_pass=None, labels=np.array([]), trading_day_span=0)
    last_day = days[-1][0]
    starts = [i for i, (d, _, _) in enumerate(days) if (last_day - d).days > EXPIRE_DAYS]
    res = [ASR.eval_run(days, s, SPEC_50K) for s in starts]
    n = len(res)
    if n == 0:
        return dict(eligible_starts=0, pass_pct=0.0, bust_pct=0.0, exp_pct=0.0, pass_count=0,
                     mean_terminal_days=None, funded_per_slot_year=0.0, attempts_per_pass=None,
                     fee_per_pass=None, labels=np.array([]), trading_day_span=len(days))
    labels = np.array([r[0] for r in res])
    days_arr = np.array([r[1] for r in res], float)
    pass_count = int((labels == "PASS").sum())
    bust_count = int((labels == "BUST").sum())
    exp_count = int((labels == "EXPIRE").sum())
    mean_terminal_days = float(days_arr.mean())
    pass_pct = 100.0 * pass_count / n
    bust_pct = 100.0 * bust_count / n
    exp_pct = 100.0 * exp_count / n
    fpsy = (365.25 / mean_terminal_days) * (pass_count / n) if mean_terminal_days else 0.0
    attempts_per_pass = (n / pass_count) if pass_count > 0 else None
    fee_per_pass = (FEE_FLAT / (pass_count / n)) if pass_count > 0 else None
    return dict(eligible_starts=n, pass_pct=round(pass_pct, 2), bust_pct=round(bust_pct, 2),
                exp_pct=round(exp_pct, 2), pass_count=pass_count,
                mean_terminal_days=round(mean_terminal_days, 3),
                funded_per_slot_year=round(fpsy, 4),
                attempts_per_pass=(round(attempts_per_pass, 3)
                                   if attempts_per_pass is not None else None),
                fee_per_pass=(round(fee_per_pass, 2) if fee_per_pass is not None else None),
                labels=labels, trading_day_span=len(days))


def slippage_flip(rows, budget, cap):
    """SLIPPAGE FLIP metric: interpolated uniform-R damage at which pass% <= bust%, reusing
    `tools_salvage_stress.dmg_slip` (rows-level uniform slippage) + `find_flip` (linear
    interpolation of margin=pass_pct-bust_pct across the ladder) verbatim."""
    pts = []
    for s in SLIP_LADDER:
        rows_s = TSS.dmg_slip(rows, s)
        c = sizing_cell(rows_s, budget, cap)
        margin = None if c["eligible_starts"] == 0 else (c["pass_pct"] - c["bust_pct"])
        pts.append((s, margin))
    return TSS.find_flip(pts)


# =================================================================================================
# STAGE 3 — BLOCK BOOTSTRAP CI + EFFECTIVE-N
# =================================================================================================
def stationary_bootstrap_ci(labels, L, n_paths, rng):
    """Politis-Romano stationary bootstrap over ORDERED eval-start outcome labels (circular block
    resampling, geometric block lengths with mean L). Returns {label: (ci_lo, ci_hi)} at 95%."""
    cats = ["PASS", "BUST", "EXPIRE"]
    N = len(labels)
    if N == 0:
        return {c: (0.0, 0.0) for c in cats}
    p = 1.0 / max(L, 1)
    labels = np.asarray(labels)
    counts = {c: np.empty(n_paths) for c in cats}
    for pi in range(n_paths):
        segs = []
        total = 0
        while total < N:
            s = int(rng.integers(0, N))
            blen = min(int(rng.geometric(p)), N)
            if s + blen <= N:
                seg = labels[s:s + blen]
            else:
                seg = np.concatenate([labels[s:], labels[:(s + blen - N)]])
            segs.append(seg)
            total += blen
        arr = np.concatenate(segs)[:N]
        for c in cats:
            counts[c][pi] = 100.0 * float(np.mean(arr == c))
    return {c: (round(float(np.percentile(counts[c], 2.5)), 2),
                round(float(np.percentile(counts[c], 97.5)), 2)) for c in cats}


def autocorr_at_lag(x, k):
    x = np.asarray(x, float)
    n = len(x)
    if k >= n:
        return 0.0
    xm = x - x.mean()
    denom = float(np.sum(xm ** 2))
    if denom == 0.0:
        return 0.0
    num = float(np.sum(xm[:n - k] * xm[k:]))
    return num / denom


def n_eff_integrated_autocorr(pass_ind):
    n = len(pass_ind)
    if n < 2:
        return float(n)
    s = 0.0
    for k in range(1, n):
        r = autocorr_at_lag(pass_ind, k)
        if r < 0:
            break
        s += r
    denom = 1.0 + 2.0 * s
    return float(n) / denom if denom > 0 else float(n)


# =================================================================================================
# MAIN GRID RUNNER
# =================================================================================================
def run_grid(surfaces):
    print("\n=== STAGE 2/3 — 36 cells/surface x 4 surfaces = 144 cells "
          "(point estimates + block-bootstrap CI + effective-N) ===", flush=True)
    rng = np.random.default_rng(BOOT_SEED)
    cells = {}
    t0 = time.time()
    for surface, rows in surfaces.items():
        for budget in BUDGETS:
            for cap in CAPS:
                c = sizing_cell(rows, budget, cap)
                L = max(15, round(c["mean_terminal_days"])) if c["mean_terminal_days"] else 15
                ci = stationary_bootstrap_ci(c["labels"], L, N_BOOT_PATHS, rng)
                pass_ind = (c["labels"] == "PASS").astype(float)
                n_eff_tiling = (c["trading_day_span"] / c["mean_terminal_days"]
                                if c["mean_terminal_days"] else 0.0)
                n_eff_iac = n_eff_integrated_autocorr(pass_ind)
                n_eff_headline = min(n_eff_tiling, n_eff_iac) if c["mean_terminal_days"] else 0.0
                flip = slippage_flip(rows, budget, cap)
                key = (surface, budget, cap)
                cells[key] = dict(
                    surface=surface, budget=budget, cap=cap,
                    eligible_starts=c["eligible_starts"], pass_pct=c["pass_pct"],
                    bust_pct=c["bust_pct"], exp_pct=c["exp_pct"], pass_count=c["pass_count"],
                    mean_terminal_days=c["mean_terminal_days"],
                    funded_per_slot_year=c["funded_per_slot_year"],
                    attempts_per_pass=c["attempts_per_pass"], e_cost_per_attempt=FEE_FLAT,
                    fee_per_pass=c["fee_per_pass"], slippage_flip_R=flip,
                    block_length_L=L, pass_ci_lo=ci["PASS"][0], pass_ci_hi=ci["PASS"][1],
                    bust_ci_lo=ci["BUST"][0], bust_ci_hi=ci["BUST"][1],
                    exp_ci_lo=ci["EXPIRE"][0], exp_ci_hi=ci["EXPIRE"][1],
                    n_eff_tiling=round(n_eff_tiling, 1), n_eff_iac=round(n_eff_iac, 1),
                    n_eff_headline=round(n_eff_headline, 1),
                    trading_day_span=c["trading_day_span"],
                )
        print(f"  [{surface}] 36 cells done ({time.time()-t0:.1f}s elapsed)", flush=True)
    return cells


# =================================================================================================
# STAGE 4 — GUARDS + FRONTIER
# =================================================================================================
def stage4(cells):
    print("\n=== STAGE 4 — guards + frontier ===", flush=True)
    baseline = cells[BASELINE_KEY]

    # ---- eligible-starts invariance (per surface) ----
    inv = {}
    for surface in {k[0] for k in cells}:
        vals = sorted({cells[k]["eligible_starts"] for k in cells if k[0] == surface})
        inv[surface] = vals
        const = (len(vals) == 1)
        print(f"  [invariance] surface={surface}: eligible_starts distinct values={vals} "
              f"-> {'CONSTANT' if const else 'NOT CONSTANT (finding)'}", flush=True)

    # ---- MIRAGE ----
    mirage_keys = []
    for k, c in cells.items():
        if c["pass_pct"] > baseline["pass_pct"] and c["pass_count"] < baseline["pass_count"]:
            mirage_keys.append(k)
    mirage_moot = all(len(v) == 1 for v in inv.values())
    print(f"  [MIRAGE] baseline={BASELINE_KEY} pass%={baseline['pass_pct']} "
          f"pass_count={baseline['pass_count']}; flagged cells: {len(mirage_keys)} {mirage_keys}",
          flush=True)
    print(f"  [MIRAGE structural check] eligible_starts constant within every surface: "
          f"{mirage_moot} -> if True, pass_count is proportional to pass% within a surface, so "
          f"MIRAGE (pass% up, pass_count down) is structurally unreachable WITHIN a surface; only "
          f"cross-surface comparisons (different eligible_starts) can produce it.", flush=True)

    # ---- joint multiple-comparisons frontier ----
    candidates = {k: c for k, c in cells.items() if k not in mirage_keys}
    top_key = max(candidates, key=lambda k: candidates[k]["pass_pct"])
    top = candidates[top_key]
    top_lo, top_hi = top["pass_ci_lo"], top["pass_ci_hi"]
    frontier_keys = [k for k, c in candidates.items()
                     if not (c["pass_ci_hi"] < top_lo or c["pass_ci_lo"] > top_hi)]
    frontier_keys.sort(key=lambda k: -candidates[k]["pass_pct"])
    print(f"  [FRONTIER] top cell={top_key} pass%={top['pass_pct']} "
          f"CI=({top_lo},{top_hi}); indistinguishable frontier count={len(frontier_keys)}",
          flush=True)

    # ---- live-config check ----
    live_in_frontier = BASELINE_KEY in frontier_keys
    print(f"  [LIVE-CONFIG] kept_exit3/$900/cap-6 pass%={baseline['pass_pct']} "
          f"CI=({baseline['pass_ci_lo']},{baseline['pass_ci_hi']})  in frontier: "
          f"{live_in_frontier}  (frontier band from top cell: ({top_lo},{top_hi}))", flush=True)

    # ---- MARGINAL / flip contract, per (surface, budget) column ----
    marginal_rows = []
    flip_contracts = {}
    for surface in {k[0] for k in cells}:
        for budget in BUDGETS:
            col = [(cap, cells[(surface, budget, cap)]) for cap in CAPS]
            flip_cap = None
            for i in range(1, len(col)):
                cap0, c0 = col[i - 1]
                cap1, c1 = col[i]
                dcap = cap1 - cap0
                dpass = (c1["pass_pct"] - c0["pass_pct"]) / dcap
                dbust = (c1["bust_pct"] - c0["bust_pct"]) / dcap
                marginal_rows.append(dict(surface=surface, budget=budget, cap_from=cap0,
                                          cap_to=cap1, dpass_per_contract=round(dpass, 4),
                                          dbust_per_contract=round(dbust, 4)))
                if flip_cap is None and dbust >= dpass:
                    flip_cap = cap1
            flip_contracts[(surface, budget)] = flip_cap
            print(f"  [MARGINAL] surface={surface} budget={budget} flip_contract="
                  f"{flip_cap if flip_cap is not None else 'not observed within tested grid'}",
                  flush=True)

    return dict(invariance=inv, mirage_keys=mirage_keys, mirage_moot=mirage_moot,
                top_key=top_key, frontier_keys=frontier_keys, live_in_frontier=live_in_frontier,
                marginal_rows=marginal_rows, flip_contracts=flip_contracts)


# =================================================================================================
# OUTPUT
# =================================================================================================
CSV_COLS = ["surface", "budget", "cap", "eligible_starts", "pass_pct", "bust_pct", "exp_pct",
            "pass_count", "mean_terminal_days", "funded_per_slot_year", "attempts_per_pass",
            "e_cost_per_attempt", "fee_per_pass", "slippage_flip_R", "block_length_L",
            "pass_ci_lo", "pass_ci_hi", "bust_ci_lo", "bust_ci_hi", "exp_ci_lo", "exp_ci_hi",
            "n_eff_tiling", "n_eff_iac", "n_eff_headline", "trading_day_span", "mirage_flag"]


def write_csv(cells, mirage_keys):
    lines = [",".join(CSV_COLS)]
    for k in sorted(cells, key=lambda k: (k[0], k[1], k[2])):
        c = cells[k]
        row = [c.get(col, "") for col in CSV_COLS[:-1]]
        row.append(k in mirage_keys)
        lines.append(",".join(str(x) for x in row))
    with open(CSV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")


def _fmt(v):
    return "-" if v is None else v


def write_md(cells, s4, canary_lines, runtime_s):
    md = []
    md.append("# A-Only Sizing Geometry Monte-Carlo Sweep\n")
    md.append("**SIM-OPTIMAL under current fill model -- NOT real pass probability; gated on "
               "N>=30 live fills.**\n")
    md.append("RESEARCH ONLY. LIVE HOLD ACTIVE. Pure mechanical execution of pinned formulas over "
               "FROZEN trade streams -- no edge/filter/exit discovery, no config/DEC/register/live "
               "edits, no commits. Numbers/flags only; no verdict language.\n")
    md.append(f"Runtime: {runtime_s:.1f}s.\n")

    md.append("## Canaries (Stage 1)\n")
    for line in canary_lines:
        md.append(f"- {line}")
    md.append("")

    md.append("## Cells sorted by pass% desc (all 144)\n")
    cols = ["surface", "budget", "cap", "eligible_starts", "pass_pct", "bust_pct", "exp_pct",
            "pass_ci_lo", "pass_ci_hi", "pass_count", "mean_terminal_days",
            "funded_per_slot_year", "attempts_per_pass", "fee_per_pass", "slippage_flip_R",
            "n_eff_tiling", "n_eff_iac", "n_eff_headline"]
    md.append("| " + " | ".join(cols) + " |")
    md.append("|" + "---|" * len(cols))
    for k in sorted(cells, key=lambda k: -cells[k]["pass_pct"]):
        c = cells[k]
        md.append("| " + " | ".join(str(_fmt(c.get(col))) for col in cols) + " |")
    md.append("")

    md.append("## SUMMARY (mechanical -- numbers/flags only, no recommendation)\n")

    md.append("### Effective-N\n")
    all_tiling = [c["n_eff_tiling"] for c in cells.values()]
    all_iac = [c["n_eff_iac"] for c in cells.values()]
    all_headline = [c["n_eff_headline"] for c in cells.values()]
    md.append(f"- non-overlapping tiling (trading_day_span / mean_terminal_days): median="
              f"{np.median(all_tiling):.1f}, range=({min(all_tiling):.1f}, {max(all_tiling):.1f})")
    md.append(f"- integrated-autocorrelation (N_starts / (1+2*sum(rho))): median="
              f"{np.median(all_iac):.1f}, range=({min(all_iac):.1f}, {max(all_iac):.1f})")
    md.append(f"- HEADLINE (smaller of the two, per cell): median={np.median(all_headline):.1f}, "
              f"range=({min(all_headline):.1f}, {max(all_headline):.1f})")
    md.append("- this caps the cell-distinction fineness the sweep can honestly resolve.\n")

    md.append("### Block-bootstrap CI\n")
    all_hw = [(c["pass_ci_hi"] - c["pass_ci_lo"]) / 2.0 for c in cells.values()]
    md.append(f"- achieved 95% CI half-width for pass%, median across 144 cells: "
              f"{np.median(all_hw):.2f}pp (range {min(all_hw):.2f}-{max(all_hw):.2f}pp)")
    Ls = sorted({c["block_length_L"] for c in cells.values()})
    md.append(f"- per-cell mean block length L (Politis-Romano, floor 15): distinct values used = "
              f"{Ls}")
    md.append(f"- paths/cell: {N_BOOT_PATHS}\n")

    md.append("### Joint multiple-comparisons frontier\n")
    top = cells[s4["top_key"]]
    md.append(f"- top cell: surface={s4['top_key'][0]} budget={s4['top_key'][1]} "
              f"cap={s4['top_key'][2]}  pass%={top['pass_pct']} "
              f"CI=({top['pass_ci_lo']},{top['pass_ci_hi']})")
    md.append(f"- indistinguishable frontier count: {len(s4['frontier_keys'])}")
    md.append("| surface | budget | cap | pass% | CI |")
    md.append("|---|---|---|---|---|")
    for k in s4["frontier_keys"]:
        c = cells[k]
        md.append(f"| {k[0]} | {k[1]} | {k[2]} | {c['pass_pct']} | "
                  f"({c['pass_ci_lo']},{c['pass_ci_hi']}) |")
    md.append("")
    md.append(f"- live-config (kept_exit3/$900/cap-6) in frontier: {s4['live_in_frontier']}  "
              f"(pass%={cells[BASELINE_KEY]['pass_pct']}, frontier band from top cell: "
              f"({top['pass_ci_lo']},{top['pass_ci_hi']}))\n")

    md.append("### MIRAGE (denominator-artifact guard, DEC-20260706-1108)\n")
    md.append(f"- baseline = kept_exit3/$900/cap-6, pass%={cells[BASELINE_KEY]['pass_pct']}, "
              f"pass_count={cells[BASELINE_KEY]['pass_count']}")
    md.append(f"- MIRAGE-flagged cells (pass% > baseline AND pass_count < baseline): "
              f"{len(s4['mirage_keys'])} {s4['mirage_keys']}")
    md.append(f"- eligible-starts-invariance per surface: " +
              "; ".join(f"{s}={v}" for s, v in s4["invariance"].items()))
    md.append(f"- structurally-moot confirmation (eligible_starts constant within every surface, "
              f"so pass_count is proportional to pass% within a surface -> MIRAGE cannot fire "
              f"intra-surface): {s4['mirage_moot']}\n")

    md.append("### Per-column flip contracts (MARGINAL: first cap where "
              "Delta-bust/Delta-cap >= Delta-pass/Delta-cap)\n")
    md.append("| surface | budget | flip_contract |")
    md.append("|---|---|---|")
    for (surface, budget), flip in sorted(s4["flip_contracts"].items()):
        md.append(f"| {surface} | {budget} | "
                  f"{flip if flip is not None else 'not observed within tested grid'} |")
    md.append("")

    md.append("### kept-Fixed1.5R vs kept-Exit3 pass% delta at matched (budget, cap) cells\n")
    md.append("| budget | cap | kept_exit3 pass% | kept_fixed15 pass% | delta (fixed15-exit3) |")
    md.append("|---|---|---|---|---|")
    for budget in BUDGETS:
        for cap in CAPS:
            e3 = cells[("kept_exit3", budget, cap)]["pass_pct"]
            f15 = cells[("kept_fixed15", budget, cap)]["pass_pct"]
            md.append(f"| {budget} | {cap} | {e3} | {f15} | {round(f15 - e3, 2):+} |")
    md.append("")

    md.append("### unfiltered-vs-kept pass% delta per matched (surface-pair, budget, cap) cell\n")
    for pair in ["exit3", "fixed15"]:
        md.append(f"\n**{pair}**\n")
        md.append("| budget | cap | kept pass% | unfiltered pass% | delta (unfiltered-kept) |")
        md.append("|---|---|---|---|---|")
        for budget in BUDGETS:
            for cap in CAPS:
                k = cells[(f"kept_{pair}", budget, cap)]["pass_pct"]
                u = cells[(f"unfiltered_{pair}", budget, cap)]["pass_pct"]
                md.append(f"| {budget} | {cap} | {k} | {u} | {round(u - k, 2):+} |")
    md.append("")

    with open(MD_PATH, "w") as f:
        f.write("\n".join(md) + "\n")


# =================================================================================================
def main():
    t0 = time.time()
    stage0_asserts()
    surfaces, canary_lines = build_streams()
    if surfaces is None:
        return
    cells = run_grid(surfaces)
    s4 = stage4(cells)
    runtime_s = time.time() - t0
    write_csv(cells, s4["mirage_keys"])
    write_md(cells, s4, canary_lines, runtime_s)
    print(f"\n[saved] {CSV_PATH}\n[saved] {MD_PATH}")
    print(f"Runtime: {runtime_s:.1f}s")


if __name__ == "__main__":
    main()
