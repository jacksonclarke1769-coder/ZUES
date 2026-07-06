# VPC Execution-Lane — Build Spec + Risk Inventory
**DESIGN-ONLY — NOT BUILT.** No live-path code written; no execution module touched. For operator + advisor review. Fable auditor, 2026-07-07. LIVE HOLD ACTIVE.

Scope: define, on paper, the execution lane VPC needs and does not have. VPC (VWAP-Pullback Continuation) is validated/re-audited (PF 1.318 at 1m truth, D1c-immune, plateau-robust) but not live-buildable: it exits via a **2.5×ATR initial stop + 5.0×ATR trailing stop**, and the current stack has **no order-modify path** — Profile A uses a static stop/target bracket that is placed once and never moved. This document specs the missing path as if it will be adversarially reviewed, because the trail component will be.

---

## 0. Why this is not "just add a lane"

Profile A's live lane is a *fire-and-forget bracket*: on signal, `bridge_sender.send_exit3()` places entry + two static stop/target legs; nothing is modified for the life of the trade; exit is a broker-side bracket fill or the EOD/watchdog flatten. VPC breaks that model in one specific way — **the stop moves every bar** — and that single difference cascades into: a client-side trail manager (no native modify primitive), a new sim/live parity surface, cancel-replace race conditions, two-lane DLL accounting, and a phase-scoped sizing gate. The trail is the root; everything else is its blast radius.

---

## 1. Trail semantics spec (the single most dangerous component)

### 1.1 The pinned sim behavior (authoritative source: `tools_vpc_1m_truth.py`)
The 1m-truth walker — the honest reference, distinct from VPC's native 5m backtest — defines the trail as:

- **Initial stop**: entry ∓ 2.5 × ATR(at signal), where ATR is the 14-period value of the **most-recently-completed 5m bar** at signal time. This value is frozen for the initial stop.
- **Trail reference — high-water of 1m CLOSES**: `peak = max(1m closes since entry)` for longs (`min` for shorts). **Not** the 1m high; **not** the 5m high. Using the intrabar high is the artifact vector (§1.3).
- **Trail ATR term — a causal 5m step function**: the 5×ATR distance uses the ATR of the **last completed 5m bar** as of the current 1m bar. It updates only at 5m boundaries, only from bars that have actually closed. No forming-bar ATR.
- **Ratchet, one-directional**: `stop = max(stop, peak − 5×ATR)` for longs / `min(...)` for shorts. The stop can only move toward price, never away. This is structurally asserted in the sim and MUST be structurally asserted live.
- **Update frequency — per completed 1m bar** (not per tick). The trail recomputes once, on each 1m bar close.
- **EOD**: flat at the last RTH 1m bar close (no overnight risk).
- **No profit target**: VPC exits ONLY by stop (initial or trailed) or EOD. There is no +1R/+2R leg. (This is why it needs a modify path A never did — A's exit is a static target; VPC's exit is a moving stop.)

### 1.2 The exact adverse-ordering rule within a bar (the non-negotiable)
For each completed 1m bar, in this order, no exceptions:
1. **STOP CHECK FIRST**, against the stop level established by the *previous* bar. If the bar's low (long) / high (short) touched-or-crossed that pre-existing stop → **exit at the stop**, this bar, done. A bar can never use its own close to raise the trail and then be evaluated against the raised level on itself.
2. **Only if not stopped**: fold this bar's close into `peak`, recompute the candidate trail, ratchet the stop. That new stop takes effect from the *next* bar onward.

This ordering is the entire difference between an honest PF and a fraudulent one. It must be encoded identically in the sim walker and the live trail manager, and the parity test (§2) must prove they agree bar-for-bar.

### 1.3 The Asian-Range artifact — explicit cross-reference and how this spec avoids it
The Asian-Range Breakout strategy reported TradingView PF 2.03 that collapsed to ~0.9 under honest 5m fills. Root cause: **intrabar trailing-stop resolution** — the backtester allowed a bar's favorable excursion to advance the trailing stop and be credited *within the same bar* before that bar's adverse excursion was tested, i.e. it resolved the favorable touch before the adverse one. That is look-ahead inside the bar: the fill engine "knew" the bar went favorable-then-adverse and took the favorable outcome.

