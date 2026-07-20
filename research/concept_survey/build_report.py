"""Assemble the final report from all JSON artifacts."""
import json
import os

import numpy as np

from harness import all_cells, cell_key

OUT = "/Users/jacksonclarke/trading-team/reports/concept_survey/01_ict_concept_survey.md"


def j(path):
    with open(path) as f:
        return json.load(f)


def fmt(x, nd=3):
    if x is None:
        return "-"
    if isinstance(x, float) and (np.isnan(x) if x == x else True) and x != x:
        return "-"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def main():
    train = j("train_stats.json")
    holdout = j("holdout_stats.json")
    quarterly = j("quarterly_stats.json")
    gab = j("gate_ab_result.json")
    gate_c = j("gate_c_result.json")
    survivors = j("gate_abc_survivors.json")
    gate_d = j("gate_d_result.json") if os.path.exists("gate_d_result.json") else {}
    corr = j("correlation_result.json") if os.path.exists("correlation_result.json") else {}

    v1_holdout = j("holdout_stats_v1_ARTIFACT.json") if os.path.exists("holdout_stats_v1_ARTIFACT.json") else {}
    v1_survivors = (j("gate_abc_survivors_v1_ARTIFACT.json")
                    if os.path.exists("gate_abc_survivors_v1_ARTIFACT.json") else [])
    v1_gate_d = (j("gate_d_result_v1_ARTIFACT.json") if os.path.exists("gate_d_result_v1_ARTIFACT.json") else {})

    lines = []
    P = lines.append

    P("# ICT Concept Survey — 36-Cell Preregistered Arena, Gated Results (v2, CORRECTED)")
    P("")
    P("## CORRECTION NOTICE (v2, 2026-07-20)")
    P("")
    P("**v1 of this report and its 19-cell survivor shortlist are RETRACTED. Cause: a "
      "same-bar fill/invalidation sequencing bug in `survey_engine.py::run_cell()` "
      "(limit-order path) silently CANCELLED trades whose entry touch and stop/invalidation "
      "touch first occurred on the same 1m bar, instead of recording them as filled-then-"
      "immediately-stopped losses. This is a selection-bias bug: it deleted precisely the "
      "fastest-reversing, worst-case fills from the trade population -- for FVG_1m_long "
      "holdout alone, 8,791 same-bar candidates were wrongly cancelled vs 8,894 kept as clean "
      "fills; that deleted population WAS the edge (PF 1.90 -> 0.68, totR +5,116 -> -5,104 once "
      "corrected).**")
    P("")
    P("**Fix**: same-bar entry+invalidation now resolves as a filled trade, immediately "
      "stopped out on that same bar (conservative, consistent with PREREG §3's "
      "\"stop-fills-first on ambiguous 1m bars\"). Invalidation strictly BEFORE the entry is "
      "ever touched remains a legitimate cancel (the order never had a chance to fill "
      "cleanly). A regression test (`test_fill_sequencing.py`) now asserts this directly. "
      "The exit-management scan for clean fills is unchanged (already started at fill_i+1, "
      "already never credited target hits on the fill bar).")
    P("")
    P("**Scope of the bug**: it only affects LIMIT-mode entries -- FVG, IFVG, Order Block, "
      "Breaker Block (24/36 cells). **Sweep/MSS are market-mode (fill immediately at signal "
      "confirmation, no pre-fill touch-window logic) and are UNCHANGED by this fix** -- their "
      "v1 and v2 holdout stats are bit-identical, confirmed below.")
    P("")
    P("**Corrected verdict: Gate A+B+C survivors = 0/36 (was 19/36 in the retracted v1). "
      "The survey found nothing deployable.**")
    P("")
    if v1_survivors:
        P("### Before/after per-cell deltas for the 19 previously-claimed (now retracted) survivors")
        P("")
        P("| cell | v1 HOLDOUT n/PF/exp/totR (retracted) | v2 HOLDOUT n/PF/exp/totR (corrected) | "
          "v2 Gate A | still a survivor? |")
        P("|---|---|---|---|---|")
        for k in v1_survivors:
            v1s = v1_holdout.get(k, {})
            v2s = holdout.get(k, {})
            ga = "PASS" if gab["gate_a"].get(k) else "fail"
            still = "YES" if k in survivors else "NO"
            P(f"| {k} | {v1s.get('n')}/{fmt(v1s.get('pf'))}/{fmt(v1s.get('expectancy'))}/"
              f"{fmt(v1s.get('totR'))} | {v2s.get('n')}/{fmt(v2s.get('pf'))}/"
              f"{fmt(v2s.get('expectancy'))}/{fmt(v2s.get('totR'))} | {ga} | {still} |")
        P("")
        P("Market-mode cells (Sweep/MSS) for reference -- bit-identical v1 vs v2 (unaffected by the bug):")
        P("")
        P("| cell | v1 HOLDOUT totR | v2 HOLDOUT totR | identical? |")
        P("|---|---|---|---|")
        for concept, tf, d, dname in all_cells():
            if concept not in ("Sweep", "MSS"):
                continue
            k = cell_key(concept, tf, dname)
            v1t = v1_holdout.get(k, {}).get("totR")
            v2t = holdout.get(k, {}).get("totR")
            ident = "yes" if v1t == v2t else "NO -- UNEXPECTED"
            P(f"| {k} | {v1t} | {v2t} | {ident} |")
        P("")
    P("---")
    P("")
    P(f"Preregistration: `backtests/zeus-ict-2026-07/concept_survey/PREREG.md` (frozen 2026-07-20, "
      f"before any result was computed). Data: single-vendor Databento NQ 1m "
      f"(`data/real_futures/NQ_databento_1m_5y.parquet`), window 2024-06-22 -> 2026-06-22, "
      f"TRAIN=first 12mo, HOLDOUT=last 12mo. N=36 (6 concepts x 3 TFs x 2 directions), fixed a priori.")
    P("")
    P("## 1. Headline")
    n_a = sum(1 for v in gab["gate_a"].values() if v)
    n_b = sum(1 for v in gab["gate_b"].values() if v)
    n_ab = len(gab["gate_ab"])
    n_c = len(survivors)
    P(f"- Gate A (holdout PF>1.0 & expectancy>0): **{n_a}/36**")
    P(f"- Gate B (BH-FDR q=0.10 across all 36, one-sided block-bootstrap p): **{n_b}/36** "
      f"(BH cutoff p = {gab['bh_cutoff_p']})")
    P(f"- Gate A+B (both required to reach Gate C): **{n_ab}/36**")
    P(f"- Gate C (beats randomized-entry null 95th pctile of total R -- 1000 runs for any A+B "
      f"survivor, 200-run global null otherwise): **{n_c}/36**")
    if n_c == 0:
        P("")
        P("**No cell survived all three statistical gates. The survey found nothing "
          "deployable — this is an acceptable, honestly-reported result, not a failure "
          "of the harness.**")
    P("")

    # ---- Gate B global-null context ----
    P("## 2. Null expectation vs observed (Gate B/C context)")
    observed_pf_gt_12 = 0
    expected_pf_gt_12_under_null = 0.0
    for concept, tf, d, dname in all_cells():
        k = cell_key(concept, tf, dname)
        s = holdout.get(k, {})
        if s.get("pf") is not None and isinstance(s["pf"], (int, float)) and s["pf"] > 1.2:
            observed_pf_gt_12 += 1
        gc = gate_c.get(k, {})
        frac = gc.get("null_frac_pf_gt_1_2")
        if frac is not None:
            expected_pf_gt_12_under_null += frac
    P(f"- Observed cells with HOLDOUT PF>1.2: **{observed_pf_gt_12}/36**.")
    P(f"- Expected cells clearing PF>1.2 under the randomized-entry null (sum, across all 36 "
      f"cells, of that cell's own null-run fraction with PF>1.2 -- i.e. the false-positive yield "
      f"the SAME execution template would produce from bar-selection luck alone): "
      f"**{expected_pf_gt_12_under_null:.1f}/36**.")
    gap = observed_pf_gt_12 - expected_pf_gt_12_under_null
    P(f"- Gap (observed minus null-expected): **{gap:.1f}**. " +
      ("This gap is large relative to the null-expected count -- the survey found a real signal, "
       "not noise; Gate C (per-cell, not aggregate) is still the decisive test for individual cells."
       if gap > 5 else
       "This gap is small -- treat the per-cell Gate C outcomes as the only reliable signal; "
       "in aggregate the observed PF>1.2 rate is close to what bar-selection luck alone would produce."))
    P("- Per-cell 200-run (1000-run for A+B survivors) null total-R and null-PF distributions, "
      "and the observed-vs-null-p95 outcome, are in `gate_c_result.json` for every cell, not just "
      "survivors (per PREREG §Gate B/C).")
    P("")

    # ---- BH p-value ladder ----
    P("## 3. BH-FDR p-value ladder (q=0.10, N=36)")
    P("")
    P("| rank | cell | p | BH threshold | passes |")
    P("|---|---|---|---|---|")
    for row in gab["ladder"]:
        P(f"| {row['rank']} | {row['cell']} | {row['p']:.5f} | {row['bh_threshold']:.5f} | "
          f"{'YES' if row['passes_rank_threshold'] else ''} |")
    P("")

    # ---- Per-cell table ----
    P("## 4. Per-cell table: TRAIN | HOLDOUT | LIVE-ACHIEVABLE (Gate A+B+C+D survivors get the live column)")
    P("")
    P("| cell | TRAIN n/PF/exp | HOLDOUT n/PF/exp | Gate A | Gate B (p) | Gate C (beats null) | "
      "LIVE n/PF/exp (survivors) |")
    P("|---|---|---|---|---|---|---|")
    pmap = {row["cell"]: row["p"] for row in gab["ladder"]}
    for concept, tf, d, dname in all_cells():
        k = cell_key(concept, tf, dname)
        t = train.get(k, {}); h = holdout.get(k, {})
        ga = "PASS" if gab["gate_a"].get(k) else "fail"
        gb = f"{pmap.get(k, float('nan')):.4f}" + (" PASS" if gab["gate_b"].get(k) else "")
        gc = gate_c.get(k, {})
        gc_str = ("beats" if gc.get("beats_null_95") else "no") if k in gab["gate_ab"] else "-"
        live = gate_d.get(k)
        live_str = (f"{live['n_live_achievable']}/{fmt(live['live_pf'])}/{fmt(live['live_expectancy'])}"
                    if live else "-")
        P(f"| {k} | {t.get('n')}/{fmt(t.get('pf'))}/{fmt(t.get('expectancy'))} | "
          f"{h.get('n')}/{fmt(h.get('pf'))}/{fmt(h.get('expectancy'))} | {ga} | {gb} | {gc_str} | {live_str} |")
    P("")

    # ---- Quarterly sign stability ----
    P("## 5. Quarterly walk-forward sign stability (8 quarters across the 2y window)")
    P("")
    quarterly_rows = survivors or list(gab["gate_ab"]) or [k for k, v in gab["gate_a"].items() if v]
    if not quarterly_rows:
        P("(no cells passed even Gate A -- showing nothing; see `quarterly_stats.json` for the "
          "full per-cell, per-quarter breakdown of all 36 cells if needed.)")
    else:
        note = ("(no Gate A+B+C or Gate A+B survivors -- showing the 8 Gate-A-only cells for "
                "context; none of these cleared Gate B/C)" if not survivors and not gab["gate_ab"]
                else "")
        if note:
            P(note)
            P("")
        P("| cell | positive quarters / 8 | sign sequence |")
        P("|---|---|---|")
        for k in quarterly_rows:
            q = quarterly["cells"].get(k, {})
            P(f"| {k} | {q.get('n_positive_quarters')}/8 | {''.join(q.get('sign_by_quarter', []))} |")
    P("")

    # ---- Survivor shortlist ----
    P("## 6. Ranked survivor shortlist")
    if not survivors:
        P("")
        P("**Empty. No cell passed Gate A + Gate B (BH-FDR q=0.10) + Gate C (randomized-entry null).**")
    else:
        decorr = corr.get("mean_abs_corr_vs_others", {})
        ranked = sorted(survivors, key=lambda k: (
            0,  # all have passed all 3 gates already
            decorr.get(k, 1.0) if decorr.get(k) is not None else 1.0,
            -(gate_d.get(k, {}).get("live_expectancy") or -999)))
        P("")
        P("Ranked by (a) gates passed [all A+B+C here], (b) decorrelation vs other survivors/Profile A/VPC "
          "(lower mean |corr| = better), (c) live-achievable expectancy:")
        P("")
        for i, k in enumerate(ranked, 1):
            gd = gate_d.get(k, {})
            P(f"{i}. **{k}** — decorr={decorr.get(k)}, live-achievable n={gd.get('n_live_achievable')}, "
              f"PF={fmt(gd.get('live_pf'))}, expectancy={fmt(gd.get('live_expectancy'))}R, "
              f"suppression%={gd.get('r_weighted_suppression_pct')}, "
              f"edge_lives_in_suppressed={gd.get('edge_lives_in_suppressed_trades')}")
    P("")

    # ---- Correlation matrix ----
    P("## 7. Correlation matrix (daily-R Pearson, holdout)")
    if corr:
        keys = list(corr["pearson_daily_R"].keys())
        P("")
        P("| | " + " | ".join(keys) + " |")
        P("|" + "---|" * (len(keys) + 1))
        for a in keys:
            row = " | ".join(fmt(corr["pearson_daily_R"][a][b], 3) for b in keys)
            P(f"| {a} | {row} |")
        P("")
        P(f"Profile A (achievable, in-window) n={corr.get('profile_a_n_achievable_in_window')}; "
          f"VPC/Profile B (in-window) n={corr.get('vpc_n_in_window')}.")
    else:
        P("(no survivors -> no correlation matrix computed)")
    P("")

    # ---- Graveyard ----
    P("## 8. Graveyard (cause of death)")
    P("")
    P("| cell | cause of death |")
    P("|---|---|")
    for concept, tf, d, dname in all_cells():
        k = cell_key(concept, tf, dname)
        if k in survivors:
            continue
        if not gab["gate_a"].get(k):
            cause = "holdout collapse (Gate A: PF<=1.0 or expectancy<=0)"
        elif not gab["gate_b"].get(k):
            cause = f"FDR miss (Gate B: p={pmap.get(k):.4f} > BH cutoff {gab['bh_cutoff_p']})"
        elif k in gab["gate_ab"] and not gate_c.get(k, {}).get("beats_null_95"):
            cause = (f"null-indistinguishable (Gate C: real totR {gate_c.get(k,{}).get('real_totR')} "
                      f"<= null p95 {gate_c.get(k,{}).get('null_p95')})")
        else:
            cause = "n/a"
        P(f"| {k} | {cause} |")
    P("")

    P("## 9. Documented literal-reading resolutions")
    P("""
- **Gate B correction scope**: one-sided block-bootstrap p-values computed for ALL 36 cells
  (not just Gate-A survivors); BH-FDR (q=0.10) applied across the full N=36 ladder, per PREREG
  §4/§5/§7's repeated "across all N=36 cells." A cell needs Gate A AND Gate B to reach Gate C.
- **Gate B block length**: block length (in trades) = round(5 x that cell's own holdout
  trades-per-day), trades-per-day = cell's holdout n / 313 (unique ET calendar days with data
  in the holdout window) — "block length ~ weekly" read as 5 TRADING days of THAT cell's own
  trade cadence (PREREG's explicit wording), not 5 calendar days of raw time.
- **Gate C entry count**: "same number of entries" read as the real cell's REALIZED holdout
  trade count n (an "entry" = an executed position), not the raw pre-filter signal count.
- **Order Block "last opposing candle immediately before a displacement candle"**: read
  literally as candle i-1 exactly (no backward scan). If i-1 is not opposite-colored, no OB
  forms at that displacement bar (this is disclosed as a strict reading, not a scan-back rule).
- **IFVG inversion search horizon**: PREREG states no explicit window for "far edge closed
  through inverts"; bounded to 100 signal-TF bars, borrowing the Breaker Block's explicit
  fail-window (PREREG §6.4) for consistency and to keep detection O(n).
- **Sweep/MSS "most recent confirmed swing level"**: read as the level known as of the PRIOR
  bar (must pre-exist the bar that acts on it); the break/reclaim bar's own close is compared
  same-bar (matches the cited code's own elementwise convention).
- **MSS/BOS firing**: fires once per break (transition from not-broken to broken), not on every
  bar price remains beyond the level.
- **EOD flat / exchange day**: CME session boundary taken as 17:00 ET; a bar's trading day rolls
  forward at/after 17:00 ET; EOD-flat cutoff = 16:55 ET of the SIGNAL's (conf_ts) exchange day,
  applied to both the limit-order lifetime clock and the exit-management scan.
- **Window/split boundaries**: treated as UTC calendar timestamps (PREREG does not specify a tz
  for 2024-06-22 / 2025-06-22 / 2026-06-22).
- **Gate D**: "signal surfaces at first poll >= confirmation instant" (5m poll cadence);
  "limit entries placed AT that poll" -> the order's fill-search window is re-walked starting at
  poll_ts (not conf_ts), with the SAME absolute lifetime/EOD end anchored to conf_ts. The literal
  10-minute certified_gate staleness test is ALSO computed and reported, but is structurally
  ~0% for this survey: unlike Profile A's multi-stage internal state machine, every concept here
  has a single-instant confirmation with no extra internal lag, so the only latency source is the
  <=5-minute poll cadence itself — always under the 10-minute threshold. The substantive
  deployability effect is the poll-delay re-walk (a trade can be missed/repriced by minutes).
- **Same-bar fill/invalidation resolution (v2 correction, audited 2026-07-20)**: for LIMIT-mode
  entries, when the entry-touch and invalidation/stop-touch bars are the SAME 1m bar, the order
  is treated as FILLED at entry_price and immediately STOPPED at stop_price on that bar (a real
  loss), not cancelled -- this is the "stop-fills-first on ambiguous bars" convention (PREREG §3)
  extended to the pre-fill phase. Invalidation on a bar STRICTLY BEFORE the entry is ever touched
  remains a legitimate cancel. See the CORRECTION NOTICE at the top of this report.
""")

    P("## 10. Anti-pattern compliance")
    P("- No train/full-window number presented as a finding above (train shown only for context "
      "alongside holdout/live-achievable).")
    P("- No per-concept tuning, no sweeps, no composites — one fixed execution template for all 36 cells.")
    P("- Single-vendor Databento data only; no other data file read by the harness.")
    P("- Survey only: no arming, no change to any existing frozen edge, no LIVE HOLD change.")
    P("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(lines))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
