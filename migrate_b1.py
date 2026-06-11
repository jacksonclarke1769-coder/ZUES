"""A0 migration: widen the ledger CHECK constraint to the B1 event vocabulary.
SQLite cannot ALTER a CHECK constraint, so this is a table rebuild:
  1. create ledger_a0 with the new constraint
  2. copy all rows preserving seq
  3. drop old table, rename, recreate append-only triggers + indexes
Idempotent: detects whether the current schema already accepts the new types.
Append-only philosophy: rows are copied byte-identical; nothing is mutated or dropped.
Run: python3 migrate_b1.py [path]
"""
import sqlite3
import sys
from journal import Journal, EVENT_TYPES


def needs_migration(con):
    sql = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='ledger'").fetchone()
    if sql is None:
        return False                      # fresh db — Journal() creates new schema
    return "EMERGENCY_FLATTEN" not in sql[0]


def main(path="data/journal.db"):
    j = Journal(path)                     # ensures db exists (new schema if fresh)
    con = j.con
    if not needs_migration(con):
        n = con.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
        con.close()
        print(f"A0 schema already current at {path} ({n} events) — nothing to do")
        return 0
    types = ",".join(f"'{t}'" for t in EVENT_TYPES)
    cur = con.execute("SELECT COUNT(*), COALESCE(MAX(seq),0) FROM ledger").fetchone()
    n_before, max_seq = cur
    con.executescript(f"""
        BEGIN;
        DROP TRIGGER IF EXISTS ledger_no_update;
        DROP TRIGGER IF EXISTS ledger_no_delete;
        CREATE TABLE ledger_a0(
            seq         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc      TEXT NOT NULL,
            account_id  TEXT NOT NULL,
            strategy    TEXT,
            profile     TEXT,
            event_type  TEXT NOT NULL CHECK(event_type IN ({types})),
            cl_ord_id   TEXT,
            payload_json TEXT
        );
        INSERT INTO ledger_a0(seq, ts_utc, account_id, strategy, profile, event_type,
                              cl_ord_id, payload_json)
            SELECT seq, ts_utc, account_id, strategy, profile, event_type,
                   cl_ord_id, payload_json FROM ledger ORDER BY seq;
        DROP TABLE ledger;
        ALTER TABLE ledger_a0 RENAME TO ledger;
        CREATE TRIGGER ledger_no_update BEFORE UPDATE ON ledger
            BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
        CREATE TRIGGER ledger_no_delete BEFORE DELETE ON ledger
            BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
        CREATE INDEX IF NOT EXISTS ix_ledger_cl ON ledger(cl_ord_id);
        CREATE INDEX IF NOT EXISTS ix_ledger_acct ON ledger(account_id, event_type);
        COMMIT;
    """)
    # restore AUTOINCREMENT watermark so seq never reuses old values
    con.execute("INSERT OR REPLACE INTO sqlite_sequence(name, seq) VALUES('ledger', ?)",
                (max_seq,))
    con.commit()
    n_after = con.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    assert n_after == n_before, f"row count changed {n_before}->{n_after}: ABORT"
    # verify protections + new vocabulary live
    seq = j.append("EMERGENCY_FLATTEN", "MIGRATION", payload=dict(check="a0_ok"))
    for stmt in (f"UPDATE ledger SET account_id='x' WHERE seq={seq}",
                 f"DELETE FROM ledger WHERE seq={seq}"):
        try:
            con.execute(stmt)
            print("FATAL: append-only protection missing post-migration")
            return 1
        except sqlite3.DatabaseError:
            pass
    print(f"A0 migration OK at {path}: {n_after} rows preserved, seq watermark {max_seq},"
          f" vocabulary {len(EVENT_TYPES)} types, append-only verified")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
