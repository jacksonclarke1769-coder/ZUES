# Read-back via TradersPost API — Build Scope

**Why:** the bot trades blind (TradersPost one-way) and booked phantom trades (2026-06-30: an unfilled
retest-limit recorded as a real trade). Apex **bans Tradovate API keys** on eval/funded, so the Tradovate-REST
read-back (`live_readback.TradovateBrokerView`) is dead. Read-back MUST come from the **TradersPost API**.

**Goal:** orders OUT via TradersPost webhook (unchanged) · TRUTH IN via the TradersPost REST API → the bot
confirms fills, kills phantoms, and catches orphan positions. Closed loop, Apex-legal.

## Step 0 — VERIFY (the one real unknown, do first)
Confirm what the TradersPost API actually exposes. From the docs + a test key:
- [ ] **Positions** endpoint → per-account net position (qty + side). (For `net_by_account()`.)
- [ ] **Account/balance** endpoint → equity/cash. (For `balance()` — the floor check.)
- [ ] **Order/execution status** → can we tell a real FILL from a placed-but-unfilled limit? ⚠️ TP "Completed"
      = order *placed*, not filled (proven 06-30). We need the **execution/fill**, not the order status.
- [ ] Auth model (Bearer API key), base URL, rate limits, and how a ZEUS `signalId` maps to a TP order/trade.
If TP does **not** expose positions/fills via API → escalate: the only closed-loop options left are a
broker that allows API read on Apex, or accept supervised-only (eye-confirmed) live, never unattended.

## Step 1 — TradersPostBrokerView  (`readback_traderspost.py`, skeleton exists)
Fill in `net_by_account()`, `balance()`, `order_filled(signal_id)` with the verified endpoints. Read-only,
no write methods. Map the account label (`APEX-50K-EVAL-1`) → the TP account id.

## Step 2 — Wire into build_readback (`auto_live.py:60`)
When `TRADERSPOST_API_KEY` is set, build `TradersPostBrokerView` (preferred for Apex) instead of Tradovate;
on any auth/connection failure → `broker=None` (the existing live-requires-readback guard then keeps the bot
DOWN, fail-closed). Tradovate path stays as a fallback for non-Apex firms.

## Step 3 — Phantom + orphan detection (reuse the sentinel)
`live_readback.ReadbackSentinel` already does the logic: MISSING_POSITION ("bot expects a fill, broker is
flat" = the retest-limit didn't fill) → don't book P&L / don't flatten a ghost; ORPHAN_POSITION → BLACK;
BROKER_READ_FAIL ≥3 polls → fail-closed. Add `order_filled()` so an entry only becomes a *tracked trade*
once TP confirms the execution — directly fixes the modeled-P&L phantom.

## Step 4 — Test
- Replay/dry: a placed-but-unfilled limit → sentinel reports MISSING_POSITION, no phantom booked.
- A real fill → tracked, P&L real, daily-stop counts it.
- Read-fail → live refused. Run on the eval account a full session before trusting unattended.

## Creds needed from operator
- **A TradersPost API key** (TradersPost → Account → API). NOT a Tradovate/broker key — Apex-legal.
- (optional) `TRADERSPOST_API_BASE` if the API host differs from the default.

## Status
Skeleton + guard committed; live is fail-closed until this is built. The retest-limit ENTRY model is
CONFIRMED optimal (don't change it) — this read-back is the only thing between the bot and trustworthy live.
