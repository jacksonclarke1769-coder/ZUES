# B1 DESIGN — Execution Layer (Design Trial, no code)

Status: DESIGN ON TRIAL — 2026-06-11. Verdict at bottom: **B — approved with amendments.**
Integrates (frozen, do-not-redesign): B0 `journal.py` / `recon.py` / `recovery.py`,
`mffu_state.py` (43/43), `tradovate_client.py` (OSO + triple live-gate), SAFETY config,
HEIMDALL tiers, P3 (40/60), frozen A/B engines + parity tests.

Design invariants (non-negotiable):
- **I1** No order transmission without a durable INTENT and a passing `can_send()`.
- **I2** Ambiguity is never resolved by resend — only by reconciliation against broker.
- **I3** Protection is server-side: entry and stop travel together (OSO) or entry is cancelled.
- **I4** Time is wall-clock (`America/New_York` tz-db); bars are data, never the clock.
- **I5** Accounts are independent: per-account state, per-account lifecycles, divergence
  is accepted and measured, never "fixed" by force-syncing.
- **I6** The bot is fail-closed: any unresolved BLACK, unreachable broker, or failed
  startup recovery ⇒ no new INTENTs (existing positions remain server-side protected).

---

## PART 1 — ORDER LIFECYCLES (journal events ⊕ state transitions ⊕ recon checkpoints)

Per-account, per-signal "slot" = (account, strategy, signal_ts, role). Roles:
`entry`, `flatten`. Bracket legs ride INSIDE the entry lifecycle (OSO), with their own
events but the same `cl_ord_id`.

**A. New entry (clean path)**
1. Engine emits signal → for each enabled account, size from that account's P3 state.
2. `INTENT` (payload: side, qty, entry px, stop px, target(s) px, OSO plan) — fsynced.
3. `can_send()` gate → `SEND` (payload: exact request body) → transmit OSO
   (limit entry + stop leg + target leg(s), qty = intended).
4. Broker accepts → `ACK` (verbatim response; broker_order_ids for all legs).
   State: `working`. Recon checkpoint: CHECK4 now recognizes the working orders.
5. Entry fills → `FILL` (qty, px, broker ids). State: `open`.
   `BRACKET_CONFIRMED` only after broker shows the protective stop WORKING with
   qty == filled qty (not merely accepted in the OSO response).
   Recon checkpoint: CHECK2 covers from this moment; the gap between FILL and
   BRACKET_CONFIRMED is the ≤60s naked window (RED if exceeded — wall-clock timer).
6. Exit (stop, target, or EOD flatten) → broker fill on a bracket leg → `EXIT`
   (px, reason, broker ids). Terminal. Recon: position disappears from both sides.

**B. Partial fill**
- `PARTIAL_FILL` events accumulate (each with qty, px). State: `partial`.
- Bracket discipline: protective legs must equal **cumulative filled qty** at all times.
  OSO auto-sizing is NOT assumed (VERIFY V3, Part 3): if broker auto-sizes legs, record
  `MODIFY_CONFIRMED` from its events; else issue modify → `MODIFY_SENT` → `MODIFY_CONFIRMED`
  (Amendment A0 event types).
- Entry remainder: cancelled at signal-window expiry (A: window close 11:30 ET or
  engine-specified bar limit; B: 6×5m bars) → cancel lifecycle (D below) → final state
  `open` with the partial qty; targets sized to filled qty.

**C. Order rejection**
- OSO rejected atomically → `REJECT` (verbatim). Terminal. No retry of the same slot
  (deterministic cl_ord_id refuses); a NEW signal makes a NEW slot.
- Child-leg reject after entry accept (if broker semantics allow it — VERIFY V2):
  `ACK` then `REJECT` on the leg → position may exist unprotected → covered by the
  FILL-without-BRACKET_CONFIRMED 60s timer → emergency flatten lifecycle (role=`flatten`).

**D. Timeout / cancel ambiguity**
- Send timeout: `SEND` exists, no `ACK` → state `sent_unknown`. NO resend (I2).
  Resolution: next recon pass or `recovery.recover()` → ACK/FILL/REJECT from broker truth.
  Until resolved: slot counts as exposure-unknown ⇒ account is no-new-entries (I6 local).
- Cancel: `CANCEL_SENT` (A0) → broker confirms → `CANCEL`. Cancel/fill race: if a FILL
  arrives after CANCEL_SENT, **the fill wins** (it is broker truth); lifecycle proceeds
  as B with bracket cover; `CANCEL` is then recorded as failed-cancel in payload.

