# NQ Pattern Discovery — Foundation Lane — 01: Honest Baseline Reproduction

RESEARCH ONLY. New research path: `~/trading-team/research/nq_pattern_discovery/` (NOT the live
bot repo's live paths). LIVE HOLD ACTIVE throughout — no code in this repo was touched. Firewall
(`python3 -m pytest test_funded_config_firewall.py -q`, run from `~/trading-team/bot/nq-liq-bot`)
checked PASS (2/2) immediately before and after this work — see `03_runtime_and_summary.md`.

Repo HEAD at the time this reproduction was run: `4bf64ebac2f6e3ac5b86222a9bb4ad6420b31ec8`
(`2026-07-06 13:57:11 +0800`, "research: new-edge/salvage program — Profile A solo eval-dead,
VPC rescued, balanced combo candidate").

Incident citation: the honest 1m-truth streams reused here post-date and supersede
`INC-20260706-1141` (D1c timestamp lookahead — old certified D1c kept-set invalidated by a
UTC-relocalized-as-NY string bug in `attach_drift`; fixed via `fill_bar`-indexed `fill_index`
positional lookup, no live trades affected, live gate unaffected). The numbers reproduced below
are the POST-FIX, currently-certified numbers.

## Method

`baseline_reproduction.py` calls ONLY the three pinned, read-only reuse paths named in the task
brief — no re-derivation, no parameter changes:

1. **Unfiltered A (705, PF 1.237)** — `tools_1m_truth_recert.a_streams()["exit3"]` (1m-truth
   re-walked fills, ny_am session, NO D1c filter). PF/n computed on `R_new` only (all 705 trades
   have a 1m fill; none dropped as "never traded at 1m").
2. **Kept A (583, PF 1.361 / WR 44.9 / 2.24 tr-wk)** — `tools_sim_parity_check.load_rows()`,
   which internally calls `tools_phase3_config_sweep.a_streams_d1c(...)["exit3"][0]` — the same
   705-trade population, filtered to the 583 whose D1c drift-sign agrees with trade direction.
3. **(cap=10, budget=$1200) EOD-eval row (31.4/37.3/31.2/16d, n=525)** —
   `tools_account_size_research.build_events/day_rows/eval_run` with `MAX_A_QTY` monkeypatched
   from its file default (40) to 10 (the deployed cap, DEC-20260705-1102), `SPECS["50K"]`,
   `budget=1200`. This exact override is how `tools_sim_parity_check.CANARY_EXPECT` was itself
   derived (its module docstring cites this row as the deployed cap-10 config), so reproducing
   it via `tools_account_size_research` directly (rather than importing the canary constant) is
   an independent check of the same number.

## Result — EXACT MATCH, no mismatch >0.5pp on any metric

| metric | got | expected (task brief) | status |
|---|---|---|---|
| unfiltered PF | 1.237 | 1.237 | PASS |
| unfiltered n | 705 | 705 | PASS |
| kept PF | 1.361 | 1.361 | PASS |
| kept WR | 44.9 | 44.9 | PASS |
| kept n | 583 | 583 | PASS |
| kept tr/wk | 2.24 | 2.24 | PASS |
| row pass% | 31.4 | 31.4 | PASS |
| row bust% | 37.3 | 37.3 | PASS |
| row exp% | 31.2 | 31.2 | PASS |
| row med_days | 16 | 16 | PASS |
| row n | 525 | 525 | PASS |

Every number reproduced BYTE-for-byte (rounded to the brief's stated precision); no mismatch of
any size, let alone >0.5pp. Cleared to proceed to feature-store construction on top of this
stream.

## Data-source note (carried forward into the feature store)

The honest A streams above are built on the **Databento** feed (`apex_eval_eod_databento.py` +
`run_d1c_real.load_1m()`), spanning **2021-06-22 -> 2026-06-22**. The feature store (steps 2-3,
see `02_feature_store.md`) is required by the task brief to cover 2016-2026 and is built on the
**Dukascopy-sourced** `engine/data.py` spine, which covers 2013-12-31 -> 2026-05-25 — a
DIFFERENT vendor with a longer history. This is a deliberate, task-brief-mandated choice (the
brief pins `engine/data.py` specifically for the day/bar tables), not a bug — but it means the
Profile-A join (`profile_a_join.py`) merges two different vendors' bars by ET timestamp, not the
same underlying prints. See `02_feature_store.md` for the join-tolerance and miss-rate detail.

## Raw JSON

See `01_honest_baseline_reproduction.json` (same numbers, machine-readable, plus the full
`baseline_reproduction.py` script output).
