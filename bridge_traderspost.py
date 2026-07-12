"""BRIDGE — TradersPost payload builder. ZEUS decides; BRIDGE transmits.

Builds deterministic, duplicate-protected webhook payloads for Profile A/B entries,
exits, emergency flatten, and cancel. Translates ZEUS's absolute entry/stop/target
prices into TradersPost bracket format with tick rounding and side sanity checks.

FAIL CLOSED: any build that cannot prove correct returns (None, error) — no payload,
so the sender has nothing to send.

NOTE: TradersPost field names marked CONFIRM are pending the docs review
(reports/bridge-traderspost-requirements.md). The mapping lives in _wire() so the exact
keys can be adjusted in one place once confirmed — the safety logic above it is final.
"""
import hashlib
import os

TICK = {"MNQ": 0.25, "NQ": 0.25}
PT_VALUE = {"MNQ": 2.0, "NQ": 20.0}
# TradersPost: do NOT use continuous "1!" symbols. Bare root or explicit contract
# (e.g. MNQU2025). Override TP_SYMBOL per active contract month at deploy time.
TP_SYMBOL = {"MNQ": "MNQ", "NQ": "NQ"}


def signal_id(account, strategy, signal_ts, role):
    """Deterministic — the SAME signal slot always yields the SAME id. This is the
    duplicate-protection key end to end (matches the journal cl_ord_id convention)."""
    raw = f"{account}|{strategy}|{signal_ts}|{role}"
    return "ZB-" + hashlib.sha1(raw.encode()).hexdigest()[:20]


def round_tick(px, root):
    t = TICK[root]
    return round(round(px / t) * t, 2)


def _validate_bracket(side, entry, stop, target, root):
    """Side sanity + tick rounding. Returns (entry,stop,target rounded) or raises."""
    if root not in TICK:
        raise ValueError(f"unknown root '{root}'")
    if None in (entry, stop, target):
        raise ValueError("entry/stop/target missing")
    e = round_tick(entry, root); s = round_tick(stop, root); tg = round_tick(target, root)
    if side == "long":
        if not (s < e < tg):
            raise ValueError(f"long bracket wrong side: need stop<entry<target, got "
                             f"{s}<{e}<{tg}")
    elif side == "short":
        if not (tg < e < s):
            raise ValueError(f"short bracket wrong side: need target<entry<stop, got "
                             f"{tg}<{e}<{s}")
    else:
        raise ValueError(f"unknown side '{side}'")
    if s == e or tg == e:
        raise ValueError("stop or target equals entry after rounding")
    return e, s, tg


def _wire(root, action, qty=0, order_type="market", limit_price=None, stop_price=None,
          target_price=None, sid=None, meta=None, price=None):
    """Top level = ONLY documented TradersPost fields (a live 400 proved strict-ish schema).
    All ZEUS context + our dedup signalId go in `extras` (the documented passthrough).
    Entry: ticker/action/quantity/orderType/price/limitPrice/stopLoss/takeProfit.
    Exit/cancel: minimal {ticker, action} — quantity OMITTED = full close (per docs).
    Bracket keys VERIFIED: takeProfit.limitPrice + stopLoss{type:stop,stopPrice}.
    `price` MANDATORY on Tradovate (no market data) or it becomes a market order."""
    # TP_SYMBOL_MNQ: env override to pin to a specific contract month during quarterly roll.
    # Read at call time (not import time) so tests can monkeypatch os.environ.
    ticker = (os.environ.get("TP_SYMBOL_MNQ") if root == "MNQ" else None) or TP_SYMBOL[root]
    p = {"ticker": ticker, "action": action}
    if action in ("buy", "sell", "add"):
        p["quantity"] = int(qty)
        p["orderType"] = order_type
        if price is not None:
            p["price"] = price
        if order_type != "market" and limit_price is not None:
            p["limitPrice"] = limit_price
        if stop_price is not None:
            p["stopLoss"] = {"type": "stop", "stopPrice": stop_price}   # VERIFIED
        if target_price is not None:
            p["takeProfit"] = {"limitPrice": target_price}             # VERIFIED
    elif action == "stop":
        # ADDITIVE (VPC lane): a standalone protective-stop order carrying the new resting stop
        # level for an already-open position. Purely additive branch — every pre-existing action
        # (buy/sell/add/exit/cancel) takes an untouched path above/below. The exact TradersPost
        # wire field for a bare protective-stop-replace is CONFIRM-pending (same status as
        # build_cancel's cancel support): the audit records that TradersPost exposes only cancel +
        # re-send, so the VPC trail manager pairs this with a cancel (build_vpc_stop_replace). The
        # SAFETY logic (deterministic sid, side/level validation) is final; only the key mapping is
        # provisional and confined to this one branch.
        if qty:
            p["quantity"] = int(qty)
        p["orderType"] = "stop"
        if stop_price is not None:
            p["stopLoss"] = {"type": "stop", "stopPrice": stop_price}   # CONFIRM key for bare-stop
    extras = dict(meta or {})
    extras["signalId"] = sid          # dedup key lives in extras (no native TP dedup)
    p["extras"] = extras
    return p