**E. Manual flatten (operator intervention)**
- DECLARED path: operator runs `flatten <account>` (CLI/dashboard) → bot creates a
  `flatten` lifecycle: INTENT(reason=manual) → SEND (market close + cancel-all working
  for that account) → FILL → `EXIT`(reason=manual) on the parent slot.
- UNDECLARED path (operator acts inside broker UI): recon CHECK1/CHECK3 fires BLACK —
  **by design**: undeclared intervention IS an incident; resolution procedure appends
  `EXIT`(source=operator-undeclared) + `RECON_ALERT` + NOTE-in-payload, and the event
  goes to the monthly audit. The system never silently absorbs human action.

**F. Restart during open position**
- Startup order: single-instance lock → `recovery.recover()` BEFORE feed/engine start →
  unresolved SENDs resolved from broker; positions rebuilt; STATE_ASSERT comparing
  `mffu_state` snapshot counters vs ledger-derived (mismatch = ORANGE, no new entries);
  brackets re-verified at broker (CHECK2). Only on a clean recovery report does the
  engine begin processing bars. Open positions ride their server-side brackets
  throughout the outage (I3) — restart never flattens by default.

## PART 2 — BROKERVIEW SPECIFICATION (per platform adapter; Tradovate first)

All methods are SNAPSHOT reads (REST), authoritative at read time. WS streams feed the
same adapter as low-latency hints but recon consumes snapshots only.

- `positions() -> [{account_id, contract_id, contract_symbol, qty(net signed), avg_px}]`
  — all enabled accounts, empty list = flat (an error MUST raise, never return []).
- `working_orders() -> [{account_id, broker_order_id, order_type(Limit|Stop|StopLimit|Market),
  action(Buy|Sell), qty(remaining), px, linked_group_id(OCO/OSO id|None), cl_tag(str|None)}]`
- `fills_since(cursor) -> ([{account_id, broker_order_id, fill_id, qty, px, ts_utc}], new_cursor)`
  — cursor = broker fill id watermark, persisted in `Store` (NOT the ledger); replays
  tolerated (recon dedupes by fill_id).
- `account_state(account_id) -> {balance, open_pnl, margin_used} | raises`
- `health() -> {auth_ok, last_roundtrip_ms, server_time_utc}` — feeds HEIMDALL; clock
  skew = |server_time − local| > 2s ⇒ yellow.
- Failure semantics: every method either returns truthful data or RAISES. No partial
  silence. Two consecutive raises in-session ⇒ ORANGE + no new INTENTs (I6); positions
  remain bracket-protected.
- Polling: 20s in-session (recon piggybacks every cycle); 120s out-of-session;
  rate budget ≤ 1/3 of documented limit (VERIFY V6).

## PART 3 — TRADOVATE MAPPING (with verification spikes — nothing implicit)

| B1 action | Tradovate object/endpoint (existing client basis) | authority |
|---|---|---|
| Entry+stop+target | `order/placeoso` — entryVersion(Limit) + bracket1(Stop) + bracket2(Limit); two-target = `place_bracket_two_targets` (2 OSOs of half qty — V1) | response = ACK only; WORKING state via order list = authoritative |
| Modify (bracket resize/stop move) | `order/modifyorder` on the leg's orderId | confirm via order list snapshot, not response |
| Cancel | `order/cancelorder` | confirm via order list (order gone/Cancelled) |
| Fills | `fill/list` (or `fill/ldeps`) keyed by orderId | AUTHORITATIVE — the only truth for FILL/EXIT |
| Positions | `position/list` net per contract | authoritative snapshot |
| Balance | `cashBalance` / account snapshot | authoritative |
| Client tag | `customTag50`-class field carrying `cl_ord_id` (V4) | if unsupported → mapping via ACK orderId only (B0 already supports) |

Authoritative vs advisory: **REST snapshots (orders/positions/fills/balance) are
authoritative. The HTTP response to a place/modify/cancel is ADVISORY** (it proves
receipt, not state). WS entity events are advisory accelerators. Everything advisory
must be confirmed by snapshot before the journal records a *_CONFIRMED event.
**Verification spikes (1 demo day, blocking implementation):**
V1 limit-entry OSO supported + two-OSO half-qty behavior on partial entry fills;
V2 child-leg reject semantics (can entry live while a leg rejects?); V3 OSO bracket
auto-resize on partial entry fills (yes/no); V4 customTag/clOrdId pass-through field;
V5 bracket persistence across session disconnect + after restart; V6 documented rate
limits + p-ticket penalty behavior at 8-account burst; V7 fill/list pagination + id
monotonicity for the cursor.

