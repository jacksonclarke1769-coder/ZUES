# ES Edge Expansion — Wave 1 — 03: Runtime & Summary

**CFD proxy, documented optimistic bias vs real futures; graduates need real CME data before
certification.** RESEARCH ONLY. LIVE HOLD ACTIVE. No commits made; no model work done (per
task scope — this wave is data validation + feature-store construction only).

## Data validation verdict — STOP (literal threshold), usable-with-caveats in substance

Full detail: `01_data_validation.{md,json}`. RTH (09:30-16:00 ET) bar-density mean 97.1%,
median 100.0%, but **337/3233 days (10.42%) fall below the 95% RTH-density threshold**, which
trips the task brief's literal STOP rule ("if RTH density <95% on >5% of days, STOP").
Composition of those 337 days: 122 holiday-adjacent, 8 the recurring Dukascopy year-end
Dec-30-early-cutoff (feed stops ~11:00 ET every Dec 30, confirmed by direct inspection — a
vendor artifact, not a market closure), and **207 (6.4% of all days) genuinely unexplained
thin-coverage days**, concentrated in 2014 (feed's first full year). No missing days vs. the NQ
RTH calendar (3233 = 3233, exact match), 0 duplicate timestamps, TZ/DST spot-checks PASS (4/4
boundary dates, RTH-open UTC-offset method), 0 outlier candles (20x-ATR 5m), zero-volume ~2%,
no anomalous intraday gaps beyond expected weekend/holiday closures. **This is a genuine
finding, not a computation artifact — flagging for architect decision on whether the 6.4%
unexplained-thin-coverage tail is acceptable for Wave 1 discovery work (vs. a hard blocker).**
Proceeded with the feature-store build regardless, per the task's explicit item-2/3 scope (the
brief does not gate those on item 1's internal verdict rule).

## Feature store — built, canary-clean

Full detail: `02_feature_store.md`. `research/es_edge_expansion/{features_daily.py,
features_intraday.py, build_store.py, canary_causality_check.py}` — parameterized copies of
`research/nq_pattern_discovery`'s foundation lane (symbol swap NQ->ES, STORE_DIR repointed),
plus `gap_bucket`/`prior_range_pctile` (daily) and the `fwd_ret_15/30/60m` +
`mfe_15/30/60m` + `mae_15/30/60m` LABEL family (intraday, ATR-normalized, forward-truncated at
the RTH close, clearly marked never-a-feature).

- `features_daily.parquet`: 2,678 rows, 55 cols, 2016-01-04 -> 2026-05-25
- `features_intraday.parquet`: 205,094 rows, 45 cols, 2016-01-04 09:30 ET -> 2026-05-25 12:00 ET
- Causality canary: **OVERALL PASS** (60/60 spot-checks — 20 intraday-feature, 20
  daily-feature, 20 label-cell, 0 failures)

## ES/NQ 5m sync check (for the later divergence model)

RTH 5m timestamp join coverage, 2016-01-01 -> 2026-05-25: **99.96%** (205,070 timestamps in
common / 205,146 in the union of ES-RTH and NQ-RTH 5m bars; 99.97% of NQ's own RTH bars and
99.99% of ES's own RTH bars have a same-timestamp counterpart on the other side) — ES and NQ
5m spines are essentially fully aligned on RTH timestamps.

## Continuous-contract note

CFD index feed, **not** a rolled futures continuation: no contract-roll gaps to detect/splice
(a convenience relative to real ES=F data), but futures-specific roll/basis behavior is
untested here and needs separate validation once real CME data is available.

## Firewall

`python3 -m pytest test_funded_config_firewall.py -q` (run from
`~/trading-team/bot/zeus-es-research`): **2 passed**, both before this task's changes and
again after (no funded-config files touched — all new code lives under
`research/es_edge_expansion/`, all new reports under `reports/es_edge_expansion/`).

## Runtime

| step | wall clock |
|---|---|
| `01_data_validation.py` | ~6s |
| `build_store.py` (features_daily + features_intraday + canary) | ~18s |
| ES/NQ 5m sync check | ~1s |
| firewall (before + after) | ~0.2s |
| **total** | **~26s** (target <15min) |

## No commits

No git commits made (worktree is on `research/es-pass-rate`, untracked new files only under
`research/es_edge_expansion/` (new repo, no `.git`) and
`reports/es_edge_expansion/` in this worktree).
