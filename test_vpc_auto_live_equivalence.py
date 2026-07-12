"""test_vpc_auto_live_equivalence.py — D2: the VPC lane is wired into auto_live ADDITIVELY and stays
DISARMED (SHADOW), so with it wired the A/B machine is byte-equivalent. Proves:
  * the lane constructs in SHADOW (resolve_vpc_emission_mode() -> shadow; the locked config defines
    no arming field),
  * on_v_signal in SHADOW touches NO A/B state (sender, open_risk, counters, P&L ledger),
  * the daily-P&L `_dp` aggregation (trade_results.day_entered_pnl) already sums A + B + V,
  * _on_missing_cancel_is_safe is unchanged when the V lane holds nothing,
  * nothing in the repo constructs an armed VPC engine (disarmed-chain invariant).
"""
import os
import sys

import pytest
from store import Store
from journal import Journal
from bridge_sender import BridgeSender

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auto_live
import strategy_engine_vpc as EV
import trade_results as TR


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for d in ("data", "evidence/approvals", "out/ares", "logs/vpc"):
        os.makedirs(d, exist_ok=True)
    return Store("data/b.db"), Journal("data/j.db")


def _auto(env):
    s, j = env
    return auto_live.LiveAuto("MFFU-50K-1", "50K-conservative", "paper", s, j,
                              BridgeSender(store=s, journal=j, mode="dry-run"), 700,
                              d1c_mode="SHADOW")


def _vsig(side="long"):
    d = 1 if side == "long" else -1
    return dict(side=side, direction=d, stop_dist=10.0, entry_bar_offset=1,
                ts_signal="2024-03-01T10:00:00-05:00", slot=6, atr=4.0, vwap=100.0,
                ref_close=100.0, profile="V", emission_mode="shadow")


# --- resolver + construction -----------------------------------------------------------------------
def test_resolver_is_shadow_today():
    """The live config defines no VPC_LANE_EMISSION_MODE, so the resolver returns SHADOW."""
    import config_defaults as CD
    assert not hasattr(CD, "VPC_LANE_EMISSION_MODE"), (
        "config_defaults must NOT define the arming field — its absence keeps the lane SHADOW")
    assert EV.resolve_vpc_emission_mode() == EV.EMISSION_MODE_SHADOW


def test_lane_constructs_in_shadow(env):
    auto = _auto(env)
    assert auto.v_engine is not None                 # lane wired
    assert auto.v_emission == EV.EMISSION_MODE_SHADOW
    assert auto.v_engine.emission_mode == EV.EMISSION_MODE_SHADOW
    assert auto.v_gate is not None and auto.v_book is not None and auto.v_journal is not None


# --- on_v_signal in SHADOW is inert for A/B --------------------------------------------------------
def test_on_v_signal_shadow_touches_no_ab_state(env):
    auto = _auto(env)
    # capture A/B observables before
    sent_before, b_before = auto.sent, auto.b_sent
    open_risk_before = dict(auto.open_risk)
    sends_before = len(getattr(auto.sender, "sent_payloads", []) or [])
    # SHADOW on_v_signal
    auto.on_v_signal(_vsig("long"), ts="2024-03-01T10:00:00-05:00", bar_i=3)
    # A/B counters + risk book untouched; V only bumps its OWN blocked counter
    assert auto.sent == sent_before and auto.b_sent == b_before
    assert dict(auto.open_risk) == open_risk_before
    assert "V" not in auto.open_risk
    assert auto.v_book.combined_open_risk() == 0.0    # SHADOW never reserves/opens
    assert auto.v_sent == 0
    assert auto.v_blocked == 1                         # recorded as a disarmed missed-fill
    # NO order was routed
    assert len(getattr(auto.sender, "sent_payloads", []) or []) == sends_before
    # NO row written to the P&L ledger
    assert not os.path.exists(TR.PATH) or TR.day_entered_pnl(auto.account, "2024-03-01") == 0.0


def test_on_v_signal_shadow_journals_only(env):
    auto = _auto(env)
    auto.on_v_signal(_vsig("short"), ts="t", bar_i=1)
    # the observational signal journal exists (fail-open), but it is NOT the A/B P&L ledger
    sig_dir = os.path.join("logs", "vpc", "signal")
    assert os.path.isdir(sig_dir), "V lane should journal the raw trigger (observe-only)"


# --- _dp aggregation is strategy-agnostic (A + B + V) ----------------------------------------------
def test_dp_aggregation_includes_v(env):
    """day_entered_pnl sums EVERY entered row for the account/day, so a strategy='V' row is included
    in the same daily-stop total as A and B — the _dp extension is inherent, not a separate path."""
    auto = _auto(env)
    TR.record("2024-03-01", "paper", auto.account, "A", "long", 3, -100.0, note="fill-backed")
    TR.record("2024-03-01", "paper", auto.account, "B", "short", 2, -50.0, note="fill-backed")
    TR.record("2024-03-01", "paper", auto.account, "V", "long", 1, -75.0, note="fill-backed")
    total = TR.day_entered_pnl(auto.account, "2024-03-01")
    assert total == -225.0                             # A + B + V summed together


# --- _on_missing_cancel_is_safe unchanged when V holds nothing -------------------------------------
def test_cancel_guard_unaffected_when_v_flat(env):
    auto = _auto(env)
    safe, reason = auto_live._on_missing_cancel_is_safe(auto)
    assert safe and "single-lane" in reason           # V flat -> A-only cancel still safe


def test_cancel_guard_blocks_when_v_open(env):
    auto = _auto(env)
    auto.v_book.on_open("V", stop_pts=10.0, qty=1, side="long")   # simulate an (arm-time) open V lane
    safe, reason = auto_live._on_missing_cancel_is_safe(auto)
    assert not safe and "V lane open" in reason


# --- disarmed-chain invariant ----------------------------------------------------------------------
def test_no_repo_code_constructs_arm_live():
    """No production code path may CONSTRUCT/SET arm_live. Comparisons/guards against the arm_live
    value are fine (that IS the disarmed guard); what is forbidden is an actual assignment that turns
    the lane live — e.g. emission_mode="arm_live" or VPC_LANE_EMISSION_MODE = "arm_live". Only the
    operator's go-live-recert.sh (outside this repo's code) may set the live field."""
    here = os.path.dirname(os.path.abspath(__file__))
    live_files = ["auto_live.py", "strategy_engine_vpc.py", "vpc_trail_manager.py",
                  "vpc_lane_gate.py", "vpc_paper_harness.py", "vpc_journal.py",
                  "bridge_traderspost.py", "config_defaults.py"]
    for fn in live_files:
        p = os.path.join(here, fn)
        if not os.path.exists(p):
            continue
        with open(p) as fh:
            for i, line in enumerate(fh, 1):
                if line.lstrip().startswith("#"):
                    continue                      # comments are documentation, not construction
                packed = line.replace(" ", "")
                assert 'emission_mode="arm_live"' not in packed, (
                    f"{fn}:{i} constructs an engine with arm_live: {line.strip()}")
                assert 'VPC_LANE_EMISSION_MODE="arm_live"' not in packed, (
                    f"{fn}:{i} sets the live arming field to arm_live: {line.strip()}")
