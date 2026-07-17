"""WP-F synthetic self-test (PREREG_PHASE3.md §8, MANDATORY before the IS run): a
planted effect must PASS the gates and a null placebo must FAIL them, on synthetic data
shaped like the real files. Also validates G2 (a B-confound placebo whose raw effect is
real but fully explained by baseline B must DIE at G2) and the F2 AUC path (planted
uplift passes, null uplift fails). The IS run may not start unless all behave correctly.
"""
from __future__ import annotations

import time
from typing import Dict

import numpy as np
import pandas as pd

from . import statlib as S
from . import wp_f_cells as W


def _log(m: str) -> None:
    print(f"[wp-f selftest {time.strftime('%H:%M:%S')}] {m}", flush=True)


def _synth_frame(n: int, rng: np.random.Generator) -> pd.DataFrame:
    days = rng.integers(0, int(4 * 365.2), size=n)
    t0 = pd.Series([S.IS_START + pd.Timedelta(days=int(d), hours=int(h)) for d, h in zip(days, rng.integers(0, 24, n))])
    return pd.DataFrame(
        {
            "t0": t0,
            "tod_slot_30": rng.choice([f"{h:02d}:{m:02d}" for h in range(6, 17) for m in (0, 30)], n),
            "day_of_week": rng.integers(0, 5, n),
            "atr20_percentile_60sess": rng.uniform(0, 100, n),
            "sigma_tod_relative_vol_12": rng.normal(1, 0.3, n),
            "ret_12bar_atr": rng.normal(0, 1, n),
            "overnight_gap_atr": rng.normal(0, 0.5, n),
        }
    )


def _run_one(df: pd.DataFrame, maskA, maskB, outcome, kind: str) -> W.OutcomeResult:
    week, W_ = S.week_ids(df["t0"])
    is_year = S.is_year_bucket(df["t0"])
    C = S.make_draw_matrix(W_, W.N_DRAWS, seed=999)
    if kind == "prob":
        resid = S.logistic_residualize(df, outcome, np.isfinite(outcome), W.CAT_B, W.NUM_B)
    else:
        resid = S.ols_residualize(df, outcome, W.CAT_B, W.NUM_B)
    return W.run_contrast_outcome("TEST", "T", "synthetic", "synthetic", kind, df, week, is_year, W_, C,
                                  maskA, maskB, "A", "B", outcome, resid)


