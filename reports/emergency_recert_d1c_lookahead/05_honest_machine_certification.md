# 05 — Honest Machine Certification

HONEST-RECERT DRAFT — pending auditor verdict + operator approval

INC-20260706-1141. LIVE HOLD ACTIVE — no live/config/funded changes made.

## Data source
- CSV: `reports/emergency_recert_d1c_lookahead/honest_d1c_stream.csv (705 rows, loaded directly, not regenerated)`
- Summary JSON: `reports/emergency_recert_d1c_lookahead/honest_d1c_stream_summary.json (co-located Wave-1 artifact)`
- Span: 2021-06-22 20:00:00-04:00 .. 2026-06-22 19:59:00-04:00 (260.7 weeks)
- the CSV carries R/mae_r only for kept==True rows (583); the 122 dropped rows have blank R/mae_r (no exit simulated for them), so PF/WR/expR/totR for the full 705 cannot be recomputed from the CSV alone. Row (a) below is therefore taken from the co-located honest_d1c_stream_summary.json's unfiltered_A_all_705 block, cross-checked by independently recomputing (b) honest-kept directly from the CSV and confirming an EXACT match to summary_json's honest block (see verification below).

## D1c attachment proof (no lookahead)
- Check: eval_ts <= ts (fill timestamp) for every row in the 705-row CSV
- Result: 0 of 705 rows have eval_ts > ts (verified directly on the CSV this session)
- Cited canaries: test_d1c_timestamp_canary.py (synthetic, permanent, no data dependency), test_no_future_d1c_attachment.py (real Databento slice, skips if research data mirror unavailable)

## Cost assumptions
existing repo conventions unchanged: 1m-truth fills (tools_1m_truth_recert.M1Map), Exit#3 exit model, size-to-risk via risk_usd/trade, adverse-first (mae/trough) bookkeeping in day_rows/eval_run -- no new cost assumptions introduced this task.

## (a) Profile A unfiltered (705 signals)
n=705  PF=1.237  WR=42.8%  expR=0.106  totR=74.7R  (source: honest_d1c_stream_summary.json.unfiltered_A_all_705 (not recomputed this session, see data_source note))
Per-year: NOT AVAILABLE this session -- CSV lacks R for the 122 dropped (kept=False) rows and honest_d1c_stream_summary.json's per_year block covers honest/kept only, not the full 705

## (b) Profile A + honest D1c (583 kept)
n=583  PF=1.361  WR=44.9%  expR=0.153  totR=89.2R  (recomputed directly from the CSV this session)
Cross-check vs summary_json: EXACT match on n/PF/WR/expR/totR and all 6 per-year rows

| year | n | PF | WR% |
|---|---|---|---|
| 2021 | 70 | 1.512 | 42.9 |
| 2022 | 113 | 1.072 | 40.7 |
| 2023 | 118 | 1.326 | 47.5 |
| 2024 | 110 | 1.087 | 38.2 |
| 2025 | 118 | 1.881 | 51.7 |
| 2026 | 54 | 1.605 | 50.0 |

## (c) Sanity deltas
PF delta (honest - unfiltered) = 0.124 (reference expectation: +0.12) -> MATCH
honest D1c adds a modest real PF improvement over the raw 705-signal set, consistent with the Wave-1 characterization

## (d) Eval row: A + honest D1c + Exit#3 + A10/$1,200
Profile A + honest D1c (583 kept) + Exit#3 sizing, Apex 50K spec (start=$50,000 trail=$2,500 target=$3,000 dll=$1,000 ARES-stop=$550), MAX_A_QTY overridden to 10, budget=$1,200, via tools_account_size_research.build_events/day_rows/eval_run

| | pass% | bust% | expire% | median_days(pass) |
|---|---|---|---|---|
| computed (n=525, pass=165 bust=195 exp=165) | 31.4 | 37.1 | 31.4 | 16 |
| auditor emergency read | 31.4 | 37.3 | 31.2 | 16 |
| delta (pp) | 0.0 | 0.2 | 0.2 | -- |

Tolerance: 0.5pp per leg. Verdict: **MATCH (all legs within 0.5pp tolerance)**

Canary updates authorized (by the coordinator, citing INC-20260706-1141) and applied:
- tools_sim_parity_check.py CANARY_EXPECT -> pass_pct=31.4 bust_pct=37.1 exp_pct=31.4 med_days=16 n=525 (was 47.8/15.9/36.2/16/395)
- test_tools_sim_parity_check.py docstring updated to match
- tools_profileC_a_enhancement.py CANARY_EXPECT -> same new row (tools_wyckoff_a_tags.py and tools_8ideas_stream_studies.py import this constant, no separate definition found)

**Viability of cap-10/$1,200: BUST (37.1% bust vs 31.4% pass, and bust > pass) -- the honest-stream cap-10/$1,200 config busts more often than it passes. Plainly: NOT VIABLE as a standalone characterization at this cell; see 06_honest_sizing_matrix.csv /.md for the full budget x cap surface (auditor judges the frontier, not this task).**

See `06_honest_sizing_matrix.csv`/`.md` for the full budget x cap surface and `07_honest_eval_funnel.csv`/`.md` for the funnel comparison. Frontier selection and final viability verdicts across the matrix are RESERVED TO THE AUDITOR.

## Precision note (adjudicated)

The canonical honest cap-10/$1,200 row is 31.4/37.3/31.2/med16/n=525 (the REGENERATED pipeline value, via `tools_sim_parity_check.load_rows()` -- matches the auditor's original emergency read exactly). CSV-derived tables in this report and in `06_honest_sizing_matrix.csv`/`.md` and `07_honest_eval_funnel.csv`/`.md` may show 37.1/31.4 on the one boundary start -- a 1-ULP float round-trip through the CSV flips a single knife-edge eligible start between BUST and EXPIRE (max |delta R| 2.22e-16 across the 583-trade set; not an engine disagreement). Difference is immaterial: +-0.2pp, 1/525 starts.

