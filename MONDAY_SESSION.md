# MONDAY — First Live Auto Session Runbook (2026-06-22)

First time the bot **autonomously fires a real order in-session**. The rails are all
proven: frozen Profile A engine + ARES sizing + D1c active filter + daily guard +
kill switch + TradersPost→Tradovate bridge, on the **TradingView live feed**. 320 tests
green. Stage 2 is DONE — live is unlocked. This is how you turn it on.

## The honest status (read once)
- **Bridge path is PROVEN.** 2026-06-15: a real 1-MNQ order reached MFFU/Tradovate via
  TradersPost, stop+target attached (operator-verified), flatten/cancel clean, dedup held.
  Both arming flags (`traderspost-approved`, `bracket-verified`) are present.
- **What is NEW on Monday:** the *autonomous in-session entry* — Stage 2 was a manual
  forced order; the 6-17 full session ran paper. Monday the bot decides and fires on its own.
- **First entry size = 3 MNQ (full 50K-conservative tier).** Operator decision 2026-06-20.
  Daily stop −$700, worst-day ~$1,486 (inside the $2k eval buffer; a bust ≈ $35 reset).
- **Account is an EVAL** (MFFU-50K-1, ARES mode) — not funded. ARES funded-rail satisfied.
- **⚠ NO broker-truth reconciliation on this path.** TradersPost is a one-way relay: the bot
  trusts `http 200` = *TradersPost received it*, NOT a confirmed fill/bracket/flat at Tradovate.
  **You are the reconciliation.** Keep the Tradovate UI open and verify every transition by eye.
  (The B1 runner that would auto-reconcile is built but is the *direct-API* path — not this one.)

## ~20 min before 09:30 ET — preflight (one command)
```
cd ~/trading-team/bot/nq-liq-bot
python3 monday_preflight.py --account MFFU-50K-1 --tier 50K-conservative
```
On Monday every line must be ✓ EXCEPT `TRADERSPOST_LIVE_URL` (you supply it at launch, below).
If `git clean` is ✗, that's fine for safety but resolve if you want a clean board. If
`ET trading day` is ✗ at this point something is wrong with the clock — do NOT trade.

## Launch — supervised live auto on the TradingView feed (one command)
```
bash go_live_test.sh
```
It will: ask you to type `GO LIVE` → prompt for your **TradersPost LIVE webhook URL**
(hidden input, never stored in git/chat) → arm and run:
```
auto_live.py --account MFFU-50K-1 --tier 50K-conservative \
  --feed tradingview-1m --d1c-mode active-eval-filter --execution traderspost \
  --controlled-tv-full-live-test --live --confirm
```
The runner's own preflight still enforces every gate and **REFUSES** to fire if data isn't
GREEN, the dead-man is dead, or it's a holiday/weekend. Watch the output + the dashboard.

## During the session — you, supervising (this is the safety layer)
On every signal the bot prints the decision and (if it fires) logs the webhook. **For each
entry, confirm IN TRADOVATE within ~60s:**
- [ ] entry filled at ~the expected price
- [ ] **STOP attached and working** (this is the naked-position guard — the bot can't verify it)
- [ ] **TARGET attached and working**
- [ ] on exit / 14:30 EOD: position actually **FLAT** at Tradovate (not just `http 200`)

Backstops:
- ARES daily stop is −$700 (bot's PnL is a sim proxy, not the real fill — **you** are the
  real backstop). If the real account nears −$700, **kill it**:
  ```
  python3 -c "from store import Store; Store().set_state(auto_live_kill='1')"
  ```
  Halts all new entries instantly. Clear with `set_state(auto_live_kill='')`.
- `Ctrl-C` stops the runner. Open positions ride their server-side Tradovate brackets.
- Trades only 09:30–11:30 ET, max 2/day, one position at a time, flat by 14:30 ET.

## After the session
- Review `out/ares/bridge_webhook_log.csv` (live sends + http status) and
  `out/ares/d1c_eval_log.csv` (allowed/blocked A trades). Reconcile against Tradovate fills.
- Journal the session: did the autonomous entry fire, fill, bracket, and flatten cleanly?
- If eval passed: `python3 ares_mode.py switch-funded MFFU-50K-1` (ARES → ZEUS funded survival).

## Known limitations (honest, for after Monday)
1. **No auto fill-reconciliation on the bridge** — operator-watched; fixed later by the B1
   direct-Tradovate path (auto-reconcile + naked-position detect, enables unsupervised/VPS).
2. Profile B not in the live engine yet (Profile A only ≈ 22 of ~30 weekly pts).
3. D1c runs on the 5m feed (validated on 1m; keep-rate monitor watches for drift).
4. No VPS / external dead-man yet — session is attended only.
