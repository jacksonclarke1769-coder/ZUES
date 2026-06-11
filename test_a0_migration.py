"""A0 battery: vocabulary extension, order-fold status, rate-limit retry rule,
table-rebuild migration (idempotent, row-preserving, protection-preserving)."""
import sqlite3
import pytest
from journal import Journal, EVENT_TYPES, MAX_SENDS
import migrate_b1


@pytest.fixture
def j(tmp_path):
    return Journal(str(tmp_path / "j.db"))


def test_new_vocabulary_accepted(j):
    for t in ("CANCEL_SENT", "CANCEL_CONFIRMED", "MODIFY_SENT",
              "MODIFY_CONFIRMED", "EMERGENCY_FLATTEN"):
        assert j.append(t, "A1", payload=dict(x=1))


def test_status_fold_cancel_confirmed(j):
    cl = j.intent("A1", "A", "A", "t1", "entry", dict(side="Buy", qty=4))
    j.append("SEND", "A1", cl); j.append("ACK", "A1", cl, payload=dict(broker_order_id=1))
    j.append("CANCEL_SENT", "A1", cl)
    assert j.status(cl) == "working"            # cancel-request alone changes nothing
    j.append("CANCEL_CONFIRMED", "A1", cl)
    assert j.status(cl) == "cancelled"


def test_status_fold_failed_cancel_fill_wins(j):
    cl = j.intent("A1", "A", "A", "t2", "entry", dict(side="Buy", qty=4))
    j.append("SEND", "A1", cl); j.append("ACK", "A1", cl)
    j.append("CANCEL_SENT", "A1", cl)
    j.append("FILL", "A1", cl, payload=dict(qty=4, side="Buy"))
    j.append("CANCEL_CONFIRMED", "A1", cl, payload=dict(failed=True))   # race: fill won
    assert j.status(cl) == "open"


def test_modify_markers_do_not_change_status(j):
    cl = j.intent("A1", "A", "A", "t3", "entry", dict(side="Buy", qty=4))
    j.append("SEND", "A1", cl); j.append("ACK", "A1", cl)
    j.append("PARTIAL_FILL", "A1", cl, payload=dict(qty=2, side="Buy"))
    j.append("MODIFY_SENT", "A1", cl); j.append("MODIFY_CONFIRMED", "A1", cl)
    assert j.status(cl) == "partial"


def test_rate_limit_retry_allowed_once(j):
    cl = j.intent("A1", "A", "A", "t4", "entry", dict(side="Buy", qty=4))
    j.append("SEND", "A1", cl)
    assert not j.can_send(cl)[0]                              # ambiguous: refuse
    j.append("REJECT", "A1", cl, payload=dict(not_handled=True, p_time=5))
    ok, why = j.can_send(cl)
    assert ok and "retry" in why                              # definitive not-handled
    j.append("SEND", "A1", cl)
    assert not j.can_send(cl)[0]                              # ambiguous again: refuse
    j.append("ACK", "A1", cl, payload=dict(broker_order_id=9))
    assert j.status(cl) == "working"


def test_send_ceiling(j):
    cl = j.intent("A1", "A", "A", "t5", "entry", dict(side="Buy", qty=4))
    for _ in range(MAX_SENDS):
        assert j.can_send(cl)[0]
        j.append("SEND", "A1", cl)
        j.append("REJECT", "A1", cl, payload=dict(not_handled=True))
    ok, why = j.can_send(cl)
    assert not ok and "ceiling" in why


def test_definitive_reject_stays_terminal(j):
    cl = j.intent("A1", "A", "A", "t6", "entry", dict(side="Buy", qty=4))
    j.append("SEND", "A1", cl)
    j.append("REJECT", "A1", cl, payload=dict(reason="margin"))
    assert j.status(cl) == "rejected"
    assert not j.can_send(cl)[0]


def test_migration_rebuilds_old_schema(tmp_path):
    path = str(tmp_path / "old.db")
    # build a pre-A0 db by hand (old 12-type CHECK)
    con = sqlite3.connect(path)
    old_types = ",".join(f"'{t}'" for t in EVENT_TYPES[:12])
    con.executescript(f"""
        CREATE TABLE ledger(
            seq INTEGER PRIMARY KEY AUTOINCREMENT, ts_utc TEXT NOT NULL,
            account_id TEXT NOT NULL, strategy TEXT, profile TEXT,
            event_type TEXT NOT NULL CHECK(event_type IN ({old_types})),
            cl_ord_id TEXT, payload_json TEXT);
        CREATE TRIGGER ledger_no_update BEFORE UPDATE ON ledger
            BEGIN SELECT RAISE(ABORT,'ledger is append-only'); END;
        CREATE TRIGGER ledger_no_delete BEFORE DELETE ON ledger
            BEGIN SELECT RAISE(ABORT,'ledger is append-only'); END;
        INSERT INTO ledger(ts_utc, account_id, event_type, cl_ord_id, payload_json)
            VALUES ('2026-06-11T00:00:00Z','A1','INTENT','NQB-x','{{"qty":4}}'),
                   ('2026-06-11T00:00:01Z','A1','SEND','NQB-x',NULL),
                   ('2026-06-11T00:00:02Z','A1','ACK','NQB-x','{{"broker_order_id":7}}');
    """)
    con.commit()
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("INSERT INTO ledger(ts_utc,account_id,event_type) "
                    "VALUES('t','A1','EMERGENCY_FLATTEN')")
    con.close()
    assert migrate_b1.main(path) == 0
    j = Journal(path)
    evs = j.events("NQB-x")
    assert [e["event_type"] for e in evs] == ["INTENT", "SEND", "ACK"]   # rows preserved
    assert evs[0]["seq"] == 1                                            # seq preserved
    assert j.status("NQB-x") == "working"
    j.append("EMERGENCY_FLATTEN", "A1")                                  # new vocab live
    with pytest.raises(sqlite3.DatabaseError):                           # protections live
        j.con.execute("DELETE FROM ledger WHERE seq=1")
    # idempotent second run
    assert migrate_b1.main(path) == 0


def test_migration_seq_watermark_no_reuse(tmp_path):
    path = str(tmp_path / "w.db")
    j = Journal(path)
    s1 = j.append("INTENT", "A1", "NQB-w", payload=dict(qty=1))
    assert migrate_b1.main(path) == 0          # current schema: no-op
    j2 = Journal(path)
    s2 = j2.append("STATE_ASSERT", "A1")
    assert s2 > s1
