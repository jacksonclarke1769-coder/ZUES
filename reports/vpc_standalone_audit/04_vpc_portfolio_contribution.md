# 04 -- VPC portfolio-contribution anatomy

RESEARCH ONLY. LIVE HOLD ACTIVE. Reuses `tools_salvage_vpc_reeval.py` (ASR.build_events/day_rows/summarize_cell/event_pf) and `tools_salvage_stress.py` (damage/runner primitives) verbatim; no existing file modified. All windows 2022-2026 (the shared A+VPC window, matching the prior salvage-program C report convention).

Runtime: 24.2s.

## Firewall before/after

| file | sha256 before | sha256 after | match |
|---|---|---|---|
| config_eval_locked.py | `3ca389fc5a8a9fe47b844a6c77f6f13dc8b5c4564c135949b9a5c81e02df36e5` | `3ca389fc5a8a9fe47b844a6c77f6f13dc8b5c4564c135949b9a5c81e02df36e5` | UNCHANGED |
| config_funded_locked.py | `95276d506ec33330d46caee0223f7056d112021ab0f5f5797621cd9fdd3acbe4` | `95276d506ec33330d46caee0223f7056d112021ab0f5f5797621cd9fdd3acbe4` | UNCHANGED |
| config_defaults.py | `1cbbbe8a7bd438e19647a9e020b2bbdbe93878074b3249d8ea65653660562c22` | `1cbbbe8a7bd438e19647a9e020b2bbdbe93878074b3249d8ea65653660562c22` | UNCHANGED |
| auto_safety.py | `b7b05b423edd21f4dc707887f3e050b64699f7931b6f1dc3ab3213b73dade2bc` | `b7b05b423edd21f4dc707887f3e050b64699f7931b6f1dc3ab3213b73dade2bc` | UNCHANGED |

## Canaries

```
====================================================================================================
CANARIES
====================================================================================================

[1-3] VR.run_canaries() (reused verbatim):
====================================================================================================
CANARIES
====================================================================================================
1. VPC 408-trade signature: n=408 (expect 408), net=4919.178571pt (expect 4919.178571)  -> PASS
2a. Honest-A stream: n=583 (expect 583), PF=1.360600 (expect 1.360600)  -> PASS
2b. Honest-A internal cap-10 canary: got {'pass_pct': 31.4, 'bust_pct': 37.3, 'exp_pct': 31.2, 'med_days': 16, 'n': 525, 'e_ish': 404} vs expected {'pass_pct': 31.4, 'bust_pct': 37.3, 'exp_pct': 31.2, 'med_days': 16, 'n': 525}  -> PASS
3. Look-ahead spot-check (merge/sort cannot mutate either stream's own events; A poisoned 7x+999999, VPC events re-read unchanged): -> PASS
   (structural: VPC engine (nq_vwap_pullback/vpc_apex_eval_sim) takes no A inputs; honest-A engine (strategy_engine_profileA/run_d1c_real) takes no VPC inputs; the two streams are computed independently and only combined post-hoc by ts-sort.)
====================================================================================================
[all canaries PASS]
====================================================================================================

[4] task-pinned machine canary A: A@600/6 + VPC@600/4 (2022-2026 window):
  got pass=27.8 bust=15.5 exp=56.7 n=684 vs expected {'pass_pct': 27.8, 'bust_pct': 15.5, 'exp_pct': 56.7, 'n': 684}  -> PASS

[5] task-pinned machine canary B: A@1200/10 ALONE (2022-2026 window):
  got pass=32.6 bust=35.0 vs expected {'pass_pct': 32.6, 'bust_pct': 35.0}  -> PASS

[6] same-day reference-stats reproduction:
  got {'n_days': 701, 'same_day_corr': 0.164, 'dl_freq_pct': 9.3, 'tl_freq_pct': 53.9} vs expected {'n_days': 701, 'same_day_corr': 0.164, 'dl_freq_pct': 9.3, 'tl_freq_pct': 53.9}  -> PASS
====================================================================================================
[all canaries PASS]
====================================================================================================
```

## Part A -- six-row funnel-contribution table

`pf_dollar` = contract-sized dollar PF (existing funnel convention). `pf_R` / `wr_R_pct` / `totR` / `maxDD_R` = the MERGED R-stream (unit, size-invariant; see module docstring mapping note) -- trades that clear the row's own budget/cap sizing gate, reported in R-multiples, ts-sorted across both legs where both are present.

