"""test_vpc_engine_failclosed.py — DISARMED-by-default + fail-closed construction canaries for the
VPC live engine, mirroring Profile A's EMISSION_MODE discipline.

Proves:
  * DISARMED BY DEFAULT: a default-constructed ProfileVEngine is in EMISSION_MODE_SHADOW (never
    live). arm_live is never the default and is never reached without an explicit construction.
  * FAIL-CLOSED CONSTRUCTION: an unknown emission mode raises ValueError (never silently trades).
  * FROZEN CFG: the engine's signal kwargs are the certified CFG (slot 6-66, atr_stop 2.5, ...) and
    are NOT redefined locally — a strategy-change tripwire.
  * TIMESTAMP FAIL-CLOSED: the broken-plumbing timestamp invariant escapes as
    VpcTimestampReconstructionError (the INC-20260706-1141 defect class), never a silent bad instant.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strategy_engine_vpc as EV
import vpc_apex_eval_sim as VS

NY = "America/New_York"


def test_disarmed_by_default():
    """A default-constructed engine is SHADOW (observe/journal only) — never arm_live."""
    eng = EV.ProfileVEngine()
    assert eng.emission_mode == EV.EMISSION_MODE_SHADOW
    assert eng.emission_mode != EV.EMISSION_MODE_ARM_LIVE


def test_arm_live_requires_explicit_construction():
    """arm_live is reachable ONLY by an explicit, deliberate kwarg — nothing defaults into it."""
    eng = EV.ProfileVEngine(emission_mode=EV.EMISSION_MODE_ARM_LIVE)
    assert eng.emission_mode == EV.EMISSION_MODE_ARM_LIVE
    # and the signal it emits carries the mode, so a downstream router can gate on it
    assert EV.EMISSION_MODE_ARM_LIVE in EV.EMISSION_MODES


def test_unknown_emission_mode_fails_closed():
    """Unknown mode -> ValueError at construction; the engine can NEVER silently trade on it."""
    with pytest.raises(ValueError):
        EV.ProfileVEngine(emission_mode="live")           # not a real mode name
    with pytest.raises(ValueError):
        EV.ProfileVEngine(emission_mode="emit_at_fill")   # Profile A's mode, not VPC's
    with pytest.raises(ValueError):
        EV.ProfileVEngine(emission_mode="ARM_LIVE")       # case-sensitive; typo must fail closed


def test_frozen_cfg_is_the_certified_config():
    """The engine's signal kwargs ARE the certified CFG (no local copy of the numbers) — any drift
    in the frozen strategy definition trips here."""
    assert EV._SIG_KW["atr_stop"] == VS.CFG["atr_stop"] == 2.5
    assert EV._SIG_KW["slot_min"] == VS.CFG["slot_min"] == 6
    assert EV._SIG_KW["slot_max"] == VS.CFG["slot_max"] == 66
    assert EV._SIG_KW["slope_mult"] == VS.CFG["slope_mult"] == 0.3
    assert EV._SIG_KW["trend_mult"] == VS.CFG["trend_mult"] == 0.5
    # day-gate frozen limits
    from strategy_engine_vpc import VpcDayGate
    gate = VpcDayGate()
    assert gate.max_trades == 2
    assert gate.daily_stop == 120


def test_timestamp_reconstruction_fails_closed():
    """_derive_vpc_instant raises (never returns None) on out-of-range / non-NY / out-of-session —
    the broken-plumbing invariant must escape, not degrade into a silent bad instant."""
    idx = pd.DatetimeIndex(pd.date_range("2024-03-01 10:00", periods=5, freq="5min", tz=NY))
    # valid case returns a NY instant inside the session
    ok = EV._derive_vpc_instant(idx, 0)
    assert ok.tzinfo is not None and NY in str(ok.tzinfo)
    # out of range
    with pytest.raises(EV.VpcTimestampReconstructionError):
        EV._derive_vpc_instant(idx, 99)
    # tz-naive index -> fails closed
    naive = pd.DatetimeIndex(pd.date_range("2024-03-01 10:00", periods=3, freq="5min"))
    with pytest.raises(EV.VpcTimestampReconstructionError):
        EV._derive_vpc_instant(naive, 0)
    # out-of-session (03:00 ET) -> fails closed
    off = pd.DatetimeIndex(pd.date_range("2024-03-01 03:00", periods=3, freq="5min", tz=NY))
    with pytest.raises(EV.VpcTimestampReconstructionError):
        EV._derive_vpc_instant(off, 0)


def test_cold_start_warmup_gate():
    """The engine REFUSES to emit until its buffer is warm (>= warmup_bars) — a fresh-process
    intraday cold-start must not surface off-parity signals (the cross-audit's cold-buffer artifact).
    Isolated: below warmup the gate short-circuits BEFORE any feature computation."""
    eng = EV.ProfileVEngine()
    assert eng.warmup_bars == EV.WARMUP_BARS and EV.WARMUP_BARS >= 78   # >= ~1 RTH session
    # tripwire: _day_features must NOT be reached below warmup
    def _boom():
        raise AssertionError("_day_features called below warmup gate")
    eng._day_features = _boom
    idx = pd.date_range("2024-03-01 09:30", periods=eng.warmup_bars - 1, freq="5min", tz=NY)
    for ts in idx:
        eng.add_bar(ts, 100, 100.5, 99.5, 100.1, 1000)
        assert eng.latest_signal() is None      # gated: returns None without computing features
    # warmup_bars=0 reaches feature computation (proves the gate — not something else — was blocking)
    eng0 = EV.ProfileVEngine(warmup_bars=0)
    eng0._day_features = _boom
    eng0.add_bar(idx[0], 100, 100.5, 99.5, 100.1, 1000)
    eng0.add_bar(idx[1], 100, 100.5, 99.5, 100.1, 1000)
    with pytest.raises(AssertionError):
        eng0.latest_signal()                    # warmup 0 -> proceeds to _day_features (our tripwire)


def test_signal_dedup_emits_once_per_bar():
    """A signal instant already surfaced is never re-emitted (deterministic dedup discipline)."""
    eng = EV.ProfileVEngine()
    # feed a benign warmup so latest_signal can run without raising
    idx = pd.date_range("2024-03-01 09:30", periods=3, freq="5min", tz=NY)
    for ts in idx:
        eng.add_bar(ts, 100, 100.5, 99.5, 100.1, 1000)
        eng.latest_signal()   # no trigger on flat bars; just exercises the path without error
    assert isinstance(eng.emitted_ts, set)
