# 05 -- VPC fill/slippage/cost/entry-realism stress tests

RESEARCH ONLY. LIVE HOLD ACTIVE. STANDALONE VPC(600,4) and PORTFOLIO (A@600/6+VPC@600/4) only. Reuses `tools_salvage_stress.py` damage functions (dmg_slip/dmg_partial/dmg_chase) and generic funnel runner (run_eval_combo) verbatim; cost-ladder points re-derive VPC rows via the identical RT_COST override pattern `vpc_3pt_prior()` already uses. No existing file modified.

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

## Damage grids

(a) uniform slippage s in R {0.005, 0.01, 0.015, 0.02, 0.03, 0.042, 0.05, 0.075, 0.1}, both legs. (b) cost ladder: VPC RT_COST override at [('1x(0.75pt base)', 0.75), ('2x(1.5pt)', 1.5), ('3x(2.25pt)', 2.25)] (base=0.75pt per nq_vwap_pullback.RT_COST; the task's cited '3pt harsh' row is a DIFFERENT flat absolute cost, not '3x', quoted separately below). (c) winners' partial fill f in {0.75, 0.5, 0.25}, both legs. (d) VPC entry-realism chase ladder (VPC legs only): ['native', '+1tick(0.25pt)', '+2tick(0.5pt)', '+0.5pt', '+1pt'] -- '+2tick(0.5pt)' and '+0.5pt' are IDENTICAL by construction (NQ/MNQ tick=0.25pt) and both computed as an internal consistency check.

VPC trade-count invariance check across the cost ladder (n must stay 408 -- flat-cost shift cannot change entries/exits): [('1x(0.75pt base)', 408), ('2x(1.5pt)', 408), ('3x(2.25pt)', 408)]

**Adverse-first assumption of the underlying walker** (from `vpc_apex_eval_sim.vpc_trades_rich`): every bar's MAE/MFE are marked from that bar's own High/Low every iteration BEFORE the stop-touch test is applied on the SAME bar's High/Low (`if H[j]>=stop / L[j]<=stop`) -- there is no intra-bar path model; if a bar's range spans the stop level the exit is charged at the stop price regardless of what path a favorable move might have taken first inside that bar. Standard conservative worst-case-within-the-bar assumption, unchanged.

## Full damage grid -- slippage / partial-fill / chase

| cell | cell_desc | family | damage | pass_pct | bust_pct | exp_pct | pass_count | eligible_starts | funded_per_slot_year | pf_dollar | pass_gt_bust |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| standalone | VPC(600,4) standalone | baseline | 0 | 10.8 | 2.8 | 86.3 | 42 | 388 | 1.39 | 1.331 | True |
| standalone | VPC(600,4) standalone | a_uniform_slip | 0.005 | 10.8 | 2.8 | 86.3 | 42 | 388 | 1.39 | 1.315 | True |
| standalone | VPC(600,4) standalone | a_uniform_slip | 0.01 | 10.8 | 2.8 | 86.3 | 42 | 388 | 1.39 | 1.3 | True |
| standalone | VPC(600,4) standalone | a_uniform_slip | 0.015 | 10.8 | 3.1 | 86.1 | 42 | 388 | 1.39 | 1.285 | True |
| standalone | VPC(600,4) standalone | a_uniform_slip | 0.02 | 10.8 | 3.6 | 85.6 | 42 | 388 | 1.39 | 1.27 | True |
| standalone | VPC(600,4) standalone | a_uniform_slip | 0.03 | 10.6 | 4.6 | 84.8 | 41 | 388 | 1.36 | 1.241 | True |
| standalone | VPC(600,4) standalone | a_uniform_slip | 0.042 | 10.3 | 5.7 | 84 | 40 | 388 | 1.33 | 1.208 | True |
| standalone | VPC(600,4) standalone | a_uniform_slip | 0.05 | 9.5 | 6.2 | 84.3 | 37 | 388 | 1.23 | 1.186 | True |
| standalone | VPC(600,4) standalone | a_uniform_slip | 0.075 | 9 | 7.7 | 83.2 | 35 | 388 | 1.17 | 1.121 | True |
| standalone | VPC(600,4) standalone | a_uniform_slip | 0.1 | 8.8 | 9.3 | 82 | 34 | 388 | 1.13 | 1.06 | False |
| standalone | VPC(600,4) standalone | c_partial_fill | 0.25 | 5.4 | 2.6 | 92 | 21 | 388 | 0.67 | 0.998 | True |
| standalone | VPC(600,4) standalone | c_partial_fill | 0.5 | 0 | 4.1 | 95.9 | 0 | 388 | 0 | 0.665 | False |
| standalone | VPC(600,4) standalone | c_partial_fill | 0.75 | 0 | 7 | 93 | 0 | 388 | 0 | 0.333 | False |
| standalone | VPC(600,4) standalone | d_entry_realism | native | 10.8 | 2.8 | 86.3 | 42 | 388 | 1.39 | 1.331 | True |
| standalone | VPC(600,4) standalone | d_entry_realism | +1tick(0.25pt) | 10.8 | 2.8 | 86.3 | 42 | 388 | 1.39 | 1.322 | True |
| standalone | VPC(600,4) standalone | d_entry_realism | +2tick(0.5pt) | 10.8 | 2.8 | 86.3 | 42 | 388 | 1.39 | 1.314 | True |
| standalone | VPC(600,4) standalone | d_entry_realism | +0.5pt | 10.8 | 2.8 | 86.3 | 42 | 388 | 1.39 | 1.314 | True |
| standalone | VPC(600,4) standalone | d_entry_realism | +1pt | 10.8 | 2.8 | 86.3 | 42 | 388 | 1.39 | 1.297 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | baseline | 0 | 27.8 | 15.5 | 56.7 | 190 | 684 | 4.04 | 1.362 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | a_uniform_slip | 0.005 | 25.9 | 15.9 | 58.2 | 177 | 684 | 3.73 | 1.347 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | a_uniform_slip | 0.01 | 24.7 | 17.1 | 58.2 | 169 | 684 | 3.56 | 1.333 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | a_uniform_slip | 0.015 | 23.8 | 17.3 | 58.9 | 163 | 684 | 3.43 | 1.318 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | a_uniform_slip | 0.02 | 23.4 | 17.4 | 59.2 | 160 | 684 | 3.35 | 1.304 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | a_uniform_slip | 0.03 | 22.1 | 18.3 | 59.6 | 151 | 684 | 3.17 | 1.276 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | a_uniform_slip | 0.042 | 21.2 | 18.9 | 59.9 | 145 | 684 | 3.04 | 1.243 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | a_uniform_slip | 0.05 | 20 | 22.5 | 57.5 | 137 | 684 | 2.91 | 1.222 | False |
| portfolio | A(600,6)+VPC(600,4) portfolio | a_uniform_slip | 0.075 | 17 | 24.4 | 58.6 | 116 | 684 | 2.45 | 1.158 | False |
| portfolio | A(600,6)+VPC(600,4) portfolio | a_uniform_slip | 0.1 | 15.6 | 27.6 | 56.7 | 107 | 684 | 2.29 | 1.099 | False |
| portfolio | A(600,6)+VPC(600,4) portfolio | c_partial_fill | 0.25 | 8.9 | 19.4 | 71.6 | 61 | 684 | 1.2 | 1.022 | False |
| portfolio | A(600,6)+VPC(600,4) portfolio | c_partial_fill | 0.5 | 0.4 | 28.4 | 71.2 | 3 | 684 | 0.06 | 0.681 | False |
| portfolio | A(600,6)+VPC(600,4) portfolio | c_partial_fill | 0.75 | 0 | 44.2 | 55.8 | 0 | 684 | 0 | 0.341 | False |
| portfolio | A(600,6)+VPC(600,4) portfolio | d_entry_realism | native | 27.8 | 15.5 | 56.7 | 190 | 684 | 4.04 | 1.362 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | d_entry_realism | +1tick(0.25pt) | 26.3 | 15.5 | 58.2 | 180 | 684 | 3.8 | 1.358 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | d_entry_realism | +2tick(0.5pt) | 26.3 | 15.9 | 57.7 | 180 | 684 | 3.81 | 1.355 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | d_entry_realism | +0.5pt | 26.3 | 15.9 | 57.7 | 180 | 684 | 3.81 | 1.355 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | d_entry_realism | +1pt | 26.2 | 16.1 | 57.7 | 179 | 684 | 3.79 | 1.347 | True |

## Full damage grid -- cost ladder

| cell | cell_desc | family | damage | pass_pct | bust_pct | exp_pct | pass_count | eligible_starts | funded_per_slot_year | pf_dollar | pass_gt_bust |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| standalone | VPC(600,4) standalone | b_cost_ladder | 1x(0.75pt base) | 10.8 | 2.8 | 86.3 | 42 | 388 | 1.39 | 1.331 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | b_cost_ladder | 1x(0.75pt base) | 27.8 | 15.5 | 56.7 | 190 | 684 | 4.04 | 1.362 | True |
| standalone | VPC(600,4) standalone | b_cost_ladder | 2x(1.5pt) | 10.8 | 2.8 | 86.3 | 42 | 388 | 1.39 | 1.305 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | b_cost_ladder | 2x(1.5pt) | 26.2 | 15.9 | 57.9 | 179 | 684 | 3.78 | 1.351 | True |
| standalone | VPC(600,4) standalone | b_cost_ladder | 3x(2.25pt) | 10.8 | 3.4 | 85.8 | 42 | 388 | 1.39 | 1.28 | True |
| portfolio | A(600,6)+VPC(600,4) portfolio | b_cost_ladder | 3x(2.25pt) | 25.6 | 16.2 | 58.2 | 175 | 684 | 3.71 | 1.339 | True |

Cited reference (external, not re-derived here): {'n': 408, 'pf': 1.232, 'wr': 44.1, 'net': 4001.2}

## HEADLINE -- break points (PASS>BUST flip, linear-interpolated over the uniform-slippage grid, baseline=0 included)

| cell | cell_desc | family | flip_at |
| --- | --- | --- | --- |
| standalone | VPC(600,4) standalone | a_uniform_slip (s, R) | 0.0931 |
| portfolio | A(600,6)+VPC(600,4) portfolio | a_uniform_slip (s, R) | 0.0458 |

- **Standalone VPC(600,4) break point: 0.0931R**
- **Portfolio A(600,6)+VPC(600,4) break point: 0.0458R** -- verified against the salvage A6 precedent (`A(600,6)+VPC(600,4)`, identical cell/machinery, reports/new_edge_salvage_program/A6_salvage_fill_slippage_stress.md, cited flip_at = **0.0421**):

  | slip s (R) | this run pass/bust | A6 pass/bust | row match |
  |---|---|---|---|
  | 0.01 | 24.7/17.1 | 24.7/17.1 | MATCH |
  | 0.02 | 23.4/17.4 | 23.4/17.4 | MATCH |
  | 0.03 | 22.1/18.3 | 22.1/18.3 | MATCH |
  | 0.05 | 20.0/22.5 | 20.0/22.5 | MATCH |
  | 0.075 | 17.0/24.4 | 17.0/24.4 | MATCH |
  | 0.1 | 15.6/27.6 | 15.6/27.6 | MATCH |

  Row-for-row reproducibility at every slip level A6 itself tested: **ALL MATCH** (identical pass_pct/bust_pct at 0.01/0.02/0.03/0.05/0.075/0.10 confirms this run's machinery reproduces A6 exactly). The INTERPOLATED flip differs (0.0458R vs A6's cited 0.0421R) purely because this task's grid adds a directly-measured point at s=0.042 (pass=21.2/bust=18.9, margin still +2.3, i.e. NOT yet flipped) that sits between A6's own bracketing pair (0.03 margin +3.8, 0.05 margin -2.5) — A6's 0.0421R was a 2-point LINEAR interpolation across that 0.02R gap; this run's actual measurement at 0.042 shows the true curve is not linear there, so the denser grid resolves a more precise (and slightly HIGHER, i.e. slightly more robust) break point of 0.0458R. This is a resolution artifact of A6's sparser grid, not a reproduction failure — the underlying data at every shared point is identical.

- Does VPC standalone survive 0.015R? **YES** (pass>bust boolean at s=0.015). Does it survive 0.042R? **YES** (s=0.042).

- **VPC fragility vs Profile A solo**: A@1200/6 alone flip precedent = **0.0134R** (A6 C4, unfiltered-A(1200,6) alone). VPC standalone flips at **0.0931R**, portfolio at **0.0458R** -- both LESS fragile (higher flip) than A-alone.
- **VPC fragility vs the rejected throughput combos**: A6 C2 (A(1200,10)+VPC(600,4)) flip = **0.019R**, A6 C3 (A(1200,10)+VPC(400,4)) flip = **0.015R** (both rejected as fill-fragile). The recommended portfolio's own flip (0.0458R) sits well above that rejected band -- this is the mechanical basis for the recommended-vs-throughput sizing distinction (reused, not re-derived).

## PF freeze check: no cell/damage point anywhere breached PF>1.8.
