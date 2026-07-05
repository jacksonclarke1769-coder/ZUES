"""EVAL-PHASE CONFIG FIREWALL — frozen declarative snapshot of the LIVE EVAL machine.

STATUS: DOCUMENTATION + GUARD ONLY. This file is NOT imported by any live code path
(auto_live.py, auto_safety.py, config_defaults.py, config.py, bridge/engine files never
reference it). It exists solely so that `test_eval_config_firewall.py` — and, at runtime,
the independent reconciliation WATCHDOG (invariant CONFIG INTEGRITY) — have a frozen,
version-controlled copy of the certified eval constants to diff live values against.

This mirrors config_funded_locked.py, extended to the LIVE EVAL machine (Apex-50K-eval).

PROVENANCE:
  - DEC-20260705-1102 (cap-10 re-lock correction; see README.md "Certified Eval Numbers"
    and reports/risk_arithmetic_reconciliation_2026-07-05.md).
  - Certified machine: A10 · Exit#3 · D1c ACTIVE_EVAL_FILTER · size-to-risk $1,200 · B OFF ·
    momentum OFF · $550 daily stop (AGENTS.md "ZEUS Production Machine v2026.07.02 rev b").
  - The scalar values below are a byte-for-byte copy of the certified `config_defaults.py`
    constants; EVAL_TIERS_APEX_ROW is a byte-for-byte copy of the RESOLVED
    `auto_safety.EVAL_TIERS["Apex-50K-eval"]` row (daily_stop already resolved from
    APEX_DAILY_STOP = daily_stop_dollars() = 275 * 1 * $2 = 550.0).

RULE: no eval-sizing/exit-model change may touch this file as a side effect. If the live
constants legitimately change (a deliberate, audited eval re-certification), this file MUST
be updated in the SAME commit — together with `evidence/eval_config.sha256` (the locked-file
self-hash AND the config_defaults.py / auto_safety.py companion hashes the watchdog checks) —
so the change is a loud, greppable, provenance-carrying act rather than silent drift.
"""

# --- Certified scalar constants (exact copy of config_defaults.py, certified 2026-07-02 rev b) ---
EXIT_MODEL = "EXIT3_FIXED_PARTIAL"
A_RISK_BUDGET_USD = 1200
A_STOP_CAP_PTS = 0
DAILY_STOP_POINTS = 275
POINT_VALUE_MNQ = 2.0

# --- Certified live-eval tier row (exact copy of auto_safety.EVAL_TIERS["Apex-50K-eval"], RESOLVED) ---
# daily_stop is 550.0 because APEX_DAILY_STOP = daily_stop_dollars() resolves to a float at import.
EVAL_TIERS_APEX_ROW = dict(
    account="50K", firm="apex", am=10, bm=5, mm=6, daily_stop=550.0, worst_day=550,
    dll=1000, kill_margin=0.70, eval_days=30, spray_accept_bust=True, requires_approval=True,
)
