# NQ Pattern Discovery — Foundation Lane — 02: Feature Store

RESEARCH ONLY. Path: `~/trading-team/research/nq_pattern_discovery/` (new, not the live bot
paths). Build scripts: `features_daily.py`, `features_intraday.py`, `profile_a_join.py`,
`canary_causality_check.py`, driven by `build_store.py`. Store: `store/*.parquet` (+ one CSV
copy of the Profile-A join for the anatomy lane).

## Reuse (read-only, pinned per task brief)

- `engine/data.py` (`~/trading-team/backtests/ict-nq-framework/engine/data.py`) —
  `load_spine("NQ","5m")`. This is the Dukascopy-sourced 24h-ET spine, **2013-12-31 ->
  2026-05-25**. Coverage window used: **2016-01-01 -> 2026-05-25** (per brief; the spine does
  not currently extend past 2026-05-25, see caveat below).
- `market_calendar.py` (bot repo) — `is_market_holiday()` for the holiday-adjacent flag.
- `tools_1m_truth_recert.py` / `tools_phase3_config_sweep.py` / `tools_sim_parity_check.py` /
  `run_d1c_real.py` / `apex_eval_eod_databento.py` / `strategy_engine_profileA.py` /
  `model01_sweep_mss_fvg.py` — the honest A stream + D1c attach, for the Profile-A join only.

`engine/htf.py` and `engine/primitives.py` were read for convention (causal `merge_asof`/shift
patterns, `last_known_swings`) but not imported directly — the day/bar tables needed here are
simpler aggregates (gaps, ranges, VWAP, ATR) that don't need the swing/FVG/displacement
primitives; those are left for the pattern-mining lane to pull in if/when it needs them.

## IMPORTANT day-convention caveat

"date" in `features_daily.py` / `features_intraday.py` = the **RTH (09:30-16:00 ET) calendar
day**, NOT `engine/data.py`'s own ICT `trading_day` (18:00-anchored) used elsewhere in this repo
(e.g. `engine/htf.py`, `salvage_b_misc_common.py`). The two agree for RTH bars themselves (09:30
+ 6h is still the same calendar date), so grouping the preceding overnight (18:00-04:00) and
premarket (04:00-09:30) sessions onto `trading_day` correctly attaches them to the RTH day that
follows — but if a downstream lane joins this store against something that uses the ICT
`trading_day` convention for OTHER purposes, re-check the definitions line up for that use case.

## (a) Per-day table — `store/features_daily.parquet`

**2,678 rows, 53 columns, 2016-01-04 -> 2026-05-25** (one row per RTH trading day with data in
the spine).

| column | availability (ET) | notes |
|---|---|---|
| `date`, `dow` | midnight | RTH calendar date; day-of-week 0=Mon |
| `is_holiday_adjacent` | any time | day itself, day before, or day after a market holiday (`market_calendar.is_market_holiday`, self-maintaining, any year) |
| `is_half_day` | any time | generalized rule (day-after-Thanksgiving, Dec 24) — approximation; only `scheduler.HALF_DAYS_2026` is curated per-year in this repo, and only for 2026, so this is the all-year rule it encodes. Flagged: doesn't capture ad-hoc CME schedule changes |
| `rth_open/high/low/close`, `n_rth_bars` | 16:00 (own day) | today's own RTH OHLC — NOT causal pre-close; kept for downstream convenience, not for same-day signal features |
| `pdh`, `pdl`, `prior_close`, `prior_open`, `prior_range`, `prior_direction` | 18:00 evening before / 09:30 | prior RTH day's H/L/close/open, `shift(1)` |
| `on_hi`, `on_lo`, `on_range` | 04:00 | overnight session (18:00 prev evening -> 04:00) |
| `pm_hi`, `pm_lo`, `pm_range` | 09:30 | premarket (04:00 -> 09:30) |
| `gap_pts` | 09:30 | `rth_open - prior_close` |
| `atr14_daily` | 16:00 (own day) | TR-based rolling-14 on RTH daily bars, includes today's own TR |
| `atr14_daily_prior` | 09:30 (pre-open) | `atr14_daily.shift(1)` — the causal variant used for `gap_atr` and the vol-regime flags |
| `gap_atr` | 09:30 | `gap_pts / atr14_daily_prior` |
| `or5/15/30_high/low` | 09:35 / 09:45 / 10:00 | opening range at 5/15/30 min |
| `first_5m/15m/30m_ret` | same window closes | close of window - RTH open, points |
| `on_range_pctile`, `pm_range_pctile`, `atr14_daily_pctile` | 04:00 / 09:30 / 16:00 resp. | trailing-60-RTH-day percentile rank, current day included (its own value is complete by the availability time), `min_periods=20` (NaN before that — first ~1 month of 2016) |
| `intraday_atr14_at_open`, `..._pctile` | 09:30 (strictly pre-open) | 5m-bar TR rolling-14 computed on the full continuous spine (not RTH-restricted), `shift(1)` so it only uses bars through 09:25; percentile as above |
| `regime_*_1000`, `regime_*_1030` | 10:00 / 10:30 | see regime-label rules below |

