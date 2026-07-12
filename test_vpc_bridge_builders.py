"""test_vpc_bridge_builders.py — the ADDITIVE VPC bridge payload builders (build_vpc_entry,
build_vpc_stop_replace) follow build_entry()'s fail-closed style, and — critically — do NOT alter
any pre-existing builder's output (the additive '_wire' stop-branch is proven inert for A/B)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bridge_traderspost as BP


# ---- build_vpc_entry: market entry + protective stop, NO target ----------------------------------
def test_vpc_entry_long_ok():
    p, err = BP.build_vpc_entry(account="ACC", signal_ts="2024-03-01T10:00:00-05:00",
                                side="long", qty=2, ref_price=100.13, stop_price=94.88)
    assert err is None
    assert p["action"] == "buy"
    assert p["orderType"] == "market"
    assert p["quantity"] == 2
    assert p["stopLoss"]["stopPrice"] == 95.0        # 94.88 rounded to tick, below entry
    assert "takeProfit" not in p                       # VPC has NO fixed target
    assert p["extras"]["signalId"].startswith("ZB-")
    assert p["extras"]["strategy"] == "V"
    assert p["price"] == 100.25                        # 100.13 rounded to tick (market price hint)


def test_vpc_entry_short_ok():
    p, err = BP.build_vpc_entry(account="ACC", signal_ts="t", side="short", qty=1,
                                ref_price=100.0, stop_price=105.0)
    assert err is None
    assert p["action"] == "sell"
    assert p["stopLoss"]["stopPrice"] == 105.0         # above entry for a short


def test_vpc_entry_fail_closed():
    # wrong-side stop (long with stop above entry) -> fail closed
    _, err = BP.build_vpc_entry(account="A", signal_ts="t", side="long", qty=1,
                                ref_price=100.0, stop_price=105.0)
    assert err is not None
    # qty <= 0
    _, err = BP.build_vpc_entry(account="A", signal_ts="t", side="long", qty=0,
                                ref_price=100.0, stop_price=95.0)
    assert err is not None
    # unknown side
    _, err = BP.build_vpc_entry(account="A", signal_ts="t", side="up", qty=1,
                                ref_price=100.0, stop_price=95.0)
    assert err is not None
    # stop == ref after rounding
    _, err = BP.build_vpc_entry(account="A", signal_ts="t", side="long", qty=1,
                                ref_price=100.0, stop_price=100.01)
    assert err is not None


def test_deterministic_entry_signal_id():
    a, _ = BP.build_vpc_entry(account="ACC", signal_ts="t1", side="long", qty=1,
                              ref_price=100.0, stop_price=95.0)
    b, _ = BP.build_vpc_entry(account="ACC", signal_ts="t1", side="long", qty=1,
                              ref_price=100.0, stop_price=95.0)
    c, _ = BP.build_vpc_entry(account="ACC", signal_ts="t2", side="long", qty=1,
                              ref_price=100.0, stop_price=95.0)
    assert a["extras"]["signalId"] == b["extras"]["signalId"]     # same slot -> same id
    assert a["extras"]["signalId"] != c["extras"]["signalId"]     # different ts -> different id


# ---- build_vpc_stop_replace: cancel-replace pair -------------------------------------------------
def test_stop_replace_pair_ok():
    pair, err = BP.build_vpc_stop_replace(account="ACC", signal_ts="t", side="long", qty=2,
                                          new_stop=97.13, seq=3)
    assert err is None
    cancel_payload, stop_payload = pair
    assert cancel_payload["action"] == "cancel"
    assert stop_payload["action"] == "stop"
    assert stop_payload["orderType"] == "stop"
    assert stop_payload["quantity"] == 2
    assert stop_payload["stopLoss"]["stopPrice"] == 97.25         # 97.13 rounded to tick
    assert stop_payload["extras"]["stop_side"] == "sell"          # protective stop for a long
    assert stop_payload["extras"]["seq"] == 3
    # cancel and stop have DISTINCT deterministic ids
    assert cancel_payload["extras"]["signalId"] != stop_payload["extras"]["signalId"]


def test_stop_replace_seq_makes_unique_ids():
    p0, _ = BP.build_vpc_stop_replace(account="A", signal_ts="t", side="long", qty=1,
                                      new_stop=97.0, seq=0)
    p1, _ = BP.build_vpc_stop_replace(account="A", signal_ts="t", side="long", qty=1,
                                      new_stop=97.5, seq=1)
    assert p0[1]["extras"]["signalId"] != p1[1]["extras"]["signalId"]   # seq distinguishes replaces


def test_stop_replace_short_side():
    pair, err = BP.build_vpc_stop_replace(account="A", signal_ts="t", side="short", qty=1,
                                          new_stop=103.0, seq=0)
    assert err is None
    assert pair[1]["extras"]["stop_side"] == "buy"                # protective stop for a short


def test_stop_replace_fail_closed():
    _, err = BP.build_vpc_stop_replace(account="A", signal_ts="t", side="up", qty=1,
                                       new_stop=97.0, seq=0)
    assert err is not None
    _, err = BP.build_vpc_stop_replace(account="A", signal_ts="t", side="long", qty=0,
                                       new_stop=97.0, seq=0)
    assert err is not None


# ---- ADDITIVE proof: existing A/B builders are byte-unchanged by the new stop-branch -------------
def test_existing_build_entry_unaffected():
    """The additive '_wire' stop-branch and the new builders must not alter build_entry's output."""
    p, err = BP.build_entry(account="ACC", strategy="A", setup="ote",
                            signal_ts="2024-03-01T10:00:00-05:00", side="long", qty=2,
                            entry=100.0, stop=98.0, target=104.0, root="MNQ")
    assert err is None
    assert p["action"] == "buy"
    assert p["orderType"] == "limit"
    assert p["stopLoss"] == {"type": "stop", "stopPrice": 98.0}
    assert p["takeProfit"] == {"limitPrice": 104.0}
    assert p["extras"]["strategy"] == "A"


def test_existing_build_cancel_unaffected():
    p, err = BP.build_cancel(account="ACC", strategy="A", signal_ts="t")
    assert err is None
    assert p["action"] == "cancel"
    assert "quantity" not in p            # cancel stays minimal — the stop-branch didn't touch it
