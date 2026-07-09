# Profile D (IFVG) — §F Close-Through-SPEED Probe

_Research-only. LIVE HOLD ACTIVE — no arming, no funded-config change, no certification claim. Targeted probe of the ONE distinct IFVG rule (inversion FVG + close-through speed) vs the dead SMC3/BOS-FVG core. All figures in R._

Data: `/Users/jacksonclarke/trading-team/data/real_futures/NQ_databento_1m_5y.parquet`  (1,769,367 1m bars, 2021-06-23 -> 2026-06-22)
Costs: $2.50/side + 1 tick (0.25pt) adverse/fill. NQ $20/pt, tick 0.25. Target = fixed 2R (held constant). Stop = sweep extreme ± 4t. IS 2021-24 / OOS 2025-26H1 (by entry year).

## 1. Causal audit

- Global 60m no-lookahead (stepped source close <= 1m open): **PASS**
- Per-trade causal gates asserted (entry_ns > sweep_confirm & > FVG_formation; entry == close-through confirm; bar-after exists): **PASS** for all fired trades.
- Gate-OK fires across all 6 runs: **16,185** | Artifacts (gate-fail, excluded): **0**

| run | contexts | candidates | gate_ok | artifacts | risk_rej | blocked | open |
|---|---|---|---|---|---|---|---|
| tf1 | 17455 | 3939 | 3939 | 0 | 3051 | 714 | 2 |
| tf2 | 17455 | 2565 | 2565 | 0 | 2624 | 395 | 3 |
| tf3 | 17455 | 1974 | 1974 | 0 | 2321 | 291 | 0 |
| tf4 | 17455 | 1574 | 1574 | 0 | 2056 | 188 | 2 |
| tf5 | 17455 | 1351 | 1351 | 0 | 1843 | 162 | 3 |
| highest | 17455 | 4782 | 4782 | 0 | 0 | 1116 | 4 |

## 2. Close-through-SPEED bucket table (pooled tf 1-5, all single-tf trades)

| speed (tf bars) | n | WR% | PF(R) | avgR | totR |
|---|---|---|---|---|---|
| 1 | 2853 | 31.7 | 0.79 | -0.157 | -448.4 |
| 2 | 2013 | 33.5 | 0.86 | -0.106 | -214.2 |
| 3 | 1319 | 31.4 | 0.78 | -0.169 | -222.6 |
| 4 | 943 | 32.3 | 0.80 | -0.156 | -147.3 |
| 5 | 634 | 33.6 | 0.85 | -0.117 | -74.3 |
| >5 | 1881 | 33.2 | 0.81 | -0.143 | -269.9 |

_Speed = (inversion tf-bar idx − FVG formation tf-bar idx). Minimum speed is 1 (a formation bar can never close through its own gap). MONOTONIC faster=better would show avgR/PF/WR declining as speed rises._

### Per-tf speed buckets (avgR)

| tf | spd1 | spd2 | spd3 | spd4 | spd5 | spd>5 |
|---|---|---|---|---|---|---|
| tf1 | -0.161(n890) | -0.117(n678) | -0.220(n449) | -0.192(n367) | -0.085(n211) | -0.208(n628) |
| tf2 | -0.140(n637) | -0.026(n456) | -0.094(n313) | -0.035(n194) | -0.131(n135) | -0.194(n432) |
| tf3 | -0.138(n534) | -0.066(n343) | -0.162(n221) | -0.294(n162) | -0.066(n121) | -0.096(n302) |
| tf4 | -0.149(n407) | -0.236(n288) | -0.157(n195) | -0.130(n119) | -0.128(n87) | -0.055(n288) |
| tf5 | -0.213(n385) | -0.131(n248) | -0.197(n141) | -0.068(n101) | -0.245(n80) | -0.047(n231) |

## 3. Filter comparison  (<=4 vs >=5 vs dead-SMC3)

Pooled tf 1-5, full stat set per cumulative filter:

| filter | n | WR% | PF(R) | avgR | totR | IS avgR | OOS avgR | ex-2024 avgR | ex-Fri avgR | yr-signs |
|---|---|---|---|---|---|---|---|---|---|---|
| <=1 | 2853 | 31.7 | 0.79 | -0.157 | -448.4 | -0.143 | -0.190 | -0.173 | -0.143 | ------ |
| <=2 | 4866 | 32.4 | 0.82 | -0.136 | -662.6 | -0.124 | -0.163 | -0.156 | -0.117 | ------ |
| <=3 | 6185 | 32.2 | 0.81 | -0.143 | -885.2 | -0.131 | -0.171 | -0.163 | -0.122 | ------ |
| <=4 | 7128 | 32.2 | 0.81 | -0.145 | -1032.5 | -0.139 | -0.158 | -0.162 | -0.128 | ------ |
| <=5 | 7762 | 32.3 | 0.81 | -0.143 | -1106.8 | -0.135 | -0.159 | -0.158 | -0.126 | ------ |
| no-limit | 9643 | 32.5 | 0.81 | -0.143 | -1376.7 | -0.139 | -0.152 | -0.162 | -0.127 | ------ |
| >=5 (neg ctrl) | 2515 | 33.3 | 0.82 | -0.137 | -344.2 | -0.138 | -0.134 | -0.162 | -0.124 | ------ |

