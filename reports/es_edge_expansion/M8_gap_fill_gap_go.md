# ES Edge Expansion -- Lane D -- M8: Gap Fill / Gap-and-Go

**CFD proxy, documented optimistic bias vs real futures; graduates need real CME data before certification.** RESEARCH ONLY. LIVE HOLD ACTIVE. No commits.

Valid days: 2639 / 2678 (98.5%) -- Wave-1 adjudicated mask (density>=95% OR half-day profile).

## Behaviour table (per gap bucket x direction) -- reported FIRST, per task brief

`P(fill by 11:00 ET)` / `P(fill by EOD)` / `P(extends 1x gap before fill)`, descriptive (no PnL). `<0.25` bucket skipped per brief (noise).

| gap_bucket | dir_label | n | p_fill_1100 | p_fill_eod | p_extend_before_fill |
|---|---|---|---|---|---|
| 0.25-0.75 | down | 447 | 0.2394 | 0.4586 | 0.3848 |
| 0.25-0.75 | up | 689 | 0.2337 | 0.4107 | 0.3716 |
| 0.75-1.25 | down | 107 | 0.0654 | 0.2617 | 0.1776 |
| 0.75-1.25 | up | 97 | 0.0412 | 0.2165 | 0.0928 |
| >1.25 | down | 39 | 0.0256 | 0.0513 | 0.1795 |
| >1.25 | up | 19 | 0.0 | 0.0526 | 0.0 |

### Per-year breakdown (n>=1 shown; small-n years are noisy)

