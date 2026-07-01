"""Run this ONCE the Apex/Tradovate broker is connected in the :9222 TradingView (Trade -> connect ->
Tradovate -> login), with a position/order visible if possible. It reads the account-manager panel over
the SAME CDP channel the feed uses and dumps its structure so we can write readback_tradingview._PANEL_JS.
READ-ONLY: it never clicks, submits, or mutates the page."""
import json
from tv_feed import _CDP

# Read-only DOM probe: find the account manager, dump its tabs / tables / data-names + any trading globals.
INSPECT_JS = r"""
(() => {
  const out = { found: {}, tables: [], data_names: [], globals: [], text: null };
  const am = document.querySelector('[class*="accountManager"],[class*="tradingPanel"],[data-name*="account"]');
  out.found.accountManager = !!am;
  if (am) {
    out.text = (am.innerText || '').slice(0, 1200);
    // data-name attributes are TV's stable-ish hooks
    out.data_names = Array.from(new Set(Array.from(am.querySelectorAll('[data-name]'))
      .map(e => e.getAttribute('data-name')))).slice(0, 60);
    // any tables (positions/orders usually render as tables or role=grid)
    Array.from(am.querySelectorAll('table,[role="grid"],[role="table"]')).slice(0, 6).forEach(t => {
      const heads = Array.from(t.querySelectorAll('th,[role="columnheader"]')).map(h => (h.innerText||'').trim());
      const row0 = Array.from((t.querySelector('tbody tr,[role="row"]') || t).querySelectorAll('td,[role="gridcell"]'))
        .map(c => (c.innerText||'').trim()).slice(0, 12);
      out.tables.push({ headers: heads.slice(0, 12), sample_row: row0 });
    });
  }
  // tab labels (Positions / Orders / History)
  out.found.tabs = Array.from(document.querySelectorAll('[role="tab"],button'))
    .map(b => (b.innerText||'').trim()).filter(t => /position|order|history|account|balance|working|filled/i.test(t)).slice(0, 20);
  // broker / balance text anywhere
  const body = document.body.innerText || '';
  out.found.broker_words = ['Tradovate','Apex','Connected','Balance','Equity','Realized','Unrealized']
    .filter(w => body.includes(w));
  // trading globals (best-effort; TV keeps a broker/trading host somewhere on window)
  out.globals = Object.keys(window).filter(k => /trad|broker|account|order|position/i.test(k)).slice(0, 40);
  return out;
})()
"""


def main():
    cdp = _CDP()
    try:
        tgt = cdp.connect()
        print(f"connected to :9222 tab -> {tgt.get('title','?')[:70]}\n")
        r = cdp.eval(INSPECT_JS)
    finally:
        cdp.close()
    if not r:
        print("no result — is the :9222 TradingView chart tab open and the broker connected?"); return
    print("account manager present :", r["found"].get("accountManager"))
    print("broker/balance words    :", r["found"].get("broker_words"))
    print("tabs seen               :", r["found"].get("tabs"))
    print("\ndata-name hooks (first 60):"); print("  " + ", ".join(r.get("data_names") or []) or "  (none)")
    print("\ntables found:")
    for i, t in enumerate(r.get("tables") or []):
        print(f"  [{i}] headers   : {t['headers']}")
        print(f"      sample row: {t['sample_row']}")
    print("\ntrading globals on window:", r.get("globals"))
    print("\naccount manager text (first 1200 chars):\n" + (r.get("text") or "(empty)"))
    print("\n--> use this to write readback_tradingview._PANEL_JS (positions/balances/orders CONTRACT).")


if __name__ == "__main__":
    main()
