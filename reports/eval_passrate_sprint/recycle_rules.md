# 1G — Recycle / Abandonment Rules

**SIM CONDITIONAL — replay of one historical path**

- R0 = baseline (never abandons); R1-R4 abandonment triggers checked live during the replay; R0's own row IS every other rule's counterfactual ('would have been'), since trades already taken before an abandonment trigger are identical to the baseline path.
- Official funnel (pass_pct/bust_pct/exp_pct/abandoned_pct) is mutually exclusive per rule.
- cf_* columns = outcome distribution of ONLY the abandoned subset had they NOT abandoned (the R0 result for those same starts). forgone_pass_pct_of_all_starts = the 3-loss-style recoveries given up, as a % of ALL starts under that rule.
- Business view (stationary per-slot-year approximation): attempts/slot-year = 365.25 / mean occupancy days (occupancy = abandon day if ABANDONED else natural terminal day); funded/slot-year = attempts/slot-year * pass%; e_per_slot_year nets fees at that cadence. Two fee_col rows per rule: sticker $131 and LOW-CONF promo $30.

| rule | fee_col | n | pass_pct | bust_pct | exp_pct | abandoned_pct | cf_would_pass_pct | cf_would_bust_pct | cf_would_expire_pct | forgone_pass_pct_of_all_starts | mean_occupancy_days | attempts_per_slot_year | funded_per_slot_year | e_per_attempt | e_per_slot_year |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R0 none (baseline) | sticker_131 | 395 | 47.8 | 15.9 | 36.2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 21.3 | 17.17 | 8.209 | 5953.0 | 102233.0 |
| R0 none (baseline) | promo_30_LOWCONF | 395 | 47.8 | 15.9 | 36.2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 21.3 | 17.17 | 8.209 | 6054.0 | 103968.0 |
| R1 stop after 3 consecutive A losses | sticker_131 | 395 | 47.6 | 13.7 | 29.4 | 9.4 | 2.7 | 24.3 | 73.0 | 0.3 | 19.8 | 18.42 | 8.768 | 5928.0 | 109191.0 |
| R1 stop after 3 consecutive A losses | promo_30_LOWCONF | 395 | 47.6 | 13.7 | 29.4 | 9.4 | 2.7 | 24.3 | 73.0 | 0.3 | 19.8 | 18.42 | 8.768 | 6029.0 | 111052.0 |
| R2 stop after 2 consecutive losses AND cushion<$700 | sticker_131 | 395 | 47.8 | 9.6 | 31.1 | 11.4 | 0.0 | 55.6 | 44.4 | 0.0 | 20.6 | 17.73 | 8.476 | 5953.0 | 105563.0 |
| R2 stop after 2 consecutive losses AND cushion<$700 | promo_30_LOWCONF | 395 | 47.8 | 9.6 | 31.1 | 11.4 | 0.0 | 55.6 | 44.4 | 0.0 | 20.6 | 17.73 | 8.476 | 6054.0 | 107354.0 |
| R3 stop when P(pass)<10% AND P(expire)>70% | sticker_131 | 395 | 47.6 | 14.7 | 21.5 | 16.2 | 1.6 | 7.8 | 90.6 | 0.3 | 20.5 | 17.83 | 8.488 | 5928.0 | 105696.0 |
| R3 stop when P(pass)<10% AND P(expire)>70% | promo_30_LOWCONF | 395 | 47.6 | 14.7 | 21.5 | 16.2 | 1.6 | 7.8 | 90.6 | 0.3 | 20.5 | 17.83 | 8.488 | 6029.0 | 107497.0 |
| R4 stop after day 20 if pnl<0 | sticker_131 | 395 | 47.6 | 12.7 | 26.8 | 12.9 | 2.0 | 25.5 | 72.5 | 0.3 | 20.5 | 17.8 | 8.471 | 5928.0 | 105487.0 |
| R4 stop after day 20 if pnl<0 | promo_30_LOWCONF | 395 | 47.6 | 12.7 | 26.8 | 12.9 | 2.0 | 25.5 | 72.5 | 0.3 | 20.5 | 17.8 | 8.471 | 6029.0 | 107285.0 |
