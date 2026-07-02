"""TradingView-panel read-back — the Apex-legal read path with NO API key of any kind.

The bot already reads the :9222 TradingView chart via CDP for market data. If the Apex/Tradovate account
is connected to that TradingView as a broker, its account manager shows live positions / orders / balance —
and we read them off the SAME CDP channel. This is platform screen-reading, not a Tradovate API key
(banned on eval/funded) and not the waitlisted TradersPost API.

Implements the interface live_readback.ReadbackSentinel expects:
    net_by_account() -> {account_id: signed net qty}
    balance(account_id) -> float equity (or None)
plus order_filled(signal_id) for the phantom-killer (did the entry actually FILL vs cancel/unfilled-limit).

SPLIT OF WORK:
  * Python parsing + fail-closed wiring + tests: DONE (this file, testable with mock CDP).
  * The JS that scrapes the panel (_PANEL_JS): the ONLY piece that needs the broker connected. It must
    return the CONTRACT below; until it does it returns {"__unconfigured__": true} and every read RAISES
    -> build_readback gets broker=None -> the live-requires-readback guard keeps the bot STOOD DOWN.
    Fill _PANEL_JS via tv_readback_inspect.py once you're logged in.

CONTRACT (_PANEL_JS must return exactly this shape):
    { "positions": [ {"account": <str>, "symbol": <str>, "qty": <int>, "side": "long"|"short"} , ... ],
      "balances":  [ {"account": <str>, "equity": <float>} , ... ],
      "orders":    [ {"account": <str>, "signal": <str|null>, "status": "filled"|"working"|"canceled"|"rejected"} , ... ] }
"""
from __future__ import annotations


class TradingViewReadbackUnconfigured(RuntimeError):
    """_PANEL_JS has not been pointed at the real account-manager DOM yet. Fail-closed until it is."""


# --- The ONLY piece that needs the live broker connection. TODO: replace via tv_readback_inspect.py. ---
# Must return the CONTRACT documented above. Until then it returns __unconfigured__ so every read RAISES
# (fail-closed). It is read-only JS — it never clicks, submits, or mutates the page.
_PANEL_JS = r"""
(() => {
  // Reads the connected TRADOVATE account-manager panel (data-name hooks confirmed via tv_readback_inspect).
  // READ-ONLY: no clicks/submits/mutations. Returns the CONTRACT above.
  const num = s => { const n = parseFloat(String(s||'').replace(/[^0-9.\-]/g,'')); return isFinite(n)?n:null; };
  const clean = s => (s||'').replace(/​/g,'').trim();
  const am = document.querySelector('[class*="accountManager"]');
  const amtxt = am ? (am.innerText||'') : '';
  const acctM = amtxt.match(/APEX[0-9]+/);
  const account = acctM ? acctM[0] : null;
  if (!am || !account) return { __unconfigured__: true };   // panel not present / no Tradovate account -> fail-closed
  let equity = null;
  const eqM = amtxt.match(/Equity\s*\$?([0-9][0-9,]*(?:\.[0-9]+)?)/i);   // decimals optional (audit N/S2)
  if (eqM) equity = num(eqM[1]);
  if (equity == null) { const bM = amtxt.match(/Balance\s*\$?([0-9][0-9,]*(?:\.[0-9]+)?)/i); if (bM) equity = num(bM[1]); }

  const cell = (row, name) => clean((row.querySelector('[data-name="'+name+'"]')||{}).innerText);
  const rowsOf = t => {
    const tab = document.querySelector('[data-name="'+t+'"]');
    return tab ? Array.from(tab.querySelectorAll('tr,[role="row"]')).filter(r =>
      r.querySelector('[data-name$="-column"]') && !r.querySelector('th,[role="columnheader"]')) : [];
  };
  const positions = [];
  for (const r of rowsOf('TRADOVATE.positions-table')) {
    const sym = cell(r,'symbol-column'); const q = num(cell(r,'qty-column'));
    if (!sym || !q) continue;
    const side = cell(r,'side-column');
    const avgPx = num(cell(r,'avg-price-column'));   // READ-ONLY: average fill price for this position
    positions.push({ account, symbol: sym, qty: Math.abs(q), side: (/sell|short/i.test(side)||q<0) ? 'short' : 'long', avg_price: avgPx });
  }
  const orders = [];
  for (const r of rowsOf('TRADOVATE.orders-table')) {
    const st = cell(r,'status-column'); if (!st) continue;
    orders.push({ account, signal: cell(r,'id-column')||null, status: st.toLowerCase() });
  }
  return { positions, balances: [{ account, equity }], orders };
})()
"""


class TradingViewBrokerView:
    """Read-only view over the :9222 TradingView account manager. NEVER places/cancels orders."""

    def __init__(self, cdp=None, account_label=None):
        self.account_label = account_label            # e.g. "APEX-50K-EVAL-1" (matches the panel's account id)
        if cdp is None:
            from tv_feed import _CDP
            cdp = _CDP()
        self.cdp = cdp

    # ---- raw panel read (the CDP + fail-closed boundary) ----
    def _panel(self):
        raw = self.cdp.eval(_PANEL_JS)
        if not isinstance(raw, dict) or raw.get("__unconfigured__"):
            raise TradingViewReadbackUnconfigured(
                "TradingView read-back not configured — connect the broker in the :9222 window and "
                "fill _PANEL_JS (run tv_readback_inspect.py). Refusing to guess positions.")
        return raw

    # ---- interface the sentinel calls (pure parsing of the CONTRACT — unit-tested) ----
    def net_by_account(self):
        out = {}
        for p in self._panel().get("positions", []):
            acct = str(p["account"]); q = int(p["qty"])
            sgn = -1 if str(p.get("side", "long")).lower() == "short" else 1
            out[acct] = out.get(acct, 0) + sgn * q
        return out

    def balance(self, account_id):
        for b in self._panel().get("balances", []):
            if str(b["account"]) == str(account_id):
                return None if b.get("equity") is None else float(b["equity"])
        return None

    def primary_account(self):
        """The connected broker account id (e.g. 'APEX6046970000002') so the sentinel keys on the REAL
        account, not the human label. None if the panel isn't readable."""
        for b in self._panel().get("balances", []):
            if b.get("account"):
                return str(b["account"])
        return None

    def avg_price_by_account(self, account_id):
        """READ-ONLY: return the average fill price for the account's open position,
        or None if no position / panel not readable / avg-price cell missing.

        Sourced from the avg-price-column of TRADOVATE.positions-table (same JS scrape
        as net_by_account).  Used by exec_telemetry to compute actual_fill_px and
        slippage.  Never raises — returns None on any error."""
        try:
            for p in self._panel().get("positions", []):
                if str(p.get("account")) == str(account_id):
                    v = p.get("avg_price")
                    return float(v) if v is not None else None
        except Exception:   # noqa: BLE001 — telemetry is observational; silently return None
            pass
        return None

    def order_filled(self, signal_id):
        """True/False if a matching order's status is known; None if not found. 'filled' is the ONLY
        state that confirms a real fill — 'working'/'canceled'/'rejected' are NOT fills (the 06-30 phantom
        was a 'working' retest-limit that never filled)."""
        for o in self._panel().get("orders", []):
            if signal_id is not None and str(o.get("signal")) == str(signal_id):
                return str(o.get("status", "")).lower() == "filled"
        return None
