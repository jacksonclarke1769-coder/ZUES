# A6 — Fill/Slippage Stress on Surviving Salvage Candidates

RESEARCH ONLY. LIVE HOLD ACTIVE. Pure execution over pinned mechanics (`tools_salvage_vpc_reeval.py` / `tools_salvage_track_a.py`, imported not reimplemented). No new modeling choices beyond the explicit damage-grid formulas in the module docstring. No winner-picking beyond the mechanical PASS>BUST boolean.

Runtime: 53.6s.

## Firewall before/after

| file | sha256 before | sha256 after | match |
|---|---|---|---|
| config_eval_locked.py | `3ca389fc5a8a9fe47b844a6c77f6f13dc8b5c4564c135949b9a5c81e02df36e5` | `3ca389fc5a8a9fe47b844a6c77f6f13dc8b5c4564c135949b9a5c81e02df36e5` | UNCHANGED| 
| config_funded_locked.py | `95276d506ec33330d46caee0223f7056d112021ab0f5f5797621cd9fdd3acbe4` | `95276d506ec33330d46caee0223f7056d112021ab0f5f5797621cd9fdd3acbe4` | UNCHANGED| 
| config_defaults.py | `1cbbbe8a7bd438e19647a9e020b2bbdbe93878074b3249d8ea65653660562c22` | `1cbbbe8a7bd438e19647a9e020b2bbdbe93878074b3249d8ea65653660562c22` | UNCHANGED| 
| auto_safety.py | `b7b05b423edd21f4dc707887f3e050b64699f7931b6f1dc3ab3213b73dade2bc` | `b7b05b423edd21f4dc707887f3e050b64699f7931b6f1dc3ab3213b73dade2bc` | UNCHANGED| 

## Canaries

```
====================================================================================================
CANARIES
====================================================================================================

[0] base-machinery structural canaries (reused verbatim):
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
  -> VR.run_canaries: PASS
  -> TA.check_canaries: PASS

[1-4] reproduce the four pinned UNDAMAGED reference rows exactly:
  C1 A(600,6)+VPC(600,4): pass_pct=27.8(ref 27.8) bust_pct=15.5(ref 15.5) exp_pct=56.7(ref 56.7) eligible_starts=684(ref 684) -> PASS
  C2 A(1200,10)+VPC(600,4): pass_pct=44.6(ref 44.6) bust_pct=34.4(ref 34.4) exp_pct=21.1(ref 21.1) eligible_starts=684(ref 684) -> PASS
  C4 unfiltered-A(1200,6): pass_pct=23.4(ref 23.4) bust_pct=20.7(ref 20.7) exp_pct=55.9(ref 55.9) eligible_starts=623(ref 623) -> PASS
  C5 VPC(800,6): pass_pct=20.1(ref 20.1) bust_pct=16.7(ref 16.7) exp_pct=63.2(ref 63.2) eligible_starts=389(ref 389) -> PASS
====================================================================================================
[all canaries PASS] proceeding to damage grids.
====================================================================================================
```

## Cell definitions

| cell | description |
|---|---|
| C1 | A(600,6)+VPC(600,4) |
| C2 | A(1200,10)+VPC(600,4) |
| C3 | A(1200,10)+VPC(400,4) |
| C4 | unfiltered-A(1200,6) alone |
| C5 | VPC(800,6) alone |
| F1 (FUNDED) | kept-A(250,4) alone |
| F2 (FUNDED) | kept-A(250,4)+VPC(200,2) |

Damage grids: (a) uniform slippage s in R {0.01,0.02,0.03,0.05,0.075,0.10} on both legs; (b) winners' partial fill f in {0.75,0.50,0.25} on both legs; (c) VPC-chase extra entry slippage in {0.5,1.0}pt (VPC legs only, A untouched); (d) A-only control s=0.05R (A legs only, VPC untouched, combo cells only). FUNDED cells: grid (a) only at s in {0.02,0.05}.

## Full damage grid (EVAL cells)

