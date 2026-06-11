"""B0 THOR battery: the 7 mandated journal tests + recon/recovery coverage.
Each test = one historical/feared incident, mechanically detected within one
reconciliation cycle (grace honored where the spec demands flap suppression)."""
import pytest
from journal import Journal
from recon import Reconciler
from recovery import recover


class FakeBroker:
    """Broker-as-truth stub. Tests set its reality."""
    def __init__(self):
        self._positions = []; self._orders = []; self._fills = []; self._accounts = {}
    def positions(self): return list(self._positions)
    def working_orders(self): return list(self._orders)
    def fills_since(self, ts): return list(self._fills)
    def account_state(self, acct): return self._accounts.get(acct)


@pytest.fixture
def j(tmp_path):
    return Journal(str(tmp_path / "journal.db"))


@pytest.fixture
def b():
    return FakeBroker()


def _open_position(j, acct="ACCT1", qty=4, bid=9001):
    cl = j.intent(acct, "A", "A", f"sig-{bid}", "entry",
                  dict(side="Buy", qty=qty, entry=22000.0, stop=21950.0))
    j.append("SEND", acct, cl)
    j.append("ACK", acct, cl, payload=dict(broker_order_id=bid))
    j.append("FILL", acct, cl, payload=dict(qty=qty, side="Buy", broker_order_id=bid))
    return cl


def _confirmed(rec, **kw):
    """run twice -> apply the 2-cycle grace, return confirmed discrepancies."""
    rec.run(**kw)
    return rec.run(**kw)


# ---------------- 1. GHOST ORDER ----------------
def test_1_ghost_order_detected(j, b):
    """Broker has a working order the ledger never intended -> CHECK4 BLACK."""
    b._orders = [dict(account_id="ACCT1", broker_order_id=777, order_type="Limit",
                      action="Buy", qty=4)]
    d = _confirmed(Reconciler(j, b))
    assert any(x["check"] == "CHECK4_UNKNOWN_ORDER" and x["tier"] == "BLACK" for x in d)
    # and the alert is on the ledger (no silent handling)
    n = j.con.execute("SELECT COUNT(*) FROM ledger WHERE event_type='RECON_ALERT'").fetchone()[0]
    assert n >= 1


# ---------------- 2. DUPLICATE ORDER ----------------
def test_2_duplicate_send_impossible(j, b):
    """Same signal slot can never transmit twice — intent dedupe + send gate."""
    cl = j.intent("ACCT1", "A", "A", "sig-x", "entry", dict(side="Buy", qty=4))
    assert j.intent("ACCT1", "A", "A", "sig-x", "entry", {}) is None   # dedupe
    ok, _ = j.can_send(cl)
    assert ok
    j.append("SEND", "ACCT1", cl)
    ok, why = j.can_send(cl)
    assert not ok and "never resend" in why                            # send gate


# ---------------- 3. TIMEOUT AMBIGUITY ----------------
def test_3_timeout_resolved_by_reconciliation_not_resend(j, b):
    """SEND with unknown outcome; broker actually accepted it. Recovery must ACK
    from broker truth — and the send gate must still refuse retransmission."""
    cl = j.intent("ACCT1", "A", "A", "sig-t", "entry", dict(side="Buy", qty=4))
    j.append("SEND", "ACCT1", cl)              # ...timeout: no ACK recorded
    b._orders = [dict(account_id="ACCT1", broker_order_id=801, order_type="Limit",
                      action="Buy", qty=4, cl_ord_id=cl)]
    rep = recover(j, b)
    assert (cl, "ACK_working_at_broker") in rep["resolved"]
    assert j.status(cl) == "working"
    assert not j.can_send(cl)[0]               # still: never resend
    # counter-case: broker never got it -> REJECT, lifecycle reopens cleanly
    cl2 = j.intent("ACCT1", "A", "A", "sig-t2", "entry", dict(side="Buy", qty=4))
    j.append("SEND", "ACCT1", cl2)
    b._orders = []
    rep = recover(j, b)
    assert (cl2, "REJECTED_not_found") in rep["resolved"]
    assert j.status(cl2) == "rejected"


# ---------------- 4. CRASH MID-FILL ----------------
def test_4_crash_mid_fill_recovered_from_broker(j, b):
    """Crash between broker fill and local persist: ledger says sent_unknown,
    broker says filled. Recovery rebuilds the position; CHECK2 then flags the
    missing bracket within one (grace-free) recovery pass."""
    cl = j.intent("ACCT1", "A", "A", "sig-c", "entry", dict(side="Buy", qty=4))
    j.append("SEND", "ACCT1", cl)              # crash here in old architecture
    b._fills = [dict(account_id="ACCT1", broker_order_id=901, qty=4, px=22001.0,
                     ts_utc="2026-06-11T13:40:00Z", cl_ord_id=cl)]
    b._positions = [dict(account_id="ACCT1", qty=4, contract="MNQ")]
    rep = recover(j, b)
    assert (cl, "FILLED_at_broker") in rep["resolved"]
    assert ("ACCT1", cl) in rep["beliefs"]["open_positions"]
    assert any(x["check"] == "CHECK2_NAKED_POSITION" for x in rep["discrepancies"])


