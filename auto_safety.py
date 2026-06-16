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
    """Four modes: OFF · SHADOW · ACTIVE_EVAL_FILTER · PRODUCTION_FUNDED. Fail closed.

      eval accounts:   OFF / SHADOW / ACTIVE_EVAL_FILTER allowed.
      funded accounts: OFF / SHADOW by default; PRODUCTION_FUNDED only with ALL
                       promotion flags (approval + ATHENA-allows + gate-test); a requested
                       ACTIVE_EVAL_FILTER on a funded account degrades to SHADOW.
    Any unauthorised/illegal request degrades to SHADOW — never escalates."""
    MODES = ("OFF", "SHADOW", "ACTIVE_EVAL_FILTER", "PRODUCTION_FUNDED")
    EVAL_ALLOWED = {"OFF", "SHADOW", "ACTIVE_EVAL_FILTER"}
    FUNDED_DEFAULT = {"OFF", "SHADOW"}
    PROD_FLAGS = ("approve-d1c-production.flag", "athena-allows-d1c.flag",
                  "d1c-gate-test-pass.flag")

    def __init__(self, store=None):
        self.store = store or Store()

    def requested(self):
        r = self.store.get_state("d1c_requested_mode") or "SHADOW"
        return r if r in self.MODES else "SHADOW"

    def prod_approved(self):
        return all(os.path.exists(os.path.join(APPROVAL_DIR, f)) for f in self.PROD_FLAGS)

    def resolve(self, account_type):
        """Effective D1c mode for an account_type ('eval'|'funded'|None). Fail closed."""
        req = self.requested()
        if account_type == "eval":
            return req if req in self.EVAL_ALLOWED else "SHADOW"
        if account_type == "funded":
            if req in self.FUNDED_DEFAULT:
                return req
            if req == "PRODUCTION_FUNDED":
                return "PRODUCTION_FUNDED" if self.prod_approved() else "SHADOW"
            return "SHADOW"          # ACTIVE_EVAL_FILTER not permitted on funded
        return "OFF" if req == "OFF" else "SHADOW"

    def mode(self, account_type=None):
        return self.resolve(account_type)

    def status(self, account_type=None):
        return dict(requested=self.requested(), mode=self.resolve(account_type),
                    prod_approved=self.prod_approved())


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


# ----------------------------- APOLLO full-auto gate (TradersPost route) -----------------------------
FULL_AUTO_FLAG = "full-auto-approved.flag"
TP_PROVEN_FLAG = "../launchlock/traderspost/PROVEN.flag"   # under evidence/ (sibling of approvals/)


def feed_timeframe(feed_name):
    """Map a --feed name to its bar minutes. tradingview-1m -> 1, tradingview(-5m)/dukascopy -> 5."""
    f = (feed_name or "").lower()
    if f.endswith("-1m") or f == "tradingview1m":
        return 1
    return 5


def resolve_d1c_for_feed(requested_mode, feed_name, realtime_confirmed):
    """D1c may ONLY be ACTIVE_EVAL_FILTER on a real-time 1-minute feed (its validated fidelity).
    On a 5m feed, or without confirmed real-time data, it is forced to SHADOW. Returns
    (effective_mode, downgraded_reason_or_None). Never UPGRADES; never touches Profile B."""
    req = (requested_mode or "OFF").upper().replace("-", "_")
    if req == "ACTIVE_EVAL_FILTER":
        if feed_timeframe(feed_name) != 1:
            return "SHADOW", "feed is %dm (not 1m) — D1c forced SHADOW" % feed_timeframe(feed_name)
        if not realtime_confirmed:
            return "SHADOW", "real-time CME entitlement unconfirmed — D1c forced SHADOW"
    return req, None


def traderspost_ready(store=None):
    """(ok, fails). The live TradersPost route is proven only when the URL is configured AND the
    operator attested a passed Stage 1-3 by creating the PROVEN flag. Built != proven."""
    fails = []
    if not os.environ.get("TRADERSPOST_LIVE_URL"):
        fails.append("TRADERSPOST_LIVE_URL not set")
    if not os.path.exists(os.path.join(APPROVAL_DIR, TP_PROVEN_FLAG)):
        fails.append("TradersPost route not proven (no evidence/launchlock/traderspost/PROVEN.flag — "
                     "run bridge_test ping/one-mnq/flatten and attest)")
    return (len(fails) == 0), fails


def emergency_flatten_available():
    """The single emergency-flatten path must be importable before any live automation."""
    try:
        import ops_flatten  # noqa: F401
        return True
    except Exception:
        return False


CONTROLLED_TEST_FLAG = "controlled-tv-live-test-approved.flag"