| label | a_bc | v_bc | pf_dollar | trades_per_week | same_day_corr | dl_freq_pct | tl_freq_pct | eligible_starts | pass_count | bust_count | exp_count | pass_pct | bust_pct | exp_pct | med_days_pass | worst_day_usd | funded_per_slot_year | n_trades_R | pf_R | wr_R_pct | totR | maxDD_R | py2022_pass_pct | py2023_pass_pct | py2024_pass_pct | py2025_pass_pct | py2026_pass_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A solo (600/6) | (600, 6) | - | 1.388 | 2.21 | 0.164 | 9.3 | 53.9 | 463 | 42 | 16 | 405 | 9.1 | 3.5 | 87.5 | 23 | -1000 | 1.14 | 513 | 1.343 | 45.2 | 75.94 | 10.18 | 2.9 | 0.9 | 6.9 | 18.2 | 29.7 |
| A solo (1200/10) | (1200, 10) | - | 1.442 | 2.21 | 0.164 | 9.3 | 53.9 | 463 | 151 | 162 | 150 | 32.6 | 35 | 32.4 | 16 | -1000 | 5.92 | 513 | 1.343 | 45.2 | 75.94 | 10.18 | 17.3 | 23.6 | 28.4 | 56.4 | 43.2 |
| VPC solo (600/4) | - | (600, 4) | 1.331 | 1.75 | 0.164 | 9.3 | 53.9 | 388 | 42 | 11 | 335 | 10.8 | 2.8 | 86.3 | 16 | -1000 | 1.39 | 404 | 1.36 | 44.8 | 54.66 | 9.07 | 4.7 | 4.6 | 14 | 16.9 | 17.9 |
| A+VPC recommended (600/6+600/4) | (600, 6) | (600, 4) | 1.362 | 3.95 | 0.164 | 9.3 | 53.9 | 684 | 190 | 106 | 388 | 27.8 | 15.5 | 56.7 | 18 | -1000 | 4.04 | 917 | 1.35 | 45 | 130.59 | 13.7 | 17.9 | 18.8 | 22.4 | 44.4 | 45.9 |
| Conservative (400/4+300/3) | (400, 4) | (300, 3) | 1.39 | 3.66 | 0.164 | 9.3 | 53.9 | 650 | 28 | 0 | 622 | 4.3 | 0 | 95.7 | 23 | -737 | 0.53 | 851 | 1.344 | 44.7 | 120.67 | 14.42 | 0.7 | 1.3 | 1.4 | 13.6 | 6.1 |
| Throughput (1200/10+600/4) | (1200, 10) | (600, 4) | 1.408 | 3.95 | 0.164 | 9.3 | 53.9 | 684 | 305 | 235 | 144 | 44.6 | 34.4 | 21.1 | 14 | -1000 | 8.99 | 917 | 1.35 | 45 | 130.59 | 13.7 | 39.1 | 30.6 | 36.2 | 68.8 | 52.5 |

## Part B -- day-level anatomy (2022-2026, unit-risk 1-contract day P&L)

Definitions (documented, no prior-art precedent beyond VR's own `unit_daily`/`same_day_stats`, stated explicitly per module docstring mapping note):

- n_days (union of A/VPC active days, 2022-2026): **701**
- days A trades: **475** | days VPC trades: **400** | days BOTH trade: **175**
- days BOTH LOSE (both unit-$ < 0): **65** -- split by VPC day-R magnitude: severe (VPC day-R <= -0.5R) = **44**, mild (VPC day-R > -0.5R) = **21**
- offset days (VPC net-positive while A net-negative, same day): **23**
- days VPC fires while A sleeps (VPC-active, A-inactive): **225** days / **227** VPC trades on those days -- WR **47.1%**, PF **1.26** (trade-level, unit $, does VPC survive when A is absent? -- see mechanical answers below)
- same-week joint-loss frequency: **46** / **198** both-active weeks = **23.2%** (of 229 total weeks with any activity)
- daily unit-$ P&L Pearson corr: union (all 701 days, VR reference reused verbatim) = **0.164** | co-active only (175 both-trade days) = **0.358**

## Mechanical answers (numbers, no spin)

**Is VPC's portfolio value mainly expiry-reduction vs pass-lift vs bust-change (recommended sizing A@600/6 alone -> +VPC@600/4)?**
- A alone: pass=9.1% bust=3.5% exp=87.5%
- combo:   pass=27.8% bust=15.5% exp=56.7%
- deltas:  Δpass=+18.7pp  Δbust=+12.0pp  Δexpire=-30.8pp
- largest-magnitude delta (mechanical, |Δ| ranked): **expire** -- VPC's portfolio value is PRIMARILY expiry-reduction by magnitude, with pass-lift as the secondary contributor, partially offset by a bust increase (see next line).

**Does VPC increase bust materially at recommended sizing?** YES -- bust 3.5% -> 15.5% (Δ+12.0pp) at the EVAL side, A@600/6 alone vs +VPC@600/4 (2022-2026 window). Funded-side closest analogue (different, smaller budget scale by design): A@250/4 alone bust=0% -> +VPC@200/2 bust=0% (no funded-side bust delta at that combo; C_combined_portfolio_test.md, reused reference, not re-derived here).

**Does VPC survive when A is absent (VPC-fires-while-A-sleeps days)?** YES -- WR 47.1%, PF 1.26 on the 227 VPC trades fired on A-sleeping days.

## PF freeze check: no cell exceeded PF>1.8.
