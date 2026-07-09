# SMC3 Stage 2 — Parameter Robustness + Trade Classification

Question: does a real, risk-normalized edge hide in any parameter config or market-context sub-region, or is SMC3 structurally breakeven?  **R (net$/(risk_pts*$20)) is the headline; $/PF($) are secondary.**  IS = 2021-24, OOS = 2025-26H1.

Data: `/Users/jacksonclarke/trading-team/data/real_futures/NQ_databento_1m_5y.parquet`  (1,769,367 1m bars, 2021-06-23 -> 2026-06-22)

Baseline (default Config): 5056 trades, WR 34.4%, PF($) 1.036, **total R -52.9, avg R -0.0105**, OOS PF 0.995.

## Task A — parameter robustness (one axis at a time around the default)

Bar for a *candidate edge region*: positive **total R in BOTH IS and OOS** AND positive **avg R in >=5 of 6 calendar years**.  `clears?` column marks any cell that meets it.

### Axis: stopMode

| cell | n | WR% | totalR | avgR | PF($) | IS n | IS totR | IS avgR | OOS n | OOS totR | OOS avgR | +yrs/tot | clears? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stopMode=Recent Swing | 5056 | 34.4 | -52.9 | -0.0105 | 1.036 | 3467 | -37.9 | -0.0109 | 1589 | -15.0 | -0.0094 | 2/6 | no |
| stopMode=Sweep Extreme | 4897 | 32.0 | -796.5 | -0.1627 | 0.954 | 3383 | -548.3 | -0.1621 | 1514 | -248.2 | -0.1639 | 0/6 | no |
| stopMode=Wider Of Both | 4543 | 34.7 | +28.8 | +0.0063 | 1.051 | 3084 | +34.9 | +0.0113 | 1459 | -6.1 | -0.0042 | 3/6 | no |

| cell | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| stopMode=Recent Swing | -0.047 | -0.019 | -0.058 | +0.066 | +0.003 | -0.034 |
| stopMode=Sweep Extreme | -0.222 | -0.129 | -0.212 | -0.116 | -0.175 | -0.142 |
| stopMode=Wider Of Both | -0.049 | +0.028 | -0.068 | +0.104 | +0.004 | -0.021 |

### Axis: rrTarget

| cell | n | WR% | totalR | avgR | PF($) | IS n | IS totR | IS avgR | OOS n | OOS totR | OOS avgR | +yrs/tot | clears? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rrTarget=1.0 | 5921 | 50.7 | -165.5 | -0.0280 | 1.003 | 4122 | -59.7 | -0.0145 | 1799 | -105.8 | -0.0588 | 1/6 | no |
| rrTarget=1.5 | 5472 | 41.1 | -78.4 | -0.0143 | 1.036 | 3782 | -32.8 | -0.0087 | 1690 | -45.7 | -0.0270 | 1/6 | no |
| rrTarget=2.0 | 5056 | 34.4 | -52.9 | -0.0105 | 1.036 | 3467 | -37.9 | -0.0109 | 1589 | -15.0 | -0.0094 | 2/6 | no |
| rrTarget=2.5 | 4574 | 29.3 | -70.9 | -0.0155 | 1.027 | 3087 | -36.6 | -0.0119 | 1487 | -34.2 | -0.0230 | 1/6 | no |
| rrTarget=3.0 | 4280 | 25.5 | -89.9 | -0.0210 | 1.038 | 2921 | -66.8 | -0.0229 | 1359 | -23.1 | -0.0170 | 3/6 | no |

| cell | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| rrTarget=1.0 | -0.086 | -0.008 | -0.046 | +0.051 | -0.068 | -0.040 |
| rrTarget=1.5 | -0.063 | -0.009 | -0.077 | +0.092 | -0.016 | -0.050 |
| rrTarget=2.0 | -0.047 | -0.019 | -0.058 | +0.066 | +0.003 | -0.034 |
| rrTarget=2.5 | -0.020 | -0.004 | -0.088 | +0.060 | -0.021 | -0.028 |
| rrTarget=3.0 | -0.101 | +0.028 | -0.117 | +0.054 | +0.009 | -0.068 |

### Axis: maxStopPoints