### Regime labels (literal rules, both stamps use ONLY data <= the stamp)

- `gap_and_go`: `|gap_pts| > 0.3 * atr14_daily_prior` AND `sign(first_30m_ret) == sign(gap_pts)`.
- `gap_fill`: `|gap_pts| > 0.3 * atr14_daily_prior` AND `retrace_frac(stamp) > 0.60`, where
  `retrace_frac` = fraction of the opening gap retraced by the running RTH extreme through the
  stamp's own bar count (6 bars -> 10:00, 12 bars -> 10:30).
- `trend_up_dev` / `trend_dn_dev`: `first_30m_ret > +0.5*dATR` / `< -0.5*dATR`.
- `range_dev` (seed): `OR30 range < 30th trailing-60d percentile`.
- `high_vol` / `low_vol`: `atr14_daily_pctile > 70` / `< 30`.

**Modeling decision, documented, not a bug**: `gap`, `first_30m_ret`, OR30-percentile and the
vol percentile are ALL fully known by 10:00, so `regime_gap_and_go`, `regime_trend_up/dn_dev`,
`regime_range_dev`, `regime_high/low_vol` are byte-identical between the `_1000` and `_1030`
columns by construction. Only `regime_gap_fill`'s `retrace_frac` is a genuinely running
quantity and can differ between the two stamps (more retracement may be visible by 10:30 than
at 10:00). All seven flags are independent booleans (not mutually exclusive — e.g. a day can be
both `trend_up_dev` and `high_vol`).

## (b) Per-5m-bar table — `store/features_intraday.parquet`

**205,122 rows, 36 columns, 09:30-16:00 ET bars, 2016-01-04 -> 2026-05-25.**