This spec defeats that vector three ways, all mandatory:
1. **Stop-first ordering (§1.2)** — the adverse touch is always tested before any favorable trail update.
2. **Close-referenced high-water, not intrabar high** — `peak` advances only on *completed 1m closes*, so a spike that reverses within a bar cannot ratchet the stop.
3. **Per-bar, not per-tick, updates** — no sub-bar resolution exists to be gamed.

Adversarial-review checklist for this component (a reviewer must be able to answer YES to all):
- Can any code path let a bar advance its own trail and then exit at that advanced level on the same bar? → must be provably NO.
- Does the trail ever reference the intrabar high/low rather than the close? → must be NO.
- Does the live manager and the sim walker produce identical stop-level time series on a shared replay? → must be YES (§2).
- Is the ratchet monotone (assert on every update)? → must be YES.

---

## 2. Sim/live parity requirement

### 2.1 The sim walker: EXISTS, but with a caveat to resolve
- The honest sim walker is `tools_vpc_1m_truth.py` (the 1m-truth re-walk; PF 1.318). **This is the parity reference.**
- VPC's *native* backtest (`nq_vwap_pullback.py`) walks the trail on **5m bars** — it is NOT the parity reference and must not be used as one (5m granularity was the audit's flagged gap; the 1m walker is the honest one).
- **Build item**: the 1m-truth walker was written as a research re-walk, not as a reusable execution-mirror. It must be refactored into a single canonical `vpc_trail(bars_1m, entry, dir, atr_5m_series) -> stop_series, exit` function that BOTH the sim and the live manager call, or that the live manager is proven bit-identical to. One trail definition, two callers — never two implementations.