| cell | n | WR% | totalR | avgR | PF($) | IS n | IS totR | IS avgR | OOS n | OOS totR | OOS avgR | +yrs/tot | clears? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| maxStopPoints=40 | 5357 | 34.3 | -104.5 | -0.0195 | 0.983 | 3777 | -105.2 | -0.0278 | 1580 | +0.6 | +0.0004 | 2/6 | no |
| maxStopPoints=60 | 5351 | 34.2 | -98.0 | -0.0183 | 1.015 | 3710 | -87.7 | -0.0236 | 1641 | -10.3 | -0.0063 | 2/6 | no |
| maxStopPoints=90 | 5131 | 34.7 | -2.9 | -0.0006 | 1.056 | 3513 | -26.4 | -0.0075 | 1618 | +23.4 | +0.0145 | 3/6 | no |
| maxStopPoints=120 | 5056 | 34.4 | -52.9 | -0.0105 | 1.036 | 3467 | -37.9 | -0.0109 | 1589 | -15.0 | -0.0094 | 2/6 | no |
| maxStopPoints=150 | 5009 | 34.1 | -85.0 | -0.0170 | 1.012 | 3434 | -57.6 | -0.0168 | 1575 | -27.4 | -0.0174 | 1/6 | no |

| cell | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| maxStopPoints=40 | -0.057 | -0.051 | -0.051 | +0.038 | +0.010 | -0.020 |
| maxStopPoints=60 | -0.108 | -0.037 | -0.054 | +0.070 | +0.003 | -0.025 |
| maxStopPoints=90 | -0.051 | -0.014 | -0.053 | +0.069 | +0.016 | +0.011 |
| maxStopPoints=120 | -0.047 | -0.019 | -0.058 | +0.066 | +0.003 | -0.034 |
| maxStopPoints=150 | -0.041 | -0.027 | -0.065 | +0.058 | -0.004 | -0.046 |

### Axis: 5m_confirm

| cell | n | WR% | totalR | avgR | PF($) | IS n | IS totR | IS avgR | OOS n | OOS totR | OOS avgR | +yrs/tot | clears? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5mConfirm=BOS only | 3849 | 33.3 | -149.0 | -0.0387 | 1.018 | 2609 | -113.6 | -0.0436 | 1240 | -35.3 | -0.0285 | 1/6 | no |
| 5mConfirm=FVG only | 4803 | 34.6 | -30.5 | -0.0063 | 1.060 | 3337 | -73.1 | -0.0219 | 1466 | +42.6 | +0.0291 | 2/6 | no |
| 5mConfirm=both | 5056 | 34.4 | -52.9 | -0.0105 | 1.036 | 3467 | -37.9 | -0.0109 | 1589 | -15.0 | -0.0094 | 2/6 | no |

| cell | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 5mConfirm=BOS only | -0.108 | -0.069 | -0.096 | +0.073 | -0.038 | -0.008 |
| 5mConfirm=FVG only | -0.126 | -0.006 | -0.060 | +0.055 | +0.050 | -0.012 |
| 5mConfirm=both | -0.047 | -0.019 | -0.058 | +0.066 | +0.003 | -0.034 |

### Axis: 1m_trigger

| cell | n | WR% | totalR | avgR | PF($) | IS n | IS totR | IS avgR | OOS n | OOS totR | OOS avgR | +yrs/tot | clears? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1mTrigger=BOS only | 4762 | 34.2 | -50.1 | -0.0105 | 1.028 | 3268 | -75.7 | -0.0232 | 1494 | +25.6 | +0.0172 | 2/6 | no |
| 1mTrigger=FVG only | 4984 | 33.4 | -205.9 | -0.0413 | 0.992 | 3451 | -157.4 | -0.0456 | 1533 | -48.5 | -0.0317 | 1/6 | no |
| 1mTrigger=both | 5056 | 34.4 | -52.9 | -0.0105 | 1.036 | 3467 | -37.9 | -0.0109 | 1589 | -15.0 | -0.0094 | 2/6 | no |

| cell | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 1mTrigger=BOS only | -0.097 | -0.034 | -0.056 | +0.061 | +0.029 | -0.005 |
| 1mTrigger=FVG only | -0.060 | -0.077 | -0.097 | +0.050 | -0.034 | -0.026 |
| 1mTrigger=both | -0.047 | -0.019 | -0.058 | +0.066 | +0.003 | -0.034 |

### Axis: maxSetupBars