| cell | cell_desc | family | damage | pass_pct | bust_pct | exp_pct | pass_count | eligible_starts | funded_per_slot_year | pf_dollar | pass_gt_bust |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | A(600,6)+VPC(600,4) | baseline | 0 | 27.8 | 15.5 | 56.7 | 190 | 684 | 4.04 | 1.362 | True |
| C1 | A(600,6)+VPC(600,4) | a_uniform_slip | 0.01 | 24.7 | 17.1 | 58.2 | 169 | 684 | 3.56 | 1.333 | True |
| C1 | A(600,6)+VPC(600,4) | a_uniform_slip | 0.02 | 23.4 | 17.4 | 59.2 | 160 | 684 | 3.35 | 1.304 | True |
| C1 | A(600,6)+VPC(600,4) | a_uniform_slip | 0.03 | 22.1 | 18.3 | 59.6 | 151 | 684 | 3.17 | 1.276 | True |
| C1 | A(600,6)+VPC(600,4) | a_uniform_slip | 0.05 | 20 | 22.5 | 57.5 | 137 | 684 | 2.91 | 1.222 | False |
| C1 | A(600,6)+VPC(600,4) | a_uniform_slip | 0.075 | 17 | 24.4 | 58.6 | 116 | 684 | 2.45 | 1.158 | False |
| C1 | A(600,6)+VPC(600,4) | a_uniform_slip | 0.1 | 15.6 | 27.6 | 56.7 | 107 | 684 | 2.29 | 1.099 | False |
| C1 | A(600,6)+VPC(600,4) | b_partial_fill | 0.25 | 8.9 | 19.4 | 71.6 | 61 | 684 | 1.2 | 1.022 | False |
| C1 | A(600,6)+VPC(600,4) | b_partial_fill | 0.5 | 0.4 | 28.4 | 71.2 | 3 | 684 | 0.06 | 0.681 | False |
| C1 | A(600,6)+VPC(600,4) | b_partial_fill | 0.75 | 0 | 44.2 | 55.8 | 0 | 684 | 0 | 0.341 | False |
| C1 | A(600,6)+VPC(600,4) | c_vpc_chase | 0.5 | 26.3 | 15.9 | 57.7 | 180 | 684 | 3.81 | 1.355 | True |
| C1 | A(600,6)+VPC(600,4) | c_vpc_chase | 1 | 26.2 | 16.1 | 57.7 | 179 | 684 | 3.79 | 1.347 | True |
| C1 | A(600,6)+VPC(600,4) | d_a_only_control | 0.05 | 23.4 | 19.9 | 56.7 | 160 | 684 | 3.4 | 1.286 | True |
| C2 | A(1200,10)+VPC(600,4) | baseline | 0 | 44.6 | 34.4 | 21.1 | 305 | 684 | 8.99 | 1.408 | True |
| C2 | A(1200,10)+VPC(600,4) | a_uniform_slip | 0.01 | 42.8 | 38.2 | 19 | 293 | 684 | 8.7 | 1.378 | True |
| C2 | A(1200,10)+VPC(600,4) | a_uniform_slip | 0.02 | 40.4 | 40.9 | 18.7 | 276 | 684 | 8.23 | 1.348 | False |
| C2 | A(1200,10)+VPC(600,4) | a_uniform_slip | 0.03 | 39.2 | 42.4 | 18.4 | 268 | 684 | 8.06 | 1.32 | False |
| C2 | A(1200,10)+VPC(600,4) | a_uniform_slip | 0.05 | 36.5 | 44.9 | 18.6 | 250 | 684 | 7.55 | 1.265 | False |
| C2 | A(1200,10)+VPC(600,4) | a_uniform_slip | 0.075 | 33.5 | 45.9 | 20.6 | 229 | 684 | 6.78 | 1.2 | False |
| C2 | A(1200,10)+VPC(600,4) | a_uniform_slip | 0.1 | 28.9 | 51.8 | 19.3 | 198 | 684 | 5.9 | 1.138 | False |
| C2 | A(1200,10)+VPC(600,4) | b_partial_fill | 0.25 | 20.6 | 42.8 | 36.5 | 141 | 684 | 3.52 | 1.056 | False |
| C2 | A(1200,10)+VPC(600,4) | b_partial_fill | 0.5 | 3.9 | 53.4 | 42.7 | 27 | 684 | 0.63 | 0.704 | False |
| C2 | A(1200,10)+VPC(600,4) | b_partial_fill | 0.75 | 0 | 77.8 | 22.2 | 0 | 684 | 0 | 0.352 | False |
| C2 | A(1200,10)+VPC(600,4) | c_vpc_chase | 0.5 | 44.4 | 34.6 | 20.9 | 304 | 684 | 8.96 | 1.403 | True |
| C2 | A(1200,10)+VPC(600,4) | c_vpc_chase | 1 | 44.3 | 35.1 | 20.6 | 303 | 684 | 8.93 | 1.397 | True |
| C2 | A(1200,10)+VPC(600,4) | d_a_only_control | 0.05 | 38.3 | 43.7 | 18 | 262 | 684 | 7.87 | 1.309 | False |
| C3 | A(1200,10)+VPC(400,4) | baseline | 0 | 41.5 | 34.6 | 23.9 | 281 | 677 | 7.88 | 1.421 | True |
| C3 | A(1200,10)+VPC(400,4) | a_uniform_slip | 0.01 | 39.7 | 38.1 | 22.2 | 269 | 677 | 7.62 | 1.39 | True |
| C3 | A(1200,10)+VPC(400,4) | a_uniform_slip | 0.02 | 38 | 39.6 | 22.5 | 257 | 677 | 7.27 | 1.361 | False |
| C3 | A(1200,10)+VPC(400,4) | a_uniform_slip | 0.03 | 36.6 | 41.2 | 22.2 | 248 | 677 | 6.97 | 1.333 | False |
| C3 | A(1200,10)+VPC(400,4) | a_uniform_slip | 0.05 | 32.9 | 45.5 | 21.6 | 223 | 677 | 6.28 | 1.278 | False |
| C3 | A(1200,10)+VPC(400,4) | a_uniform_slip | 0.075 | 29.4 | 47.7 | 22.9 | 199 | 677 | 5.63 | 1.212 | False |
| C3 | A(1200,10)+VPC(400,4) | a_uniform_slip | 0.1 | 26.1 | 52.4 | 21.4 | 177 | 677 | 5.08 | 1.151 | False |
| C3 | A(1200,10)+VPC(400,4) | b_partial_fill | 0.25 | 18.2 | 41.9 | 39.9 | 123 | 677 | 2.96 | 1.065 | False |
| C3 | A(1200,10)+VPC(400,4) | b_partial_fill | 0.5 | 3.4 | 49.3 | 47.3 | 23 | 677 | 0.52 | 0.71 | False |
| C3 | A(1200,10)+VPC(400,4) | b_partial_fill | 0.75 | 0 | 68.5 | 31.5 | 0 | 677 | 0 | 0.355 | False |
| C3 | A(1200,10)+VPC(400,4) | c_vpc_chase | 0.5 | 41.5 | 34.6 | 23.9 | 281 | 677 | 7.88 | 1.417 | True |
| C3 | A(1200,10)+VPC(400,4) | c_vpc_chase | 1 | 41.2 | 34.7 | 24.1 | 279 | 677 | 7.81 | 1.413 | True |
| C3 | A(1200,10)+VPC(400,4) | d_a_only_control | 0.05 | 34.3 | 44.9 | 20.8 | 232 | 677 | 6.59 | 1.308 | False |
| C4 | unfiltered-A(1200,6) alone | baseline | 0 | 23.4 | 20.7 | 55.9 | 146 | 623 | 3.4909 | 1.405 | True |
| C4 | unfiltered-A(1200,6) alone | a_uniform_slip | 0.01 | 23 | 22 | 55.1 | 143 | 623 | 3.4319 | 1.375 | True |
| C4 | unfiltered-A(1200,6) alone | a_uniform_slip | 0.02 | 22 | 23.9 | 54.1 | 137 | 623 | 3.2847 | 1.346 | False |
| C4 | unfiltered-A(1200,6) alone | a_uniform_slip | 0.03 | 21.5 | 25.4 | 53.1 | 134 | 623 | 3.2217 | 1.318 | False |
| C4 | unfiltered-A(1200,6) alone | a_uniform_slip | 0.05 | 17.5 | 27 | 55.5 | 109 | 623 | 2.58 | 1.264 | False |
| C4 | unfiltered-A(1200,6) alone | a_uniform_slip | 0.075 | 15.6 | 29.5 | 54.9 | 97 | 623 | 2.3066 | 1.199 | False |
| C4 | unfiltered-A(1200,6) alone | a_uniform_slip | 0.1 | 13.6 | 31 | 55.4 | 85 | 623 | 2.03 | 1.139 | False |
| C4 | unfiltered-A(1200,6) alone | b_partial_fill | 0.25 | 9.6 | 20.5 | 69.8 | 60 | 623 | 1.3189 | 1.054 | False |
| C4 | unfiltered-A(1200,6) alone | b_partial_fill | 0.5 | 1.9 | 25.2 | 72.9 | 12 | 623 | 0.259 | 0.702 | False |
| C4 | unfiltered-A(1200,6) alone | b_partial_fill | 0.75 | 0 | 34.7 | 65.3 | 0 | 623 | 0 | 0.351 | False |
| C5 | VPC(800,6) alone | baseline | 0 | 20.1 | 16.7 | 63.2 | 78 | 389 | 2.9 | 1.364 | True |
| C5 | VPC(800,6) alone | a_uniform_slip | 0.01 | 18.8 | 17.2 | 64 | 73 | 389 | 2.7 | 1.333 | True |
| C5 | VPC(800,6) alone | a_uniform_slip | 0.02 | 18.5 | 18 | 63.5 | 72 | 389 | 2.66 | 1.302 | True |
| C5 | VPC(800,6) alone | a_uniform_slip | 0.03 | 18.3 | 18.8 | 63 | 71 | 389 | 2.62 | 1.272 | False |
| C5 | VPC(800,6) alone | a_uniform_slip | 0.05 | 17.2 | 22.9 | 59.9 | 67 | 389 | 2.5 | 1.216 | False |
| C5 | VPC(800,6) alone | a_uniform_slip | 0.075 | 16.5 | 25.4 | 58.1 | 64 | 389 | 2.43 | 1.149 | False |
| C5 | VPC(800,6) alone | a_uniform_slip | 0.1 | 15.7 | 26.7 | 57.6 | 61 | 389 | 2.32 | 1.086 | False |
| C5 | VPC(800,6) alone | b_partial_fill | 0.25 | 9.5 | 19.5 | 71 | 37 | 389 | 1.3 | 1.023 | False |
| C5 | VPC(800,6) alone | b_partial_fill | 0.5 | 2.1 | 23.4 | 74.6 | 8 | 389 | 0.27 | 0.682 | False |
| C5 | VPC(800,6) alone | b_partial_fill | 0.75 | 0 | 26 | 74 | 0 | 389 | 0 | 0.341 | False |
| C5 | VPC(800,6) alone | c_vpc_chase | 0.5 | 19.5 | 16.7 | 63.8 | 76 | 389 | 2.82 | 1.346 | True |
| C5 | VPC(800,6) alone | c_vpc_chase | 1 | 18.8 | 17.5 | 63.8 | 73 | 389 | 2.7 | 1.329 | True |

