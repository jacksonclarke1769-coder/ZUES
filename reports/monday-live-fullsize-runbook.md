# MONDAY — LIVE at FULL EVAL SIZE (A3/B2 + B + P3 + Exit #3)
_operator decision 2026-06-21: skip paper, go live Monday at full 50K-conservative size_

## What runs Monday
`go_live_test.sh` → `auto_live --tier 50K-conservative --live --confirm` on the TradingView feed:
- **Profile A** Exit #3 two-leg = **3 MNQ** (1@+1R, 2@+2R, shared stop)
- **Profile B** ORB single bracket = **2 MNQ** (ATR stop/target)
- **P3 brake** (paper cushion), **D1c active**, **−$700 daily stop**, worst-day $1,486 (< $2k buffer)
- EXIT3_FIXED_PARTIAL (CONFIGLOCK fail-closed), ARGUS logging every decision

## ⚠️ Residual risks at full size (eyes open)
1. **First-ever live fills for the aligned system** — A two-leg + B single bracket + P3, all at once, full size. Only A's *single-target 1-MNQ* bracket was ever proven live (Stage 2).
2. **B has never fired a live order.** Its bracket *format* is the same proven `_wire` as A's legs — but B's autonomous trigger at 2 MNQ is new. **Watch the first B fill attach.**
3. **P3 reads the PAPER cushion** (SimBot equity), not the real broker balance. It only brakes near the floor, so it's transparent on a healthy eval start — but it's not broker-truth. (Funded broker-truth cushion is unbuilt.)
4. **No broker reconciliation** — the bridge trusts `http 200`, not a confirmed fill. **You are the reconciliation.**

## What YOU must supply before it can trade (I did NOT create these)
- [ ] `touch evidence/approvals/exit-model-approved.flag` — **without this, every live entry fails closed** ("LIVE BLOCKED: exit model not approved"). This is the live arming gate.
- [ ] **TradersPost LIVE webhook URL** for the eval account (the launcher prompts, hidden).
- [ ] **The 50K eval account + its TradersPost→Tradovate connection.** If it's a *new* account, re-run the Stage 1–3 bridge proof (1-MNQ bracket attach) on it first.

## Pre-open (~09:00 ET)
```
cd ~/trading-team/bot/nq-liq-bot
python3 monday_preflight.py --account MFFU-50K-1 --tier 50K-conservative   # every line ✓ except the URL
bash tools/launch-tv-chrome.sh                                             # load CME_MINI:NQ1! @ 1m
python3 tools/probe_tradingview_bars.py --duration 120                     # must say PROBE PASS
touch evidence/approvals/exit-model-approved.flag                          # <-- YOU arm it here
```

## Launch (~09:20 ET)
```
bash go_live_test.sh
# type GO LIVE -> paste TradersPost URL (hidden) -> it runs A3/B2 + B + P3 live
```

## In-flight supervision — this is the safety layer (no reconciliation)
For **every** entry, confirm in Tradovate within ~60s:
- A: **both** legs filled? **stop + both targets working** (1@+1R, 2@+2R)?
- **B (first one especially): single bracket — stop + target attached?** If a B bracket doesn't attach, **kill immediately.**
- P3: if the account nears the floor, confirm size cuts (it shouldn't trigger early).
- 14:30 ET: confirm **flat** in Tradovate (not just http 200).

**Kill switch** (real account nears −$700; bot PnL is a sim proxy — you're the backstop):
```
python3 -c "from store import Store; Store().set_state(auto_live_kill='1')"
```
`Ctrl-C` stops the runner; open positions ride their server-side brackets.

## The one safety step that does NOT shrink your size
**Let B's FIRST live signal be the bracket proof:** when B fires, watch Tradovate confirm the stop+target attach before trusting it for the rest of the session. If it attaches clean, B is proven; if not, kill and fall back to A-only (`--no-profile-b` if you add the flag, or disable B). This proves B live without running a separate tiny session.

## After the session
```
python3 tools/audit_live_engine_session.py --date today --session ny-am
python3 tools/check_exit3_parity.py
```
Clean = `SESSION CLEAN`, A two-leg + B single-bracket fills reconcile vs Tradovate, no synthetic P&L.

## Honest expectation
Realistic week: **choppy, two-sided** — the rehearsals showed −$436 (weak 2wk) to +$2,427 (strong month) at this size. **Not +$1,400.** Judge it over the week, not the day.
