"""B1 — live execution runner (the ARM). Turns an approved Profile-A signal into
a journaled, server-side-bracketed order through a BrokerView, reconciles against
broker truth every poll, and recovers from broker truth on startup.

This is the piece FENRIR flagged as the single critical-path gap: bot.py (SimBot)
is the BRAIN (signal generation + MFFU/P3 risk gate, parity-verified) but never
had an order path. B1Runner is the hand on the order button — and it is built so
the button is mechanically impossible to push wrongly.

It writes NO new order logic: it composes already-tested, frozen pieces —
  journal.Journal      (B0)  INTENT / can_send / status / open_positions  (idempotent ledger)
  recon.Reconciler     (B0)  5 BLACK checks every poll
  recovery.recover     (B0)  broker-wins resolution of unknown SENDs on startup
  flatten.EmergencyFlatten (W4) the one terminal path for every BLACK
  instance_lock.InstanceLock (FENRIR) single-instance guard
and drives them through the BrokerView/BrokerActions interfaces (SimBroker today,
TradovateBrokerView after the A3 spike).

Invariants enforced here (B1_DESIGN I1-I6):
  I1 no SEND without a durable INTENT + passing can_send()
  I2 ambiguity (SEND w/o ACK) is resolved by reconciliation, NEVER by resend
  I3 protection is server-side (OSO); BRACKET_CONFIRMED only when the stop is
     WORKING at the broker with qty == filled qty
  I4 time is wall-clock (the caller supplies signal_ts; bars are never the clock)
  I5 per-account state and lifecycles; divergence is measured, never force-synced
  I6 fail-closed: emergency lockout, an unreachable broker, or any unresolved SEND
     => that account takes NO new INTENTs (existing positions ride their brackets)

NOTHING here can place a live order without a real BrokerView wired in AND the
SAFETY/live latches in auto_safety — B1Runner against SimBroker is pure simulation.
"""
from journal import Journal
from recon import Reconciler, BLACK
from recovery import recover
from flatten import EmergencyFlatten

FILL_CURSOR_KEY = "b1_fill_cursor"