**Dead SMC3 baseline:** n5056 · WR 34.4% · avgR -0.010  (2R/1R breakeven WR ≈ 33.3%).

**Head-to-head (pooled):**
- `<=4` close-through: n7128 WR 32.2% PF(R) 0.81 avgR -0.145 (ex-2024 -0.162)
- `>=5` close-through: n2515 WR 33.3% PF(R) 0.82 avgR -0.137 (ex-2024 -0.162)
- dead SMC3:          n5056 WR 34.4% avgR -0.010

## 4. IFVG timeframe table (1m..5m), <=4 close-through headline

| tf | n(<=4) | WR% | PF(R) | avgR | totR | IS avgR | OOS avgR | ex-2024 avgR | ex-Fri avgR | yr-signs |
|---|---|---|---|---|---|---|---|---|---|---|
| 1m | 2384 | 32.1 | 0.79 | -0.164 | -391.9 | -0.135 | -0.233 | -0.183 | -0.166 | ------ |
| 2m | 1600 | 34.2 | 0.88 | -0.086 | -137.2 | -0.104 | -0.044 | -0.105 | -0.058 | +---+- |
| 3m | 1260 | 32.2 | 0.81 | -0.143 | -179.6 | -0.124 | -0.185 | -0.147 | -0.135 | +----- |
| 4m | 1009 | 30.7 | 0.77 | -0.173 | -174.5 | -0.184 | -0.147 | -0.211 | -0.127 | ------ |
| 5m | 875 | 30.7 | 0.78 | -0.171 | -149.2 | -0.184 | -0.142 | -0.179 | -0.138 | ------ |
| highest(5→1) | 2926 | 27.2 | 0.60 | -0.341 | -998.5 | -0.339 | -0.345 | -0.354 | -0.342 | ------ |

## 5. Sub-splits on the `<=4` pooled headline bucket

| split | n | WR% | PF(R) | avgR | totR |
|---|---|---|---|---|---|
| long | 3477 | 32.3 | 0.84 | -0.122 | -425.9 |
| short | 3651 | 32.2 | 0.79 | -0.166 | -606.6 |
| NY-AM 0930-1200 | 1231 | 30.6 | 0.77 | -0.182 | -224.2 |
| all-sessions | 7128 | 32.2 | 0.81 | -0.145 | -1032.5 |
| 2024-in | 7128 | 32.2 | 0.81 | -0.145 | -1032.5 |
| 2024-ex | 5723 | 31.7 | 0.79 | -0.162 | -928.0 |
| Friday-in | 7128 | 32.2 | 0.81 | -0.145 | -1032.5 |
| Friday-ex | 5852 | 32.8 | 0.83 | -0.128 | -746.4 |

## 6. Best candidate

Best tf by ex-2024 avgR (n>=100) = **2m**, `<=4` close-through:
- n1600 · WR 34.2% · PF(R) 0.88 · avgR -0.086 · totR -137.2
- IS avgR -0.104 · OOS avgR -0.044 · ex-2024 avgR -0.105 · ex-Friday avgR -0.058
- per-year R signs 2021..2026: +---+-

## 6b. Risk-floor robustness (cost-artifact control)

Sweep-extreme stops produce many sub-1pt-risk trades whose R is dominated by fixed costs (down to −2.5R). Re-checking the pooled book at rising risk floors to prove the KILL is NOT merely that cost bleed:

| risk floor | n | WR% | PF(R) | avgR | spd1..5 avgR (gradient) |
|---|---|---|---|---|---|
| >=0pt | 9643 | 32.5 | 0.81 | -0.143 | -0.157 -0.106 -0.169 -0.156 -0.117 |
| >=2pt | 8823 | 33.6 | 0.92 | -0.053 | -0.075 -0.018 -0.101 -0.068 -0.026 |
| >=5pt | 7816 | 33.8 | 0.97 | -0.022 | -0.048 +0.015 -0.070 -0.026 +0.009 |
| >=10pt | 6975 | 34.2 | 1.00 | -0.001 | -0.026 +0.044 -0.056 +0.015 +0.015 |

Even at risk>=10pt (removing the cost-bleed tail) the book converges to WR ~34% / PF ~1.00 / avgR ~0.00 — i.e. it reproduces the SAME ~33% 2R breakeven distribution as dead SMC3 (WR 34.4%), and the speed buckets stay non-monotonic (spd2 best, spd3 worst). Close-through SPEED carries no information about outcome.

## 7. Hand-trace artifact audit (tz-aware UTC)