| cell | n | WR% | totalR | avgR | PF($) | IS n | IS totR | IS avgR | OOS n | OOS totR | OOS avgR | +yrs/tot | clears? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| maxSetupBars=60 | 4287 | 34.7 | +6.4 | +0.0015 | 1.039 | 2937 | +7.4 | +0.0025 | 1350 | -0.9 | -0.0007 | 3/6 | no |
| maxSetupBars=120 | 4867 | 34.4 | -40.9 | -0.0084 | 1.038 | 3337 | -29.8 | -0.0089 | 1530 | -11.1 | -0.0073 | 2/6 | no |
| maxSetupBars=180 | 5056 | 34.4 | -52.9 | -0.0105 | 1.036 | 3467 | -37.9 | -0.0109 | 1589 | -15.0 | -0.0094 | 2/6 | no |
| maxSetupBars=300 | 5151 | 34.2 | -81.3 | -0.0158 | 1.030 | 3539 | -63.5 | -0.0179 | 1612 | -17.8 | -0.0110 | 1/6 | no |

| cell | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| maxSetupBars=60 | -0.035 | +0.002 | -0.054 | +0.078 | +0.025 | -0.053 |
| maxSetupBars=120 | -0.054 | -0.025 | -0.057 | +0.081 | +0.008 | -0.038 |
| maxSetupBars=180 | -0.047 | -0.019 | -0.058 | +0.066 | +0.003 | -0.034 |
| maxSetupBars=300 | -0.038 | -0.021 | -0.071 | +0.051 | -0.002 | -0.030 |

### Axis: session

| cell | n | WR% | totalR | avgR | PF($) | IS n | IS totR | IS avgR | OOS n | OOS totR | OOS avgR | +yrs/tot | clears? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| session=all 0000-2359 | 5056 | 34.4 | -52.9 | -0.0105 | 1.036 | 3467 | -37.9 | -0.0109 | 1589 | -15.0 | -0.0094 | 2/6 | no |
| session=RTH 0930-1600ET | 2684 | 34.9 | +56.9 | +0.0212 | 1.081 | 1869 | +6.6 | +0.0035 | 815 | +50.4 | +0.0618 | 2/6 | no |
| session=NY-AM 0930-1200ET | 1624 | 35.5 | +67.7 | +0.0417 | 1.119 | 1147 | +46.1 | +0.0402 | 477 | +21.6 | +0.0452 | 3/6 | no |

| cell | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| session=all 0000-2359 | -0.047 | -0.019 | -0.058 | +0.066 | +0.003 | -0.034 |
| session=RTH 0930-1600ET | -0.047 | -0.023 | -0.063 | +0.124 | +0.132 | -0.081 |
| session=NY-AM 0930-1200ET | +0.002 | -0.006 | -0.086 | +0.235 | +0.078 | -0.021 |

## Task A summary

**NO cell clears the bar.** No single-axis parameter configuration produces positive total R in both IS and OOS with >=5/6 positive-avgR years. SMC3 has no robust parameter config.

Best cells by **OOS avg R** (OOS n >= 100):

| rank | cell | OOS n | OOS avgR | OOS totR | IS avgR | IS totR | +yrs/tot | clears? |
|---|---|---|---|---|---|---|---|---|
| 1 | session=RTH 0930-1600ET | 815 | +0.0618 | +50.4 | +0.0035 | +6.6 | 2/6 | no |
| 2 | session=NY-AM 0930-1200ET | 477 | +0.0452 | +21.6 | +0.0402 | +46.1 | 3/6 | no |
| 3 | 5mConfirm=FVG only | 1466 | +0.0291 | +42.6 | -0.0219 | -73.1 | 2/6 | no |
| 4 | 1mTrigger=BOS only | 1494 | +0.0172 | +25.6 | -0.0232 | -75.7 | 2/6 | no |
| 5 | maxStopPoints=90 | 1618 | +0.0145 | +23.4 | -0.0075 | -26.4 | 3/6 | no |
| 6 | maxStopPoints=40 | 1580 | +0.0004 | +0.6 | -0.0278 | -105.2 | 2/6 | no |
| 7 | maxSetupBars=60 | 1350 | -0.0007 | -0.9 | +0.0025 | +7.4 | 3/6 | no |
| 8 | stopMode=Wider Of Both | 1459 | -0.0042 | -6.1 | +0.0113 | +34.9 | 3/6 | no |



---

## Task B — trade classification (causal, entry-time) on baseline trades

Baseline: n=5056, WR 34.4%, total R -52.9, avg R -0.0105.  R = net$/(risk_pts*$20) per trade (risk-normalized).  All features causal (known at/before entry-bar close).  `*` = n<100.

