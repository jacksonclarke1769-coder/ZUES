"""SLIP-PIN CANARY (fork_a/05, operator-authorized 2026-07-17).

Every certification of Profile A was computed at slip_ticks=8 (A_PARAMS["exit3"],
apex_sim.py, apex_eval_deployed.py, replay_eval30.py, apex_joint_bar_sim.py). model01's
module default is slip_ticks=2. Before this pin, the LIVE engine passed bare PROFILE_A to
both emission paths and silently inherited slip=2 — posting the resting limit 1.5pt deeper
than anything certified (fewer fills, uncertified fill distribution).

These tests make that drift impossible to reintroduce silently:
  1. PROFILE_A itself must pin slip_ticks=8.
  2. The pin must EQUAL the certified harness value (ties live to certification — if a
     future re-certification changes slip, both sides must move together, loudly).
  3. model01's module default must still differ, proving the pin is load-bearing (if the
     default ever becomes 8 this canary flags it so the comment/rationale can be retired,
     rather than leaving a stale pin nobody understands).
"""
import os, sys

BOT = os.path.dirname(os.path.abspath(__file__))
FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
for p in (os.path.join(FW, "engine"), os.path.join(FW, "models"),
          os.path.expanduser("~/trading-team/backtests"), FW, BOT):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_profile_a_pins_slip_8():
    from strategy_engine_profileA import PROFILE_A
    assert PROFILE_A.get("slip_ticks") == 8, (
        "PROFILE_A must pin slip_ticks=8 (certified basis, fork_a/05). "
        f"Got: {PROFILE_A.get('slip_ticks')!r}"
    )


def test_pin_matches_certified_harness():
    from strategy_engine_profileA import PROFILE_A
    from tools_1m_truth_recert import A_PARAMS
    cert = A_PARAMS["exit3"].get("slip_ticks")
    assert cert == PROFILE_A.get("slip_ticks"), (
        "Live emission slip must equal the certified harness slip "
        f"(certified={cert!r}, live={PROFILE_A.get('slip_ticks')!r}). "
        "If re-certifying at a new slip, change BOTH together."
    )


def test_pin_is_load_bearing_vs_model_default():
    import model01_sweep_mss_fvg as M1
    from strategy_engine_profileA import PROFILE_A
    default = getattr(M1, "DEFAULT_PARAMS", {}).get("slip_ticks", 2)
    if default == PROFILE_A.get("slip_ticks"):
        raise AssertionError(
            "model01's default slip now equals the pin — the pin is no longer load-bearing. "
            "Retire/update the pin rationale in strategy_engine_profileA.py deliberately."
        )
