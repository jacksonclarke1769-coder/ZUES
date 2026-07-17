"""Phase 4 — STAGE 4A bridge cells IS run (PREREG_PHASE4.md v1.0, frozen git hash
ff1d59980743). Governing chain: PREREG_PHASE3 (cd652ea→bc35ceddcb10), Phase-3 verdict
dd3b685.

The Phase-3 certified content (F2a′: depth predicts sweep-vs-acceptance) is resolved
BEFORE a sweep-family strategy enters. Stage 4A tests the NEW bridge claim: does depth /
level-class predict the POST-confirmation PATH of a SWEEP_CONFIRMED event? Unit =
`sweep_confirmed_is.parquet` (nothing re-extracted). Two cells only:

  * P4-B1 depth: feature = excursion_depth_ticks × tick ÷ atr20 (ATR-normalized), IS
    terciles (frozen on IS); contrast BOTTOM vs TOP tercile.
  * P4-B2 level class: weekly-class vs intraday-class.

Primary outcome: fwd24 SIGNED IN THE REVERSAL DIRECTION. Reversal-sign mapping (already
encoded in WP-E's `direction` column, verified 1:1 in-data): a BUY-side sweep grabs
buy-side liquidity ABOVE a high-type level then closes back inside → reversal = DOWN
(fwd24_reversal = −Δclose/ATR); a SELL-side sweep grabs sell-side liquidity BELOW a
low-type level then closes back inside → reversal = UP (fwd24_reversal = +Δclose/ATR).
So the extracted `fwd_24` (=fwd_raw_24×sign(direction)), `maxcont_24`, `maxrev_24` ARE
already the reversal-direction outcomes. Secondary outcomes: maxcont24(reversal),
maxrev24. Estimators/gates identical to Phase-3 §4-§5. BH q=0.10 within this 2-cell
family (over the two cells' PRIMARY-outcome p-values; secondaries reported as context).
IS ONLY — `sweep_confirmed_holdout` stays sealed.
"""
from __future__ import annotations

import os
import time
from typing import Dict, List

import numpy as np
import pandas as pd

from . import statlib as S
from . import wp_f_cells as W
from .wp_f_selftest import _run_one, _synth_frame

BOT_REPO = os.path.expanduser("~/trading-team/bot/nq-liq-bot")
DATA_DIR = os.path.join(BOT_REPO, "research", "ict_v2", "phase3", "data")
REPORT_PATH = os.path.join(BOT_REPO, "reports", "ict_v2", "05_phase4a_bridge_is.md")
PREREG_HASH = "ff1d59980743"
TICK = 0.25


def _log(m: str) -> None:
    print(f"[phase4a {time.strftime('%H:%M:%S')}] {m}", flush=True)


def _fmt(x, nd=3):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    return f"{x:.{nd}f}"


def quick_selftest() -> Dict:
    """Reuse the Phase-3 planted/placebo machinery on this unit shape: a planted mag
    contrast must PASS G1-G3, a null must FAIL G1."""
    _log("self-test (planted passes / null fails) on the contrast machinery ...")
    rng = np.random.default_rng(4041)
    n = 40000
    dfp = _synth_frame(n, rng)
    g = rng.integers(0, 2, n)
    out = 0.30 * g + rng.normal(0, 1, n)
    rp = _run_one(dfp, g == 1, g == 0, out, "mag")
    rp.g4 = S.benjamini_hochberg([rp.p_value], 0.10)[0]
    planted_pass = rp.g1 and rp.g2 and rp.g3 and rp.g4
    dfn = _synth_frame(n, rng)
    gn = rng.integers(0, 2, n)
    rn = _run_one(dfn, gn == 1, gn == 0, rng.normal(0, 1, n), "mag")
    null_fail = not rn.g1
    ok = planted_pass and null_fail
    _log(f"  planted survives={planted_pass} (Δ={rp.delta:.3f}); null G1={rn.g1} -> null_fails={null_fail}; self-test {'PASSED' if ok else 'FAILED'}")
    return {"planted_pass": planted_pass, "null_fail": null_fail, "ok": ok,
            "planted_delta": rp.delta, "null_delta": rn.delta}


def run_cell(cell: str, df: pd.DataFrame, week, is_year, W_, C, maskA, maskB, gA, gB) -> List[W.OutcomeResult]:
    """Primary + two secondary outcomes for a bridge cell; all magnitudes (floor 0.10)."""
    out = []
    specs = [
        ("fwd24_reversal", df["fwd_24"].to_numpy(dtype=float)),
        ("maxcont24_reversal", df["maxcont_24"].to_numpy(dtype=float)),
        ("maxrev24", df["maxrev_24"].to_numpy(dtype=float)),
    ]
    for name, outcome in specs:
        resid = S.ols_residualize(df, outcome, W.CAT_B, W.NUM_B)
        r = W.run_contrast_outcome(cell, "P4-4A", "sweep_confirmed", name, "mag",
                                   df, week, is_year, W_, C, maskA, maskB, gA, gB, outcome, resid)
        out.append(r)
    return out