## PART 4 — TIMEOUT & DISCONNECT MATRIX

| event | expected state | unknown state | recovery path |
|---|---|---|---|
| send timeout | none | order may exist | `sent_unknown` → recon/recovery resolves (ACK/FILL/REJECT); account no-new-entries until resolved |
| API disconnect (mins) | positions bracket-protected | fills may have occurred | on reconnect: recovery.recover() before any send; fills_since cursor replays the gap |
| VPS restart | same | same + local state stale | Part 1F startup order; lock prevents double-instance |
| internet loss (hours) | brackets live at broker | exits may have filled | same as disconnect; EOD: broker-side flatten does NOT exist — see EOD note |
| broker latency spike | slow ACKs | rising sent_unknown count | ≥2 sent_unknown in 60s ⇒ ORANGE, stop new sends, widen poll |

EOD note: there is no broker-side scheduled flatten; if connectivity is lost
approaching 14:30 ET with a position, the bracket still bounds risk but EOD-flat
policy is violated → this exact scenario is the operator's ONE daily page-worthy
condition (HEIMDALL RED: "feed/API down with open position past 14:00 ET").

## PART 5 — PARTIAL FILLS & DIVERGENCE (48-MNQ aggregate reality)

- Sizing decided per account at signal time from that account's own P3 cushion (I5).
- Each account's lifecycle proceeds independently: fills 4/4 on one, 2/4 on another,
  0/4 on a third = three valid states, not an error.
- Bracket qty ≡ that account's cumulative filled qty (Part 1B); remainder cancels at
  window expiry.
