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
                 on_critical=None, journal=None):
        self.account = str(account_id)
        self.floor = floor
        self.grace = grace
        self.on_critical = on_critical
        self.journal = journal
        self.expected = 0          # bot's belief: signed net qty (long>0, short<0, flat=0)
        self.halted = False
        self.reason = None
        self._seen = {}
        self._read_fail = 0
        self.last = []             # last confirmed discrepancies (for monitoring)

    # ----- the loop tells the sentinel what it BELIEVES it did -----
    def on_entry(self, side, qty):
        s = 1 if str(side).lower() in ("long", "buy") else -1
        self.expected += s * int(qty)

    def on_partial_or_exit(self, signed_delta):
        """Apply a known reduction/close (signed). For a full flat, prefer on_flat()."""
        self.expected += int(signed_delta)

    def on_flat(self):
        self.expected = 0

    # ----- monitoring hook for the entry gate -----
    def ready(self):
        return (not self.halted), ("readback HALT: " + (self.reason or "")) if self.halted else ""

    # ----- one reconciliation pass -----
    def poll(self, broker):
        try:
            net = broker.net_by_account()
            bal = broker.balance(self.account)
            self._read_fail = 0
        except Exception as e:                                    # noqa: BLE001 — fail closed, never raise
            # the read-fail COUNTER is its own persistence gate (don't double-apply grace).
            self._read_fail += 1
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

        if bal is not None and self.floor is not None and bal <= self.floor:
            found.append(("BALANCE_FLOOR", BLACK, f"equity {bal:.2f} <= floor {self.floor:.2f}"))

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
        """Halt + alert + fire the critical callback ONCE on any confirmed BLACK."""
        crit = [c for c in confirmed if c[1] == BLACK]
        if not crit or self.halted:
            return
        self.halted = True
        self.reason = "; ".join(f"{c}({d})" for c, _, d in crit)
        if self.journal is not None:
            try:
                self.journal.append("RECON_ALERT", self.account,
                                    payload=dict(reason=self.reason, source="readback_sentinel"))
            except Exception:                                     # noqa: BLE001 — logging must never break safety
                pass
        if self.on_critical is not None:
            try:
                self.on_critical(self.reason)
            except Exception:                                     # noqa: BLE001
                pass