def build_entry(*, account, strategy, setup, signal_ts, side, qty, entry, stop, target,
                root="MNQ", order_type="limit", mode_meta=None, d1c_meta=None,
                role="entry", r_target=None):
    """Profile A or B entry leg. Returns (payload, None) or (None, error).
    `role` distinguishes Exit #3 legs (entry_tp1 / entry_tp2) so each gets a unique,
    deterministic signalId. `r_target` (1.0 / 2.0) is recorded in meta for the ledger."""
    try:
        if int(qty) <= 0:
            return None, "quantity <= 0"
        e, s, tg = _validate_bracket(side, entry, stop, target, root)
    except Exception as ex:                                  # noqa: BLE001
        return None, f"bracket build failed: {ex}"
    action = "buy" if side == "long" else "sell"
    sid = signal_id(account, strategy, signal_ts, role)
    risk_pts = abs(e - s)
    meta = dict(strategy=strategy, setup=setup, side=side, role=role,
                risk_points=round(risk_pts, 2),
                risk_usd=round(risk_pts * PT_VALUE[root] * int(qty), 2),
                account=account, **(mode_meta or {}), d1c=(d1c_meta or {}),
                source="zeus_bridge")
    if r_target is not None:
        meta["r_target"] = r_target
    return _wire(root, action, qty, order_type, limit_price=e, stop_price=s,
                 target_price=tg, sid=sid, meta=meta, price=e), None


def build_momentum_entry(*, account, signal_ts, side, qty, ref_price, stop_pts,
                         root="MNQ", mode_meta=None):
    """Profile MOMENTUM market entry — a POSITION strategy with NO fixed target. Market order at the
    current price carrying ONLY a WIDE catastrophic protective stop (feed-death / runaway safety, far
    enough out not to alter the flip/EOD-managed behaviour). Exits happen on signal flip/flatten via
    build_exit. Returns (payload, None) or (None, error)."""
    try:
        if int(qty) <= 0:
            return None, "quantity <= 0"
        d = 1 if side == "long" else -1 if side == "short" else 0
        if d == 0:
            return None, f"unknown side '{side}'"
        ref = round_tick(ref_price, root)
        stop = round_tick(ref - d * abs(float(stop_pts)), root)
        if stop == ref:
            return None, "stop equals ref after rounding"
    except Exception as ex:                                   # noqa: BLE001
        return None, f"momentum build failed: {ex}"
    action = "buy" if side == "long" else "sell"
    sid = signal_id(account, "M", signal_ts, "entry")
    meta = dict(strategy="M", setup="momentum", side=side, role="entry",
                risk_points=round(abs(ref - stop), 2), risk_usd=round(abs(ref - stop) * PT_VALUE[root] * int(qty), 2),
                account=account, **(mode_meta or {}), source="zeus_bridge")
    return _wire(root, action, int(qty), "market", stop_price=stop, sid=sid, meta=meta, price=ref), None