- Divergence accounting: per-signal divergence record (intended vs filled per account)
  derived from the ledger; HEIMDALL panel: rolling 20-signal fill-rate per account and
  cross-account spread; spread beyond fill-luck bounds (>15 pts of fill-rate) = yellow
  (suggests rate-limit ordering bias — FENRIR X #1; rotate send order daily).
- P3 interaction: P3 gates INTENDED qty only; realized-vs-intended shortfall is income
  noise, never risk excess (realized ≤ intended always, enforced by qty in OSO).
- Recon: all checks already operate per account on filled qty; nothing assumes sync.

## PART 6 — TOP 10 RESIDUAL EXECUTION RISKS (post-B0; P/S/D 1-5, 5 worst)

1. **Fill-vs-cancel race at window expiry** P4 S3 D2 — protection: fill-wins rule (1D);
   missing: none after A0; mitigation: replay test forcing the race.
2. **Naked window between FILL and stop WORKING** P3 S5 D2 — protection: 60s timer +
   emergency flatten; missing: V2/V3 facts; mitigation: spike then encode.
3. **Bracket-resize race on rapid partials** P3 S4 D3 — protection: modify lifecycle
   (A0); missing: broker auto-resize semantics (V3); mitigation: resize only on snapshot
   confirmation, never assume.
4. **WS/REST ordering inversion** (fill hint before ack processed) P4 S2 D2 —
   protection: WS advisory-only; recon consumes snapshots; mitigation: event application
   idempotent by broker ids.
5. **Duplicate WS/fill replay** P3 S3 D1 — dedupe by fill_id (B0 CHECK3 map).
6. **8-account burst rate-limit ordering bias** P3 S2 D3 — jitter + rotation + V6.
7. **Contract-id mismatch across accounts (roll week)** P2 S4 D2 — pre-session assert:
   identical resolved contract on all accounts or no trading (THOR ⑦).
8. **Cancel confirmed but order actually filled (broker-side race)** P2 S4 D2 —
   covered: CHECK1/CHECK3 catch the orphan fill within a cycle; fill-wins reopens slot.
9. **Operator undeclared intervention** P2 S3 D1 — 1E procedure + BLACK by design.
10. **Two-OSO half-qty desync (Exit #3) on partial entry** P3 S3 D3 — if V1 shows the
    two-OSO pattern can't track partials cleanly, Amendment A6 fallback: single full-qty
    stop + leg-1 target as a separate reduce-only-style limit confirmed by snapshot
    (still server-side; design decided AFTER V1, before code).

## PART 7 — SEQUENCE DIAGRAMS (text; J=journal, B=broker, R=recon)

1. CLEAN: sig→J:INTENT→gate→B:placeOSO→J:SEND→resp→J:ACK→[poll]B:orders=working→
   …B:fill→J:FILL→B:orders shows stop working→J:BRACKET_CONFIRMED→…→B:bracket fill→J:EXIT.
2. TIMEOUT: …J:SEND→(no resp)→state sent_unknown→R: B.working_orders match→J:ACK(src=recon)
   | B.fills match→J:ACK+FILL | neither→J:REJECT(not_found). Never a second placeOSO.
3. PARTIAL: …J:ACK→B:fill 2/4→J:PARTIAL_FILL→stop leg qty?→(V3 yes: B auto→J:MODIFY_CONFIRMED |
   no: J:MODIFY_SENT→B:modify→snapshot→J:MODIFY_CONFIRMED)→window expiry→J:CANCEL_SENT→
   B:cancel→snapshot→J:CANCEL→state open(qty 2).
4. CRASH MID-FILL: …J:SEND→[crash]→restart→lock→recovery: B.fills→J:ACK+FILL(src=recovery)→
   beliefs rebuilt→R grace-free: CHECK2 naked→emergency flatten lifecycle or bracket re-place
   (operator ack required: RED).
5. RESTART RECOVERY: lock→recover()→resolve unknowns→STATE_ASSERT vs mffu snapshot→
   clean? engine start : ORANGE hold.
6. MANUAL FLATTEN: operator cmd→J:INTENT(role=flatten)→B:cancel-all+market close→
   J:FILL→J:EXIT(manual)→R: both sides flat→quiet.
7. RECON MISMATCH: R cycle1: diff found→grace count→cycle2: confirmed→J:RECON_ALERT→
   HEIMDALL BLACK→no silent correction→operator procedure (flatten/disable per tier).

## PART 8 — HOSTILE REVIEW OF THIS DESIGN (attacks and their outcomes)

- "OSO response treated as protection" — REJECTED by design: BRACKET_CONFIRMED requires
  the stop WORKING in a snapshot (Part 1A.5). Attack fails.
- "Two-OSO Exit #3 desyncs on partials" — attack LANDS conditionally → V1 spike +
  predecided fallback (A6). Design survives only with the amendment.
- "Cancel race makes `partial` terminal-ambiguous" — fill-wins rule + snapshot-confirmed
  CANCEL closes it (A0 vocabulary needed → amendment).
- "Recovery re-places brackets automatically = hidden resend" — caught: bracket
  re-placement after crash is a NEW lifecycle requiring operator RED-ack (diagram 4),
  not an auto-resend. Codified.
- "fills_since cursor in Store violates never-trust-memory" — acceptable: cursor loss
  only causes REPLAY (dedup by fill_id), never omission. Attack fails.
- "STATE_ASSERT compares to a snapshot that may itself be stale" — true; assert runs
  against broker-derived balance too (CHECK5). Residual: firm-dashboard floor still a
  daily manual check (LOKI #11). Accepted, documented.
- "Design assumes Tradovate facts not in evidence" — correct → V1–V7 spike day is a
  BLOCKING precondition; any spike surprise returns the relevant section to design.
- "8 accounts × OSO legs × modifies could exceed rate limits in one signal burst" —
  V6 + jitter + budget; if V6 shows hard ceilings, amendment path: stagger entries by
  account over ≤5s (acceptable: limit entries at fixed px, no chase).

## PART 9 — VERDICT: **B — APPROVED WITH AMENDMENTS**

Implementation may begin only after:
- **A0** Ledger vocabulary extension: `CANCEL_SENT`, `MODIFY_SENT`, `MODIFY_CONFIRMED`
  (+ table-rebuild migration `migrate_b1.py`; CHECK constraint widened; append-only
  preserved).
- **A1** Wall-clock authority module (flatten/EOD/session/news from tz-db; bars are data)
  — built WITH B1, blocking.
- **A2** Single-instance lock — blocking, trivial.
- **A3** Tradovate verification spike V1–V7 on demo — one day, BLOCKING; results
  appended to this document; any surprise re-opens the affected section.
- **A4** Exit #3 partial-fill policy decided from V1 results (two-OSO vs A6 fallback)
  BEFORE coding the bracket module.
- **A5** Emergency-flatten lifecycle (role=`flatten`) implemented and battery-tested
  before any other lifecycle goes live — it is every failure path's terminal state.
- **A6** (conditional) single-stop fallback design if V1 fails.

With A0–A5 satisfied, this design reduces every THOR/LOKI execution risk to either a
mechanically-detected-within-one-cycle condition or an explicitly operator-acknowledged
RED. The highest-risk component in the project enters implementation with its failure
modes enumerated before its functions.
