"""B0 unit tests: ledger integrity, idempotency, lifecycle derivation, evidence export.
pytest-collectable (FENRIR B6 standard)."""
import sqlite3
import pytest
from journal import Journal, make_cl_ord_id, EVENT_TYPES


@pytest.fixture
def j(tmp_path):
    return Journal(str(tmp_path / "journal.db"))


def _full_chain(j, acct="ACCT1", sig="2026-06-11T09:35:00", role="entry"):
    cl = j.intent(acct, "A", "A", sig, role, dict(side="Buy", qty=4, entry=22000.0,
                                                  stop=21950.0, target=22100.0))
    j.append("SEND", acct, cl, payload=dict(body="entry+oso"))
    j.append("ACK", acct, cl, payload=dict(broker_order_id=9001))
    j.append("FILL", acct, cl, payload=dict(qty=4, px=22000.25, side="Buy",
                                            broker_order_id=9001))
    j.append("BRACKET_SENT", acct, cl, payload=dict(stop=21950.0, target=22100.0))
    j.append("BRACKET_CONFIRMED", acct, cl, payload=dict(broker_order_id=9002))
    return cl


def test_append_only_update_blocked(j):
    seq = j.append("STATE_ASSERT", "A1", payload=dict(x=1))
    with pytest.raises(sqlite3.DatabaseError):
        j.con.execute(f"UPDATE ledger SET account_id='hax' WHERE seq={seq}")


def test_append_only_delete_blocked(j):
    seq = j.append("STATE_ASSERT", "A1")
    with pytest.raises(sqlite3.DatabaseError):
        j.con.execute(f"DELETE FROM ledger WHERE seq={seq}")


def test_unknown_event_type_rejected(j):
    with pytest.raises(ValueError):
        j.append("HACK", "A1")


def test_synchronous_full(j):
    assert j.con.execute("PRAGMA synchronous").fetchone()[0] == 2


def test_intent_is_durable_and_first(j):
    cl = j.intent("A1", "A", "A", "t1", "entry", dict(side="Buy", qty=4))
    evs = j.events(cl)
    assert evs[0]["event_type"] == "INTENT" and len(evs) == 1
    assert j.status(cl) == "pending_send"


def test_duplicate_intent_refused(j):
    a = j.intent("A1", "A", "A", "t1", "entry", {})
    b = j.intent("A1", "A", "A", "t1", "entry", {})
    assert a is not None and b is None


def test_cl_ord_id_deterministic_across_instances(tmp_path):
    assert make_cl_ord_id("A1", "A", "t1", "entry") == make_cl_ord_id("A1", "A", "t1", "entry")
    j1 = Journal(str(tmp_path / "j.db"))
    cl = j1.intent("A1", "A", "A", "t1", "entry", {})
    j2 = Journal(str(tmp_path / "j.db"))    # "second instance", same db
    assert j2.intent("A1", "A", "A", "t1", "entry", {}) is None
    ok, why = j2.can_send(cl)
    assert ok                                # INTENT exists, no SEND yet -> one send allowed
    j2.append("SEND", "A1", cl)
    ok, why = j1.can_send(cl)                # instance 1 now refused too
    assert not ok and "never resend" in why


def test_can_send_requires_intent(j):
    ok, why = j.can_send("NQB-doesnotexist")
    assert not ok and "no INTENT" in why


def test_lifecycle_status_progression(j):
    cl = j.intent("A1", "A", "A", "t1", "entry", dict(side="Buy", qty=4))
    j.append("SEND", "A1", cl)
    assert j.status(cl) == "sent_unknown"
    j.append("ACK", "A1", cl, payload=dict(broker_order_id=1))
    assert j.status(cl) == "working"
    j.append("PARTIAL_FILL", "A1", cl, payload=dict(qty=2, side="Buy"))
    assert j.status(cl) == "partial"
    j.append("FILL", "A1", cl, payload=dict(qty=2, side="Buy"))
    assert j.status(cl) == "open"
    j.append("EXIT", "A1", cl, payload=dict(px=22050.0))
    assert j.status(cl) == "closed"


def test_open_positions_and_broker_map(j):
    cl = _full_chain(j)
    pos = j.open_positions()
    assert pos[("ACCT1", cl)]["qty"] == 4 and pos[("ACCT1", cl)]["side"] == "Buy"
    assert j.broker_map()["9001"] == cl
    j.append("EXIT", "ACCT1", cl, payload=dict(px=22100.0))
    assert j.open_positions() == {}


def test_unresolved_sends(j):
    cl = j.intent("A1", "A", "A", "t9", "entry", dict(side="Buy", qty=4))
    j.append("SEND", "A1", cl)
    assert j.unresolved_sends() == [cl]
    j.append("ACK", "A1", cl, payload=dict(broker_order_id=5))
    assert j.unresolved_sends() == []


def test_evidence_export_full_chain(j):
    cl = _full_chain(j)
    j.append("EXIT", "ACCT1", cl, payload=dict(px=22100.0, reason="target"))
    out = j.export(cl_ord_id=cl)
    assert len(out) == 1
    chain = out[0]
    kinds = [e["event_type"] for e in chain["events"]]
    assert kinds == ["INTENT", "SEND", "ACK", "FILL", "BRACKET_SENT",
                     "BRACKET_CONFIRMED", "EXIT"]
    assert chain["status"] == "closed"
    assert chain["events"][0]["payload"]["signal_ts"]          # signal embedded in INTENT
    assert chain["events"][3]["payload"]["broker_order_id"] == 9001  # verbatim broker ref


def test_export_by_account_and_date(j):
    cl = _full_chain(j)
    date = j.events(cl)[0]["ts_utc"][:10]
    assert len(j.export(account_id="ACCT1", date=date)) == 1
    assert j.export(account_id="NOPE") == []