| column | notes |
|---|---|
| `ts`, `date`, `minutes_since_open` | bar's own close-availability convention (this repo's standard: a bar's OHLC is "known" at its close) |
| `vwap`, `vwap_dist_pts`, `vwap_dist_atr` | causal cumulative typical-price x volume from 09:30 (zero-volume bars fall back to `Close`) |
| `vwap_slope_6bar` | `vwap.diff(6)/6` |
| `trend_slope_20bar` | rolling-20-bar OLS slope of `Close` (closed-form covariance/variance identity, no lookahead — slope at bar t uses bars [t-19, t]) |
| `atr14_5m` | within-session TR rolling-14 (first bar of each day has no prior close -> NaN TR contribution, `min_periods=1`) |
| `compression_score` | mean range of the last 6 bars / mean range of the prior 24 bars (bars 7-30 back) |
| `day_high_sofar`, `day_low_sofar` | causal cummax/cummin within the RTH session |
| `d1c_drift` | `Close - today's own 09:30 Open` — the "honest" D1c definition (`run_d1c_real.py`'s live convention), available at the bar's own close (only needs today's own already-known open) |
| `dist_to_{pdh,pdl,onh,onl,pmh,pml,or15h,or15l,prior_close}` (+ `_atr` variants) | `Close - level`, joined from the day table; `_atr` = divided by `atr14_daily_prior` |

## (c) Regime labels — see (a) above (folded into the per-day table as `regime_*_1000/1030` columns).

## (d) Profile-A context join — `store/profile_a_context.parquet` (+ `.csv`)

**705 rows (the full unfiltered honest A stream), 107 columns.** For each trade: `ts` (signal =
1m-truth fill-bar timestamp), `direction`, `entry`, `stop`, `target`, `risk_pts`, `risk_usd`,
`stop_bucket` (bins reused verbatim from `profile_a_overlay_research.py` FAMILY 1: 0-30 / 30-45
/ 45-60 / 60-75 / 75-90 / 90+ pts), `d1c_keep` + `d1c_drift_sign` (from `run_d1c_real.attach_drift`,
unfiltered — 583 True / 122 False, matching the certified kept/dropped split exactly),
`confluence_score`, `grade`, `R`/`mae_r`/`mfe_r`/`filled`/`outcome` (win/loss/be),
`trade_seq_in_day`/`is_first_of_day`/`is_second_of_day`, then every day-level and bar-level
feature-store column joined on the trade's RTH date (day table) and via `merge_asof` backward
with a 5-minute tolerance (bar table).

**MAE/MFE note**: the pinned `tools_1m_truth_recert.walk_1m` only tracks MAE (`mae_new`); there
is no MFE in the certified stream. `profile_a_join._walk_1m_with_mfe` is NEW code (not a
modification of any pinned module) that mirrors the exact same causal convention (1m-truth,
stop-first every bar including a 0.5pt `A_SLIP` stop-exit penalty, no same-bar target/partial on
the fill bar) and additionally tracks running MFE. Its own R/MAE outputs are cross-validated
trade-by-trade against the pinned stream's `R_new`/`mae_new` — **0 mismatches / 705 trades**
(tolerance 5e-4, matching the 4dp rounding used for storage) — and the aggregate PF/netR of the
re-walked stream reproduces the baseline exactly (PF 1.237, netR +74.66). See build log in
`03_runtime_and_summary.md`.

**Vendor-mismatch caveat**: the day/bar feature store is built on the Dukascopy-sourced
`engine/data.py` spine; the 705-trade A stream's timestamps come from the Databento feed. Both
are 5m-bar-aligned RTH sessions in ET so timestamps line up, but the OHLC prints themselves are
a different vendor. Join misses (where no day/bar row exists within tolerance): **13/705** on
the day join, **17/705** on the bar join — all at the tails: (1) the Databento stream runs
through 2026-06-22 but the Dukascopy spine currently ends 2026-05-25 (documented in
`01_honest_baseline_reproduction.md`), and (2) a handful of thin-holiday sessions (e.g.
2023-07-04) that one vendor recorded as a tradeable RTH session and the other didn't. These are
genuine cross-vendor calendar gaps, not join-logic bugs — left as NaN rather than silently
filled.

## Causality canary — PASS (40/40 spot-checks)

`canary_causality_check.py`: 20 random intraday bars (`day_high_sofar`/`day_low_sofar`/`vwap`/
`d1c_drift`, independently recomputed from the raw spine using only bars `<= ts`) + 20 random
days (`pdh`/`pdl`/`gap_pts`/`atr14_daily_prior`, independently recomputed from only the prior 14
RTH days). **All 40/40 PASS** — see `03_runtime_and_summary.md` for the full log.

## Column list (machine-readable)

See `02_feature_store.json` for the full column list of all three tables plus row counts, dtypes,
and per-column NaN rates.
