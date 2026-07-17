"""WP-F orchestrator (PREREG_PHASE3.md §4-§8, git hash cd652ea81093): mandatory
synthetic self-test, then the IS run on *_is.parquet ONLY (the HOLDOUT files are never
opened -- the §6 holdout pass is a separate later execution), then the report to
reports/ict_v2/03_phase3_is_results.md. NO PF/WR/expectancy; nothing outside the 17
preregistered cells.

    python3 -m research.ict_v2.phase3.run_wp_f
"""
from __future__ import annotations

import os
import time
from typing import Dict, List

import numpy as np
import pandas as pd

from . import wp_f_cells as W
from .wp_f_selftest import run_selftest

BOT_REPO = os.path.expanduser("~/trading-team/bot/nq-liq-bot")
DATA_DIR = os.path.join(BOT_REPO, "research", "ict_v2", "phase3", "data")
REPORT_PATH = os.path.join(BOT_REPO, "reports", "ict_v2", "03_phase3_is_results.md")
PREREG_HASH = "cd652ea81093"

# HARD GUARD: WP-F may only ever read IS files. Opening a holdout file is a prereg
# violation (§6/§8) -- this loader refuses any path containing "holdout".
_IS_FILES = {
    "excursion_episodes": "excursion_episodes_is.parquet",
    "sweep_confirmed": "sweep_confirmed_is.parquet",
    "displacement_qualified": "displacement_qualified_is.parquet",
    "mss": "mss_is.parquet",
    "level_tested": "level_tested_is.parquet",
    "fvg_tested": "fvg_tested_is.parquet",
}


def _log(m: str) -> None:
    print(f"[wp-f {time.strftime('%H:%M:%S')}] {m}", flush=True)


def load_is(name: str) -> pd.DataFrame:
    fn = _IS_FILES[name]
    if "holdout" in fn:
        raise RuntimeError("WP-F must never open a holdout file (PREREG §6/§8).")
    return pd.read_parquet(os.path.join(DATA_DIR, fn))


def _fmt(x, nd=3):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:.{nd}f}"


def _verdict(g1, g2, g3, g4):
    return "SURVIVES" if (g1 and g2 and g3 and g4) else "dies"


