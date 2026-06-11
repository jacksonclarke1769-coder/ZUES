"""B0 migration: create data/journal.db (append-only ledger) and verify protections.
Idempotent — safe to run repeatedly. Run: python3 migrate_b0.py"""
import sqlite3
import sys
from journal import Journal


def main(path="data/journal.db"):
    j = Journal(path)
    # verify append-only triggers actually fire
    seq = j.append("STATE_ASSERT", "MIGRATION", payload=dict(check="schema_ok"))
    for stmt in (f"UPDATE ledger SET account_id='x' WHERE seq={seq}",
                 f"DELETE FROM ledger WHERE seq={seq}"):
        try:
            j.con.execute(stmt)
            print(f"FATAL: append-only protection missing for: {stmt}")
            return 1
        except sqlite3.DatabaseError as e:
            assert "append-only" in str(e), e
    mode = j.con.execute("PRAGMA synchronous").fetchone()[0]
    assert mode == 2, f"synchronous must be FULL(2), got {mode}"
    n = j.con.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    print(f"journal.db OK at {path} · append-only verified · synchronous=FULL · {n} events")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
