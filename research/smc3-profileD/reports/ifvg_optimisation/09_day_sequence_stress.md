# 09 — Stress test: top rows by ex-2024 avgR

Method: cost stress recomputes R by subtracting `(cost_mult-1) x $15 (baseline $5 RT commission + $10 = 2-tick slippage) / (risk_pts x $20/pt)` from every trade's R (extra $ cost converted to R via the trade's own risk). Flat-slippage stress subtracts a fixed R amount from every trade. Winner-fill degradation multiplies ONLY winning trades' R by the fill factor (expected-value method — MFE not available in this ledger, so this approximates 'some winners get a worse fill / clipped early' rather than literally re-drawing a subset of winners).

| rule | scenario | n | avgR | ex2024_avgR | PF(R) | dies? |
|---|---|---|---|---|---|---|
| B.standalone_sig#3 | baseline | 145 | +0.0736 | +0.0959 | 1.113 | (ref) |
| B.standalone_sig#3 | 2x costs | 145 | +0.0507 | +0.0732 | 1.076 | - |
| B.standalone_sig#3 | 3x costs | 145 | +0.0278 | +0.0505 | 1.041 | - |
| B.standalone_sig#3 | -0.01R flat slip | 145 | +0.0636 | +0.0859 | 1.097 | - |
| B.standalone_sig#3 | -0.02R flat slip | 145 | +0.0536 | +0.0759 | 1.081 | - |
| B.standalone_sig#3 | -0.03R flat slip | 145 | +0.0436 | +0.0659 | 1.065 | - |
| B.standalone_sig#3 | 90% winner fill | 145 | +0.0014 | +0.0222 | 1.002 | - |
| B.standalone_sig#3 | 85% winner fill | 145 | -0.0348 | -0.0147 | 0.946 | DIES |
| B.standalone_sig#4+ | baseline | 26 | +0.2470 | +0.0812 | 1.418 | (ref) |
| B.standalone_sig#4+ | 2x costs | 26 | +0.2249 | +0.0571 | 1.371 | - |
| B.standalone_sig#4+ | 3x costs | 26 | +0.2027 | +0.0329 | 1.327 | - |
| B.standalone_sig#4+ | -0.01R flat slip | 26 | +0.2370 | +0.0712 | 1.397 | - |
| B.standalone_sig#4+ | -0.02R flat slip | 26 | +0.2270 | +0.0612 | 1.377 | - |
| B.standalone_sig#4+ | -0.03R flat slip | 26 | +0.2170 | +0.0512 | 1.357 | - |
| B.standalone_sig#4+ | 90% winner fill | 26 | +0.1632 | +0.0082 | 1.276 | - |
| B.standalone_sig#4+ | 85% winner fill | 26 | +0.1213 | -0.0282 | 1.205 | DIES |
| F.dir_lock_first_sweep | baseline | 1438 | +0.0561 | +0.0157 | 1.086 | (ref) |
| F.dir_lock_first_sweep | 2x costs | 1438 | +0.0335 | -0.0067 | 1.050 | DIES |
| F.dir_lock_first_sweep | 3x costs | 1438 | +0.0110 | -0.0291 | 1.016 | DIES |
| F.dir_lock_first_sweep | -0.01R flat slip | 1438 | +0.0461 | +0.0057 | 1.070 | - |
| F.dir_lock_first_sweep | -0.02R flat slip | 1438 | +0.0361 | -0.0043 | 1.054 | DIES |
| F.dir_lock_first_sweep | -0.03R flat slip | 1438 | +0.0261 | -0.0143 | 1.039 | DIES |
| F.dir_lock_first_sweep | 90% winner fill | 1438 | -0.0151 | -0.0528 | 0.977 | DIES |
| F.dir_lock_first_sweep | 85% winner fill | 1438 | -0.0506 | -0.0870 | 0.923 | DIES |
| F.no_opp_within_60min_entry | baseline | 1555 | +0.0615 | +0.0111 | 1.094 | (ref) |
| F.no_opp_within_60min_entry | 2x costs | 1555 | +0.0388 | -0.0115 | 1.058 | DIES |
| F.no_opp_within_60min_entry | 3x costs | 1555 | +0.0161 | -0.0341 | 1.024 | DIES |
| F.no_opp_within_60min_entry | -0.01R flat slip | 1555 | +0.0515 | +0.0011 | 1.078 | - |
| F.no_opp_within_60min_entry | -0.02R flat slip | 1555 | +0.0415 | -0.0089 | 1.062 | DIES |
| F.no_opp_within_60min_entry | -0.03R flat slip | 1555 | +0.0315 | -0.0189 | 1.047 | DIES |
| F.no_opp_within_60min_entry | 90% winner fill | 1555 | -0.0100 | -0.0571 | 0.985 | DIES |
| F.no_opp_within_60min_entry | 85% winner fill | 1555 | -0.0457 | -0.0911 | 0.930 | DIES |
| F.no_opp_after_loss | baseline | 1548 | +0.0588 | +0.0083 | 1.090 | (ref) |
| F.no_opp_after_loss | 2x costs | 1548 | +0.0363 | -0.0141 | 1.054 | DIES |
| F.no_opp_after_loss | 3x costs | 1548 | +0.0137 | -0.0366 | 1.020 | DIES |
| F.no_opp_after_loss | -0.01R flat slip | 1548 | +0.0488 | -0.0017 | 1.074 | DIES |
| F.no_opp_after_loss | -0.02R flat slip | 1548 | +0.0388 | -0.0117 | 1.058 | DIES |
| F.no_opp_after_loss | -0.03R flat slip | 1548 | +0.0288 | -0.0217 | 1.043 | DIES |
| F.no_opp_after_loss | 90% winner fill | 1548 | -0.0125 | -0.0596 | 0.981 | DIES |
| F.no_opp_after_loss | 85% winner fill | 1548 | -0.0481 | -0.0936 | 0.926 | DIES |
