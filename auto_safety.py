"""ARES AUTO — safety core. Single source of truth for sizing, the daily-loss guard,
the D1c gate, the broker smoke gate, and the live-startup latches.

Everything here FAILS CLOSED. A check that cannot prove safe returns not-safe.
"""
import json
import os
import subprocess
from datetime import datetime, timezone

from store import Store

# ---- worst-day-$ per sizing tier from challenger/ares_sizing.py (4y data, real engine)
EVAL_TIERS = {
    "50K-conservative":  dict(account="50K",  am=3, bm=2, daily_stop=700,  worst_day=1486),
    "50K-balanced":      dict(account="50K",  am=4, bm=2, daily_stop=700,  worst_day=1921),
    "150K-balanced":     dict(account="150K", am=8, bm=4, daily_stop=1600, worst_day=3841),
    "150K-aggressive":   dict(account="150K", am=10, bm=6, daily_stop=1600, worst_day=4892,
                              requires_approval=True),
}
FUNDED_TIERS = {
    "50K":  dict(account="50K",  am=2, bm=1, daily_stop=400, worst_day=960),
    "150K": dict(account="150K", am=4, bm=2, daily_stop=800, worst_day=1921),
}
DD_ALLOWANCE = {"50K": 2000, "150K": 4500}
APPROVAL_DIR = "evidence/approvals"


def tier_spec(mode, tier):
    table = EVAL_TIERS if mode == "eval" else FUNDED_TIERS
    if tier not in table:
        raise ValueError(f"unknown {mode} tier '{tier}'. options: {list(table)}")
    return dict(table[tier], tier=tier, mode=mode)


def validate_size(spec, available_buffer):
    """HARD RULE: worst historical day at this size must not exceed the available
    drawdown buffer. Fails closed (blocks) on any doubt."""
    if available_buffer is None or available_buffer <= 0:
        return False, "available drawdown buffer unknown/zero — BLOCK"
    if spec["worst_day"] >= available_buffer:
        return False, (f"worst day ${spec['worst_day']:,} >= buffer "
                       f"${available_buffer:,.0f} — one bad day could breach. BLOCK")
    if spec.get("requires_approval") and not os.path.exists(
            os.path.join(APPROVAL_DIR, f"approve-{spec['tier']}.flag")):
        return False, f"tier {spec['tier']} requires approval flag — BLOCK"
    return True, "ok"


# ----------------------------- daily loss guard -----------------------------

class DailyGuard:
    """Persistent, date-keyed daily-loss stop. NO restart bypass: state lives in the
    store keyed by (account, ET trading date) and is re-read on every startup."""
    def __init__(self, store=None):
        self.store = store or Store()

    def _key(self, account, et_date):
        return f"daily_guard:{account}:{et_date}"

    def state(self, account, et_date):
        return json.loads(self.store.get_state(self._key(account, et_date)) or
                          '{"pnl":0,"stopped":false,"trades":0}')

    def record(self, account, et_date, pnl, limit):
        s = self.state(account, et_date)
        s["pnl"] += pnl
        s["trades"] += 1
        if s["pnl"] <= -abs(limit):
            s["stopped"] = True
        self.store.set_state(**{self._key(account, et_date): json.dumps(s)})
        return s

    def stop_now(self, account, et_date, reason="manual"):
        s = self.state(account, et_date)
        s["stopped"] = True
        s["stop_reason"] = reason
        self.store.set_state(**{self._key(account, et_date): json.dumps(s)})

    def is_stopped(self, account, et_date):
        return self.state(account, et_date).get("stopped", False)


# ------------------------------- D1c gate -----------------------------------

class D1cGate:
    """Shadow by default; production LOCKED behind explicit, multi-condition approval.
    Never flips to production accidentally — production requires ALL of: approval flag,
    ATHENA-allows flag, and a passing gate-test flag, re-checked every call."""
    def __init__(self, store=None):
        self.store = store or Store()

    def mode(self):
        req = self.store.get_state("d1c_requested_mode") or "SHADOW"
        if req != "PRODUCTION":
            return "SHADOW"
        # production requested -> verify EVERY latch, else fall back to SHADOW
        for f in ("approve-d1c-production.flag", "athena-allows-d1c.flag",
                  "d1c-gate-test-pass.flag"):
            if not os.path.exists(os.path.join(APPROVAL_DIR, f)):
                return "SHADOW"
        return "PRODUCTION"

    def status(self):
        return dict(mode=self.mode(),
                    requested=self.store.get_state("d1c_requested_mode") or "SHADOW")


# --------------------------- broker smoke gate ------------------------------

SMOKE_TESTS = ("auth", "account_resolve", "market_data", "order_permission",
               "demo_bracket", "cancel", "flatten", "reconnect")


def broker_smoke(creds_available=False):
    """Runs (or refuses) the broker smoke battery. Without credentials it cannot run,
    so it reports FAIL -> live stays blocked. Result is written for the latch to read."""
    if not creds_available:
        res = dict(passed=False, ran=False,
                   reason="no Tradovate credentials / API access — cannot run smoke",
                   tests={t: "skipped" for t in SMOKE_TESTS})
    else:
        # placeholder: real smoke runs against demo via spike_day/B1. Not reachable today.
        res = dict(passed=False, ran=False,
                   reason="B1 live runner not built — smoke harness present, not wired",
                   tests={t: "pending-B1" for t in SMOKE_TESTS})
    Store().set_state(broker_smoke_result=json.dumps(res),
                      broker_smoke_ts=datetime.now(timezone.utc).isoformat())
    return res


def smoke_passed(store=None):
    store = store or Store()
    r = json.loads(store.get_state("broker_smoke_result") or '{"passed":false}')
    return bool(r.get("passed"))


# ----------------------------- live latches ---------------------------------

def b1_runner_present():
    """Live order placement requires a real B1 runner. The current bot is SimBot only."""
    return os.path.exists("b1_runner.py")     # does not exist yet -> live blocked


def live_latches(account, store=None, dashboard_green=False):
    """Master live-startup gate. Returns (ok, failures[]). Live is allowed ONLY if
    every latch is satisfied. Any failure => live refused (fail closed)."""
    store = store or Store()
    fails = []
    if not account:
        fails.append("no explicit account (silent default forbidden)")
    if not os.path.exists(os.path.join(APPROVAL_DIR, "live-approved.flag")):
        fails.append("missing live approval flag (evidence/approvals/live-approved.flag)")
    if not smoke_passed(store):
        fails.append("broker API smoke has not passed")
    if not b1_runner_present():
        fails.append("B1 live order runner not built (bot is SimBot only)")
    if not os.path.exists(os.path.join(APPROVAL_DIR, "firm-rules-confirmed.flag")):
        fails.append("firm rules not confirmed in writing")
    if not dashboard_green:
        fails.append("dashboard safety not green")
    return (len(fails) == 0), fails
