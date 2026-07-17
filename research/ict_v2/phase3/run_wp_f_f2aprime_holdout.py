"""WP-F Amendment v1.2 — F2a' §6 HOLDOUT confirmation (PREREG_PHASE3.md Amendment v1.2,
hash bc35ceddcb10; IS report fb798d7). FINAL Phase-3 measurement. SEPARATE, single
execution, after the F2a' IS survival was adjudicated ACCEPTED by Fable.

Confirmatory holdout for a prediction cell: the B and B+ICT logistic models are fit on
the IS post-t0 population (IS files are not holdout), then evaluated EXACTLY ONCE on the
frozen holdout post-t0 population. §6 F2 survival rule: holdout AUC uplift >= 0.01 AND
same sign as the IS uplift (which was +0.347).

Only F2a's needed columns are read from `excursion_episodes_holdout`. DISCLOSURE (per
Amendment v1.2): that file was previously opened once for F1a's columns (which included
the terminal column); no F2a' FEATURE column had been read from holdout before now. No
other holdout file is touched. No PF/WR/expectancy.
"""
from __future__ import annotations

import os
import time

import numpy as np
import pandas as pd

from . import statlib as S
from . import wp_f_cells as W

BOT_REPO = os.path.expanduser("~/trading-team/bot/nq-liq-bot")
DATA_DIR = os.path.join(BOT_REPO, "research", "ict_v2", "phase3", "data")
VERDICT_PATH = os.path.join(BOT_REPO, "reports", "ict_v2", "04_phase3_verdict.md")
AMEND_HASH = "bc35ceddcb10"
IS_COMMIT = "fb798d7"

IS_UPLIFT = 0.347  # committed F2a' IS uplift (report §v1.2), for the same-sign / context check
N_DRAWS = 2000

# exactly the columns F2a' needs from the holdout file
_F2AP_COLS = ["t0", "terminal_event_type", "terminal_confirmed_at"] + list(
    dict.fromkeys(W.F2_CAT_FULL + W.F2_NUM_FULL)
)


def _log(m: str) -> None:
    print(f"[wp-f v1.2 holdout {time.strftime('%H:%M:%S')}] {m}", flush=True)


def _fmt(x, nd=3):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:.{nd}f}"


def _fit_predict(df_train, y_train, df_eval, cat, num):
    Xtr, fit = S.build_design(df_train, cat, num, fitted=None)
    beta = S.logistic_irls(Xtr, y_train)
    Xev, _ = S.build_design(df_eval, cat, num, fitted=fit)
    return S.logistic_predict(Xev, beta)


def main() -> None:
    t0 = time.time()

    _log("loading IS excursion (train; IS files are not holdout) and restricting to post-t0 ...")
    dfi = pd.read_parquet(os.path.join(DATA_DIR, "excursion_episodes_is.parquet"))
    is_kept, is_meta = W.restrict_post_t0(dfi)
    y_is = (is_kept["terminal_event_type"].to_numpy() == "SWEEP_CONFIRMED").astype(np.int64)

    _log("opening excursion_episodes_holdout.parquet — ONLY F2a' columns — and restricting to post-t0 ...")
    dfh = pd.read_parquet(os.path.join(DATA_DIR, "excursion_episodes_holdout.parquet"), columns=_F2AP_COLS)
    h_kept, h_meta = W.restrict_post_t0(dfh)
    y_h = (h_kept["terminal_event_type"].to_numpy() == "SWEEP_CONFIRMED").astype(np.int64)
    _log(f"  holdout kept post-t0={h_meta['kept_post_t0_pair']:,} "
         f"(excluded same-bar={h_meta['excluded_same_bar_resolutions']:,}); "
         f"class SC={h_meta['n_sweep_confirmed']:,} vs AB={h_meta['n_accepted_breakout']:,}")

    _log("fitting B-only on IS, scoring holdout ...")
    p_base = _fit_predict(is_kept, y_is, h_kept, W.CAT_B, W.NUM_B)
    _log("fitting B+ICT on IS, scoring holdout ...")
    p_full = _fit_predict(is_kept, y_is, h_kept, W.F2_CAT_FULL, W.F2_NUM_FULL)

    auc_base = S.auc_score(p_base, y_h)
    auc_full = S.auc_score(p_full, y_h)
    uplift = auc_full - auc_base
    same_sign = np.sign(uplift) == np.sign(IS_UPLIFT)
    survives = bool(same_sign and uplift >= 0.01)

    # supplementary: weekly-block-bootstrap CI of the holdout uplift (context, not the gate)
    week, Wn = S.week_ids(h_kept["t0"])
    C = S.make_draw_matrix(Wn, N_DRAWS, seed=246810)
    boot = S.auc_uplift_bootstrap(p_base, p_full, y_h, week, Wn, C)

    runtime = round(time.time() - t0, 2)
    _log(f"F2a' HOLDOUT: AUC(B)={auc_base:.4f} AUC(B+ICT)={auc_full:.4f} uplift={uplift:.4f} "
         f"(IS uplift {IS_UPLIFT:.3f})  CI[{boot.ci_lo:.4f},{boot.ci_hi:.4f}]  -> "
         f"{'CERTIFIED-CONDITIONAL' if survives else 'REFUTED'}")

    _update_verdict(is_meta, h_meta, auc_base, auc_full, uplift, boot, survives, runtime)

    print(f"F2APRIME_HOLDOUT uplift={uplift:.4f} CI[{boot.ci_lo:.4f},{boot.ci_hi:.4f}] "
          f"same_sign={same_sign} ge_0.01={uplift>=0.01} -> "
          f"{'CERTIFIED-CONDITIONAL' if survives else 'REFUTED'}", flush=True)