def write_report(contrast: List[W.OutcomeResult], f2: List[W.F2Result], selftest: Dict, timings: Dict) -> str:
    lines: List[str] = []
    lines.append("# ICT V2 Phase 3, WP-F — IS Measurement Results")
    lines.append("")
    lines.append(
        f"**Governs:** `research/ict_v2/PREREG_PHASE3.md` v1.0 + Amendment v1.1, git hash `{PREREG_HASH}`. "
        "**Scope:** WP-F IS run (§4-§5) on the *_is.parquet files ONLY. The frozen HOLDOUT files were "
        "NOT opened — the §6 confirmatory pass is a separate later execution. No PF/WR/expectancy; nothing "
        "outside the 17 preregistered cells."
    )
    lines.append("")

    # -- self-test --
    lines.append("## 1. Synthetic self-test (§8, mandatory gate before the IS run)")
    lines.append("")
    lines.append("| check | result | required |")
    lines.append("|---|:---:|:---:|")
    for name, actual, expected in selftest["checks"]:
        lines.append(f"| {name} | {actual} | {expected} |")
    lines.append("")
    lines.append(
        f"**Self-test verdict: {'PASSED' if selftest['all_ok'] else 'FAILED'}.** A planted effect passes all gates, "
        "a null placebo fails G1, a B-confound placebo (real raw effect fully explained by baseline B) dies at G2, "
        "and the F2 AUC path passes on planted signal / fails on noise. The IS run below was permitted only because "
        "these all behaved correctly."
    )
    lines.append("")

    # -- method notes --
    lines.append("## 2. Estimators & gates (as implemented, per §4-§5)")
    lines.append("")
    lines.append(
        "- Contrast cells (F1, F3-F7): Δ = mean/proportion(group A) − (group B); 95% CI + two-sided p via the "
        "weekly block bootstrap (resample calendar weeks, 2,000 draws, vectorized via per-week sums). Floors: "
        "probabilities |Δ|≥0.05, magnitudes |Δ|≥0.10 ATR.\n"
        "- F2 (prediction): standardized logistic regression (IRLS, numpy-only — sklearn is not installed), blocked "
        "5-fold CV by calendar week, metric = out-of-fold AUC uplift of (B+ICT) over (B alone); CI/p via the weekly "
        "block bootstrap of the AUC uplift (exact c⊤Uc quadratic form over the cross-week Mann-Whitney matrix).\n"
        "- G1: CI excludes 0 AND floor met (F2: uplift ≥0.02 & CI excl 0). G2: B-residualized contrast retains ≥50% "
        "of raw size, same sign (F2: uplift over B IS the metric → holds by construction). G3: sign consistent in ≥3 "
        "of 4 IS-years AND no year >60% of the aggregate (n·Δ share). G4: Benjamini-Hochberg q=0.10 within family.\n"
        "- Two-outcome cells: each declared outcome is a separate statistic; the CELL survives iff ≥1 outcome passes "
        "G1∧G2∧G3∧G4; BH is applied within each family over ALL its (cell,outcome) statistics (conservative FDR reading; "
        "the prereg's cell/outcome granularity is imprecise — flagged for Fable)."
    )
    lines.append("")

    # -- per-outcome detailed table --
    lines.append("## 3. Per-cell / per-outcome results (contrast families F1, F3–F7)")
    lines.append("")
    lines.append("| cell | family | unit | outcome | groups (A vs B) | Δ | 95% CI | floor✓ | G1 | G2 ret | G2 | per-yr Δ signs | G3 | p | q(BH) | G4 | verdict |")
    lines.append("|---|---|---|---|---|---:|---|:---:|:---:|---:|:---:|---|:---:|---:|---:|:---:|:---:|")
    for r in contrast:
        floor_ok = "✓" if abs(r.delta) >= r.floor else "✗"
        signs = "".join("+" if (v is not None and np.isfinite(v) and v > 0) else ("−" if (v is not None and np.isfinite(v) and v < 0) else "·") for v in r.per_year.values())
        ci = f"[{_fmt(r.ci_lo)}, {_fmt(r.ci_hi)}]"
        lines.append(
            f"| {r.cell} | {r.family} | {r.unit} | {r.outcome} | {r.groupA} vs {r.groupB} | {_fmt(r.delta)} | {ci} | "
            f"{floor_ok} | {r.g1} | {_fmt(r.g2_retention,2)} | {r.g2} | {signs} | {r.g3} | {_fmt(r.p_value,4)} | "
            f"{_fmt(r.q_bh,4)} | {r.g4} | {_verdict(r.g1,r.g2,r.g3,r.g4)} |"
        )
    lines.append("")

    # -- F2 table --
    lines.append("## 4. F2 prediction cells (AUC uplift of B+ICT over baseline B)")
    lines.append("")
    lines.append("| cell | target | n | n_pos | AUC(B) | AUC(B+ICT) | uplift | 95% CI | G1(≥.02) | G2 | per-yr uplift signs | G3 | p | q(BH) | G4 | verdict |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|:---:|:---:|---|:---:|---:|---:|:---:|:---:|")
    for r in f2:
        signs = "".join("+" if (v is not None and np.isfinite(v) and v > 0) else ("−" if (v is not None and np.isfinite(v) and v < 0) else "·") for v in r.per_year.values())
        ci = f"[{_fmt(r.ci_lo)}, {_fmt(r.ci_hi)}]"
        lines.append(
            f"| {r.cell} | {r.target} | {r.n:,} | {r.n_pos:,} | {_fmt(r.auc_base)} | {_fmt(r.auc_full)} | {_fmt(r.uplift)} | "
            f"{ci} | {r.g1} | {r.g2} | {signs} | {r.g3} | {_fmt(r.p_value,4)} | {_fmt(r.q_bh,4)} | {r.g4} | "
            f"{_verdict(r.g1,r.g2,r.g3,r.g4)} |"
        )
    lines.append("")

    # -- per-cell one-line verdict summary --
    lines.append("## 5. Per-cell verdict summary (one line per preregistered cell)")
    lines.append("")
    cell_map: Dict[str, List] = {}
    for r in contrast:
        cell_map.setdefault(r.cell, []).append(r)
    for r in f2:
        cell_map.setdefault(r.cell, []).append(r)
    order = ["F1a", "F1b", "F1c", "F1d", "F1e", "F2a", "F2b", "F3", "F4a", "F4b", "F4c", "F5a", "F5b", "F6a", "F6b", "F7a", "F7b"]
    lines.append("| cell | family | survives? | driving outcome (if any) | G1 | G2 | G3 | G4 |")
    lines.append("|---|---|:---:|---|:---:|:---:|:---:|:---:|")
    survivors = []
    for cell in order:
        rs = cell_map.get(cell, [])
        if not rs:
            lines.append(f"| {cell} | — | NO-DATA | — | — | — | — | — |")
            continue
        winning = next((r for r in rs if r.survives), None)
        fam = rs[0].family
        if winning is not None:
            survivors.append(cell)
            oc = getattr(winning, "outcome", getattr(winning, "target", ""))
            lines.append(f"| {cell} | {fam} | **SURVIVES** | {oc} | {winning.g1} | {winning.g2} | {winning.g3} | {winning.g4} |")
        else:
            # show the best-progressing outcome for context (max gates cleared)
            best = max(rs, key=lambda r: (r.g1, r.g2, r.g3, r.g4))
            oc = getattr(best, "outcome", getattr(best, "target", ""))
            lines.append(f"| {cell} | {fam} | dies | {oc} | {best.g1} | {best.g2} | {best.g3} | {best.g4} |")
    lines.append("")
    lines.append(f"**IS survivors (pass G1∧G2∧G3∧G4): {len(survivors)}** — {survivors if survivors else 'none'}.")
    lines.append("")
    lines.append(
        "Per §7 verdict rules, the survivor set determines routing; only cells that pass all IS gates are eligible "
        "for the single §6 holdout pass (a later, separate execution). This report makes NO holdout contact."
    )
    lines.append("")

    # -- runtime --
    lines.append("## 6. Runtime")
    lines.append("")
    lines.append("| stage | seconds |")
    lines.append("|---|---:|")
    for k, v in timings.items():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write(content)
    return REPORT_PATH