def main() -> None:
    t0 = time.time()
    st = quick_selftest()
    if not st["ok"]:
        raise SystemExit("SELF-TEST FAILED — 4A IS run aborted (planted must pass, null must fail).")

    _log("loading sweep_confirmed_is.parquet (IS ONLY; holdout sealed) ...")
    df = pd.read_parquet(os.path.join(DATA_DIR, "sweep_confirmed_is.parquet"))
    week, W_ = S.week_ids(df["t0"])
    is_year = S.is_year_bucket(df["t0"])
    C = S.make_draw_matrix(W_, 2000, seed=40412)

    # P4-B1: ATR-normalized depth terciles (frozen on IS), BOTTOM vs TOP.
    depth_atr = df["excursion_depth_ticks"].to_numpy(dtype=float) * TICK / df["atr20"].to_numpy(dtype=float)
    tm = W._tercile_masks(depth_atr, np.ones(len(df), bool))
    top_mask, bot_mask = tm  # helper returns (top, bottom)
    _log(f"P4-B1 depth terciles: bottom n={int(bot_mask.sum()):,} vs top n={int(top_mask.sum()):,}")
    b1 = run_cell("P4-B1", df, week, is_year, W_, C, bot_mask, top_mask, "depth_bottom_tercile", "depth_top_tercile")

    # P4-B2: weekly vs intraday.
    tf = df["level_timeframe_class"].to_numpy()
    _log(f"P4-B2 class: weekly n={int((tf=='weekly').sum()):,} vs intraday n={int((tf=='intraday').sum()):,}")
    b2 = run_cell("P4-B2", df, week, is_year, W_, C, tf == "weekly", tf == "intraday", "weekly", "intraday")

    # BH within the 2-cell family over the two PRIMARY-outcome p-values.
    primary = [b1[0], b2[0]]
    pvals = [r.p_value for r in primary]
    rej = S.benjamini_hochberg(pvals, 0.10)
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    m = len(p)
    qadj = np.full(m, np.nan)
    running = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        running = min(running, p[i] * m / (rank + 1))
        qadj[i] = running
    for k, r in enumerate(primary):
        r.q_bh = float(qadj[k])
        r.g4 = bool(rej[k])

    runtime = round(time.time() - t0, 2)
    write_report(b1, b2, st, runtime)

    for cell, rs in (("P4-B1", b1), ("P4-B2", b2)):
        pr = rs[0]
        verdict = "SURVIVES" if pr.survives else "dies"
        print(f"CELL {cell} (primary fwd24_reversal): {verdict}  "
              f"Δ={pr.delta:.3f} CI[{pr.ci_lo:.3f},{pr.ci_hi:.3f}] "
              f"G1={pr.g1} G2={pr.g2}(ret={_fmt(pr.g2_retention,2)}) G3={pr.g3} G4={pr.g4} q={_fmt(pr.q_bh,4)}", flush=True)
    survivors = [c for c, rs in (("P4-B1", b1), ("P4-B2", b2)) if rs[0].survives]
    print(f"4A SURVIVORS: {survivors if survivors else 'none'}", flush=True)
    print(f"SELF-TEST: {'PASSED' if st['ok'] else 'FAILED'}  RUNTIME: {runtime}s", flush=True)