def full_auto_preflight(account, feed_name, requested_d1c, data_status, store=None,
                        dashboard_green=False, controlled_test=False):
    """APOLLO master gate for FULL AUTO over the TradersPost route. Returns
    (ok, fails[], effective_d1c, summary). Fail-closed: any missing proof blocks live.

    controlled_test=True = a SUPERVISED, operator-present, single-session live test on the
    TradingView browser feed: it swaps the production approval flag for a one-time test flag and
    permits the browser feed, but keeps EVERY other gate (data GREEN, dead-man, dashboard green,
    ARES, TradersPost proven, bracket verified, daily stop, emergency flatten). PRODUCTION
    (controlled_test=False) still hard-blocks the browser feed and requires full-auto-approved.flag."""
    store = store or Store()
    ds = data_status or {}
    fails = []
    # 1. explicit account
    if not account:
        fails.append("no explicit account (silent default forbidden)")
    # 2. approval flag — controlled test uses a one-time test flag, production uses the full-auto flag
    approval = CONTROLLED_TEST_FLAG if controlled_test else FULL_AUTO_FLAG
    if not os.path.exists(os.path.join(APPROVAL_DIR, approval)):
        fails.append("missing %s/%s" % (APPROVAL_DIR, approval))
    # 3. live data ready (real-time, warmup>=2wk, not stale, reconnect-stable) — computed by the feed
    if not ds.get("DATA_READY"):
        fails.append("DATA not ready: " + "; ".join(ds.get("reasons") or ["no data_status"]))
    if ds.get("data_state") and ds.get("data_state") != "GREEN":
        fails.append("DATA state %s (need GREEN; reconnect must be stable)" % ds.get("data_state"))
    # 3b. HEIMDALL dead-man — full auto requires a live, fresh process heartbeat
    try:
        from heimdall_monitor import deadman_status
        dm = deadman_status()
    except Exception as _e:
        dm = dict(alive=False, reason="dead-man unavailable: %s" % _e)
    if not dm.get("alive"):
        fails.append("DEAD-MAN: " + dm.get("reason", "heartbeat not healthy"))
    # 3c. FEED SOURCE — PRODUCTION needs a proven, soak-passed, non-browser feed (browser froze
    #     twice -> SEMI_AUTO_ONLY). A controlled, supervised test MAY use the browser feed.
    if not controlled_test:
        if (not feed_name) or str(feed_name).startswith("tradingview"):
            fails.append("FEED: '%s' is browser/CDP (SEMI_AUTO_ONLY — froze twice); unattended full auto "
                         "requires a proper API feed (tradovate/databento)" % (feed_name or "none"))
        elif not os.path.exists(os.path.join(APPROVAL_DIR, "feed-soak-passed.flag")):
            fails.append("FEED: '%s' has no soak-pass on record "
                         "(evidence/approvals/feed-soak-passed.flag)" % feed_name)
    # 4. TradersPost execution proven (URL + PROVEN flag) AND the pre-existing technical flags
    #    (kept from LAUNCHLOCK — defense in depth, nothing loosened)
    tp_ok, tp_fails = traderspost_ready(store)
    if not tp_ok:
        fails.extend("EXECUTION: " + f for f in tp_fails)
    for flag in ("traderspost-approved.flag", "bracket-verified.flag"):
        if not os.path.exists(os.path.join(APPROVAL_DIR, flag)):
            fails.append("EXECUTION: missing %s/%s" % (APPROVAL_DIR, flag))
    # 5. dashboard green from source-of-truth
    if not dashboard_green:
        fails.append("dashboard not green")
    # 6. ARES active on this account (ares_mode.py stores under "ares_mode")
    ares = json.loads(store.get_state("ares_mode") or "{}")
    if account and account not in ares:
        fails.append("ARES not armed on %s (arm-eval first)" % account)
    # 7. daily stop configured for the run (caller passes via data_status['daily_stop'] or store)
    if not (ds.get("daily_stop") or store.get_state("auto_daily_stop")):
        fails.append("daily stop not configured")
    # 8. emergency flatten available
    if not emergency_flatten_available():
        fails.append("emergency flatten (ops_flatten) unavailable")
    # 9. duplicate-protection ledger active (BridgeSender keys every send on signalId)
    #    structural in bridge_sender; assert the ledger key is reachable
    try:
        json.loads(store.get_state("bridge_sent") or "{}")
    except Exception:
        fails.append("duplicate ledger unreadable")
    # D1c fidelity resolution (does not fail the gate; downgrades to SHADOW if not 1m+realtime)
    eff_d1c, d1c_reason = resolve_d1c_for_feed(
        requested_d1c, feed_name, bool(ds.get("realtime_confirmed")))
    summary = dict(account=account, feed=feed_name, feed_tf="%dm" % feed_timeframe(feed_name),
                   data_ready=bool(ds.get("DATA_READY")), traderspost_ready=tp_ok,
                   dashboard_green=dashboard_green, requested_d1c=requested_d1c,
                   effective_d1c=eff_d1c, d1c_downgrade=d1c_reason)
    return (len(fails) == 0), fails, eff_d1c, summary
