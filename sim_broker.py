"""B1 test-double broker — an in-memory, deterministic CME-style broker that
implements the SAME interfaces the live B1 path will: the recon `BrokerView`
(positions / working_orders / fills_since / account_state / health) AND the
flatten `BrokerActions` (cancel_all / close_position), PLUS the order-placement
surface the runner drives (place_oso / modify_order / cancel_order).

It exists so the ENTIRE B1 runner can be built and battery-tested OFFLINE,
with zero credentials, before the Tradovate verification spike (A3) is run.
When the real `TradovateBrokerView` adapter lands it is a drop-in for this:
same method signatures, same return shapes, same fail-LOUD contract.

Fail-loud contract (mirrors Part 2 of B1_DESIGN):
  - every snapshot read returns truthful data or RAISES — never partial silence,
    never an empty list to mean "I couldn't reach the server";
  - the place/modify/cancel HTTP response is ADVISORY (proves receipt, not state);
  - state is authoritative only via the snapshot reads.

OSO model (matches "children Suspended -> activate-on-fill"):
  place_oso creates a WORKING limit entry + a SUSPENDED stop + SUSPENDED target.
  On entry fill the stop+target become WORKING (the protective bracket appears in
  working_orders only once there is a position to protect — so a pre-fill OSO is
  never falsely "naked"). A stop/target fill closes the position and cancels its
  sibling; the closing fill carries closes_cl for the EXIT sweep.

Driving methods (tests/replay only — a real broker has no such hooks):
  fill_entry / partial_fill_entry / fill_stop / fill_target,
  reject_next_send, disconnect / reconnect.
"""


class BrokerError(RuntimeError):
    """Raised by every snapshot read while disconnected — never returns []."""