def write_report(b1, b2, st, runtime) -> None:
    def rows_for(rs):
        lines = []
        for r in rs:
            floor_ok = "✓" if abs(r.delta) >= r.floor else "✗"
            signs = "".join("+" if (v is not None and np.isfinite(v) and v > 0) else ("−" if (v is not None and np.isfinite(v) and v < 0) else "·") for v in r.per_year.values())
            ci = f"[{_fmt(r.ci_lo)}, {_fmt(r.ci_hi)}]"
            tag = " (PRIMARY)" if r.outcome == "fwd24_reversal" else ""
            g4 = r.g4 if r.outcome == "fwd24_reversal" else "—"
            q = _fmt(r.q_bh, 4) if r.outcome == "fwd24_reversal" else "—"
            verdict = ("SURVIVES" if r.survives else "dies") if r.outcome == "fwd24_reversal" else "(secondary)"
            lines.append(
                f"| {r.cell} | {r.outcome}{tag} | {r.groupA} vs {r.groupB} | {_fmt(r.delta)} | {ci} | {floor_ok} | "
                f"{r.g1} | {_fmt(r.g2_retention,2)} | {r.g2} | {signs} | {r.g3} | {_fmt(r.p_value,4)} | {q} | {g4} | {verdict} |"
            )
        return lines

    L = []
    L.append("# ICT V2 Phase 4 — Stage 4A Bridge Cells (IS)")
    L.append("")
    L.append(
        f"**Governs:** `research/ict_v2/PREREG_PHASE4.md` v1.0, git hash `{PREREG_HASH}` (chain: PREREG_PHASE3 "
        "cd652ea→bc35ceddcb10, Phase-3 verdict dd3b685). **Scope:** Stage 4A IS bridge test on the existing "
        "`sweep_confirmed_is.parquet` (nothing re-extracted). Two cells only. `sweep_confirmed_holdout` NOT opened. "
        "No PF/WR reported (§Bans). No new features/sessions/thresholds."
    )
    L.append("")
    L.append("## 0. The bridge question & reversal-sign mapping")
    L.append("")
    L.append(
        "Phase-3 F2a′ certified that t0 depth predicts WHETHER an excursion resolves sweep-vs-acceptance — resolved "
        "before a sweep strategy enters. Stage 4A tests the NEW claim: does depth / level-class predict the "
        "POST-confirmation PATH of a confirmed sweep? **Reversal-sign mapping** (verified 1:1 in-data): "
        "side=`buy` (buy-side liquidity above a high-type level, closed back inside) → reversal = **down** → "
        "`fwd24_reversal = −Δclose/ATR20`; side=`sell` (sell-side liquidity below a low-type level) → reversal = "
        "**up** → `fwd24_reversal = +Δclose/ATR20`. This is exactly WP-E's `direction` column (buy→down, sell→up); "
        "the extracted `fwd_24`/`maxcont_24`/`maxrev_24` are already reversal-signed, so no re-derivation was needed. "
        "Primary outcome = `fwd24_reversal`; `maxcont24_reversal` / `maxrev24` reported as secondary context."
    )
    L.append("")
    L.append("## 1. Self-test (planted passes / null fails)")
    L.append("")
    L.append(f"- Planted mag contrast survives all gates: **{st['planted_pass']}** (Δ={_fmt(st['planted_delta'])}).")
    L.append(f"- Null placebo fails G1: **{st['null_fail']}** (Δ={_fmt(st['null_delta'])}).")
    L.append(f"- Self-test verdict: **{'PASSED' if st['ok'] else 'FAILED'}** (IS run permitted only on PASS).")
    L.append("")
    L.append("## 2. Results (contrast Δ = mean(A) − mean(B); weekly block bootstrap 2,000; floor 0.10 ATR)")
    L.append("")
    L.append("| cell | outcome | groups (A vs B) | Δ | 95% CI | floor✓ | G1 | G2 ret | G2 | per-yr signs | G3 | p | q(BH) | G4 | verdict |")
    L.append("|---|---|---|---:|---|:---:|:---:|---:|:---:|---|:---:|---:|---:|:---:|:---:|")
    L += rows_for(b1)
    L += rows_for(b2)
    L.append("")
    L.append(
        "BH q=0.10 is applied within the 2-cell family over the two cells' PRIMARY-outcome (`fwd24_reversal`) "
        "p-values; the secondary outcomes are descriptive and do not enter the FDR set or decide survival."
    )
    L.append("")
    L.append("## 3. Verdict (per cell, on the primary outcome)")
    L.append("")
    survivors = []
    for cell, rs in (("P4-B1", b1), ("P4-B2", b2)):
        pr = rs[0]
        v = "SURVIVES" if pr.survives else "dies"
        if pr.survives:
            survivors.append(cell)
        why = []
        if not pr.g1:
            why.append(f"G1 fails (|Δ|={_fmt(abs(pr.delta))} vs 0.10 floor / CI {_fmt(pr.ci_lo)},{_fmt(pr.ci_hi)})")
        if pr.g1 and not pr.g2:
            why.append(f"G2 fails (B-residual retention {_fmt(pr.g2_retention,2)} < 0.5 → market-state, not ICT)")
        if pr.g1 and pr.g2 and not pr.g3:
            why.append("G3 fails (era instability)")
        if pr.g1 and pr.g2 and pr.g3 and not pr.g4:
            why.append("G4 fails (BH within family)")
        L.append(f"- **{cell}** ({'depth bottom-vs-top tercile' if cell=='P4-B1' else 'weekly-vs-intraday class'}): "
                 f"**{v}**{(' — ' + '; '.join(why)) if why else ''}.")
    L.append("")
    L.append(f"**Stage 4A-IS survivors: {survivors if survivors else 'NONE'}.**")
    L.append("")
    if survivors:
        L.append(
            "Per §Verdict rules, 4A survivor(s) get ONE §6-style holdout pass (same sign AND ≥50% IS magnitude), run "
            "as a separate execution AFTER this report is committed and Fable adjudicates; only holdout survivors "
            "proceed to Stage 4B one-shot trade gates. This report makes NO holdout contact."
        )
    else:
        L.append(
            "Per §Verdict rules, **zero 4A survivors → the Phase-4 translation FAILS**: F1a/F2a′ remain event-level "
            "knowledge (depth predicts sweep-vs-acceptance AT resolution) but do NOT predict the post-confirmation "
            "reversal path, so no acceptance-gate is licensed; the thesis routes to order-flow (Court D1). No holdout "
            "contact; no Stage 4B."
        )
    L.append("")
    L.append(f"*Runtime: {runtime} s. sweep_confirmed_is only; holdout sealed.*")
    L.append("")

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
