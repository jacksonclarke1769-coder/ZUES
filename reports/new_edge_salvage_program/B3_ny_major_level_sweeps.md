# JOB 1 (B3) -- NY Major-Level Sweeps -- RESEARCH ONLY

Runtime: 64.8s. Profile A reference: 583 trades / 537 signal days (2021-06-25..2026-06-18).

Overlap screen: 24 (level x model) combos checked, **0 REJECTED-IN-DISGUISE** (overlap > 60.0%), 24 proceeded to backtest (112 grid cells).


## Overlap-reject table

         level                        model  n_signal_days  overlap_pct  rejected_in_disguise
           PDH       sweep_reclaim_reversal           1026         19.0                 False
           PDH    break_retest_continuation            967         19.5                 False
           PDH failed_break_back_into_range            813         20.0                 False
           PDL       sweep_reclaim_reversal            782         20.1                 False
           PDL    break_retest_continuation            685         20.3                 False
           PDL failed_break_back_into_range            604         19.4                 False
           ONH       sweep_reclaim_reversal           1432         18.0                 False
           ONH    break_retest_continuation           1249         16.1                 False
           ONH failed_break_back_into_range           1062         17.4                 False
           ONL       sweep_reclaim_reversal           1339         16.9                 False
           ONL    break_retest_continuation           1120         16.7                 False
           ONL failed_break_back_into_range            976         16.5                 False
           PMH       sweep_reclaim_reversal           1660         19.2                 False
           PMH    break_retest_continuation           1449         17.6                 False
           PMH failed_break_back_into_range           1216         18.8                 False
           PML       sweep_reclaim_reversal           1616         19.6                 False
           PML    break_retest_continuation           1372         19.1                 False
           PML failed_break_back_into_range           1199         19.4                 False
PRIOR_CLOSE_hi       sweep_reclaim_reversal           1433         22.6                 False
PRIOR_CLOSE_hi    break_retest_continuation           1427         22.3                 False
PRIOR_CLOSE_hi failed_break_back_into_range           1226         23.0                 False
PRIOR_CLOSE_lo       sweep_reclaim_reversal           1459         21.9                 False
PRIOR_CLOSE_lo    break_retest_continuation           1361         22.4                 False
PRIOR_CLOSE_lo failed_break_back_into_range           1203         23.2                 False


