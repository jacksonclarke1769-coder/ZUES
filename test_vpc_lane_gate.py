"""test_vpc_lane_gate.py — two-lane (A + VPC) risk accounting: per-lane contract caps (A cap-6 /
VPC cap-3 per C1), per-lane size-to-risk budgets, and the shared combined-open-risk ceiling
(combined_open + new <= remaining_daily_budget). The conflict rule (both lanes MAY hold; no
direction block; opposite-direction stacking is OBSERVED not vetoed pending a DEC) is asserted too.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vpc_lane_gate import VpcLaneRiskBook, C1_LANE_CAPS, C1_LANE_BUDGET_USD

PV = 2.0   # $/pt/MNQ


def _book(daily=3000.0, **over):
    kw = dict(daily_budget_usd=daily, point_value=PV)
    kw.update(over)
    return VpcLaneRiskBook(**kw)


def test_construction_fail_closed():
    with pytest.raises(ValueError):
        VpcLaneRiskBook(daily_budget_usd=0, point_value=PV)
    with pytest.raises(ValueError):
        VpcLaneRiskBook(daily_budget_usd=1000, point_value=0)


def test_c1_defaults():
    assert C1_LANE_CAPS == {"A": 6, "V": 3}
    assert C1_LANE_BUDGET_USD == {"A": 900.0, "V": 600.0}


def test_per_lane_contract_cap_vpc_three():
    """VPC caps at 3 contracts even when budget/risk would allow more."""
    b = _book()
    # tiny risk (1pt -> $2/ct); VPC lane budget 600 -> 300 ct by budget, but cap=3 binds
    ok, q, why = b.admit("V", stop_pts=1.0, requested_qty=100)
    assert ok and q == 3, (q, why)


def test_per_lane_contract_cap_a_six():
    b = _book()
    ok, q, why = b.admit("A", stop_pts=1.0, requested_qty=100)
    assert ok and q == 6, (q, why)


def test_per_lane_budget_sizes_down():
    """VPC size-to-risk budget 600: at 50pt stop ($100/ct) -> 6 by budget, but cap 3 still binds;
    at a risk where budget is the binding constraint below the cap, budget sizes down."""
    b = _book()
    # 120pt stop -> $240/ct; VPC budget 600 -> floor(600/240)=2 contracts (below cap 3) -> budget binds
    ok, q, why = b.admit("V", stop_pts=120.0, requested_qty=3)
    assert ok and q == 2, (q, why)


def test_combined_open_risk_ceiling():
    """Once A holds risk, VPC admission is bounded by the SHARED remaining daily budget."""
    b = _book(daily=1000.0)
    # A opens with $800 of open risk
    ok, q, _ = b.admit("A", stop_pts=40.0, requested_qty=10)   # $80/ct, budget A 900 -> 11 -> cap 6
    assert ok
    b.on_open("A", stop_pts=40.0, qty=q, side="long")
    assert b.combined_open_risk() == 40.0 * PV * q
    # now only (1000 - open) remains for VPC combined ceiling
    rem = b.remaining_daily_budget()
    assert rem == max(0.0, 1000.0 - 40.0 * PV * q)
    # VPC wants big size but the combined ceiling sizes it down (or blocks if nothing fits)
    ok2, q2, why2 = b.admit("V", stop_pts=100.0, requested_qty=3)   # $200/ct
    fit = int(rem // (100.0 * PV))
    if fit >= 1:
        assert ok2 and q2 == min(3, fit), (q2, why2, rem)
    else:
        assert not ok2


def test_both_lanes_may_hold_simultaneously():
    """Decorrelated by design — the gate never blocks VPC merely because A is open (only the
    combined budget can size it down)."""
    b = _book(daily=100000.0)               # huge budget -> only caps bind
    okA, qA, _ = b.admit("A", stop_pts=10.0, requested_qty=6)
    b.on_open("A", stop_pts=10.0, qty=qA, side="long")
    okV, qV, _ = b.admit("V", stop_pts=10.0, requested_qty=3)
    assert okA and okV and qV == 3          # VPC admitted while A holds


def test_lane_reopen_blocked_until_close():
    b = _book(daily=100000.0)
    ok, q, _ = b.admit("V", stop_pts=10.0, requested_qty=3)
    b.on_open("V", stop_pts=10.0, qty=q, side="long")
    ok2, q2, why2 = b.admit("V", stop_pts=10.0, requested_qty=3)
    assert not ok2 and "already holds" in why2
    b.on_close("V")
    ok3, q3, _ = b.admit("V", stop_pts=10.0, requested_qty=3)
    assert ok3


def test_opposite_direction_is_observed_not_blocked():
    """The conflict rule: opposite-direction A+VPC stacking is FLAGGED (observational) but NEVER
    vetoed here — the blocking policy is reserved to an operator DEC."""
    b = _book(daily=100000.0)
    okA, qA, _ = b.admit("A", stop_pts=10.0, requested_qty=6)
    b.on_open("A", stop_pts=10.0, qty=qA, side="long")
    # VPC short while A is long -> admission still succeeds (no veto)
    okV, qV, _ = b.admit("V", stop_pts=10.0, requested_qty=3, side="short")
    assert okV and qV == 3
    b.on_open("V", stop_pts=10.0, qty=qV, side="short")
    flag = b.flag_opposite_direction("V", "short")
    assert flag == {"A": "long"}            # observed, not blocked


def test_new_day_clears_book():
    b = _book()
    ok, q, _ = b.admit("A", stop_pts=10.0, requested_qty=6)
    b.on_open("A", stop_pts=10.0, qty=q, side="long")
    assert b.combined_open_risk() > 0
    b.new_day()
    assert b.combined_open_risk() == 0.0
    assert b.open_side == {}


def test_zero_fit_blocks():
    b = _book(daily=50.0)                    # $50 total budget
    ok, q, why = b.admit("V", stop_pts=100.0, requested_qty=3)   # $200/ct > budget
    assert not ok and q == 0 and "no size fits" in why
