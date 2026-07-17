"""WP-F Amendment v1.2 — F2a' IS measurement (PREREG_PHASE3.md Amendment v1.2, frozen
at git hash bc35ceddcb10; IS report base committed fb798d7). SEPARATE execution.

F2a' = F2a re-scoped to excursion episodes whose FSM terminal resolves STRICTLY AFTER
t0 (same-bar/tautological resolutions excluded from fit AND evaluation). Same features,
estimator, and gates as F2 (§4-§5). BH/G4 is applied within family F2 = {F2a, F2b,
F2a'} using the already-measured F2a/F2b p-values from the committed IS run fb798d7.

IS ONLY — the holdout is NOT opened (the §6 holdout for F2a' as a fresh cell is a later,
separate execution, per Amendment v1.2). Results are APPENDED to
reports/ict_v2/03_phase3_is_results.md as a clearly-marked v1.2 section.
"""
from __future__ import annotations

import os
import time
from typing import Dict

import numpy as np
import pandas as pd

from . import statlib as S
from . import wp_f_cells as W
from .wp_f_selftest import run_selftest

BOT_REPO = os.path.expanduser("~/trading-team/bot/nq-liq-bot")
DATA_DIR = os.path.join(BOT_REPO, "research", "ict_v2", "phase3", "data")
REPORT_PATH = os.path.join(BOT_REPO, "reports", "ict_v2", "03_phase3_is_results.md")
AMEND_HASH = "bc35ceddcb10"
IS_COMMIT = "fb798d7"

# Already-measured family-F2 p-values from the committed IS run (fb798d7, report §4).
F2A_PVALUE = 0.0
F2B_PVALUE = 0.863


def _log(m: str) -> None:
    print(f"[wp-f v1.2 {time.strftime('%H:%M:%S')}] {m}", flush=True)


def _fmt(x, nd=3):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:.{nd}f}"


def main() -> None:
    t0 = time.time()
    _log("running self-test (now incl. the F2a' unit-restriction path) — mandatory gate ...")
    st = run_selftest()
    if not st["all_ok"]:
        raise SystemExit("SELF-TEST FAILED — F2a' IS run aborted (planted post-t0 must pass; same-bar leak must be removed).")

    _log("loading excursion_episodes_is.parquet (IS ONLY; holdout NOT opened) ...")
    df = pd.read_parquet(os.path.join(DATA_DIR, "excursion_episodes_is.parquet"))

    res, meta = W.run_F2a_prime(df)

    # BH within family F2 = {F2a, F2b, F2a'} (Amendment v1.2).
    fam_p = [F2A_PVALUE, F2B_PVALUE, res.p_value]
    fam_names = ["F2a", "F2b", "F2a'"]
    rej = S.benjamini_hochberg(fam_p, 0.10)
    # BH-adjusted q for F2a'
    p = np.asarray(fam_p, dtype=float)
    order = np.argsort(p)
    m = len(p)
    qadj = np.full(m, np.nan)
    running = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        running = min(running, p[i] * m / (rank + 1))
        qadj[i] = running
    res.q_bh = float(qadj[2])
    res.g4 = bool(rej[2])

    runtime = round(time.time() - t0, 2)
    _append_report(res, meta, st, runtime, dict(zip(fam_names, [(fam_p[i], bool(rej[i])) for i in range(m)])))

    verdict = "SURVIVES" if res.survives else "dies"
    _log(f"F2a' RESULT: excluded_same_bar={meta['excluded_same_bar_resolutions']:,}  "
         f"class SC={meta['n_sweep_confirmed']:,} vs AB={meta['n_accepted_breakout']:,}  "
         f"AUC(B)={res.auc_base:.3f} AUC(B+ICT)={res.auc_full:.3f} uplift={res.uplift:.3f} "
         f"CI[{res.ci_lo:.3f},{res.ci_hi:.3f}]  G1={res.g1} G2={res.g2} G3={res.g3} G4={res.g4} -> {verdict}")
    print(f"F2APRIME_VERDICT {verdict} uplift={res.uplift:.4f} CI[{res.ci_lo:.4f},{res.ci_hi:.4f}] "
          f"G1={res.g1} G2={res.g2} G3={res.g3} G4={res.g4} p={res.p_value:.4f} q={res.q_bh:.4f}", flush=True)
    print(f"SELF-TEST: {'PASSED' if st['all_ok'] else 'FAILED'}  RUNTIME: {runtime}s", flush=True)


