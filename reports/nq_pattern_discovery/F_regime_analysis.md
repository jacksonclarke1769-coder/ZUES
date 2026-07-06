# F — Regime Splits (Profile A, honest streams)

RESEARCH ONLY. Discovery lane F+G. Input: `store/profile_a_context.parquet` (705 unfiltered
honest A trades, 107 context columns). Firewall (`python3 -m pytest test_funded_config_firewall.py
-q`, from `~/trading-team/bot/nq-liq-bot`) checked **2/2 PASS** immediately before and after this
work. Runtime: 8.3s.

## Stream canaries (firewall before proceeding)

| stream | n | PF | WR% | netR | reference | match |
|---|---|---|---|---|---|---|
| unfiltered_705 | 705 | 1.237 | 42.8 | +74.7 | n=705 PF=1.237 WR=42.8 netR=+74.7 | True |
| kept_583 | 583 | 1.361 | 44.9 | +89.2 | n=583 PF=1.361 WR=44.9 netR=+89.2 | True |
| run_cell (10,$1200) kept | pass=31.4 bust=37.3 exp=31.2 med=16.0d n=525 | | | | ref: pass=31.4 bust=37.3 exp=31.2 med=16d n=525 | True |

## Method

Regime flags (causal, 10:00/10:30 stamps, from `store/features_daily.parquet`, folded into the
join): `gap_and_go`, `gap_fill`, `trend_up_dev`, `trend_dn_dev`, `range_dev`, `high_vol`,
`low_vol`. Per the feature-store doc, all flags except `gap_fill` are byte-identical between the
`_1000`/`_1030` stamps by construction (gap/first_30m_ret/percentiles are fully known by 10:00);
only `gap_fill_1030` is reported as a distinct row (running retracement fraction can differ).
Continuous splits: `vwap_slope_6bar` (signal-time), `atr14_daily_pctile` (daily vol regime),
`gap_atr` (opening gap in ATR units) — each cut into quintiles on the unfiltered-705 distribution,
same bin edges applied to the kept-583 subset for comparability.

Criterion (per task brief): **concentration/vanish flag** = `|expR_in_regime - expR_pooled| >= 0.10`
AND `n_in_regime >= 60` AND directional consistency (in-regime expR vs full-stream expR that
year, same sign as the pooled effect) holds in **>=4 of the up-to-6 A-years (2021-2026)**.

## Hits (effect >= +-0.10 expR vs pooled, n>=60, >=4/6yr consistent)

| stream | split | value | n | WR | PF | expR | pooled_expR | effect_vs_pooled | totR_share_pct | consistent_years | eligible_years | flag_concentration |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| kept_583 | atr_pctile_quintile | Q2 | 115 | 53.0 | 1.751 | 0.296 | 0.153 | 0.143 | 38.2 | 4 | 6 | True |
| kept_583 | vwap_slope_quintile | Q1 | 94 | 58.5 | 2.407 | 0.396 | 0.153 | 0.243 | 41.7 | 5 | 6 | True |
| unfiltered_705 | gap_and_go_1000 | TRUE | 82 | 31.7 | 0.742 | -0.148 | 0.106 | -0.254 | -16.2 | 5 | 6 | True |
| unfiltered_705 | gap_fill_1000 | TRUE | 101 | 40.6 | 0.943 | -0.03 | 0.106 | -0.136 | -4.0 | 4 | 6 | True |
| unfiltered_705 | gap_fill_1030 | TRUE | 145 | 42.1 | 1.009 | 0.004 | 0.106 | -0.102 | 0.9 | 4 | 6 | True |
| unfiltered_705 | vwap_slope_quintile | Q1 | 97 | 58.8 | 2.52 | 0.415 | 0.106 | 0.309 | 53.8 | 5 | 6 | True |
| unfiltered_705 | vwap_slope_quintile | Q3 | 96 | 30.2 | 0.737 | -0.15 | 0.106 | -0.256 | -19.3 | 6 | 6 | True |


**Reading the hits**: `gap_and_go_1000` and `gap_fill` (both stamps) are where the honest A edge
**vanishes/inverts** on both streams (unfiltered PF 0.74/0.94, expR -0.15/-0.03 vs pooled +0.11 —
a full sign flip on gap-and-go). `vwap_slope Q1` (steepest downward 6-bar VWAP slope at signal) is
where edge **concentrates**: PF 2.52 (unfiltered) / 2.41 (kept), expR +0.42/+0.40, roughly 4x
pooled, 5/6-year consistent, and (unfiltered only) `vwap_slope Q3` (near-flat/mildly negative
slope straddling zero) is where it **vanishes** (PF 0.74, expR -0.15, 6/6yr — the single most
consistent split in the whole table). `atr_pctile Q2` (kept-583 only, mid-low daily-vol days)
shows a secondary concentration (PF 1.75, expR +0.30).

