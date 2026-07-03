"""
STAGE B — LIVE READ-BACK SENTINEL. Closes the "confirm fills by eye" gap for UNATTENDED ops.

Under TradersPost one-way routing the bot gets no fills back, so it cannot self-verify its broker
position. This sentinel makes execution a CLOSED loop: orders go OUT via TradersPost, TRUTH comes IN
via Tradovate REST (READ-ONLY: /position/list + cashBalance snapshot). Each poll it reconciles broker
reality against (a) the bot's expected net position and (b) the MFFU trailing floor. On a CONFIRMED
critical discrepancy (grace-filtered to ignore in-flight fills) it HALTS new entries, writes a
RECON_ALERT, and fires an optional critical callback (flatten). It NEVER places an opening order.

BROKER IS TRUTH (same doctrine as recon.py). Detects the unattended-critical failure modes:
  ORPHAN_POSITION     broker holds a position while the bot believes it is FLAT  -> BLACK (uncovered exposure)
  DIRECTION_MISMATCH  broker net sign != bot expected sign                       -> BLACK (wrong-way risk)
  MISSING_POSITION    bot expects a position but broker is FLAT                  -> ORANGE (entry didn't fill / closed)
  BALANCE_FLOOR       broker balance <= MFFU trailing floor                      -> BLACK (independent of bot P&L)
  BROKER_READ_FAIL    cannot read the broker for >=3 polls                       -> ORANGE->BLACK (can't verify = fail closed)

Fail-closed: a sentinel that cannot SEE the broker blocks new entries — a gate failure can only cost
income, never add risk.
"""
from __future__ import annotations

GRACE_CYCLES = 2
BLACK, ORANGE = "BLACK", "ORANGE"

# READ-class BLACKs mean "cannot SEE the broker" (panel/API failure) — halt + alert, but NEVER
# market-flatten a possibly-healthy position over a cosmetic read failure (2026-07-02 audit T0-3:
# a collapsed TV panel triggered a live flatten). MISMATCH-class BLACKs (panel READ, disagrees)
# still fire on_critical (flatten).
READ_FAIL_CHECKS = {"BROKER_READ_FAIL", "BALANCE_UNREADABLE"}
BAL_NONE_CONFIRM = 5   # consecutive None balances (with a floor set) before failing closed


# ---------------------------------------------------------------------------
# Broker adapters (READ-ONLY). net_by_account() -> {account_id: signed net qty};
# balance(account_id) -> float equity or None.
# ---------------------------------------------------------------------------
class TradovateBrokerView:
    """Read-only view over a connected TradovateClient. Never places orders."""

    def __init__(self, client):
        self.c = client

    def net_by_account(self):
        out = {}
        for p in (self.c.positions() or []):
            acct = str(p.get("accountId"))
            out[acct] = out.get(acct, 0) + int(p.get("netPos", 0) or 0)
        return out

    def balance(self, account_id):
        snap = self.c.account_snapshot() or {}
        cb = snap.get("cashBalance")
        if cb is None:
            return None
        return float(cb) + float(snap.get("openPnL", 0) or 0)   # equity (conservative for the floor)


