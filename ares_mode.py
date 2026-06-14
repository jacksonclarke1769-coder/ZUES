"""ARES mode switch — hard distinction between ARES EVAL MODE and ZEUS FUNDED MODE.

ARES (controlled-aggression eval sizing) may exist ONLY during evaluation. The moment
an account is funded, ARES is forbidden on it. This module enforces that:
  - arm() refuses to arm a funded account
  - the ZEUS dashboard raises a RED alert if ARES is ever active on a funded account
  - every arm/disarm is journaled (audit trail)

There is NO live automation here (manual/supervised trading). This is a discipline,
display, and logging tool — the operator-facing mode flag and its safety rail.

CLI:
  python3 ares_mode.py arm <ACCOUNT> <SIZE>   e.g. arm MFFU-150K-1 A8/B4
  python3 ares_mode.py disarm <ACCOUNT>
  python3 ares_mode.py status
"""
import json
import sys
from datetime import datetime, timezone

from store import Store
from journal import Journal

KEY = "ares_mode"          # store key -> {account: {size, started, target}}
APPROVED = {"50K": ["A3/B2", "A4/B2"], "150K": ["A6/B3", "A8/B4", "A10/B6"]}


def _now():
    return datetime.now(timezone.utc).isoformat()


def get(store):
    return json.loads(store.get_state(KEY) or "{}")


def account_phase(store, account):
    """Look up the account's phase from the dashboard account state, if registered."""
    for a in json.loads(store.get_state("zeus_accounts") or "[]"):
        if a.get("name") == account:
            return a.get("phase")
    return None


def arm(account, size, store=None, journal=None):
    store = store or Store()
    journal = journal or Journal()
    phase = account_phase(store, account)
    if phase == "FUNDED":
        raise RuntimeError(f"REFUSED: {account} is FUNDED — ARES sizing is forbidden on a "
                           "funded account. Trade ZEUS funded mode (A4/B2 + P3).")
    m = get(store)
    m[account] = dict(size=size, started=_now(),
                      mode="ARES", note="controlled-aggression eval attack")
    store.set_state(**{KEY: json.dumps(m)})
    journal.append("STATE_ASSERT", account, payload=dict(
        action="ares_arm", account=account, size=size, ts=_now()))
    return m[account]


def disarm(account, store=None, journal=None):
    store = store or Store()
    journal = journal or Journal()
    m = get(store)
    prev = m.pop(account, None)
    store.set_state(**{KEY: json.dumps(m)})
    journal.append("STATE_ASSERT", account, payload=dict(
        action="ares_disarm", account=account, prior=prev, ts=_now(),
        note="ARES ended -> ZEUS funded mode (reduce size, activate P3)"))
    return prev


def violations(store):
    """Accounts where ARES is active AND the account is funded — must be empty."""
    m = get(store)
    out = []
    for acct in m:
        if account_phase(store, acct) == "FUNDED":
            out.append(acct)
    return out


if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]
    s = Store()
    if a[0] == "arm":
        print("ARMED:", arm(a[1], a[2], s))
    elif a[0] == "disarm":
        print("DISARMED:", disarm(a[1], s))
    else:
        m = get(s)
        print("ARES mode:", json.dumps(m, indent=2) if m else "OFF (all accounts ZEUS mode)")
        v = violations(s)
        if v:
            print("!! VIOLATION — ARES active on FUNDED account(s):", v)