def _update_verdict(is_meta, h_meta, auc_base, auc_full, uplift, boot, survives, runtime) -> None:
    verdict = "CERTIFIED-CONDITIONAL" if survives else "REFUTED"
    L = []
    L.append("\n\n---\n")
    L.append(f"## v1.2 — F2a′ §6 holdout (Amendment v1.2, git hash `{AMEND_HASH}`)")
    L.append("")
    L.append(
        f"Final Phase-3 measurement. F2a′ (F2a re-scoped to episodes whose FSM terminal resolves STRICTLY AFTER t0) "
        f"passed all IS gates (uplift 0.347; leak audit accepted by Fable) and was taken to the one-shot §6 holdout. "
        f"Confirmatory design: B and B+ICT logistic models FIT on the IS post-t0 population (committed IS run "
        f"`{IS_COMMIT}`), evaluated EXACTLY ONCE on the frozen holdout post-t0 population. §6 F2 rule: holdout AUC "
        "uplift ≥ 0.01 AND same sign as IS. DISCLOSURE: `excursion_episodes_holdout` was previously opened once for "
        "F1a's columns (incl. the terminal column); no F2a′ FEATURE column had been read from holdout before this pass."
    )
    L.append("")
    L.append("| quantity | IS (train) | HOLDOUT (eval) |")
    L.append("|---|---:|---:|")
    L.append(f"| kept post-t0 episodes | {is_meta['kept_post_t0_pair']:,} | {h_meta['kept_post_t0_pair']:,} |")
    L.append(f"| excluded same-bar resolutions | {is_meta['excluded_same_bar_resolutions']:,} | {h_meta['excluded_same_bar_resolutions']:,} |")
    L.append(f"| SWEEP_CONFIRMED | {is_meta['n_sweep_confirmed']:,} | {h_meta['n_sweep_confirmed']:,} |")
    L.append(f"| ACCEPTED_BREAKOUT | {is_meta['n_accepted_breakout']:,} | {h_meta['n_accepted_breakout']:,} |")
    L.append("")
    L.append("| metric | value |")
    L.append("|---|---:|")
    L.append(f"| IS AUC uplift (committed) | {IS_UPLIFT:.3f} |")
    L.append(f"| holdout AUC(B-only) | {_fmt(auc_base,4)} |")
    L.append(f"| holdout AUC(B+ICT) | {_fmt(auc_full,4)} |")
    L.append(f"| **holdout AUC uplift** | **{_fmt(uplift,4)}** |")
    L.append(f"| holdout uplift 95% CI (weekly block bootstrap, supplementary) | [{_fmt(boot.ci_lo,4)}, {_fmt(boot.ci_hi,4)}] |")
    L.append(f"| §6 bar (≥0.01, same sign) | {'MET' if survives else 'NOT MET'} |")
    L.append("")
    L.append(f"### F2a′ FINAL VERDICT: **{verdict}**")
    L.append("")
    if survives:
        L.append(
            f"The out-of-sample holdout AUC uplift ({_fmt(uplift,4)}) clears the §6 bar (≥0.01, same positive sign as "
            "the IS uplift), confirming genuine ex-ante conditional structure in acceptance-vs-rejection once the "
            "same-bar tautological episodes are excluded. Per §7, **F2a′ is CERTIFIED-CONDITIONAL** and joins F1a as a "
            "Phase-4 building block (acceptance-gate / Alpha-Asset-#2 candidate), to be built only under its own "
            "Phase-4/5 prereg — including the deferred level-kind attribution check, which is Phase-4 work, not a §6 "
            "gate. This is the honest answer to the book's Chapter-20 question for this event stream: whether a level "
            "excursion is accepted or rejected is partly predictable BEFORE it resolves — carried chiefly by the "
            "initial thrust depth at t0, not by the discredited same-bar close-location tautology."
        )
    else:
        L.append(
            f"The out-of-sample holdout AUC uplift ({_fmt(uplift,4)}) fails the §6 bar (<0.01 or sign flip). The IS "
            "signal did not confirm out of sample; **F2a′ is REFUTED**. The re-scoped Chapter-20 question resolves "
            "negative for this event stream on the frozen holdout."
        )
    L.append("")
    L.append(
        f"**Phase-3 certified-conditional set is now: F1a"
        + (", F2a′" if survives else "")
        + f".** F2a's original (unrestricted) cell remains superseded by F2a′ per Amendment v1.2. Amendment v1.2 paper "
        f"trail closed (prereg hash `{AMEND_HASH}`, IS base `{IS_COMMIT}`). This was the final measurement of Phase 3."
    )
    L.append("")
    L.append(f"*F2a′ holdout runtime: {runtime} s. Holdout opened once, F2a′ columns only.*")
    L.append("")

    with open(VERDICT_PATH, "a") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