def run_selftest() -> Dict[str, object]:
    _log("building synthetic data shaped like the real files ...")
    rng = np.random.default_rng(2026)
    n = 60000
    results: Dict[str, object] = {}
    checks = []

    # 1) PLANTED contrast effect, independent of B: must PASS G1-G3 (single-test BH -> G4 pass).
    df = _synth_frame(n, rng)
    grp = rng.integers(0, 2, n)
    outcome = 0.30 * grp + rng.normal(0, 1.0, n)  # Δ ~ 0.30 ATR > 0.10 floor, uniform across years
    r = _run_one(df, grp == 1, grp == 0, outcome, "mag")
    r.g4 = S.benjamini_hochberg([r.p_value], 0.10)[0]
    planted_pass = r.g1 and r.g2 and r.g3 and r.g4
    results["planted"] = r
    checks.append(("planted_effect_PASSES", planted_pass, True))
    _log(f"  planted: Δ={r.delta:.3f} CI[{r.ci_lo:.3f},{r.ci_hi:.3f}] G1={r.g1} G2ret={r.g2_retention:.2f} G3={r.g3} G4={r.g4} -> survives={planted_pass}")

    # 2) NULL placebo, no group effect: must FAIL G1.
    df2 = _synth_frame(n, rng)
    grp2 = rng.integers(0, 2, n)
    outcome2 = rng.normal(0, 1.0, n)
    r2 = _run_one(df2, grp2 == 1, grp2 == 0, outcome2, "mag")
    r2.g4 = S.benjamini_hochberg([r2.p_value], 0.10)[0]
    null_fails = not (r2.g1 and r2.g2 and r2.g3 and r2.g4)
    results["null"] = r2
    checks.append(("null_placebo_FAILS", null_fails, True))
    _log(f"  null: Δ={r2.delta:.3f} CI[{r2.ci_lo:.3f},{r2.ci_hi:.3f}] G1={r2.g1} -> survives={not null_fails}")

    # 3) B-CONFOUND placebo: real raw effect but fully explained by baseline B -> must DIE at G2.
    df3 = _synth_frame(n, rng)
    x = df3["ret_12bar_atr"].to_numpy()  # a baseline-B feature
    grp3 = (x > np.median(x)).astype(int)  # group tracks a B feature
    outcome3 = 1.0 * x + rng.normal(0, 0.3, n)  # outcome driven by that same B feature
    r3 = _run_one(df3, grp3 == 1, grp3 == 0, outcome3, "mag")
    confound_dies_at_g2 = (r3.g1 and not r3.g2)  # G1 fires (raw effect real) but G2 kills it
    results["b_confound"] = r3
    checks.append(("b_confound_DIES_at_G2", confound_dies_at_g2, True))
    _log(f"  b_confound: Δ={r3.delta:.3f} G1={r3.g1} G2ret={r3.g2_retention:.2f} G2={r3.g2} -> dies_at_G2={confound_dies_at_g2}")

    # 4) F2 PLANTED: an ICT feature carries signal beyond B -> AUC uplift passes.
    m = 40000
    dff = _synth_frame(m, rng)
    for c in W.F2_NUM_FULL:
        if c not in dff.columns:
            dff[c] = rng.normal(0, 1, m)
    dff["level_timeframe_class"] = rng.choice(["weekly", "intraday"], m)
    signal = dff["excursion_depth_atr_t0"].to_numpy()
    yb = (1 / (1 + np.exp(-(1.2 * signal))) > rng.random(m)).astype(np.int64)
    rf = W._run_f2_target(dff, yb, "TESTF2", "planted")
    f2_planted_pass = rf.g1
    results["f2_planted"] = rf
    checks.append(("f2_planted_uplift_PASSES_G1", f2_planted_pass, True))
    _log(f"  f2_planted: AUC B={rf.auc_base:.3f} B+ICT={rf.auc_full:.3f} uplift={rf.uplift:.3f} CI[{rf.ci_lo:.3f},{rf.ci_hi:.3f}] G1={rf.g1}")

    # 5) F2 NULL: ICT feature is pure noise -> uplift ~ 0, fails G1.
    dfn = _synth_frame(m, rng)
    for c in W.F2_NUM_FULL:
        if c not in dfn.columns:
            dfn[c] = rng.normal(0, 1, m)
    dfn["level_timeframe_class"] = rng.choice(["weekly", "intraday"], m)
    yn = rng.integers(0, 2, m).astype(np.int64)  # unrelated to any feature
    rn = W._run_f2_target(dfn, yn, "TESTF2N", "null")
    f2_null_fails = not rn.g1
    results["f2_null"] = rn
    checks.append(("f2_null_uplift_FAILS_G1", f2_null_fails, True))
    _log(f"  f2_null: uplift={rn.uplift:.3f} CI[{rn.ci_lo:.3f},{rn.ci_hi:.3f}] G1={rn.g1}")

    # 6) UNIT-RESTRICTION path (Amendment v1.2, F2a'): the same-bar exclusion must
    #    (a) let a genuine POST-t0 signal through -> passes G1, and
    #    (b) STRIP a purely t0-contemporaneous (same-bar) tautology -> after restriction
    #        the residual post-t0 signal is noise -> fails G1 (no leak).
    r_planted, r_leak_full, r_leak_restricted = _unit_restriction_checks(rng)
    results["f2aprime_planted"] = r_planted
    results["f2aprime_leak_full"] = r_leak_full
    results["f2aprime_leak_restricted"] = r_leak_restricted
    checks.append(("f2aprime_planted_post_t0_PASSES_G1", r_planted.g1, True))
    # the leak must be REAL when unrestricted (sanity) and REMOVED after restriction:
    checks.append(("f2aprime_same_bar_leak_present_when_unrestricted", r_leak_full.g1, True))
    checks.append(("f2aprime_same_bar_leak_REMOVED_by_restriction", not r_leak_restricted.g1, True))
    _log(f"  f2aprime_planted(post-t0): uplift={r_planted.uplift:.3f} CI[{r_planted.ci_lo:.3f},{r_planted.ci_hi:.3f}] G1={r_planted.g1}")
    _log(f"  f2aprime_leak unrestricted: uplift={r_leak_full.uplift:.3f} G1={r_leak_full.g1}  |  restricted: uplift={r_leak_restricted.uplift:.3f} G1={r_leak_restricted.g1}")

    all_ok = all(actual == expected for _, actual, expected in checks)
    results["checks"] = checks
    results["all_ok"] = all_ok
    _log(f"SELF-TEST {'PASSED' if all_ok else 'FAILED'}: " + ", ".join(f"{name}={actual}" for name, actual, _ in checks))
    return results


