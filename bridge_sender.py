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

# Actions that are safe to repeat: closing/cancelling twice is safe-direction.
# Anything not in this set is treated as opening exposure (fail-closed: ambiguous = entry).
_SAFE_REPEAT_ACTIONS = frozenset({"exit", "cancel"})


def _is_entry_payload(payload):
    """Return True when the payload opens exposure.  Fail-closed: unknown action = entry."""
    action = (payload or {}).get("action")
    return action not in _SAFE_REPEAT_ACTIONS


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
        action = payload.get("action")
        # EXITLOCK gate (2026-06-21): the live bridge sends full-qty single-target, which does
        # NOT match the validated Exit #3 partial backtest. Block every live ENTRY until the exit
        # model is aligned or explicitly approved via exit-model-approved.flag. Exits and cancels
        # (incl. emergency flatten) are NEVER blocked — risk must always be reducible.
        if action in ("buy", "sell", "add"):
            if not os.path.exists(os.path.join(APPROVAL_DIR, "exit-model-approved.flag")):
                fails.append("LIVE BLOCKED: exit model not approved/aligned")
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
            except requests.Timeout as e:
                # Delivery is UNKNOWN — server may have processed the POST before the timeout.
                # Retry is safe ONLY for exit/cancel (closing/cancelling twice is safe-direction).
                # For entry payloads (open exposure): do NOT retry; mark pending-unverified.
                if _is_entry_payload(payload):
                    reason = ("timeout-unverified — no blind retry on entries; "
                              "verify position via read-back before re-sending")
                    self._mark(sid, "pending-unverified")
                    self.j.append("STATE_ASSERT",
                                  payload.get("extras", {}).get("account", "ALL"),
                                  payload=dict(action="bridge_timeout_unverified",
                                               signal_id=sid, mode=self.mode, note=reason))
                    self._log(sid, payload, self.mode, "timeout-unverified", reason)
                    return dict(sent=False, reason=reason)
                last = repr(e)        # exit/cancel: safe to retry
            except requests.RequestException as e:   # ConnectionError etc. — nothing delivered; retry
                last = repr(e)
        # all attempts failed; left 'pending' (NOT confirmed) so a later manual retry of the
        # SAME signalId cannot create a second order (TradersPost + our dedup both key on it)
        self._log(sid, payload, self.mode, "failed", last or "")
        return dict(sent=False, reason=f"send failed after retries: {last}")

    # ---- EXITFORGE incident block (half-built Exit #3 position -> no new entries) ----
    INCIDENT_KEY = "exit3_incident"

    def incident_blocked(self):
        v = self.store.get_state(self.INCIDENT_KEY)
        return v if v else None

    def _incident(self, account, kind, role, details):
        self.store.set_state(**{self.INCIDENT_KEY: json.dumps(
            dict(ts=_now(), kind=kind, role=role, account=account))})
        self.j.append("STATE_ASSERT", account, payload=dict(
            action="exit3_incident", kind=kind, role=role, details=str(details)[:300]))

    def clear_incident(self, operator_note):
        if not operator_note or len(operator_note.strip()) < 10:
            raise ValueError("operator note required (>=10 chars)")
        self.store.set_state(**{self.INCIDENT_KEY: ""})
        self.j.append("STATE_ASSERT", "ALL", payload=dict(
            action="exit3_incident_cleared", note=operator_note.strip()))
        return True

    def send_exit3(self, legs, account, root="MNQ"):
        """EXITFORGE: transmit the two Exit #3 legs in order (CORE/TP2 first, then TP1).
        FAIL CLOSED — never leave a half-built position:
          * core leg fails first (nothing sent)  -> ENTRY_ABORTED (no position, no flatten)
          * a later leg fails after one was sent  -> flatten/cancel + PARTIAL_ENTRY_FAILED + block
          * any leg missing stop/target          -> abort/flatten + INCIDENT + block
        Returns dict(ok, reason, legs=[...], flattened?)."""
        if self.incident_blocked():
            return dict(ok=False, reason="exit3 incident active — manual reset required", legs=[])
        if not legs:
            return dict(ok=False, reason="no legs to send", legs=[])
        # pre-send integrity: every leg must carry a stop AND a target
        for leg in legs:
            p = leg["payload"]
            if "stopLoss" not in p or "takeProfit" not in p:
                self._incident(account, "MISSING_BRACKET", leg.get("role"), p)
                self.flatten(account, root=root, reason=f"exit3_missing_bracket_{_now()}")
                return dict(ok=False, reason="leg missing stop/target — flattened + blocked",
                            legs=[], flattened=True)
        results = []
        sent_any = False
        for leg in legs:
            res = self.send(leg["payload"])
            results.append(dict(role=leg["role"], qty=leg["qty"], **res))
            ok = bool(res.get("sent")) or self.mode != "live"   # dry-run/test = built-ok
            if not ok:
                if sent_any:
                    self.flatten(account, root=root, reason=f"exit3_partial_fail_{_now()}")
                    self._incident(account, "PARTIAL_ENTRY_FAILED", leg["role"], results)
                    return dict(ok=False, reason="PARTIAL_ENTRY_FAILED", legs=results,
                                flattened=True)
                # core leg never sent -> no position exists; abort without blocking (no incident)
                self.j.append("STATE_ASSERT", account, payload=dict(
                    action="exit3_entry_aborted", role=leg["role"]))
                return dict(ok=False, reason="ENTRY_ABORTED", legs=results)
            sent_any = True
        return dict(ok=True, reason="exit3 both legs sent", legs=results)

    def flatten(self, account, root="MNQ", reason="emergency"):
        """Emergency flatten = CANCEL working orders THEN EXIT the position.

        TradersPost `exit` only closes the position; it leaves attached bracket legs WORKING
        (orphan stop/target that can re-open a position). So we first send `cancel` (cancels all
        working orders for the ticker), then `exit`. Cancel-first removes the stop/target before
        the market exit, avoiding a stop/exit double-fill. Returns both results + an `ok` flag.
        Pass a fresh `reason` (e.g. a timestamp) so a retry is not dedup-blocked."""
        import bridge_traderspost as BP
        cancel_p, _ = BP.build_cancel(account=account, strategy="EMERGENCY",
                                      signal_ts=reason, root=root)
        cancel_res = self.send(cancel_p)
        exit_p, _ = BP.build_flatten(account=account, root=root, reason=reason)
        exit_res = self.send(exit_p)
        done = self.mode != "live"
        ok = (cancel_res.get("sent") or done) and (exit_res.get("sent") or done)
        return dict(cancel=cancel_res, exit=exit_res, ok=bool(ok))


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
