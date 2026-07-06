# Wyckoff state tags on the FROZEN Profile A stream — Role 2 (Wyckoff sprint)

**RESEARCH ONLY / SIM CONDITIONAL.** Profile A model is FROZEN; this is tag-and-measure only.

Base stream: 435 certified trades (exit3 + D1c, 1m-truth) reconstructed via `tools_profileC_a_enhancement.load_frames/build_raw_and_kept` (imported, not duplicated) and asserted byte-for-byte identical to `tools_sim_parity_check.load_rows()`. Pre-D1c raw signal set: 705 (ny_am session, post model01, pre-D1c-drop).
Baseline totR = +183.9R (register: +183.9R).

## Canary (mandatory, blocking)
- @(cap10,$1200): pass=47.8 bust=15.9 exp=36.2 med=16d n=395 — expected 47.8/15.9/36.2/med16/n395 -> MATCH
- @(cap15,$1000): pass=55.2 bust=13.4 exp=31.4 med=15d n=395

## Annotation coverage (of 435 kept)
| tag | n | % |
|---|---|---|
| `w1_inrange_15m` | 434 | 99.8% |
| `w1_inrange_30m` | 433 | 99.5% |
| `w1_inrange_1h` | 364 | 83.7% |
| `w1_trend_aligned_15m` | 1 | 0.2% |
| `w1_trend_aligned_30m` | 0 | 0.0% |
| `w1_trend_aligned_1h` | 28 | 6.4% |
| `w1_trend_opposed_15m` | 0 | 0.0% |
| `w1_trend_opposed_30m` | 2 | 0.5% |
| `w1_trend_opposed_1h` | 43 | 9.9% |
| `w2_spring_aligned_15m` | 8 | 1.8% |
| `w2_spring_aligned_30m` | 23 | 5.3% |
| `w2_spring_aligned_1h` | 16 | 3.7% |
| `w3_upthrust_aligned_15m` | 14 | 3.2% |
| `w3_upthrust_aligned_30m` | 29 | 6.7% |
| `w3_upthrust_aligned_1h` | 32 | 7.4% |
| `w4_sos_aligned_15m` | 165 | 37.9% |
| `w4_sos_aligned_30m` | 149 | 34.3% |
| `w4_sos_aligned_1h` | 91 | 20.9% |
| `w4_sow_aligned_15m` | 193 | 44.4% |
| `w4_sow_aligned_30m` | 166 | 38.2% |
| `w4_sow_aligned_1h` | 106 | 24.4% |
| `w4_opposed_15m` | 233 | 53.6% |
| `w4_opposed_30m` | 184 | 42.3% |
| `w4_opposed_1h` | 92 | 21.1% |
| `w5_lps_aligned_15m` | 59 | 13.6% |
| `w5_lps_aligned_30m` | 39 | 9.0% |
| `w5_lps_aligned_1h` | 12 | 2.8% |
| `w5_lpsy_aligned_15m` | 83 | 19.1% |
| `w5_lpsy_aligned_30m` | 46 | 10.6% |
| `w5_lpsy_aligned_1h` | 21 | 4.8% |
| `w6_failedbrk_aligned_15m` | 1 | 0.2% |
| `w6_failedbrk_aligned_30m` | 10 | 2.3% |
| `w6_failedbrk_aligned_1h` | 19 | 4.4% |
| `w6_failedbrk_opposed_15m` | 19 | 4.4% |
| `w6_failedbrk_opposed_30m` | 18 | 4.1% |
| `w6_failedbrk_opposed_1h` | 7 | 1.6% |
| `w7_absorption_aligned_15m` | 0 | 0.0% |
| `w7_absorption_aligned_30m` | 5 | 1.1% |
| `w7_absorption_aligned_1h` | 20 | 4.6% |
| `w8_chop_15m` | 0 | 0.0% |
| `w8_chop_30m` | 0 | 0.0% |
| `w8_chop_1h` | 0 | 0.0% |
| `w9_accum_15m` | 312 | 71.7% |
| `w9_accum_30m` | 268 | 61.6% |
| `w9_accum_1h` | 148 | 34.0% |
| `w9_dist_15m` | 83 | 19.1% |
| `w9_dist_30m` | 106 | 24.4% |
| `w9_dist_1h` | 99 | 22.8% |
| `w9_markup_15m` | 0 | 0.0% |
| `w9_markup_30m` | 2 | 0.5% |
| `w9_markup_1h` | 41 | 9.4% |
| `w9_markdown_15m` | 1 | 0.2% |
| `w9_markdown_30m` | 0 | 0.0% |
| `w9_markdown_1h` | 30 | 6.9% |
| `w9_none_15m` | 39 | 9.0% |
| `w9_none_30m` | 59 | 13.6% |
| `w9_none_1h` | 117 | 26.9% |
| `w9_opposed_15m` | 165 | 37.9% |
| `w9_opposed_30m` | 135 | 31.0% |
| `w9_opposed_1h` | 65 | 14.9% |

