"""FUNDED-PHASE CONFIG FIREWALL — frozen declarative snapshot.

STATUS: DOCUMENTATION + GUARD ONLY. This file is NOT imported by any live code path
(auto_live.py, auto_safety.py, config_defaults.py, config.py, bridge/engine files never
reference it). It exists solely so that `test_funded_config_firewall.py` has a frozen,
version-controlled copy of the funded-phase constants to diff the live values against.

PROVENANCE:
  - FUNDED_TIERS below is a byte-for-byte copy of `auto_safety.FUNDED_TIERS` as certified
    2026-07-02 (rev b) and re-confirmed live 2026-07-05.
  - Context: DEC-20260705-1102 (cap-10 re-lock correction; see README.md "Certified Eval
    Numbers" and reports/risk_arithmetic_reconciliation_2026-07-05.md).
  - Harness of record for the funded-PA lifecycle rules built on top of these sizing
    constants: apex_funded_40.py (payout ladder, trailing-DD lock, DLL) — read-only,
    never edited by sizing research.

RULE: no eval-sizing change may touch this file. Funded-phase constants are certified
separately (funded re-lock), not as a side effect of eval-tier research. If `auto_safety.
FUNDED_TIERS` legitimately changes (a deliberate, audited funded re-certification), this
file MUST be updated in the SAME commit — together with `evidence/funded_config.sha256`
(see test_funded_config_firewall.py) — so the change is a loud, greppable, provenance-
carrying act rather than silent drift.
"""

# Exact copy of auto_safety.FUNDED_TIERS (certified 2026-07-02 rev b; re-confirmed 2026-07-05).
FUNDED_TIERS = {
    "50K":  dict(account="50K",  am=2, bm=1, daily_stop=400, worst_day=960),
    "150K": dict(account="150K", am=4, bm=2, daily_stop=800, worst_day=1921),
    "Apex-50K":          dict(account="50K",  firm="apex", am=4, bm=2, mm=2, daily_stop=550, worst_day=550,
                              dll=1000, kill_margin=0.85),    # PHASE 1: profit < +$2k, floor still trailing
    "Apex-50K-scaled":   dict(account="50K",  firm="apex", am=6, bm=3, mm=6, daily_stop=550, worst_day=550,
                              dll=1000, kill_margin=0.85),    # PHASE 2: profit >= +$2k, floor LOCKED at $50k
}

# Funded risk budget: RESEARCH VALUE, NOT YET a live constant (auto_safety.py / config_defaults.py
# have no such constant today — eval-phase sizing uses config_defaults.A_RISK_BUDGET_USD instead).
# (research value, pending funded re-lock — see vault Funded Funnel — 2026-07-05)
FUNDED_RISK_BUDGET_USD_CERTIFIED = 480
