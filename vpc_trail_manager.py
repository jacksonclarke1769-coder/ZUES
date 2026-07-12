"""
VPC live trailing-stop order manager (ADDITIVE, DISARMED-by-default).

The single highest-risk VPC component (per the design spec): a client-side 5.0xATR trailing-stop
manager that must reproduce the certified sim's stop series bit-for-bit while surviving
cancel-replace failure modes WITHOUT ever leaving the position naked. It drives the CANONICAL
`vpc_trail.VpcTrail` stepper (never a second trail implementation) one closed 1m bar at a time and
issues stop cancel-replaces through the additive bridge builders
(`bridge_traderspost.build_vpc_stop_replace`).

Risk-register controls implemented here (design spec §"Carry-forward risk register"):
  * NEVER-NAKED ordering: on each ratchet, the NEW protective stop is sent FIRST; the stale stop is
    cancelled only after the new one is accepted. A failed new-stop send aborts the replace and
    keeps the LAST resting stop working — the position is never left without protection.
  * CANCEL-REPLACE TIMEOUT (fail-safe): a replace that is not confirmed within `timeout_s` triggers
    stand-down — the manager keeps the LAST confirmed resting stop, raises an alert, and stops
    issuing further replaces (never naked, never churning into a hung broker).
  * RATE LIMIT: at most ONE replace per closed 1m bar (bounds the watchdog trail-churn risk).

NO-ACK MODEL: TradersPost returns HTTP-200 "accepted", never "filled", and passes zero market data.
`confirm_fn` is the optional readback hook that reports whether the new stop is actually resting; if
None (default), a successful SEND is treated as landed (optimistic) but a failed send never advances
the resting stop. `send_fn(payload)->{"sent": bool}` mirrors the existing bridge sender contract.

This module is imported by NOTHING on the live path yet — it is exercised only by the paper harness
and its unit tests until the lane is armed via the go-live-recert.sh-gated flag (Phase 4).
"""
import time as _time

import vpc_trail as VT
import bridge_traderspost as BP