## Backtest results (post-overlap-screen survivors only)

         level                        model                                                    params verdict    n    pf  freq_tr_wk  last6_pos  last6_of                                                           reasons
           PDH       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 3919 0.795       6.072          1         6 PF 0.795 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PDH       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 3919 0.747       6.072          1         6 PF 0.747 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PDH       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 5389 0.809       8.349          1         6 PF 0.809 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PDH       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 5389 0.761       8.349          1         6 PF 0.761 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PDH       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 3665 0.823       5.678          2         6 PF 0.823 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           PDH       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 3665 0.776       5.678          1         6 PF 0.776 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PDH       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 5129 0.830       7.947          2         6 PF 0.830 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           PDH       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 5129 0.783       7.947          1         6 PF 0.783 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PDH    break_retest_continuation                                        {'exit_type': 1.5}    DEAD 5622 0.845       8.710          4         6                                                   PF 0.845 < 1.15
           PDH    break_retest_continuation                                    {'exit_type': 'exit3'}    DEAD 5622 0.822       8.710          5         6                                                   PF 0.822 < 1.15
           PDH failed_break_back_into_range                          {'fb_bars': 2, 'exit_type': 1.5}    DEAD 2126 0.851       3.294          3         6 PF 0.851 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
           PDH failed_break_back_into_range                      {'fb_bars': 2, 'exit_type': 'exit3'}    DEAD 2126 0.805       3.294          2         6 PF 0.805 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           PDH failed_break_back_into_range                          {'fb_bars': 4, 'exit_type': 1.5}    DEAD 3282 0.859       5.085          3         6 PF 0.859 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
           PDH failed_break_back_into_range                      {'fb_bars': 4, 'exit_type': 'exit3'}    DEAD 3282 0.809       5.085          2         6 PF 0.809 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           PDL       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 3012 0.884       4.673          2         6 PF 0.884 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           PDL       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 3012 0.884       4.673          1         6 PF 0.884 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PDL       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 4085 0.907       6.338          2         6 PF 0.907 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           PDL       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 4085 0.914       6.338          3         6 PF 0.914 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
           PDL       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 2851 0.897       4.423          3         6 PF 0.897 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
           PDL       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 2851 0.901       4.423          3         6 PF 0.901 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
           PDL       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 3923 0.918       6.086          2         6 PF 0.918 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           PDL       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 3923 0.929       6.086          4         6                                                   PF 0.929 < 1.15
           PDL    break_retest_continuation                                        {'exit_type': 1.5}    DEAD 3683 0.788       5.706          4         6                                                   PF 0.788 < 1.15
           PDL    break_retest_continuation                                    {'exit_type': 'exit3'}    DEAD 3683 0.756       5.706          4         6                                                   PF 0.756 < 1.15
           PDL failed_break_back_into_range                          {'fb_bars': 2, 'exit_type': 1.5}    DEAD 1584 0.943       2.457          3         6 PF 0.943 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
           PDL failed_break_back_into_range                      {'fb_bars': 2, 'exit_type': 'exit3'}    DEAD 1584 0.984       2.457          4         6                                                   PF 0.984 < 1.15
           PDL failed_break_back_into_range                          {'fb_bars': 4, 'exit_type': 1.5}    DEAD 2391 0.972       3.709          3         6 PF 0.972 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
           PDL failed_break_back_into_range                      {'fb_bars': 4, 'exit_type': 'exit3'}    DEAD 2391 1.001       3.709          4         6                                                   PF 1.001 < 1.15
           ONH       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 5495 0.733       8.517          1         6 PF 0.733 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           ONH       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 5495 0.702       8.517          1         6 PF 0.702 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           ONH       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 7319 0.764      11.345          1         6 PF 0.764 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           ONH       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 7319 0.737      11.345          2         6 PF 0.737 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           ONH       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 5087 0.759       7.885          1         6 PF 0.759 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           ONH       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 5087 0.728       7.885          1         6 PF 0.728 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           ONH       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 6902 0.785      10.698          1         6 PF 0.785 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           ONH       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 6902 0.759      10.698          2         6 PF 0.759 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           ONH    break_retest_continuation                                        {'exit_type': 1.5}    DEAD 6709 0.767      10.397          5         6                                                   PF 0.767 < 1.15
           ONH    break_retest_continuation                                    {'exit_type': 'exit3'}    DEAD 6709 0.741      10.397          4         6                                                   PF 0.741 < 1.15
           ONH failed_break_back_into_range                          {'fb_bars': 2, 'exit_type': 1.5}    DEAD 2732 0.837       4.235          2         6 PF 0.837 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           ONH failed_break_back_into_range                      {'fb_bars': 2, 'exit_type': 'exit3'}    DEAD 2732 0.830       4.235          3         6 PF 0.830 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
           ONH failed_break_back_into_range                          {'fb_bars': 4, 'exit_type': 1.5}    DEAD 4112 0.848       6.372          2         6 PF 0.848 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           ONH failed_break_back_into_range                      {'fb_bars': 4, 'exit_type': 'exit3'}    DEAD 4112 0.835       6.372          3         6 PF 0.835 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
           ONL       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 5055 0.845       7.832          1         6 PF 0.845 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           ONL       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 5055 0.814       7.832          0         6 PF 0.814 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
           ONL       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 6593 0.877      10.215          1         6 PF 0.877 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           ONL       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 6593 0.847      10.215          1         6 PF 0.847 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           ONL       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 4749 0.867       7.358          1         6 PF 0.867 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           ONL       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 4749 0.839       7.358          1         6 PF 0.839 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           ONL       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 6282 0.896       9.733          1         6 PF 0.896 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           ONL       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 6282 0.868       9.733          1         6 PF 0.868 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           ONL    break_retest_continuation                                        {'exit_type': 1.5}    DEAD 5513 0.720       8.540          4         6                                                   PF 0.720 < 1.15
           ONL    break_retest_continuation                                    {'exit_type': 'exit3'}    DEAD 5513 0.699       8.540          3         6 PF 0.699 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
           ONL failed_break_back_into_range                          {'fb_bars': 2, 'exit_type': 1.5}    DEAD 2440 0.945       3.780          2         6 PF 0.945 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           ONL failed_break_back_into_range                      {'fb_bars': 2, 'exit_type': 'exit3'}    DEAD 2440 0.921       3.780          2         6 PF 0.921 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           ONL failed_break_back_into_range                          {'fb_bars': 4, 'exit_type': 1.5}    DEAD 3565 0.979       5.523          2         6 PF 0.979 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           ONL failed_break_back_into_range                      {'fb_bars': 4, 'exit_type': 'exit3'}    DEAD 3565 0.946       5.523          2         6 PF 0.946 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           PMH       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 6435 0.728       9.964          0         6 PF 0.728 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
           PMH       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 6435 0.700       9.964          0         6 PF 0.700 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
           PMH       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 8577 0.760      13.280          1         6 PF 0.760 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PMH       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 8577 0.737      13.280          1         6 PF 0.737 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PMH       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 5991 0.752       9.276          0         6 PF 0.752 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
           PMH       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 5991 0.728       9.276          0         6 PF 0.728 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
           PMH       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 8123 0.780      12.577          1         6 PF 0.780 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PMH       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 8123 0.761      12.577          1         6 PF 0.761 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PMH    break_retest_continuation                                        {'exit_type': 1.5}    DEAD 7933 0.758      12.288          4         6                                                   PF 0.758 < 1.15
           PMH    break_retest_continuation                                    {'exit_type': 'exit3'}    DEAD 7933 0.732      12.288          4         6                                                   PF 0.732 < 1.15
           PMH failed_break_back_into_range                          {'fb_bars': 2, 'exit_type': 1.5}    DEAD 3206 0.822       4.966          2         6 PF 0.822 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           PMH failed_break_back_into_range                      {'fb_bars': 2, 'exit_type': 'exit3'}    DEAD 3206 0.812       4.966          2         6 PF 0.812 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           PMH failed_break_back_into_range                          {'fb_bars': 4, 'exit_type': 1.5}    DEAD 4819 0.838       7.465          1         6 PF 0.838 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PMH failed_break_back_into_range                      {'fb_bars': 4, 'exit_type': 'exit3'}    DEAD 4819 0.830       7.465          1         6 PF 0.830 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PML       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 6315 0.818       9.791          1         6 PF 0.818 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PML       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 6315 0.799       9.791          1         6 PF 0.799 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PML       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 8249 0.854      12.789          1         6 PF 0.854 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PML       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 8249 0.841      12.789          1         6 PF 0.841 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PML       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 5952 0.841       9.228          1         6 PF 0.841 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PML       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 5952 0.826       9.228          1         6 PF 0.826 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PML       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 7880 0.873      12.217          1         6 PF 0.873 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PML       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 7880 0.865      12.217          1         6 PF 0.865 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PML    break_retest_continuation                                        {'exit_type': 1.5}    DEAD 6997 0.715      10.834          2         6 PF 0.715 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           PML    break_retest_continuation                                    {'exit_type': 'exit3'}    DEAD 6997 0.687      10.834          2         6 PF 0.687 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
           PML failed_break_back_into_range                          {'fb_bars': 2, 'exit_type': 1.5}    DEAD 3068 0.946       4.766          1         6 PF 0.946 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
           PML failed_break_back_into_range                      {'fb_bars': 2, 'exit_type': 'exit3'}    DEAD 3068 0.954       4.766          3         6 PF 0.954 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
           PML failed_break_back_into_range                          {'fb_bars': 4, 'exit_type': 1.5}    DEAD 4491 0.969       6.977          3         6 PF 0.969 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
           PML failed_break_back_into_range                      {'fb_bars': 4, 'exit_type': 'exit3'}    DEAD 4491 0.973       6.977          3         6 PF 0.973 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_hi       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 5771 0.704       8.943          0         6 PF 0.704 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_hi       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 5771 0.654       8.943          0         6 PF 0.654 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_hi       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 8190 0.704      12.692          0         6 PF 0.704 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_hi       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 8190 0.661      12.692          0         6 PF 0.661 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_hi       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 5472 0.719       8.480          0         6 PF 0.719 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_hi       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 5472 0.669       8.480          0         6 PF 0.669 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_hi       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 7882 0.714      12.215          0         6 PF 0.714 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_hi       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 7882 0.672      12.215          0         6 PF 0.672 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_hi    break_retest_continuation                                        {'exit_type': 1.5}    DEAD 9092 0.791      14.090          3         6 PF 0.791 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_hi    break_retest_continuation                                    {'exit_type': 'exit3'}    DEAD 9092 0.756      14.090          3         6 PF 0.756 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_hi failed_break_back_into_range                          {'fb_bars': 2, 'exit_type': 1.5}    DEAD 3350 0.711       5.191          0         6 PF 0.711 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_hi failed_break_back_into_range                      {'fb_bars': 2, 'exit_type': 'exit3'}    DEAD 3350 0.668       5.191          0         6 PF 0.668 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_hi failed_break_back_into_range                          {'fb_bars': 4, 'exit_type': 1.5}    DEAD 5311 0.717       8.230          0         6 PF 0.717 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_hi failed_break_back_into_range                      {'fb_bars': 4, 'exit_type': 'exit3'}    DEAD 5311 0.680       8.230          0         6 PF 0.680 < 1.15; only 0/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_lo       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 5953 0.784       9.225          1         6 PF 0.784 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_lo       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 5953 0.748       9.225          1         6 PF 0.748 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_lo       sweep_reclaim_reversal     {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 8277 0.823      12.827          1         6 PF 0.823 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_lo       sweep_reclaim_reversal {'tick_mult': 1, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 8277 0.785      12.827          1         6 PF 0.785 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_lo       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 1.5}    DEAD 5621 0.805       8.711          1         6 PF 0.805 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_lo       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 1, 'exit_type': 'exit3'}    DEAD 5621 0.775       8.711          1         6 PF 0.775 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_lo       sweep_reclaim_reversal     {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 1.5}    DEAD 7939 0.840      12.303          1         6 PF 0.840 < 1.15; only 1/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_lo       sweep_reclaim_reversal {'tick_mult': 3, 'reclaim_bars': 3, 'exit_type': 'exit3'}    DEAD 7939 0.806      12.303          2         6 PF 0.806 < 1.15; only 2/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_lo    break_retest_continuation                                        {'exit_type': 1.5}    DEAD 8449 0.686      13.093          3         6 PF 0.686 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_lo    break_retest_continuation                                    {'exit_type': 'exit3'}    DEAD 8449 0.619      13.093          3         6 PF 0.619 < 1.15; only 3/6 of last-6-full-years PF>=1.0 (need >=4)
PRIOR_CLOSE_lo failed_break_back_into_range                          {'fb_bars': 2, 'exit_type': 1.5}    DEAD 3333 0.907       5.165          4         6                                                   PF 0.907 < 1.15
PRIOR_CLOSE_lo failed_break_back_into_range                      {'fb_bars': 2, 'exit_type': 'exit3'}    DEAD 3333 0.880       5.165          4         6                                                   PF 0.880 < 1.15
PRIOR_CLOSE_lo failed_break_back_into_range                          {'fb_bars': 4, 'exit_type': 1.5}    DEAD 5165 0.916       8.004          5         6                                                   PF 0.916 < 1.15
PRIOR_CLOSE_lo failed_break_back_into_range                      {'fb_bars': 4, 'exit_type': 'exit3'}    DEAD 5165 0.885       8.004          5         6                                                   PF 0.885 < 1.15


## Survivor canaries

(no survivors -- no canary needed)


## Verdict

**ALL COMBOS DEAD.** Either rejected-in-disguise on overlap, or killed by PF<1.15 / <4-of-6-last-full-years / frequency floor. No new edge found in the NY major-level-sweep family. Priors (turtle-soup 0.84-0.91, W5 dead, idea-7 dead-on-frequency) hold.