## Full damage grid (FUNDED cells, grid (a) only)

| cell | cell_desc | family | damage | n_starts | e_paid | bust_pct | med_months | med_paid | closed_max_pct | safety_net_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | kept-A(250,4) alone | a_uniform_slip | 0 | 42 | 7292 | 0 | 31.1 | 7346 | 69 | 100 |
| F1 | kept-A(250,4) alone | a_uniform_slip | 0.02 | 42 | 7253 | 0 | 33 | 7670 | 61.9 | 100 |
| F1 | kept-A(250,4) alone | a_uniform_slip | 0.05 | 42 | 4922 | 0 | 33.1 | 4989 | 4.8 | 100 |
| F2 | kept-A(250,4)+VPC(200,2) | a_uniform_slip | 0 | 42 | 8567 | 0 | 28.2 | 8758 | 73.8 | 100 |
| F2 | kept-A(250,4)+VPC(200,2) | a_uniform_slip | 0.02 | 42 | 8468 | 2.4 | 29.1 | 9248 | 71.4 | 100 |
| F2 | kept-A(250,4)+VPC(200,2) | a_uniform_slip | 0.05 | 42 | 5495 | 23.8 | 23 | 6560 | 47.6 | 88.1 |

## HEADLINE TABLE 1 — damage level where PASS>BUST flips false (interpolated, per cell x family)

