# NQ Pattern Discovery — Discovery Lane D: VWAP Behaviour

RESEARCH ONLY — distributions/conditional stats only, no strategy construction, no backtest. Reads `store/features_intraday.parquet` + `store/features_daily.parquet` (foundation-lane, read-only). Full methodology in `D_vwap_behaviour.py`'s module docstring (touch/reclaim/rejection/extension/sweep/quadrant definitions).

PRIOR (from task brief): VPC (VWAP pullback continuation) is the one surviving VWAP strategy (PF 1.29); Asia/London VWAP scalpers are dead. This lane maps raw VWAP behaviour — it does not rebuild or re-test any strategy.

## Summary: 183/196 cells consistency-flagged

Consistency flag = pooled n >= 200 AND same-sign (vs the null: 0.5 for fractions/shares, 0 for mean returns) in >= 8 of the 11 calendar years 2016-2026.

## D1 — first VWAP touch after open: timing

Touch-minute distribution (minutes since 09:30 open) by prior side:

```
             count      mean       std  min  25%  50%  75%   max
prior_side                                                      
above       2752.0  5.472384  3.372322  5.0  5.0  5.0  5.0  90.0
below       2598.0  5.146266  1.611522  5.0  5.0  5.0  5.0  50.0
```

## 10 strongest consistency-flagged cells (across D1-D5)

| workstream | analysis | metric | n | value | n_years_match | n_years_total | consistent | prior_side | horizon_min | dir | event_type | bucket | tod | sweep_any | quadrant |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D | D5_slope_quadrant_upfrac | up | 87066 | 0.5319 | 11 | 11 | True | nan | nan | nan | nan | nan | nan | nan | slope_up/price_above |
| D | D4_sweep_interaction_30m | outcome_30=extend | 65390 | 0.4707 | 11 | 11 | True | nan | nan | nan | nan | >2.0 | nan | False | nan |
| D | D4_sweep_interaction_30m | outcome_30=neither | 65390 | 0.4943 | 11 | 11 | True | nan | nan | nan | nan | >2.0 | nan | False | nan |
| D | D4_sweep_interaction_30m | outcome_30=revert | 65390 | 0.0346 | 11 | 11 | True | nan | nan | nan | nan | >2.0 | nan | False | nan |
| D | D4_sweep_interaction_30m | outcome_30=tie | 65390 | 0.0004 | 11 | 11 | True | nan | nan | nan | nan | >2.0 | nan | False | nan |
| D | D4_sweep_interaction_60m | outcome_60=extend | 65390 | 0.5586 | 11 | 11 | True | nan | nan | nan | nan | >2.0 | nan | False | nan |
| D | D4_sweep_interaction_60m | outcome_60=revert | 65390 | 0.0855 | 11 | 11 | True | nan | nan | nan | nan | >2.0 | nan | False | nan |
| D | D4_sweep_interaction_60m | outcome_60=neither | 65390 | 0.3553 | 11 | 11 | True | nan | nan | nan | nan | >2.0 | nan | False | nan |
| D | D4_sweep_interaction_60m | outcome_60=tie | 65390 | 0.0007 | 11 | 11 | True | nan | nan | nan | nan | >2.0 | nan | False | nan |
| D | D3_extension_race_30m | outcome_30=extend | 43001 | 0.4926 | 11 | 11 | True | nan | nan | nan | nan | >2.0 | post_1330 | nan | nan |

## 5 most decisive nulls (largest n, NOT consistency-flagged)

| workstream | analysis | metric | n | value | n_years_match | n_years_total | consistent | prior_side | horizon_min | dir | event_type | bucket | tod | sweep_any | quadrant |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D | D5_slope_quadrant | fwd_ret_30m_atr | 65544 | -0.0016 | 6 | 11 | False | nan | nan | nan | nan | nan | nan | nan | slope_down/price_below |
| D | D4_sweep_interaction_60m | outcome_60=revert | 16694 | 0.253 | 6 | 11 | False | nan | nan | nan | nan | 1.5-2.0 | nan | False | nan |
| D | D3_extension_race_30m | outcome_30=neither | 11787 | 0.2628 | 7 | 11 | False | nan | nan | nan | nan | 1.0-1.5 | mid_1100_1330 | nan | nan |
| D | D5_slope_quadrant | fwd_ret_30m_atr | 10323 | 0.0032 | 7 | 11 | False | nan | nan | nan | nan | nan | nan | nan | slope_down/price_above |
| D | D3_extension_race_60m | outcome_60=revert | 10208 | 0.2577 | 7 | 11 | False | nan | nan | nan | nan | 1.5-2.0 | mid_1100_1330 | nan | nan |

## Event counts

- D1 touch events: 5350
- D2 cross events (reclaim/rejection/plain-cross-shallow, both directions): 23358
- D3/D4 extension-bucket bar-events: 162321
- D5 quadrant bar-events: 172835

## Full cell table

See `D_vwap_behaviour.csv` for all cells (workstream/analysis/metric/n/value/n_years_match/consistent).