### 2.2 What "live matches sim" means mechanically
The live trail manager, replayed over a historical 1m session with the same signal and same 5m-ATR series, must produce:
- the identical **stop-level time series** (every bar's stop value), and
- the identical **exit bar and exit price**,
as `tools_vpc_1m_truth.py` on that session. Bit-identical on the stop series is the bar; "close enough" is a fail.

### 2.3 The gating parity canary (analogous to A's Exit#3 = +89.2R / Fixed-1.5R = +96.9R)
Before the VPC lane may arm:
- **VPC trail parity canary**: the refactored canonical trail, run in "live-manager mode" (consuming bars sequentially as if streaming, issuing simulated cancel-replace events), reproduces the sim's full-stream signature **n=408, net = +5,319.67pt, PF = 1.318** exactly, AND the per-trade stop-series matches on a sampled ≥50-trade audit. Any deviation → the lane does not arm.
- This canary joins `gate.sh` and becomes permanent, like the A exit canaries and the timestamp canaries.

---

## 3. Order-modify path inventory

### 3.1 What the live stack currently has
`bridge_sender.py` exposes exactly three order primitives: `send()` (generic webhook POST), `send_exit3()` (entry + two static bracket legs), `flatten()` (cancel-then-exit). **There is no `modify`, `replace`, `amend`, or `move-stop` primitive anywhere in `bridge_sender.py` / `bridge_traderspost.py`.** No live strategy trails a stop today (the `auto_live` "trail" references are the Apex *drawdown floor*, a P&L threshold, not an order operation).

### 3.2 The two implementation options and their failure modes
**Option A — native broker order-modify (if TradersPost/Tradovate exposes it).** Requires verification: does the TradersPost webhook schema support a stop-modify action on a working order, and does Tradovate honor it atomically? UNKNOWN — must be confirmed against live API docs before this option is costed. If it exists it is preferable (atomic, no cancel-replace gap).

**Option B — client-side cancel-replace (the fallback, and the current-stack-only option).** Each trail update = `flatten`-the-stop-leg-then-`send`-a-new-stop. Failure modes, each needing an explicit fail-closed rule:
- **Naked-position gap**: between cancel-accepted and replace-accepted, the position has NO working stop. If the market moves adversely in that window, the account is unprotected. → FAIL-CLOSED RULE: never cancel the old stop until the new stop is confirmed working (replace-then-cancel, not cancel-then-replace); if replace is rejected, the OLD stop stays live and the trail simply doesn't advance this bar (a stop that's too loose by one bar is safe; a naked position is not).
- **Rejected modify/replace**: broker rejects the new stop (price through market, throttle, session state). → the old stop persists; log a `missed-trail` telemetry event; do NOT retry-spam (watchdog dedup discipline). Repeated rejections over N bars → HALT new entries + alert (the trail is not tracking).
- **Partial fill during modify**: position size changes mid-trail-update. → the trail manager must re-read broker position before every replace (never trust believed size — this is the `latest_signal()` defect class, §3.3); size mismatch → flatten + halt (watchdog invariant, §4).
- **Race: trail-update vs. market move**: the stop we compute from bar N's close is placed during bar N+1, by which time price may already be through it. → if the new stop would be placed already-through-market, do not place a limit that rests; convert to immediate flatten (the trail's intent was to exit at that level anyway). Spec the "already-through" test explicitly.
- **Cascade with EOD/half-day flatten**: a trail replace in flight at the EOD guardian time. → the EOD/half-day flatten (and the watchdog's independent flat-time signature) always wins; the trail manager must be idempotent under a concurrent flatten.

### 3.3 Cross-reference: the `latest_signal()` sibling defect
The live `latest_signal()` freshness check reconstructs timestamps from the model's mislabeled strings (INC-20260706-1141 scope addendum) and is TICKETED-NOT-FIXED. The VPC lane MUST NOT inherit this: **every VPC timestamp — signal freshness, ATR-bar selection, EOD test — derives from the tz-aware bar index, never from reconstructed strings.** This is a hard spec item, listed in build-order before any wiring. The A `latest_signal()` fix is a prerequisite of the whole hold lifting; the VPC lane is built correct-by-construction from day one.

### 3.4 Cross-reference: Watchdog fail-closed authority
The watchdog already has flatten/cancel/halt authority and fail-closed polarity. Its role for VPC is unchanged in kind but expanded in surface (§4): it must understand a *moving* stop as legitimate (not flag every trail replace as an orphan), while still catching a genuinely naked or mis-sized position. This is a watchdog invariant change — NEEDS AUDIT, not a copy-adapt.

---

## 4. Two-lane interaction

VPC fires on 225 days A sleeps (corr +0.11) — mostly non-overlapping, but co-active days exist and are where the risk concentrates.

### 4.1 Shared $550 daily stop + $1,000 DLL — the racing-resource problem
Today the $550 stop and $1,000 DLL are single-lane tallies. With two lanes they become a **shared, race-able resource**: A and VPC can each independently open risk that, summed, breaches the daily loss budget before either lane's own tally trips. Spec:
- **Single authoritative daily-risk ledger**, lane-agnostic, updated on every fill from BOTH lanes. The $550 blocker and DLL clamp read the *combined* realized+open risk, not per-lane.
- **Pre-trade admission control**: a lane may open a position only if `combined_open_risk + new_risk ≤ remaining_daily_budget`. On a co-active day this means the second lane to fire may be denied — that is correct and must be logged, not worked around.
- **No lane priority needed** for signal collision (the optimisation showed A and VPC almost never fire within 60 min), but the *budget* admission gate is mandatory and is where two-lane discipline lives.

### 4.2 Position / margin interaction
Two independent MNQ positions (A static bracket + VPC trailing) coexist on one account. Margin is shared; the daily-risk ledger (§4.1) governs. No netting assumption — they are separate positions with separate exits; the watchdog must reconcile aggregate net, not per-lane (it already does — the aggregate-net design is lane-count-agnostic, which is the one piece that composes cleanly).

### 4.3 Watchdog reconciliation of two lanes
- **Position parity** becomes: broker net == (A believed + VPC believed). A mismatch can now come from either lane — the watchdog flattens ALL and halts (it does not, and must not, try to attribute the break to one lane).
- **Orphan detection** must whitelist VPC's *expected* cancel-replace churn (a stop leg vanishing and reappearing is normal for VPC, an orphan for A). This is the specific invariant that NEEDS AUDIT — a naive orphan check will false-positive on every trail update and either spam-flatten VPC or get disabled by a human (the false-positive-fatigue failure the watchdog spec explicitly warns against).

---

## 5. Phase-scope enforcement (coded gate, not doctrine)

VPC eval sizing = $600/cap-3; VPC funded sizing = $150/cap-1 (survival). Same phase-inversion class as A's D1c-stream-by-phase. This MUST be a coded gate:
- **Where it lives**: the sizing resolver that translates (lane, phase, account-state) → (budget, cap). It reads the account's certified phase (eval vs funded) from the same authority the A/D1c phase split reads, and returns the phase-correct VPC sizing. There is no code path that lets eval sizing reach a funded account or vice-versa.
- **Firewall**: the VPC funded sizing joins the config hash-lock (like `config_funded_locked.py`); a phase-scope test in `gate.sh` asserts eval-config and funded-config VPC rows are byte-distinct and correctly routed. The negative control from the re-lock pack (eval sizing through the funded sim busts 54.8%) is the standing evidence for why this gate is not optional.

---

## 6. Risk inventory / build-order

### 6.1 Components ranked by risk-of-injecting-a-defect (highest first)
1. **The trail manager (live cancel-replace under adverse ordering)** — highest. Combines the artifact vector (§1.3), the naked-position failure mode (§3.2), and a race surface. A defect here loses positions or manufactures a fraudulent live P&L.
2. **Sim/live parity of the trail** — high. If the canonical trail function isn't shared/proven-identical, sim and live diverge silently and every certified VPC number becomes notional.
3. **Two-lane daily-risk ledger + admission control** — high. A race here breaches the DLL and busts a funded account.
4. **Watchdog orphan-whitelist for trail churn** — high. Gets false-positive-disabled by a human (worse than none) OR spam-flattens VPC.
5. **Timestamp derivation (index, never strings)** — medium-high (correct-by-construction is cheap here IF specced up front; the defect class is known).
6. **Phase-scope sizing gate** — medium (mechanically simple; high consequence if omitted; firewall-testable).
7. **Order-modify primitive choice (native vs cancel-replace)** — medium (a scoping/verification task; gates everything above it).

### 6.2 Build order (parity-tested sim + trail canary BEFORE any live wiring)
**Phase 0 — paper, no wiring:**
- (a) Refactor the trail into ONE canonical `vpc_trail()` function; the sim (`tools_vpc_1m_truth.py`) calls it; prove it reproduces n=408/+5,319.67pt/PF 1.318.
- (b) Write the trail parity canary (§2.3) and add to `gate.sh`.
- (c) Verify the order-modify primitive question (§3.2 Option A vs B) against live API docs — a written finding, no code.

**Before this lane may be PAPER-SHADOWED, all must be true:**
- (a)+(b) green in `gate.sh`; the live A `latest_signal()` fix is landed and audited; the two-lane daily-risk ledger and admission control exist with tests; the watchdog orphan-whitelist for trail churn is built and its false-positive rate is proven zero on a clean replay; the phase-scope sizing gate exists and is firewall-locked; VPC timestamps are index-derived by construction.

**Before this lane may be ARMED, all must additionally be true:**
- Paper-shadow run across ≥ the watchdog's observation-mode session count with ZERO trail-parity deviations, ZERO orphan false-positives, ZERO naked-position events, and ZERO phase-scope violations; a new certification + DEC on the two-lane machine; explicit operator arming approval. The hold does not lift on any partial completion.

### 6.3 Do not shortcut
There is no fast version of the trail. Every "simplification" (tick-level trail, intrabar high-water, cancel-then-replace, per-lane DLL, remembered-not-coded phase scope) reintroduces a specific defect enumerated above. This is a multi-component build with a parity surface that must be proven before a dollar moves; it should be scoped and estimated as such, not as "add a second lane."

---

## HIGHEST-RISK COMPONENT (one sentence)
The live 5×ATR trailing-stop manager is the single highest-risk component: it must reproduce the sim's stop series bit-for-bit under strict stop-before-trail adverse ordering while surviving cancel-replace failure modes without ever leaving the position naked — and any deviation either loses the position or manufactures the exact intrabar-trail artifact (Asian-Range PF 2.03→0.9) in live capital.

**Awaiting review before any build pass is scoped. No code written; no execution module touched.**
