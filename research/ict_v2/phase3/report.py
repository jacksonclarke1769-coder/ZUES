"""WP-E counts report (PREREG_PHASE3.md v1.0 §8: "NO statistics beyond event
counts"). Builds `reports/ict_v2/03a_phase3_extraction_counts.md`: events per family
per year, NO-TEST flags (any IS-compared-group < 50 events), feature completeness
(% non-null), and the knowability-assertion result. NO means/effects/outcomes
summaries anywhere in this module -- it only ever counts rows.

Cell -> (unit, grouping) map mirrors PREREG_PHASE3.md v1.0 §3's 17 cells exactly.
Terciles (F1e/F4a-c/F5a-b/F6a-b): computed on the IS split only, non-null feature
values, `pd.qcut(..., 3)`; the reported "compared group" sizes are the TOP and
BOTTOM tercile only (the prereg's own "top vs bottom" contrast language for F1e;
applied uniformly to every other tercile-featured cell for consistency) -- the
middle tercile is not itself a compared group for the NO-TEST gate.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

MIN_NO_TEST_N = 50

BOT_REPO = os.path.expanduser("~/trading-team/bot/nq-liq-bot")
REPORT_PATH = os.path.join(BOT_REPO, "reports", "ict_v2", "03a_phase3_extraction_counts.md")

# feature columns per unit (excludes t0/split/year/session/direction bookkeeping and
# every outcome/raw-outcome column) -- used ONLY for % non-null completeness.
FEATURE_COLUMNS: Dict[str, List[str]] = {
    "excursion_episodes": [
        "level_kind", "side", "level_timeframe_class", "level_price", "breach_price",
        "excursion_depth_pts_t0", "excursion_depth_ticks_t0", "excursion_depth_atr_t0",
        "t0_close_location", "body_vs_tod_t0", "volume_z_t0", "prominence_above_pts",
        "prominence_below_pts", "prominence_pts_relevant", "roundness_major",
        "roundness_minor", "equality_count", "equality_flag", "roundness_flag",
        "prior_test_count", "tod_slot_30", "day_of_week", "atr20",
        "atr20_percentile_60sess", "sigma_tod_relative_vol_12", "ret_12bar_atr",
        "overnight_gap_atr",
    ],
    "sweep_confirmed": [
        "level_kind", "side", "direction", "reclaim_speed_bars", "duration_bars",
        "excursion_depth_ticks", "level_timeframe_class", "prominence_above_pts",
        "prominence_below_pts", "roundness_major", "roundness_minor", "equality_count",
        "session", "session_range_consumed", "tod_slot_30", "day_of_week", "atr20",
        "atr20_percentile_60sess", "sigma_tod_relative_vol_12", "ret_12bar_atr",
        "overnight_gap_atr",
    ],
    "displacement_qualified": [
        "direction", "body", "mean20_body", "ratio", "body_vs_tod_magnitude",
        "close_location", "volume_z", "efficiency_12", "tod_slot_30", "day_of_week",
        "atr20", "atr20_percentile_60sess", "sigma_tod_relative_vol_12",
        "ret_12bar_atr", "overnight_gap_atr",
    ],
    "mss": [
        "direction", "choch_bars_elapsed", "efficiency_12", "session",
        "session_range_consumed", "tod_slot_30", "day_of_week", "atr20",
        "atr20_percentile_60sess", "sigma_tod_relative_vol_12", "ret_12bar_atr",
        "overnight_gap_atr",
    ],
    "level_tested": [
        "level_kind", "test_count", "test_number_ge2", "age_seconds", "direction",
        "tod_slot_30", "day_of_week", "atr20", "atr20_percentile_60sess",
        "sigma_tod_relative_vol_12", "ret_12bar_atr", "overnight_gap_atr",
    ],
    "fvg_tested": [
        "fvg_direction", "test_count", "test_number_ge2", "direction", "tod_slot_30",
        "day_of_week", "atr20", "atr20_percentile_60sess", "sigma_tod_relative_vol_12",
        "ret_12bar_atr", "overnight_gap_atr",
    ],
}


def _tercile_topbottom_n(series: pd.Series) -> Tuple[int, int, int]:
    """Returns (n_bottom, n_top, n_nonnull). `pd.qcut` with `duplicates="drop"` can
    yield <3 bins on degenerate/near-constant data -- reported honestly (bottom==top
    bin in that case), never fabricated."""
    s = series.dropna()
    n_nonnull = len(s)
    if n_nonnull < 3:
        return (0, 0, n_nonnull)
    try:
        bins = pd.qcut(s, 3, labels=False, duplicates="drop")
    except ValueError:
        return (0, 0, n_nonnull)
    n_bins = bins.nunique()
    n_bottom = int((bins == 0).sum())
    n_top = int((bins == n_bins - 1).sum())
    return (n_bottom, n_top, n_nonnull)


def _binary_group_n(series: pd.Series, groups: List[Any]) -> Dict[Any, int]:
    return {g: int((series == g).sum()) for g in groups}


def compute_cell_notest(dfs: Dict[str, pd.DataFrame]) -> List[Dict[str, Any]]:
    """One row per PREREG §3 cell: IS-only compared-group sizes + NO-TEST flag."""
    rows: List[Dict[str, Any]] = []

    def add(cell: str, family: str, unit: str, groups: Dict[Any, int], note: str = "") -> None:
        no_test = any(n < MIN_NO_TEST_N for n in groups.values()) if groups else True
        rows.append({"cell": cell, "family": family, "unit": unit, "groups": groups, "no_test": no_test, "note": note})

    exc = dfs["excursion_episodes"]

    add("F1a", "F1 SALIENCE", "excursion_episodes", _binary_group_n(exc["level_timeframe_class"], ["weekly", "intraday"]))

    prior0 = int((exc["prior_test_count"] == 0).sum())
    prior1p = int((exc["prior_test_count"] >= 1).sum())
    add("F1b", "F1 SALIENCE", "excursion_episodes", {"prior_test_count=0": prior0, "prior_test_count>=1": prior1p})

    add("F1c", "F1 SALIENCE", "excursion_episodes", _binary_group_n(exc["equality_flag"], [False, True]))
    add("F1d", "F1 SALIENCE", "excursion_episodes", _binary_group_n(exc["roundness_flag"], [False, True]))

    nb, nt, nn = _tercile_topbottom_n(exc["prominence_pts_relevant"])
    add("F1e", "F1 SALIENCE", "excursion_episodes", {"bottom_tercile": nb, "top_tercile": nt}, note=f"n_nonnull={nn}")

    terminal_counts = exc["terminal_event_type"].value_counts().to_dict()
    a_groups = {
        "SWEEP_CONFIRMED": terminal_counts.get("SWEEP_CONFIRMED", 0),
        "ACCEPTED_BREAKOUT": terminal_counts.get("ACCEPTED_BREAKOUT", 0),
    }
    excluded = terminal_counts.get("EXCURSION_TIMEOUT", 0) + terminal_counts.get("UNRESOLVED_AT_DATA_END", 0)
    add("F2 Target A", "F2 ACCEPTANCE/REJECTION", "excursion_episodes", a_groups, note=f"excluded(timeouts+unresolved)={excluded}")

    n_fwd24 = int(exc["fwd_raw_24"].notna().sum())
    add("F2 Target B", "F2 ACCEPTANCE/REJECTION", "excursion_episodes", {"population(sign(fwd24))": n_fwd24})

    sw = dfs["sweep_confirmed"]
    add("F3", "F3 CONFIRMATION LATENCY", "sweep_confirmed", _binary_group_n(sw["reclaim_speed_bars"], [1, 2, 3]))

    dq = dfs["displacement_qualified"]
    for cell, col in (("F4a", "body_vs_tod_magnitude"), ("F4b", "close_location"), ("F4c", "volume_z")):
        nb, nt, nn = _tercile_topbottom_n(dq[col])
        add(cell, "F4 DISPLACEMENT PERSISTENCE", "displacement_qualified", {"bottom_tercile": nb, "top_tercile": nt}, note=f"n_nonnull={nn}")

    nb, nt, nn = _tercile_topbottom_n(dq["efficiency_12"])
    add("F5a", "F5 PATH CLEANLINESS", "displacement_qualified", {"bottom_tercile": nb, "top_tercile": nt}, note=f"n_nonnull={nn}")

    mss = dfs["mss"]
    nb, nt, nn = _tercile_topbottom_n(mss["efficiency_12"])
    add("F5b", "F5 PATH CLEANLINESS", "mss", {"bottom_tercile": nb, "top_tercile": nt}, note=f"n_nonnull={nn}")

    sw_nyam = sw[sw["session"] == "ny_am"]
    nb, nt, nn = _tercile_topbottom_n(sw_nyam["session_range_consumed"])
    add("F6a", "F6 REMAINING OPPORTUNITY", "sweep_confirmed(ny_am)", {"bottom_tercile": nb, "top_tercile": nt}, note=f"n_nonnull={nn}, ny_am_total={len(sw_nyam)}")

    mss_nyam = mss[mss["session"] == "ny_am"]
    nb, nt, nn = _tercile_topbottom_n(mss_nyam["session_range_consumed"])
    add("F6b", "F6 REMAINING OPPORTUNITY", "mss(ny_am)", {"bottom_tercile": nb, "top_tercile": nt}, note=f"n_nonnull={nn}, ny_am_total={len(mss_nyam)}")

    lt = dfs["level_tested"]
    add("F7a", "F7 FRESHNESS", "level_tested", _binary_group_n(lt["test_number_ge2"], [False, True]))

    fv = dfs["fvg_tested"]
    add("F7b", "F7 FRESHNESS", "fvg_tested", _binary_group_n(fv["test_number_ge2"], [False, True]))

    return rows


def per_year_counts(dfs_is: Dict[str, pd.DataFrame], dfs_holdout: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for name in dfs_is:
        is_y = dfs_is[name]["year"].value_counts().sort_index()
        ho_y = dfs_holdout[name]["year"].value_counts().sort_index()
        years = sorted(set(is_y.index) | set(ho_y.index))
        rows = [{"year": y, "IS": int(is_y.get(y, 0)), "HOLDOUT": int(ho_y.get(y, 0))} for y in years]
        out[name] = pd.DataFrame(rows)
    return out


def feature_completeness(dfs_all: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}
    for name, cols in FEATURE_COLUMNS.items():
        df = dfs_all[name]
        n = len(df)
        rows = []
        for c in cols:
            if c not in df.columns:
                rows.append({"feature": c, "pct_nonnull": None, "note": "MISSING COLUMN"})
                continue
            nonnull = int(df[c].notna().sum())
            rows.append({"feature": c, "pct_nonnull": round(100.0 * nonnull / n, 2) if n else None})
        out[name] = pd.DataFrame(rows)
    return out


def write_report(
    frame_assertion: Dict[str, Any],
    dfs_is: Dict[str, pd.DataFrame],
    dfs_holdout: Dict[str, pd.DataFrame],
    timings: Dict[str, float],
    knowability_checks: int,
    knowability_violations: int,
    per_engine_event_counts: Dict[str, Dict[str, int]],
    unsplit_counts: Dict[str, int],
    conformance: Optional[Dict[str, int]] = None,
    prereg_git_hash: str = "cd652ea81093",
) -> str:
    dfs_all = {name: pd.concat([dfs_is[name], dfs_holdout[name]], ignore_index=True) for name in dfs_is}

    yearly = per_year_counts(dfs_is, dfs_holdout)
    notest_rows = compute_cell_notest(dfs_is)
    completeness = feature_completeness(dfs_all)

    lines: List[str] = []
    lines.append("# ICT V2 Phase 3, WP-E — Extraction Counts Report")
    lines.append("")
    lines.append(
        f"**Governs:** `research/ict_v2/PREREG_PHASE3.md` v1.0 + Amendment v1.1, git hash `{prereg_git_hash}`. "
        "**Scope:** WP-E (build) only — event/feature/outcome extraction. NO statistics beyond event "
        "counts anywhere in this report (PREREG §8 ban): no means, no effects, no PF/WR/expectancy, "
        "no outcome summaries."
    )
    lines.append("")

    lines.append("## 1. Frame assertion (Amendment v1.1)")
    lines.append("")
    for k, v in frame_assertion.items():
        lines.append(f"- **{k}:** {v}")
    lines.append("")

    lines.append("## 2. Runtime")
    lines.append("")
    lines.append("| stage | seconds |")
    lines.append("|---|---:|")
    for k, v in timings.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    lines.append("## 3. Engine event inventory (raw, all event types emitted, IS+HOLDOUT combined)")
    lines.append("")
    for engine, counts in per_engine_event_counts.items():
        total = sum(counts.values())
        lines.append(f"- **{engine}**: {total:,} total events — " + ", ".join(f"{k}={v:,}" for k, v in counts.items()))
    lines.append("")
    lines.append(
        "AMD excluded per prereg §8 ban. `opening_range`/`overnight`/`ranges`/`swings_b`/`swings_c` not "
        "registered — no §3 cell names an event type from any of them (baseline B's ATR-percentile / "
        "overnight-gap are computed independently from the bar array, see `baseline.py`)."
    )
    lines.append("")

    lines.append("## 4. Event UNAVAILABLE check")
    lines.append("")
    required = [
        "EXCURSION_OPEN", "SWEEP_CONFIRMED", "ACCEPTED_BREAKOUT", "EXCURSION_TIMEOUT",
        "DISPLACEMENT_QUALIFIED", "MSS", "LEVEL_TESTED", "FVG_TESTED",
    ]
    emitted_types = set()
    for counts in per_engine_event_counts.values():
        emitted_types.update(counts.keys())
    missing = [t for t in required if t not in emitted_types]
    if missing:
        lines.append(f"**UNAVAILABLE:** {missing} — not emitted by any registered certified engine.")
    else:
        lines.append(
            "None. All prereg-named event types (`EXCURSION_OPEN`/`SWEEP_CONFIRMED`/`ACCEPTED_BREAKOUT`/"
            "`EXCURSION_TIMEOUT`, `DISPLACEMENT_QUALIFIED`, `MSS`, `LEVEL_TESTED`, `FVG_TESTED`) are "
            "emitted by the certified engines exactly as named — no detector was improvised."
        )
    lines.append("")

    lines.append("## 5. Per-family event counts by year (IS / HOLDOUT — row counts only)")
    lines.append("")
    for name, ydf in yearly.items():
        total_is = int(ydf["IS"].sum())
        total_ho = int(ydf["HOLDOUT"].sum())
        lines.append(f"### `{name}` — IS total {total_is:,}, HOLDOUT total {total_ho:,}")
        lines.append("")
        lines.append("| year | IS | HOLDOUT |")
        lines.append("|---:|---:|---:|")
        for _, row in ydf.iterrows():
            lines.append(f"| {int(row['year'])} | {row['IS']:,} | {row['HOLDOUT']:,} |")
        lines.append("")

    lines.append("## 6. NO-TEST flags (PREREG §3 house rule: <50 IS events per compared group)")
    lines.append("")
    lines.append("| cell | family | unit | IS compared-group sizes | NO-TEST | note |")
    lines.append("|---|---|---|---|:---:|---|")
    for r in notest_rows:
        groups_str = ", ".join(f"{k}={v:,}" for k, v in r["groups"].items())
        flag = "**NO-TEST**" if r["no_test"] else "ok"
        lines.append(f"| {r['cell']} | {r['family']} | {r['unit']} | {groups_str} | {flag} | {r['note']} |")
    lines.append("")

    lines.append("## 7. Feature completeness (% non-null, IS+HOLDOUT combined)")
    lines.append("")
    for name, cdf in completeness.items():
        lines.append(f"### `{name}`")
        lines.append("")
        lines.append("| feature | % non-null |")
        lines.append("|---|---:|")
        for _, row in cdf.iterrows():
            v = row["pct_nonnull"]
            lines.append(f"| {row['feature']} | {v if v is not None else 'MISSING'} |")
        lines.append("")

    lines.append("## 8. Knowability assertion")
    lines.append("")
    lines.append(
        f"`assert_knowable()` (structural check: every cross-referenced event feeding a feature at t0 "
        f"must have `confirmed_at <= t0`) was invoked and passed on **{knowability_checks:,}** individual "
        f"event lookups (prior LEVEL_TESTED counts for F1b's `prior_test_count`, plus a same-bar-or-later "
        f"assertion on every terminal-event linkage in `excursion_episodes`), **{knowability_violations}** "
        f"violations. The extraction run would have raised `AssertionError` and halted before writing any "
        f"parquet on the first violation — this report existing at all IS the pass evidence (fail-closed "
        f"design, `research/ict_v2/phase3/extract.py::assert_knowable`)."
    )
    lines.append("")
    if conformance is not None:
        lines.append(
            "**Fast-path conformance (vectorization fidelity):** `run_conformance_checks()` ran at the "
            "START of the extraction (before any parquet write) and proved the fast vectorized path "
            "equals the slow per-event reference EXACTLY on a deterministic >=200-event sample per "
            "family: " + ", ".join(f"{k}={v:,}" for k, v in conformance.items()) + " comparisons, 0 "
            "mismatches (the run would have aborted on the first mismatch). The vectorized outcomes / "
            "efficiency / prior_test_count are therefore bit-for-bit identical to the audited slow path."
        )
        lines.append("")

    lines.append("## 9. Integrity: unsplit rows (t0 outside both IS and HOLDOUT ranges)")
    lines.append("")
    for name, n in unsplit_counts.items():
        lines.append(f"- `{name}`: {n}")
    lines.append("")

    lines.append("## 10. Output files")
    lines.append("")
    lines.append(
        "`research/ict_v2/phase3/data/{unit}_is.parquet` and `{unit}_holdout.parquet` for unit in "
        "`{" + ", ".join(dfs_is.keys()) + "}`. IS and HOLDOUT written to SEPARATE files; this "
        "extraction run never re-reads the holdout files after writing them (PREREG §6/§8)."
    )
    lines.append("")

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write(content)
    return REPORT_PATH