### By session (ET)   (WR-spread 2.7pp, avgR-spread +0.0675R across n>=100 buckets)

| bucket | n | WR% | avgR | totR | IS n | IS avgR | IS totR | OOS n | OOS avgR | OOS totR |
|---|---|---|---|---|---|---|---|---|---|---|
| Asia | 723 | 36.4 | +0.0260 | +18.8 | 437 | +0.0411 | +18.0 | 286 | +0.0030 | +0.9 |
| London | 1397 | 33.7 | -0.0415 | -58.0 | 981 | -0.0421 | -41.3 | 416 | -0.0400 | -16.6 |
| NY-AM | 1719 | 34.1 | -0.0043 | -7.4 | 1220 | +0.0185 | +22.6 | 499 | -0.0600 | -30.0 |
| NY-PM | 1051 | 34.3 | -0.0017 | -1.8 | 717 | -0.0399 | -28.6 | 334 | +0.0802 | +26.8 |
| Break | 166 | 34.3 | -0.0272 | -4.5 | 112 | -0.0755 | -8.5 | 54 | +0.0731 | +3.9 |

_`*` = n < 100 (distrust)._

### By ET hour-band   (WR-spread 4.1pp, avgR-spread +0.1100R across n>=100 buckets)

| bucket | n | WR% | avgR | totR | IS n | IS avgR | IS totR | OOS n | OOS avgR | OOS totR |
|---|---|---|---|---|---|---|---|---|---|---|
| 0-2 | 317 | 34.7 | -0.0284 | -9.0 | 218 | -0.0031 | -0.7 | 99 | -0.0839 | -8.3 |
| 2-8 | 1568 | 32.8 | -0.0660 | -103.5 | 1111 | -0.0622 | -69.2 | 457 | -0.0752 | -34.4 |
| 8-12 | 1708 | 34.7 | +0.0168 | +28.7 | 1192 | +0.0228 | +27.1 | 516 | +0.0030 | +1.6 |
| 12-16 | 899 | 34.7 | +0.0068 | +6.1 | 613 | -0.0100 | -6.1 | 286 | +0.0429 | +12.3 |
| 16-24 | 564 | 36.9 | +0.0439 | +24.8 | 333 | +0.0328 | +10.9 | 231 | +0.0600 | +13.9 |

_`*` = n < 100 (distrust)._

### By direction   (WR-spread 0.3pp, avgR-spread +0.0177R across n>=100 buckets)

| bucket | n | WR% | avgR | totR | IS n | IS avgR | IS totR | OOS n | OOS avgR | OOS totR |
|---|---|---|---|---|---|---|---|---|---|---|
| long | 2351 | 34.5 | -0.0010 | -2.3 | 1646 | -0.0004 | -0.7 | 705 | -0.0022 | -1.6 |
| short | 2705 | 34.2 | -0.0187 | -50.6 | 1821 | -0.0204 | -37.2 | 884 | -0.0152 | -13.4 |

_`*` = n < 100 (distrust)._

### By stop-width (risk pts)   (WR-spread 1.7pp, avgR-spread +0.1135R across n>=100 buckets)

| bucket | n | WR% | avgR | totR | IS n | IS avgR | IS totR | OOS n | OOS avgR | OOS totR |
|---|---|---|---|---|---|---|---|---|---|---|
| tight<20 | 2068 | 33.7 | -0.0615 | -127.2 | 1586 | -0.0707 | -112.1 | 482 | -0.0312 | -15.0 |
| mid20-60 | 2287 | 34.7 | +0.0165 | +37.8 | 1517 | +0.0163 | +24.7 | 770 | +0.0171 | +13.2 |
| wide>60 | 701 | 35.4 | +0.0520 | +36.5 | 364 | +0.1361 | +49.6 | 337 | -0.0389 | -13.1 |

_`*` = n < 100 (distrust)._

### By 60m EMA50 alignment   (WR-spread 0.9pp, avgR-spread +0.0300R across n>=100 buckets)

| bucket | n | WR% | avgR | totR | IS n | IS avgR | IS totR | OOS n | OOS avgR | OOS totR |
|---|---|---|---|---|---|---|---|---|---|---|
| with-60m | 1224 | 35.0 | +0.0123 | +15.1 | 856 | +0.0302 | +25.8 | 368 | -0.0293 | -10.8 |
| counter-60m | 3832 | 34.1 | -0.0177 | -68.0 | 2611 | -0.0244 | -63.7 | 1221 | -0.0035 | -4.2 |