**Note (below the n>=60 bar but worth flagging)**: `trend_dn_dev_1000` shows a striking PF
3.23(unfiltered)/6.81(kept) and expR +0.51/+0.71, but n=15-17 — too thin to certify per the
brief's own bar; reported for completeness only, not as a hit.

## Full split table (46 rows; also `F_regime_analysis.csv`)

| stream | split | value | n | WR | PF | expR | pooled_expR | effect_vs_pooled | totR_share_pct | consistent_years | eligible_years | flag_concentration |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| kept_583 | atr_pctile_quintile | Q1 | 116 | 44.8 | 1.223 | 0.101 | 0.153 | -0.052 | 13.1 | 3 | 6 | False |
| kept_583 | atr_pctile_quintile | Q2 | 115 | 53.0 | 1.751 | 0.296 | 0.153 | 0.143 | 38.2 | 4 | 6 | True |
| kept_583 | atr_pctile_quintile | Q3 | 111 | 39.6 | 1.161 | 0.068 | 0.153 | -0.085 | 8.5 | 5 | 6 | False |
| kept_583 | atr_pctile_quintile | Q4 | 119 | 47.9 | 1.413 | 0.178 | 0.153 | 0.025 | 23.8 | 4 | 6 | False |
| kept_583 | atr_pctile_quintile | Q5 | 110 | 39.1 | 1.333 | 0.137 | 0.153 | -0.016 | 16.9 | 2 | 6 | False |
| kept_583 | gap_and_go_1000 | TRUE | 56 | 30.4 | 0.647 | -0.218 | 0.153 | -0.371 | -13.7 | 5 | 6 | False |
| kept_583 | gap_fill_1000 | TRUE | 93 | 44.1 | 1.115 | 0.055 | 0.153 | -0.098 | 5.7 | 4 | 6 | False |
| kept_583 | gap_fill_1030 | TRUE | 131 | 45.0 | 1.172 | 0.08 | 0.153 | -0.073 | 11.8 | 4 | 6 | False |
| kept_583 | high_vol_1000 | TRUE | 215 | 42.8 | 1.371 | 0.156 | 0.153 | 0.003 | 37.7 | 4 | 6 | False |
| kept_583 | low_vol_1000 | TRUE | 171 | 50.3 | 1.557 | 0.23 | 0.153 | 0.077 | 44.0 | 5 | 6 | False |
| kept_583 | opening_gap_atr_quintile | Q1 | 124 | 42.7 | 1.159 | 0.076 | 0.153 | -0.077 | 10.6 | 5 | 6 | False |
| kept_583 | opening_gap_atr_quintile | Q2 | 110 | 44.5 | 1.303 | 0.142 | 0.153 | -0.011 | 17.5 | 3 | 6 | False |
| kept_583 | opening_gap_atr_quintile | Q3 | 105 | 43.8 | 1.622 | 0.214 | 0.153 | 0.061 | 25.2 | 3 | 6 | False |
| kept_583 | opening_gap_atr_quintile | Q4 | 116 | 46.6 | 1.481 | 0.196 | 0.153 | 0.043 | 25.5 | 4 | 6 | False |
| kept_583 | opening_gap_atr_quintile | Q5 | 116 | 47.4 | 1.412 | 0.167 | 0.153 | 0.014 | 21.7 | 3 | 6 | False |
| kept_583 | range_dev_1000 | TRUE | 167 | 43.7 | 1.402 | 0.167 | 0.153 | 0.014 | 31.2 | 3 | 6 | False |
| kept_583 | trend_dn_dev_1000 | TRUE | 15 | 66.7 | 6.807 | 0.708 | 0.153 | 0.555 | 11.9 | 5 | 5 | False |
| kept_583 | trend_up_dev_1000 | TRUE | 11 | 27.3 | 0.444 | -0.387 | 0.153 | -0.54 | -4.8 | 5 | 6 | False |
| kept_583 | vwap_slope_quintile | Q1 | 94 | 58.5 | 2.407 | 0.396 | 0.153 | 0.243 | 41.7 | 5 | 6 | True |
| kept_583 | vwap_slope_quintile | Q2 | 71 | 45.1 | 1.574 | 0.225 | 0.153 | 0.072 | 17.9 | 4 | 6 | False |
| kept_583 | vwap_slope_quintile | Q3 | 55 | 36.4 | 0.936 | -0.034 | 0.153 | -0.187 | -2.1 | 6 | 6 | False |
| kept_583 | vwap_slope_quintile | Q4 | 71 | 39.4 | 0.975 | -0.013 | 0.153 | -0.166 | -1.0 | 3 | 6 | False |
| kept_583 | vwap_slope_quintile | Q5 | 87 | 49.4 | 1.529 | 0.213 | 0.153 | 0.06 | 20.8 | 4 | 6 | False |
| unfiltered_705 | atr_pctile_quintile | Q1 | 140 | 42.1 | 1.119 | 0.055 | 0.106 | -0.051 | 10.4 | 4 | 6 | False |
| unfiltered_705 | atr_pctile_quintile | Q2 | 140 | 48.6 | 1.449 | 0.195 | 0.106 | 0.089 | 36.5 | 3 | 6 | False |
| unfiltered_705 | atr_pctile_quintile | Q3 | 140 | 41.4 | 1.22 | 0.097 | 0.106 | -0.009 | 18.1 | 4 | 6 | False |
| unfiltered_705 | atr_pctile_quintile | Q4 | 140 | 45.0 | 1.262 | 0.118 | 0.106 | 0.012 | 22.0 | 4 | 6 | False |
| unfiltered_705 | atr_pctile_quintile | Q5 | 132 | 37.1 | 1.19 | 0.083 | 0.106 | -0.023 | 14.7 | 2 | 6 | False |
| unfiltered_705 | gap_and_go_1000 | TRUE | 82 | 31.7 | 0.742 | -0.148 | 0.106 | -0.254 | -16.2 | 5 | 6 | True |
| unfiltered_705 | gap_fill_1000 | TRUE | 101 | 40.6 | 0.943 | -0.03 | 0.106 | -0.136 | -4.0 | 4 | 6 | True |
| unfiltered_705 | gap_fill_1030 | TRUE | 145 | 42.1 | 1.009 | 0.004 | 0.106 | -0.102 | 0.9 | 4 | 6 | True |
| unfiltered_705 | high_vol_1000 | TRUE | 256 | 40.2 | 1.213 | 0.095 | 0.106 | -0.011 | 32.6 | 4 | 6 | False |
| unfiltered_705 | low_vol_1000 | TRUE | 210 | 46.2 | 1.324 | 0.144 | 0.106 | 0.038 | 40.5 | 4 | 6 | False |
| unfiltered_705 | opening_gap_atr_quintile | Q1 | 139 | 41.0 | 1.075 | 0.037 | 0.106 | -0.069 | 6.9 | 3 | 6 | False |
| unfiltered_705 | opening_gap_atr_quintile | Q2 | 138 | 42.0 | 1.146 | 0.072 | 0.106 | -0.034 | 13.4 | 3 | 6 | False |
| unfiltered_705 | opening_gap_atr_quintile | Q3 | 138 | 39.9 | 1.255 | 0.103 | 0.106 | -0.003 | 19.1 | 3 | 6 | False |
| unfiltered_705 | opening_gap_atr_quintile | Q4 | 138 | 45.7 | 1.473 | 0.194 | 0.106 | 0.088 | 35.9 | 3 | 6 | False |
| unfiltered_705 | opening_gap_atr_quintile | Q5 | 139 | 46.0 | 1.34 | 0.142 | 0.106 | 0.036 | 26.5 | 2 | 6 | False |
| unfiltered_705 | range_dev_1000 | TRUE | 218 | 40.8 | 1.207 | 0.094 | 0.106 | -0.012 | 27.4 | 2 | 6 | False |
| unfiltered_705 | trend_dn_dev_1000 | TRUE | 17 | 58.8 | 3.23 | 0.506 | 0.106 | 0.4 | 11.5 | 5 | 5 | False |
| unfiltered_705 | trend_up_dev_1000 | TRUE | 11 | 27.3 | 0.444 | -0.387 | 0.106 | -0.493 | -5.7 | 5 | 6 | False |
| unfiltered_705 | vwap_slope_quintile | Q1 | 97 | 58.8 | 2.52 | 0.415 | 0.106 | 0.309 | 53.8 | 5 | 6 | True |
| unfiltered_705 | vwap_slope_quintile | Q2 | 96 | 44.8 | 1.467 | 0.19 | 0.106 | 0.084 | 24.5 | 3 | 6 | False |
| unfiltered_705 | vwap_slope_quintile | Q3 | 96 | 30.2 | 0.737 | -0.15 | 0.106 | -0.256 | -19.3 | 6 | 6 | True |
| unfiltered_705 | vwap_slope_quintile | Q4 | 96 | 42.7 | 1.096 | 0.05 | 0.106 | -0.056 | 6.4 | 3 | 6 | False |
| unfiltered_705 | vwap_slope_quintile | Q5 | 96 | 46.9 | 1.349 | 0.15 | 0.106 | 0.044 | 19.2 | 4 | 6 | False |

