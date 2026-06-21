# Multi-Account Copier — Build Scope
_2026-06-21 · scope only · unblocks running >1 account (the gate to ZEUS-MAX)_

## The problem
ZEUS-MAX runs **8 accounts trading the SAME A+B+P3 signal**, one shared **TradingView feed**.
Today: one `auto_live` process, one account, one TradersPost URL, one instance lock. To run N
accounts the signal must be generated **once** and **fanned out** to N accounts, each with its own
URL, sizing, P3 state, journal, and daily stop.

## Two options — and why Option A wins
| | A — **Copier** (1 engine, fan-out) | B — Per-account isolation (N processes) |
|---|---|---|
| Feed | **1 feed → 1 engine** ✅ | N processes share/duplicate the feed ❌ (only 1 TV Chrome) |
| Signal consistency | computed **once**, identical for all ✅ | each process recomputes → drift risk ❌ |
| Supervision | **1 process, N-account dashboard** ✅ | N processes to watch ❌ |
| Code change | moderate (fan-out layer) | small (parameterize lock/store/url) but feed bottleneck kills it |
| Failure blast radius | per-account isolation needed in-process | naturally isolated ✅ |

**Recommend Option A (Copier).** The single TradingView feed is the deciding constraint — you can't
cleanly run 8 Chrome CDP feeds. One feed → one engine → fan out is the only sane architecture.

## Architecture: signal once → fan out to `AccountBook`s
```
TV feed → engine (SimBot A + ProfileBEngine + bars)   [runs ONCE]
   on A signal / B signal:
       for book in account_books:        # 3 MFFU + 5 Topstep
           size = book.p3.size(...)       # per-account brake on THAT account's cushion
           payload = build (book.account, size, ...)   # per-account signalId
           book.sender.send(payload)      # per-account TradersPost URL, EXITLOCK-gated
           book.tracker / book.journal    # per-account P&L + ledger
```
**`AccountBook`** (new) holds everything per-account: `account_id`, `firm`, `tier`, `sender`(URL),
`p3` brake, `daily_guard`, `journal`, `b_tracker`, `cushion` source. The engine is shared; the
**state is per-book**.

## What's reused vs new
**Reused (already per-account-keyed):** journal (`account_id` in every row), bridge dedup (signalId
includes account), `DailyGuard(account)`, `P3Brake` (per-instance), `ProfileBPaperTracker(account)`,
EXITLOCK gate (`_live_ok` per payload), ARGUS (logs `account`). The single-account building blocks
are already account-parameterized — that's why the copier is moderate, not huge.

**New to build:**
1. **`AccountBook`** dataclass + a registry (load the 8 from a config: account_id, firm, tier, url-env-key).
2. **Fan-out in `on_decision` / `on_b_signal`** — loop over books instead of one account; per-book size + send + track.
3. **Send ordering / jitter** — rotate the send order daily + small jitter, so no account is always first (FENRIR-X rate-limit ordering bias). Stagger ≤5s if V6 shows hard limits.
4. **Per-account cushion for P3** — v1: parallel sim-cushion (one `mffu`/`funded_sim` per book, tracks that book's fills); v2: broker-truth balance per account (the recon path).
5. **Failure isolation** — per-book `try/except`: one account's send failure logs + continues the others; never blocks the fan-out. Incident-block is per-book.
6. **N-account dashboard** — `/api/state` shows per-account posture, P&L, P3 state, fills; cross-account fill-rate spread monitor (FENRIR-X: >15pt spread = yellow).
7. **Per-account instance lock** — replace the single `data/bot.lock` with one lock for the copier process (one process now owns all accounts; the lock guards the copier, not per-account).
8. **Payout-window pause** — disable a book's sends during its firm's payout processing (LOKI #1: Topstep 5-XFA enforcement).

## Safety carry-over (must hold per-account)
- EXITLOCK flag gates **every** book's entries (still fail-closed).
- Each book's **daily stop** + **kill switch** independent; a global kill stops all.
- Each book's **two-leg Exit #3 / B bracket** is its own; flatten is per-account.
- ARGUS logs every book's decision (the `account` field already supports it).

## Dependencies / risks
- **Broker-truth cushion (v2)** — accurate funded P3 needs each account's real balance (the recon path, also unbuilt). **v1 ships with sim-cushion** (parallel `mffu` per book) — fine for eval + early funded; v2 refines P3 accuracy.
- **FENRIR-X #1 rate-limit fan-out bias** — 8 brackets × 2 legs in one signal burst can hit TradersPost/Tradovate limits; mitigate with jitter + rotation + ≤5s stagger (verify limits, V6).
- **Per-account fill divergence** — accounts get slightly different fills; that's expected (measured, not "fixed"). Dashboard tracks the spread.
- **Correlated blast radius** — all 8 trade the same signal, so a routing bug hits all 8. Per-book isolation limits *send* failures, not *signal* bugs — the parity/tests are the guard there.

## Phased build
- **Phase 1 (v1 copier, ~3–4d):** `AccountBook` + registry + fan-out + per-book sender/dedup/journal/tracker + failure isolation + send jitter/rotation. Sim-cushion P3. Tests: fan-out to N, per-account dedup, one-account-fail-isolated, EXITLOCK per book, jitter ordering.
- **Phase 2 (~2d):** N-account dashboard + fill-rate spread monitor + payout-window pause.
- **Phase 3 (~3–4d, later):** broker-truth cushion (recon balance per account) → accurate funded P3. Couples with the B1 direct-Tradovate recon work.

**v1 (Phase 1) unblocks running 2–8 accounts on the cadence.** Phases 2–3 harden it for funded scale.

## Estimate
~**5–6 days for v1+v2** (the runnable copier), +~3–4d for the broker-truth cushion (Phase 3, can lag).
Gate: needed **before account #2 goes live concurrently** — account #1 runs on today's single-account path.
