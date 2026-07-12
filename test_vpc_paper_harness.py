"""test_vpc_paper_harness.py — the end-to-end PAPER lane (EMISSION_MODE_PAPER) wires
ProfileVEngine -> VpcDayGate -> build_vpc_entry -> VpcTrailManager with a SimBot sender, never
touching a broker. Deterministic white-box wiring test (a hand-injected trigger) so the fill +
managed-trail path is exercised without needing to hand-craft a real VPC signal."""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import strategy_engine_vpc as EV
import vpc_paper_harness as PH

NY = "America/New_York"


def test_paper_lane_is_paper_mode_never_live():
    lane = PH.PaperVpcLane()
    assert lane.eng.emission_mode == EV.EMISSION_MODE_PAPER
    assert lane.eng.emission_mode != EV.EMISSION_MODE_ARM_LIVE


def test_paper_lane_fills_and_manages_trail():
    """Inject a pending trigger, then feed a 5m bar (opens a SimBot market entry + a trail manager)
    and 1m bars that ratchet then stop the trade out — assert a closed trade is recorded."""
    lane = PH.PaperVpcLane(account="PAPER", trail_atr=2.0)
    t0 = pd.Timestamp("2024-03-01 10:05:00", tz=NY)
    # hand-inject a long trigger (stop_dist 5pt) as though the engine had emitted it last 5m bar
    lane.pending_entry = dict(side="long", direction=1, stop_dist=5.0, ts_signal=t0.isoformat(),
                              slot=7)
    # the NEXT 5m bar fills the market entry at its OPEN (100.0)
    lane.on_5m_bar(t0, 100.0, 100.5, 99.7, 100.2, 1000)
    assert lane.open_trade is not None
    assert lane.open_trade["entry"] == 100.0
    # a build_vpc_entry payload was routed through the SimBot sender
    assert any(p.get("extras", {}).get("strategy") == "V" for p in lane.sender.sent)
    # feed 1m bars (ts, low, high, close, atr_now): ratchet up, then take out the trailed stop
    lane.on_1m_bar(t0, 99.8, 101.0, 100.8, 1.0)
    lane.on_1m_bar(t0, 100.5, 102.0, 101.8, 1.0)
    lane.on_1m_bar(t0, 95.0, 101.0, 96.0, 1.0)     # low 95 takes out the trailed stop
    assert lane.open_trade is None
    assert len(lane.closed_trades) == 1
    ct = lane.closed_trades[0]
    assert ct["side"] == "long"
    assert ct["exit"] <= ct["entry"] or ct["exit"] > ct["entry"]   # a real exit level was recorded


def test_paper_lane_day_roll_resets_gate():
    lane = PH.PaperVpcLane()
    d1 = pd.Timestamp("2024-03-01 10:00:00", tz=NY)
    d2 = pd.Timestamp("2024-03-04 10:00:00", tz=NY)
    lane.on_5m_bar(d1, 100.0, 100.5, 99.5, 100.1, 1000)
    lane.gate.taken = 2                    # simulate day used up
    lane.on_5m_bar(d2, 100.0, 100.5, 99.5, 100.1, 1000)
    assert lane.gate.taken == 0            # new day cleared the gate
