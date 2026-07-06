# 01 -- Baseline Reproduction (A+VPC Optimisation, Lane 1)

RESEARCH ONLY. LIVE HOLD ACTIVE. Modifies nothing existing.

## (a) A solo 600/6 (2022+ window)
- computed: {'eligible_starts': 463, 'pass_count': 42, 'bust_count': 16, 'exp_count': 405, 'pass_pct': 9.1, 'bust_pct': 3.5, 'exp_pct': 87.5, 'med_days_pass': 23, 'mean_days_all': 29.082, 'funded_per_slot_year': 1.14, 'worst_day_usd': -1000.0}
- reference: {'pass_pct': 9.1, 'bust_pct': 3.5, 'exp_pct': 87.5, 'n': 463, 'funded_per_slot_year': 1.14}
- match (tolerance 0.3pp): **True**

## (b) VPC solo 600/4 (1m-truth stream)
- computed: {'eligible_starts': 388, 'pass_count': 42, 'bust_count': 12, 'exp_count': 334, 'pass_pct': 10.8, 'bust_pct': 3.1, 'exp_pct': 86.1, 'med_days_pass': 16, 'mean_days_all': 28.363, 'funded_per_slot_year': 1.39, 'worst_day_usd': -1000.0}
- reference: {'pass_pct': 10.8, 'bust_pct': 3.1, 'exp_pct': 86.1, 'n': 388, 'funded_per_slot_year': 1.39}
- match (tolerance 0.3pp): **True**

## (c) A600/6 + VPC600/4 combined
- computed: {'eligible_starts': 684, 'pass_count': 196, 'bust_count': 116, 'exp_count': 372, 'pass_pct': 28.7, 'bust_pct': 17.0, 'exp_pct': 54.4, 'med_days_pass': 18, 'mean_days_all': 24.792, 'funded_per_slot_year': 4.22, 'worst_day_usd': -1000.0}
- reference: {'pass_pct': 28.7, 'bust_pct': 17.0, 'exp_pct': 54.4, 'n': 684, 'funded_per_slot_year': 4.22}
- match (tolerance 0.3pp): **True**

## (d) 3-point slippage probe of the (c) baseline (0.015/0.030/0.046R)

| damage(R) | pass% | bust% | exp% | pass>bust |
| --- | --- | --- | --- | --- |
| 0.015 | 26.5 | 17.8 | 55.7 | True |
| 0.03 | 24.9 | 17.8 | 57.3 | True |
| 0.046 | 23.0 | 18.6 | 58.5 | True |

pass>bust at all three probe points: **True**

## Overall verdict
**MATCH — proceeding to 02_sizing_grid**

## Firewall before/after
- before: `{'config_eval_locked.py': '3ca389fc5a8a9fe47b844a6c77f6f13dc8b5c4564c135949b9a5c81e02df36e5', 'config_funded_locked.py': '95276d506ec33330d46caee0223f7056d112021ab0f5f5797621cd9fdd3acbe4', 'config_defaults.py': '1cbbbe8a7bd438e19647a9e020b2bbdbe93878074b3249d8ea65653660562c22', 'auto_safety.py': 'b7b05b423edd21f4dc707887f3e050b64699f7931b6f1dc3ab3213b73dade2bc'}`
- after: `{'config_eval_locked.py': '3ca389fc5a8a9fe47b844a6c77f6f13dc8b5c4564c135949b9a5c81e02df36e5', 'config_funded_locked.py': '95276d506ec33330d46caee0223f7056d112021ab0f5f5797621cd9fdd3acbe4', 'config_defaults.py': '1cbbbe8a7bd438e19647a9e020b2bbdbe93878074b3249d8ea65653660562c22', 'auto_safety.py': 'b7b05b423edd21f4dc707887f3e050b64699f7931b6f1dc3ab3213b73dade2bc'}`
- match: **True**

Runtime: 19.4s