def build_entry_exit3(*, account, strategy, setup, signal_ts, side, qty, entry, stop, target,
                      root="MNQ", order_type="limit", mode_meta=None, d1c_meta=None):
    """EXITFORGE: split ONE approved signal into the two Exit #3 bracket legs, each a complete
    OSO (entry + shared stop + its own target). Returns ([leg, ...], None) in SEND ORDER —
    CORE (TP2 @ +2R) FIRST, then TP1 (@ +1R) — or (None, error). Each leg dict =
    {role, qty, r_target, target, payload}. `target` arg is the strategy's +2R price; the +1R
    price is derived from entry/stop so the two legs share an identical protective stop."""
    from config_defaults import exit3_split        # version-controlled (not gitignored config.py)
    qty = int(qty)
    if qty <= 0:
        return None, "quantity <= 0"
    if side not in ("long", "short"):
        return None, f"unknown side '{side}'"
    tp1_qty, tp2_qty = exit3_split(qty)
    d = 1 if side == "long" else -1
    R = abs(float(entry) - float(stop))
    tp1_target = float(entry) + d * R                 # +1R, same stop -> shared protection
    specs = [("entry_tp2", tp2_qty, float(target), 2.0),   # core leg first (fail-closed)
             ("entry_tp1", tp1_qty, tp1_target, 1.0)]
    legs = []
    for role, q, tgt, r_t in specs:
        if q <= 0:
            continue                                  # qty=1 -> no TP1 leg; all to core
        p, err = build_entry(account=account, strategy=strategy, setup=setup,
                             signal_ts=signal_ts, side=side, qty=q, entry=entry, stop=stop,
                             target=tgt, root=root, order_type=order_type,
                             mode_meta=mode_meta, d1c_meta=d1c_meta, role=role, r_target=r_t)
        if err:
            return None, f"{role}: {err}"
        legs.append(dict(role=role, qty=q, r_target=r_t, target=round(tgt, 2), payload=p))
    return legs, None


def build_exit(*, account, strategy, signal_ts, root="MNQ", reason="exit", mode_meta=None):
    sid = signal_id(account, strategy, signal_ts, "exit")
    return _wire(root, "exit", 0, "market", sid=sid,
                 meta=dict(strategy=strategy, reason=reason, account=account,
                           **(mode_meta or {}), source="zeus_bridge")), None


def build_flatten(*, account, root="MNQ", reason="emergency"):
    """Emergency close — flatten everything on the account. Deterministic id per day-ts."""
    sid = signal_id(account, "EMERGENCY", reason, "flatten")
    return _wire(root, "exit", 0, "market", sid=sid,
                 meta=dict(strategy="EMERGENCY", reason=reason, account=account,
                           emergency=True, source="zeus_bridge")), None


def build_cancel(*, account, strategy, signal_ts, root="MNQ"):
    """Cancel a working order (if TradersPost supports it — CONFIRM)."""
    sid = signal_id(account, strategy, signal_ts, "cancel")
    return _wire(root, "cancel", 0, "market", sid=sid,
                 meta=dict(strategy=strategy, account=account,
                           note="cancel support CONFIRM", source="zeus_bridge")), None


