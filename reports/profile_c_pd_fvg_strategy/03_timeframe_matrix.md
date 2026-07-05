# Profile C (PD/FVG) — Timeframe x Session Matrix

NOTE: distinct from the pre-existing `profileC_*` gap-fill research lineage.

Data span: 646.9 weeks. Full grid runtime: 318.5s. Total runtime incl. canary + Profile A load: 429.7s.

## Canary results

| pd_tf | sig_tf | session | tick | disp | disc | entry | exit | poison-future | same-bar-fill | violations | baseline n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1h | 5m | ny_am | 1 | 1 | False | top | fixed2r | PASS | PASS | 0 | 243 |
| 1h | 5m | 24h | 3 | 2 | True | mid | exit3 | PASS | PASS | 0 | 813 |
| 15m | 1m | ny_am | 1 | 1 | False | top | fixed2r | PASS | PASS | 0 | 843 |
| 15m | 1m | 24h | 3 | 2 | True | mid | exit3 | PASS | PASS | 0 | 2884 |

## Profile A overlap reference: 435 trades / 405 unique trade-days

## Family-level kill-gate summary (best variant per pd_tf x sig_tf x session)

| pd_tf | sig_tf | session | status | gate fired | best PF | n | tr/wk | NY overlap % |
|---|---|---|---|---|---|---|---|---|
| 1h | 5m | ny_am | REJECTED | PF 0.82 < 1.15 | 0.82 | 196 | 0.303 |  |
| 1h | 5m | london | REJECTED | PF 0.81 < 1.15 | 0.81 | 211 | 0.326 |  |
| 1h | 5m | asia | REJECTED | PF 0.84 < 1.15 | 0.84 | 270 | 0.417 |  |
| 1h | 5m | 24h | REJECTED | PF 0.76 < 1.15 | 0.76 | 1484 | 2.294 |  |
| 1h | 15m | ny_am | REJECTED | PF 0.96 < 1.15 | 0.96 | 82 | 0.127 |  |
| 1h | 15m | london | REJECTED | PF 0.97 < 1.15 | 0.97 | 188 | 0.291 |  |
| 1h | 15m | asia | REJECTED | tr/wk 0.07 < 0.5 | 1.19 | 45 | 0.07 |  |
| 1h | 15m | 24h | REJECTED | PF 0.87 < 1.15 | 0.87 | 741 | 1.146 |  |
| 4h | 5m | ny_am | REJECTED | PF 1.10 < 1.15 | 1.1 | 105 | 0.162 |  |
| 4h | 5m | london | REJECTED | PF 1.04 < 1.15 | 1.04 | 214 | 0.331 |  |
| 4h | 5m | asia | REJECTED | PF 0.88 < 1.15 | 0.88 | 258 | 0.399 |  |
| 4h | 5m | 24h | REJECTED | PF 0.77 < 1.15 | 0.77 | 1537 | 2.376 |  |
| 4h | 15m | ny_am | REJECTED | tr/wk 0.28 < 0.5 | 1.19 | 178 | 0.275 | 13.5 |
| 4h | 15m | london | REJECTED | tr/wk 0.12 < 0.5 | 1.51 | 78 | 0.121 |  |
| 4h | 15m | asia | REJECTED | tr/wk 0.04 < 0.5 | 1.18 | 29 | 0.045 |  |
| 4h | 15m | 24h | REJECTED | PF 1.00 < 1.15 | 1.0 | 300 | 0.464 |  |
| 15m | 1m | ny_am | REJECTED | PF 0.79 < 1.15 | 0.79 | 287 | 0.444 |  |
| 15m | 1m | london | REJECTED | PF 0.56 < 1.15 | 0.56 | 1091 | 1.687 |  |
| 15m | 1m | asia | REJECTED | PF 0.63 < 1.15 | 0.63 | 714 | 1.104 |  |
| 15m | 1m | 24h | REJECTED | PF 0.62 < 1.15 | 0.62 | 5460 | 8.441 |  |
| 30m | 5m | ny_am | REJECTED | PF 0.88 < 1.15 | 0.88 | 323 | 0.499 |  |
| 30m | 5m | london | REJECTED | PF 0.88 < 1.15 | 0.88 | 379 | 0.586 |  |
| 30m | 5m | asia | REJECTED | PF 0.73 < 1.15 | 0.73 | 560 | 0.866 |  |
| 30m | 5m | 24h | REJECTED | PF 0.76 < 1.15 | 0.76 | 2652 | 4.1 |  |
| D | 5m | ny_am | REJECTED | tr/wk 0.08 < 0.5 | 1.27 | 54 | 0.083 | 11.1 |
| D | 5m | london | REJECTED | PF 0.72 < 1.15 | 0.72 | 147 | 0.227 |  |
| D | 5m | asia | REJECTED | PF 0.84 < 1.15 | 0.84 | 39 | 0.06 |  |
| D | 5m | 24h | REJECTED | PF 0.79 < 1.15 | 0.79 | 594 | 0.918 |  |
| D | 15m | ny_am | REJECTED | PF 0.82 < 1.15 | 0.82 | 82 | 0.127 |  |
| D | 15m | london | REJECTED | tr/wk 0.04 < 0.5 | 1.42 | 25 | 0.039 |  |
| D | 15m | asia | REJECTED | tr/wk 0.03 < 0.5 | 3.15 | 17 | 0.026 |  |
| D | 15m | 24h | REJECTED | PF 0.78 < 1.15 | 0.78 | 339 | 0.524 |  |

## BUG FLAGS: 4 cells with PF > 1.8 (STOPPED, not optimised further, flagged for auditor)

| pd_tf | sig_tf | session | tick | disp | disc | entry | exit | n | PF |
|---|---|---|---|---|---|---|---|---|---|
| D | 15m | asia | 1 | 2 | False | top | fixed2r | 17 | 3.15 |
| D | 15m | asia | 1 | 2 | False | top | exit3 | 17 | 2.65 |
| D | 15m | asia | 1 | 2 | False | mid | fixed2r | 15 | 2.08 |
| D | 15m | asia | 3 | 2 | False | mid | fixed2r | 12 | 2.04 |

## Full matrix (all 1024 cells): see `02_timeframe_matrix.csv`
