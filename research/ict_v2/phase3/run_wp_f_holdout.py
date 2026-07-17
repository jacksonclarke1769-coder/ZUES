"""WP-F §6 HOLDOUT confirmation pass (PREREG_PHASE3.md §6, git hash cd652ea81093; IS
report committed at fb798d7). SEPARATE, single execution, run AFTER the IS report was
committed and adjudicated by Fable.

ONLY the two Fable-certified IS survivors touch holdout data:
  * F1a  (unit excursion_episodes) -- outcome P(terminal=SWEEP_CONFIRMED), groups
          weekly vs intraday level timeframe class.
  * F4b  (unit displacement_qualified) -- outcome maxrev(24), groups close_location
          top vs bottom tercile.
F2a is NOT taken to holdout (Fable ruling: survives the prereg's letter, fails its
spirit -- re-scope required; operator-gated amendment). No other cell is measured.

Only these two holdout files are opened, and only each cell's preregistered columns are
read (`columns=` on read_parquet). §6 survival rule: HOLDOUT effect has the SAME SIGN as
the IS effect AND |holdout Δ| >= 0.5 * |IS Δ|. B-residualized holdout Δ is reported as
supplementary confirmation (the cells' IS survival required G2) but is not the §6 gate.
No PF/WR/expectancy.
"""
from __future__ import annotations

import os
import time
from typing import Dict

import numpy as np
import pandas as pd

from . import statlib as S
from .wp_f_cells import CAT_B, NUM_B, N_DRAWS, _tercile_masks

BOT_REPO = os.path.expanduser("~/trading-team/bot/nq-liq-bot")
DATA_DIR = os.path.join(BOT_REPO, "research", "ict_v2", "phase3", "data")
REPORT_PATH = os.path.join(BOT_REPO, "reports", "ict_v2", "04_phase3_verdict.md")
PREREG_HASH = "cd652ea81093"
IS_REPORT_COMMIT = "fb798d7"


def _log(m: str) -> None:
    print(f"[wp-f holdout {time.strftime('%H:%M:%S')}] {m}", flush=True)


def _fmt(x, nd=3):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:.{nd}f}"


def _contrast(df: pd.DataFrame, maskA, maskB, outcome, kind: str, cat_B=CAT_B, num_B=NUM_B):
    week, W = S.week_ids(df["t0"])
    C = S.make_draw_matrix(W, N_DRAWS, seed=54321)
    raw = S.contrast_bootstrap(week, maskA, maskB, outcome, W, C)
    if kind == "prob":
        resid = S.logistic_residualize(df, outcome, np.isfinite(outcome), cat_B, num_B)
    else:
        resid = S.ols_residualize(df, outcome, cat_B, num_B)
    rres = S.contrast_bootstrap(week, maskA, maskB, resid, W, C)
    return raw, rres


def run_holdout() -> Dict:
    t0 = time.time()
    results = {}

    # ---- F1a: excursion_episodes, P(SWEEP_CONFIRMED), weekly vs intraday ----
    _log("F1a: opening excursion_episodes_holdout.parquet (only preregistered columns) ...")
    cols_f1a = ["t0", "level_timeframe_class", "terminal_event_type"] + CAT_B + NUM_B
    dfh = pd.read_parquet(os.path.join(DATA_DIR, "excursion_episodes_holdout.parquet"), columns=cols_f1a)
    dfi = pd.read_parquet(
        os.path.join(DATA_DIR, "excursion_episodes_is.parquet"), columns=cols_f1a
    )  # IS reference magnitude (IS files are not holdout)
    tf_h = dfh["level_timeframe_class"].to_numpy()
    y_h = (dfh["terminal_event_type"].to_numpy() == "SWEEP_CONFIRMED").astype(float)
    raw_h, rres_h = _contrast(dfh, tf_h == "weekly", tf_h == "intraday", y_h, "prob")
    tf_i = dfi["level_timeframe_class"].to_numpy()
    y_i = (dfi["terminal_event_type"].to_numpy() == "SWEEP_CONFIRMED").astype(float)
    raw_i, _ = _contrast(dfi, tf_i == "weekly", tf_i == "intraday", y_i, "prob")
    results["F1a"] = _survival("F1a", "P(SWEEP_CONFIRMED)", "weekly vs intraday", "prob", raw_i, raw_h, rres_h)
    _log(f"F1a done: IS Δ={raw_i.delta:.4f}  HOLDOUT Δ={raw_h.delta:.4f}  -> {results['F1a']['verdict']}")

    # ---- F4b: displacement_qualified, maxrev(24), close_location top vs bottom tercile ----
    _log("F4b: opening displacement_qualified_holdout.parquet (only preregistered columns) ...")
    cols_f4b = ["t0", "close_location", "maxrev_24"] + CAT_B + NUM_B
    dfh2 = pd.read_parquet(os.path.join(DATA_DIR, "displacement_qualified_holdout.parquet"), columns=cols_f4b)
    dfi2 = pd.read_parquet(os.path.join(DATA_DIR, "displacement_qualified_is.parquet"), columns=cols_f4b)
    tmh = _tercile_masks(dfh2["close_location"].to_numpy(dtype=float), np.ones(len(dfh2), bool))
    tmi = _tercile_masks(dfi2["close_location"].to_numpy(dtype=float), np.ones(len(dfi2), bool))
    mv_h = dfh2["maxrev_24"].to_numpy(dtype=float)
    mv_i = dfi2["maxrev_24"].to_numpy(dtype=float)
    raw_h2, rres_h2 = _contrast(dfh2, tmh[0], tmh[1], mv_h, "mag")
    raw_i2, _ = _contrast(dfi2, tmi[0], tmi[1], mv_i, "mag")
    results["F4b"] = _survival("F4b", "maxrev24", "close_location_top vs close_location_bottom", "mag", raw_i2, raw_h2, rres_h2)
    _log(f"F4b done: IS Δ={raw_i2.delta:.4f}  HOLDOUT Δ={raw_h2.delta:.4f}  -> {results['F4b']['verdict']}")

    results["_runtime_s"] = round(time.time() - t0, 2)
    return results


