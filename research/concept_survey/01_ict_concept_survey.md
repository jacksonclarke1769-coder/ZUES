# ICT Concept Survey — 36-Cell Preregistered Arena, Gated Results (v2, CORRECTED)

## CORRECTION NOTICE (v2, 2026-07-20)

**v1 of this report and its 19-cell survivor shortlist are RETRACTED. Cause: a same-bar fill/invalidation sequencing bug in `survey_engine.py::run_cell()` (limit-order path) silently CANCELLED trades whose entry touch and stop/invalidation touch first occurred on the same 1m bar, instead of recording them as filled-then-immediately-stopped losses. This is a selection-bias bug: it deleted precisely the fastest-reversing, worst-case fills from the trade population -- for FVG_1m_long holdout alone, 8,791 same-bar candidates were wrongly cancelled vs 8,894 kept as clean fills; that deleted population WAS the edge (PF 1.90 -> 0.68, totR +5,116 -> -5,104 once corrected).**

**Fix**: same-bar entry+invalidation now resolves as a filled trade, immediately stopped out on that same bar (conservative, consistent with PREREG §3's "stop-fills-first on ambiguous 1m bars"). Invalidation strictly BEFORE the entry is ever touched remains a legitimate cancel (the order never had a chance to fill cleanly). A regression test (`test_fill_sequencing.py`) now asserts this directly. The exit-management scan for clean fills is unchanged (already started at fill_i+1, already never credited target hits on the fill bar).

**Scope of the bug**: it only affects LIMIT-mode entries -- FVG, IFVG, Order Block, Breaker Block (24/36 cells). **Sweep/MSS are market-mode (fill immediately at signal confirmation, no pre-fill touch-window logic) and are UNCHANGED by this fix** -- their v1 and v2 holdout stats are bit-identical, confirmed below.

**Corrected verdict: Gate A+B+C survivors = 0/36 (was 19/36 in the retracted v1). The survey found nothing deployable.**

### Before/after per-cell deltas for the 19 previously-claimed (now retracted) survivors

| cell | v1 HOLDOUT n/PF/exp/totR (retracted) | v2 HOLDOUT n/PF/exp/totR (corrected) | v2 Gate A | still a survivor? |
|---|---|---|---|---|
| FVG_1m_long | 7953/1.897/0.643/5115.532 | 13824/0.741/-0.260/-3595.868 | fail | NO |
| Breaker_5m_long | 910/1.245/0.165/150.392 | 1065/0.949/-0.038/-40.348 | fail | NO |
| FVG_5m_short | 1739/1.465/0.368/640.763 | 2175/1.042/0.036/78.926 | PASS | NO |
| FVG_1m_short | 7832/1.822/0.598/4685.379 | 13452/0.732/-0.269/-3622.439 | fail | NO |
| IFVG_5m_short | 1582/1.355/0.294/465.137 | 2090/0.870/-0.120/-251.792 | fail | NO |
| Breaker_1m_short | 3689/1.438/0.281/1036.861 | 5302/0.736/-0.222/-1177.553 | fail | NO |
| FVG_5m_long | 1810/1.488/0.378/683.371 | 2342/0.979/-0.019/-44.120 | fail | NO |
| IFVG_5m_long | 1389/1.364/0.297/412.249 | 1852/0.886/-0.104/-192.027 | fail | NO |
| Breaker_1m_long | 3648/1.487/0.310/1132.681 | 5252/0.772/-0.190/-997.221 | fail | NO |
| FVG_15m_long | 642/1.355/0.275/176.667 | 740/1.042/0.035/25.620 | PASS | NO |
| OB_1m_long | 5392/1.362/0.227/1223.989 | 7381/0.781/-0.173/-1278.515 | fail | NO |
| IFVG_1m_long | 6449/1.924/0.663/4277.503 | 11859/0.698/-0.308/-3657.270 | fail | NO |
| IFVG_1m_short | 6567/1.831/0.618/4060.550 | 12120/0.666/-0.348/-4216.166 | fail | NO |
| Breaker_15m_short | 353/1.234/0.162/57.207 | 370/1.141/0.101/37.235 | PASS | NO |
| IFVG_15m_short | 537/1.513/0.404/216.879 | 645/1.120/0.102/65.564 | PASS | NO |
| MSS_15m_long | 747/1.182/0.047/35.009 | 747/1.182/0.047/35.009 | PASS | NO |
| OB_5m_long | 1312/1.236/0.149/195.279 | 1482/1.004/0.003/3.821 | PASS | NO |
| OB_1m_short | 5269/1.275/0.183/965.100 | 7264/0.742/-0.212/-1539.770 | fail | NO |
| Breaker_5m_short | 872/1.214/0.147/128.604 | 996/0.968/-0.024/-24.118 | fail | NO |

Market-mode cells (Sweep/MSS) for reference -- bit-identical v1 vs v2 (unaffected by the bug):

| cell | v1 HOLDOUT totR | v2 HOLDOUT totR | identical? |
|---|---|---|---|
| Sweep_1m_long | -835.5434 | -835.5434 | yes |
| Sweep_1m_short | -964.2826 | -964.2826 | yes |
| Sweep_5m_long | -54.5268 | -54.5268 | yes |
| Sweep_5m_short | -276.1182 | -276.1182 | yes |
| Sweep_15m_long | -18.2416 | -18.2416 | yes |
| Sweep_15m_short | -130.2679 | -130.2679 | yes |
| MSS_1m_long | -219.8319 | -219.8319 | yes |
| MSS_1m_short | -455.8624 | -455.8624 | yes |
| MSS_5m_long | -12.1885 | -12.1885 | yes |
| MSS_5m_short | -38.8829 | -38.8829 | yes |
| MSS_15m_long | 35.0089 | 35.0089 | yes |
| MSS_15m_short | 8.2349 | 8.2349 | yes |

---

Preregistration: `backtests/zeus-ict-2026-07/concept_survey/PREREG.md` (frozen 2026-07-20, before any result was computed). Data: single-vendor Databento NQ 1m (`data/real_futures/NQ_databento_1m_5y.parquet`), window 2024-06-22 -> 2026-06-22, TRAIN=first 12mo, HOLDOUT=last 12mo. N=36 (6 concepts x 3 TFs x 2 directions), fixed a priori.

## 1. Headline
- Gate A (holdout PF>1.0 & expectancy>0): **8/36**
- Gate B (BH-FDR q=0.10 across all 36, one-sided block-bootstrap p): **0/36** (BH cutoff p = None)
- Gate A+B (both required to reach Gate C): **0/36**
- Gate C (beats randomized-entry null 95th pctile of total R -- 1000 runs for any A+B survivor, 200-run global null otherwise): **0/36**

**No cell survived all three statistical gates. The survey found nothing deployable — this is an acceptable, honestly-reported result, not a failure of the harness.**

## 2. Null expectation vs observed (Gate B/C context)
- Observed cells with HOLDOUT PF>1.2: **0/36**.
- Expected cells clearing PF>1.2 under the randomized-entry null (sum, across all 36 cells, of that cell's own null-run fraction with PF>1.2 -- i.e. the false-positive yield the SAME execution template would produce from bar-selection luck alone): **0.3/36**.
- Gap (observed minus null-expected): **-0.3**. This gap is small -- treat the per-cell Gate C outcomes as the only reliable signal; in aggregate the observed PF>1.2 rate is close to what bar-selection luck alone would produce.
- Per-cell 200-run (1000-run for A+B survivors) null total-R and null-PF distributions, and the observed-vs-null-p95 outcome, are in `gate_c_result.json` for every cell, not just survivors (per PREREG §Gate B/C).

## 3. BH-FDR p-value ladder (q=0.10, N=36)

| rank | cell | p | BH threshold | passes |
|---|---|---|---|---|
| 1 | MSS_15m_long | 0.04420 | 0.00278 |  |
| 2 | Breaker_15m_short | 0.14070 | 0.00556 |  |
| 3 | IFVG_15m_short | 0.18080 | 0.00833 |  |
| 4 | FVG_5m_short | 0.24060 | 0.01111 |  |
| 5 | FVG_15m_long | 0.32740 | 0.01389 |  |
| 6 | MSS_15m_short | 0.32970 | 0.01667 |  |
| 7 | OB_15m_long | 0.39660 | 0.01944 |  |
| 8 | OB_5m_long | 0.47100 | 0.02222 |  |
| 9 | FVG_15m_short | 0.57770 | 0.02500 |  |
| 10 | Sweep_15m_long | 0.64910 | 0.02778 |  |
| 11 | MSS_5m_long | 0.65400 | 0.03056 |  |
| 12 | FVG_5m_long | 0.66080 | 0.03333 |  |
| 13 | Breaker_5m_short | 0.68490 | 0.03611 |  |
| 14 | Breaker_15m_long | 0.69640 | 0.03889 |  |
| 15 | Sweep_5m_long | 0.75770 | 0.04167 |  |
| 16 | IFVG_15m_long | 0.76510 | 0.04444 |  |
| 17 | Breaker_5m_long | 0.78330 | 0.04722 |  |
| 18 | MSS_5m_short | 0.85650 | 0.05000 |  |
| 19 | OB_15m_short | 0.92820 | 0.05278 |  |
| 20 | IFVG_5m_long | 0.96950 | 0.05556 |  |
| 21 | MSS_1m_long | 0.98480 | 0.05833 |  |
| 22 | OB_5m_short | 0.98720 | 0.06111 |  |
| 23 | Sweep_15m_short | 0.99290 | 0.06389 |  |
| 24 | IFVG_5m_short | 0.99610 | 0.06667 |  |
| 25 | Sweep_5m_short | 0.99900 | 0.06944 |  |
| 26 | FVG_1m_long | 1.00000 | 0.07222 |  |
| 27 | FVG_1m_short | 1.00000 | 0.07500 |  |
| 28 | IFVG_1m_long | 1.00000 | 0.07778 |  |
| 29 | IFVG_1m_short | 1.00000 | 0.08056 |  |
| 30 | OB_1m_long | 1.00000 | 0.08333 |  |
| 31 | OB_1m_short | 1.00000 | 0.08611 |  |
| 32 | Breaker_1m_long | 1.00000 | 0.08889 |  |
| 33 | Breaker_1m_short | 1.00000 | 0.09167 |  |
| 34 | Sweep_1m_long | 1.00000 | 0.09444 |  |
| 35 | Sweep_1m_short | 1.00000 | 0.09722 |  |
| 36 | MSS_1m_short | 1.00000 | 0.10000 |  |

## 4. Per-cell table: TRAIN | HOLDOUT | LIVE-ACHIEVABLE (Gate A+B+C+D survivors get the live column)

| cell | TRAIN n/PF/exp | HOLDOUT n/PF/exp | Gate A | Gate B (p) | Gate C (beats null) | LIVE n/PF/exp (survivors) |
|---|---|---|---|---|---|---|
| FVG_1m_long | 13920/0.679/-0.328 | 13824/0.741/-0.260 | fail | 1.0000 | - | - |
| FVG_1m_short | 13697/0.699/-0.304 | 13452/0.732/-0.269 | fail | 1.0000 | - | - |
| FVG_5m_long | 2339/0.979/-0.019 | 2342/0.979/-0.019 | fail | 0.6608 | - | - |
| FVG_5m_short | 2163/0.943/-0.050 | 2175/1.042/0.036 | PASS | 0.2406 | - | - |
| FVG_15m_long | 737/1.077/0.064 | 740/1.042/0.035 | PASS | 0.3274 | - | - |
| FVG_15m_short | 648/1.186/0.147 | 635/0.982/-0.015 | fail | 0.5777 | - | - |
| IFVG_1m_long | 11966/0.655/-0.356 | 11859/0.698/-0.308 | fail | 1.0000 | - | - |
| IFVG_1m_short | 12145/0.653/-0.363 | 12120/0.666/-0.348 | fail | 1.0000 | - | - |
| IFVG_5m_long | 1895/0.830/-0.155 | 1852/0.886/-0.104 | fail | 0.9695 | - | - |
| IFVG_5m_short | 2083/0.890/-0.100 | 2090/0.870/-0.120 | fail | 0.9961 | - | - |
| IFVG_15m_long | 584/0.970/-0.025 | 567/0.922/-0.067 | fail | 0.7651 | - | - |
| IFVG_15m_short | 648/1.043/0.037 | 645/1.120/0.102 | PASS | 0.1808 | - | - |
| OB_1m_long | 7248/0.706/-0.236 | 7381/0.781/-0.173 | fail | 1.0000 | - | - |
| OB_1m_short | 7153/0.711/-0.240 | 7264/0.742/-0.212 | fail | 1.0000 | - | - |
| OB_5m_long | 1519/0.894/-0.074 | 1482/1.004/0.003 | PASS | 0.4710 | - | - |
| OB_5m_short | 1570/1.003/0.002 | 1536/0.877/-0.092 | fail | 0.9872 | - | - |
| OB_15m_long | 578/1.167/0.106 | 568/1.025/0.017 | PASS | 0.3966 | - | - |
| OB_15m_short | 538/1.021/0.014 | 532/0.844/-0.117 | fail | 0.9282 | - | - |
| Breaker_1m_long | 5185/0.747/-0.212 | 5252/0.772/-0.190 | fail | 1.0000 | - | - |
| Breaker_1m_short | 5101/0.717/-0.237 | 5302/0.736/-0.222 | fail | 1.0000 | - | - |
| Breaker_5m_long | 1081/0.882/-0.091 | 1065/0.949/-0.038 | fail | 0.7833 | - | - |
| Breaker_5m_short | 1018/1.073/0.052 | 996/0.968/-0.024 | fail | 0.6849 | - | - |
| Breaker_15m_long | 368/0.958/-0.032 | 355/0.937/-0.047 | fail | 0.6964 | - | - |
| Breaker_15m_short | 367/0.959/-0.029 | 370/1.141/0.101 | PASS | 0.1407 | - | - |
| Sweep_1m_long | 15270/0.912/-0.050 | 15475/0.908/-0.054 | fail | 1.0000 | - | - |
| Sweep_1m_short | 15572/0.919/-0.048 | 15598/0.899/-0.062 | fail | 1.0000 | - | - |
| Sweep_5m_long | 3494/0.962/-0.021 | 3449/0.973/-0.016 | fail | 0.7577 | - | - |
| Sweep_5m_short | 3575/0.941/-0.035 | 3783/0.884/-0.073 | fail | 0.9990 | - | - |
| Sweep_15m_long | 1171/1.014/0.008 | 1149/0.972/-0.016 | fail | 0.6491 | - | - |
| Sweep_15m_short | 1208/0.870/-0.077 | 1328/0.844/-0.098 | fail | 0.9929 | - | - |
| MSS_1m_long | 10263/0.833/-0.047 | 9611/0.921/-0.023 | fail | 0.9848 | - | - |
| MSS_1m_short | 10120/0.844/-0.044 | 9950/0.847/-0.046 | fail | 1.0000 | - | - |
| MSS_5m_long | 2074/0.944/-0.015 | 2074/0.980/-0.006 | fail | 0.6540 | - | - |
| MSS_5m_short | 2045/0.938/-0.017 | 1987/0.934/-0.020 | fail | 0.8565 | - | - |
| MSS_15m_long | 711/1.115/0.029 | 747/1.182/0.047 | PASS | 0.0442 | - | - |
| MSS_15m_short | 734/1.052/0.014 | 678/1.041/0.012 | PASS | 0.3297 | - | - |

## 5. Quarterly walk-forward sign stability (8 quarters across the 2y window)

(no Gate A+B+C or Gate A+B survivors -- showing the 8 Gate-A-only cells for context; none of these cleared Gate B/C)

| cell | positive quarters / 8 | sign sequence |
|---|---|---|
| FVG_5m_short | 3/8 | --+-+-+- |
| FVG_15m_long | 6/8 | ++-++-++ |
| IFVG_15m_short | 5/8 | ++--+++- |
| OB_5m_long | 2/8 | -----+-+ |
| OB_15m_long | 6/8 | +-++-+++ |
| Breaker_15m_short | 5/8 | -+--++++ |
| MSS_15m_long | 6/8 | ++-+++-+ |
| MSS_15m_short | 5/8 | --+++++- |

## 6. Ranked survivor shortlist

**Empty. No cell passed Gate A + Gate B (BH-FDR q=0.10) + Gate C (randomized-entry null).**

## 7. Correlation matrix (daily-R Pearson, holdout)

| | ProfileA_OTE | VPC_ProfileB |
|---|---|---|
| ProfileA_OTE | 1.000 | 0.126 |
| VPC_ProfileB | 0.126 | 1.000 |

Profile A (achievable, in-window) n=74; VPC/Profile B (in-window) n=98.

## 8. Graveyard (cause of death)

| cell | cause of death |
|---|---|
| FVG_1m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| FVG_1m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| FVG_5m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| FVG_5m_short | FDR miss (Gate B: p=0.2406 > BH cutoff None) |
| FVG_15m_long | FDR miss (Gate B: p=0.3274 > BH cutoff None) |
| FVG_15m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| IFVG_1m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| IFVG_1m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| IFVG_5m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| IFVG_5m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| IFVG_15m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| IFVG_15m_short | FDR miss (Gate B: p=0.1808 > BH cutoff None) |
| OB_1m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| OB_1m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| OB_5m_long | FDR miss (Gate B: p=0.4710 > BH cutoff None) |
| OB_5m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| OB_15m_long | FDR miss (Gate B: p=0.3966 > BH cutoff None) |
| OB_15m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Breaker_1m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Breaker_1m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Breaker_5m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Breaker_5m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Breaker_15m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Breaker_15m_short | FDR miss (Gate B: p=0.1407 > BH cutoff None) |
| Sweep_1m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Sweep_1m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Sweep_5m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Sweep_5m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Sweep_15m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| Sweep_15m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| MSS_1m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| MSS_1m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| MSS_5m_long | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| MSS_5m_short | holdout collapse (Gate A: PF<=1.0 or expectancy<=0) |
| MSS_15m_long | FDR miss (Gate B: p=0.0442 > BH cutoff None) |
| MSS_15m_short | FDR miss (Gate B: p=0.3297 > BH cutoff None) |

## 9. Documented literal-reading resolutions

- **Gate B correction scope**: one-sided block-bootstrap p-values computed for ALL 36 cells
  (not just Gate-A survivors); BH-FDR (q=0.10) applied across the full N=36 ladder, per PREREG
  §4/§5/§7's repeated "across all N=36 cells." A cell needs Gate A AND Gate B to reach Gate C.
- **Gate B block length**: block length (in trades) = round(5 x that cell's own holdout
  trades-per-day), trades-per-day = cell's holdout n / 313 (unique ET calendar days with data
  in the holdout window) — "block length ~ weekly" read as 5 TRADING days of THAT cell's own
  trade cadence (PREREG's explicit wording), not 5 calendar days of raw time.
- **Gate C entry count**: "same number of entries" read as the real cell's REALIZED holdout
  trade count n (an "entry" = an executed position), not the raw pre-filter signal count.
- **Order Block "last opposing candle immediately before a displacement candle"**: read
  literally as candle i-1 exactly (no backward scan). If i-1 is not opposite-colored, no OB
  forms at that displacement bar (this is disclosed as a strict reading, not a scan-back rule).
- **IFVG inversion search horizon**: PREREG states no explicit window for "far edge closed
  through inverts"; bounded to 100 signal-TF bars, borrowing the Breaker Block's explicit
  fail-window (PREREG §6.4) for consistency and to keep detection O(n).
- **Sweep/MSS "most recent confirmed swing level"**: read as the level known as of the PRIOR
  bar (must pre-exist the bar that acts on it); the break/reclaim bar's own close is compared
  same-bar (matches the cited code's own elementwise convention).
- **MSS/BOS firing**: fires once per break (transition from not-broken to broken), not on every
  bar price remains beyond the level.
- **EOD flat / exchange day**: CME session boundary taken as 17:00 ET; a bar's trading day rolls
  forward at/after 17:00 ET; EOD-flat cutoff = 16:55 ET of the SIGNAL's (conf_ts) exchange day,
  applied to both the limit-order lifetime clock and the exit-management scan.
- **Window/split boundaries**: treated as UTC calendar timestamps (PREREG does not specify a tz
  for 2024-06-22 / 2025-06-22 / 2026-06-22).
- **Gate D**: "signal surfaces at first poll >= confirmation instant" (5m poll cadence);
  "limit entries placed AT that poll" -> the order's fill-search window is re-walked starting at
  poll_ts (not conf_ts), with the SAME absolute lifetime/EOD end anchored to conf_ts. The literal
  10-minute certified_gate staleness test is ALSO computed and reported, but is structurally
  ~0% for this survey: unlike Profile A's multi-stage internal state machine, every concept here
  has a single-instant confirmation with no extra internal lag, so the only latency source is the
  <=5-minute poll cadence itself — always under the 10-minute threshold. The substantive
  deployability effect is the poll-delay re-walk (a trade can be missed/repriced by minutes).
- **Same-bar fill/invalidation resolution (v2 correction, audited 2026-07-20)**: for LIMIT-mode
  entries, when the entry-touch and invalidation/stop-touch bars are the SAME 1m bar, the order
  is treated as FILLED at entry_price and immediately STOPPED at stop_price on that bar (a real
  loss), not cancelled -- this is the "stop-fills-first on ambiguous bars" convention (PREREG §3)
  extended to the pre-fill phase. Invalidation on a bar STRICTLY BEFORE the entry is ever touched
  remains a legitimate cancel. See the CORRECTION NOTICE at the top of this report.

## 10. Anti-pattern compliance
- No train/full-window number presented as a finding above (train shown only for context alongside holdout/live-achievable).
- No per-concept tuning, no sweeps, no composites — one fixed execution template for all 36 cells.
- Single-vendor Databento data only; no other data file read by the harness.
- Survey only: no arming, no change to any existing frozen edge, no LIVE HOLD change.
