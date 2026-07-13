"""core/config.py: ParamSet / ICT_V2_PARAMS_V0 -- immutability + v0 pins present."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from research.ict_v2.core.config import ICT_V2_PARAMS_V0, ParamSet


def test_param_version_is_the_v0_tag():
    assert ICT_V2_PARAMS_V0.param_version == "ICT_V2_PARAMS_V0"


def test_frozen_cannot_set_attribute():
    with pytest.raises(FrozenInstanceError):
        ICT_V2_PARAMS_V0.swing_left = 5  # type: ignore[misc]


def test_tuple_fields_are_actually_tuples_not_lists():
    assert isinstance(ICT_V2_PARAMS_V0.sweep_h_bars, tuple)
    assert isinstance(ICT_V2_PARAMS_V0.ote_band, tuple)
    assert isinstance(ICT_V2_PARAMS_V0.or_duration_minutes_options, tuple)


def test_constructing_a_new_paramset_does_not_affect_v0_singleton():
    other = ParamSet(
        **{**ICT_V2_PARAMS_V0.__dict__, "param_version": "ICT_V2_PARAMS_V1", "swing_left": 5}
    )
    assert other.swing_left == 5
    assert ICT_V2_PARAMS_V0.swing_left == 3  # untouched


# --- every v0 pin named in SPEC.md's "Engine definitions (v0 pins)" section ----

def test_swing_pins():
    p = ICT_V2_PARAMS_V0
    assert (p.swing_left, p.swing_right) == (3, 3)
    assert p.swing_b_min_reversal_ticks == 8
    assert p.swing_b_min_reversal_atr_mult == 0.25
    assert p.swing_c_lookback_bars == 20


def test_level_pins():
    p = ICT_V2_PARAMS_V0
    assert p.equal_level_tolerance_ticks == 2
    assert p.equal_level_min_bars_apart == 5
    assert p.equal_level_max_sessions_old == 3
    assert p.level_expiry_sessions_intraday == 2
    assert p.level_expiry_sessions_weekly == 5
    assert p.level_test_tolerance_ticks == 1
    assert (p.round_number_step, p.round_number_minor_step) == (100, 50)


def test_sweep_fsm_pins():
    p = ICT_V2_PARAMS_V0
    assert p.sweep_h_bars == (1, 3, 6)
    assert p.sweep_h_default == 3
    assert p.sweep_reclaim_rule == "close_back_inside"


def test_zone_pins():
    p = ICT_V2_PARAMS_V0
    assert p.fvg_min_ticks == 4
    assert p.fvg_expiry_mode == "full_session"
    assert p.orderblock_scan_back_bars == 10
    assert p.orderblock_zone_mode == "full_candle"


def test_ote_pins():
    p = ICT_V2_PARAMS_V0
    assert p.ote_band == (0.62, 0.79)
    assert p.ote_control_band_low == (0.38, 0.55)
    assert p.ote_control_band_high == (0.80, 0.97)


def test_amd_pins():
    p = ICT_V2_PARAMS_V0
    assert p.amd_range_atr_mult == 0.6
    assert p.amd_range_window_bars == 12
    assert p.amd_range_min_bars == 6
    assert p.amd_manipulation_reclaim_bars == 6
    assert p.amd_distribution_window_bars == 12


def test_displacement_pins():
    p = ICT_V2_PARAMS_V0
    assert p.displacement_body_mult == 1.5
    assert p.displacement_sigma_tod_lookback_sessions == 20
    assert p.displacement_volume_z_lookback_bars == 20


def test_structure_pins():
    p = ICT_V2_PARAMS_V0
    assert p.mss_window_bars == 12
    assert p.break_type == "close"


def test_opening_range_pins():
    p = ICT_V2_PARAMS_V0
    assert p.or_duration_minutes_default == 15
    assert p.or_duration_minutes_options == (5, 15, 30)


def test_tick_size_pin():
    assert ICT_V2_PARAMS_V0.tick_size == 0.25


# --- internal consistency validation -------------------------------------------

def test_sweep_h_default_must_be_in_family():
    kwargs = {**ICT_V2_PARAMS_V0.__dict__, "sweep_h_default": 99}
    with pytest.raises(ValueError):
        ParamSet(**kwargs)


def test_or_duration_default_must_be_in_options():
    kwargs = {**ICT_V2_PARAMS_V0.__dict__, "or_duration_minutes_default": 99}
    with pytest.raises(ValueError):
        ParamSet(**kwargs)