def _survival(cell, outcome, groups, kind, raw_is, raw_hold, rres_hold) -> Dict:
    same_sign = np.sign(raw_hold.delta) == np.sign(raw_is.delta) and raw_is.delta != 0
    ratio = abs(raw_hold.delta) / abs(raw_is.delta) if raw_is.delta != 0 else np.nan
    survives = bool(same_sign and np.isfinite(ratio) and ratio >= 0.50)
    ci_excl0 = (raw_hold.ci_lo > 0 and raw_hold.ci_hi > 0) or (raw_hold.ci_lo < 0 and raw_hold.ci_hi < 0)
    g2_ret_hold = (rres_hold.delta / raw_hold.delta) if raw_hold.delta != 0 else np.nan
    return {
        "cell": cell, "outcome": outcome, "groups": groups, "kind": kind,
        "is_delta": raw_is.delta, "hold_delta": raw_hold.delta,
        "hold_ci_lo": raw_hold.ci_lo, "hold_ci_hi": raw_hold.ci_hi, "hold_p": raw_hold.p_value,
        "same_sign": bool(same_sign), "magnitude_ratio": float(ratio) if np.isfinite(ratio) else np.nan,
        "ci_excludes_zero_supp": bool(ci_excl0), "g2_retention_hold_supp": float(g2_ret_hold) if np.isfinite(g2_ret_hold) else np.nan,
        "n_a": raw_hold.n_a, "n_b": raw_hold.n_b,
        "verdict": "CERTIFIED-CONDITIONAL" if survives else "REFUTED",
    }


