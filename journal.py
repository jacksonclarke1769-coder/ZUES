"""B0 — Intent Ledger (journal-lite, per ODIN II verdict).

THE BOT MUST NEVER TRUST ITS OWN MEMORY. BROKER IS ALWAYS TRUTH.

Append-only sqlite ledger. Every order lifecycle begins with an INTENT that is
durably committed (synchronous=FULL) BEFORE any transmission. cl_ord_id is
DETERMINISTIC over (account, strategy, signal_ts, role) so a restarted or duplicate
instance computes the SAME id and is refused by the ledger — duplicate sends are
structurally impossible, not merely unlikely.

No UPDATE. No DELETE. Enforced by sqlite triggers. Lives in its own file
(data/journal.db) so Store.reset() and bot reinstalls can never touch it.
"""
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone

EVENT_TYPES = (
    "INTENT", "SEND", "ACK", "REJECT", "PARTIAL_FILL", "FILL",
    "BRACKET_SENT", "BRACKET_CONFIRMED", "EXIT", "CANCEL",
    "STATE_ASSERT", "RECON_ALERT",
    # A0 extension (B1 Review Board + V-day amendments)
    "CANCEL_SENT", "CANCEL_CONFIRMED", "MODIFY_SENT", "MODIFY_CONFIRMED",
    "EMERGENCY_FLATTEN",
)
MAX_SENDS = 3   # hard ceiling on transmission attempts per lifecycle (rate-limit retries)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def make_cl_ord_id(account_id, strategy, signal_ts, role):
    """Deterministic client order id. Same signal slot -> same id, always."""
    raw = f"{account_id}|{strategy}|{signal_ts}|{role}"
    return "NQB-" + hashlib.sha1(raw.encode()).hexdigest()[:20]


