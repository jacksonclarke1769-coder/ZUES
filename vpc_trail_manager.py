"""
VPC live trailing-stop order manager (ADDITIVE, DISARMED-by-default).

The single highest-risk VPC component (per the design spec): a client-side 5.0xATR trailing-stop
manager that must reproduce the certified sim's stop series bit-for-bit while surviving
cancel-replace failure modes WITHOUT ever leaving the position naked. It drives the CANONICAL
`vpc_trail.VpcTrail` stepper (never a second trail implementation) one closed 1m bar at a time and
issues stop cancel-replaces through the additive bridge builder
(`bridge_traderspost.build_vpc_stop_replace`).

D6 SINGLE-CALL BUNDLED CANCEL-REPLACE (docs.traderspost.io, verbatim-verified 2026-07-12):
  TradersPost does NOT OCO-link a stop added to an open position, so the previous two-payload
  "place NEW stop, confirm, then cancel OLD" ordering would create a window with two un-linked live
  stops = double-fill exposure. The documented correct primitive is ONE webhook call carrying the
  new protective-stop order AND `cancel: true` — TradersPost sequences cancel-of-old + place-new
  server-side and, on any cancel/timeout, FAILS THE WHOLE trade (the old stop stands, nothing
  changed) instead of orphaning. That maps perfectly onto never-naked, so this manager sends the
  replace exactly ONCE per ratchet; the eager client-side cancel of the old stop is GONE entirely.

Risk-register controls implemented here (design spec §"Carry-forward risk register"):
  * NEVER-NAKED: every replace is a single bundled cancel-replace. A failed send (or an unconfirmed
    readback) leaves the OLD resting stop working, unchanged — the position is never without a stop.
  * NO TWO LIVE STOPS: the manager's model believes in exactly ONE live protective stop at every
    instant (`live_stops()` -> always a single level). During an in-flight readback the belief stays
    the OLD level until confirmed; the bundled replace either fully lands (new) or fully fails (old).
  * CANCEL-REPLACE TIMEOUT (fail-safe): a readback replace not confirmed within `timeout_s` stands
    down — keep the OLD (still-working) stop, alert, stop issuing further replaces.
  * RATE LIMIT + MONOTONIC BAR ORDERING: at most ONE replace per closed 1m bar; any bar_id <= the
    last processed (duplicate re-poll / reconnect replay / out-of-order stale delivery) is rejected.
  * KILL/FLATTEN (D3): a kill or flatten — including one arriving mid-replace-confirm — NEVER
    cancels the believed-resting stop first. It market-flattens, and the leftover resting stop is
    cleaned up ONLY after the readback path confirms the position is flat (naked-impossible).

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
        self.resting_stop = self.trail.stop     # the ONE live protective stop the manager believes in
        self.seq = 0                             # monotone replace counter -> deterministic sids
        self.last_bar_processed = None           # idempotency + rate-limit: one step/replace per bar id
        self.pending = None                      # in-flight readback replace: {stop, old_stop, sent_at, seq}
        self.stood_down = False                  # fail-safe latched: keep last resting stop, stop replacing
        self.exited = False
        self.killed = False                      # D3: kill/flatten latched -> no more replaces
        self.awaiting_flat = False               # D3: market-flatten sent, resting-stop cleanup deferred
        self.replaces_sent = 0
        self.replaces_failed = 0
        # cancelled_stops: stop LEVELS for which the manager itself issued a client-side cancel. In the
        # SINGLE-CALL model (D6) the ratchet cancel is BUNDLED server-side, so this stays EMPTY during
        # normal trailing — a level lands here ONLY on the D3 flat-confirmed cleanup (position already
        # flat). INVARIANT (asserted in tests): resting_stop is NEVER in cancelled_stops while a
        # position is open — the believed-working protective stop is never one we have cancelled.
        self.cancelled_stops = []

    def _record_cancel(self, level):
        self.cancelled_stops.append(level)

    def live_stops(self):
        """The set of protective-stop LEVELS the manager believes are simultaneously LIVE at the
        broker. Under the single-call bundled cancel-replace model this is ALWAYS exactly one level:
        the bundled replace either fully lands (new stop; old auto-cancelled server-side) or fully
        fails (old stop stands). The in-flight `pending["stop"]` is NOT yet believed-live —
        resting_stop stays the OLD level until confirmed — so there is never a window with two
        un-linked live stops. Empty only once the position is flat and its stop cleaned up."""
        if self.exited and not self.awaiting_flat and self.resting_stop in self.cancelled_stops:
            return set()
        return {self.resting_stop}

    # -- readback resolution of an in-flight single-call replace (never-naked, no eager cancel) -----
    def _check_timeout(self):
        """Readback path only. The old stop is NEVER cancelled by us — the bundled cancel-replace
        handles it server-side atomically. Until confirm_fn confirms the NEW stop resting, the
        believed-resting stop stays the OLD (still-working) level, so on timeout/rejection the
        position is genuinely still protected — never naked, never two live stops.

          confirm_fn(new_stop) -> True/"resting" : bundled replace landed -> advance resting to new.
                                  "rejected"      : bundled replace failed-whole -> keep OLD stop
                                                     (unchanged, working), alert, stand down.
                                  else (False/None): not yet known -> wait until timeout_s, then keep
                                                     the OLD stop, alert, stand down."""
        if self.pending is None or self.stood_down:
            return
        status = None
        if self.confirm_fn is not None:
            try:
                status = self.confirm_fn(self.pending["stop"])
            except Exception:                                    # noqa: BLE001 — broken hook -> pending
                status = None
        if status is True or status == "resting":
            # bundled cancel-replace CONFIRMED landed -> the new stop is now the single live stop.
            self.resting_stop = self.pending["stop"]
            self.pending = None
            return
        if status == "rejected":
            self.stood_down = True                               # LATCH fail-safe
            self.alert_fn("vpc_trail_replace_rejected",
                          account=self.account, signal_ts=self.signal_ts,
                          detail=f"bundled cancel-replace to {self.pending['stop']} failed-whole; "
                                 f"keeping OLD resting stop {self.resting_stop} (unchanged, working); "
                                 f"standing down")
            self.pending = None                                  # resting_stop already == old (never advanced)
            return
        if self.clock_fn() - self.pending["sent_at"] > self.timeout_s:
            self.stood_down = True                               # LATCH fail-safe
            self.alert_fn("vpc_trail_timeout",
                          account=self.account, signal_ts=self.signal_ts,
                          detail=f"bundled cancel-replace not confirmed in {self.timeout_s}s; the "
                                 f"replace fails-whole, so the OLD resting stop {self.resting_stop} "
                                 f"stands (unchanged, working); standing down further replaces")
            self.pending = None

    def on_1m_bar(self, bar_id, low, high, close, atr_now, now_ts=None):
        """Advance the trail by one closed 1m bar. Returns:
          ("exit", stop_level)     -- the resting stop was hit; the position is out at stop_level.
          ("replace", new_stop)    -- a cancel-replace was issued this bar (rate-limited).
          ("hold", resting_stop)   -- no change (or rate-limited / stood-down / killed).
        The stop-HIT check uses the resting stop established BEFORE this bar (adverse-first ordering,
        enforced inside VpcTrail.step)."""
        if self.exited:
            return ("exit", self.resting_stop)
        if self.killed:
            return ("hold", self.resting_stop)     # D3: kill latched -> no stepping/replacing
        # IDEMPOTENCY + MONOTONIC ORDERING (F2): bar_id must be strictly increasing (a
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
        payload, err = BP.build_vpc_stop_replace(
            account=self.account, signal_ts=self.signal_ts, side=self.side, qty=self.qty,
            new_stop=new_stop, root=self.root, seq=self.seq, mode_meta=self.mode_meta)
        if err:                                    # fail-closed: no payload -> keep last resting stop
            self.replaces_failed += 1
            self.alert_fn("vpc_trail_build_fail", account=self.account, detail=err)
            return ("hold", self.resting_stop)
        # SINGLE-CALL bundled cancel-replace (D6): send ONCE. The server sequences cancel-old +
        # place-new; a failed send is a failed-whole replace, so the OLD stop stands (never naked,
        # never two live stops). There is no separate client-side cancel to issue.
        res = self.send_fn(payload)
        if not res.get("sent"):
            self.replaces_failed += 1
            self.alert_fn("vpc_trail_send_fail", account=self.account,
                          detail=f"bundled replace to {new_stop} not accepted; failed-whole -> "
                                 f"keeping OLD resting stop {self.resting_stop} (never naked)")
            return ("hold", self.resting_stop)     # old stop still works — never naked
        self.seq += 1
        self.replaces_sent += 1
        sent_at = now_ts if now_ts is not None else self.clock_fn()
        old_stop = self.resting_stop
        if self.confirm_fn is None:
            # NO-ACK model (default): a good send of the bundled cancel-replace is optimistically
            # treated as landed, so resting advances to the new level. Still one live stop throughout
            # (the server cancels the old as it places the new). The inherent webhook-only gap — a 200
            # that fails downstream — is the Phase-4 wire/ticket item, NOT a two-stops defect.
            self.resting_stop = new_stop
            self.pending = None
        else:
            # READBACK model: hold the replace in-flight with resting_stop STILL AT THE OLD
            # (unchanged, working) level; _check_timeout advances to the new level ONLY after
            # confirm_fn confirms it resting. On timeout/rejection the OLD stop stands (failed-whole).
            self.pending = {"stop": new_stop, "old_stop": old_stop,
                            "sent_at": sent_at, "seq": self.seq - 1}
        return ("replace", new_stop)

    # -- D3: KILL / FLATTEN semantics (Phase-4 DEC) -------------------------------------------------
    def kill_flatten(self, reason, *, flatten_fn=None, now_ts=None):
        """A kill or flatten arriving at ANY point — INCLUDING while a cancel-replace confirm is
        in flight — must NEVER cancel the believed-resting protective stop first (that would open a
        naked window). Sequence (F1 pattern, single-call model):
          1. LATCH kill: stop issuing further replaces; ABANDON any in-flight pending replace WITHOUT
             cancelling anything — the OLD resting stop is unchanged and still working, so the
             position stays protected the entire time.
          2. Send a MARKET-FLATTEN (flatten_fn -> e.g. bridge.build_flatten + sender). The position
             is closed at MARKET, never by cancelling its stop.
          3. Resting-stop CLEANUP is DEFERRED to on_flat_confirmed(): the leftover resting stop is
             cancelled ONLY after the readback path confirms the position is flat. So there is never
             a moment where the position is open AND its stop has been cancelled (naked-impossible).
        Returns the flatten payload/result (or None if no flatten_fn given). Idempotent."""
        was_killed = self.killed
        self.killed = True
        self.stood_down = True
        self.pending = None                # abandon in-flight replace; resting_stop stays the OLD stop
        self.awaiting_flat = True
        result = None
        if flatten_fn is not None and not was_killed:
            result = flatten_fn(reason)    # market-flatten (the position's exit; NOT a stop cancel)
        if not was_killed:
            self.alert_fn("vpc_trail_kill_flatten", account=self.account, signal_ts=self.signal_ts,
                          detail=f"{reason}; market-flatten issued; resting stop {self.resting_stop} "
                                 f"left WORKING until flat-confirmed (never naked)")
        return result

    def on_flat_confirmed(self, *, cancel_fn=None):
        """Called by the readback path once the position is confirmed FLAT after a kill/flatten. NOW
        — and only now, with no position left to protect — cancel any leftover resting protective
        stop. Cancelling before flat-confirm would be naked; deferring it here makes naked impossible.
        Returns the cancel payload/result (or None). Idempotent (no-op if not awaiting flat)."""
        if not self.awaiting_flat:
            return None
        self.awaiting_flat = False
        self.exited = True
        result = None
        if cancel_fn is not None:
            result = cancel_fn(self.resting_stop)     # safe: position is flat, nothing left to protect
        self._record_cancel(self.resting_stop)
        return result
