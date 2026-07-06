# ES Edge Expansion — 02: Feature Store

**CFD proxy, documented optimistic bias vs real futures; graduates need real CME data before
certification.**

Source code: `~/trading-team/research/es_edge_expansion/{features_daily.py,
features_intraday.py, build_store.py, canary_causality_check.py}` — parameterized copies of
`research/nq_pattern_discovery`'s foundation lane (symbol `"ES"` instead of `"NQ"`,
`STORE_DIR` repointed to this directory), plus two additions requested by the ES task brief:
`gap_bucket` / `prior_range_pctile` (daily) and the `fwd_ret_*` / `mfe_*` / `mae_*` LABEL
family (intraday). Data: `engine/data.py` `load_spine("ES","5m")`
(Dukascopy 24h ET CFD-index proxy, 2016-01-01 -> 2026-05-25 window used here).

Store location: `research/es_edge_expansion/store/{features_daily,features_intraday}.parquet`.

## Row counts

| table | rows | cols | date/ts range |
|---|---|---|---|
| `features_daily.parquet`   | 2,678   | 55 | 2016-01-04 -> 2026-05-25 |
| `features_intraday.parquet`| 205,094 | 45 | 2016-01-04 09:30 ET -> 2026-05-25 12:00 ET |

## `features_daily.parquet` — column availability timestamps (all ET, all causal)

"date" = the RTH (09:30-16:00 ET) calendar trading day. Every timestamp below is the earliest
moment the column's value is fully known and safe to condition on.

| column(s) | available at |
|---|---|
| `rth_open`, `rth_high`, `rth_low`, `rth_close`, `n_rth_bars` | 16:00 (same day, EOD) |
| `or5_high/low`, `first_5m_ret` | 09:35 |
| `or15_high/low`, `first_15m_ret` | 09:45 |
| `or30_high/low`, `first_30m_ret` | 10:00 |
| `on_hi`, `on_lo`, `on_range` | 04:00 |
| `pm_hi`, `pm_lo`, `pm_range` | 09:30 |
| `dow`, `is_holiday_adjacent`, `is_half_day` | 00:00 (calendar-only) |
| `pdh`, `pdl`, `prior_close`, `prior_open`, `prior_range`, `prior_direction` | 18:00 evening before (prior day fully closed) |
| `gap_pts`, `gap_atr`, `gap_bucket`, `atr14_daily_prior` | 09:30 (uses only completed prior days) |
| `prior_range_pctile` | 09:30 (trailing-60-RTH-day pctile of the already-lagged `prior_range`) |
| `atr14_daily`, `atr14_daily_pctile` | 16:00 (same-day EOD variant, uses today's own TR) |
| `on_range_pctile`, `pm_range_pctile` | 04:00 / 09:30 respectively (trailing 60-RTH-day window) |
| `intraday_atr14_at_open`, `..._pctile` | 09:30 (5m ATR through the 09:25 bar, strictly pre-open) |
| `regime_*_1000` (7 flags) | 10:00 |
| `regime_*_1030` (7 flags) | 10:30 (only `regime_gap_fill_1030` differs from its `_1000` twin — see `build_regime_labels` docstring in `features_daily.py`) |

**New vs. the NQ engine** (ES task brief additions):
- `gap_bucket` — categorical bucket of `|gap_atr|`: `<0.25`, `0.25-0.75`, `0.75-1.25`, `>1.25`.
- `prior_range_pctile` — trailing-60-RTH-day percentile of `prior_range` (pdh-pdl).
- (`rth_open` already existed in the NQ engine and satisfies the brief's "RTH-open price"
  ask; `first_5m/15m/30m_ret` and `on_range_pctile`/`pm_range_pctile` likewise already existed
  and satisfy "first-N-minute returns" / "overnight+premarket range percentiles".)

## `features_intraday.parquet` — column availability timestamps

One row per RTH 5m bar. All FEATURE columns are known at the row's own bar CLOSE (this repo's
`engine/htf.py` convention).

| column(s) | available at |
|---|---|
| `Open/High/Low/Close/Volume`, `minutes_since_open` | this bar's own close |
| `vwap`, `vwap_dist_pts`, `vwap_dist_atr`, `vwap_slope_6bar` | this bar's own close (causal cumulative from 09:30) |
| `trend_slope_20bar`, `atr14_5m`, `compression_score` | this bar's own close (trailing-window, same-session only) |
| `day_high_sofar`, `day_low_sofar` | this bar's own close (causal cummax/cummin) |
| `d1c_drift` | this bar's own close (= close - today's own 09:30 open) |
| `dist_to_{pdh,pdl,onh,onl,pmh,pml,or15h,or15l,prior_close}` (+ `_atr` variants) | this bar's own close (levels themselves already causal per the daily table above) |

### LABEL columns — NOT features, forward-looking by construction

`fwd_ret_15m/30m/60m`, `mfe_15m/30m/60m`, `mae_15m/30m/60m` (9 columns) are ATR-normalized
(divided by `atr14_daily_prior`) targets computed from bars **strictly after** the row's own
bar: `fwd_ret_Nm` = the N-minute-later close vs. this bar's close; `mfe_Nm`/`mae_Nm` = the
max/min running excursion over that same forward window vs. this bar's close. Each window is
truncated at the RTH session close (16:00) — rows within N minutes of the close have `NaN` for
that horizon. **Using any of these nine columns as a model input at time t is a look-ahead bug
by construction.** They exist so per-model lanes can build their own event labels without
re-deriving the forward-return machinery. This is the "raw forward-return machinery" the task
brief asks the store to provide — per-event labels are a later, per-model-lane responsibility.

## Causality canary (40+ spot-checks, `canary_causality_check.py`)

Recomputes a representative feature per column family from scratch using only data within its
documented availability window, and asserts an exact match (`atol=1e-6`) against the stored
value. Three sub-canaries, same "NQ pattern" plus one new sub-canary for the label family:

| canary | n | result |
|---|---|---|
| intraday (day_high_sofar, day_low_sofar, vwap, d1c_drift) | 20 random bars | **PASS** |
| daily (pdh, pdl, gap_pts, atr14_daily_prior) | 20 random days | **PASS** |
| labels (fwd_ret_60m, mfe_60m, mae_60m — forward window truncated to exactly 12 bars) | 20 random (bar, horizon) cells | **PASS** |

**OVERALL CANARY: PASS** (60/60 checks, 0 failures) — see
`research/es_edge_expansion/canary_causality_check.py` for the recompute logic; run via
`python3 build_store.py` or standalone `python3 canary_causality_check.py`.
