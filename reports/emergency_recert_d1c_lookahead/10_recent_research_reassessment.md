# D1c Attachment Timestamp Look-Ahead — July Research Reassessment

INC-20260706-1141. Classification only — no code or existing report is edited by this task.
Mechanism: `01_defect_trace.md`. Invalidation ledger: `04_invalidated_numbers.md`.

Rule applied throughout: a lane is INVALIDATED-MUST-RERUN if its **absolute** numbers depend on the
D1c kept-stream (`tools_phase3_config_sweep.a_streams_d1c` / `tools_sim_parity_check.load_rows()` /
`tools_profileC_a_enhancement.build_raw_and_kept`, see `01_defect_trace.md` §7); it SURVIVES if its
conclusion is standalone (never touches the Profile A D1c stream) or is a method/tooling result
independent of any specific stream's contents.

## Eval-sizing sprint (cap x budget matrix, state policies, cadence) — INVALIDATED-MUST-RERUN

- Files: `tools_eval_sizing_sweep.py` (imports `a_streams_d1c` directly, line 36, and
  `tools_account_size_research.day_rows`/`eval_run`, line 37), `tools_sprint_state_policies.py`
  (imports `tools_sim_parity_check.load_rows`/`group_by_day`/`SPEC_50K`/`EXPIRE_DAYS`),
  `tools_sprint_cadence.py` (`import tools_sim_parity_check as P`, line 60),
  `tools_sprint_cap_risk.py` (`import tools_sim_parity_check as PARITY`, line 42),
  `tools_sprint_fill_sensitivity.py` (`PARITY.load_rows()`, line 454).
- Every absolute funnel number in `reports/eval_sizing_sweep_2026-07-05.json` (cap x budget matrix
  cells, e.g. `evals_per_funded=2.08`), every state-policy pass/bust/expire%, and every cadence/
  recycle-rule funnel row was computed on the contaminated 435-trade kept-set.
- **The METHOD and harnesses SURVIVE**: the count-basis / denominator-artifact check
  (`count_basis_check` pattern), the canary-first-and-abort discipline each of these files enforces
  (each aborts if it can't reproduce `CANARY_EXPECT` / the certified 47.8/15.9/36.2/16d row before
  writing anything — the same discipline that halted the 8-ideas sprint), the `simulate()`
  generalization in `tools_sprint_cadence.py`, and the R0-R4 recycle-rule design are all reusable
  as-is against the honest stream once `run_d1c_real.attach_drift` is fixed. Rerun, don't rebuild.

## cap-15 x $1,000 candidate — INVALIDATED

- `08 Decisions/DEC-20260705-2101-cap15-remains-sim-conditional-kill-line-15pct.md` (vault). Its
  SIM CONDITIONAL status and 15% kill-line were computed against the contaminated stream via the
  same `a_streams_d1c` chain. Now moot pending re-certification — re-evaluate the kill-line logic
  itself (which is sound) against the honest stream's numbers.

## Fill-model audit (touch/penetration >= 2.08pt) — SURVIVES

- File: `tools_eval_sizing_sweep.py` (`penetration_depth`, line 226; `mean_penetration_pts`, line
  298; `evals_per_funded=2.08` appears in `reports/eval_sizing_sweep_2026-07-05.json` — note this is
  a distinct "2.08" figure from the sizing matrix, not the penetration-depth statistic itself, but
  both live in the same file/report).
- Fill mechanics (limit-order penetration depth, MFE at the FVG-mid entry, stop-distance buckets)
  are a property of the 1m-truth walk (`walk_1m`) and the entry/stop geometry — **independent of
  which trades the D1c flag kept or dropped**. The audit's conclusions about fill realism survive.
- CAVEAT (per the incident brief): its INPUT STREAM was still the D1c kept-set (`a_streams_d1c`,
  same file, line 36) — so the exact per-trade population it measured penetration over is the
  contaminated 435, not the honest 583. Penetration statistics should be re-checked on the honest
  stream once regenerated; given the mechanism is fill-model-not-stream-composition, the expectation
  is the numbers will be **similar but not re-verified** — mark this a should-recheck, not a
  should-discard.

## Pass-path anatomy — INVALIDATED-MUST-RERUN

- Breakdown of pass/bust/expire sequencing across the cap x budget grid
  (`reports/eval_sizing_sweep_2026-07-05.json` `matrix`/`buckets`/`overlays`); same root dependency
  as the eval-sizing sprint above (same file, same `a_streams_d1c` import). Kept-stream sequencing
  (which trades land on which simulated eval-day, in what order) is exactly what the timestamp bug
  corrupts — this lane cannot be salvaged without a rerun.

## Funded funnel — INVALIDATED

- `reports/funded_funnel_2026-07-05.json`, `apex_funded_40.py` (`a_streams_d1c` import, lines
  28-31), `tools_funded_funnel.py` (same import, lines 26-29). The ~$12.6-12.8k/PA and ~0% bust
  figures (A4=$12,649/0.0%, A5=$12,827/0.0% per the canary block in the funnel JSON) are funded-tier
  replays of the same contaminated stream.

## Asia/London + Profile C (PD/FVG) + Wyckoff standalone lanes — SURVIVE AS DEAD

