"""STAGED RE-LOCK PROPOSAL (V2) — NOT the live locked config. DO NOT import from any live path.

STATUS: STAGED PROPOSAL ONLY. This file is a version-controlled DRAFT of the two-lane (Profile A +
VPC) sizing re-lock. It is NOT the authority for any running machine and is imported by NO live code
path (auto_live.py / auto_safety.py / config_defaults.py / config.py / the bridge & engine files
never reference it). It exists so that:

  1. the eventual swap into the real locked config is MECHANICAL and reviewable — every scalar here
     is laid out in the SAME schema/style as `config_eval_locked.py`, and
     `test_config_relock_v2_staged.py` asserts schema-compatibility with that locked file, and
  2. the VPC lane's disarmed-by-default resolver (strategy_engine_vpc / auto_live) can document the
     single new field — `VPC_LANE_EMISSION_MODE` — that ARMS the lane. The CURRENT live/locked
     config does NOT contain that field, so the resolver always resolves SHADOW today. Only the
     operator's `go-live-recert.sh` process may promote this staged block into the live config (and
     re-hash `evidence/eval_config.sha256`); until it does, nothing here changes machine behavior.

>>> APPLICATION IS OPERATOR-GATED. The ONLY sanctioned way this proposal reaches a running machine
>>> is via `go-live-recert.sh` (config-hash firewall + companion-hash re-lock in the same commit).
>>> This file is inert documentation until then. No code in this repo imports it to make a decision.

PROVENANCE:
  - DEC-20260712-RELOCK-V2-SIGNED (two-lane C1 target): Profile A $900 size-to-risk / cap 6 contracts
    + VPC $600 size-to-risk / cap 3 contracts, sharing the certified $550 daily stop under a combined
    open-risk ceiling. Supersedes the single-lane cap-10 A-only sizing of DEC-20260705-1102 (the
    current `config_eval_locked.py`) IF AND ONLY IF the operator applies this re-lock.
  - The A/daily/point-value scalars below carry the SAME meaning as config_eval_locked.py; the
    A_RISK_BUDGET_USD and the A cap change (1200/10 -> 900/6) and the VPC block + emission field are
    what this re-lock ADDS. Numbers must trace to reports/apex_validation.json / the vault DEC at
    apply time exactly as the locked file's do.

RULE: while this file is STAGED it may drift only as the DEC does. At the moment it is applied it
becomes the locked config's content and this staged copy is retired (superseded), so the change is a
loud, greppable, provenance-carrying act — never silent drift.
"""

# =================================================================================================
# SCHEMA-COMPATIBLE with config_eval_locked.py (same names, same types) so the swap is mechanical.
# =================================================================================================
# --- Certified scalar constants (same schema as config_eval_locked.py) ---
EXIT_MODEL = "EXIT3_FIXED_PARTIAL"
A_RISK_BUDGET_USD = 900          # V2 RE-LOCK: was 1200 (cap-10 A-only) -> $900 two-lane C1
A_STOP_CAP_PTS = 0
DAILY_STOP_POINTS = 275
POINT_VALUE_MNQ = 2.0

# --- Certified live-eval tier row (same schema as config_eval_locked.EVAL_TIERS_APEX_ROW, RESOLVED) ---
# daily_stop stays 550.0 (APEX_DAILY_STOP = daily_stop_dollars() = 275 * 1 * $2). am drops 10 -> 6
# (the A lane cap under the two-lane C1); the VPC lane cap (3) lives in the VPC block below.
EVAL_TIERS_APEX_ROW = dict(
    account="50K", firm="apex", am=6, bm=5, mm=6, daily_stop=550.0, worst_day=550,
    dll=1000, kill_margin=0.70, eval_days=30, spray_accept_bust=True, requires_approval=True,
)

# =================================================================================================
# V2 ADDITIONS — the two-lane (Profile A + VPC) sizing block + the lane-arming field.
# These names do NOT exist in config_eval_locked.py; they are what this re-lock introduces.
# `VpcLaneRiskBook` reads caps/budget as constructor params, so at arm time the locked config (once
# this is promoted) is the single authority — never a value hard-coded into a shipped decision.
# =================================================================================================
# C1 target: A $900 size-to-risk / cap 6 ; VPC $600 size-to-risk / cap 3.
LANE_CAPS = {"A": 6, "V": 3}
LANE_BUDGET_USD = {"A": 900.0, "V": 600.0}
# Shared combined-open-risk ceiling both lanes admit against (the certified $550 daily stop).
COMBINED_OPEN_RISK_CEILING_USD = 550.0

# --- THE lane-arming field (disarmed-by-default) --------------------------------------------------
# The VPC lane emission mode. The CURRENT live/locked config (config_eval_locked.py / config_defaults)
# does NOT define this name, so strategy_engine_vpc.resolve_vpc_emission_mode() resolves SHADOW today.
# Promoting THIS staged file's value into the live config via go-live-recert.sh is the ONLY act that
# can set it to "arm_live". Kept "shadow" even in this proposal so that applying the sizing re-lock
# does NOT itself arm live routing — arming is a deliberate, separate flip of this one field.
VPC_LANE_EMISSION_MODE = "shadow"      # {"shadow","paper","arm_live"} — see EMISSION_MODES

# Signed basis marker (documentation only; the watchdog/tests key provenance off this).
RELOCK_DEC = "DEC-20260712-RELOCK-V2-SIGNED"
