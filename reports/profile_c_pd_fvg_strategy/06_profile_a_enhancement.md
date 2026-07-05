# Profile C — Workstream B: PD-array / FVG / SMT filters on the FROZEN Profile A stream

**RESEARCH ONLY / SIM CONDITIONAL.** Profile A model is FROZEN; this is tag-and-measure only.
No entry replacement tested (register: fvg50-entry lane already killed, PF 1.46 vs 1.78, chasing -30R).

Base stream: 435 certified trades (exit3 + D1c, 1m-truth) reconstructed via the exact `tools_sim_parity_check.load_rows()` code path and asserted byte-for-byte identical to it (ts/R/mae_r/risk_usd). Pre-D1c raw signal set: 705 (ny_am session, post model01, pre-D1c-drop).
Baseline totR = +183.9R (register: +183.9R).

## Canary (mandatory, blocking)
- @(cap10,$1200): pass=47.8 bust=15.9 exp=36.2 med=16d n=395 — expected 47.8/15.9/36.2/med16/n395 -> MATCH
- @(cap15,$1000): pass=55.2 bust=13.4 exp=31.4 med=15d n=395

## Annotation coverage (of 435 kept)
- `b1_fvg_h1_in`: 0/435 (0.0%)
- `b1_fvg_h1_near`: 0/435 (0.0%)
- `b1_fvg_h4_in`: 0/435 (0.0%)
- `b1_fvg_h4_near`: 11/435 (2.5%)
- `b1_fvg_d1_in`: 7/435 (1.6%)
- `b1_fvg_d1_near`: 14/435 (3.2%)
- `b1_pdhl_10`: 52/435 (12.0%)
- `b1_pdhl_20`: 94/435 (21.6%)
- `b1_h1swing_10`: 74/435 (17.0%)
- `b1_h1swing_20`: 115/435 (26.4%)
- `b2_disp_fvg_confirm`: 37/435 (8.5%)
- `b3_ote_fvg_confluence`: 121/435 (27.8%)
- `b4_smt_es`: 38/435 (8.7%)
- `b4_smt_ym`: 38/435 (8.7%)
- `b4_smt_rty`: 38/435 (8.7%)
- SMT testability: ES 435/435, YM 435/435, RTY 435/435

## Filter table (top 5 by totR, full table in 08/09 CSVs)
| filter | n | WR | PF | expR | totR | removed WR | pass@10/1200 | E$@10/1200 | pass@15/1000 | E$@15/1000 | auditor? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| b3_ote_fvg_confluence | 121 | 58.7% | 2.278 | 0.4235 | +51.2 | 58.6% | 19.8% | 639 | 16.4% | 1,219 | no |
| b1_h1swing_20 | 115 | 53.9% | 1.808 | 0.3201 | +36.8 | 60.3% | 7.5% | 508 | 10.3% | 442 | no |
| b1_pdhl_20 | 94 | 46.8% | 1.481 | 0.1988 | +18.7 | 61.9% | 5.5% | 136 | 6.6% | 122 | no |
| b1_h1swing_10 | 74 | 51.4% | 1.561 | 0.2502 | +18.5 | 60.1% | 5.9% | 199 | 7.4% | 243 | no |
| b4_smt_ym | 38 | 60.5% | 2.297 | 0.453 | +17.2 | 58.4% | 2.9% | 54 | 2.9% | 52 | no |

**All-fail-if-so check:** ALL individual filters have totR <= baseline — no filter wins on raw totR.

### Top combinations
| combo | n | WR | PF | expR | totR | pass@10/1200 | E$@10/1200 | pass@15/1000 | E$@15/1000 | auditor? |
|---|---|---|---|---|---|---|---|---|---|---|
| b3_ote_fvg_confluence+b1_h1swing_20 | 24 | 70.8% | 3.437 | 0.6385 | +15.3 | 0.0% | -68 | 0.0% | -68 | no |
| b3_ote_fvg_confluence+b1_pdhl_20 | 29 | 48.3% | 1.776 | 0.2812 | +8.2 | 7.1% | 22 | 3.6% | -42 | no |
| b3_ote_fvg_confluence+b1_h1swing_20+b1_pdhl_20 | 7 | 71.4% | 2.376 | 0.438 | +3.1 | 0.0% | -68 | 0.0% | -68 | no |
| b1_h1swing_20+b1_pdhl_20 | 27 | 44.4% | 1.054 | 0.0276 | +0.7 | 0.0% | -68 | 0.0% | -68 | no |

## Preregistered check: 'no filter raises total R' (3 replications, by tag family)
- **pd_zone**: best=b1_h1swing_20 totR=+36.8 vs baseline +183.9 -> holds
- **b2**: best=b2_disp_fvg_confirm totR=+12.6 vs baseline +183.9 -> holds
- **b3**: best=b3_ote_fvg_confluence totR=+51.2 vs baseline +183.9 -> holds

## SMT testability verdict
- ES (primary): 435/435 testable
- YM / RTY (secondary): 435/435, 435/435
- 'Testable' requires the matched (ffilled) other-instrument bar within 15min of the NQ sweep bar and full 20-bar-lookback coverage; trades outside an instrument's data range are marked not-testable rather than silently reusing a stale value.

## B5 — D1c complement-vs-duplicate
**Verdict: COMPLEMENT (tags largely independent of D1c keep/reject)**

| tag | n11 (tag&kept) | n10 (tag&dropped) | n01 (notag&kept) | n00 (notag&dropped) | phi | overlap(tag->kept)% |
|---|---|---|---|---|---|---|
| b1_fvg_h1_in | 0 | 0 | 435 | 270 | None | 0.0 |
| b1_fvg_h1_near | 0 | 0 | 435 | 270 | None | 0.0 |
| b1_fvg_h4_in | 0 | 3 | 435 | 267 | -0.083 | 0.0 |
| b1_fvg_h4_near | 11 | 9 | 424 | 261 | -0.024 | 55.0 |
| b1_fvg_d1_in | 7 | 5 | 428 | 265 | -0.009 | 58.3 |
| b1_fvg_d1_near | 14 | 13 | 421 | 257 | -0.04 | 51.9 |
| b1_pdhl_10 | 52 | 35 | 383 | 235 | -0.015 | 59.8 |
| b1_pdhl_20 | 94 | 66 | 341 | 204 | -0.033 | 58.8 |
| b1_h1swing_10 | 74 | 43 | 361 | 227 | 0.014 | 63.2 |
| b1_h1swing_20 | 115 | 75 | 320 | 195 | -0.015 | 60.5 |
| b2_disp_fvg_confirm | 37 | 26 | 398 | 244 | -0.019 | 58.7 |
| b3_ote_fvg_confluence | 121 | 66 | 314 | 204 | 0.037 | 64.7 |
| b4_smt_es | 38 | 31 | 397 | 239 | -0.045 | 55.1 |
| b4_smt_ym | 38 | 42 | 397 | 228 | -0.105 | 47.5 |
| b4_smt_rty | 38 | 43 | 397 | 227 | -0.11 | 46.9 |

## Firewall
See harness stdout (`test_eval_config_firewall.py` + `test_funded_config_firewall.py` run before and after this workstream) — pass/fail state must be identical (no existing file touched).

---
All numbers above: RESEARCH ONLY / SIM CONDITIONAL. No commits. Profile A live machine unchanged.
