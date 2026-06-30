"""TradersPost-API read-back view — the Apex-legal read path (Tradovate API is banned on eval/funded).

Implements the SAME interface live_readback.ReadbackSentinel expects from TradovateBrokerView:
    net_by_account() -> {account_id: signed net qty}
    balance(account_id) -> float equity (or None)
…but sources TRUTH from the TradersPost REST API (api.traderspost.io) instead of Tradovate. TradersPost
sits between the bot and Tradovate and tracks every order's lifecycle + position, so a TradersPost API key
(NOT a broker key) lets the bot confirm fills, catch unfilled retest-limits (the 2026-06-30 phantom), and
detect orphan positions — all without touching the Tradovate API.

⚠️ STATUS: SKELETON. The exact TradersPost endpoints/paths + response shapes MUST be verified against the
TradersPost API docs (see reports/readback-traderspost-scope.md) before this is trusted. Until then,
build_readback() returns broker=None for this view and the live-requires-readback guard keeps the bot DOWN
(fail-closed). Filling in the two TODO calls + a key is the whole job.
"""
from __future__ import annotations
import os


class TradersPostError(RuntimeError):
    pass


class TradersPostBrokerView:
    """Read-only view over the TradersPost API. NEVER places orders (no write methods)."""

    BASE = os.environ.get("TRADERSPOST_API_BASE", "https://api.traderspost.io")

    def __init__(self, api_key=None, account_label=None, session=None):
        self.api_key = api_key or os.environ.get("TRADERSPOST_API_KEY")
        self.account_label = account_label          # e.g. "APEX-50K-EVAL-1" -> map to TP account id
        if not self.api_key:
            raise TradersPostError("no TRADERSPOST_API_KEY set")
        import requests                              # local import: keep the module import-safe w/o requests
        self._s = session or requests.Session()
        self._s.headers.update({"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"})

    def _get(self, path, **params):
        r = self._s.get(f"{self.BASE}{path}", params=params, timeout=8)
        if r.status_code != 200:
            raise TradersPostError(f"GET {path} -> {r.status_code}: {r.text[:200]}")
        return r.json()

    # ---- the interface the sentinel calls -------------------------------------------------
    def net_by_account(self):
        """{account_id: signed net qty}. TODO: confirm the TradersPost positions endpoint + field names.
        Likely shape: GET /v1/.../positions -> [{account, symbol, quantity, side}]. signed = +long / -short."""
        raise NotImplementedError("VERIFY TradersPost positions endpoint (scope doc) before enabling")
        # data = self._get("/v1/users/<uid>/brokers/<bid>/positions")
        # out = {}
        # for p in data.get("positions", []):
        #     acct = str(p["account"]); q = int(p["quantity"]); sgn = -1 if p["side"].lower()=="short" else 1
        #     out[acct] = out.get(acct, 0) + sgn*q
        # return out

    def balance(self, account_id):
        """Account equity, or None. TODO: confirm the TradersPost account/balance endpoint + field."""
        raise NotImplementedError("VERIFY TradersPost account/balance endpoint (scope doc) before enabling")
        # snap = self._get(f"/v1/.../accounts/{account_id}")
        # return float(snap.get("equity")) if snap.get("equity") is not None else None

    # ---- fill confirmation (the phantom-killer) -------------------------------------------
    def order_filled(self, signal_id):
        """Did the entry order for this ZEUS signalId actually FILL (vs cancel/reject/unfilled-limit)?
        This is the direct fix for the 2026-06-30 phantom: a retest-limit that 'Completed' (placed) but
        never filled. TODO: map TradersPost order/trade status -> {FILLED, CANCELED, REJECTED, WORKING}.
        Note: TP 'Completed' = order PLACED, not necessarily filled — must read the FILL/execution, not
        just the order status."""
        raise NotImplementedError("VERIFY TradersPost order/execution status endpoint (scope doc)")