## Top-5 KEEP filters (by totR; full table in 04/05 CSVs)
| tag | n | WR | PF | expR | totR | removed WR | pass@10/1200 | E$@10/1200 | pass@15/1000 | E$@15/1000 | auditor? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| w1_inrange_30m | 433 | 58.7% | 2.316 | 0.4249 | +184.0 | 50.0% | 48.7% | 5,881 | 55.6% | 6,506 | no |
| w1_inrange_15m | 434 | 58.5% | 2.296 | 0.4204 | +182.4 | 100.0% | 47.0% | 5,664 | 53.8% | 6,296 | no |
| w1_inrange_1h | 364 | 59.3% | 2.272 | 0.4226 | +153.8 | 54.9% | 43.8% | 5,432 | 51.4% | 6,189 | no |
| w9_accum_15m | 312 | 58.0% | 2.255 | 0.407 | +127.0 | 60.2% | 31.7% | 3,862 | 39.5% | 4,741 | no |
| w4_opposed_15m | 233 | 60.9% | 2.568 | 0.4777 | +111.3 | 55.9% | 25.0% | 3,028 | 33.8% | 2,964 | no |

## Top-5 AVOID filters (by totR — drop trades where tag==True)
| tag | n | WR | PF | expR | totR | removed(dropped) WR | pass@10/1200 | E$@10/1200 | pass@15/1000 | E$@15/1000 | auditor? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| w7_absorption_aligned_30m | 430 | 59.1% | 2.347 | 0.4315 | +185.5 | 20.0% | 47.8% | 6,017 | 55.0% | 6,622 | no |
| w6_failedbrk_opposed_1h | 428 | 59.1% | 2.345 | 0.432 | +184.9 | 28.6% | 48.2% | 6,098 | 55.6% | 6,668 | no |
| w2_spring_aligned_15m | 427 | 59.0% | 2.36 | 0.4322 | +184.5 | 37.5% | 47.3% | 5,951 | 55.0% | 6,827 | no |
| w6_failedbrk_aligned_1h | 416 | 59.4% | 2.385 | 0.443 | +184.3 | 42.1% | 48.7% | 6,240 | 55.8% | 6,947 | no |
| w7_absorption_aligned_1h | 415 | 59.5% | 2.401 | 0.444 | +184.2 | 40.0% | 47.5% | 6,004 | 55.4% | 6,857 | no |

**All-fail-if-so check (KEEP):** At least one keep-filter raised raw totR (see preregistered check).
**All-fail-if-so check (AVOID):** At least one avoid-filter raised raw totR (see preregistered check).

