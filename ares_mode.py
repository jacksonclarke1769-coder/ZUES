"""ARES AUTO — account mode controller. Hard distinction between:
  ARES EVAL MODE  (controlled-aggression eval sizing — eval accounts only)
  ZEUS FUNDED MODE (lower size + P3 survival — funded accounts)
  PAUSED          (no mode set)

ARES sizing may exist ONLY during evaluation. The moment an account is funded, ARES
is forbidden on it: arm-eval refuses a funded account, switch-funded clears ARES, and
the dashboard raises RED if ARES is ever active on a funded account. Every switch is
journaled. No live automation here — discipline, display, logging, and the safety rail.

CLI:
  python3 ares_mode.py arm-eval <ACCOUNT> <TIER>     e.g. arm-eval MFFU-50K-1 50K-conservative
  python3 ares_mode.py switch-funded <ACCOUNT>       (call the instant the eval passes)
  python3 ares_mode.py disarm <ACCOUNT>
  python3 ares_mode.py status
"""
import json
import sys
from datetime import datetime, timezone

from store import Store
from journal import Journal
from auto_safety import EVAL_TIERS, tier_spec

ARES_KEY = "ares_mode"        # {account: {tier, am, bm, started}}
FUNDED_KEY = "zeus_funded"    # {account: {tier, am, bm, started}}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _get(store, key):
    return json.loads(store.get_state(key) or "{}")


def account_phase(store, account):
    for a in json.loads(store.get_state("zeus_accounts") or "[]"):
        if a.get("name") == account:
            return a.get("phase")
    return None


def arm_eval(account, tier, store=None, journal=None):
    store = store or Store(); journal = journal or Journal()
    if account_phase(store, account) == "FUNDED":
        raise RuntimeError(f"REFUSED: {account} is FUNDED — ARES sizing forbidden. Use "
                           "switch-funded; trade ZEUS funded mode (A4/B2 + P3).")
    if tier not in EVAL_TIERS:
        raise ValueError(f"unknown eval tier '{tier}'. options: {list(EVAL_TIERS)}")
    spec = tier_spec("eval", tier)
    m = _get(store, ARES_KEY)
    m[account] = dict(tier=tier, size=f"A{spec['am']}/B{spec['bm']}",
                      am=spec["am"], bm=spec["bm"], daily_stop=spec["daily_stop"],
                      started=_now(), mode="ARES")
    store.set_state(**{ARES_KEY: json.dumps(m)})
    journal.append("STATE_ASSERT", account, payload=dict(
        action="ares_arm_eval", account=account, tier=tier, ts=_now()))
    return m[account]


def switch_funded(account, store=None, journal=None):
    """End ARES, enter ZEUS funded survival mode (lower size + P3)."""
    store = store or Store(); journal = journal or Journal()
    a = _get(store, ARES_KEY)
    prev = a.pop(account, None)
    store.set_state(**{ARES_KEY: json.dumps(a)})
    size_tier = "150K" if "150" in (account or "") else "50K"
    f = _get(store, FUNDED_KEY)
    spec = tier_spec("funded", size_tier)
    f[account] = dict(tier=size_tier, size=f"A{spec['am']}/B{spec['bm']}",
                      am=spec["am"], bm=spec["bm"], daily_stop=spec["daily_stop"],
                      p3=True, started=_now(), mode="ZEUS_FUNDED")
    store.set_state(**{FUNDED_KEY: json.dumps(f)})
    journal.append("STATE_ASSERT", account, payload=dict(
        action="ares_to_zeus_funded", account=account, prior=prev, ts=_now(),
        note="ARES ended -> ZEUS funded (reduce size, P3 active)"))
    return f[account]


def disarm(account, store=None, journal=None):
    store = store or Store(); journal = journal or Journal()
    a = _get(store, ARES_KEY); prev = a.pop(account, None)
    store.set_state(**{ARES_KEY: json.dumps(a)})
    journal.append("STATE_ASSERT", account, payload=dict(
        action="ares_disarm", account=account, prior=prev, ts=_now()))
    return prev


def current_mode(store, account):
    if account in _get(store, ARES_KEY):
        return "ARES"
    if account in _get(store, FUNDED_KEY):
        return "ZEUS_FUNDED"
    return "PAUSED"


def violations(store):
    return [a for a in _get(store, ARES_KEY) if account_phase(store, a) == "FUNDED"]


if __name__ == "__main__":
    a = sys.argv[1:] or ["status"]
    s = Store()
    if a[0] == "arm-eval":
        print("ARMED (ARES eval):", arm_eval(a[1], a[2], s))
    elif a[0] == "switch-funded":
        print("SWITCHED -> ZEUS funded:", switch_funded(a[1], s))
    elif a[0] == "disarm":
        print("DISARMED:", disarm(a[1], s))
    else:
        print("ARES:", json.dumps(_get(s, ARES_KEY), indent=2) or "OFF")
        print("ZEUS FUNDED:", json.dumps(_get(s, FUNDED_KEY), indent=2) or "none")
        v = violations(s)
        if v:
            print("!! VIOLATION — ARES on FUNDED account(s):", v)
