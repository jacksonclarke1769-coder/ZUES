"""test_vpc_bridge_builders.py — the ADDITIVE VPC bridge payload builders (build_vpc_entry,
build_vpc_stop_replace) follow build_entry()'s fail-closed style, and — critically — do NOT alter
any pre-existing builder's output (the additive '_wire' stop_replace branch, keyed on an explicit
flag, is proven inert for A/B: buy/sell/add/exit/cancel never set stop_replace=True)."""
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


# ---- build_vpc_stop_replace: D6 SINGLE-CALL bundled cancel-replace -------------------------------
def test_stop_replace_single_call_ok():
    """D6: ONE payload — a valid exit-side action + orderType 'stop' + stopPrice + cancel:true (the
    bundled server-side cancel-replace). 'stop' is NOT a valid action; it is only the orderType."""
    payload, err = BP.build_vpc_stop_replace(account="ACC", signal_ts="t", side="long", qty=2,
                                             new_stop=97.13, seq=3)
    assert err is None
    assert payload["action"] == "sell"                # protective stop for a LONG = a resting SELL
    assert payload["orderType"] == "stop"
    assert payload["quantity"] == 2
    assert payload["stopPrice"] == 97.25              # 97.13 rounded to tick
    assert payload["price"] == 97.25                  # Tradovate needs an explicit price
    assert payload["cancel"] is True                  # bundled server-side cancel of the prior stop
    assert payload["extras"]["stop_side"] == "sell"
    assert payload["extras"]["seq"] == 3
    assert payload["extras"]["cancel_bundled"] is True
    assert payload["extras"]["signalId"].startswith("ZB-")


def test_stop_replace_seq_makes_unique_ids():
    p0, _ = BP.build_vpc_stop_replace(account="A", signal_ts="t", side="long", qty=1,
                                      new_stop=97.0, seq=0)
    p1, _ = BP.build_vpc_stop_replace(account="A", signal_ts="t", side="long", qty=1,
                                      new_stop=97.5, seq=1)
    assert p0["extras"]["signalId"] != p1["extras"]["signalId"]   # seq distinguishes replaces


def test_stop_replace_short_side():
    payload, err = BP.build_vpc_stop_replace(account="A", signal_ts="t", side="short", qty=1,
                                             new_stop=103.0, seq=0)
    assert err is None
    assert payload["action"] == "buy"                            # protective stop for a SHORT = BUY
    assert payload["extras"]["stop_side"] == "buy"


def test_stop_replace_action_is_never_the_string_stop():
    """Guard against regressing to the invalid action:'stop' (an orderType, not an action — it 400s
    or, on Tradovate BETA, silently falls back to the strategy default)."""
    for side in ("long", "short"):
        payload, err = BP.build_vpc_stop_replace(account="A", signal_ts="t", side=side, qty=1,
                                                 new_stop=97.0 if side == "long" else 103.0, seq=0)
        assert err is None
        assert payload["action"] in ("buy", "sell")
        assert payload["action"] != "stop"


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


# ---- HARDENING: round_tick rejects non-finite prices --------------------------------------------
def test_round_tick_rejects_nan_inf():
    for bad in (float("nan"), float("inf"), float("-inf"), None):
        with pytest.raises(ValueError):
            BP.round_tick(bad, "MNQ")


def test_vpc_builders_fail_closed_on_nan():
    """A NaN stop must never emit a `stopPrice: nan` payload — the builders fail closed."""
    _, err = BP.build_vpc_entry(account="A", signal_ts="t", side="long", qty=1,
                                ref_price=100.0, stop_price=float("nan"))
    assert err is not None
    _, err = BP.build_vpc_stop_replace(account="A", signal_ts="t", side="long", qty=1,
                                       new_stop=float("nan"), seq=0)
    assert err is not None