### Top combinations
| combo | dir | n | WR | PF | expR | totR | pass@10/1200 | E$@10/1200 | pass@15/1000 | E$@15/1000 | auditor? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| w1_inrange_30m+w1_inrange_15m | keep | 432 | 58.6% | 2.305 | 0.4224 | +182.5 | 47.6% | 5,740 | 54.7% | 6,402 | no |
| w1_inrange_30m+w1_inrange_1h | keep | 364 | 59.3% | 2.272 | 0.4226 | +153.8 | 43.8% | 5,432 | 51.4% | 6,189 | no |
| w1_inrange_15m+w1_inrange_1h | keep | 363 | 59.2% | 2.259 | 0.4196 | +152.3 | 43.3% | 5,372 | 50.9% | 6,134 | no |
| w1_inrange_30m+w1_inrange_15m+w1_inrange_1h | keep | 363 | 59.2% | 2.259 | 0.4196 | +152.3 | 43.3% | 5,372 | 50.9% | 6,134 | no |
| AVOID w7_absorption_aligned_30m+w6_failedbrk_opposed_1h+w2_spring_aligned_15m | avoid | 415 | 60.0% | 2.447 | 0.4508 | +187.1 | 47.8% | 6,017 | 54.9% | 6,871 | no |
| AVOID w7_absorption_aligned_30m+w6_failedbrk_opposed_1h | avoid | 423 | 59.6% | 2.388 | 0.4408 | +186.5 | 48.5% | 6,144 | 55.7% | 6,877 | no |
| AVOID w7_absorption_aligned_30m+w2_spring_aligned_15m | avoid | 422 | 59.5% | 2.404 | 0.4411 | +186.1 | 47.3% | 5,931 | 54.5% | 6,685 | no |
| AVOID w6_failedbrk_opposed_1h+w2_spring_aligned_15m | avoid | 420 | 59.5% | 2.402 | 0.4417 | +185.5 | 47.5% | 5,982 | 55.1% | 6,981 | no |

## Preregistered check: 'no filter raises total R' (6 replications, by tag family, KEEP direction)
- **in_range_trend**: best=w1_inrange_30m totR=+184.0 vs baseline +183.9 -> HYPOTHESIS FALSIFIED (raw totR)
- **spring_upthrust**: best=w2_spring_aligned_30m totR=+10.4 vs baseline +183.9 -> holds
- **sos_sow_lps**: best=w4_opposed_15m totR=+111.3 vs baseline +183.9 -> holds
- **failed_breakout**: best=w6_failedbrk_opposed_15m totR=+10.5 vs baseline +183.9 -> holds
- **absorption**: best=w7_absorption_aligned_15m totR=+0.0 vs baseline +183.9 -> holds
- **chop_phase**: best=w9_accum_15m totR=+127.0 vs baseline +183.9 -> holds
- **regime classification (w9 accum/dist/markup/markdown) all dead**: best=w9_accum_15m totR=+127.0 vs baseline +183.9 -> holds

## The AVOID question: does dropping CHOP / opposed-phase trades raise E$/attempt?
### CHOP (W10) avoidance
| tag | n dropped | removed WR | totR | pass@10/1200 (Δ vs base) | E$@10/1200 (Δ) | pass@15/1000 (Δ) | E$@15/1000 (Δ) |
|---|---|---|---|---|---|---|---|
| w8_chop_15m | 0 | None% | +183.9 | 47.8% (+0.0pp) | 5,773 (+0) | 55.2% (+0.0pp) | 6,459 (+0) |
| w8_chop_30m | 0 | None% | +183.9 | 47.8% (+0.0pp) | 5,773 (+0) | 55.2% (+0.0pp) | 6,459 (+0) |
| w8_chop_1h | 0 | None% | +183.9 | 47.8% (+0.0pp) | 5,773 (+0) | 55.2% (+0.0pp) | 6,459 (+0) |
### Opposed-phase (w9_opposed) avoidance
| tag | n dropped | removed WR | totR | pass@10/1200 (Δ vs base) | E$@10/1200 (Δ) | pass@15/1000 (Δ) | E$@15/1000 (Δ) |
|---|---|---|---|---|---|---|---|
| w9_opposed_15m | 165 | 58.2% | +115.2 | 31.0% (-16.8pp) | 3,598 (-2,175) | 34.3% (-20.9pp) | 3,822 (-2,637) |
| w9_opposed_30m | 135 | 57.0% | +133.0 | 35.6% (-12.2pp) | 4,514 (-1,259) | 36.3% (-18.9pp) | 4,285 (-2,174) |
| w9_opposed_1h | 65 | 56.9% | +155.9 | 41.7% (-6.1pp) | 5,110 (-663) | 45.0% (-10.2pp) | 5,527 (-932) |