_`*` = n < 100 (distrust)._

### By daily EMA20 alignment   (WR-spread 1.5pp, avgR-spread +0.0490R across n>=100 buckets)

| bucket | n | WR% | avgR | totR | IS n | IS avgR | IS totR | OOS n | OOS avgR | OOS totR |
|---|---|---|---|---|---|---|---|---|---|---|
| with-daily | 2345 | 35.1 | +0.0152 | +35.8 | 1608 | +0.0185 | +29.7 | 737 | +0.0082 | +6.0 |
| counter-daily | 2708 | 33.6 | -0.0337 | -91.3 | 1856 | -0.0379 | -70.3 | 852 | -0.0247 | -21.0 |
| flat * | 3 | 66.7 | +0.8859 | +2.7 | 3 | +0.8859 | +2.7 | 0 | +nan | +0.0 |

_`*` = n < 100 (distrust)._

### By sweep magnitude   (WR-spread 0.8pp, avgR-spread +0.0158R across n>=100 buckets)

| bucket | n | WR% | avgR | totR | IS n | IS avgR | IS totR | OOS n | OOS avgR | OOS totR |
|---|---|---|---|---|---|---|---|---|---|---|
| sm<1.8 | 1550 | 34.9 | -0.0099 | -15.4 | 1160 | -0.0213 | -24.7 | 390 | +0.0240 | +9.4 |
| sm>4.5 | 1812 | 34.1 | -0.0031 | -5.5 | 1103 | -0.0137 | -15.1 | 709 | +0.0135 | +9.6 |
| sm1.8-4.5 | 1694 | 34.1 | -0.0189 | -32.0 | 1204 | +0.0016 | +1.9 | 490 | -0.0692 | -33.9 |

_`*` = n < 100 (distrust)._

### By 5m-confirm type   (WR-spread 3.0pp, avgR-spread +0.0901R across n>=100 buckets)

| bucket | n | WR% | avgR | totR | IS n | IS avgR | IS totR | OOS n | OOS avgR | OOS totR |
|---|---|---|---|---|---|---|---|---|---|---|
| BOS | 1762 | 32.8 | -0.0515 | -90.8 | 1190 | -0.0660 | -78.5 | 572 | -0.0214 | -12.2 |
| FVG | 2535 | 35.0 | +0.0034 | +8.6 | 1767 | +0.0075 | +13.3 | 768 | -0.0061 | -4.7 |
| both | 759 | 35.8 | +0.0386 | +29.3 | 510 | +0.0536 | +27.3 | 249 | +0.0078 | +1.9 |

_`*` = n < 100 (distrust)._

### By ATR percentile (5m)   (WR-spread 2.1pp, avgR-spread +0.0292R across n>=100 buckets)

| bucket | n | WR% | avgR | totR | IS n | IS avgR | IS totR | OOS n | OOS avgR | OOS totR |
|---|---|---|---|---|---|---|---|---|---|---|
| atr-lo | 849 | 35.9 | +0.0085 | +7.3 | 518 | +0.0044 | +2.3 | 331 | +0.0151 | +5.0 |
| atr-mid | 1485 | 34.3 | -0.0206 | -30.6 | 1056 | -0.0186 | -19.6 | 429 | -0.0256 | -11.0 |
| atr-hi | 2722 | 33.9 | -0.0109 | -29.5 | 1893 | -0.0109 | -20.5 | 829 | -0.0109 | -9.0 |

_`*` = n < 100 (distrust)._

### By day-of-week   (WR-spread 6.1pp, avgR-spread +0.1849R across n>=100 buckets)

| bucket | n | WR% | avgR | totR | IS n | IS avgR | IS totR | OOS n | OOS avgR | OOS totR |
|---|---|---|---|---|---|---|---|---|---|---|
| Mon | 920 | 34.0 | -0.0228 | -21.0 | 632 | -0.0213 | -13.5 | 288 | -0.0262 | -7.6 |
| Tue | 1036 | 35.6 | +0.0267 | +27.6 | 696 | +0.0408 | +28.4 | 340 | -0.0022 | -0.8 |
| Wed | 1027 | 31.8 | -0.0848 | -87.1 | 691 | -0.0849 | -58.7 | 336 | -0.0845 | -28.4 |
| Thu | 1052 | 32.4 | -0.0680 | -71.6 | 731 | -0.0808 | -59.0 | 321 | -0.0390 | -12.5 |
| Fri | 883 | 37.9 | +0.1001 | +88.4 | 626 | +0.0997 | +62.4 | 257 | +0.1011 | +26.0 |
| Sun | 138 | 37.7 | +0.0779 | +10.8 | 91 | +0.0277 | +2.5 | 47 | +0.1752 | +8.2 |

