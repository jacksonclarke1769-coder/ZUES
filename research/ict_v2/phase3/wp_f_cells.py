"""WP-F: the 17 preregistered cells (PREREG_PHASE3.md §3), each measured EXACTLY per
§4 (estimators) and gated per §5 (G1-G4). git hash cd652ea81093. NOTHING outside the
17 cells is computed or reported. No PF/WR/expectancy.

Cell -> outcome map (several cells carry two declared outcomes; each outcome is a
separate statistic, the cell SURVIVES iff >=1 of its outcomes passes G1&G2&G3&G4;
BH/G4 is applied within each family over ALL that family's (cell,outcome) statistics
-- the conservative FDR reading of "within each family over that family's cells"; the
prereg's cell/outcome granularity is imprecise here and this choice is flagged for
Fable). Floors (§4): probabilities |Δ|>=0.05, magnitudes |Δ|>=0.10 ATR.

G1 effect: 95% CI excludes 0 AND meets the floor (F2: AUC uplift >=0.02 & CI excl 0).
G2 ICT-free: B-residualized contrast retains >=50% of raw size, same sign (F2: uplift
    over B IS the metric, so G2 holds by construction).
G3 era: sign consistent in >=3 of 4 IS years AND no year >60% of aggregate.
G4 FDR: Benjamini-Hochberg q=0.10 within family.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import statlib as S

N_DRAWS = 2000
CAT_B = ["tod_slot_30", "day_of_week"]
NUM_B = ["atr20_percentile_60sess", "sigma_tod_relative_vol_12", "ret_12bar_atr", "overnight_gap_atr"]


def _log(msg: str) -> None:
    print(f"[wp-f {time.strftime('%H:%M:%S')}] {msg}", flush=True)


# --- outcome-level result ------------------------------------------------------------


@dataclass
class OutcomeResult:
    cell: str
    family: str
    unit: str
    outcome: str
    kind: str  # 'mag' or 'prob' or 'auc'
    groupA: str
    groupB: str
    delta: float
    ci_lo: float
    ci_hi: float
    floor: float
    n_a: int
    n_b: int
    g1: bool
    resid_delta: float
    g2_retention: float
    g2: bool
    per_year: Dict[int, float]
    g3_sign_ok: bool
    g3_conc_ok: bool
    g3_max_share: float
    g3: bool
    p_value: float
    q_bh: float = np.nan
    g4: bool = False

    @property
    def survives(self) -> bool:
        return bool(self.g1 and self.g2 and self.g3 and self.g4)


def _ci_excludes_zero(lo: float, hi: float) -> bool:
    return (lo > 0 and hi > 0) or (lo < 0 and hi < 0)


def _tercile_masks(values: np.ndarray, base: np.ndarray) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    v = np.where(base, values, np.nan)
    fin = np.isfinite(v)
    if fin.sum() < 30:
        return None
    idx = np.where(fin)[0]
    labels = pd.qcut(pd.Series(v[idx]), 3, labels=False, duplicates="drop").to_numpy()
    nb = int(np.nanmax(labels)) + 1
    if nb < 2:
        return None
    top = np.zeros(len(v), dtype=bool)
    bot = np.zeros(len(v), dtype=bool)
    top[idx[labels == nb - 1]] = True
    bot[idx[labels == 0]] = True
    return top, bot


def run_contrast_outcome(
    cell: str, family: str, unit: str, outcome_name: str, kind: str,
    df_pop: pd.DataFrame, week: np.ndarray, is_year: np.ndarray, W: int, C: np.ndarray,
    maskA: np.ndarray, maskB: np.ndarray, groupA: str, groupB: str,
    outcome: np.ndarray, resid: np.ndarray,
) -> OutcomeResult:
    floor = 0.05 if kind == "prob" else 0.10
    raw = S.contrast_bootstrap(week, maskA, maskB, outcome, W, C)
    g1 = _ci_excludes_zero(raw.ci_lo, raw.ci_hi) and abs(raw.delta) >= floor

    rres = S.contrast_bootstrap(week, maskA, maskB, resid, W, C)
    retention = (rres.delta / raw.delta) if (raw.delta not in (0.0,) and np.isfinite(raw.delta) and raw.delta != 0) else np.nan
    g2 = bool(np.isfinite(retention) and np.sign(rres.delta) == np.sign(raw.delta) and abs(retention) >= 0.50)

    py = S.per_year_deltas(is_year, maskA, maskB, outcome)
    sign_ok, conc_ok, max_share, _shares = S.g3_era_stability(raw.delta, py)
    g3 = bool(sign_ok and conc_ok)

    return OutcomeResult(
        cell=cell, family=family, unit=unit, outcome=outcome_name, kind=kind,
        groupA=groupA, groupB=groupB, delta=raw.delta, ci_lo=raw.ci_lo, ci_hi=raw.ci_hi,
        floor=floor, n_a=raw.n_a, n_b=raw.n_b, g1=g1, resid_delta=rres.delta,
        g2_retention=float(retention) if np.isfinite(retention) else np.nan, g2=g2,
        per_year={y: v[0] for y, v in py.items()}, g3_sign_ok=sign_ok, g3_conc_ok=conc_ok,
        g3_max_share=max_share, g3=g3, p_value=raw.p_value,
    )


# --- family drivers ------------------------------------------------------------------


def _prep(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, int, np.ndarray]:
    week, W = S.week_ids(df["t0"])
    is_year = S.is_year_bucket(df["t0"])
    C = S.make_draw_matrix(W, N_DRAWS, seed=12345)
    return week, is_year, W, C


def run_F1(df: pd.DataFrame) -> List[OutcomeResult]:
    _log(f"F1 SALIENCE (excursion, n={len(df):,})")
    week, is_year, W, C = _prep(df)
    absfwd24 = np.abs(df["fwd_raw_24"].to_numpy(dtype=float))
    pswept = (df["terminal_event_type"].to_numpy() == "SWEEP_CONFIRMED").astype(float)
    # residuals precomputed once per outcome (shared across F1a..F1e)
    resid_mag = S.ols_residualize(df, absfwd24, CAT_B, NUM_B)
    resid_prob = S.logistic_residualize(df, pswept, np.isfinite(pswept), CAT_B, NUM_B)

    tf = df["level_timeframe_class"].to_numpy()
    ptc = df["prior_test_count"].to_numpy()
    eq = df["equality_flag"].to_numpy(dtype=bool)
    rnd = df["roundness_flag"].to_numpy(dtype=bool)
    prom = df["prominence_pts_relevant"].to_numpy(dtype=float)

    cells = {
        "F1a": (tf == "weekly", tf == "intraday", "weekly", "intraday"),
        "F1b": (ptc >= 1, ptc == 0, "prior_test>=1", "prior_test=0"),
        "F1c": (eq, ~eq, "equality", "no_equality"),
        "F1d": (rnd, ~rnd, "round", "not_round"),
    }
    tm = _tercile_masks(prom, np.ones(len(df), bool))
    if tm is not None:
        cells["F1e"] = (tm[0], tm[1], "prominence_top_tercile", "prominence_bottom_tercile")

    out: List[OutcomeResult] = []
    for cell, (mA, mB, gA, gB) in cells.items():
        out.append(run_contrast_outcome(cell, "F1", "excursion_episodes", "abs_fwd24", "mag",
                                        df, week, is_year, W, C, mA, mB, gA, gB, absfwd24, resid_mag))
        out.append(run_contrast_outcome(cell, "F1", "excursion_episodes", "P(SWEEP_CONFIRMED)", "prob",
                                        df, week, is_year, W, C, mA, mB, gA, gB, pswept, resid_prob))
    return out


def run_F3(df: pd.DataFrame) -> List[OutcomeResult]:
    _log(f"F3 CONFIRMATION LATENCY (sweep_confirmed, n={len(df):,})")
    week, is_year, W, C = _prep(df)
    fwd24 = df["fwd_24"].to_numpy(dtype=float)
    resid = S.ols_residualize(df, fwd24, CAT_B, NUM_B)
    spd = df["reclaim_speed_bars"].to_numpy(dtype=float)
    mA, mB = spd == 1, spd == 3
    return [run_contrast_outcome("F3", "F3", "sweep_confirmed", "fwd24_reversal", "mag",
                                 df, week, is_year, W, C, mA, mB, "speed=1(fast)", "speed=3(slow)", fwd24, resid)]


def run_F4(df: pd.DataFrame) -> List[OutcomeResult]:
    _log(f"F4 DISPLACEMENT PERSISTENCE (displacement_qualified, n={len(df):,})")
    week, is_year, W, C = _prep(df)
    fwd24 = df["fwd_24"].to_numpy(dtype=float)
    maxrev24 = df["maxrev_24"].to_numpy(dtype=float)
    resid_fwd = S.ols_residualize(df, fwd24, CAT_B, NUM_B)
    resid_rev = S.ols_residualize(df, maxrev24, CAT_B, NUM_B)
    feats = {"F4a": "body_vs_tod_magnitude", "F4b": "close_location", "F4c": "volume_z"}
    out: List[OutcomeResult] = []
    for cell, col in feats.items():
        tm = _tercile_masks(df[col].to_numpy(dtype=float), np.ones(len(df), bool))
        if tm is None:
            continue
        mA, mB = tm
        out.append(run_contrast_outcome(cell, "F4", "displacement_qualified", "fwd24_continuation", "mag",
                                        df, week, is_year, W, C, mA, mB, f"{col}_top", f"{col}_bottom", fwd24, resid_fwd))
        out.append(run_contrast_outcome(cell, "F4", "displacement_qualified", "maxrev24", "mag",
                                        df, week, is_year, W, C, mA, mB, f"{col}_top", f"{col}_bottom", maxrev24, resid_rev))
    return out


def run_F5(df_disp: pd.DataFrame, df_mss: pd.DataFrame) -> List[OutcomeResult]:
    _log(f"F5 PATH CLEANLINESS (disp n={len(df_disp):,}, mss n={len(df_mss):,})")
    out: List[OutcomeResult] = []
    for cell, unit, df in (("F5a", "displacement_qualified", df_disp), ("F5b", "mss", df_mss)):
        week, is_year, W, C = _prep(df)
        fwd24 = df["fwd_24"].to_numpy(dtype=float)
        resid = S.ols_residualize(df, fwd24, CAT_B, NUM_B)
        tm = _tercile_masks(df["efficiency_12"].to_numpy(dtype=float), np.ones(len(df), bool))
        if tm is None:
            continue
        mA, mB = tm
        out.append(run_contrast_outcome(cell, "F5", unit, "fwd24_event_dir", "mag",
                                        df, week, is_year, W, C, mA, mB, "efficiency_top", "efficiency_bottom", fwd24, resid))
    return out


def run_F6(df_sweep: pd.DataFrame, df_mss: pd.DataFrame) -> List[OutcomeResult]:
    _log("F6 REMAINING OPPORTUNITY (ny_am subsets)")
    out: List[OutcomeResult] = []
    for cell, unit, df_full in (("F6a", "sweep_confirmed", df_sweep), ("F6b", "mss", df_mss)):
        df = df_full[df_full["session"] == "ny_am"].reset_index(drop=True)
        if len(df) < 30:
            continue
        week, is_year, W, C = _prep(df)
        absfwd24 = np.abs(df["fwd_raw_24"].to_numpy(dtype=float))
        maxcont24 = df["maxcont_24"].to_numpy(dtype=float)
        resid_abs = S.ols_residualize(df, absfwd24, CAT_B, NUM_B)
        resid_cont = S.ols_residualize(df, maxcont24, CAT_B, NUM_B)
        tm = _tercile_masks(df["session_range_consumed"].to_numpy(dtype=float), np.ones(len(df), bool))
        if tm is None:
            continue
        mA, mB = tm
        out.append(run_contrast_outcome(cell, "F6", f"{unit}(ny_am)", "abs_fwd24", "mag",
                                        df, week, is_year, W, C, mA, mB, "range_consumed_top", "range_consumed_bottom", absfwd24, resid_abs))
        out.append(run_contrast_outcome(cell, "F6", f"{unit}(ny_am)", "maxcont24", "mag",
                                        df, week, is_year, W, C, mA, mB, "range_consumed_top", "range_consumed_bottom", maxcont24, resid_cont))
    return out


def run_F7(df_level: pd.DataFrame, df_fvg: pd.DataFrame) -> List[OutcomeResult]:
    _log(f"F7 FRESHNESS (level_tested n={len(df_level):,}, fvg_tested n={len(df_fvg):,})")
    out: List[OutcomeResult] = []
    for cell, unit, df in (("F7a", "level_tested", df_level), ("F7b", "fvg_tested", df_fvg)):
        week, is_year, W, C = _prep(df)
        fwd12 = df["fwd_12"].to_numpy(dtype=float)  # direction-adjusted (away from level/zone)
        bounce = np.where(np.isfinite(fwd12), (fwd12 > 0).astype(float), np.nan)
        absfwd12 = np.abs(df["fwd_raw_12"].to_numpy(dtype=float))
        resid_bounce = S.logistic_residualize(df, bounce, np.isfinite(bounce), CAT_B, NUM_B)
        resid_mag = S.ols_residualize(df, absfwd12, CAT_B, NUM_B)
        tc = df["test_count"].to_numpy(dtype=float)
        mA, mB = tc == 1, tc >= 2  # 1st vs 2nd+
        out.append(run_contrast_outcome(cell, "F7", unit, "P(bounce)", "prob",
                                        df, week, is_year, W, C, mA, mB, "1st_test", "2nd+_test", bounce, resid_bounce))
        out.append(run_contrast_outcome(cell, "F7", unit, "abs_fwd12", "mag",
                                        df, week, is_year, W, C, mA, mB, "1st_test", "2nd+_test", absfwd12, resid_mag))
    return out


# --- F2 prediction cells -------------------------------------------------------------


F2_CAT_FULL = CAT_B + ["level_timeframe_class"]
F2_NUM_FULL = NUM_B + [
    "excursion_depth_ticks_t0", "excursion_depth_atr_t0", "t0_close_location",
    "body_vs_tod_t0", "volume_z_t0", "prominence_pts_relevant", "roundness_major",
    "roundness_minor", "equality_count", "prior_test_count",
]


@dataclass
class F2Result:
    cell: str
    family: str
    target: str
    auc_base: float
    auc_full: float
    uplift: float
    ci_lo: float
    ci_hi: float
    n: int
    n_pos: int
    g1: bool
    g2: bool  # by construction (uplift over B is the metric)
    per_year: Dict[int, float]
    g3_sign_ok: bool
    g3_conc_ok: bool
    g3_max_share: float
    g3: bool
    p_value: float
    q_bh: float = np.nan
    g4: bool = False

    @property
    def survives(self) -> bool:
        return bool(self.g1 and self.g2 and self.g3 and self.g4)


def run_F2(df: pd.DataFrame) -> List[F2Result]:
    _log(f"F2 ACCEPTANCE/REJECTION prediction (excursion, n={len(df):,})")
    out: List[F2Result] = []

    # Target A: SWEEP_CONFIRMED (1) vs ACCEPTED_BREAKOUT (0); timeouts/unresolved excluded.
    term = df["terminal_event_type"].to_numpy()
    a_mask = np.isin(term, ["SWEEP_CONFIRMED", "ACCEPTED_BREAKOUT"])
    _log(f"  Target A: kept {int(a_mask.sum()):,}, excluded(timeouts+unresolved)={int((~a_mask).sum()):,}")
    yA = (term[a_mask] == "SWEEP_CONFIRMED").astype(np.int64)
    out.append(_run_f2_target(df[a_mask].reset_index(drop=True), yA, "F2a", "SWEEP_CONFIRMED vs ACCEPTED_BREAKOUT"))

    # Target B: sign(fwd(24)) > 0.
    fwd = df["fwd_raw_24"].to_numpy(dtype=float)
    b_mask = np.isfinite(fwd)
    yB = (fwd[b_mask] > 0).astype(np.int64)
    out.append(_run_f2_target(df[b_mask].reset_index(drop=True), yB, "F2b", "sign(fwd24)"))
    return out


def _run_f2_target(df: pd.DataFrame, y: np.ndarray, cell: str, target: str) -> F2Result:
    week, W = S.week_ids(df["t0"])
    is_year = S.is_year_bucket(df["t0"])
    fold_of_week = S.week_folds(W, 5)
    C = S.make_draw_matrix(W, N_DRAWS, seed=777)

    _log(f"  {cell} fitting baseline-B OOF ...")
    p_base = S.cv_oof_predict(df, y, week, fold_of_week, CAT_B, NUM_B)
    _log(f"  {cell} fitting B+ICT OOF ...")
    p_full = S.cv_oof_predict(df, y, week, fold_of_week, F2_CAT_FULL, F2_NUM_FULL)

    fin = np.isfinite(p_base) & np.isfinite(p_full)
    res = S.auc_uplift_bootstrap(p_base[fin], p_full[fin], y[fin], week[fin], W, C)
    g1 = _ci_excludes_zero(res.ci_lo, res.ci_hi) and res.uplift >= 0.02

    py = S.auc_uplift_per_year(p_base, p_full, y, is_year)
    sign_ok, conc_ok, max_share, _ = S.g3_era_stability(res.uplift, {k: (v[0], v[1]) for k, v in py.items()})
    g3 = bool(sign_ok and conc_ok)

    return F2Result(
        cell=cell, family="F2", target=target, auc_base=res.auc_base, auc_full=res.auc_full,
        uplift=res.uplift, ci_lo=res.ci_lo, ci_hi=res.ci_hi, n=res.n, n_pos=res.n_pos, g1=g1,
        g2=True, per_year={k: v[0] for k, v in py.items()}, g3_sign_ok=sign_ok, g3_conc_ok=conc_ok,
        g3_max_share=max_share, g3=g3, p_value=res.p_value,
    )


# --- F2a' (Amendment v1.2, hash bc35ceddcb10): F2a re-scoped to episodes whose FSM
# terminal resolves STRICTLY AFTER t0 (same-bar/tautological resolutions excluded) -----


def restrict_post_t0(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Amendment v1.2 unit: keep excursion episodes with terminal in {SWEEP_CONFIRMED,
    ACCEPTED_BREAKOUT} AND `terminal_confirmed_at` STRICTLY AFTER `t0`. Same-bar
    resolutions (terminal_confirmed_at == t0 -- the reclaim_speed_bars=1 tautological
    majority) are excluded from BOTH fit and evaluation; timeouts/unresolved excluded
    (counted). Returns (kept_df, meta counts)."""
    term = df["terminal_event_type"].to_numpy()
    tconf = pd.to_datetime(df["terminal_confirmed_at"])
    t0 = pd.to_datetime(df["t0"])
    is_pair = np.isin(term, ["SWEEP_CONFIRMED", "ACCEPTED_BREAKOUT"])
    strictly_after = (tconf > t0).to_numpy()  # NaT > t0 -> False (unresolved excluded)
    keep = is_pair & strictly_after
    same_bar_excluded = int((is_pair & ~strictly_after).sum())
    non_pair_excluded = int((~is_pair).sum())
    kept = df[keep].reset_index(drop=True)
    kept_term = kept["terminal_event_type"].to_numpy()
    meta = {
        "total_episodes": int(len(df)),
        "kept_post_t0_pair": int(len(kept)),
        "excluded_same_bar_resolutions": same_bar_excluded,
        "excluded_non_pair_timeout_or_unresolved": non_pair_excluded,
        "n_sweep_confirmed": int((kept_term == "SWEEP_CONFIRMED").sum()),
        "n_accepted_breakout": int((kept_term == "ACCEPTED_BREAKOUT").sum()),
    }
    return kept, meta


