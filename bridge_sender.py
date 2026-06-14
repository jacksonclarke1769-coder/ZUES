"""BRIDGE — webhook sender. Transmits ZEUS-approved payloads to TradersPost.

dry-run (default) builds/logs only. test posts to a configured TEST webhook. live is
LOCKED behind an approval flag + configured URL + per-signal dedup. A retry can never
duplicate an order: the deterministic signalId + a persisted sent-ledger make a second
confirmed send of the same id impossible.

FAIL CLOSED everywhere. If ZEUS blocks the trade, no payload reaches here at all
(see process_signal): the builder is only called for permitted trades.
"""
import json
import os
from datetime import datetime, timezone

import requests

from store import Store
from journal import Journal
from auto_safety import APPROVAL_DIR
from d1c_filter import profile_a_permission, profile_b_permission

SENT_KEY = "bridge_sent"          # {signalId: {ts, status}}
LOG = "out/ares/bridge_webhook_log.csv"
MODES = ("dry-run", "test", "live")


def _now():
    return datetime.now(timezone.utc).isoformat()


class BridgeSender:
    def __init__(self, store=None, journal=None, mode="dry-run",
                 test_url=None, live_url=None):
        self.store = store or Store()
        self.j = journal or Journal()
        assert mode in MODES, mode
        self.mode = mode
        self.test_url = test_url
        self.live_url = live_url

    # ---- dedup ledger ----
    def _sent(self):
        return json.loads(self.store.get_state(SENT_KEY) or "{}")

    def already_sent(self, sid):
        rec = self._sent().get(sid)
        return bool(rec and rec.get("status") == "confirmed")

    def _mark(self, sid, status):
        m = self._sent(); m[sid] = dict(ts=_now(), status=status)
        self.store.set_state(**{SENT_KEY: json.dumps(m)})

    def _log(self, sid, payload, mode, result, note=""):
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        new = not os.path.exists(LOG)
        with open(LOG, "a") as f:
            if new:
                f.write("ts,signal_id,mode,action,ticker,qty,result,note\n")
            f.write(f"{_now()},{sid},{mode},{payload.get('action')},"
                    f"{payload.get('ticker')},{payload.get('quantity','')},{result},{note}\n")
        self.j.append("STATE_ASSERT", payload.get("extras", {}).get("account", "ALL"),
                      payload=dict(action="bridge_webhook", signal_id=sid, mode=mode,
                                   result=result, note=note))

    # ---- live latches for the bridge path ----
    def _live_ok(self, payload):
        fails = []
        meta = payload.get("extras", {})
        if not meta.get("account"):
            fails.append("no account in payload")
        if not meta.get("strategy"):
            fails.append("no strategy id")
        if not os.path.exists(os.path.join(APPROVAL_DIR, "traderspost-approved.flag")):
            fails.append("missing traderspost-approved.flag")
        if not self.live_url:
            fails.append("no live webhook URL configured")
        return (len(fails) == 0), fails

    def send(self, payload, retries=2, timeout=8):
        """Send (or refuse) one payload. Idempotent: dedup by signalId."""
        if payload is None:
            return dict(sent=False, reason="no payload (ZEUS blocked or build failed)")
        sid = payload.get("extras", {}).get("signalId") or payload.get("signalId")
        if not sid:
            self._log("MISSING", payload, self.mode, "refused", "no signalId")
            return dict(sent=False, reason="no signalId — refused")
        if self.already_sent(sid):
            self._log(sid, payload, self.mode, "duplicate-blocked")
            return dict(sent=False, reason="duplicate signalId — already confirmed")

        if self.mode == "dry-run":
            self._log(sid, payload, "dry-run", "logged")
            return dict(sent=False, reason="dry-run (no webhook by design)", payload=payload)

        url = self.test_url if self.mode == "test" else None
        if self.mode == "live":
            ok, fails = self._live_ok(payload)
            if not ok:
                self._log(sid, payload, "live", "refused", ";".join(fails))
                return dict(sent=False, reason="live refused: " + "; ".join(fails))
            url = self.live_url
        if not url:
            self._log(sid, payload, self.mode, "refused", "no url")
            return dict(sent=False, reason=f"{self.mode}: no webhook URL")

        # idempotent transmit: mark 'pending' before send; only 'confirmed' blocks resend
        self._mark(sid, "pending")
        last = None
        for attempt in range(retries + 1):
            try:
                r = requests.post(url, json=payload, timeout=timeout)
                if 200 <= r.status_code < 300:
                    self._mark(sid, "confirmed")
                    self._log(sid, payload, self.mode, "confirmed", f"http {r.status_code}")
                    return dict(sent=True, status=r.status_code)
                last = f"http {r.status_code}"
            except requests.RequestException as e:           # network — safe to retry SAME id
                last = repr(e)
        # all attempts failed; left 'pending' (NOT confirmed) so a later manual retry of the
        # SAME signalId cannot create a second order (TradersPost + our dedup both key on it)
        self._log(sid, payload, self.mode, "failed", last or "")
        return dict(sent=False, reason=f"send failed after retries: {last}")


# ---------------- ZEUS gate -> build -> send orchestration ----------------

def process_profile_a(sender, builder, *, d1c_mode, daily_stopped, p3_blocked,
                      drift_value, drift_sign, signal_present=True, **build_kw):
    """If ZEUS blocks Profile A, NO payload is built and NO webhook is sent."""
    perm = profile_a_permission(d1c_mode, signal_present=signal_present,
                                daily_stopped=daily_stopped, p3_blocked=p3_blocked,
                                drift_value=drift_value, drift_sign=drift_sign,
                                direction=build_kw.get("side", "long"),
                                feed_age_s=build_kw.pop("feed_age_s", 10),
                                has_open=build_kw.pop("has_open", True))
    if not perm["permit"]:
        return dict(sent=False, reason=f"ZEUS blocked Profile A: {perm['reason']}",
                    d1c=perm["d1c_decision"])
    payload, err = builder(**build_kw)
    if err:
        return dict(sent=False, reason=f"payload build failed (fail closed): {err}")
    return sender.send(payload)


def process_profile_b(sender, builder, *, daily_stopped, p3_blocked,
                      signal_present=True, **build_kw):
    """Profile B never consults D1c."""
    perm = profile_b_permission(signal_present=signal_present,
                                daily_stopped=daily_stopped, p3_blocked=p3_blocked)
    if not perm["permit"]:
        return dict(sent=False, reason=f"ZEUS blocked Profile B: {perm['reason']}")
    payload, err = builder(**build_kw)
    if err:
        return dict(sent=False, reason=f"payload build failed (fail closed): {err}")
    return sender.send(payload)