_`*` = n < 100 (distrust)._

## Task B — filter-candidate scan (IS>0 AND OOS>0 avg R, both n>=100)

| feature | bucket | IS n | IS avgR | OOS n | OOS avgR | overall avgR | overall totR |
|---|---|---|---|---|---|---|---|
| By session (ET) | Asia | 437 | +0.0411 | 286 | +0.0030 | +0.0260 | +18.8 |
| By ET hour-band | 8-12 | 1192 | +0.0228 | 516 | +0.0030 | +0.0168 | +28.7 |
| By ET hour-band | 16-24 | 333 | +0.0328 | 231 | +0.0600 | +0.0439 | +24.8 |
| By stop-width (risk pts) | mid20-60 | 1517 | +0.0163 | 770 | +0.0171 | +0.0165 | +37.8 |
| By daily EMA20 alignment | with-daily | 1608 | +0.0185 | 737 | +0.0082 | +0.0152 | +35.8 |
| By 5m-confirm type | both | 510 | +0.0536 | 249 | +0.0078 | +0.0386 | +29.3 |
| By ATR percentile (5m) | atr-lo | 518 | +0.0044 | 331 | +0.0151 | +0.0085 | +7.3 |
| By day-of-week | Fri | 626 | +0.0997 | 257 | +0.1011 | +0.1001 | +88.4 |

**Before/after (keep only the bucket vs full baseline):**

| filter | baseline avgR | baseline totR | kept n | kept avgR | kept totR | kept IS avgR | kept OOS avgR |
|---|---|---|---|---|---|---|---|
| keep Asia | -0.0105 | -52.9 | 723 | +0.0260 | +18.8 | +0.0411 | +0.0030 |
| keep 8-12 | -0.0105 | -52.9 | 1708 | +0.0168 | +28.7 | +0.0228 | +0.0030 |
| keep 16-24 | -0.0105 | -52.9 | 564 | +0.0439 | +24.8 | +0.0328 | +0.0600 |
| keep mid20-60 | -0.0105 | -52.9 | 2287 | +0.0165 | +37.8 | +0.0163 | +0.0171 |
| keep with-daily | -0.0105 | -52.9 | 2345 | +0.0152 | +35.8 | +0.0185 | +0.0082 |
| keep both | -0.0105 | -52.9 | 759 | +0.0386 | +29.3 | +0.0536 | +0.0078 |
| keep atr-lo | -0.0105 | -52.9 | 849 | +0.0085 | +7.3 | +0.0044 | +0.0151 |
| keep Fri | -0.0105 | -52.9 | 883 | +0.1001 | +88.4 | +0.0997 | +0.1011 |

## Task B — spread summary (does outcome depend on context?)

| feature | WR-spread (pp) | avgR-spread (R) |
|---|---|---|
| By session (ET) | 2.7 | +0.0675 |
| By ET hour-band | 4.1 | +0.1100 |
| By direction | 0.3 | +0.0177 |
| By stop-width (risk pts) | 1.7 | +0.1135 |
| By 60m EMA50 alignment | 0.9 | +0.0300 |
| By daily EMA20 alignment | 1.5 | +0.0490 |
| By sweep magnitude | 0.8 | +0.0158 |
| By 5m-confirm type | 3.0 | +0.0901 |
| By ATR percentile (5m) | 2.1 | +0.0292 |
| By day-of-week | 6.1 | +0.1849 |


---
## Task B — day-of-week deep-dive (the one live feature)

Day-of-week is the ONLY causal feature whose outcome gradient is both large and
IS+OOS-stable. WR is otherwise pinned 32-38% across every other context bucket.

### avg R by (day x year) — Friday is positive in ALL 6 years; Wed/Thu consistently negative