# ---------------- 5. BRACKET REJECTION ----------------
def test_5_bracket_rejection_naked_within_one_cycle(j, b):
    """Entry filled, protective stop absent at broker -> CHECK2 BLACK."""
    cl = _open_position(j, qty=4)
    b._positions = [dict(account_id="ACCT1", qty=4, contract="MNQ")]
    b._orders = []                              # bracket leg rejected/never placed
    d = _confirmed(Reconciler(j, b))
    assert any(x["check"] == "CHECK2_NAKED_POSITION" and x["tier"] == "BLACK" for x in d)
    # healthy case: stop present -> no alarm
    b._orders = [dict(account_id="ACCT1", broker_order_id=9002, order_type="Stop",
                      action="Sell", qty=4, cl_ord_id=cl)]
    rec = Reconciler(j, b)
    assert _confirmed(rec) == []


# ---------------- 6. RECONCILIATION MISMATCH ----------------
def test_6_position_mismatch_black(j, b):
    """Ledger believes long 4; broker is flat -> CHECK1 BLACK (after grace)."""
    cl = _open_position(j, qty=4)
    b._positions = []
    b._orders = [dict(account_id="ACCT1", broker_order_id=9002, order_type="Stop",
                      action="Sell", qty=4, cl_ord_id=cl)]
    rec = Reconciler(j, b)
    assert rec.run() == []                      # cycle 1: grace holds fire
    d = rec.run()                               # cycle 2: confirmed
    assert any(x["check"] == "CHECK1_POSITION_MISMATCH" and x["tier"] == "BLACK" for x in d)
    # grace counter resets when reality heals
    b._positions = [dict(account_id="ACCT1", qty=4, contract="MNQ")]
    assert rec.run() == []
    b._positions = []
    assert rec.run() == []                      # needs 2 consecutive again


def test_6b_p3_state_mismatch(j, b):
    """CHECK5: broker balance says cushion < ON threshold but bot thinks P3 off."""
    b._accounts["ACCT1"] = dict(balance=146_200.0)        # floor 145,500 -> cushion 700
    sv = {"ACCT1": dict(balance=146_200.0, floor=145_500.0, p3_braked=False)}
    p3 = {"ACCT1": dict(dd=4_500)}                        # ON at 1,800
    d = _confirmed(Reconciler(j, b), state_view=sv, p3_params=p3)
    assert any(x["check"] == "CHECK5_P3_SHOULD_BE_ON" for x in d)
    # hysteresis band is NOT a mismatch
    sv2 = {"ACCT1": dict(balance=146_200.0, floor=144_200.0, p3_braked=True)}  # cushion 2,000 in [1800,2700)
    rec = Reconciler(j, b)
    assert all(x["check"] != "CHECK5_P3_SHOULD_BE_OFF"
               for x in _confirmed(rec, state_view=sv2, p3_params=p3))


def test_6c_balance_divergence(j, b):
    b._accounts["ACCT1"] = dict(balance=150_000.0)
    sv = {"ACCT1": dict(balance=151_250.0)}
    d = _confirmed(Reconciler(j, b), state_view=sv)
    assert any(x["check"] == "CHECK5_STATE_DIVERGENCE" for x in d)


def test_6d_unknown_fill_black(j, b):
    b._fills = [dict(account_id="ACCT1", broker_order_id=4242, qty=2, px=22000.0,
                     ts_utc="2026-06-11T14:00:00Z")]
    d = _confirmed(Reconciler(j, b))
    assert any(x["check"] == "CHECK3_UNKNOWN_FILL" and x["tier"] == "BLACK" for x in d)


# ---------------- 7. EVIDENCE EXPORT ----------------
def test_7_evidence_export_reconstructs_dispute_chain(j, b):
    """Single call yields the complete signal->exit chain with broker confirmations."""
    cl = _open_position(j, qty=4, bid=9001)
    j.append("BRACKET_SENT", "ACCT1", cl, payload=dict(stop=21950.0, target=22100.0))
    j.append("BRACKET_CONFIRMED", "ACCT1", cl, payload=dict(broker_order_id=9002))
    j.append("EXIT", "ACCT1", cl, payload=dict(px=22100.0, reason="target",
                                               broker_order_id=9002))
    chains = j.export(account_id="ACCT1")
    assert len(chains) == 1
    c = chains[0]
    kinds = [e["event_type"] for e in c["events"]]
    assert kinds[0] == "INTENT" and kinds[-1] == "EXIT" and "FILL" in kinds
    assert c["events"][0]["payload"]["signal_ts"]                       # signal origin
    assert all(e["ts_utc"] for e in c["events"])                        # timestamps
    broker_refs = [e["payload"].get("broker_order_id") for e in c["events"]
                   if e["payload"] and "broker_order_id" in e["payload"]]
    assert 9001 in broker_refs and 9002 in broker_refs                  # broker confirms
