"""Tests for the bridge_test.py Stage-2 1-MNQ helper (no network — sender is faked)."""
import os

import bridge_test


class FakeSender:
    last = None

    def __init__(self, *a, **k):
        pass

    def send(self, payload):
        FakeSender.last = payload
        return {"sent": True, "status": 200}


def test_one_mnq_forces_qty_1_and_attaches_bracket(monkeypatch, tmp_path):
    monkeypatch.setenv("TRADERSPOST_TEST_URL", "https://example.test/webhook")
    monkeypatch.setattr(bridge_test, "BridgeSender", FakeSender)
    # write evidence to a tmp dir so the test never pollutes the real evidence/ tree
    monkeypatch.setattr(bridge_test, "EVID_DIR", str(tmp_path))
    # --qty 5 must be ignored; qty hard-forced to 1
    rc = bridge_test.main(["--account", "MFFU-50K-1", "--one-mnq", "--ref", "20000",
                           "--mode", "test", "--qty", "5"])
    assert rc == 0
    p = FakeSender.last
    assert p["ticker"]                                  # MNQ contract present
    assert p["quantity"] == 1                           # forced smallest size
    assert p["price"] is not None                       # entry/limit price present
    assert p["stopLoss"]["stopPrice"] is not None       # stop attaches
    assert p["takeProfit"]["limitPrice"] is not None    # target attaches
    assert p["extras"]["signalId"]                      # deterministic dedup id
    assert os.path.exists(os.path.join(str(tmp_path), "stage2-1mnq.json"))


def test_one_mnq_resting_bracket_derived_from_ref():
    # long: rests BELOW market so it won't fill immediately (controlled test)
    rc = None
    import bridge_traderspost as BP
    payload, err = BP.build_entry(
        account="X", strategy="BRIDGE-TEST", setup="stage2-1mnq",
        signal_ts="X-stage2", side="long", qty=1,
        entry=20000 - 30.0, stop=20000 - 30.0 - 20.0, target=20000 - 30.0 + 40.0,
        root="MNQ", order_type="limit")
    assert err is None
    assert payload["price"] == 19970.0
    assert payload["stopLoss"]["stopPrice"] == 19950.0
    assert payload["takeProfit"]["limitPrice"] == 20010.0


def test_one_mnq_refuses_without_url(monkeypatch):
    monkeypatch.delenv("TRADERSPOST_TEST_URL", raising=False)
    monkeypatch.setattr(bridge_test, "BridgeSender", FakeSender)
    rc = bridge_test.main(["--account", "X", "--one-mnq", "--ref", "20000", "--mode", "test"])
    assert rc == 2                                       # fail-closed: no URL, no send
