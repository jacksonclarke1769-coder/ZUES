# ES Edge Expansion -- Lane D -- M13: ES/NQ Divergence Context

**CFD proxy, documented optimistic bias vs real futures; graduates need real CME data before certification.** RESEARCH ONLY. LIVE HOLD ACTIVE. No commits.

Descriptive/conditional-stats lane only -- no strategy grid, no PnL.

## Joint ES/NQ 5m frame coverage

- ES bars: 205,094  ·  NQ bars: 205,122  ·  common ts: 205,070 (99.99% of ES, 99.97% of NQ) -- both stores are the same-vintage Dukascopy 24h ET CFD-index-proxy pipeline, 2016-01-04 -> 2026-05-25.

## Context-tag stats (ES forward 30m/60m, conditioned on tag)

`up_frac_Nm` = P(ES fwd_ret_Nm > 0). `mean_fwd_ret/mfe/mae_*_atr` are ATR-normalized (atr14_daily_prior). Tags 1/2 measured at the 10:00 ET stamp (first-30m window close); tags 3/4 measured at both 10:00 and 10:30 stamps.

**Data-availability note** (structural, matches `H_statistical_baseline_search.py`'s documented precedent): `vwap_slope_6bar` (tag 4's basis) needs 6 prior bars and is NaN at the 10:00 stamp for BOTH instruments (only 6 bars elapsed, `diff(6)` has no history) -- `tag4_rs_slope_1000` is therefore structurally empty and correctly absent from the table below (not a coding omission); tag4 is only reportable at the 10:30 stamp.

| tag | value | n | n_fwd30 | up_frac_30m | mean_fwd_ret_30m_atr | mean_mfe_30m_atr | mean_mae_30m_atr | n_fwd60 | up_frac_60m | mean_fwd_ret_60m_atr |
|---|---|---|---|---|---|---|---|---|---|---|
| tag1_dir_agree | agree | 2135 | 2122 | 0.5434 | 0.0002 | 0.1449 | -0.1555 | 2122 | 0.5424 | -0.0013 |
| tag1_dir_agree | disagree | 540 | 539 | 0.4787 | -0.0121 | 0.1307 | -0.158 | 539 | 0.5083 | -0.0201 |
| tag2_es_stronger | es_stronger | 1087 | 1087 | 0.517 | -0.0068 | 0.1381 | -0.1588 | 1087 | 0.5336 | -0.0019 |
| tag2_es_stronger | nq_stronger | 1577 | 1577 | 0.5396 | 0.0009 | 0.1447 | -0.1542 | 1577 | 0.5377 | -0.007 |
| tag3_vwap_side_1000 | es_above_nq_below | 227 | 227 | 0.4626 | -0.0265 | 0.1192 | -0.1619 | 227 | 0.5022 | -0.0377 |
| tag3_vwap_side_1000 | es_below_nq_above | 241 | 241 | 0.5809 | 0.0144 | 0.1493 | -0.1485 | 241 | 0.556 | 0.0219 |
| tag3_vwap_side_1000 | same_side | 2196 | 2196 | 0.5319 | -0.0016 | 0.1436 | -0.1563 | 2196 | 0.5373 | -0.0045 |
| tag3_vwap_side_1030 | es_above_nq_below | 212 | 212 | 0.5566 | -0.0083 | 0.1144 | -0.1295 | 211 | 0.5782 | 0.0037 |
| tag3_vwap_side_1030 | es_below_nq_above | 204 | 204 | 0.5637 | 0.0155 | 0.1412 | -0.1292 | 204 | 0.6078 | 0.037 |
| tag3_vwap_side_1030 | same_side | 2248 | 2248 | 0.5116 | -0.0038 | 0.1266 | -0.1383 | 2242 | 0.5241 | 0.0 |
| tag4_rs_slope_1030 | es_relatively_stronger_slope | 1240 | 1229 | 0.5102 | -0.0092 | 0.1307 | -0.1516 | 1224 | 0.5123 | -0.0027 |
| tag4_rs_slope_1030 | nq_relatively_stronger_slope | 1438 | 1435 | 0.5268 | 0.0029 | 0.1234 | -0.1244 | 1433 | 0.5541 | 0.0082 |

### Per-year breakdown (30m horizon, years with n>=5 shown)

