# Read-back via the TradingView panel — Runbook (Apex-legal, no API key)

**Why this path:** Tradovate API is banned on Apex eval/funded; the TradersPost API is waitlisted. The bot
already reads the :9222 TradingView chart via CDP for data — if the Apex/Tradovate account is connected to
that TradingView as a broker, we read its account-manager positions/fills off the SAME channel. Platform
screen-reading, not an API key.

```
orders OUT → TradersPost → Tradovate            (works)
truth  IN  → Tradovate → TradingView panel → bot reads via CDP :9222   (this)
```

## ✅ Already built (before credentials — done)
- `readback_tradingview.TradingViewBrokerView` — implements the sentinel interface (`net_by_account`,
  `balance`) + `order_filled(signal_id)` (phantom-killer). Pure parsing of a fixed CONTRACT; unit-tested.
- **Fail-closed:** until `_PANEL_JS` is pointed at the real panel it returns `{__unconfigured__:true}` and
  every read RAISES → `build_readback` gets `broker=None` → the live-requires-readback guard keeps the bot
  STOOD DOWN. No chance of guessing positions.
- `tv_readback_inspect.py` — dumps the account-manager DOM/tabs/tables so we write `_PANEL_JS` fast.
- `build_readback` wired: `READBACK_SOURCE=tradingview` selects this path (fail-closed until configured).
- `test_readback_tradingview.py` — parsing + fail-closed proven with a mock CDP (no live needed).

## Tonight — the only steps left
**1. You (needs your login — I don't touch credentials):** in the :9222 TradingView window, click
   **Trade → connect broker → Tradovate → log in** with the Apex account. Confirm the **account manager
   (bottom panel)** shows positions / orders / balance. *This is the go/no-go gate.* If a small position is
   open while we inspect, even better.

**2. Me:** `python3 tv_readback_inspect.py` → read the DOM dump → write the real `_PANEL_JS` in
   `readback_tradingview.py` (returns the CONTRACT: positions[], balances[], orders[]).

**3. Verify before trusting (do NOT skip):**
   - real fill → sentinel reports the position, P&L real ✅
   - unfilled retest / cancel → sentinel reports `MISSING_POSITION`, books NO phantom (the 06-30 bug) ✅
   - read fails → live refuses (fail-closed) ✅
   - one full session supervised before unattended.

**4. Activate:** launch with `READBACK_SOURCE=tradingview`. With the read-back live + green, the
   `live-requires-readback` guard is satisfied → the bot can trade **1RR** live seeing real fills.

## CONTRACT `_PANEL_JS` must return
```
{ "positions": [ {"account","symbol","qty":int,"side":"long"|"short"} ],
  "balances":  [ {"account","equity":float} ],
  "orders":    [ {"account","signal":str|null,"status":"filled"|"working"|"canceled"|"rejected"} ] }
```
Note: only `"filled"` confirms a real fill — `"working"` is the unfilled-limit case that caused the phantom.

## Unknowns we resolve tonight (in order)
1. Can the Apex/Tradovate account connect to TradingView at all? (step 1 — the real gate)
2. Does the panel expose positions/fills readably via CDP? (step 2 — main technical unknown; known in minutes)
3. Apex-legality of the platform connection (screen-read ≠ API key — confirm against your terms)
4. DOM fragility — same class as the data read we already depend on; `_PANEL_JS` isolated for easy repair.