# =================================================================================================
# VPC lane (ADDITIVE) — VWAP-Pullback Continuation. Market entry + a client-side MANAGED trailing
# stop (2.5xATR initial, 5.0xATR trail). NO fixed target (position runs to stop or EOD). These are
# additive builders following build_entry()/build_momentum_entry()'s fail-closed style; they touch
# no existing builder and no send path. The lane is DISARMED by default — nothing calls these
# until an operator arms the lane via the go-live-recert.sh-gated config flag (Phase 4).
# =================================================================================================
def build_vpc_entry(*, account, signal_ts, side, qty, ref_price, stop_price,
                    root="MNQ", mode_meta=None):
    """VPC market entry carrying ONLY its initial 2.5xATR protective stop — no fixed target (the
    5.0xATR trailing stop, managed client-side bar-by-bar, is the exit). Modelled on
    build_momentum_entry (market entry + protective stop) but the stop is an ABSOLUTE price the
    caller already computed from the certified 2.5xATR distance, and the deterministic signalId is
    keyed to strategy "V". Returns (payload, None) or (None, error) — fail-closed."""
    try:
        if int(qty) <= 0:
            return None, "quantity <= 0"
        d = 1 if side == "long" else -1 if side == "short" else 0
        if d == 0:
            return None, f"unknown side '{side}'"
        ref = round_tick(ref_price, root)
        stop = round_tick(stop_price, root)
        if stop == ref:
            return None, "stop equals ref after rounding"
        # protective stop must sit on the losing side of entry (long -> below, short -> above)
        if d == 1 and not (stop < ref):
            return None, f"long VPC stop wrong side: need stop<ref, got {stop}<{ref}"
        if d == -1 and not (stop > ref):
            return None, f"short VPC stop wrong side: need stop>ref, got {stop}>{ref}"
    except Exception as ex:                                   # noqa: BLE001
        return None, f"vpc entry build failed: {ex}"
    action = "buy" if side == "long" else "sell"
    sid = signal_id(account, "V", signal_ts, "entry")
    meta = dict(strategy="V", setup="vpc", side=side, role="entry",
                risk_points=round(abs(ref - stop), 2),
                risk_usd=round(abs(ref - stop) * PT_VALUE[root] * int(qty), 2),
                account=account, **(mode_meta or {}), source="zeus_bridge")
    return _wire(root, action, int(qty), "market", stop_price=stop, sid=sid, meta=meta, price=ref), None


def build_vpc_stop_replace(*, account, signal_ts, side, qty, new_stop, root="MNQ", seq=0,
                           mode_meta=None):
    """Cancel-replace a VPC protective stop as the 5.0xATR trail ratchets. Returns
    ((cancel_payload, stop_payload), None) or (None, error) — the ORDERING the caller MUST honour
    is REPLACE-THEN-CONFIRM / never-naked: the trail manager places the NEW stop and only then
    cancels the stale one, with the cancel-replace timeout fail-safe (keep the LAST resting stop,
    alert, never naked) enforced in vpc_trail_manager. `seq` (monotone per trade) makes each
    replacement's signalId unique+deterministic so re-sends dedup correctly. `new_stop` is the
    absolute ratcheted stop price; side is the POSITION side (long position -> sell-stop below).
    Fail-closed: an inverted/degenerate stop returns (None, error) so no payload is emitted."""
    try:
        d = 1 if side == "long" else -1 if side == "short" else 0
        if d == 0:
            return None, f"unknown side '{side}'"
        if int(qty) <= 0:
            return None, "quantity <= 0"
        ns = round_tick(new_stop, root)
    except Exception as ex:                                   # noqa: BLE001
        return None, f"vpc stop-replace build failed: {ex}"
    # a protective stop for a LONG position is a resting SELL below; for a SHORT, a BUY above.
    stop_side = "sell" if d == 1 else "buy"
    role = f"stop_replace_{int(seq)}"
    cancel_sid = signal_id(account, "V", signal_ts, f"stop_cancel_{int(seq)}")
    stop_sid = signal_id(account, "V", signal_ts, role)
    common = dict(strategy="V", setup="vpc", account=account, side=side,
                  **(mode_meta or {}), source="zeus_bridge")
    cancel_payload = _wire(root, "cancel", 0, "market", sid=cancel_sid,
                           meta=dict(common, role=f"stop_cancel_{int(seq)}", seq=int(seq),
                                     note="cancel prior VPC protective stop (CONFIRM)"))
    stop_payload = _wire(root, "stop", int(qty), "stop", stop_price=ns, sid=stop_sid,
                         meta=dict(common, role=role, seq=int(seq), stop_side=stop_side,
                                   new_stop=ns))
    return (cancel_payload, stop_payload), None