def _append_report(res, meta, st, runtime, bh_family) -> None:
    r = res
    signs = "".join("+" if (v is not None and np.isfinite(v) and v > 0) else ("−" if (v is not None and np.isfinite(v) and v < 0) else "·") for v in r.per_year.values())
    unit_st_checks = [c for c in st["checks"] if c[0].startswith("f2aprime")]
    L = []
    L.append("\n\n---\n")
    L.append(f"## v1.2 — F2a′ (re-scope of F2a), Amendment v1.2 (git hash `{AMEND_HASH}`)")
    L.append("")
    L.append(
        f"Filed under PREREG Amendment v1.2 (operator-approved 2026-07-17), appended to the IS report base "
        f"committed `{IS_COMMIT}`. F2a′ measures the book's Chapter-20 question honestly — is acceptance-vs-rejection "
        "predictable BEFORE resolution — on the population where prediction is possible at all: excursion episodes "
        "whose FSM terminal `confirmed_at` is STRICTLY AFTER t0 (same-bar/tautological resolutions excluded from fit "
        "AND evaluation). Features, estimator, and gates are identical to F2 (§4-§5). IS ONLY — holdout not opened."
    )
    L.append("")
    L.append("### Self-test extension (unit-restriction path)")
    L.append("")
    L.append("| check | result |")
    L.append("|---|:---:|")
    for name, actual, _ in unit_st_checks:
        L.append(f"| {name} | {actual} |")
    L.append("")
    L.append(
        "The extended self-test confirms the restriction is faithful: a planted POST-t0 signal passes G1, and a "
        "purely same-bar (t0-contemporaneous) tautology — which passes G1 when unrestricted — is REMOVED by the "
        "restriction (uplift → ~0, G1 fails). The same-bar exclusion therefore strips the tautological signal, not a genuine one."
    )
    L.append("")
    L.append("### Unit restriction — episode accounting")
    L.append("")
    L.append("| quantity | count |")
    L.append("|---|---:|")
    L.append(f"| total excursion episodes (IS) | {meta['total_episodes']:,} |")
    L.append(f"| **excluded — same-bar resolutions (terminal confirmed_at == t0)** | {meta['excluded_same_bar_resolutions']:,} |")
    L.append(f"| excluded — timeouts / unresolved / non-pair | {meta['excluded_non_pair_timeout_or_unresolved']:,} |")
    L.append(f"| **kept — post-t0 SWEEP_CONFIRMED vs ACCEPTED_BREAKOUT** | {meta['kept_post_t0_pair']:,} |")
    L.append(f"| class balance — SWEEP_CONFIRMED | {meta['n_sweep_confirmed']:,} |")
    L.append(f"| class balance — ACCEPTED_BREAKOUT | {meta['n_accepted_breakout']:,} |")
    sc, ab = meta["n_sweep_confirmed"], meta["n_accepted_breakout"]
    frac = sc / (sc + ab) if (sc + ab) else float("nan")
    L.append(f"| SWEEP_CONFIRMED fraction | {_fmt(frac,3)} |")
    L.append("")
    L.append("### F2a′ result (AUC uplift of B+ICT over baseline B, blocked-5-fold weekly CV)")
    L.append("")
    L.append("| cell | n | n_pos(SC) | AUC(B) | AUC(B+ICT) | uplift | 95% CI | G1(≥.02) | G2 | per-yr uplift signs | G3 | p | q(BH, family F2) | G4 | verdict |")
    L.append("|---|---:|---:|---:|---:|---:|---|:---:|:---:|---|:---:|---:|---:|:---:|:---:|")
    ci = f"[{_fmt(r.ci_lo)}, {_fmt(r.ci_hi)}]"
    verdict = "SURVIVES" if r.survives else "dies"
    L.append(
        f"| F2a′ | {r.n:,} | {r.n_pos:,} | {_fmt(r.auc_base)} | {_fmt(r.auc_full)} | {_fmt(r.uplift)} | {ci} | "
        f"{r.g1} | {r.g2} | {signs} | {r.g3} | {_fmt(r.p_value,4)} | {_fmt(r.q_bh,4)} | {r.g4} | **{verdict}** |"
    )
    L.append("")
    bh_str = ", ".join(f"{k}: p={_fmt(v[0],4)}, BH-reject={v[1]}" for k, v in bh_family.items())
    L.append(f"**BH within family F2** (q=0.10 over {{F2a, F2b, F2a′}}, using the committed F2a/F2b p-values): {bh_str}.")
    L.append("")
    L.append("### Verdict")
    L.append("")
    if r.survives:
        L.append(
            f"**F2a′ SURVIVES the IS gates** (uplift {_fmt(r.uplift)} ≥ 0.02 floor, CI excludes 0, G2 incremental over "
            "B by construction, G3 era-stable, G4 BH-clean). Acceptance-vs-rejection carries genuine ex-ante "
            "conditional structure once the tautological same-bar episodes are removed — eligible for the §6 holdout "
            "as a fresh cell (a later, separate execution). Awaiting Fable adjudication before any holdout contact."
        )
    else:
        reasons = []
        if not r.g1:
            reasons.append(f"G1 FAILS (uplift {_fmt(r.uplift)} vs 0.02 floor / CI {ci})")
        if not r.g3:
            reasons.append("G3 fails (era instability)")
        if not r.g4:
            reasons.append("G4 fails (BH within family F2)")
        L.append(
            f"**F2a′ dies at IS** — {'; '.join(reasons) if reasons else 'did not clear all gates'}. Once the "
            "~same-bar tautological majority is excluded, the ex-ante features (excursion depth, t0 close-location, "
            "body_vs_tod, volume_z, salience) do NOT predict acceptance-vs-rejection materially better than baseline "
            "B. This is the honest answer to the Chapter-20 question for this event stream: rejection is NOT "
            "meaningfully predictable BEFORE it resolves — consistent with the cited priors (the F2a AUC 0.956 was "
            "the tautology, not a decision-layer asset). No holdout contact; nothing further certified."
        )
    L.append("")
    L.append(f"*F2a′ runtime (incl. self-test): {runtime} s. IS files only; holdout not opened.*")
    L.append("")

    with open(REPORT_PATH, "a") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