| dow | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | +yrs |
|---|---|---|---|---|---|---|---|
| Mon | +0.179 | -0.202 | +0.023 | +0.069 | -0.061 | +0.038 | 4/6 |
| Tue | -0.128 | +0.167 | -0.176 | +0.199 | +0.031 | -0.072 | 3/6 |
| Wed | +0.014 | -0.086 | -0.163 | -0.069 | -0.030 | -0.218 | 1/6 |
| Thu | -0.249 | -0.014 | -0.049 | -0.080 | -0.023 | -0.070 | 0/6 |
| **Fri** | **+0.034** | **+0.054** | **+0.067** | **+0.222** | **+0.132** | **+0.040** | **6/6** |

Friday: IS avgR +0.0997 (n626) vs OOS avgR +0.1011 (n257) — near-identical across
halves, positive every calendar year. This is the single bucket in the entire
Stage-2 study that clears "positive in both halves AND >=5/6 years."

### Filter candidate: Friday-only (before / after)

| variant | n | WR% | avgR | totR | IS totR | OOS totR | net$ | maxDD$ |
|---|---|---|---|---|---|---|---|---|
| baseline (all days) | 5056 | 34.4 | -0.0105 | -52.9 | -37.9 | -15.0 | +79,410 | 61,825 |
| **Friday-only** | 883 | 37.9 | +0.1001 | +88.4 | +62.4 | +26.0 | +76,580 | 21,845 |
| drop-Friday | 4173 | 33.6 | -0.0339 | -141.3 | -100.3 | -41.0 | +2,830 | 56,025 |

Friday alone captures essentially all baseline dollar profit ($76.6k of $79.4k) on
1/6 of the trades and 1/3 of the drawdown; the other four weekdays sum to total R
-141.3. So the whole strategy's positive dollars live on Fridays.

**Caveat (do not oversell):** this is a single-weekday *calendar/seasonal* effect,
not evidence the sweep->confirm->trigger *logic* has an entry edge. avg R is only
+0.10 (~177 tr/yr => ~+18R/yr), the mechanism is unexplained, and day-of-week was
one of ~10 features scanned. It clears the stated statistical bar (uniquely: 6/6
years + both halves, and Tue by contrast is only 3/6) but needs a causal "why
Friday" before it could justify any deployment sim. It rescues P&L via *when to
trade*, not via a better signal.

---
## Stage-2 VERDICT

**Task A (parameters): NO robust config.** Sweeping every axis one-at-a-time around
the default, ZERO cells clear "positive total R in BOTH IS and OOS AND positive avg
R in >=5/6 years." Overall avg R stays within ~[-0.16, +0.04] and the only cells
with positive R in both halves (session=NY-AM 0930-1200 ET: avgR +0.042, IS +46.1R
/ OOS +21.6R; session=RTH: OOS +50.4R) are 2024-25 window artifacts — NY-AM is
positive in just 3/6 years, RTH in 2/6. SMC3 has no robust parameter region.

**Task B (context): outcome is pinned ~32-38% WR almost everywhere.** WR-spreads
across buckets: direction 0.3pp, sweep-magnitude 0.8pp, 60m-align 0.9pp, stop-width
1.7pp, ATR-percentile 2.1pp, session 2.7pp, 5m-confirm 3.0pp, hour-band 4.1pp. This
is the *dead candle-flip flat ~3.9pt* pattern, NOT the sweep->OTE 7-15pt WR gradient.
Where a bucket is positive in IS it typically decays to ~0 or flips in OOS (Asia
+0.041->+0.003; wide-stop +0.136->-0.039; NY-AM +0.019->-0.060). The sweep->confirm
->trigger *signal* carries no context-conditional edge.

**The one exception is day-of-week** (WR-spread 6.1pp, avgR-spread 0.185R): Friday is
positive in both halves and all 6 years and holds essentially all the P&L, while
Wed/Thu are consistent losers. That is a *seasonal* filter, not a signal edge.

**Blunt bottom line:** There is no real edge hiding in SMC3's parameters or in its
intraday market-context — on a risk-normalized basis the entry logic is structurally
breakeven (avg R ~ -0.01, WR pinned near the 2R/1R breakeven everywhere). The only
thing with a stable positive-R gradient is *which weekday you trade* (Friday), a
mechanism-free calendar effect that is too thin to stand on its own. Recommendation:
do NOT proceed to Apex / static-DD / emission deployment sims on the strategy as-is;
the parameter and context search is exhausted. If anything is worth a follow-up it
is "why is Friday different," not further tuning of the sweep logic.