class B1Runner:
    def __init__(self, journal, broker, store, accounts, strategy="profileA",
                 profile="A", emergency=None):
        self.j = journal
        self.b = broker
        self.store = store
        self.accounts = list(accounts)
        self.strategy = strategy
        self.profile = profile
        self.em = emergency or EmergencyFlatten(journal, broker, store)
        self._recon = Reconciler(journal, broker)
        cur = store.get_state(FILL_CURSOR_KEY)
        self._fill_cursor = int(cur) if cur not in (None, "") else None

    # ============================ startup ============================
    def startup(self, state_view=None, p3_params=None):
        """Part 1F: recovery from BROKER TRUTH before any engine bar is processed.
        A BLACK discrepancy on recovery routes straight to the one terminal path
        (emergency flatten + lockout) — the engine never starts dirty (I6)."""
        report = recover(self.j, self.b, state_view, p3_params)
        black = [d for d in report["discrepancies"] if d.get("tier") == BLACK]
        if black:
            self.em.trigger("startup_recovery_black", account_id="ALL",
                            source="recovery",
                            detail=[d["check"] for d in black])
        report["ready"] = not black and not self.em.locked()
        return report

    # ============================ gating ============================
    def can_trade(self, account_id):
        """I6 fail-closed, derived from ledger + lockout (never from cached belief)."""
        if self.em.locked():
            return False, "emergency_lockout"
        if account_id not in self.accounts:
            return False, "account_not_enabled"
        for cl in self.j.unresolved_sends():
            if self.j.events(cl)[0]["account_id"] == account_id:
                return False, "unresolved_send_on_account"
        return True, "ok"

    # ====================== signal -> order =========================
    def on_signal(self, account_id, sig, qty, signal_ts=None):
        """Approved signal in -> durable INTENT -> gated SEND -> OSO -> ACK.
        `sig` = the same dict the brain emits: side/entry/stop/target/ts_signal.
        Returns a dict describing exactly what happened (never raises on a
        broker timeout — that becomes a fail-closed sent_unknown)."""
        ok, why = self.can_trade(account_id)
        if not ok:
            return dict(action="blocked", account=account_id, reason=why)
        ts = signal_ts or sig.get("ts_signal")
        action = "Buy" if sig["side"] == "long" else "Sell"
        cl = self.j.intent(account_id, self.strategy, self.profile, ts, "entry",
                           payload=dict(side=action, qty=qty, entry=sig["entry"],
                                        stop=sig["stop"], target=sig["target"]))
        if cl is None:                                   # duplicate slot -> refused (I1)
            return dict(action="duplicate", account=account_id)
        return self._send(cl, account_id, action, qty, sig)

    def _send(self, cl, account_id, action, qty, sig):
        ok, why = self.j.can_send(cl)                    # I1 idempotency gate
        if not ok:
            return dict(action="gated", account=account_id, cl=cl, reason=why)
        self.j.append("SEND", account_id, cl, payload=dict(
            side=action, qty=qty, entry=sig["entry"], stop=sig["stop"],
            target=sig["target"]))
        try:
            resp = self.b.place_oso(cl_ord_id=cl, account_id=account_id,
                                    action=action, qty=qty, entry_px=sig["entry"],
                                    stop_px=sig["stop"], target_px=sig["target"])
        except Exception as e:                           # I2: timeout/disconnect
            # SEND exists, no ACK -> sent_unknown. NEVER resend. Account is now
            # no-new-entries (can_trade) until recon/recovery resolves the slot.
            return dict(action="sent_unknown", account=account_id, cl=cl,
                        error=repr(e))
        if not resp.get("accepted"):
            self.j.append("REJECT", account_id, cl, payload=dict(
                reason=resp.get("reason"),
                not_handled=bool(resp.get("not_handled"))))
            return dict(action="rejected", account=account_id, cl=cl,
                        reason=resp.get("reason"))
        self.j.append("ACK", account_id, cl, payload=dict(
            broker_order_id=resp.get("broker_order_id"),
            legs=resp.get("legs"), source="live"))
        return dict(action="acked", account=account_id, cl=cl,
                    broker_order_id=resp.get("broker_order_id"))

    # ============================ poll ==============================
    def poll(self, state_view=None, p3_params=None):
        """One reconciliation cycle (B1_DESIGN 20s in-session):
          1. ingest broker fills since cursor -> FILL/PARTIAL_FILL/EXIT
          2. confirm brackets (stop WORKING == filled qty) -> BRACKET_CONFIRMED
          3. run the 5 BLACK recon checks -> any BLACK => emergency flatten
        A broker that raises mid-poll is treated as fail-closed (I6): positions
        ride their server-side brackets, no new work is invented this cycle."""
        summary = dict(fills=[], bracket_confirmed=[], discrepancies=[],
                       broker_unreachable=False, flattened=False)
        try:
            self._ingest_fills(summary)
            self._confirm_brackets(summary)
            found = self._recon.run(state_view=state_view, p3_params=p3_params)
        except Exception as e:                           # broker unreachable
            summary["broker_unreachable"] = True
            summary["error"] = repr(e)
            return summary
        summary["discrepancies"] = [d["check"] for d in found]
        black = [d for d in found if d.get("tier") == BLACK]
        if black:
            self.em.trigger("recon_black", account_id="ALL", source="recon",
                            detail=[d["check"] for d in black])
            summary["flattened"] = True
        return summary

    def _ingest_fills(self, summary):
        new = self.b.fills_since(self._fill_cursor)
        bmap = self.j.broker_map()
        for f in sorted(new, key=lambda x: x["fill_id"]):
            self._fill_cursor = max(self._fill_cursor or 0, f["fill_id"])
            cl = f.get("cl_ord_id") or bmap.get(str(f.get("broker_order_id")))
            if cl is None or not self.j.has_event(cl, "INTENT"):
                continue                                 # recon CHECK3 will BLACK it
            acct = f["account_id"]
            leg = f.get("leg")
            if leg == "entry":
                intended = (self.j.events(cl)[0]["payload"] or {}).get("qty", f["qty"])
                filled = self._ledger_filled(cl) + f["qty"]
                kind = "FILL" if filled >= intended else "PARTIAL_FILL"
                self.j.append(kind, acct, cl, payload=dict(
                    qty=f["qty"], px=f.get("px"), fill_id=f.get("fill_id"),
                    broker_order_id=f.get("broker_order_id"), source="live"))
                summary["fills"].append((cl, kind, f["qty"]))
            else:                                        # stop / target / flatten
                if cl and self.j.status(cl) in ("open", "partial", "working"):
                    self.j.append("EXIT", acct, cl, payload=dict(
                        qty=f["qty"], px=f.get("px"), reason=leg,
                        fill_id=f.get("fill_id"),
                        broker_order_id=f.get("broker_order_id"), source="live"))
                    summary["fills"].append((cl, "EXIT", f["qty"]))
        self.store.set_state(**{FILL_CURSOR_KEY: self._fill_cursor})

    def _confirm_brackets(self, summary):
        """I3: a stop is protection only when it is WORKING at the broker with
        qty == the position's filled qty. The OSO *response* never confirms it."""
        stops = {}
        for o in self.b.working_orders():
            if o["order_type"] == "Stop":
                stops.setdefault(o["account_id"], []).append(o)
        for (acct, cl), p in self.j.open_positions().items():
            if self.j.has_event(cl, "BRACKET_CONFIRMED"):
                continue
            cover = sum(o["qty"] for o in stops.get(acct, []))
            if cover >= p["qty"] and p["qty"] > 0:
                self.j.append("BRACKET_CONFIRMED", acct, cl, payload=dict(
                    stop_qty=cover, filled_qty=p["qty"], source="live"))
                summary["bracket_confirmed"].append(cl)

    def _ledger_filled(self, cl):
        q = 0
        for e in self.j.events(cl):
            if e["event_type"] in ("FILL", "PARTIAL_FILL"):
                q += (e["payload"] or {}).get("qty", 0)
        return q

    # ====================== declared manual flatten =================
    def flatten_account(self, account_id, reason="manual"):
        """1E DECLARED path: operator-initiated flat. Distinct from an emergency
        BLACK — cancels working + closes the net position and records EXIT on each
        open lifecycle, WITHOUT engaging the lockout. (Undeclared broker-UI action
        is caught as a BLACK by recon, by design — not handled here.)"""
        self.b.cancel_all(account_id)
        self.b.close_position(account_id)
        out = []
        for (acct, cl), p in list(self.j.open_positions().items()):
            if acct != account_id:
                continue
            self.j.append("EXIT", acct, cl, payload=dict(
                qty=p["qty"], reason=reason, source="operator-declared"))
            out.append(cl)
        return dict(account=account_id, exited=out, reason=reason)