| tag | value | year | n | up_frac_30m | mean_fwd_ret_30m_atr |
|---|---|---|---|---|---|
| tag1_dir_agree | agree | 2016 | 209 | 0.5102 | -0.0038 |
| tag1_dir_agree | agree | 2017 | 189 | 0.4921 | 0.0031 |
| tag1_dir_agree | agree | 2018 | 201 | 0.5274 | -0.0055 |
| tag1_dir_agree | agree | 2019 | 220 | 0.5455 | 0.0105 |
| tag1_dir_agree | agree | 2020 | 191 | 0.6335 | 0.013 |
| tag1_dir_agree | agree | 2021 | 203 | 0.5616 | -0.0064 |
| tag1_dir_agree | agree | 2022 | 220 | 0.5227 | -0.0128 |
| tag1_dir_agree | agree | 2023 | 194 | 0.5361 | 0.0005 |
| tag1_dir_agree | agree | 2024 | 205 | 0.5268 | -0.0041 |
| tag1_dir_agree | agree | 2025 | 218 | 0.5872 | 0.0141 |
| tag1_dir_agree | agree | 2026 | 85 | 0.5176 | -0.0161 |
| tag1_dir_agree | disagree | 2016 | 49 | 0.4375 | -0.0231 |
| tag1_dir_agree | disagree | 2017 | 66 | 0.5303 | -0.001 |
| tag1_dir_agree | disagree | 2018 | 56 | 0.5179 | -0.006 |
| tag1_dir_agree | disagree | 2019 | 38 | 0.4474 | -0.0188 |
| tag1_dir_agree | disagree | 2020 | 68 | 0.4706 | -0.0304 |
| tag1_dir_agree | disagree | 2021 | 54 | 0.4074 | -0.03 |
| tag1_dir_agree | disagree | 2022 | 38 | 0.4737 | -0.0262 |
| tag1_dir_agree | disagree | 2023 | 62 | 0.4355 | -0.0257 |
| tag1_dir_agree | disagree | 2024 | 54 | 0.6111 | 0.0215 |
| tag1_dir_agree | disagree | 2025 | 39 | 0.3846 | -0.011 |
| tag1_dir_agree | disagree | 2026 | 16 | 0.5625 | 0.0794 |
| tag2_es_stronger | es_stronger | 2016 | 97 | 0.4948 | -0.0034 |
| tag2_es_stronger | es_stronger | 2017 | 117 | 0.4786 | -0.0082 |
| tag2_es_stronger | es_stronger | 2018 | 90 | 0.5111 | -0.0288 |
| tag2_es_stronger | es_stronger | 2019 | 120 | 0.525 | 0.0063 |
| tag2_es_stronger | es_stronger | 2020 | 102 | 0.549 | 0.0028 |
| tag2_es_stronger | es_stronger | 2021 | 117 | 0.5128 | -0.0201 |
| tag2_es_stronger | es_stronger | 2022 | 108 | 0.5185 | -0.0246 |
| tag2_es_stronger | es_stronger | 2023 | 95 | 0.4947 | -0.0156 |
| tag2_es_stronger | es_stronger | 2024 | 102 | 0.5882 | 0.0206 |
| tag2_es_stronger | es_stronger | 2025 | 99 | 0.5152 | 0.0046 |
| tag2_es_stronger | es_stronger | 2026 | 40 | 0.475 | -0.0166 |
| tag2_es_stronger | nq_stronger | 2016 | 147 | 0.4966 | -0.0103 |
| tag2_es_stronger | nq_stronger | 2017 | 140 | 0.5214 | 0.0098 |
| tag2_es_stronger | nq_stronger | 2018 | 167 | 0.5329 | 0.0069 |
| tag2_es_stronger | nq_stronger | 2019 | 138 | 0.5362 | 0.006 |
| tag2_es_stronger | nq_stronger | 2020 | 157 | 0.6178 | 0.0008 |
| tag2_es_stronger | nq_stronger | 2021 | 141 | 0.5461 | -0.0028 |
| tag2_es_stronger | nq_stronger | 2022 | 150 | 0.5133 | -0.0077 |
| tag2_es_stronger | nq_stronger | 2023 | 161 | 0.5217 | -0.0001 |
| tag2_es_stronger | nq_stronger | 2024 | 157 | 0.5159 | -0.0114 |
| tag2_es_stronger | nq_stronger | 2025 | 158 | 0.5823 | 0.0139 |
| tag2_es_stronger | nq_stronger | 2026 | 61 | 0.5574 | 0.0093 |
| tag3_vwap_side_1000 | es_above_nq_below | 2016 | 19 | 0.3684 | -0.0404 |
| tag3_vwap_side_1000 | es_above_nq_below | 2017 | 27 | 0.3333 | -0.0334 |
| tag3_vwap_side_1000 | es_above_nq_below | 2018 | 13 | 0.5385 | -0.0111 |
| tag3_vwap_side_1000 | es_above_nq_below | 2019 | 18 | 0.7222 | 0.0432 |
| tag3_vwap_side_1000 | es_above_nq_below | 2020 | 23 | 0.3913 | -0.0776 |
| tag3_vwap_side_1000 | es_above_nq_below | 2021 | 26 | 0.5385 | -0.0022 |
| tag3_vwap_side_1000 | es_above_nq_below | 2022 | 14 | 0.3571 | -0.0635 |
| tag3_vwap_side_1000 | es_above_nq_below | 2023 | 33 | 0.5152 | -0.0174 |
| tag3_vwap_side_1000 | es_above_nq_below | 2024 | 29 | 0.4828 | -0.0374 |
| tag3_vwap_side_1000 | es_above_nq_below | 2025 | 17 | 0.3529 | -0.038 |
| tag3_vwap_side_1000 | es_above_nq_below | 2026 | 8 | 0.5 | 0.0058 |
| tag3_vwap_side_1000 | es_below_nq_above | 2016 | 26 | 0.4615 | -0.0187 |
| tag3_vwap_side_1000 | es_below_nq_above | 2017 | 23 | 0.5217 | 0.0007 |
| tag3_vwap_side_1000 | es_below_nq_above | 2018 | 23 | 0.5217 | 0.0029 |
| tag3_vwap_side_1000 | es_below_nq_above | 2019 | 23 | 0.5652 | -0.0076 |
| tag3_vwap_side_1000 | es_below_nq_above | 2020 | 26 | 0.6538 | 0.0124 |
| tag3_vwap_side_1000 | es_below_nq_above | 2021 | 35 | 0.6 | 0.0161 |
| tag3_vwap_side_1000 | es_below_nq_above | 2022 | 20 | 0.6 | -0.0107 |
| tag3_vwap_side_1000 | es_below_nq_above | 2023 | 21 | 0.5238 | 0.0169 |
| tag3_vwap_side_1000 | es_below_nq_above | 2024 | 20 | 0.6 | 0.017 |
| tag3_vwap_side_1000 | es_below_nq_above | 2025 | 17 | 0.7647 | 0.1015 |
| tag3_vwap_side_1000 | es_below_nq_above | 2026 | 7 | 0.7143 | 0.136 |
| tag3_vwap_side_1000 | same_side | 2016 | 199 | 0.5126 | -0.003 |
| tag3_vwap_side_1000 | same_side | 2017 | 207 | 0.5217 | 0.0062 |
| tag3_vwap_side_1000 | same_side | 2018 | 221 | 0.5249 | -0.0062 |
| tag3_vwap_side_1000 | same_side | 2019 | 217 | 0.5115 | 0.0045 |
| tag3_vwap_side_1000 | same_side | 2020 | 210 | 0.6048 | 0.009 |
| tag3_vwap_side_1000 | same_side | 2021 | 197 | 0.5178 | -0.0165 |
| tag3_vwap_side_1000 | same_side | 2022 | 224 | 0.5179 | -0.0121 |
| tag3_vwap_side_1000 | same_side | 2023 | 202 | 0.5099 | -0.0063 |
| tag3_vwap_side_1000 | same_side | 2024 | 210 | 0.5476 | 0.0051 |
| tag3_vwap_side_1000 | same_side | 2025 | 223 | 0.5561 | 0.007 |
| tag3_vwap_side_1000 | same_side | 2026 | 86 | 0.5116 | -0.0127 |
| tag3_vwap_side_1030 | es_above_nq_below | 2016 | 14 | 0.6429 | 0.0289 |
| tag3_vwap_side_1030 | es_above_nq_below | 2017 | 25 | 0.68 | -0.0462 |
| tag3_vwap_side_1030 | es_above_nq_below | 2018 | 12 | 0.75 | 0.1188 |
| tag3_vwap_side_1030 | es_above_nq_below | 2019 | 23 | 0.5652 | -0.0289 |
| tag3_vwap_side_1030 | es_above_nq_below | 2020 | 30 | 0.4667 | -0.0402 |
| tag3_vwap_side_1030 | es_above_nq_below | 2021 | 30 | 0.4667 | -0.0084 |
| tag3_vwap_side_1030 | es_above_nq_below | 2022 | 12 | 0.3333 | -0.0613 |
| tag3_vwap_side_1030 | es_above_nq_below | 2023 | 21 | 0.4286 | -0.0225 |
| tag3_vwap_side_1030 | es_above_nq_below | 2024 | 15 | 0.7333 | 0.0361 |
| tag3_vwap_side_1030 | es_above_nq_below | 2025 | 21 | 0.5714 | -0.0115 |
| tag3_vwap_side_1030 | es_above_nq_below | 2026 | 9 | 0.6667 | 0.0673 |
| tag3_vwap_side_1030 | es_below_nq_above | 2016 | 27 | 0.6296 | 0.02 |
| tag3_vwap_side_1030 | es_below_nq_above | 2017 | 22 | 0.5 | 0.0351 |
| tag3_vwap_side_1030 | es_below_nq_above | 2018 | 31 | 0.5806 | -0.0219 |
| tag3_vwap_side_1030 | es_below_nq_above | 2019 | 16 | 0.5625 | 0.0092 |
| tag3_vwap_side_1030 | es_below_nq_above | 2020 | 21 | 0.7619 | 0.0316 |
| tag3_vwap_side_1030 | es_below_nq_above | 2021 | 24 | 0.5417 | -0.001 |
| tag3_vwap_side_1030 | es_below_nq_above | 2022 | 14 | 0.5714 | 0.0957 |
| tag3_vwap_side_1030 | es_below_nq_above | 2023 | 14 | 0.5714 | 0.0345 |
| tag3_vwap_side_1030 | es_below_nq_above | 2024 | 15 | 0.3333 | -0.0409 |
| tag3_vwap_side_1030 | es_below_nq_above | 2025 | 17 | 0.4118 | -0.0053 |
| tag3_vwap_side_1030 | same_side | 2016 | 203 | 0.4975 | -0.0116 |
| tag3_vwap_side_1030 | same_side | 2017 | 210 | 0.5143 | 0.0194 |
| tag3_vwap_side_1030 | same_side | 2018 | 214 | 0.5 | -0.0061 |
| tag3_vwap_side_1030 | same_side | 2019 | 219 | 0.5753 | 0.0078 |
| tag3_vwap_side_1030 | same_side | 2020 | 208 | 0.5096 | -0.0185 |
| tag3_vwap_side_1030 | same_side | 2021 | 204 | 0.5441 | 0.0039 |
| tag3_vwap_side_1030 | same_side | 2022 | 232 | 0.4655 | -0.0029 |
| tag3_vwap_side_1030 | same_side | 2023 | 221 | 0.5068 | -0.0123 |
| tag3_vwap_side_1030 | same_side | 2024 | 229 | 0.4803 | -0.0085 |
| tag3_vwap_side_1030 | same_side | 2025 | 219 | 0.4886 | -0.0189 |
| tag3_vwap_side_1030 | same_side | 2026 | 89 | 0.6067 | 0.022 |
| tag4_rs_slope_1030 | es_relatively_stronger_slope | 2016 | 116 | 0.5619 | 0.0088 |
| tag4_rs_slope_1030 | es_relatively_stronger_slope | 2017 | 124 | 0.5242 | 0.0077 |
| tag4_rs_slope_1030 | es_relatively_stronger_slope | 2018 | 120 | 0.475 | -0.007 |
| tag4_rs_slope_1030 | es_relatively_stronger_slope | 2019 | 124 | 0.5806 | -0.0069 |
| tag4_rs_slope_1030 | es_relatively_stronger_slope | 2020 | 99 | 0.5455 | 0.0009 |
| tag4_rs_slope_1030 | es_relatively_stronger_slope | 2021 | 118 | 0.5339 | -0.0116 |
| tag4_rs_slope_1030 | es_relatively_stronger_slope | 2022 | 127 | 0.5039 | 0.0019 |
| tag4_rs_slope_1030 | es_relatively_stronger_slope | 2023 | 120 | 0.4583 | -0.0342 |
| tag4_rs_slope_1030 | es_relatively_stronger_slope | 2024 | 122 | 0.4344 | -0.0262 |
| tag4_rs_slope_1030 | es_relatively_stronger_slope | 2025 | 121 | 0.438 | -0.0328 |
| tag4_rs_slope_1030 | es_relatively_stronger_slope | 2026 | 49 | 0.6531 | 0.0175 |
| tag4_rs_slope_1030 | nq_relatively_stronger_slope | 2016 | 142 | 0.4892 | -0.0167 |
| tag4_rs_slope_1030 | nq_relatively_stronger_slope | 2017 | 133 | 0.5338 | 0.0205 |
| tag4_rs_slope_1030 | nq_relatively_stronger_slope | 2018 | 137 | 0.562 | 0.002 |
| tag4_rs_slope_1030 | nq_relatively_stronger_slope | 2019 | 134 | 0.5672 | 0.0152 |
| tag4_rs_slope_1030 | nq_relatively_stronger_slope | 2020 | 160 | 0.5125 | -0.028 |
| tag4_rs_slope_1030 | nq_relatively_stronger_slope | 2021 | 140 | 0.5357 | 0.0134 |
| tag4_rs_slope_1030 | nq_relatively_stronger_slope | 2022 | 131 | 0.4275 | -0.0023 |
| tag4_rs_slope_1030 | nq_relatively_stronger_slope | 2023 | 136 | 0.5441 | 0.0103 |
| tag4_rs_slope_1030 | nq_relatively_stronger_slope | 2024 | 137 | 0.5328 | 0.0086 |
| tag4_rs_slope_1030 | nq_relatively_stronger_slope | 2025 | 136 | 0.5368 | -0.0036 |
| tag4_rs_slope_1030 | nq_relatively_stronger_slope | 2026 | 52 | 0.5962 | 0.0447 |

