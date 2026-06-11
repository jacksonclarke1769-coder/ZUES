"""B0 — Reconciliation Engine. BROKER IS ALWAYS TRUTH.

Runs every poll cycle (20s in-session). Diffs broker reality against ledger
expectation. NO SILENT CORRECTIONS — every confirmed discrepancy is appended to
the ledger as RECON_ALERT and returned to the caller (HEIMDALL tier in payload).

BrokerView interface (B1 implements via TradovateClient/TopstepX; tests use FakeBroker):
    positions()              -> [{account_id, qty(net signed), contract}]
    working_orders()         -> [{account_id, broker_order_id, order_type('Stop'|'Limit'|...),
                                  action('Buy'|'Sell'), qty, cl_ord_id(optional)}]
    fills_since(ts_utc|None) -> [{account_id, broker_order_id, qty, px, ts_utc,
                                  cl_ord_id(optional)}]
    account_state(account_id)-> {balance: float}

Transient-state grace: in-flight lifecycles (SEND/ACK age < GRACE_CYCLES polls) are
counted, and a discrepancy fires only when seen on consecutive cycles — partial fills
and bracket placement must not flap alarms (ODIN II Part 5 #2).
"""

GRACE_CYCLES = 2
BLACK, ORANGE = "BLACK", "ORANGE"


class Discrepancy(dict):
    def __init__(self, check, tier, account_id, detail):
        super().__init__(check=check, tier=tier, account_id=account_id, detail=detail)


class Reconciler:
    def __init__(self, journal, broker, grace_cycles=GRACE_CYCLES):
        self.j = journal
        self.b = broker
        self.grace = grace_cycles
        self._seen = {}          # discrepancy key -> consecutive cycle count
        self._fill_cursor = None

    # ---------------- the five checks ----------------

    def run(self, state_view=None, p3_params=None, record=True):
        """One reconciliation pass. Returns CONFIRMED discrepancies (grace applied).
        state_view: {account_id: {balance, floor, p3_braked}} — the bot's beliefs.
        p3_params: {account_id: {dd, on=0.40, off=0.60}} for CHECK 5."""
        found = []
        found += self._check1_positions()
        found += self._check2_naked()
        found += self._check3_unknown_fills()
        found += self._check4_unknown_orders()
        if state_view:
            found += self._check5_state(state_view, p3_params or {})
        confirmed = self._apply_grace(found)
        if record:
            for d in confirmed:
                self.j.append("RECON_ALERT", d["account_id"], payload=dict(d))
        return confirmed

    def _check1_positions(self):
        """Broker net position vs ledger open positions, per account."""
        led = {}
        for (acct, cl), p in self.j.open_positions().items():
            sgn = 1 if (p["side"] or "").lower() in ("buy", "long") else -1
            led[acct] = led.get(acct, 0) + sgn * p["qty"]
        brk = {}
        for p in self.b.positions():
            brk[p["account_id"]] = brk.get(p["account_id"], 0) + p["qty"]
        out = []
        for acct in set(led) | set(brk):
            l, k = led.get(acct, 0), brk.get(acct, 0)
            if l != k:
                out.append(Discrepancy("CHECK1_POSITION_MISMATCH", BLACK, acct,
                                       dict(ledger_net=l, broker_net=k)))
        return out

    def _check2_naked(self):
        """Every ledger-open position must have a broker-side protective Stop."""
        stops = {}
        for o in self.b.working_orders():
            if o["order_type"] == "Stop":
                stops[o["account_id"]] = stops.get(o["account_id"], 0) + o["qty"]
        out = []
        need = {}
        for (acct, cl), p in self.j.open_positions().items():
            need[acct] = need.get(acct, 0) + p["qty"]
        for acct, q in need.items():
            cover = stops.get(acct, 0)
            if cover < q:
                out.append(Discrepancy("CHECK2_NAKED_POSITION", BLACK, acct,
                                       dict(open_qty=q, stop_qty=cover)))
        return out

    def _check3_unknown_fills(self):
        """Every broker fill must trace to a ledger INTENT (via cl_ord_id or broker map)."""
        m = self.j.broker_map()
        out = []
        for f in self.b.fills_since(self._fill_cursor):
            cl = f.get("cl_ord_id") or m.get(str(f.get("broker_order_id")))
            if cl is None or not self.j.has_event(cl, "INTENT"):
                out.append(Discrepancy("CHECK3_UNKNOWN_FILL", BLACK, f["account_id"],
                                       dict(fill=f)))
        return out

    def _check4_unknown_orders(self):
        """Every broker working order must map to a live ledger lifecycle (ghost detector)."""
        m = self.j.broker_map()
        out = []
        for o in self.b.working_orders():
            cl = o.get("cl_ord_id") or m.get(str(o.get("broker_order_id")))
            ok = cl is not None and self.j.status(cl) in (
                "sent_unknown", "working", "partial", "open")
            if not ok:
                out.append(Discrepancy("CHECK4_UNKNOWN_ORDER", BLACK, o["account_id"],
                                       dict(order=o)))
        return out

    def _check5_state(self, state_view, p3_params):
        """Bot beliefs (balance / P3 state) vs broker account state."""
        out = []
        for acct, sv in state_view.items():
            st = self.b.account_state(acct)
            if st is None:
                continue
            tol = max(5.0, abs(sv.get("balance", 0)) * 1e-5)
            if abs(st["balance"] - sv.get("balance", st["balance"])) > tol:
                out.append(Discrepancy("CHECK5_STATE_DIVERGENCE", BLACK, acct,
                                       dict(bot_balance=sv.get("balance"),
                                            broker_balance=st["balance"])))
            p3 = p3_params.get(acct)
            if p3 and "floor" in sv:
                cushion = st["balance"] - sv["floor"]
                lo, hi = p3.get("on", 0.40) * p3["dd"], p3.get("off", 0.60) * p3["dd"]
                braked = bool(sv.get("p3_braked"))
                # hysteresis band [lo, hi) is legitimately ambiguous — only the
                # unambiguous zones can prove a mismatch
                if cushion < lo and not braked:
                    out.append(Discrepancy("CHECK5_P3_SHOULD_BE_ON", BLACK, acct,
                                           dict(cushion=cushion, on_threshold=lo)))
                elif cushion >= hi and braked:
                    out.append(Discrepancy("CHECK5_P3_SHOULD_BE_OFF", BLACK, acct,
                                           dict(cushion=cushion, off_threshold=hi)))
        return out

    # ---------------- grace / flap suppression ----------------

    def _apply_grace(self, found):
        keys = set()
        confirmed = []
        for d in found:
            k = (d["check"], d["account_id"], str(sorted(d["detail"].items()))[:120])
            keys.add(k)
            self._seen[k] = self._seen.get(k, 0) + 1
            if self._seen[k] >= self.grace:
                confirmed.append(d)
        for k in list(self._seen):
            if k not in keys:
                del self._seen[k]       # discrepancy healed — reset its counter
        return confirmed