Linear interpolation of margin=pass_pct-bust_pct across the tested grid points (baseline=0 included). "not observed within tested grid" = margin stayed positive through the largest tested damage point for that family.

| cell | cell_desc | family | flip_at |
| --- | --- | --- | --- |
| C1 | A(600,6)+VPC(600,4) | a_uniform_slip (s, R) | 0.0421 |
| C1 | A(600,6)+VPC(600,4) | b_partial_fill (1-f) | 0.1349 |
| C1 | A(600,6)+VPC(600,4) | c_vpc_chase (pts) | >1 (not observed within tested grid) |
| C2 | A(1200,10)+VPC(600,4) | a_uniform_slip (s, R) | 0.019 |
| C2 | A(1200,10)+VPC(600,4) | b_partial_fill (1-f) | 0.0787 |
| C2 | A(1200,10)+VPC(600,4) | c_vpc_chase (pts) | >1 (not observed within tested grid) |
| C3 | A(1200,10)+VPC(400,4) | a_uniform_slip (s, R) | 0.015 |
| C3 | A(1200,10)+VPC(400,4) | b_partial_fill (1-f) | 0.0564 |
| C3 | A(1200,10)+VPC(400,4) | c_vpc_chase (pts) | >1 (not observed within tested grid) |
| C4 | unfiltered-A(1200,6) alone | a_uniform_slip (s, R) | 0.0134 |
| C4 | unfiltered-A(1200,6) alone | b_partial_fill (1-f) | 0.0496 |
| C5 | VPC(800,6) alone | a_uniform_slip (s, R) | 0.025 |
| C5 | VPC(800,6) alone | b_partial_fill (1-f) | 0.0634 |
| C5 | VPC(800,6) alone | c_vpc_chase (pts) | >1 (not observed within tested grid) |