def main() -> None:
    t_start = time.time()
    timings: Dict[str, float] = {}

    _log("running mandatory synthetic self-test (§8) ...")
    t = time.time()
    selftest = run_selftest()
    timings["selftest_s"] = round(time.time() - t, 2)
    if not selftest["all_ok"]:
        raise SystemExit("SELF-TEST FAILED — IS run aborted per PREREG §8 (planted must pass, null must fail).")

    _log("loading IS datasets (holdout files NOT opened) ...")
    t = time.time()
    exc = load_is("excursion_episodes")
    sweep = load_is("sweep_confirmed")
    disp = load_is("displacement_qualified")
    mss = load_is("mss")
    level = load_is("level_tested")
    fvg = load_is("fvg_tested")
    timings["load_is_s"] = round(time.time() - t, 2)

    contrast: List[W.OutcomeResult] = []
    t = time.time(); contrast += W.run_F1(exc); timings["F1_s"] = round(time.time() - t, 2)
    t = time.time(); contrast += W.run_F3(sweep); timings["F3_s"] = round(time.time() - t, 2)
    t = time.time(); contrast += W.run_F4(disp); timings["F4_s"] = round(time.time() - t, 2)
    t = time.time(); contrast += W.run_F5(disp, mss); timings["F5_s"] = round(time.time() - t, 2)
    t = time.time(); contrast += W.run_F6(sweep, mss); timings["F6_s"] = round(time.time() - t, 2)
    t = time.time(); contrast += W.run_F7(level, fvg); timings["F7_s"] = round(time.time() - t, 2)

    t = time.time(); f2 = W.run_F2(exc); timings["F2_s"] = round(time.time() - t, 2)

    _log("applying Benjamini-Hochberg within families (G4) ...")
    W.apply_bh_within_families(contrast, f2, q=0.10)

    timings["total_s"] = round(time.time() - t_start, 2)
    path = write_report(contrast, f2, selftest, timings)
    _log(f"report written: {path}")

    # compact stdout summary (one line per cell)
    cell_map: Dict[str, List] = {}
    for r in contrast + f2:
        cell_map.setdefault(r.cell, []).append(r)
    survivors = []
    for cell in ["F1a","F1b","F1c","F1d","F1e","F2a","F2b","F3","F4a","F4b","F4c","F5a","F5b","F6a","F6b","F7a","F7b"]:
        rs = cell_map.get(cell, [])
        win = next((r for r in rs if r.survives), None) if rs else None
        if win:
            survivors.append(cell)
        # show the DRIVING outcome's gate tuple (the survivor, or the best-progressing outcome) --
        # never OR-aggregate gates across different outcomes (that would be misleading).
        drv = win if win else (max(rs, key=lambda r: (r.g1, r.g2, r.g3, r.g4)) if rs else None)
        gates = "|".join(f"{g}={getattr(drv, g)}" for g in ("g1", "g2", "g3", "g4")) if drv else "no-data"
        print(f"CELL {cell}: {'SURVIVES' if win else 'dies'}  [{gates}]", flush=True)
    print(f"SURVIVORS: {survivors if survivors else 'none'}", flush=True)
    print(f"SELF-TEST: {'PASSED' if selftest['all_ok'] else 'FAILED'}  RUNTIME: {timings['total_s']}s", flush=True)


if __name__ == "__main__":
    main()