## B5 — D1c complement-vs-duplicate
**Verdict: COMPLEMENT (tags largely independent of D1c keep/reject)**

| tag | n11 (tag&kept) | n10 (tag&dropped) | n01 (notag&kept) | n00 (notag&dropped) | phi | overlap(tag->kept)% |
|---|---|---|---|---|---|---|
| w1_inrange_15m | 434 | 270 | 1 | 0 | -0.03 | 61.6 |
| w1_inrange_30m | 433 | 270 | 2 | 0 | -0.042 | 61.6 |
| w1_inrange_1h | 364 | 228 | 71 | 42 | -0.01 | 61.5 |
| w1_trend_aligned_15m | 1 | 0 | 434 | 270 | 0.03 | 100.0 |
| w1_trend_aligned_30m | 0 | 0 | 435 | 270 | None | 0.0 |
| w1_trend_aligned_1h | 28 | 18 | 407 | 252 | -0.005 | 60.9 |
| w1_trend_opposed_15m | 0 | 0 | 435 | 270 | None | 0.0 |
| w1_trend_opposed_30m | 2 | 0 | 433 | 270 | 0.042 | 100.0 |
| w1_trend_opposed_1h | 43 | 24 | 392 | 246 | 0.017 | 64.2 |
| w2_spring_aligned_15m | 8 | 8 | 427 | 262 | -0.037 | 50.0 |
| w2_spring_aligned_30m | 23 | 27 | 412 | 243 | -0.089 | 46.0 |
| w2_spring_aligned_1h | 16 | 19 | 419 | 251 | -0.075 | 45.7 |
| w3_upthrust_aligned_15m | 14 | 17 | 421 | 253 | -0.073 | 45.2 |
| w3_upthrust_aligned_30m | 29 | 34 | 406 | 236 | -0.101 | 46.0 |
| w3_upthrust_aligned_1h | 32 | 37 | 403 | 233 | -0.104 | 46.4 |
| w4_sos_aligned_15m | 165 | 87 | 270 | 183 | 0.058 | 65.5 |
| w4_sos_aligned_30m | 149 | 80 | 286 | 190 | 0.048 | 65.1 |
| w4_sos_aligned_1h | 91 | 43 | 344 | 227 | 0.062 | 67.9 |
| w4_sow_aligned_15m | 193 | 128 | 242 | 142 | -0.03 | 60.1 |
| w4_sow_aligned_30m | 166 | 106 | 269 | 164 | -0.011 | 61.0 |
| w4_sow_aligned_1h | 106 | 65 | 329 | 205 | 0.003 | 62.0 |
| w4_opposed_15m | 233 | 171 | 202 | 99 | -0.096 | 57.7 |
| w4_opposed_30m | 184 | 131 | 251 | 139 | -0.061 | 58.4 |
| w4_opposed_1h | 92 | 64 | 343 | 206 | -0.03 | 59.0 |
| w5_lps_aligned_15m | 59 | 16 | 376 | 254 | 0.12 | 78.7 |
| w5_lps_aligned_30m | 39 | 10 | 396 | 260 | 0.101 | 79.6 |
| w5_lps_aligned_1h | 12 | 2 | 423 | 268 | 0.07 | 85.7 |
| w5_lpsy_aligned_15m | 83 | 26 | 352 | 244 | 0.127 | 76.1 |
| w5_lpsy_aligned_30m | 46 | 16 | 389 | 254 | 0.08 | 74.2 |
| w5_lpsy_aligned_1h | 21 | 5 | 414 | 265 | 0.077 | 80.8 |
| w6_failedbrk_aligned_15m | 1 | 2 | 434 | 268 | -0.038 | 33.3 |
| w6_failedbrk_aligned_30m | 10 | 17 | 425 | 253 | -0.101 | 37.0 |
| w6_failedbrk_aligned_1h | 19 | 34 | 416 | 236 | -0.152 | 35.8 |
| w6_failedbrk_opposed_15m | 19 | 11 | 416 | 259 | 0.007 | 63.3 |
| w6_failedbrk_opposed_30m | 18 | 8 | 417 | 262 | 0.03 | 69.2 |
| w6_failedbrk_opposed_1h | 7 | 4 | 428 | 266 | 0.005 | 63.6 |
| w7_absorption_aligned_15m | 0 | 0 | 435 | 270 | None | 0.0 |
| w7_absorption_aligned_30m | 5 | 2 | 430 | 268 | 0.02 | 71.4 |
| w7_absorption_aligned_1h | 20 | 20 | 415 | 250 | -0.059 | 50.0 |
| w8_chop_15m | 0 | 0 | 435 | 270 | None | 0.0 |
| w8_chop_30m | 0 | 0 | 435 | 270 | None | 0.0 |
| w8_chop_1h | 0 | 0 | 435 | 270 | None | 0.0 |
| w9_accum_15m | 312 | 202 | 123 | 68 | -0.034 | 60.7 |
| w9_accum_30m | 268 | 182 | 167 | 88 | -0.059 | 59.6 |
| w9_accum_1h | 148 | 91 | 287 | 179 | 0.003 | 61.9 |
| w9_dist_15m | 83 | 45 | 352 | 225 | 0.03 | 64.8 |
| w9_dist_30m | 106 | 54 | 329 | 216 | 0.051 | 66.2 |
| w9_dist_1h | 99 | 62 | 336 | 208 | -0.002 | 61.5 |
| w9_markup_15m | 0 | 0 | 435 | 270 | None | 0.0 |
| w9_markup_30m | 2 | 0 | 433 | 270 | 0.042 | 100.0 |
| w9_markup_1h | 41 | 20 | 394 | 250 | 0.035 | 67.2 |
| w9_markdown_15m | 1 | 0 | 434 | 270 | 0.03 | 100.0 |
| w9_markdown_30m | 0 | 0 | 435 | 270 | None | 0.0 |
| w9_markdown_1h | 30 | 22 | 405 | 248 | -0.023 | 57.7 |
| w9_none_15m | 39 | 23 | 396 | 247 | 0.008 | 62.9 |
| w9_none_30m | 59 | 34 | 376 | 236 | 0.014 | 63.4 |
| w9_none_1h | 117 | 75 | 318 | 195 | -0.01 | 60.9 |
| w9_opposed_15m | 165 | 126 | 270 | 144 | -0.086 | 56.7 |
| w9_opposed_30m | 135 | 100 | 300 | 170 | -0.062 | 57.4 |
| w9_opposed_1h | 65 | 40 | 370 | 230 | 0.002 | 61.9 |

