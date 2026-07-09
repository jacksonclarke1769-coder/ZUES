# 09 — Day-sequence baseline (SMC3 NY-AM 09:30-12:00 ET)

Reproduced from `smc3_engine.run_backtest(Config(useSession=True, sessStart="09:30", sessEnd="12:00"))`,
filtered to `reason in {target, stop}`. Matches spec exactly: n=1624, WR 35.5%,
PF($) 1.119, totR +67.7, avgR +0.042, ex-2024 avgR -0.008, IS +0.042 / OOS +0.041.

## Headline
| metric | value |
|---|---|
| n (closed trades) | 1624 |
| trading days | 961 |
| trades/day | 1.69 |
| WR | 35.5% |
| PF(R) | 1.063 (PF($) 1.119 per spec baseline) |
| avgR | +0.042 |
| totR | +67.7 |
| maxDD(R) | -45.2 |

## Per-year R
| year | n | WR% | avgR | totR |
|---|---|---|---|---|
| 2021 | 158 | 34.2 | -0.005 | -0.8 |
| 2022 | 345 | 33.9 | -0.003 | -1.0 |
| 2023 | 322 | 31.4 | -0.086 | -27.7 |
| 2024 | 323 | 42.1 | +0.240 | +77.6 |
| 2025 | 319 | 36.4 | +0.072 | +22.8 |
| 2026 | 157 | 33.1 | -0.021 | -3.3 |

ex-2024 avgR = **-0.008** (n=1301, totR -9.9) — confirms 2024 alone carries the entire edge.
ex-Friday avgR = **+0.026** (n=1302, totR +33.6).

## Trades-per-day bucket diagnostic (the Jun-29 hypothesis)

**Trade-level** (avgR per trade, grouped by how many trades fired that day):
| bucket | n trades | WR% | avgR | totR |
|---|---|---|---|---|
| 1 trade/day | 469 | 36.5 | +0.071 | +33.1 |
| 2 trades/day | 694 | 35.3 | +0.037 | +25.7 |
| 3 trades/day | 366 | 34.7 | +0.019 | +6.9 |
| 4+ trades/day | 95 | 34.7 | +0.021 | +2.0 |

**Day-level** (per-day total R and day-winrate, grouped by trades-that-day):
| bucket | days | day-WR% | avg day R |
|---|---|---|---|
| 1 trade/day | 469 | 36.5 | +0.071 |
| 2 trades/day | 347 | 55.9 | +0.074 |
| 3 trades/day | 122 | 28.7 | +0.056 |
| 4+ trades/day | 23 | 47.8 | +0.089 |

**Reading**: NOT a clean "multi-trade days bleed" story. Trade-level avgR does decay
monotonically from 1-trade days (+0.071) down to 3-trade days (+0.019), but 4+ days
tick back up slightly. At the day level, 2-trade days are actually the BEST bucket
(day-WR 55.9%, avg day R +0.074) — better than 1-trade days. The worst bucket by
day-WR is 3-trade days (28.7%), not the largest (4+) bucket. So the bleed is not
uniformly "more trades = worse" — it is concentrated specifically in 3-trade days,
with 2-trade days actually pulling their weight. This partially supports and
partially contradicts a naive "cap trades/day" hypothesis (see filter battery,
`A.max_trades_2` underperforms `A.max_trades_3` on ex-2024 in the actual causal
replay because dropping trade #3 removes some of its (mixed) R along with skipping
the worst bucket).

## Worst/best 10 days (context for filter battery flags)
Worst 5 days by R: 2022-09-21 (-4.15), 2023-05-01 (-4.14), 2022-11-14 (-4.08),
2024-03-28 (-3.14), 2023-12-29 (-3.12).
Best 5 days by R: 2026-02-11 (+5.97), 2024-09-05 (+5.96), 2024-06-28 (+5.95),
2022-04-28 (+5.95), 2024-10-21 (+5.95).