# ---------------------------------------------------------------------------
# Sentinel
# ---------------------------------------------------------------------------
class ReadbackSentinel:
    """Reconciles broker truth vs the bot's belief. Halts fail-closed on confirmed criticals.

    account_id : the Tradovate account to watch.
    floor      : absolute equity floor (MFFU trailing line); <= floor => BLACK. None disables.
    grace      : a discrepancy must persist this many consecutive polls before it is CONFIRMED.
    on_critical: callback(reason:str) fired ONCE when a BLACK is confirmed (wire to flatten). Optional.
    journal    : object with .append(event_type, account_id, payload=dict). Optional.
    """

    def __init__(self, account_id, floor=None, grace=GRACE_CYCLES,
                 on_critical=None, journal=None, on_alert=None,
                 on_missing=None, missing_confirm=6):
        self.account = str(account_id)
        self.floor = floor
        self.grace = grace
        self.on_critical = on_critical
        self.on_alert = on_alert   # callback(msg:str) for operator notification (e.g. Telegram). Optional.
        self.journal = journal
        self.on_missing = on_missing        # callback(expected:int) fired ONCE per episode after missing_confirm polls
        self.missing_confirm = missing_confirm  # consecutive MISSING_POSITION polls before on_missing fires (~2 min at 20s)
        self.expected = 0          # bot's belief: signed net qty (long>0, short<0, flat=0)
        self.halted = False
        self.reason = None
        self._seen = {}
        self._read_fail = 0
        self._bal_none = 0         # consecutive successful polls where balance() returned None
        self.last = []             # last confirmed discrepancies (for monitoring)
        self._missing_consec = 0   # consecutive polls where MISSING_POSITION was observed
        self._missing_fired = False  # on_missing already fired this episode (reset when condition clears)
        self._fill_confirmed = False  # FILL_CONFIRMED journaled this entry episode (reset on on_entry)

    def _alert(self, msg):
        if self.on_alert is None:
            return
        try:
            self.on_alert(msg)
        except Exception:                                         # noqa: BLE001 — alerting never breaks safety
            pass

    def reset(self):
        """Operator re-arm (/resume): clear the halt latch and all persistence counters.
        Does NOT touch `expected` — the bot's position belief survives a re-arm."""
        self.halted = False
        self.reason = None
        self._seen = {}
        self._read_fail = 0
        self._bal_none = 0
        self.last = []
        self._missing_consec = 0
        self._missing_fired = False
        self._fill_confirmed = False

    # ----- the loop tells the sentinel what it BELIEVES it did -----
    def on_entry(self, side, qty):
        s = 1 if str(side).lower() in ("long", "buy") else -1
        self.expected += s * int(qty)
        self._fill_confirmed = False   # new entry episode: re-arm the fill-confirmation log

    def on_partial_or_exit(self, signed_delta):
        """Apply a known reduction/close (signed). For a full flat, prefer on_flat()."""
        self.expected += int(signed_delta)

    def on_flat(self):
        self.expected = 0
        self._fill_confirmed = False
        self._missing_consec = 0
        self._missing_fired = False

    # ----- monitoring hook for the entry gate -----
    def ready(self):
        return (not self.halted), ("readback HALT: " + (self.reason or "")) if self.halted else ""

    def slip_halt(self, reason):
        """SLIP-class halt: execution slippage / miss-rate breached tolerance (slip_tripwire).

        Latches entries CLOSED via the SAME `halted` gate the entry path already checks
        (auto_live `_entry_ready`), and alerts ONCE.  NEVER flattens — bad fills mean the ENTRY
        assumption is leaking, not that the open position is wrong, so existing brackets stay on
        the book (mirrors READ-class discipline, T0-3 audit).  Clears only via operator reset()
        (/resume).  Idempotent: a second call while already halted is a no-op."""
        if self.halted:
            return
        self.halted = True
        self.reason = "SLIP-HALT: " + str(reason)
        self._alert(f"⚠ SLIP-HALT — {self.account}\n{reason}\n"
                    "Entries FROZEN (no flatten — brackets live, position untouched). /resume to clear.")

    # ----- one reconciliation pass -----
    def poll(self, broker):
        try:
            net = broker.net_by_account()
            bal = broker.balance(self.account)
            self._read_fail = 0
        except Exception as e:                                    # noqa: BLE001 — fail closed, never raise
            # the read-fail COUNTER is its own persistence gate (don't double-apply grace).
            self._read_fail += 1
            if self._read_fail == 1:                              # first failure: tell the operator NOW
                self._alert(f"⚠ read-back: broker read FAILED ({type(e).__name__}) — "
                            f"halting entries at 3 consecutive fails. Check the TV broker panel.")
            if self._read_fail >= 3:
                conf = [("BROKER_READ_FAIL", BLACK,
                         f"{type(e).__name__}: {e} (x{self._read_fail})")]
                self._trigger(conf)
                self.last = conf
                return conf
            self.last = []
            return []                                             # 1-2 fails: ORANGE, not yet confirmed

        bpos = int(net.get(self.account, 0))
        found = []
        if self.expected == 0 and bpos != 0:
            found.append(("ORPHAN_POSITION", BLACK, f"broker net={bpos}, bot expects FLAT"))
        elif self.expected != 0 and bpos == 0:
            found.append(("MISSING_POSITION", ORANGE, f"bot expects {self.expected}, broker FLAT"))
        elif self.expected != 0 and bpos != 0 and (bpos > 0) != (self.expected > 0):
            found.append(("DIRECTION_MISMATCH", BLACK, f"broker net={bpos}, expected {self.expected}"))

        if self.floor is not None:
            if bal is None:
                # fail CLOSED: with a floor armed, an unreadable balance must not silently disable
                # the floor check (2026-07-02 audit S2/N — comma-only equity render -> None -> inert).
                self._bal_none += 1
                if self._bal_none == 1:
                    self._alert("⚠ read-back: balance unreadable (floor check degraded) — "
                                f"fails closed after {BAL_NONE_CONFIRM} consecutive polls.")
                if self._bal_none >= BAL_NONE_CONFIRM:
                    found.append(("BALANCE_UNREADABLE", BLACK,
                                  f"balance None x{self._bal_none} with floor armed"))
            else:
                self._bal_none = 0
                if bal <= self.floor:
                    found.append(("BALANCE_FLOOR", BLACK, f"equity {bal:.2f} <= floor {self.floor:.2f}"))

        # ---- positive fill confirmation: first poll where broker position matches expected ----
        # Journals FILL_CONFIRMED once per entry episode (re-armed by on_entry). No behavior change.
        if (self.expected != 0 and bpos != 0
                and (bpos > 0) == (self.expected > 0)
                and not self._fill_confirmed):
            self._fill_confirmed = True
            if self.journal is not None:
                try:
                    self.journal.append("FILL_CONFIRMED", self.account,
                                        payload=dict(expected=self.expected, broker=bpos))
                except Exception:                             # noqa: BLE001 — logging never breaks safety
                    pass

        # ---- missing escalation: count consecutive polls; fire on_missing ONCE per episode ----
        # MISSING stays ORANGE (never halts). This only adds the callback — tier semantics unchanged.
        _is_missing = any(f[0] == "MISSING_POSITION" for f in found)
        if _is_missing:
            self._missing_consec += 1
            if (self._missing_consec >= self.missing_confirm
                    and not self._missing_fired
                    and self.on_missing is not None):
                self._missing_fired = True
                try:
                    self.on_missing(self.expected)
                except Exception:                             # noqa: BLE001 — callback never breaks safety
                    pass
        elif self._missing_consec > 0:                       # condition healed: re-arm for next episode
            self._missing_consec = 0
            self._missing_fired = False

        return self._apply(found)

    # ----- grace filtering + critical action -----
    def _apply(self, found):
        keys = set()
        confirmed = []
        for check, tier, detail in found:
            k = (check, tier)
            keys.add(k)
            self._seen[k] = self._seen.get(k, 0) + 1
            if self._seen[k] >= self.grace:
                confirmed.append((check, tier, detail))
        for k in list(self._seen):                                # healed -> reset counter
            if k not in keys:
                del self._seen[k]

        self.last = confirmed
        self._trigger(confirmed)
        return confirmed

    def _trigger(self, confirmed):
        """Halt + alert on any confirmed BLACK. Fire the critical callback (flatten) ONLY for
        MISMATCH-class BLACKs — READ-class means "can't see the broker", where a market flatten
        of a possibly-healthy position is the wrong reflex (halt + operator alert instead)."""
        crit = [c for c in confirmed if c[1] == BLACK]
        if not crit or self.halted:
            return
        self.halted = True
        self.reason = "; ".join(f"{c}({d})" for c, _, d in crit)
        mismatch = [c for c in crit if c[0] not in READ_FAIL_CHECKS]
        self._alert(f"☠ READ-BACK {'CRITICAL' if mismatch else 'HALT'} — {self.account}\n{self.reason}\n"
                    + ("FLATTEN sent + entries halted." if mismatch else
                       "Entries HALTED (no flatten — broker unreadable, position left on brackets). "
                       "Fix the TV broker panel, then /resume."))
        if self.journal is not None:
            try:
                self.journal.append("RECON_ALERT", self.account,
                                    payload=dict(reason=self.reason, source="readback_sentinel"))
            except Exception:                                     # noqa: BLE001 — logging must never break safety
                pass
        if self.on_critical is not None and mismatch:
            try:
                self.on_critical(self.reason)
            except Exception:                                     # noqa: BLE001
                pass
