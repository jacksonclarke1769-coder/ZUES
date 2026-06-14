"""
Tradovate API client — REST auth + contract resolve + bar history + order/bracket
placement + flatten/positions. WebSocket helpers for live quotes/bars.

Designed to run in three modes:
  * paper=True  -> never sends real orders; fills simulated by the bot (works w/o key)
  * connected, paper=False -> places real OSO brackets on your Tradovate account
Auth uses the appId/cid/secret + user/password OAuth flow (accesstokenrequest).
Docs: https://api.tradovate.com/  (endpoints: /auth/accesstokenrequest, /contract/find,
/md/getChart via WS, /order/placeOSO, /order/liquidatePosition, /position/list)
"""
import time, json, requests

# HARD live-order gate (default OFF). Every real-order send (place_bracket / place_market /
# flatten / two-leg live path) requires BOTH this module constant AND the per-instance switch
# derived from config.SAFETY (enabled=True, paper=False). Default state = no order can be sent.
LIVE_ORDERS_ENABLED = False

class TradovateError(RuntimeError):
    pass

class TradovateClient:
    def __init__(self, tcfg, hosts, safety=None):
        self.cfg = tcfg
        self.host = hosts[tcfg["env"]]
        self.rest = self.host["rest"]
        self.token = None
        self.md_token = None
        self.token_exp = 0
        self.account_id = None
        self.account_spec = tcfg.get("account_spec")
        self.s = requests.Session()
        # operator gate: live orders require SAFETY.enabled=True AND SAFETY.paper=False.
        # No safety passed -> live orders impossible (the safe default for data-only use).
        self.live_orders_ok = bool(safety and safety.get("enabled") and not safety.get("paper", True))

    def _guard_live(self):
        """Raise unless live orders are explicitly enabled at BOTH levels (code constant +
        operator SAFETY switches). Called first inside every real-order method so an order can
        never be sent by accident — including from the legacy single-target/market/flatten paths."""
        if not (LIVE_ORDERS_ENABLED and self.live_orders_ok):
            raise TradovateError(
                "live order placement is DISABLED — set tradovate_client.LIVE_ORDERS_ENABLED=True and "
                "construct TradovateClient(..., safety=config.SAFETY) with SAFETY.enabled=True, paper=False. "
                "Paper-test first.")

    # ---------------- auth ----------------
    def authenticate(self):
        body = dict(name=self.cfg["name"], password=self.cfg["password"],
                    appId=self.cfg["app_id"], appVersion=self.cfg["app_version"],
                    cid=self.cfg["cid"], sec=self.cfg["sec"], deviceId=self.cfg["device_id"])
        r = self.s.post(f"{self.rest}/auth/accesstokenrequest", json=body, timeout=20)
        d = r.json()
        if "accessToken" not in d:
            raise TradovateError(f"auth failed: {d.get('errorText', d)}")
        self.token = d["accessToken"]; self.md_token = d.get("mdAccessToken")
        self.token_exp = time.time() + 60*60
        self.s.headers.update({"Authorization": f"Bearer {self.token}"})
        self._resolve_account()
        return d

    def _resolve_account(self):
        """VULCAN P11: account selection is EXPLICIT or it is an error. No silent
        first-account fallback — with multiple funded accounts on one login, guessing
        is how the wrong account gets traded."""
        spec = self.account_spec
        if not spec or str(spec).startswith("YOUR_"):
            raise TradovateError(
                "account_spec is required (explicit account name or id in config.TRADOVATE) "
                "— refusing to guess among the login's accounts")
        accts = self._get("/account/list")
        for a in accts:
            if a.get("name") == spec or str(a.get("id")) == str(spec):
                self.account_id = a["id"]; return
        raise TradovateError(
            f"account_spec {spec!r} not found among {len(accts)} accounts on this login "
            f"({[a.get('name') for a in accts][:8]}) — refusing first-account fallback")

    def _ensure(self):
        if not self.token or time.time() > self.token_exp - 120:
            self.authenticate()

    def _get(self, path, **params):
        self._ensure()
        r = self.s.get(f"{self.rest}{path}", params=params, timeout=20)
        return r.json()

    def _post(self, path, body):
        self._ensure()
        r = self.s.post(f"{self.rest}{path}", json=body, timeout=20)
        return r.json()

    # ---------------- contract ----------------
    def resolve_front_month(self, root):
        """Return the active contract (e.g. NQM6) dict for a root symbol."""
        res = self._get("/contract/suggest", t=root, l=10)
        # pick the nearest non-expired outright future
        futs = [c for c in res if c.get("name","").startswith(root)]
        return futs[0] if futs else (res[0] if res else None)

    # ---------------- market data (history) ----------------
    def get_bars(self, contract_id, unit="MinuteBar", size=5, count=400):
        """
        Fetch recent bars. Tradovate serves chart data over WS (md/getChart). For a simple
        REST-style pull we use the chart endpoint; if unavailable, the bot falls back to its
        local CSV buffer. Returns list of {timestamp,open,high,low,close,volume}.
        """
        body = dict(symbol=contract_id,
                    chartDescription=dict(underlyingType=unit, elementSize=size,
                                          elementSizeUnit="UnderlyingUnits"),
                    timeRange=dict(asMuchAsElements=count))
        try:
            d = self._post("/md/getChart", body)
            bars = d.get("bars") or d.get("charts", [{}])[0].get("bars", [])
            return bars
        except Exception as e:
            raise TradovateError(f"get_bars failed ({e}); use local buffer fallback")

    # ---------------- orders ----------------
    def place_bracket(self, contract_id, action, qty, stop_px, target_px=None):
        """
        OSO bracket: market entry + protective stop (+ optional target).
        action: 'Buy'|'Sell'. Returns the placeOSO response.
        """
        self._guard_live()
        entry = dict(accountId=self.account_id, action=action, symbol=contract_id,
                     orderQty=qty, orderType="Market", isAutomated=True)
        brackets = [dict(action=("Sell" if action=="Buy" else "Buy"), orderType="Stop",
                         stopPrice=round(stop_px*4)/4, orderQty=qty)]
        if target_px is not None:
            brackets.append(dict(action=("Sell" if action=="Buy" else "Buy"), orderType="Limit",
                                 price=round(target_px*4)/4, orderQty=qty))
        body = dict(entryVersion=entry, bracket1=brackets[0],
                    **({"bracket2": brackets[1]} if len(brackets) > 1 else {}))
        return self._post("/order/placeOSO", body)

    def place_bracket_two_targets(self, contract_id, action, qty, entry_px, stop_px,
                                  tp1_px=None, tp2_px=None, tick=0.25, dry_run=True,
                                  bracket_id=None):
        """Profile A v2 Exit #3 bracket: LIMIT entry + protective STOP (full qty) +
        TP1 (50% @ +1R) + TP2 (remaining 50% @ +2R), with the stop quantity reducing as
        targets fill and full cancellation when flat.

        Returns a `TwoLegBracket` state machine. dry_run=True (default) NEVER contacts the
        broker — it only records order INTENTS in `.actions` and exposes `.working_orders()`.
        The live send path is intentionally disabled (raises) until paper-tested, so this
        function cannot place real orders. The single-target `place_bracket()` is unchanged."""
        b = TwoLegBracket(bracket_id or f"PA-{contract_id}", action, qty, entry_px, stop_px,
                          tp1_px=tp1_px, tp2_px=tp2_px, tick=tick, contract_id=contract_id)
        b.start()
        if not dry_run:
            self._guard_live()   # blocked unless explicitly enabled at both levels
            # LIVE PATH deliberately disabled until paper-tested; the test suite never reaches here.
            raise NotImplementedError("live two-leg bracket sending is disabled — paper-test via dry_run first")
        return b

    def place_market(self, contract_id, action, qty):
        self._guard_live()
        body = dict(accountId=self.account_id, action=action, symbol=contract_id,
                    orderQty=qty, orderType="Market", isAutomated=True)
        return self._post("/order/placeorder", body)

    def flatten(self, contract_id):
        self._guard_live()
        body = dict(accountId=self.account_id, symbol=contract_id, admin=False)
        return self._post("/order/liquidatePosition", body)

    def positions(self):
        return self._get("/position/list")

    def account_snapshot(self):
        """cashBalance + open P&L if available."""
        try:
            cash = self._get("/cashBalance/getcashbalancesnapshot", accountId=self.account_id)
            return cash
        except Exception:
            return {}