## Portfolio question: NQ-quiet vs NQ-active days -- what does ES do?

NQ-active = date in honest-A3 stream (`kept==True`, 537 unique dates) UNION VPC-408 stream (401 unique dates) = 763 unique active dates. Window: 2022-01-01 -> 2026-05-25 (VPC-408's own certified window).

| group | n | mean_rth_range_atr | median_rth_range_atr | mean_first30m_ret_atr_abs | pct_trend_days |
|---|---|---|---|---|---|
| NQ-active | 685 | 0.9013 | 0.8244 | 0.1653 | 2.9197 |
| NQ-quiet | 446 | 0.9286 | 0.8538 | 0.1758 | 3.139 |

### Per-year breakdown

| group | year | n | mean_rth_range_atr | median_rth_range_atr | mean_first30m_ret_atr_abs | pct_trend_days |
|---|---|---|---|---|---|---|
| NQ-active | 2022 | 151 | 0.8908 | 0.8109 | 0.1644 | 1.3245 |
| NQ-quiet | 2022 | 107 | 0.9578 | 0.894 | 0.1933 | 1.8692 |
| NQ-active | 2023 | 159 | 0.8817 | 0.8308 | 0.1537 | 1.2579 |
| NQ-quiet | 2023 | 97 | 0.9354 | 0.8726 | 0.1589 | 1.0309 |
| NQ-active | 2024 | 152 | 0.8984 | 0.8453 | 0.1508 | 3.2895 |
| NQ-quiet | 2024 | 107 | 0.9729 | 0.8589 | 0.1475 | 2.8037 |
| NQ-active | 2025 | 161 | 0.941 | 0.7717 | 0.1698 | 4.9689 |
| NQ-quiet | 2025 | 96 | 0.8472 | 0.7365 | 0.1982 | 6.25 |
| NQ-active | 2026 | 62 | 0.8816 | 0.8477 | 0.2214 | 4.8387 |
| NQ-quiet | 2026 | 39 | 0.9109 | 0.8502 | 0.1923 | 5.1282 |

**Answer**: ES's mean RTH-range/ATR is 0.9286 on NQ-quiet days vs 0.9013 on NQ-active days -> ES shows MORE range/opportunity when NQ (A3+VPC) sleeps. Trend-day rate (|first_30m_ret|>0.5xATR): 3.1% (quiet) vs 2.9% (active).

## Runtime

2.2s wall clock.
