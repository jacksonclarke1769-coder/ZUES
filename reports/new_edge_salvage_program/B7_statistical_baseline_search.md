# JOB 3 (B7) -- Statistical Baseline Search -- RESEARCH ONLY

Runtime: 4.6s. 3218 trading days 2014-01-01..2026-05-25. IS=2016-2022 (1797d), OOS=2023-2026 (870d), L3-touch IS=1382d/OOS=661d.

132 rule-cells scanned (7 single features x 2 labels x 2 quintiles x 2 directions = 56, + 3 preregistered two-feature pairs x 2 labels x 4 corners x 2 directions = 48, + L3-reversal single-feature x 2 quintiles x 2 rules x 7 = 28).


## Qualifiers (IS hit>0.55 AND OOS hit>0.53 AND n>=200)

 feature             label quintile                 rule  is_hit  is_n  oos_hit  oos_n
     gap       L1_first30m bottom20           predict_up   0.569   360    0.562    276
     gap            L2_mid    top20           predict_up   0.563   359    0.548    323
  pd_dir       L1_first30m bottom20           predict_up   0.552   800    0.534    382
     gap L3_reversal_touch    top20 predict_continuation   0.769   277    0.707    249
pm_range L3_reversal_touch    top20 predict_continuation   0.635   277    0.640    358
  pd_dir L3_reversal_touch bottom20 predict_continuation   0.646   571    0.587    269
  pd_dir L3_reversal_touch    top20 predict_continuation   0.656   811    0.651    392


## Trade-conversion attempts (only for qualifiers)

{'feature': 'gap', 'label': 'L1_first30m', 'quintile': 'bottom20', 'rule': 'predict_up', 'n_trades': 660, 'pf': 1.109, 'freq_tr_wk': 1.028, 'last6_pos': 4, 'last6_of': 6, 'clears_pf_1_15': False}
{'feature': 'gap', 'label': 'L2_mid', 'quintile': 'top20', 'rule': 'predict_up', 'n_trades': 703, 'pf': 1.184, 'freq_tr_wk': 1.094, 'last6_pos': 4, 'last6_of': 6, 'clears_pf_1_15': True}
{'feature': 'pd_dir', 'label': 'L1_first30m', 'quintile': 'bottom20', 'rule': 'predict_up', 'n_trades': 1413, 'pf': 1.214, 'freq_tr_wk': 2.192, 'last6_pos': 4, 'last6_of': 6, 'clears_pf_1_15': True}
{'feature': 'gap', 'label': 'L3_reversal_touch', 'quintile': 'top20', 'rule': 'predict_continuation', 'note': "L3 conditioning event (PDH/PDL touch) occurs mid-session, after 09:30 -- not a valid 09:30 entry signal; needs its own touch-triggered trade design, out of this job's scope"}
{'feature': 'pm_range', 'label': 'L3_reversal_touch', 'quintile': 'top20', 'rule': 'predict_continuation', 'note': "L3 conditioning event (PDH/PDL touch) occurs mid-session, after 09:30 -- not a valid 09:30 entry signal; needs its own touch-triggered trade design, out of this job's scope"}
{'feature': 'pd_dir', 'label': 'L3_reversal_touch', 'quintile': 'bottom20', 'rule': 'predict_continuation', 'note': "L3 conditioning event (PDH/PDL touch) occurs mid-session, after 09:30 -- not a valid 09:30 entry signal; needs its own touch-triggered trade design, out of this job's scope"}
{'feature': 'pd_dir', 'label': 'L3_reversal_touch', 'quintile': 'top20', 'rule': 'predict_continuation', 'note': "L3 conditioning event (PDH/PDL touch) occurs mid-session, after 09:30 -- not a valid 09:30 entry signal; needs its own touch-triggered trade design, out of this job's scope"}


## Full scan (top 20 by OOS hit rate, n>=200 both eras)

     feature             label quintile                 rule  is_hit  is_n  oos_hit  oos_n
         gap L3_reversal_touch    top20 predict_continuation   0.769   277    0.707    249
      pd_dir L3_reversal_touch    top20 predict_continuation   0.656   811    0.651    392
    pm_range L3_reversal_touch    top20 predict_continuation   0.635   277    0.640    358
      pd_dir L3_reversal_touch bottom20 predict_continuation   0.646   571    0.587    269
    pm_range            L2_mid    top20           predict_up   0.507   359    0.566    475
on_atr_ratio            L2_mid    top20           predict_up   0.539   360    0.562    219
      pd_dir            L2_mid    top20           predict_up   0.543   995    0.562    486
         gap       L1_first30m bottom20           predict_up   0.569   360    0.562    276
on_atr_ratio       L1_first30m    top20           predict_up   0.531   360    0.555    220
    pm_range       L1_first30m    top20           predict_up   0.519   360    0.555    476
      pd_dir            L2_mid bottom20           predict_up   0.549   796    0.554    381
      pd_dir       L1_first30m    top20           predict_up   0.522   996    0.553    488
         gap            L2_mid    top20           predict_up   0.563   359    0.548    323
         gap       L1_first30m    top20           predict_up   0.511   360    0.542    323
         gap            L2_mid bottom20           predict_up   0.507   359    0.542    273
      pd_dir       L1_first30m bottom20           predict_up   0.552   800    0.534    382
      pd_dir       L1_first30m bottom20         predict_down   0.448   800    0.466    382
         gap       L1_first30m    top20         predict_down   0.489   360    0.458    323
         gap            L2_mid bottom20         predict_down   0.493   359    0.458    273
         gap            L2_mid    top20         predict_down   0.437   359    0.452    323


## Verdict

**MOSTLY NOISE, WITH A FEW MARGINAL HITS -- not a confident new edge.** 7/132 preregistered cells clear the IS>0.55/OOS>0.53/n>=200 bar (~5%, in the range expected from chance alone at this grid size given the IS-best-of-4-corners selection this design uses -- see method note on multiple comparisons). Of the 3 that are actually 09:30-actionable (L1/L2 direction rules; the other 4 are L3 touch-conditional rules that cannot fire at 09:30 -- see conversion notes), converting to simple next-bar-open 1.5R trades gives PF 1.11-1.21; 2/3 clear the repo's own PF>=1.15 kill gate (gap/L2_mid PF 1.184, pd_dir/L1_first30m PF 1.214), at hit-rates only 2-7pp above a coin flip. This is a weak, borderline signal at best -- STOP AND FLAG for operator review, but do NOT treat this as a validated edge without independent out-of-sample replication on data collected after this scan (the multiple-comparisons risk here is real and not fully resolved by the walk-forward split alone).