def _synth_excursion(n: int, rng: np.random.Generator, label_mode: str) -> pd.DataFrame:
    """Synthetic excursion-episode frame shaped like excursion_episodes_is.parquet for
    the F2a' unit-restriction self-test. Half the episodes resolve SAME-BAR
    (terminal_confirmed_at == t0), half resolve POST-t0 (terminal_confirmed_at > t0).

    label_mode:
      - 'planted_post_t0': POST-t0 label driven by excursion_depth_atr_t0 (a genuine
        strictly-pre-label feature); same-bar label = noise.
      - 'leak_same_bar': SAME-bar label = a deterministic function of t0_close_location
        (the tautology); POST-t0 label = noise. Restricting to post-t0 must remove it.
    """
    df = _synth_frame(n, rng)
    for c in W.F2_NUM_FULL:
        if c not in df.columns:
            df[c] = rng.normal(0, 1, n)
    df["level_timeframe_class"] = rng.choice(["weekly", "intraday"], n)
    same_bar = rng.random(n) < 0.5
    t0 = pd.to_datetime(df["t0"])
    steps = rng.integers(1, 4, n)  # 1..3 bars later for post-t0
    add_min = np.where(same_bar, 0, steps * 5)
    df["terminal_confirmed_at"] = t0 + pd.to_timedelta(add_min, unit="min")  # tz preserved

    depth = df["excursion_depth_atr_t0"].to_numpy()
    cloc = df["t0_close_location"].to_numpy()
    y = np.empty(n, dtype=int)
    post = ~same_bar
    if label_mode == "planted_post_t0":
        y[post] = (1 / (1 + np.exp(-(1.3 * depth[post]))) > rng.random(post.sum())).astype(int)
        y[same_bar] = rng.integers(0, 2, same_bar.sum())
    elif label_mode == "leak_same_bar":
        y[same_bar] = (1 / (1 + np.exp(-(4.0 * cloc[same_bar]))) > rng.random(same_bar.sum())).astype(int)
        y[post] = rng.integers(0, 2, post.sum())
    else:
        raise ValueError(label_mode)
    df["terminal_event_type"] = np.where(y == 1, "SWEEP_CONFIRMED", "ACCEPTED_BREAKOUT")
    return df


def _unit_restriction_checks(rng: np.random.Generator):
    """Returns (planted_result, leak_unrestricted_result, leak_restricted_result)."""
    m = 40000
    # (a) genuine post-t0 signal survives the restriction and passes G1.
    dfp = _synth_excursion(m, rng, "planted_post_t0")
    kept, _ = W.restrict_post_t0(dfp)
    yk = (kept["terminal_event_type"].to_numpy() == "SWEEP_CONFIRMED").astype(np.int64)
    r_planted = W._run_f2_target(kept, yk, "STF2AP", "planted post-t0")

    # (b) a purely same-bar tautology: real when unrestricted, GONE after restriction.
    dfl = _synth_excursion(m, rng, "leak_same_bar")
    pair = np.isin(dfl["terminal_event_type"].to_numpy(), ["SWEEP_CONFIRMED", "ACCEPTED_BREAKOUT"])
    yfull = (dfl["terminal_event_type"].to_numpy()[pair] == "SWEEP_CONFIRMED").astype(np.int64)
    r_leak_full = W._run_f2_target(dfl[pair].reset_index(drop=True), yfull, "STF2AL", "leak unrestricted")
    keptl, _ = W.restrict_post_t0(dfl)
    ykl = (keptl["terminal_event_type"].to_numpy() == "SWEEP_CONFIRMED").astype(np.int64)
    r_leak_restricted = W._run_f2_target(keptl, ykl, "STF2ALR", "leak restricted")
    return r_planted, r_leak_full, r_leak_restricted