## Per-year robustness flags
- **best_keep(w1_inrange_30m)**: none
- **best_avoid(w7_absorption_aligned_30m)**: none
- **avoid(w8_chop_15m)**: none
- **avoid(w9_opposed_15m)**: none
- **avoid(w8_chop_30m)**: none
- **avoid(w9_opposed_30m)**: none
- **avoid(w8_chop_1h)**: none
- **avoid(w9_opposed_1h)**: none

## Auditor-review-required rows (pass beats baseline by >1pp at either base)
- AVOID:w9_markdown_1h

## Auditor follow-up: w9_markdown_1h avoid, per-year funnel

Requested by auditor review of the previously flagged row `AVOID:w9_markdown_1h` — prior against it: structurally an HTF(1h)-phase-classification skip (ticket Z already invalidated HTF-alignment skips as a lever), and it removes a NET-POSITIVE removed cohort while raising pass% (sequencing-effect smell).

Baseline n=435 trades; avoid-stream (drop `w9_markdown_1h`==True) n=405 trades (30 removed, removed-cohort totR = +9.0R — i.e. the removed cohort was net PROFITABLE, consistent with the auditor's smell-test).

### Base (cap10, $1200)
| start-year | n (baseline) | pass% (baseline) | n (avoid) | pass% (avoid) | delta (pp) |
|---|---|---|---|---|---|
| 2021 | 45 | 51.1% | 42 | 52.4% | +1.3 |
| 2022 | 70 | 38.6% | 64 | 42.2% | +3.6 |
| 2023 | 89 | 52.8% | 84 | 52.4% | -0.4 |
| 2024 | 74 | 35.1% | 68 | 26.5% | -8.6 |
| 2025 | 89 | 62.9% | 84 | 71.4% | +8.5 |
| 2026 | 28 | 35.7% | 25 | 36.0% | +0.3 |
- net gain in passing eval-starts = -9 (RAW pass count) -> **CONCENTRATED** — top-2 years [(2025, 4)] account for 100% of the positive-year gain
- total eligible eval-starts: baseline=395 avoid=367 (shrank by 28)
- **DENOMINATOR ARTIFACT**: the RAW number of passing eval-starts fell by 9, but pass% still rose because the total pool of eligible eval-starts shrank by 28 (fewer trading days remain within the 30-day-expiry start window once these trades are dropped). **This is not a genuine pass-rate lift — it is exactly the sequencing-effect the auditor flagged.**

### Base (cap15, $1000)
| start-year | n (baseline) | pass% (baseline) | n (avoid) | pass% (avoid) | delta (pp) |
|---|---|---|---|---|---|
| 2021 | 45 | 57.8% | 42 | 61.9% | +4.1 |
| 2022 | 70 | 48.6% | 64 | 51.6% | +3.0 |
| 2023 | 89 | 66.3% | 84 | 69.0% | +2.7 |
| 2024 | 74 | 36.5% | 68 | 36.8% | +0.3 |
| 2025 | 89 | 66.3% | 84 | 73.8% | +7.5 |
| 2026 | 28 | 46.4% | 25 | 44.0% | -2.4 |
- net gain in passing eval-starts = -3 (RAW pass count) -> **CONCENTRATED** — top-2 years [(2025, 3)] account for 100% of the positive-year gain
- total eligible eval-starts: baseline=395 avoid=367 (shrank by 28)
- **DENOMINATOR ARTIFACT**: the RAW number of passing eval-starts fell by 3, but pass% still rose because the total pool of eligible eval-starts shrank by 28 (fewer trading days remain within the 30-day-expiry start window once these trades are dropped). **This is not a genuine pass-rate lift — it is exactly the sequencing-effect the auditor flagged.**

### Removed cohort (w9_markdown_1h==True, n=30) — distribution by year x side
| year | long n (R) | short n (R) |
|---|---|---|
| 2021 | 2 (+0.5R) | 1 (+1.5R) |
| 2022 | 4 (-0.5R) | 2 (+1.0R) |
| 2023 | 1 (+1.5R) | 4 (-0.6R) |
| 2024 | 1 (+1.5R) | 5 (+3.5R) |
| 2025 | 2 (-1.6R) | 3 (+1.6R) |
| 2026 | 1 (+0.9R) | 4 (-0.2R) |

**"Drop 2024 longs in disguise" check**: NO — largest single (year,side) cell is 2024 short at 5/30 (17%), not a majority.

## Firewall
`test_eval_config_firewall.py` + `test_funded_config_firewall.py` run before and after this workstream — pass/fail state identical (no existing file touched).

---
All numbers above: RESEARCH ONLY / SIM CONDITIONAL. No commits. Profile A live machine unchanged.
