# NQ Pattern Discovery -- Lane H: Extended Interpretable Statistical Scan

RESEARCH ONLY. No strategy promotion. Preregistered design, no expansion after first run -- see `H_statistical_baseline_search.py` module docstring for the full method (decision-stamp mapping, ATR convention, race tie-break rule, quintile-edge-fit-on-IS-only convention).

**Panel**: 5328 (date,stamp) rows -- IS(2016-2022)=3582, OOS(2023-2026)=1746. Decision stamps: 10:00 and 10:30 ET.

**Cells tested**: 6055 total (680 single-feature feature x stamp x bin x label cells + 5375 two-feature pair x stamp x corner(5x5) x label cells, from the preregistered 8-feature pair subset, C(8,2)=28 pairs).

## Data-availability note (structural, not a bug)

The store's intraday rolling windows reset per RTH day (`features_intraday.py`). At the 10:00 stamp only 6 bars of the session have elapsed; at 10:30, 12 bars. Consequences for three of the preregistered features:
- `trend_slope_20bar` (needs a trailing 20-bar window) is **structurally NaN at BOTH decision stamps** (6 and 12 bars elapsed respectively, both < 20) -- excluded from the scan entirely, not a coding omission.
- `vwap_slope_6bar` (needs 6 prior bars) is NaN at 10:00 (only 6 bars total, `diff(6)` has no history) and valid at 10:30 -- scanned at 10:30 only.
- `compression_score` (needs a shift(6)+24-bar window, `min_periods=6`) is NaN at 10:00 and valid (marginally, min_periods reached) at 10:30 -- scanned at 10:30 only.

## Nominee table

                              feature  stamp          label   bin  is_hit  is_n  oos_hit  oos_n monotone direction  n_trades    pf  per_year
                      prior_direction   1030    L3_race_atr   1.0   0.406   446    0.450    218     True      down      1483 0.983     143.7
                      prior_direction   1030   L5_or30_cont  -1.0   0.720   189    0.824     74     True        up      1181 1.055     114.2
                      prior_direction   1030   L5_or30_cont   1.0   0.695   174    0.714     84     True        up      1483 0.944     143.7
                   time_of_day_bucket POOLED   L5_or30_cont  1030   0.708   363    0.766    158     True        up      2664 0.995     257.7
first_15m_ret_atr__x__vwap_slope_6bar   1030 L1_next30m_dir Q1,Q1   0.430   114    0.422     90     None      down       204 1.424      19.8
  first_15m_ret_atr__x__d1c_drift_atr   1000 L1_next30m_dir Q3,Q3   0.567   141    0.547     75     None        up       216 1.143      21.1
  first_15m_ret_atr__x__d1c_drift_atr   1000 L1_next30m_dir Q5,Q5   0.582   237    0.649     94     None        up       331 1.145      32.2
  first_15m_ret_atr__x__d1c_drift_atr   1000 L2_next60m_dir Q5,Q5   0.565   237    0.574     94     None        up       331 1.145      32.2
  first_15m_ret_atr__x__d1c_drift_atr   1000    L3_race_atr Q1,Q1   0.440   159    0.365     85     None      down       361 1.217      35.1
  first_15m_ret_atr__x__d1c_drift_atr   1030 L1_next30m_dir Q1,Q1   0.435   184    0.465    101     None      down       285 1.441      27.7
  first_15m_ret_atr__x__d1c_drift_atr   1030 L2_next60m_dir Q5,Q5   0.559   202    0.537     95     None        up       297 1.175      28.9
      vwap_dist_atr__x__d1c_drift_atr   1000 L2_next60m_dir Q5,Q5   0.563   231    0.557    106     None        up       337 1.279      32.9
      vwap_dist_atr__x__d1c_drift_atr   1000    L3_race_atr Q5,Q5   0.562   144    0.567     67     None        up       337 1.279      32.9
      vwap_dist_atr__x__d1c_drift_atr   1030 L1_next30m_dir Q3,Q3   0.586   133    0.676     68     None        up       201 1.109      19.6
    vwap_slope_6bar__x__d1c_drift_atr   1030 L2_next60m_dir Q5,Q5   0.597   196    0.531    175     None        up       371 1.102      36.1
 vwap_slope_6bar__x__pdh_pdl_dist_atr   1030 L1_next30m_dir Q1,Q1   0.449   127    0.462     93     None      down       220 1.182      21.4
 vwap_slope_6bar__x__pdh_pdl_dist_atr   1030 L2_next60m_dir Q5,Q5   0.600   110    0.600    100     None        up       210 1.375      20.4
         gap_atr__x__pdh_pdl_dist_atr   1000 L1_next30m_dir Q5,Q5   0.571   170    0.565     85     None        up       255 0.983      24.7
         gap_atr__x__pdh_pdl_dist_atr   1030 L1_next30m_dir Q1,Q1   0.442   156    0.444     81     None      down       237 1.074      23.1
         gap_atr__x__pdh_pdl_dist_atr   1030 L2_next60m_dir Q5,Q5   0.585   164    0.533     75     None        up       239 0.939      23.1
   d1c_drift_atr__x__pdh_pdl_dist_atr   1030 L2_next60m_dir Q5,Q5   0.585   147    0.547     75     None        up       222 1.227      21.7

## False-positive expectation (multiple-comparisons honesty)

Sum of per-cell binomial-null probabilities (normal approximation, p=0.5, independent IS/OOS draws) of clearing (|IS-50%|>=5pp AND same-sign OOS>=3pp) using each cell's ACTUAL is_n/oos_n -- **this ignores the pooled-n>=200 and monotone-across-bins gates**, so it is an UPPER BOUND on the true null rate (monotonicity in particular is a strong additional filter with no closed-form probability computed here):

- single-feature cells: expected false positives ~ 20.37 (out of 680 cells)
- pair cells: expected false positives ~ 774.07 (out of 5375 cells)
- **total expected false positives (upper bound): ~794.44 out of 6055 cells tested**
- actual nominees found: 21

## Verdict

**NOISE-GRADE / DECISIVE NULL** -- observed nominee count (21) is at or below the binomial-null upper-bound expectation (~794.4) at this cell count. Consistent with the B7 precedent (132-cell scan, 3 marginal hits ~ null expectation). No robust interpretable statistical edge found in this lane.

## Runtime

3.9s wall clock.