## HEADLINE TABLE 2 — break-even vs honest A-alone reference (C4 = unfiltered-A(1200,6))

Family (a) uniform-slippage only (the one damage measure common/comparable across all cell types). `beats_honest_A_alone` = (cell's pass_pct-bust_pct margin) > (C4's margin at the SAME slippage level s).

| cell | cell_desc | slip_s | cell_pass_pct | cell_bust_pct | cell_margin | ref_C4_pass_pct | ref_C4_bust_pct | ref_C4_margin | beats_honest_A_alone |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | A(600,6)+VPC(600,4) | 0 | 27.8 | 15.5 | 12.3 | 23.4 | 20.7 | 2.7 | True |
| C1 | A(600,6)+VPC(600,4) | 0.01 | 24.7 | 17.1 | 7.6 | 23 | 22 | 1 | True |
| C1 | A(600,6)+VPC(600,4) | 0.02 | 23.4 | 17.4 | 6 | 22 | 23.9 | -1.9 | True |
| C1 | A(600,6)+VPC(600,4) | 0.03 | 22.1 | 18.3 | 3.8 | 21.5 | 25.4 | -3.9 | True |
| C1 | A(600,6)+VPC(600,4) | 0.05 | 20 | 22.5 | -2.5 | 17.5 | 27 | -9.5 | True |
| C1 | A(600,6)+VPC(600,4) | 0.075 | 17 | 24.4 | -7.4 | 15.6 | 29.5 | -13.9 | True |
| C1 | A(600,6)+VPC(600,4) | 0.1 | 15.6 | 27.6 | -12 | 13.6 | 31 | -17.4 | True |
| C2 | A(1200,10)+VPC(600,4) | 0 | 44.6 | 34.4 | 10.2 | 23.4 | 20.7 | 2.7 | True |
| C2 | A(1200,10)+VPC(600,4) | 0.01 | 42.8 | 38.2 | 4.6 | 23 | 22 | 1 | True |
| C2 | A(1200,10)+VPC(600,4) | 0.02 | 40.4 | 40.9 | -0.5 | 22 | 23.9 | -1.9 | True |
| C2 | A(1200,10)+VPC(600,4) | 0.03 | 39.2 | 42.4 | -3.2 | 21.5 | 25.4 | -3.9 | True |
| C2 | A(1200,10)+VPC(600,4) | 0.05 | 36.5 | 44.9 | -8.4 | 17.5 | 27 | -9.5 | True |
| C2 | A(1200,10)+VPC(600,4) | 0.075 | 33.5 | 45.9 | -12.4 | 15.6 | 29.5 | -13.9 | True |
| C2 | A(1200,10)+VPC(600,4) | 0.1 | 28.9 | 51.8 | -22.9 | 13.6 | 31 | -17.4 | False |
| C3 | A(1200,10)+VPC(400,4) | 0 | 41.5 | 34.6 | 6.9 | 23.4 | 20.7 | 2.7 | True |
| C3 | A(1200,10)+VPC(400,4) | 0.01 | 39.7 | 38.1 | 1.6 | 23 | 22 | 1 | True |
| C3 | A(1200,10)+VPC(400,4) | 0.02 | 38 | 39.6 | -1.6 | 22 | 23.9 | -1.9 | True |
| C3 | A(1200,10)+VPC(400,4) | 0.03 | 36.6 | 41.2 | -4.6 | 21.5 | 25.4 | -3.9 | False |
| C3 | A(1200,10)+VPC(400,4) | 0.05 | 32.9 | 45.5 | -12.6 | 17.5 | 27 | -9.5 | False |
| C3 | A(1200,10)+VPC(400,4) | 0.075 | 29.4 | 47.7 | -18.3 | 15.6 | 29.5 | -13.9 | False |
| C3 | A(1200,10)+VPC(400,4) | 0.1 | 26.1 | 52.4 | -26.3 | 13.6 | 31 | -17.4 | False |
| C5 | VPC(800,6) alone | 0 | 20.1 | 16.7 | 3.4 | 23.4 | 20.7 | 2.7 | True |
| C5 | VPC(800,6) alone | 0.01 | 18.8 | 17.2 | 1.6 | 23 | 22 | 1 | True |
| C5 | VPC(800,6) alone | 0.02 | 18.5 | 18 | 0.5 | 22 | 23.9 | -1.9 | True |
| C5 | VPC(800,6) alone | 0.03 | 18.3 | 18.8 | -0.5 | 21.5 | 25.4 | -3.9 | True |
| C5 | VPC(800,6) alone | 0.05 | 17.2 | 22.9 | -5.7 | 17.5 | 27 | -9.5 | True |
| C5 | VPC(800,6) alone | 0.075 | 16.5 | 25.4 | -8.9 | 15.6 | 29.5 | -13.9 | True |
| C5 | VPC(800,6) alone | 0.1 | 15.7 | 26.7 | -11 | 13.6 | 31 | -17.4 | True |