| gap_bucket | dir_label | year | n | p_fill_1100 | p_fill_eod | p_extend_before_fill |
|---|---|---|---|---|---|---|
| 0.25-0.75 | down | 2016 | 53 | 0.3019 | 0.5094 | 0.3585 |
| 0.25-0.75 | down | 2017 | 46 | 0.2391 | 0.3913 | 0.2826 |
| 0.25-0.75 | down | 2018 | 38 | 0.2632 | 0.4737 | 0.4737 |
| 0.25-0.75 | down | 2019 | 37 | 0.2703 | 0.4865 | 0.3784 |
| 0.25-0.75 | down | 2020 | 40 | 0.175 | 0.425 | 0.225 |
| 0.25-0.75 | down | 2021 | 40 | 0.175 | 0.4 | 0.475 |
| 0.25-0.75 | down | 2022 | 54 | 0.2037 | 0.3704 | 0.4444 |
| 0.25-0.75 | down | 2023 | 52 | 0.2308 | 0.4808 | 0.3846 |
| 0.25-0.75 | down | 2024 | 32 | 0.2812 | 0.5938 | 0.4688 |
| 0.25-0.75 | down | 2025 | 36 | 0.2222 | 0.5 | 0.4167 |
| 0.25-0.75 | down | 2026 | 19 | 0.3158 | 0.4737 | 0.3158 |
| 0.25-0.75 | up | 2016 | 57 | 0.2456 | 0.3684 | 0.4035 |
| 0.25-0.75 | up | 2017 | 68 | 0.2353 | 0.3824 | 0.4265 |
| 0.25-0.75 | up | 2018 | 74 | 0.1892 | 0.3378 | 0.4459 |
| 0.25-0.75 | up | 2019 | 72 | 0.1944 | 0.375 | 0.2917 |
| 0.25-0.75 | up | 2020 | 74 | 0.2568 | 0.3919 | 0.2432 |
| 0.25-0.75 | up | 2021 | 75 | 0.24 | 0.3867 | 0.4267 |
| 0.25-0.75 | up | 2022 | 57 | 0.2456 | 0.5439 | 0.4035 |
| 0.25-0.75 | up | 2023 | 54 | 0.2778 | 0.5185 | 0.4074 |
| 0.25-0.75 | up | 2024 | 67 | 0.2239 | 0.4925 | 0.403 |
| 0.25-0.75 | up | 2025 | 66 | 0.2576 | 0.4091 | 0.2879 |
| 0.25-0.75 | up | 2026 | 25 | 0.2 | 0.28 | 0.36 |
| 0.75-1.25 | down | 2016 | 8 | 0.125 | 0.125 | 0.25 |
| 0.75-1.25 | down | 2017 | 8 | 0.0 | 0.5 | 0.125 |
| 0.75-1.25 | down | 2018 | 15 | 0.2 | 0.3333 | 0.2 |
| 0.75-1.25 | down | 2019 | 10 | 0.0 | 0.1 | 0.1 |
| 0.75-1.25 | down | 2020 | 10 | 0.0 | 0.4 | 0.0 |
| 0.75-1.25 | down | 2021 | 7 | 0.1429 | 0.2857 | 0.4286 |
| 0.75-1.25 | down | 2022 | 12 | 0.0 | 0.3333 | 0.1667 |
| 0.75-1.25 | down | 2023 | 13 | 0.0 | 0.1538 | 0.2308 |
| 0.75-1.25 | down | 2024 | 10 | 0.0 | 0.0 | 0.3 |
| 0.75-1.25 | down | 2025 | 9 | 0.1111 | 0.3333 | 0.1111 |
| 0.75-1.25 | down | 2026 | 5 | 0.2 | 0.4 | 0.0 |
| 0.75-1.25 | up | 2016 | 3 | 0.0 | 0.0 | 0.0 |
| 0.75-1.25 | up | 2017 | 12 | 0.0833 | 0.4167 | 0.0833 |
| 0.75-1.25 | up | 2018 | 6 | 0.0 | 0.0 | 0.0 |
| 0.75-1.25 | up | 2019 | 11 | 0.0 | 0.0 | 0.0909 |
| 0.75-1.25 | up | 2020 | 19 | 0.0 | 0.0526 | 0.2105 |
| 0.75-1.25 | up | 2021 | 7 | 0.2857 | 0.5714 | 0.1429 |
| 0.75-1.25 | up | 2022 | 4 | 0.0 | 0.25 | 0.0 |
| 0.75-1.25 | up | 2023 | 11 | 0.0 | 0.2727 | 0.0909 |
| 0.75-1.25 | up | 2024 | 13 | 0.0769 | 0.3077 | 0.0 |
| 0.75-1.25 | up | 2025 | 9 | 0.0 | 0.3333 | 0.1111 |
| 0.75-1.25 | up | 2026 | 2 | 0.0 | 0.0 | 0.0 |
| >1.25 | down | 2016 | 1 | 0.0 | 0.0 | 0.0 |
| >1.25 | down | 2017 | 2 | 0.0 | 0.0 | 0.5 |
| >1.25 | down | 2018 | 1 | 0.0 | 0.0 | 0.0 |
| >1.25 | down | 2019 | 4 | 0.0 | 0.0 | 0.25 |
| >1.25 | down | 2020 | 12 | 0.0 | 0.0 | 0.1667 |
| >1.25 | down | 2021 | 4 | 0.0 | 0.0 | 0.0 |
| >1.25 | down | 2022 | 2 | 0.0 | 0.5 | 0.5 |
| >1.25 | down | 2024 | 4 | 0.0 | 0.0 | 0.0 |
| >1.25 | down | 2025 | 7 | 0.1429 | 0.1429 | 0.2857 |
| >1.25 | down | 2026 | 2 | 0.0 | 0.0 | 0.0 |
| >1.25 | up | 2016 | 2 | 0.0 | 0.0 | 0.0 |
| >1.25 | up | 2017 | 2 | 0.0 | 0.0 | 0.0 |
| >1.25 | up | 2018 | 1 | 0.0 | 0.0 | 0.0 |
| >1.25 | up | 2019 | 1 | 0.0 | 0.0 | 0.0 |
| >1.25 | up | 2020 | 3 | 0.0 | 0.3333 | 0.0 |
| >1.25 | up | 2021 | 1 | 0.0 | 0.0 | 0.0 |
| >1.25 | up | 2022 | 2 | 0.0 | 0.0 | 0.0 |
| >1.25 | up | 2024 | 3 | 0.0 | 0.0 | 0.0 |
| >1.25 | up | 2025 | 3 | 0.0 | 0.0 | 0.0 |
| >1.25 | up | 2026 | 1 | 0.0 | 0.0 | 0.0 |

## Strategy grid -- live regions

648 cells run total (all in CSV: `M8_gap_fill_gap_go.csv`). 'live_candidate' = PF>=1.15, freq>=0.3/wk, PF<=1.8.

- live_candidate: 20  ·  freeze (PF>1.8, re-verify): 0  ·  dead (PF<1.15): 160  ·  sub-frequency-floor: 468  ·  insufficient n: 0

### live_candidate cells (top 25 by PF)

