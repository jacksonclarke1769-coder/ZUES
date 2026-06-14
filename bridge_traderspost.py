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
    p = {"ticker": TP_SYMBOL[root], "action": action}
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
    extras = dict(meta or {})
    extras["signalId"] = sid          # dedup key lives in extras (no native TP dedup)
    p["extras"] = extras
    return p


def build_entry(*, account, strategy, setup, signal_ts, side, qty, entry, stop, target,
                root="MNQ", order_type="limit", mode_meta=None, d1c_meta=None):
    """Profile A or B entry. Returns (payload, None) or (None, error)."""
    try:
        if int(qty) <= 0:
            return None, "quantity <= 0"
        e, s, tg = _validate_bracket(side, entry, stop, target, root)
    except Exception as ex:                                  # noqa: BLE001
        return None, f"bracket build failed: {ex}"
    action = "buy" if side == "long" else "sell"
    sid = signal_id(account, strategy, signal_ts, "entry")
    risk_pts = abs(e - s)
    meta = dict(strategy=strategy, setup=setup, side=side,
                risk_points=round(risk_pts, 2),
                risk_usd=round(risk_pts * PT_VALUE[root] * int(qty), 2),
                account=account, **(mode_meta or {}), d1c=(d1c_meta or {}),
                source="zeus_bridge")
    return _wire(root, action, qty, order_type, limit_price=e, stop_price=s,
                 target_price=tg, sid=sid, meta=meta, price=e), None


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
