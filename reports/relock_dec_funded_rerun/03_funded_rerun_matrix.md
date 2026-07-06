# 03 -- Funded Re-Run Matrix (RE-LOCK DEC + Funded Re-Run)

RESEARCH ONLY. LIVE HOLD ACTIVE. Uses ONLY the repo's implemented funded/payout rules (`apex_funded_40.py` / `tools_recert_funded.py`, imported not retyped): PA ladder [1500,1500,2000,2500,2500,3000], CLOSED_MAX, safety net (LOCK_EOD reach), $1,000 DLL, $550 daily stop, 0.50 consistency, 30-day payout-sweep cycle.

OVERLAP CAVEAT (verbatim): monthly rolling starts OVERLAP -> effective independent samples ~4-5, bust% has wide CI

Grid: A-kept [(150, 2), (200, 3), (250, 4), (300, 4), (400, 4), (480, 4)] x VPC ['OFF', (100, 1), (150, 1), (200, 2), (250, 2), (300, 2)] = 36 cells; A-unfiltered [(250, 4), (300, 4)] x VPC ['OFF', (200, 2)] = 4 cells; +1 negative control (eval-style A900/6+VPC600/3 run through the funded simulator).

## Top-10 by E[paid]
| label | n | E[paid] | med paid | mean paid | med mo | mean mo | bust% | SN% | med SN day | 1st-payout% | 2nd-payout% | full-ladder% | maxDD med | maxDD worst | worst yr (bust%) | trades/mo | risk/mo | A-vs-VPC coactive r (n) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A@250/4+VPC@300/2 | 42 | $10,291 | $12,232 | $10,291 | 26.5 | 25.0 | 14.3 | 100.0 | 130.0 | 100.0 | 92.9 | 73.8 | $3,548 | $6,265 | 2025 (33.3%) | 15.39 | $3,072 | 0.33 (n=135) |
| A@480/4+VPC@100/1 | 42 | $9,308 | $11,883 | $9,308 | 17.8 | 20.3 | 23.8 | 85.7 | 163.5 | 85.7 | 76.2 | 73.8 | $3,432 | $4,149 | 2023 (75.0%) | 10.02 | $2,942 | -0.333 (n=11) |
| A@480/4+VPC@150/1 | 42 | $9,161 | $12,336 | $9,161 | 16.1 | 18.7 | 28.6 | 85.7 | 129.5 | 85.7 | 71.4 | 71.4 | $3,009 | $5,236 | 2023 (66.7%) | 11.69 | $3,157 | 0.297 (n=48) |
| A@300/4+VPC@150/1 | 42 | $8,974 | $9,347 | $8,974 | 24.2 | 25.8 | 2.4 | 100.0 | 205.5 | 100.0 | 97.6 | 83.3 | $3,365 | $4,102 | 2022 (8.3%) | 11.42 | $2,292 | 0.261 (n=48) |
| A@200/3+VPC@300/2 | 42 | $8,729 | $10,000 | $8,729 | 30.0 | 29.1 | 7.1 | 100.0 | 167.5 | 100.0 | 92.9 | 38.1 | $3,717 | $4,199 | 2023 (25.0%) | 14.99 | $2,654 | 0.339 (n=128) |
| A@400/4+VPC@200/2 | 42 | $8,715 | $11,895 | $8,715 | 18.2 | 19.5 | 31.0 | 85.7 | 124.0 | 83.3 | 73.8 | 64.3 | $3,808 | $5,242 | 2023 (66.7%) | 13.43 | $3,157 | 0.333 (n=80) |
| A@480/4+VPC@200/2 | 42 | $8,689 | $12,319 | $8,689 | 16.7 | 18.1 | 35.7 | 85.7 | 120.0 | 81.0 | 71.4 | 64.3 | $3,470 | $4,965 | 2023 (83.3%) | 13.5 | $3,506 | 0.305 (n=80) |
| A@250/4+VPC@200/2 | 42 | $8,622 | $8,918 | $8,622 | 27.5 | 26.6 | 2.4 | 100.0 | 217.0 | 100.0 | 100.0 | 71.4 | $3,304 | $4,780 | 2022 (8.3%) | 12.92 | $2,258 | 0.25 (n=79) |
| A@400/4+VPC@300/2 | 42 | $8,595 | $12,132 | $8,595 | 16.1 | 18.9 | 33.3 | 88.1 | 101.0 | 85.7 | 71.4 | 59.5 | $3,791 | $5,881 | 2023 (83.3%) | 15.89 | $3,972 | 0.407 (n=143) |
| A@300/4+VPC@100/1 | 42 | $8,525 | $8,890 | $8,525 | 28.6 | 28.1 | 2.4 | 100.0 | 244.5 | 100.0 | 97.6 | 85.7 | $3,018 | $4,040 | 2023 (8.3%) | 9.76 | $2,076 | -0.329 (n=11) |

## Negative control (eval-style A900/6+VPC600/3 through the FUNDED simulator)
| label | n | E[paid] | med paid | mean paid | med mo | mean mo | bust% | SN% | med SN day | 1st-payout% | 2nd-payout% | full-ladder% | maxDD med | maxDD worst | worst yr (bust%) | trades/mo | risk/mo | A-vs-VPC coactive r (n) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NEGATIVE CONTROL A@900/6+VPC@600/3 (eval-style thru funded sim) | 42 | $5,977 | $1,499 | $5,977 | 3.9 | 11.4 | 54.8 | 64.3 | 34.0 | 54.8 | 45.2 | 45.2 | $4,044 | $5,855 | 2023 (58.3%) | 17.12 | $8,362 | 0.385 (n=173) |

No winner-picking.