- Asia/London (5 session strategies): vault `Research Register.md:47` — "10.4y baselines all <= PF
  0.98 ... NIGHTWATCH re-confirmed all 6 families OOS PF 0.69-0.92". This is a standalone rejection
  (the strategies fail on their own merits, no Profile A / D1c stream involved at all) — verdict
  stands untouched.
- Profile C (PD/FVG): vault `Research Register.md:89` — "Standalone 0/32 families (1,024-cell
  preregistered matrix, 1m truth, canaries PASS; PF or <0.5tr/wk gates)" is a standalone-strategy
  rejection independent of the D1c stream; that DEAD verdict stands. HOWEVER its **A-enhancement**
  sub-analysis in the same writeup ("HTF-FVG zones miss OTE entries 0-1.6% coverage; SMT
  testable+null; phi<=0.11 vs D1c") and its overlap-with-A statistics were computed against the
  certified 435 (via `tools_profileC_a_enhancement.py`, which calls `RD.attach_drift` directly,
  line 93) — those sub-tables are STALE. The null/DEAD verdict on the enhancement question survives
  **a fortiori**: it failed to beat an INFLATED (PF 2.31-grade) baseline, so it certainly fails
  against the honest (PF 1.36-grade) one too. Re-running would only confirm, not overturn.
- Wyckoff (W1-W12): vault `Research Register.md:91` — "Standalone 398/400 families (4,000-cell
  matrix, 1m-truth, canaries PASS)" DEAD, plus 2 marginal W6 survivors "rejected-in-practice" for
  reasons unrelated to D1c (fill-degradation fragility, regime fade). Standalone verdict stands.
  Its "A-features all null (chop structurally absent from A 0/435 ...)" line explicitly cites the
  435-trade count — that sub-table (and the associated denominator-artifact discovery example) used
  the contaminated stream; mark it stale, but the NULL verdict survives a fortiori by the same
  inflated-baseline logic as Profile C above.
- **Wyckoff/PD-FVG A-tag studies**: the directional null verdicts ("A-features null", "no filter
  raises totR", the repeated replication count) survive directionally; any absolute funnel row
  quoted from those studies (counts, pass%, R-totals tied to the 435) is stale and must be
  re-derived if ever needed again — but no one should expect the null conclusion to flip.

## 8-ideas sprint (Ideas 1-8, halted mid-flight) — mostly INVALIDATED-MUST-RERUN if wanted

- Idea 4 (`tools_8ideas_stream_studies.py:449-491`, `do_idea4`, D1c drift-strength bands/
  `reports/eval_improvement_8_ideas/04_d1c_strength_bands.{csv,md}`): built directly on the `kept`
  population from `build_raw_and_kept` (contaminated `d1c_keep` membership) — INVALIDATED. This is
  also the idea whose independent `ts`-correct recompute (`drift_value_at`, using the true
  `fi[fb]`-derived timestamp) is what exposed the sign-flip that triggered this incident (see
  `01_defect_trace.md` §6) — so Idea 4's own machinery is simultaneously the bug-finder and a
  contaminated-input consumer.
- Ideas 3, 5, 5b, 6 (`tools_8ideas_stream_studies.py` `do_idea3`/`do_idea5`/`do_idea6`,
  `reports/eval_improvement_8_ideas/03_*`, `05_*`, `06_*`): all iterate over the same `kept` list
  from `build_raw_and_kept` — INVALIDATED-MUST-RERUN.
- Idea 7 (NY opening-drive failed-breakout reversal,
  `reports/eval_improvement_8_ideas/07_ny_opening_drive_reversal.{csv,md}`, engine
  `~/trading-team/backtests/ict-nq-framework/ny_fbr_engine.py`): this is a STANDALONE strategy grid
  (40 families, all REJECTED on their own PF/tr-wk/canary gates) that only references "435 trades /
  405 unique trade-days" for overlap/correlation context (line 37 of that report) — the standalone
  REJECTED verdicts (0 survivors) do not depend on D1c composition and stand; only the overlap-vs-A
  context line is stale.
- "Near-miss" lane: halted before producing a committed report file (per the incident, "8-ideas
  sprint halted (invalid baseline)"); nothing to invalidate beyond what's already listed — its
  in-flight finding IS the incident itself.
- Net for the sprint: rerun Ideas 3/4/5/5b/6 against the honest stream if still wanted; Idea 7's
  REJECTED verdict needs no rerun (standalone, already dead on its own gates).

## Denominator-artifact rule — SURVIVES (methodological)

- Adopted 2026-07-06 (`DEC-20260706-1108-wyckoff-playbook-rejected-both-roles-denominator-artifact-ru.md`):
  the rule that avoid/skip filters can raise pass% while lowering pass COUNT via start-shrinkage, and
  that removals must be judged on funded/slot-year count, not just percentage. This is a statement
  about how to interpret ANY funnel (whichever stream feeds it) and requires no change or rerun —
  it will be applied to the re-generated honest-stream numbers exactly as it was meant to be applied
  generally.

## Firewall check

```
$ python3 -m pytest test_eval_config_firewall.py test_funded_config_firewall.py -q
5 passed in 0.09s
```
Green before and after this task (no code/config touched).