class VpcTrailManager:
    def __init__(self, *, account, signal_ts, side, qty, entry, init_stop_dist, trail_atr,
                 send_fn, alert_fn=None, clock_fn=None, confirm_fn=None, timeout_s=8.0,
                 root="MNQ", mode_meta=None):
        if side not in ("long", "short"):
            raise ValueError(f"unknown side {side!r}")
        if int(qty) <= 0:
            raise ValueError("qty must be > 0")
        if float(init_stop_dist) <= 0:
            raise ValueError("init_stop_dist must be > 0")
        self.account = account
        self.signal_ts = signal_ts
        self.side = side
        self.direction = 1 if side == "long" else -1
        self.qty = int(qty)
        self.root = root
        self.mode_meta = mode_meta
        self.send_fn = send_fn
        self.alert_fn = alert_fn or (lambda *a, **k: None)
        self.clock_fn = clock_fn or _time.monotonic
        self.confirm_fn = confirm_fn
        self.timeout_s = float(timeout_s)
        # canonical trail — the ONE implementation, shared with the sim/replay path
        self.trail = VT.VpcTrail(entry, self.direction, float(init_stop_dist), float(trail_atr))
        self.resting_stop = self.trail.stop     # last CONFIRMED working protective stop
        self.seq = 0                             # monotone replace counter -> deterministic sids
        self.last_bar_processed = None           # idempotency + rate-limit: one step/replace per bar id
        self.pending = None                      # in-flight replace: {stop, old_stop, cancel_payload, sent_at, seq}
        self.stood_down = False                  # fail-safe latched: keep last resting stop, stop replacing
        self.exited = False
        self.replaces_sent = 0
        self.replaces_failed = 0
        self.cancelled_stops = []                # every stop LEVEL for which a cancel was sent
        # INVARIANT (asserted in tests): self.resting_stop is NEVER in self.cancelled_stops — the
        # believed-working protective stop is never an order we have already cancelled.

    def _record_cancel(self, level):
        self.cancelled_stops.append(level)

    # -- CONFIRM-THEN-CANCEL resolution of an in-flight readback replace (F1 fix) ------------------
    def _check_timeout(self):
        """Readback path only. The old stop is NEVER cancelled until confirm_fn confirms the NEW
        stop is actually resting (confirm-then-cancel), so on timeout/rejection the OLD stop we keep
        is genuinely still working — never a cancelled order held under a false belief of protection.

          confirm_fn(new_stop) -> True/"resting" : new stop confirmed -> NOW cancel the old stop and
                                                     advance resting to the new level.
                                  "rejected"      : new stop failed downstream -> keep the OLD (still
                                                     uncancelled, TRUE) stop, alert, stand down.
                                  else (False/None): not yet known -> wait until timeout_s, then keep
                                                     the OLD stop (uncancelled, TRUE), alert, stand down."""
        if self.pending is None or self.stood_down:
            return
        status = None
        if self.confirm_fn is not None:
            try:
                status = self.confirm_fn(self.pending["stop"])
            except Exception:                                    # noqa: BLE001 — broken hook -> treat as pending
                status = None
        if status is True or status == "resting":
            # CONFIRMED the new stop is working -> only NOW is it safe to cancel the old one.
            self.send_fn(self.pending["cancel_payload"])
            self._record_cancel(self.pending["old_stop"])
            self.resting_stop = self.pending["stop"]
            self.pending = None
            return
        if status == "rejected":
            self.stood_down = True                               # LATCH fail-safe
            self.alert_fn("vpc_trail_replace_rejected",
                          account=self.account, signal_ts=self.signal_ts,
                          detail=f"new stop {self.pending['stop']} rejected downstream; keeping OLD "
                                 f"resting stop {self.resting_stop} (uncancelled, working); standing down")
            self.pending = None                                  # resting_stop already == old (never advanced)
            return
        if self.clock_fn() - self.pending["sent_at"] > self.timeout_s:
            self.stood_down = True                               # LATCH fail-safe
            self.alert_fn("vpc_trail_timeout",
                          account=self.account, signal_ts=self.signal_ts,
                          detail=f"cancel-replace not confirmed in {self.timeout_s}s; keeping OLD "
                                 f"resting stop {self.resting_stop} (uncancelled, working — the old "
                                 f"stop was never cancelled); standing down further replaces")
            # resting_stop is the OLD stop, which we deliberately never cancelled -> genuinely protected
            self.pending = None

    def on_1m_bar(self, bar_id, low, high, close, atr_now, now_ts=None):
        """Advance the trail by one closed 1m bar. Returns:
          ("exit", stop_level)     -- the resting stop was hit; the position is out at stop_level.
          ("replace", new_stop)    -- a cancel-replace was issued this bar (rate-limited).
          ("hold", resting_stop)   -- no change (or rate-limited / stood-down).
        The stop-HIT check uses the resting stop established BEFORE this bar (adverse-first ordering,
        enforced inside VpcTrail.step)."""
        if self.exited:
            return ("exit", self.resting_stop)
        # IDEMPOTENCY + MONOTONIC ORDERING (F2 fix): bar_id must be strictly increasing (a
        # timestamp-ordered monotone id). Any bar_id <= the last one processed — a duplicate re-poll,
        # a reconnect that REPLAYS the last N minutes, or an out-of-order stale delivery — is
        # REJECTED without re-stepping the canonical trail. Re-stepping a stale bar would either
        # double-ratchet the internal stop past the actually-working resting stop or fire a PHANTOM
        # exit against a level that was never truly resting.
        if self.last_bar_processed is not None and bar_id <= self.last_bar_processed:
            return ("hold", self.resting_stop)
        self.last_bar_processed = bar_id
        self._check_timeout()
        flag, level = self.trail.step(low, high, close, atr_now)
        if flag == "stop":
            self.exited = True
            return ("exit", self.resting_stop)     # exit at the LAST CONFIRMED resting stop (never a phantom)
        # candidate ratcheted stop = `level`; only replace if it actually moved and we're allowed to
        if level == self.resting_stop or self.stood_down:
            return ("hold", self.resting_stop)
        if self.pending is not None:
            return ("hold", self.resting_stop)     # a prior replace still in flight — do not stack
        return self._issue_replace(level, bar_id, now_ts)

    def _issue_replace(self, new_stop, bar_id, now_ts):
        pair, err = BP.build_vpc_stop_replace(
            account=self.account, signal_ts=self.signal_ts, side=self.side, qty=self.qty,
            new_stop=new_stop, root=self.root, seq=self.seq, mode_meta=self.mode_meta)
        if err:                                    # fail-closed: no payload -> keep last resting stop
            self.replaces_failed += 1
            self.alert_fn("vpc_trail_build_fail", account=self.account, detail=err)
            return ("hold", self.resting_stop)
        cancel_payload, stop_payload = pair
        # NEVER-NAKED: place the NEW stop first; the stale stop is cancelled only per the model below.
        res_new = self.send_fn(stop_payload)
        if not res_new.get("sent"):
            self.replaces_failed += 1
            self.alert_fn("vpc_trail_send_fail", account=self.account,
                          detail=f"new stop {new_stop} not accepted; keeping resting {self.resting_stop}")
            return ("hold", self.resting_stop)     # old stop still works — never naked
        self.seq += 1
        self.replaces_sent += 1
        sent_at = now_ts if now_ts is not None else self.clock_fn()
        old_stop = self.resting_stop
        if self.confirm_fn is None:
            # NO-ACK model (default): a good send is optimistically treated as landed immediately, so
            # the stale stop is cancelled now and resting advances. (This still carries the inherent
            # webhook-only gap — a 200 that fails downstream — flagged as a Phase-4 wire item; it is
            # NOT the F1 defect, which was the readback path cancelling BEFORE confirmation.)
            self.send_fn(cancel_payload)
            self._record_cancel(old_stop)
            self.resting_stop = new_stop
            self.pending = None
        else:
            # READBACK model (F1 fix): do NOT cancel the old stop yet. Hold the replace in-flight with
            # resting_stop STILL AT THE OLD (uncancelled, working) level; _check_timeout cancels the old
            # stop ONLY after confirm_fn confirms the new one resting (confirm-then-cancel). On
            # timeout/rejection the old stop is kept — and it is genuinely still working, never naked.
            self.pending = {"stop": new_stop, "old_stop": old_stop, "cancel_payload": cancel_payload,
                            "sent_at": sent_at, "seq": self.seq - 1}
        return ("replace", new_stop)
