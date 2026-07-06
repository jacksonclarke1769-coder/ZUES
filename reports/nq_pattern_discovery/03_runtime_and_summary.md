# NQ Pattern Discovery — Foundation Lane — 03: Runtime, Canary, Firewall Summary

RESEARCH ONLY. LIVE HOLD ACTIVE. No file inside `~/trading-team/bot/nq-liq-bot` was modified —
only this `reports/nq_pattern_discovery/` directory was added. All new code lives at
`~/trading-team/research/nq_pattern_discovery/` (a new path, not any bot repo live path). No
commits were made.

## Firewall (mandatory, before/after)

```
cd ~/trading-team/bot/nq-liq-bot && python3 -m pytest test_funded_config_firewall.py -q
```
- **Before**: `2 passed in 0.07s`
- **After**: `2 passed in 0.12s`

No mismatch, no STOP condition triggered.

## Runtime

`build_store.py` (features_daily -> features_intraday -> profile_a_join ->
canary_causality_check), single run, cold cache:

```
=== [1/4] features_daily ===        rows=2678   cols=53
=== [2/4] features_intraday ===     rows=205122 cols=36   (+2.4s)
=== [3/4] profile_a_join ===        rows=705    cols=107  (+11.3s)
=== [4/4] canary_causality_check ===                       (+35.4s)
[done] total wall clock: 36.1s
```

**36.1 seconds total** — well inside the <20min target. `profile_a_join.py` is the slow step
(~24s standalone) because it reloads the full Databento 1m/5m frames and re-runs the Profile-A
model/feature build (`eng._features()`), matching the cost profile of the pinned
`tools_1m_truth_recert.py`/`tools_account_size_research.py` scripts it reuses. `baseline_
reproduction.py` (run separately, not part of `build_store.py`) takes a comparable ~15-20s for
the same reason.

## Results summary

| deliverable | result |
|---|---|
| Baseline reproduction (01) | 11/11 metrics exact match, 0 mismatch (tolerance 0.5pp) |
| `store/features_daily.parquet` | 2,678 rows x 53 cols, 2016-01-04 -> 2026-05-25 |
| `store/features_intraday.parquet` | 205,122 rows x 36 cols, same date range |
| `store/profile_a_context.parquet` (+`.csv`) | 705 rows x 107 cols; MFE-walker cross-validated 0/705 mismatches vs the pinned stream; re-walked PF 1.237 matches baseline exactly |
| Causality canary | 40/40 spot-checks PASS (20 intraday bars, 20 daily rows) |
| Firewall | PASS before and after (2/2 both times) |

## Known limitations / flagged for downstream lanes

1. **Data-source split**: feature store built on Dukascopy (`engine/data.py`, 2013-2026-05-25);
   Profile-A stream built on Databento (2021-06-22 -> 2026-06-22). Join misses at the tails
   (13/705 day-level, 17/705 bar-level) — see `02_feature_store.md`.
2. **`is_half_day`** is a generalized 2-rule approximation (Thanksgiving Friday, Dec 24), not a
   curated per-year CME table across 2016-2026 (only 2026 is curated in this repo, in
   `scheduler.py`). Flagged, not silently trusted for exact half-day-session-length logic.
3. **`atr14_daily`/percentiles** use RTH-session daily bars (09:30-16:00 H/L/C), a different
   convention from `engine/data.py`'s own ICT 18:00-anchored daily bars used elsewhere in this
   repo — chosen for consistency with the gap/PDH/PDL/ATR feature family, documented in
   `02_feature_store.md`'s day-convention caveat.
4. **Regime labels at 10:00 vs 10:30**: five of the seven flags are identical between the two
   stamps by construction (their inputs are all known by 10:00); only `gap_fill` can genuinely
   differ. This is a documented modeling decision given the brief's literal rule text, not a bug
   — flagged for the pattern-mining lane in case a richer 10:30-specific rule set is wanted later.
5. This lane did not (and was not asked to) draw any conclusions about NEW patterns/edges — it
   is foundation-only (feature store + baseline reproduction). No trading recommendation is made.

## File index

```
~/trading-team/research/nq_pattern_discovery/
  features_daily.py            per-day table builder
  features_intraday.py         per-5m-bar table builder
  profile_a_join.py            705-trade Profile-A context join + MFE-walker + cross-validation
  canary_causality_check.py    40-spot-check causality canary
  baseline_reproduction.py     the 3-number honest baseline reproduction (task step 1)
  build_store.py               single entrypoint: 2-4 in order
  store/
    features_daily.parquet
    features_intraday.parquet
    profile_a_context.parquet
    profile_a_context.csv

~/trading-team/bot/nq-liq-bot/reports/nq_pattern_discovery/
  01_honest_baseline_reproduction.md / .json
  02_feature_store.md / .json
  03_runtime_and_summary.md   (this file)
```
