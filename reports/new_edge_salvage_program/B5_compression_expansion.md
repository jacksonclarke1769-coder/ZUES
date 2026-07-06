# JOB 2 (B5) -- NY-Open Compression -> Expansion -- RESEARCH ONLY

Runtime: 2.2s. Incumbent: Profile B (ORB) honest PF ~1.07 (the bar this job must beat, in addition to the shared kill gates).

## Lane signal counts + Profile-A overlap

     lane  n_setups  n_signal_days  overlap_with_A_pct
overnight       759            759                11.7
premarket       868            868                15.6
   atr_or       815            815                15.6


## Backtest results (3 lanes x 3 exits = 9 cells)

     lane exit_type verdict   n    pf  freq_tr_wk  last6_pos  last6_of  beats_incumbent_B_1_07                                                           reasons
overnight       1.5    DEAD 570 0.622       0.909          3         6                   False PF 0.622 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
overnight       2.0    DEAD 570 0.625       0.909          2         6                   False PF 0.625 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
overnight     exit3    DEAD 570 0.539       0.909          2         6                   False PF 0.539 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
premarket       1.5    DEAD 637 0.638       1.017          2         6                   False PF 0.638 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
premarket       2.0    DEAD 637 0.711       1.017          2         6                   False PF 0.711 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
premarket     exit3    DEAD 637 0.614       1.017          1         6                   False PF 0.614 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
   atr_or       1.5    DEAD 577 0.675       0.921          2         6                   False PF 0.675 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
   atr_or       2.0    DEAD 577 0.747       0.921          3         6                   False PF 0.747 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
   atr_or     exit3    DEAD 577 0.641       0.921          2         6                   False PF 0.641 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)


## Survivor canaries

(no survivors -- no canary needed)


## Verdict

**ALL 9 CELLS DEAD** (PF<1.15 / <4-of-6-last-full-years / freq floor). None came close to beating Profile B's honest 1.07 incumbent either. No new edge in the NY-open compression->expansion family.