def write_report(res: Dict) -> str:
    L = []
    L.append("# ICT V2 Phase 3 — WP-F §6 Holdout Verdict")
    L.append("")
    L.append(
        f"**Governs:** `research/ict_v2/PREREG_PHASE3.md` v1.0 + Amendment v1.1, git hash `{PREREG_HASH}`. "
        f"**IS report:** committed `{IS_REPORT_COMMIT}` (`reports/ict_v2/03_phase3_is_results.md`), adjudicated by "
        "Fable. **Scope:** the single §6 holdout confirmation pass — a separate execution touching the frozen "
        "holdout files EXACTLY ONCE, only for the two Fable-certified IS survivors (F1a, F4b), reading only each "
        "cell's preregistered columns. F2a was NOT taken to holdout (Fable ruling — see §3). No PF/WR/expectancy."
    )
    L.append("")
    L.append("## 1. Holdout confirmation (§6 rule: same sign AND |holdout Δ| ≥ 0.5·|IS Δ|)")
    L.append("")
    L.append("| cell | unit | outcome | groups (A vs B) | IS Δ | HOLDOUT Δ | 95% CI (holdout) | same sign | |Δ| ratio | ≥0.5 | VERDICT |")
    L.append("|---|---|---|---|---:|---:|---|:---:|---:|:---:|:---:|")
    for cell in ("F1a", "F4b"):
        r = res[cell]
        unit = "excursion_episodes" if cell == "F1a" else "displacement_qualified"
        ci = f"[{_fmt(r['hold_ci_lo'])}, {_fmt(r['hold_ci_hi'])}]"
        ge = "✓" if (np.isfinite(r["magnitude_ratio"]) and r["magnitude_ratio"] >= 0.5) else "✗"
        L.append(
            f"| {cell} | {unit} | {r['outcome']} | {r['groups']} | {_fmt(r['is_delta'])} | {_fmt(r['hold_delta'])} | "
            f"{ci} | {r['same_sign']} | {_fmt(r['magnitude_ratio'],2)} | {ge} | **{r['verdict']}** |"
        )
    L.append("")
    L.append(
        "Supplementary (not the §6 gate): holdout bootstrap p and B-residualized retention — "
        + "; ".join(
            f"{c}: p={_fmt(res[c]['hold_p'],4)}, CI-excl-0={res[c]['ci_excludes_zero_supp']}, "
            f"G2-retention(holdout)={_fmt(res[c]['g2_retention_hold_supp'],2)}, n_A={res[c]['n_a']:,}, n_B={res[c]['n_b']:,}"
            for c in ("F1a", "F4b")
        )
        + "."
    )
    L.append("")

    # ---- final per-cell verdict ----
    L.append("## 2. Final Phase-3 verdict per cell")
    L.append("")
    f1a_cc = res["F1a"]["verdict"] == "CERTIFIED-CONDITIONAL"
    f4b_cc = res["F4b"]["verdict"] == "CERTIFIED-CONDITIONAL"
    L.append(f"- **F1a** (salience: weekly vs intraday level → P(SWEEP_CONFIRMED)): **{res['F1a']['verdict']}**.")
    L.append(f"- **F4b** (displacement close-location tercile → maxrev(24)): **{res['F4b']['verdict']}**.")
    L.append("")

    # ---- §7 routing ----
    L.append("## 3. §7 routing summary")
    L.append("")
    L.append(
        "- **F2a** — IS-SURVIVOR, **HOLDOUT DEFERRED, re-scope required.** Fable ruling: F2a passes the prereg's "
        "letter but fails its spirit. For the `reclaim_speed_bars=1` majority (~69% of confirmed sweeps) the terminal "
        "resolves ON the t0 (first-beyond) bar, so the preregistered `t0 close-location` feature is quasi-"
        "contemporaneous with the label — AUC 0.956 mostly *reads* the outcome rather than *predicting* it. This is a "
        "design defect in the cell's own definition (t0 = first-beyond close while terminals can resolve same-bar), "
        "NOT look-ahead and NOT an extraction error. It did NOT touch holdout. Disposition: re-scope via a "
        "prereg amendment (either restrict the unit to episodes UNRESOLVED at t0, or restrict features to strictly-"
        "pre-t0 bars); the amendment is OPERATOR-GATED and the re-scoped cell is not implemented here."
    )
    L.append(
        "  - **Residual scientific content carried to the amendment:** whether acceptance/rejection of a level "
        "excursion is predictable *before* it resolves is exactly the book's Chapter-20 question, and it remains "
        "**OPEN**. The tautological version (F2a as written) answers nothing about it; the re-scoped cell would."
    )
    L.append(
        "- **F6a, F6b** (remaining-opportunity: ny_am session-range-consumed → |fwd24| / maxcont24): route to "
        "**ATLAS as market-state, NOT ICT.** Both showed large raw contrasts (|Δ|≈1.3–1.6 ATR) but the effect is "
        "fully explained by baseline set B (G2 retention ≈ 0) — i.e. it is generic volatility/opportunity structure, "
        "not a decision-layer (ICT) signal. Per §7 this is filed to ATLAS; the ICT label is redundant here."
    )
    L.append(
        "- **F2b** (sign(fwd24) prediction): AUC uplift ≈ 0 — a **reconfirmation of the ATLAS meta-law "
        "(direction ≈ null at event granularity)**, cited in the prereg as a known prior. Filed as such."
    )
    L.append(
        "- **12 dead cells** (no conditional structure on IS; not taken further): F1b, F1c, F1d, F1e, F2b, F3, F4a, "
        "F4c, F5a, F5b, F7a, F7b — each failed >=1 IS gate (floor/G1, or G2 market-state, or G3 era-instability, or "
        "BH/G4). Recorded for the causal ledger. (F2b is among these 12 and additionally carries the direction≈null "
        "note above.)"
    )
    L.append("")

    # ---- programme verdict ----
    n_cc = int(f1a_cc) + int(f4b_cc)
    L.append("## 4. Programme verdict (§7)")
    L.append("")
    if n_cc >= 1:
        L.append(
            f"**{n_cc} feature(s) CERTIFIED-CONDITIONAL** (passed all IS gates AND the §6 holdout): "
            + ", ".join([c for c in ("F1a", "F4b") if res[c]["verdict"] == "CERTIFIED-CONDITIONAL"])
            + ". Per §7, a certified-conditional feature becomes a Phase-4 building block (acceptance-gate / "
            "Alpha-Asset-#2 candidate), to be built only under its own Phase-4/5 prereg. Phase 3 is CLOSED for the "
            "measured cells, pending the operator's F2a re-scope amendment decision."
        )
    else:
        L.append(
            "**0 features survived the holdout.** Per §7 the decision layer carries no confirmed conditional "
            "structure on price-only NQ data for the measured cells; Phase 4 would test only the declared raw "
            "sequences. Phase 3 CLOSED for the measured cells, pending the operator's F2a re-scope amendment."
        )
    L.append("")
    L.append(f"*Holdout pass runtime: {res['_runtime_s']} s. Holdout files opened exactly once, for F1a and F4b only.*")
    L.append("")

    content = "\n".join(L)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write(content)
    return REPORT_PATH


def main() -> None:
    res = run_holdout()
    path = write_report(res)
    _log(f"verdict report written: {path}")
    for cell in ("F1a", "F4b"):
        r = res[cell]
        print(
            f"HOLDOUT {cell}: IS Δ={r['is_delta']:.4f} HOLD Δ={r['hold_delta']:.4f} "
            f"same_sign={r['same_sign']} ratio={r['magnitude_ratio']:.2f} -> {r['verdict']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