| model | confirm | entry | filter | bucket | stop | exit | n | tr_wk | wr | pf | expR | totR | maxDD_R | mirage |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fill | conf5 | next_open | first15m_strength | 0.25-0.75 | open_buffer | 1.5R | 184 | 0.339 | 0.6087 | 1.7909 | 0.3401 | 62.58 | -6.125 | False |
| fill | conf5 | next_open | first15m_strength | 0.25-0.75 | open_buffer | prior_close | 184 | 0.339 | 0.6685 | 1.762 | 0.2693 | 49.556 | -8.651 | False |
| fill | conf5 | next_open | first15m_strength | 0.25-0.75 | open_buffer | 2R | 184 | 0.339 | 0.5326 | 1.7241 | 0.3634 | 66.865 | -7.819 | False |
| and_go | conf5 | next_open | first15m_strength | 0.25-0.75 | open_buffer | 1.5R | 220 | 0.406 | 0.5909 | 1.7155 | 0.3142 | 69.124 | -9.269 | False |
| and_go | conf5 | next_open | first15m_strength | 0.25-0.75 | open_buffer | 2R | 220 | 0.406 | 0.5182 | 1.5943 | 0.3084 | 67.851 | -8.269 | False |
| fill | conf5 | next_open | first15m_strength | 0.25-0.75 | atr1.5 | 1.5R | 184 | 0.339 | 0.5598 | 1.5771 | 0.0855 | 15.727 | -2.444 | False |
| fill | conf5 | next_open | first15m_strength | 0.25-0.75 | atr1.5 | 2R | 184 | 0.339 | 0.5598 | 1.5651 | 0.0837 | 15.4 | -2.444 | False |
| fill | conf5 | next_open | first15m_strength | 0.25-0.75 | atr1.0 | 2R | 184 | 0.339 | 0.5598 | 1.5453 | 0.1233 | 22.687 | -4.029 | False |
| fill | conf5 | next_open | first15m_strength | 0.25-0.75 | atr1.0 | 1.5R | 184 | 0.339 | 0.5598 | 1.5428 | 0.1227 | 22.584 | -4.029 | False |
| fill | conf5 | next_open | first15m_strength | 0.25-0.75 | atr1.5 | prior_close | 184 | 0.339 | 0.7283 | 1.3806 | 0.034 | 6.248 | -3.12 | False |
| fill | conf15 | next_open | first15m_strength | 0.25-0.75 | atr1.5 | 1.5R | 187 | 0.345 | 0.5615 | 1.3464 | 0.0553 | 10.35 | -4.652 | False |
| fill | conf15 | next_open | first15m_strength | 0.25-0.75 | atr1.0 | 1.5R | 187 | 0.345 | 0.5615 | 1.329 | 0.0792 | 14.802 | -6.247 | False |
| fill | conf15 | next_open | first15m_strength | 0.25-0.75 | open_buffer | 2R | 187 | 0.345 | 0.5027 | 1.3204 | 0.15 | 28.043 | -8.751 | False |
| fill | conf15 | next_open | first15m_strength | 0.25-0.75 | atr1.5 | 2R | 187 | 0.345 | 0.5615 | 1.3136 | 0.0501 | 9.367 | -4.652 | False |
| fill | conf15 | next_open | first15m_strength | 0.25-0.75 | atr1.0 | 2R | 187 | 0.345 | 0.5615 | 1.3134 | 0.0754 | 14.099 | -6.247 | False |
| fill | conf15 | next_open | first15m_strength | 0.25-0.75 | open_buffer | 1.5R | 187 | 0.345 | 0.5241 | 1.3086 | 0.1396 | 26.104 | -9.312 | False |
| fill | conf5 | next_open | first15m_strength | 0.25-0.75 | atr1.0 | prior_close | 184 | 0.339 | 0.7283 | 1.2894 | 0.0415 | 7.631 | -4.357 | False |
| and_go | conf5 | next_open | first15m_strength | 0.25-0.75 | atr1.0 | 1.5R | 220 | 0.406 | 0.5455 | 1.1714 | 0.0385 | 8.479 | -9.982 | False |
| and_go | conf5 | next_open | first15m_strength | 0.25-0.75 | atr1.0 | 2R | 220 | 0.406 | 0.5455 | 1.169 | 0.038 | 8.361 | -9.982 | False |
| fill | conf5 | next_open | first15m_strength | 0.25-0.75 | open_buffer | half_gap | 184 | 0.339 | 0.5652 | 1.1572 | 0.0338 | 6.21 | -8.78 | False |

- of the 20 live_candidate cells, 20 are NOT mirage/one-regime-flagged.

## VERDICT: M8 has 20 non-mirage live_candidate cell(s) -- see table above. RESEARCH ONLY, not certified: needs independent replication + the full edge-killer battery before any promotion.

## Runtime

9.9s wall clock.