### Pooled <=4 — 5 winners
   long tf5 spd4 | sweep 2026-03-15 22:48 < fvg 00:30 < entry 00:50 <= exit 14:11 | entry 24513.25 stop 24393.75 tgt 24752.25 exit 24752.25 | R +1.99 target | causal_order=OK
  short tf5 spd2 | sweep 2022-09-30 15:18 < fvg 16:45 < entry 16:55 <= exit 22:01 | entry 11235.00 stop 11354.50 tgt 10996.00 exit 10996.00 | R +1.99 target | causal_order=OK
   long tf2 spd2 | sweep 2026-04-06 00:01 < fvg 01:58 < entry 02:02 <= exit 14:01 | entry 24206.25 stop 24086.75 tgt 24445.25 exit 24445.25 | R +1.99 target | causal_order=OK
   long tf1 spd2 | sweep 2023-10-23 13:46 < fvg 14:03 < entry 14:05 <= exit 14:49 | entry 14637.50 stop 14518.00 tgt 14876.50 exit 14876.50 | R +1.99 target | causal_order=OK
   long tf5 spd1 | sweep 2026-04-06 00:01 < fvg 02:00 < entry 02:05 <= exit 14:01 | entry 24205.00 stop 24086.75 tgt 24441.50 exit 24441.50 | R +1.99 target | causal_order=OK
### Pooled <=4 — 5 losers
   long tf2 spd1 | sweep 2024-06-24 15:18 < fvg 15:28 < entry 15:30 <= exit 15:31 | entry 19912.25 stop 19911.75 tgt 19913.25 exit 19911.75 | R -2.50 stop | causal_order=OK
  short tf5 spd4 | sweep 2025-10-29 03:35 < fvg 03:45 < entry 04:05 <= exit 04:06 | entry 26232.75 stop 26233.25 tgt 26231.75 exit 26233.25 | R -2.50 stop | causal_order=OK
  short tf3 spd1 | sweep 2024-11-07 08:11 < fvg 08:30 < entry 08:33 <= exit 08:34 | entry 20938.75 stop 20939.25 tgt 20937.75 exit 20939.25 | R -2.50 stop | causal_order=OK
  short tf1 spd1 | sweep 2024-02-09 09:36 < fvg 09:41 < entry 09:42 <= exit 09:43 | entry 17899.25 stop 17899.75 tgt 17898.25 exit 17899.75 | R -2.50 stop | causal_order=OK
  short tf2 spd1 | sweep 2021-12-30 10:15 < fvg 10:22 < entry 10:24 <= exit 10:25 | entry 16526.75 stop 16527.25 tgt 16525.75 exit 16527.25 | R -2.50 stop | causal_order=OK
### Pooled <=4 — 3 largest winners
   long tf5 spd4 | sweep 2026-03-15 22:48 < fvg 00:30 < entry 00:50 <= exit 14:11 | entry 24513.25 stop 24393.75 tgt 24752.25 exit 24752.25 | R +1.99 target | causal_order=OK
  short tf5 spd2 | sweep 2022-09-30 15:18 < fvg 16:45 < entry 16:55 <= exit 22:01 | entry 11235.00 stop 11354.50 tgt 10996.00 exit 10996.00 | R +1.99 target | causal_order=OK
   long tf2 spd2 | sweep 2026-04-06 00:01 < fvg 01:58 < entry 02:02 <= exit 14:01 | entry 24206.25 stop 24086.75 tgt 24445.25 exit 24445.25 | R +1.99 target | causal_order=OK
### Pooled <=4 — 3 largest losers
   long tf2 spd1 | sweep 2024-06-24 15:18 < fvg 15:28 < entry 15:30 <= exit 15:31 | entry 19912.25 stop 19911.75 tgt 19913.25 exit 19911.75 | R -2.50 stop | causal_order=OK
  short tf5 spd4 | sweep 2025-10-29 03:35 < fvg 03:45 < entry 04:05 <= exit 04:06 | entry 26232.75 stop 26233.25 tgt 26231.75 exit 26233.25 | R -2.50 stop | causal_order=OK
  short tf3 spd1 | sweep 2024-11-07 08:11 < fvg 08:30 < entry 08:33 <= exit 08:34 | entry 20938.75 stop 20939.25 tgt 20937.75 exit 20939.25 | R -2.50 stop | causal_order=OK

Total artifacts (gate failures, excluded) across all runs: **0**

## 8. VERDICT

**CLOSE-THROUGH IFVG PROBE STATUS: KILL.**

- Mechanism visible as monotonic faster=better gradient? **NO** (<=4 avgR -0.145 vs >=5 avgR -0.137; exact-speed 1..5 avgR seq = [-0.157, -0.106, -0.169, -0.156, -0.117])
- KILL triggers:
  - PF(R) 0.81 <= 1.15
  - ex-2024 avgR -0.162 breakeven/negative
  - WR 32.2% pinned at ~33% breakeven
  - no monotonic faster=better gradient

**Recommendation: SHELVE — build NOT justified. **

