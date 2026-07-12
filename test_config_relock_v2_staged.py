"""test_config_relock_v2_staged.py — D1: the STAGED V2 re-lock proposal is schema-compatible with
the live locked config (so the operator's go-live-recert.sh swap is MECHANICAL), carries the signed
C1 two-lane sizing, and — critically — stays DISARMED (the arming field defaults to shadow and the
current locked config does not even define it, so the VPC resolver resolves SHADOW today)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config_eval_locked as LOCKED
import config_relock_v2_staged as STAGED


# --- schema compatibility with the LOCKED file (mechanical-swap guarantee) ------------------------
LOCKED_SCALARS = ("EXIT_MODEL", "A_RISK_BUDGET_USD", "A_STOP_CAP_PTS",
                  "DAILY_STOP_POINTS", "POINT_VALUE_MNQ")


def test_staged_has_every_locked_name_with_matching_type():
    """Every top-level name the locked config exposes must exist in the staged proposal with the
    same Python type, so promoting the staged block into the locked file is a pure value swap."""
    for name in LOCKED_SCALARS + ("EVAL_TIERS_APEX_ROW",):
        assert hasattr(STAGED, name), f"staged config missing locked name {name!r}"
        assert type(getattr(STAGED, name)) is type(getattr(LOCKED, name)), (
            f"{name}: staged type {type(getattr(STAGED, name))} != locked "
            f"{type(getattr(LOCKED, name))}")


def test_eval_tiers_row_schema_matches_locked_exactly():
    """The RESOLVED Apex eval-tier row must carry the exact same keys as the locked row (values
    may differ — am 10->6 under C1 — but the schema is identical for a mechanical swap)."""
    assert set(STAGED.EVAL_TIERS_APEX_ROW) == set(LOCKED.EVAL_TIERS_APEX_ROW)
    # value TYPES per key match too (so nothing downstream that reads the row breaks on the swap)
    for k in LOCKED.EVAL_TIERS_APEX_ROW:
        assert type(STAGED.EVAL_TIERS_APEX_ROW[k]) is type(LOCKED.EVAL_TIERS_APEX_ROW[k]), (
            f"EVAL_TIERS_APEX_ROW[{k!r}] type differs")


# --- the signed C1 two-lane sizing basis ----------------------------------------------------------
def test_c1_two_lane_sizing_values():
    """DEC-20260712-RELOCK-V2-SIGNED: A $900 / cap 6, VPC $600 / cap 3, shared $550 ceiling."""
    assert STAGED.RELOCK_DEC == "DEC-20260712-RELOCK-V2-SIGNED"
    assert STAGED.A_RISK_BUDGET_USD == 900
    assert STAGED.LANE_CAPS == {"A": 6, "V": 3}
    assert STAGED.LANE_BUDGET_USD == {"A": 900.0, "V": 600.0}
    assert STAGED.COMBINED_OPEN_RISK_CEILING_USD == 550.0
    # A lane cap is reflected in the eval-tier row's am too
    assert STAGED.EVAL_TIERS_APEX_ROW["am"] == 6
    # the certified daily stop is unchanged by the re-lock
    assert STAGED.EVAL_TIERS_APEX_ROW["daily_stop"] == LOCKED.EVAL_TIERS_APEX_ROW["daily_stop"]


# --- disarmed-by-default: the arming field is staged-only and defaults to shadow -------------------
def test_arming_field_is_staged_only_and_defaults_shadow():
    """The lane-arming field must (a) exist in the staged proposal, (b) NOT exist in the current
    locked config, and (c) default to 'shadow' even in the proposal — so applying the sizing re-lock
    does not itself arm live routing, and the VPC resolver resolves SHADOW until an explicit flip."""
    assert hasattr(STAGED, "VPC_LANE_EMISSION_MODE")
    assert STAGED.VPC_LANE_EMISSION_MODE == "shadow"
    assert not hasattr(LOCKED, "VPC_LANE_EMISSION_MODE"), (
        "the locked config must NOT define VPC_LANE_EMISSION_MODE — its absence is what keeps the "
        "lane SHADOW today")


def test_staged_config_not_imported_by_live_paths():
    """The staged proposal must be inert: no live code path imports it (it is documentation until
    go-live-recert.sh promotes it)."""
    import glob
    here = os.path.dirname(os.path.abspath(__file__))
    live_files = ["auto_live.py", "auto_safety.py", "config_defaults.py", "config.py",
                  "bridge_traderspost.py", "bridge_sender.py", "strategy_engine_vpc.py",
                  "vpc_trail_manager.py", "vpc_lane_gate.py"]
    for fn in live_files:
        p = os.path.join(here, fn)
        if not os.path.exists(p):
            continue
        with open(p) as fh:
            for i, line in enumerate(fh, 1):
                stripped = line.lstrip()
                assert not (stripped.startswith("import config_relock_v2_staged")
                            or stripped.startswith("from config_relock_v2_staged")), (
                    f"{fn}:{i} IMPORTS the STAGED config — it must stay inert until arm-time")