def run_F2a_prime(df: pd.DataFrame) -> Tuple[F2Result, Dict[str, int]]:
    _log(f"F2a' ACCEPTANCE prediction, POST-t0 only (Amendment v1.2), from n={len(df):,} episodes")
    kept, meta = restrict_post_t0(df)
    _log(f"  kept post-t0 pair={meta['kept_post_t0_pair']:,} "
         f"(excluded same-bar={meta['excluded_same_bar_resolutions']:,}, "
         f"non-pair/timeout/unresolved={meta['excluded_non_pair_timeout_or_unresolved']:,})")
    _log(f"  class balance: SWEEP_CONFIRMED={meta['n_sweep_confirmed']:,} vs ACCEPTED_BREAKOUT={meta['n_accepted_breakout']:,}")
    y = (kept["terminal_event_type"].to_numpy() == "SWEEP_CONFIRMED").astype(np.int64)
    res = _run_f2_target(kept, y, "F2a_prime", "SWEEP_CONFIRMED vs ACCEPTED_BREAKOUT (terminal strictly after t0)")
    return res, meta


# --- BH within family + assembly -----------------------------------------------------


def apply_bh_within_families(contrast: List[OutcomeResult], f2: List[F2Result], q: float = 0.10) -> None:
    families: Dict[str, List[Any]] = {}
    for r in contrast:
        families.setdefault(r.family, []).append(r)
    for r in f2:
        families.setdefault(r.family, []).append(r)
    for fam, results in families.items():
        pvals = [r.p_value for r in results]
        rej = S.benjamini_hochberg(pvals, q)
        # BH-adjusted q per test (for reporting)
        p = np.asarray(pvals, dtype=float)
        order = np.argsort(np.where(np.isfinite(p), p, np.inf))
        m = int(np.isfinite(p).sum())
        qadj = np.full(len(p), np.nan)
        running = 1.0
        for rank in range(len(order) - 1, -1, -1):
            i = order[rank]
            if not np.isfinite(p[i]):
                continue
            val = p[i] * m / (rank + 1)
            running = min(running, val)
            qadj[i] = running
        for k, r in enumerate(results):
            r.q_bh = float(qadj[k]) if np.isfinite(qadj[k]) else np.nan
            r.g4 = bool(rej[k])