class Journal:
    def __init__(self, path="data/journal.db"):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        self.path = path
        self.con = sqlite3.connect(path)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA synchronous=FULL")   # commit == fsync'd
        self._schema()

    def _schema(self):
        c = self.con
        types = ",".join(f"'{t}'" for t in EVENT_TYPES)
        c.execute(f"""CREATE TABLE IF NOT EXISTS ledger(
            seq         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_utc      TEXT NOT NULL,
            account_id  TEXT NOT NULL,
            strategy    TEXT,
            profile     TEXT,
            event_type  TEXT NOT NULL CHECK(event_type IN ({types})),
            cl_ord_id   TEXT,
            payload_json TEXT
        )""")
        c.execute("""CREATE TRIGGER IF NOT EXISTS ledger_no_update
            BEFORE UPDATE ON ledger
            BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END""")
        c.execute("""CREATE TRIGGER IF NOT EXISTS ledger_no_delete
            BEFORE DELETE ON ledger
            BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END""")
        c.execute("CREATE INDEX IF NOT EXISTS ix_ledger_cl ON ledger(cl_ord_id)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_ledger_acct ON ledger(account_id, event_type)")
        c.commit()

    # ---------------- append paths ----------------

    def append(self, event_type, account_id, cl_ord_id=None, strategy=None,
               profile=None, payload=None, ts=None):
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event_type {event_type}")
        cur = self.con.execute(
            "INSERT INTO ledger(ts_utc, account_id, strategy, profile, event_type, cl_ord_id, payload_json)"
            " VALUES (?,?,?,?,?,?,?)",
            (ts or utcnow(), account_id, strategy, profile, event_type,
             cl_ord_id, json.dumps(payload) if payload is not None else None))
        self.con.commit()           # synchronous=FULL -> durable before return
        return cur.lastrowid

    def intent(self, account_id, strategy, profile, signal_ts, role, payload):
        """Begin an order lifecycle. Returns cl_ord_id, or None if this exact
        intent already exists (duplicate signal slot -> REFUSED)."""
        cl = make_cl_ord_id(account_id, strategy, signal_ts, role)
        if self.has_event(cl, "INTENT"):
            return None
        self.append("INTENT", account_id, cl, strategy, profile,
                    dict(payload or {}, signal_ts=str(signal_ts), role=role))
        return cl

    def can_send(self, cl_ord_id):
        """Idempotency gate: an order may be transmitted exactly once — with ONE
        narrowly-defined exception (V-day finding V5b): a REJECT whose payload carries
        not_handled=True (Tradovate 429/p-ticket: 'the request was not handled') is a
        DEFINITIVE non-execution, so one further attempt is allowed, capped at
        MAX_SENDS total. Ambiguity (SEND without outcome) still NEVER permits resend."""
        evs = self.events(cl_ord_id)
        if not any(e["event_type"] == "INTENT" for e in evs):
            return False, "no INTENT on ledger"
        st = self.status(cl_ord_id)
        if st in ("closed", "cancelled", "rejected"):
            return False, "lifecycle already terminal"
        n_sends = sum(1 for e in evs if e["event_type"] == "SEND")
        if n_sends == 0:
            return True, "ok"
        if n_sends >= MAX_SENDS:
            return False, f"send ceiling reached ({MAX_SENDS})"
        if st == "pending_send":   # only reachable again via REJECT(not_handled=True)
            return True, "ok (retry after definitive not-handled rejection)"
        return False, "SEND already recorded — resolve via reconciliation, never resend"

    # ---------------- queries ----------------

    def events(self, cl_ord_id):
        cur = self.con.execute(
            "SELECT seq, ts_utc, account_id, strategy, profile, event_type, cl_ord_id, payload_json"
            " FROM ledger WHERE cl_ord_id=? ORDER BY seq", (cl_ord_id,))
        return [self._row(r) for r in cur.fetchall()]

    def has_event(self, cl_ord_id, event_type):
        cur = self.con.execute(
            "SELECT 1 FROM ledger WHERE cl_ord_id=? AND event_type=? LIMIT 1",
            (cl_ord_id, event_type))
        return cur.fetchone() is not None

    def status(self, cl_ord_id):
        """Order-fold status derivation (A0): events are applied IN ORDER, so a
        REJECT(not_handled) followed by a fresh SEND/ACK progresses correctly.
        Marker events (BRACKET_*, MODIFY_*, CANCEL_SENT, STATE_ASSERT, RECON_ALERT,
        EMERGENCY_FLATTEN) do not change lifecycle status."""
        st = "unknown"
        for e in self.events(cl_ord_id):
            t, p = e["event_type"], (e["payload"] or {})
            if t == "INTENT":
                st = "pending_send"
            elif t == "SEND":
                st = "sent_unknown"
            elif t == "ACK":
                st = "working"
            elif t == "PARTIAL_FILL":
                st = "partial"
            elif t == "FILL":
                st = "open"
            elif t == "REJECT":
                st = "pending_send" if p.get("not_handled") else "rejected"
            elif t in ("CANCEL", "CANCEL_CONFIRMED"):
                if not p.get("failed"):        # failed-cancel: fill won the race
                    st = "cancelled"
            elif t == "EXIT":
                st = "closed"
        return st

    def open_orders(self, account_id=None):
        """cl_ord_ids whose lifecycle is not terminal, grouped by status."""
        q = "SELECT DISTINCT cl_ord_id FROM ledger WHERE cl_ord_id IS NOT NULL"
        args = ()
        if account_id:
            q += " AND account_id=?"; args = (account_id,)
        out = {}
        for (cl,) in self.con.execute(q, args).fetchall():
            st = self.status(cl)
            if st not in ("closed", "cancelled", "rejected"):
                out.setdefault(st, []).append(cl)
        return out

    def open_positions(self, account_id=None):
        """{(account_id, cl_ord_id): {qty, side, strategy}} for FILLed, un-EXITed orders."""
        out = {}
        for st, cls in self.open_orders(account_id).items():
            if st not in ("open", "partial"):
                continue
            for cl in cls:
                evs = self.events(cl)
                fills = [e for e in evs if e["event_type"] in ("FILL", "PARTIAL_FILL")]
                qty = sum((e["payload"] or {}).get("qty", 0) for e in fills)
                head = evs[0]
                side = (head["payload"] or {}).get("side")
                out[(head["account_id"], cl)] = dict(
                    qty=qty, side=side, strategy=head["strategy"])
        return out

    def broker_map(self):
        """{broker_order_id: cl_ord_id} learned from ACK/FILL payloads."""
        cur = self.con.execute(
            "SELECT cl_ord_id, payload_json FROM ledger"
            " WHERE event_type IN ('ACK','FILL','PARTIAL_FILL','BRACKET_CONFIRMED',"
            "'MODIFY_CONFIRMED','CANCEL_CONFIRMED')"
            " AND cl_ord_id IS NOT NULL")
        m = {}
        for cl, pj in cur.fetchall():
            p = json.loads(pj) if pj else {}
            b = p.get("broker_order_id")
            if b is not None:
                m[str(b)] = cl
        return m

    def unresolved_sends(self):
        """SENDs with no ACK/REJECT/FILL/CANCEL — outcome unknown. NEVER resend these."""
        out = []
        for st, cls in self.open_orders().items():
            if st == "sent_unknown":
                out.extend(cls)
        return out

    # ---------------- evidence locker ----------------

    def export_chain(self, cl_ord_id):
        """Full lifecycle for one order: signal->intent->send->ack->fill->bracket->exit."""
        evs = self.events(cl_ord_id)
        return dict(cl_ord_id=cl_ord_id, status=self.status(cl_ord_id),
                    n_events=len(evs), events=evs)

    def export(self, account_id=None, date=None, cl_ord_id=None):
        if cl_ord_id:
            return [self.export_chain(cl_ord_id)]
        q = "SELECT DISTINCT cl_ord_id FROM ledger WHERE cl_ord_id IS NOT NULL"
        args = []
        if account_id:
            q += " AND account_id=?"; args.append(account_id)
        if date:
            q += " AND substr(ts_utc,1,10)=?"; args.append(date)
        cls = [r[0] for r in self.con.execute(q, args).fetchall()]
        return [self.export_chain(cl) for cl in cls]

    def _row(self, r):
        return dict(seq=r[0], ts_utc=r[1], account_id=r[2], strategy=r[3],
                    profile=r[4], event_type=r[5], cl_ord_id=r[6],
                    payload=json.loads(r[7]) if r[7] else None)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="B0 evidence locker export")
    ap.add_argument("--db", default="data/journal.db")
    ap.add_argument("--clordid")
    ap.add_argument("--account")
    ap.add_argument("--date", help="YYYY-MM-DD")
    a = ap.parse_args()
    j = Journal(a.db)
    print(json.dumps(j.export(account_id=a.account, date=a.date, cl_ord_id=a.clordid),
                     indent=2, default=str))