## HEADLINE TABLE 3 — VPC-chase stress

VPC prior cert (vpc_recert_real.py cost ladder, RT_COST=3.0pt flat, 2022+ real Databento, same CFG/engine): n=408 PF=1.232 WR%=44.1 net=+4001.2pt — the cost ladder's own "survived 3pt flat costs" point, printed here as the prior VPC's chase-stress result below should be read against.

| cell | cell_desc | extra_entry_pts | pass_pct | bust_pct | exp_pct | pass_gt_bust |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | A(600,6)+VPC(600,4) | 0 | 27.8 | 15.5 | 56.7 | True |
| C1 | A(600,6)+VPC(600,4) | 0.5 | 26.3 | 15.9 | 57.7 | True |
| C1 | A(600,6)+VPC(600,4) | 1 | 26.2 | 16.1 | 57.7 | True |
| C2 | A(1200,10)+VPC(600,4) | 0 | 44.6 | 34.4 | 21.1 | True |
| C2 | A(1200,10)+VPC(600,4) | 0.5 | 44.4 | 34.6 | 20.9 | True |
| C2 | A(1200,10)+VPC(600,4) | 1 | 44.3 | 35.1 | 20.6 | True |
| C3 | A(1200,10)+VPC(400,4) | 0 | 41.5 | 34.6 | 23.9 | True |
| C3 | A(1200,10)+VPC(400,4) | 0.5 | 41.5 | 34.6 | 23.9 | True |
| C3 | A(1200,10)+VPC(400,4) | 1 | 41.2 | 34.7 | 24.1 | True |
| C5 | VPC(800,6) alone | 0 | 20.1 | 16.7 | 63.2 | True |
| C5 | VPC(800,6) alone | 0.5 | 19.5 | 16.7 | 63.8 | True |
| C5 | VPC(800,6) alone | 1 | 18.8 | 17.5 | 63.8 | True |

## PF freeze check: no cell/damage point anywhere breached PF>1.8.
