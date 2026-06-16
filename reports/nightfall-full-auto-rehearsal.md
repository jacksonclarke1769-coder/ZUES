# NIGHTFALL — Full-Auto Rehearsal
_2026-06-16 · rehearsal only · Profile A/B/D1c/sizing untouched_

## VERDICT: **FULL-AUTO REHEARSAL PASS** → live unattended full auto **NOT allowed tonight**
Every live system worked. Full auto is correctly **blocked** by the feed source (TradingView browser
= SEMI_AUTO_ONLY), the absent approval flag, and no proper-feed soak. Allowed mode: **SEMI-AUTO**.

## 1–18
1. **Feed source:** `tradingview-1m` (Chrome/CDP).
2. **Browser or proper API feed?** **Browser/CDP** — not a proper API feed.
3. **Feed health:** GREEN — recovered at the overnight reopen, streaming fresh 1m bars.
4. **Soak result:** none. No proper feed exists to soak; the browser feed **froze twice** historically → SEMI_AUTO_ONLY.
5. **Heartbeat:** fresh (OK, ~18s).
6. **Dead-man:** OK (process alive).
7. **Data state:** GREEN.
8. **DATA_READY:** True (real-time confirmed).
9. **D1c:** ACTIVE_EVAL_FILTER (legal — 1m + real-time + GREEN).
10. **ARES:** armed · MFFU-50K-1 · 50K-conservative (A3/B2).
11. **TradersPost:** PROVEN (ping + 1-MNQ bracket + flatten evidence + PROVEN.flag).
12. **Dashboard:** GREEN = systems healthy / **semi-auto-ready** (not the full-auto authority).
13. **Full-auto preflight:** **BLOCKED.**
14. **Exact blockers:**
    - `missing evidence/approvals/full-auto-approved.flag`
    - `FEED: 'tradingview-1m' is browser/CDP (SEMI_AUTO_ONLY — froze twice); needs a proper API feed (tradovate/databento)`
    - `EXECUTION: TRADERSPOST_LIVE_URL not set` (verification-shell artifact — operator holds it locally)
15. **Current allowed mode:** SEMI-AUTO GO.
16. **Live unattended full auto tonight?** **NO.**
17. **Allowed command:** supervised paper/rehearsal runner —
    `python3 auto_live.py --account MFFU-50K-1 --tier 50K-conservative --feed tradingview-1m --d1c-mode active-eval-filter`
    (no `--live`); + operator's manual semi-auto bridge sends with the local URL.
18. **Forbidden:** `auto_live ... --live --confirm`; `touch evidence/approvals/full-auto-approved.flag`.

## What the rehearsal PROVED works (live, end-to-end)
Live data GREEN (dual 1m→D1c / 5m→engine) · D1c ACTIVE legal · heartbeat + dead-man · honest dashboard ·
wall-clock EOD flatten armed · entry gate armed (blocks on non-GREEN) · reconnect + self-healer ·
TradersPost execution proven · ARES armed. The full chain operates; only the *authorization* gates remain.

## Safety hardening added this session (directive-aligned)
- **Preflight now HARD-FAILS on a browser/CDP feed** and requires `feed-soak-passed.flag` for a proper
  feed — so even with every other gate green (and even if someone created the approval flag), a
  TradingView browser feed cannot reach full auto. Defense in depth.
- `full_auto_preflight.py` CLI added (read-only) so the gate is one command + repeatable.

## Exact path to FULL AUTO (in order)
1. **Build a proper feed:** Tradovate API market data (`--feed tradovate`, `LiveBarFeed` scaffolded — needs
   Tradovate API `cid`/`sec` + md entitlement) **or** Databento live CME 1m (needs account/key + adapter).
2. **Soak it clean** (a full session, zero stalls/resets) → `touch evidence/approvals/feed-soak-passed.flag`.
3. **Operator approves** → `touch evidence/approvals/full-auto-approved.flag`.
4. Preflight then passes → run `--live --confirm`.

## Hard rules honored
Browser feed → preflight fails ✓ · no `--live` ✓ · `full-auto-approved.flag` NOT created ✓ ·
no trade on non-GREEN ✓ · dashboard truthful ✓.
