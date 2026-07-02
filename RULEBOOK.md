# 📕 ZEUS Rule Book

The single canonical reference for how the bot trades and how you run it.
Operative account: **Apex 50K eval** (v2026.07.02 machine — see `AGENTS.md` §"THE SELECTED MACHINE").
When this file and code disagree, **code wins** — sources are noted per section.

> **Golden rule:** Built ≠ proven, and `http 200` ≠ filled. The bot only knows that
> TradersPost *received* the order, never that Tradovate *executed* it. Your eyes on
> the broker are the only thing closing that loop until the B1 direct path lands.

---

## 1. Strategy rules — what the bot trades (Profile A only)
_Source: `strategy_engine_profileA` (frozen, parity-verified), `bot.py`._

- **Setup:** NY-AM killzone liquidity continuation (frozen A v2 engine).
- **Entry window:** 09:30–11:30 ET only (signal poll runs to 13:35 ET to resolve late setups).
- **One position at a time. Max 2 trades/day.**
- **Flat by 14:30 ET every day** — wall-clock EOD flatten, feed-independent, no exceptions.
- Every trade carries a **server-side bracket**: limit entry + stop + target (Exit #3, two-target).
- Profile B is **not** in the live engine yet → Monday is A-only (≈22 of ~30 weekly pts).

## 2. Sizing & risk rules — tier `50K-conservative`
_Source: `auto_safety.py` tier table, `config.py SAFETY`, ARES docs._

| Rule | Value |
|---|---|
| Size (A) | **3 MNQ** (B=2, not live) |
| Daily stop | **−$700** → halt new entries for the day |
| Worst historical day | **~$1,486** (must stay < buffer) |
| Trailing buffer | **$2,000** |
| Bust cost (eval) | ~$35 reset |

- **Core ARES rule:** never size where the worst historical day exceeds the trailing buffer.
- **P3 cushion-brake:** when cushion (equity − trailing floor) < **40%** of trailing-DD allowance
  → cut to `A//2, B=0`; resume full size at **60%** (hysteresis latch, no flip-flop).
- **D1c DriftGate:** filters Profile A by drift direction (active on the 1m TV feed). Can only
  *subtract* trades, never add size. Fail-closed: stale / missing-open / zero-drift → SUSPEND.

## 3. Hard safety gates — what the bot REFUSES to do (fail-closed)
_Source: `auto_live.py` entry gate, `auto_safety.py`, `scheduler.py` calendar, approval flags._

The runner will **not fire** unless ALL are true:
- ✅ It's a **trading day** — weekend/holiday gate blocks otherwise (the Juneteenth fix).
- ✅ Data is **GREEN** (fresh) — stale feed → blocked as "arming."
- ✅ **Dead-man** alive.
- ✅ Live fully armed — needs **both flags** (`traderspost-approved` + `bracket-verified`)
  **AND** `--live` **AND** `--confirm` **AND** `TRADERSPOST_LIVE_URL`. Miss any → **PAPER**.
- ✅ Daily stop not hit, kill-switch not set.
- ✅ Account is not funded — **ARES refuses to arm a funded account** (active account is an Apex eval).

Any unmet gate = no webhook. Fail-closed is the default everywhere.

## 4. Execution path (the architecture)
_Source: `auto_live.py` → `bridge_sender` → `bridge_traderspost`; Stage 2 proven 2026-06-15._

```
TradingView live data → bot fires signal → TradersPost webhook → Tradovate (Apex) → order
```
- TradersPost IS the broker connection (no direct Tradovate API on this path).
- Bracket attaches at Tradovate (Stage 2 operator-verified: stop+target WORKING).
- Client-side dedup (TradersPost has none natively) — a retry can't double-fire.
- **No broker-truth reconciliation** — the bot trusts `http 200` = received, not filled.

## 5. Operator rules — your duties (this is the safety layer)
_Source: `MONDAY_SESSION.md`, `go_live_test.sh`._

- **You ARE the reconciliation.** For **every entry**, confirm in Tradovate within ~60s:
  filled? **stop attached & working?** **target attached & working?**
- **Confirm flat at 14:30 ET** in Tradovate — not just the `http 200`.
- **Stay present the whole session** (no VPS / external dead-man yet — attended only).
- **Kill switch** if the real account nears −$700 (bot PnL is a sim proxy; you're the backstop):
  ```
  python3 -c "from store import Store; Store().set_state(auto_live_kill='1')"
  ```
  Clear with `set_state(auto_live_kill='')`. `Ctrl-C` stops the runner; open positions ride
  their server-side brackets.

## 6. Launch sequence (Monday)
```
# launch ONLY via the certified script (rotates creds, verifies config, fails closed)
bash ./go-live-recert.sh
```

## 7. Posture & escalation
- **Default posture (idle):** `env=demo` · `paper=True` · `SAFETY.enabled=False` (master kill-switch off).
  The supervised-live launcher arms it for the session and it returns to off after.
- **Eval → funded:** on pass, follow the Apex funded transition procedure (see `OPERATOR_RUNBOOK.md`);
  sizing shifts to funded_40_recert recommendation (A4-A5). Survival rules tighten.
- **Roadmap (closes the golden-rule gap):** the B1 direct-Tradovate runner (built, tested offline,
  `b1_runner.py`) adds journaled INTENT → recon-against-broker-truth → auto naked-position detect,
  enabling unsupervised/VPS operation. Blocked on Tradovate demo API creds (A3 spike). Not on the
  bridge path's critical path.

---
_Last refreshed 2026-06-20. Canonical; supersedes scattered rules in per-project docs._