class SimBroker:
    def __init__(self, accounts, start_balance=50_000.0, contract="MNQ"):
        self.contract = contract
        self.acct_balance = {a: float(start_balance) for a in accounts}
        self._connected = True
        self._reject_next = None        # None | dict(reason=, not_handled=)
        self._oso_seq = 0
        self._fill_seq = 0
        # order rows keyed by broker_order_id
        # {bid: {account_id, cl_ord_id, leg, order_type, action, qty, px, status}}
        self.orders = {}
        self.fills = []                  # append-only list of fill dicts
        self.position = {a: 0 for a in accounts}   # net signed qty per account

    # ---------------- connection control (test harness) ----------------
    def disconnect(self):
        self._connected = False

    def reconnect(self):
        self._connected = True

    def reject_next_send(self, reason="risk", not_handled=False):
        self._reject_next = dict(reason=reason, not_handled=not_handled)

    def _guard(self):
        if not self._connected:
            raise BrokerError("broker unreachable")

    # ---------------- BrokerView: snapshot reads (authoritative) ----------------
    def positions(self):
        self._guard()
        return [dict(account_id=a, qty=q, contract=self.contract)
                for a, q in self.position.items() if q != 0]

    def working_orders(self):
        self._guard()
        out = []
        for bid, o in self.orders.items():
            if o["status"] != "Working":
                continue
            out.append(dict(account_id=o["account_id"], broker_order_id=bid,
                            cl_ord_id=o["cl_ord_id"], order_type=o["order_type"],
                            action=o["action"], qty=o["qty"], px=o["px"]))
        return out

    def fills_since(self, cursor=None):
        """List of fills with fill_id > cursor (None = all). Replays tolerated —
        recon/recovery dedupe by fill_id. Returns a LIST (matches B0 recon/recovery
        which iterate the return directly)."""
        self._guard()
        lo = -1 if cursor is None else int(cursor)
        return [dict(f) for f in self.fills if f["fill_id"] > lo]

    def account_state(self, account_id):
        self._guard()
        return dict(balance=self.acct_balance.get(account_id, 0.0))

    def health(self):
        if not self._connected:
            raise BrokerError("broker unreachable")
        return dict(auth_ok=True, last_roundtrip_ms=5, server_time_utc=None)

    # ---------------- BrokerActions: emergency flatten ----------------
    def cancel_all(self, account_id):
        self._guard()
        for o in self.orders.values():
            if o["account_id"] == account_id and o["status"] in ("Working", "Suspended"):
                o["status"] = "Cancelled"

    def close_position(self, account_id):
        self._guard()
        net = self.position.get(account_id, 0)
        if net == 0:
            return
        self._fill_seq += 1
        self.fills.append(dict(
            account_id=account_id, broker_order_id=f"FLAT-{self._fill_seq}",
            cl_ord_id=None, fill_id=self._fill_seq, qty=abs(net),
            px=0.0, ts_utc=None, leg="flatten", closes_cl=None))
        self.position[account_id] = 0

    # ---------------- order placement surface (runner drives) ----------------
    def place_oso(self, cl_ord_id, account_id, action, qty, entry_px, stop_px, target_px):
        """ADVISORY response. Raises while disconnected (-> runner records
        sent_unknown, NEVER resends). A scripted reject returns accepted=False."""
        self._guard()
        if self._reject_next is not None:
            rej = self._reject_next
            self._reject_next = None
            return dict(accepted=False, reason=rej["reason"],
                        not_handled=rej["not_handled"])
        self._oso_seq += 1
        g = self._oso_seq
        entry_bid, stop_bid, tgt_bid = f"E-{g}", f"S-{g}", f"T-{g}"
        opp = "Sell" if action == "Buy" else "Buy"
        self.orders[entry_bid] = dict(account_id=account_id, cl_ord_id=cl_ord_id,
                                      leg="entry", order_type="Limit", action=action,
                                      qty=qty, px=entry_px, status="Working")
        self.orders[stop_bid] = dict(account_id=account_id, cl_ord_id=cl_ord_id,
                                     leg="stop", order_type="Stop", action=opp,
                                     qty=qty, px=stop_px, status="Suspended")
        self.orders[tgt_bid] = dict(account_id=account_id, cl_ord_id=cl_ord_id,
                                    leg="target", order_type="Limit", action=opp,
                                    qty=qty, px=target_px, status="Suspended")
        return dict(accepted=True, broker_order_id=entry_bid,
                    legs=dict(entry=entry_bid, stop=stop_bid, target=tgt_bid))

    def modify_order(self, broker_order_id, qty):
        self._guard()
        o = self.orders.get(broker_order_id)
        if not o:
            return dict(accepted=False, reason="not_found")
        o["qty"] = qty
        return dict(accepted=True)

    def cancel_order(self, broker_order_id):
        self._guard()
        o = self.orders.get(broker_order_id)
        if o and o["status"] in ("Working", "Suspended"):
            o["status"] = "Cancelled"
        return dict(accepted=True)

    # ---------------- test/replay drivers (no real-broker analogue) ----------------
    def _leg(self, cl_ord_id, leg):
        for bid, o in self.orders.items():
            if o["cl_ord_id"] == cl_ord_id and o["leg"] == leg:
                return bid, o
        raise KeyError(f"no {leg} leg for {cl_ord_id}")

    def _record_fill(self, o, bid, qty, px, leg, closes_cl=None):
        self._fill_seq += 1
        self.fills.append(dict(
            account_id=o["account_id"], broker_order_id=bid, cl_ord_id=o["cl_ord_id"],
            fill_id=self._fill_seq, qty=qty, px=px, ts_utc=None,
            leg=leg, closes_cl=closes_cl))
        return self._fill_seq

    def _activate_bracket(self, cl_ord_id, qty):
        """On (any) entry fill the protective legs go WORKING, sized to filled qty."""
        for leg in ("stop", "target"):
            _bid, o = self._leg(cl_ord_id, leg)
            if o["status"] == "Suspended":
                o["status"] = "Working"
            o["qty"] = qty

    def fill_entry(self, cl_ord_id, px=None):
        bid, o = self._leg(cl_ord_id, "entry")
        o["status"] = "Filled"
        sign = 1 if o["action"] == "Buy" else -1
        self.position[o["account_id"]] += sign * o["qty"]
        self._record_fill(o, bid, o["qty"], px if px is not None else o["px"], "entry")
        self._activate_bracket(cl_ord_id, abs(self.position[o["account_id"]]))

    def partial_fill_entry(self, cl_ord_id, qty, px=None):
        bid, o = self._leg(cl_ord_id, "entry")
        sign = 1 if o["action"] == "Buy" else -1
        self.position[o["account_id"]] += sign * qty
        o["qty"] = max(o["qty"] - qty, 0)            # remaining resting qty
        if o["qty"] == 0:
            o["status"] = "Filled"
        self._record_fill(o, bid, qty, px if px is not None else o["px"], "entry")
        self._activate_bracket(cl_ord_id, abs(self.position[o["account_id"]]))

    def _close_via(self, cl_ord_id, leg):
        bid, o = self._leg(cl_ord_id, leg)
        acct = o["account_id"]
        net = self.position.get(acct, 0)
        qty = abs(net)
        o["status"] = "Filled"
        self._record_fill(o, bid, qty, o["px"], leg, closes_cl=cl_ord_id)
        self.position[acct] = 0
        # cancel the sibling protective leg (OCO)
        sib = "target" if leg == "stop" else "stop"
        try:
            _sbid, so = self._leg(cl_ord_id, sib)
            if so["status"] in ("Working", "Suspended"):
                so["status"] = "Cancelled"
        except KeyError:
            pass

    def fill_stop(self, cl_ord_id):
        self._close_via(cl_ord_id, "stop")

    def fill_target(self, cl_ord_id):
        self._close_via(cl_ord_id, "target")
