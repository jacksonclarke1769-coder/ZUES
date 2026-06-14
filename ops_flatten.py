"""ARES AUTO — emergency flatten CLI. Wraps the tested EmergencyFlatten engine
(flatten.py): cancel all working orders, close all positions, verify flat, journal the
incident, set dashboard lockout, require a manual operator-acknowledged reset.

Paper/sim works today (uses a stub broker). LIVE use is BLOCKED until the broker smoke
gate passes (no creds / no B1) — refuses to run --live otherwise. Fails closed.

  python3 ops_flatten.py --paper [--account ALL]
  python3 ops_flatten.py --live  --account MFFU-150K-1   (blocked until smoke passes)
  python3 ops_flatten.py --status
"""
import argparse
import sys

from store import Store
from journal import Journal
from flatten import EmergencyFlatten
from auto_safety import smoke_passed


class StubBroker:
    """Paper/sim broker — proves the flatten pathway end-to-end without live risk."""
    def __init__(self):
        self._positions = []
        self.calls = []
    def positions(self):
        return list(self._positions)
    def cancel_all(self, acct):
        self.calls.append(("cancel_all", acct))
    def close_position(self, acct):
        self.calls.append(("close", acct))
        self._positions = [p for p in self._positions if p["account_id"] != acct]


def main(argv=None):
    p = argparse.ArgumentParser(description="emergency flatten (fail-closed)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--paper", action="store_true")
    g.add_argument("--live", action="store_true")
    g.add_argument("--status", action="store_true")
    p.add_argument("--account", default="ALL")
    p.add_argument("--reason", default="manual operator flatten")
    a = p.parse_args(argv)

    store = Store(); j = Journal()
    if a.status:
        ef = EmergencyFlatten(j, StubBroker(), store)
        print("lockout:", ef.locked() or "CLEAR")
        return 0
    if a.live:
        if not smoke_passed(store):
            print("REFUSED: live flatten blocked — broker smoke has not passed "
                  "(no API/B1). Use the broker mobile app to flatten manually.")
            return 2
        print("live flatten path requires the B1 broker adapter (not built).")
        return 2
    # paper/sim
    b = StubBroker()
    b._positions = [dict(account_id=a.account if a.account != "ALL" else "PAPER-1", qty=4)]
    ef = EmergencyFlatten(j, b, store)
    r = ef.trigger(a.reason, account_id=a.account)
    print(f"PAPER flatten: flat={r['flat']} accounts={r['accounts']} "
          f"attempts={r['attempts']}")
    print(f"lockout set: {ef.locked()}")
    print("manual reset required: ares_mode/flatten.operator_clear with a written note")
    return 0


if __name__ == "__main__":
    sys.exit(main())