def _round_tick(px, tick=0.25):
    return round(round(px / tick) * tick, 4)


class TwoLegBracket:
    """Network-free state machine for Profile A v2's Exit #3 two-leg bracket.

    Legs: ENTRY (limit) · STOP (full position) · TP1 (50% @ +1R) · TP2 (50% @ +2R).
    It emits order INTENTS (PLACE / MODIFY / CANCEL) into `self.actions`; it never sends
    anything itself, so it is fully testable and broker-agnostic. A driver (live client
    or the simulation test) places the intents and reports back via `on_fill()`.

    Core invariant, re-established after every fill event:
        working STOP qty  == current open position
        TP1/TP2 work down their allocation; when flat, everything is cancelled.
    This single rule makes every case safe (TP1→TP2, TP1→stop, stop-first, partial
    entry, partial leg fills) with no naked or over-hedged position, ever.
    Duplicate orders are prevented by stable per-leg ids (`{bracket_id}-ROLE`) and by
    only PLACING a leg that is not already working.
    """

    ROLES = ("ENTRY", "STOP", "TP1", "TP2")

    def __init__(self, bracket_id, action, qty, entry_px, stop_px,
                 tp1_px=None, tp2_px=None, tick=0.25, contract_id=None):
        assert action in ("Buy", "Sell"), "action must be Buy (long) or Sell (short)"
        assert qty >= 1, "qty must be >= 1"
        self.bid = bracket_id
        self.contract_id = contract_id
        self.action = action                       # entry side
        self.exit_action = "Sell" if action == "Buy" else "Buy"
        self.dirn = 1 if action == "Buy" else -1
        self.qty = int(qty)
        self.tick = tick
        self.entry_px = _round_tick(entry_px, tick)
        self.stop_px = _round_tick(stop_px, tick)
        R = abs(self.entry_px - self.stop_px)
        self.tp1_px = _round_tick(tp1_px if tp1_px is not None else self.entry_px + self.dirn * R, tick)
        self.tp2_px = _round_tick(tp2_px if tp2_px is not None else self.entry_px + self.dirn * 2 * R, tick)
        # cumulative fills
        self.entry_filled = 0
        self.tp1_filled = 0
        self.tp2_filled = 0
        self.stop_filled = 0
        self.state = "PENDING_ENTRY"
        self.closed = False
        # role -> dict(id, type, side, qty, price, working, filled)
        self.orders = {}
        self.actions = []                          # intent log (the only output)

    # ---------- introspection ----------
    def open_pos(self):
        return self.entry_filled - self.tp1_filled - self.tp2_filled - self.stop_filled

    def working_orders(self):
        return {r: o for r, o in self.orders.items() if o.get("working")}

    def snapshot(self):
        """Persistable state for crash/restart recovery."""
        return dict(bid=self.bid, action=self.action, qty=self.qty, contract_id=self.contract_id,
                    entry_px=self.entry_px, stop_px=self.stop_px, tp1_px=self.tp1_px, tp2_px=self.tp2_px,
                    tick=self.tick, entry_filled=self.entry_filled, tp1_filled=self.tp1_filled,
                    tp2_filled=self.tp2_filled, stop_filled=self.stop_filled, state=self.state,
                    closed=self.closed)

    @classmethod
    def from_snapshot(cls, s):
        b = cls(s["bid"], s["action"], s["qty"], s["entry_px"], s["stop_px"],
                tp1_px=s["tp1_px"], tp2_px=s["tp2_px"], tick=s["tick"], contract_id=s["contract_id"])
        b.entry_filled = s["entry_filled"]; b.tp1_filled = s["tp1_filled"]
        b.tp2_filled = s["tp2_filled"]; b.stop_filled = s["stop_filled"]
        b.state = s["state"]; b.closed = s["closed"]
        return b

    # ---------- intent emission (with dedup) ----------
    def _emit(self, op, role, otype, side, qty, price):
        o = self.orders.get(role)
        if op == "PLACE":
            if o and o.get("working"):
                return                              # already working -> no duplicate
            self.orders[role] = dict(id=f"{self.bid}-{role}", type=otype, side=side,
                                     qty=qty, price=price, working=True, filled=0)
        elif op == "MODIFY":
            if not (o and o.get("working")):
                return
            if o["qty"] == qty and o["price"] == price:
                return                              # nothing changed -> no spurious modify
            o["qty"] = qty; o["price"] = price
        elif op == "CANCEL":
            if not (o and o.get("working")):
                return
            o["working"] = False
        rec = self.orders[role]
        self.actions.append(dict(op=op, role=role, id=rec["id"], type=rec["type"],
                                 side=rec["side"], qty=rec["qty"], price=rec["price"],
                                 contract_id=self.contract_id))

    def _ensure(self, role, otype, side, qty, price):
        """Drive leg `role` toward (qty, price): place / modify / cancel as needed."""
        o = self.orders.get(role)
        if qty <= 0:
            if o and o.get("working"):
                self._emit("CANCEL", role, otype, side, 0, price)
            return
        if o and o.get("working"):
            self._emit("MODIFY", role, otype, side, qty, price)
        else:
            self._emit("PLACE", role, otype, side, qty, price)

    # ---------- lifecycle ----------
    def start(self):
        """Place the resting LIMIT entry (idempotent)."""
        if self.closed:
            return
        self._ensure("ENTRY", "Limit", self.action, self.qty, self.entry_px)

    def cancel_entry(self):
        """Cancel an unfilled resting entry (e.g. window expired). No-op once any fill."""
        o = self.orders.get("ENTRY")
        if o and o.get("working") and self.entry_filled == 0:
            self._emit("CANCEL", "ENTRY", o["type"], o["side"], 0, o["price"])
            self.state = "CANCELLED"; self.closed = True

    def on_fill(self, role, qty):
        """Report a (possibly partial) fill of a leg. role in ENTRY/STOP/TP1/TP2."""
        assert role in self.ROLES
        if qty <= 0 or self.closed:
            return
        if role == "ENTRY":
            self.entry_filled += qty
            o = self.orders.get("ENTRY")
            if o:
                o["filled"] += qty
                if o["filled"] >= self.qty:
                    o["working"] = False            # fully filled -> consumed at broker
        elif role == "TP1":
            self.tp1_filled += qty
            self._mark_filled("TP1", qty)
        elif role == "TP2":
            self.tp2_filled += qty
            self._mark_filled("TP2", qty)
        elif role == "STOP":
            self.stop_filled += qty
            self._mark_filled("STOP", qty)
        self._reconcile()

    def _mark_filled(self, role, qty):
        o = self.orders.get(role)
        if o:
            o["filled"] += qty
            if o["filled"] >= o["qty"]:
                o["working"] = False                # fully filled -> gone at broker

    def _reconcile(self):
        """Re-establish the invariant after any event."""
        if self.closed or self.entry_filled <= 0:
            return
        op = self.open_pos()
        if op <= 0:                                  # flat -> cancel everything still working
            for r in ("ENTRY", "STOP", "TP1", "TP2"):
                o = self.orders.get(r)
                if o and o.get("working"):
                    self._emit("CANCEL", r, o["type"], o["side"], 0, o["price"])
            self.state = "CLOSED"; self.closed = True
            return
        self.state = "ACTIVE"
        tp1_alloc = self.entry_filled // 2
        tp2_alloc = self.entry_filled - tp1_alloc
        # STOP must always cover exactly the open position
        self._ensure("STOP", "Stop", self.exit_action, op, self.stop_px)
        # targets work down their remaining allocation
        self._ensure("TP1", "Limit", self.exit_action, max(0, tp1_alloc - self.tp1_filled), self.tp1_px)
        self._ensure("TP2", "Limit", self.exit_action, max(0, tp2_alloc - self.tp2_filled), self.tp2_px)

    # ---------- crash / disconnect recovery ----------
    def reconcile(self, working_ids, net_position):
        """After a restart: given the broker's set of still-working order ids and the
        actual net position, re-establish the invariant — re-place any protective leg
        that is missing, cancel any leg that should not be working, and FLATTEN if the
        broker position disagrees with our recorded open position (safety first).
        Idempotent: legs already working are not re-placed (no duplicates)."""
        working_ids = set(working_ids)
        # rebuild local 'working' flags from the broker truth
        for role in self.ROLES:
            oid = f"{self.bid}-{role}"
            o = self.orders.get(role)
            is_working = oid in working_ids
            if o:
                o["working"] = is_working
            elif is_working:
                # broker has a leg we don't model yet — register it as working
                self.orders[role] = dict(id=oid, type=("Limit" if role != "STOP" else "Stop"),
                                         side=(self.action if role == "ENTRY" else self.exit_action),
                                         qty=0, price=0, working=True, filled=0)
        if net_position != self.open_pos():
            self.actions.append(dict(op="FLATTEN", role="RECONCILE", id=f"{self.bid}-FLATTEN",
                                     reason=f"broker pos {net_position} != tracked {self.open_pos()}",
                                     contract_id=self.contract_id))
            return False                              # caller should flatten + alert
        if self.open_pos() <= 0:
            for r in ("ENTRY", "STOP", "TP1", "TP2"):
                o = self.orders.get(r)
                if o and o.get("working"):
                    self._emit("CANCEL", r, o["type"], o["side"], 0, o["price"])
            self.state = "CLOSED"; self.closed = True
            return True
        self._reconcile()                            # re-place missing protective legs, fix qtys
        return True
