"""W4 — Emergency Flatten Engine. The universal kill switch.

EVERY BLACK condition terminates here, through ONE path:
    BLACK -> cancel all working -> close all positions -> verify flat
          -> journal EMERGENCY_FLATTEN trail -> LOCKOUT -> human acknowledgement.

BrokerActions interface (B1 implements per platform; tests use fakes):
    cancel_all(account_id)        -> None | raises
    close_position(account_id)    -> None | raises   (market-flatten net position)
    positions()                   -> [{account_id, qty, ...}]  (broker truth)

Lockout is persisted in Store (survives restarts). While locked, callers of
`locked()` must refuse all new INTENTs. Only `operator_clear()` with a written
note releases it — and that act itself is journaled.
"""
from journal import utcnow

LOCK_KEY = "emergency_lockout"


class EmergencyFlatten:
    def __init__(self, journal, broker, store, verify_attempts=3, verify_wait=2.0,
                 sleep=None):
        self.j = journal
        self.b = broker
        self.store = store
        self.attempts = verify_attempts
        self.wait = verify_wait
        self._sleep = sleep or (lambda s: None)   # injectable for tests; B1 wires time.sleep

    # ---------------- the single path ----------------

    def trigger(self, reason, account_id="ALL", source="recon", detail=None):
        """Returns dict(flat=bool, accounts=[...], attempts=n). Always ends LOCKED."""
        self.j.append("EMERGENCY_FLATTEN", account_id, payload=dict(
            stage="triggered", reason=reason, source=source, detail=detail))
        targets = self._targets(account_id)
        errors = []
        for acct in targets:
            for op, fn in (("cancel_all", self.b.cancel_all),
                           ("close_position", self.b.close_position)):
                try:
                    fn(acct)
                except Exception as e:           # noqa: BLE001 — record and continue
                    errors.append((acct, op, repr(e)))
        flat, attempts = self._verify_flat(targets)
        self.j.append("EMERGENCY_FLATTEN", account_id, payload=dict(
            stage="verified" if flat else "VERIFY_FAILED", flat=flat,
            attempts=attempts, errors=errors))
        self._lock(reason, account_id, flat)
        return dict(flat=flat, accounts=targets, attempts=attempts, errors=errors)

    def _targets(self, account_id):
        if account_id != "ALL":
            return [account_id]
        accts = {p["account_id"] for p in self.b.positions()}
        accts |= {a for (a, _cl) in self.j.open_positions().keys()}
        return sorted(accts) or ["ALL"]

    def _verify_flat(self, targets):
        for i in range(1, self.attempts + 1):
            try:
                open_pos = [p for p in self.b.positions()
                            if p["account_id"] in targets and p["qty"] != 0]
            except Exception:                     # broker unreachable: cannot verify
                open_pos = None
            if open_pos == []:
                return True, i
            if open_pos:                          # still open: re-issue closes
                for p in open_pos:
                    try:
                        self.b.close_position(p["account_id"])
                    except Exception:
                        pass
            self._sleep(self.wait)
        return False, self.attempts

    # ---------------- lockout ----------------

    def _lock(self, reason, account_id, flat):
        self.store.set_state(**{LOCK_KEY: f"{utcnow()}|{account_id}|{reason}|flat={flat}"})
        self.j.append("EMERGENCY_FLATTEN", account_id, payload=dict(
            stage="lockout", reason=reason))

    def locked(self):
        v = self.store.get_state(LOCK_KEY)
        return v if v else None

    def operator_clear(self, operator_note):
        """Human acknowledgement. Refuses empty notes. Journals the clearance."""
        if not operator_note or len(operator_note.strip()) < 10:
            raise ValueError("operator note required (>=10 chars): what happened, why safe")
        prev = self.locked()
        if prev is None:
            return False
        self.j.append("STATE_ASSERT", "ALL", payload=dict(
            action="lockout_cleared", prior=prev, note=operator_note.strip()))
        self.store.set_state(**{LOCK_KEY: ""})
        return True
