# VPC Execution Lane — Independent Cross-Audit (adversarial)

Auditor: independent (no self-certification). Branch: `vpc-execution-lane` @ `71fa2f5`
(range `dcb9e02..71fa2f5`). READ-ONLY audit; only this file added. Suite re-run by the auditor.

**Overall verdict: FIX-REQUIRED (pre-arm).** The branch is a coherent, safely DISARMED Phase-3
prep artifact: Profile A is byte-untouched, the streaming engine reproduces the certified ledger
EXACTLY, the bridge edit is inert for A/B, and nothing routes to a broker today. But three
reproduced findings in the (disarmed, Phase-4-gated) order-management layer must be fixed before
the lane can be trusted to arm — and two of them contradict explicit claims in
`00_BUILD_REPORT.md`. No live exposure exists in the meantime (lane disarmed, unwired).

Certifiable-as-a-disarmed-build: yes. Certifiable-to-arm: NO until F1–F3 below are closed.

---

## Suite (auditor re-run)

- `python3 -m pytest -q` → **931 passed, 1 skipped** in 161s. Matches the expected 931.
- No `pytest-randomly`; order is deterministic. VPC subset re-run (2nd pass) → 50 passed, 1 skipped,
  identical. No flakiness/reordering sensitivity observed.
- The 1 skip = `test_live_shaped_parity_arm_STUB` (intentionally superseded by the built ARM B). OK.

---

## 1. Never-naked invariant — `vpc_trail_manager.py`  → SPLIT: optimistic SOUND(-gap), readback DEFECT

**Optimistic path (`confirm_fn=None`, the DEFAULT): GAP-DEFERRED-OK.** Under the manager's own model
(HTTP-200 send == landed) the ordering is never-naked: the new stop is sent first (`_issue_replace`),
the stale stop is cancelled only after the new send returns `sent:True`, and a *failed* new-stop send
aborts the replace keeping the last resting stop (`test_never_naked_on_failed_new_stop` — verified:
on reject only the `stop` payload is attempted, no `cancel`). The real belief-vs-reality divergence —
TradersPost returns 200 but the new stop fails downstream at Tradovate while the cancel of the old one
succeeds ⇒ naked with `resting_stop` advanced — is the inherent webhook-only NO-ACK limitation. It is
explicitly flagged (build report item 6; the `NO-ACK MODEL` docstring), the wire mapping is
CONFIRM-pending, and the lane is disarmed. The `confirm_fn` readback *hook* exists but is **not
integrated with any real broker read-back source** (none exists in this stack — "confirm fills by
eye"). Acceptable to defer; must be resolved at Phase-4 wire verification.

**Readback path (`confirm_fn` set): DEFECT (reproduced).** The readback path is meant to CLOSE the
no-ACK gap, but its ordering is unsound: `_issue_replace` sends the old-stop `cancel` **eagerly**
(`vpc_trail_manager.py:131`) — *before* `confirm_fn` ever confirms the new stop is resting — yet holds
`resting_stop` at the OLD level and, on timeout, "keeps the LAST confirmed resting stop" (lines 79–86).
That old stop was already cancelled. So under a downstream new-stop failure the manager stands down
believing it is protected by a stop that no longer exists → **naked, with a false belief of
protection** — the exact divergence this hook was added to prevent.

Reproduction:
```
confirm_fn=lambda s: False, timeout_s=5
on_1m_bar(1, 99,101,100.5, atr=1, now_ts=0)  -> sends ['stop','cancel']; resting(belief)=95.0, pending=98.5
   (OLD stop cancel SENT before any confirm)
clock->10; on_1m_bar(2, ...)                 -> stood_down=True, "keeps resting=95.0"
   (but 95.0 order was cancelled at the broker)
```
`test_cancel_replace_timeout_stands_down_and_keeps_last_resting` passes only because its FakeSender
has no broker state — it never checks that the cancelled old order is gone. Correct never-naked with
readback: do NOT emit the old-stop cancel until `confirm_fn` confirms the new stop resting (move the
cancel into the confirm branch of `_check_timeout`). Blocks trusting the readback path at arm.

Minor (hardening, note): the `cancel` payload carries only a fresh `signalId`; it does not reference
the prior stop order to cancel — a generic cancel. Wire-mapping CONFIRM-pending (already item 6).

## 2. One-step-per-bar idempotency guard — DEFECT (reproduced)

The guard is `if bar_id == self.last_bar_processed` (`vpc_trail_manager.py:100`). It blocks only the
*immediately-preceding* bar id. The docstring and `00_BUILD_REPORT.md` claim "process each distinct
1m bar EXACTLY ONCE" / duplicate-feed double-step "actually fixed and test-covered." It is not: a
**non-consecutive / out-of-order re-delivered bar** (a feed reconnect that replays the last N minutes —
exactly the reconnect case the design spec worries about) bypasses the guard and re-steps the
canonical trail.

Reproduction:
```
on_1m_bar(1, 99,101,100.5, atr=1) -> replace, resting 98.5
on_1m_bar(2,100,103,102.5, atr=1) -> replace, resting 100.5
on_1m_bar(1, 99,101,100.5, atr=1) -> "exit" @100.5   <-- PHANTOM EXIT
```
The re-delivered stale bar (low 99 < the ratcheted internal stop 100.5) fires a spurious stop exit;
in other price paths it double-ratchets the internal stop past the true resting stop. The only test,
`test_rate_limit_one_replace_per_bar`, covers only the consecutive-duplicate case. Fix: enforce
monotonic bar ids (reject `bar_id <= last_bar_processed`) or track ordering explicitly. The paper
harness masks this (its `bar_id` is a monotonic counter), so the live-feed wiring is where it bites.
Blocks arm.

## 3. `bridge_traderspost.py` diff (the one pre-existing-file edit) — SOUND

Byte-level: the diff is purely additive — one `elif action == "stop"` branch inserted in `_wire`
after the `buy/sell/add` block, plus two new builder functions appended at EOF. Every pre-existing
action path is unchanged: `buy/sell/add` still hit the first branch; `exit`/`cancel` match **neither**
`if` nor the new `elif`, so they fall through to `extras`/`signalId` exactly as before
(`test_existing_build_cancel_unaffected` proves `cancel` stays minimal — no `quantity` leaked from the
stop branch; `test_existing_build_entry_unaffected` proves entry output identical).

Unreachable for A/B (grep-proven, not trusted from the report): no A/B/live builder passes
`action="stop"`; the only caller of `_wire(..., "stop", ...)` is `build_vpc_stop_replace`, which is
imported only by `vpc_trail_manager.py` and `vpc_paper_harness.py` — both disarmed/paper-only.
`auto_live.py`/`bot.py`/`copier.py`/`fanout_book.py` never reference it.

Fail-closed: `build_vpc_stop_replace`/`build_vpc_entry` validate side and qty and `round_tick`, return
`(None, error)` on any exception, matching `build_entry`'s style. One residual hole (hardening only,
not reachable today): `round_tick(nan)` returns `nan` without raising, so a NaN `new_stop` would emit a
`stopPrice: nan` — but the engine guards `np.isnan(atr)` before emitting and ARM-B reconstructs a
non-NaN atr, so no live path supplies NaN. Recommend an explicit `math.isfinite` check before arm.

## 4. Parity independence — SOUND

Auditor re-ran BOTH canaries green (ARM A 1m-truth n=408/net +5319.669643/PF 1.31759 bit-identical;
5m-native n=408/net +4919.178571 6-dp exact). Independent full-history comparison of the STREAMING
engine (`replay_5m_native`) vs the certified `vpc_trades_rich`, using the auditor's own per-trade
comparator (not the suite helper): **n=408, net 4919.178571 == 4919.178571, 0 per-trade mismatches.**

One windowed comparison (arbitrary slice starting 2023-10-01) showed a first-trade divergence
(streaming picked 11:30, certified 10:10). Diagnosed as a **cold-buffer warmup artifact**, NOT an
engine defect: the streaming engine recomputes ATR on its own rolling buffer, which is cold when the
history is sliced mid-stream, so early-window rolling(14) ATR differs from the continuously-computed
batch ATR. Re-running the same window WITH a 2-month warmup prefix → **0 mismatches.** Confirms parity
and isolates the cause. Live operational note (Phase-4 runbook): the engine must be buffer-warm
(continuous run, ≥1 session) before its signals match certified; a fresh-process intraday cold-start
could emit off-parity signals until warm. Not flagged in the build report — recommend a warmup gate.

## 5. Risk gate — `vpc_lane_gate.py` — mostly SOUND, one same-bar GAP

Sound: per-lane caps (A6/V3) and per-lane $ budgets bind correctly and size DOWN; combined-open-risk
ceiling `combined + new ≤ daily·cushion` enforced; reopen blocked while a lane holds; `new_day` clears;
fail-closed on construction (`daily_budget≤0`, `point_value≤0`) and on NaN/negative `stop_pts`
(`abs(nan)≤0` is False, but the subsequent `int(nan//risk)` raises → caught → `(False,0,err)`).
Cap boundaries exact (`min(q, cap)`; exact-budget fills to the `≤` boundary). `flag_opposite_direction`
is observational-only (never blocks) per the deferred conflict DEC.

**GAP — simultaneous same-bar A+V admission (reproduced).** `admit()` does not *reserve*; it reads
`remaining_daily_budget()` live and books nothing. If a caller admits A and V in the same bar before
`on_open`-ing either, both see the same remaining budget and both pass:
```
daily=$1000; admit('A',stop100,q4)->4 ($800); admit('V',stop100,q3)->3 ($600)
combined booked = $1400 > $1000   (ceiling silently violated)
```
The `combined_open_risk + new_risk ≤ remaining` invariant holds ONLY if the caller sequences
admit→on_open per lane. A and V "almost never fire within 60 min" (design), and the `auto_live`
wiring is Phase-4 (item 2), so exposure is bounded — but the module offers no atomic reserve and the
report does not flag this. Phase-4 wiring MUST book each admit before admitting the next lane, or the
book should expose a reserve/`admit_all`. GAP-DEFERRED but must be an explicit Phase-4 audit item.

**Disarmed-by-default chain — SOUND (grep-proven).** No production code constructs `arm_live`
(`emission_mode=ARM_LIVE` appears only in `test_vpc_engine_failclosed.py`); default construction is
`shadow`; unknown modes raise (`test_unknown_emission_mode_fails_closed`). `auto_live.py` has ZERO
VPC/ProfileVEngine/`"V"`-lane references. `VpcTrailManager`/`VpcLaneRiskBook`/`build_vpc_*` are
constructed only by tests and the paper harness. Nothing in the repo can build an armed engine.

## 6. Full suite / determinism — SOUND

931 passed, 1 skipped; deterministic across two runs; the single skip is the intended superseded stub.

---

## Verdict table

| Area | Verdict |
|---|---|
| 1. Never-naked — optimistic (default) path | GAP-DEFERRED-OK (inherent no-ACK; flagged, disarmed) |
| 1. Never-naked — readback (`confirm_fn`) path | **DEFECT** (F1) — cancels old stop before confirming new |
| 2. One-step-per-bar idempotency | **DEFECT** (F2) — guard bypassed by non-consecutive/OOO bar |
| 3. bridge_traderspost.py diff | SOUND (inert for A/B, fail-closed; NaN-stop hardening note) |
| 4. Parity independence | SOUND (full-history 0 mismatch; window diff = warmup artifact) |
| 5. Risk gate | SOUND + one same-bar admission **GAP** (F3); disarmed chain SOUND |
| 6. Full suite / determinism | SOUND (931 pass / 1 skip, stable) |

## FIX-REQUIRED before arming (all in the disarmed layer — no live exposure today)

- **F1** (`vpc_trail_manager.py:131`) — in the readback path, defer the old-stop `cancel` until
  `confirm_fn` confirms the new stop resting; otherwise "keep last resting stop" on timeout keeps a
  cancelled order (naked + false belief). Correct the report's unqualified "never leaves naked" claim.
- **F2** (`vpc_trail_manager.py:100`) — enforce monotonic bar ids (`bar_id <= last_bar_processed` →
  hold) so a reconnect-replayed/out-of-order stale bar cannot re-step the trail (phantom exit /
  double-ratchet). Correct the report's "one step per bar … test-covered" claim (only the consecutive
  case is covered) and add an OOO/stale-bar test.
- **F3** (`vpc_lane_gate.py`) — provide an atomic reserve or require the Phase-4 wiring to book each
  lane's `on_open` before admitting the next; add a same-bar A+V combined-ceiling test. Document that
  `admit` alone does not enforce the combined ceiling across concurrent same-bar admits.

## Deferrals I concur are legitimately Phase-4 (GAP-DEFERRED-OK)

Locked-config `vm` sizing; `auto_live` lane registration + `_dp` A+B+V aggregation; conflict-policy
DEC; kill-switch-vs-in-flight-trail semantics; causal-reachability split; real-broker stop-replace
wire field (item 6); ARM B over real 408-trade 1m slices; watchdog trail-churn paper-shadow
acceptance. Add to that list: the engine cold-start **buffer-warmup gate** (§4) and the readback
integration with a real broker read-back source (§1).

---

# Round 2 — Remediation re-verification (auditor, 2026-07-12)

Re-audited `4945dd2..bc81cf6` (fixes `76961c0` F1/F2, `b6117f8` F3, `2369d9e` hardenings,
`bc81cf6` docs). Method: re-ran the auditor's OWN round-1 attack code (not the builder's new tests)
against the fixed code, plus one new variant per defect.

## Per-defect kill-confirmation (original repros re-run)

- **F1 (readback never-naked) — KILLED.** `_issue_replace` no longer sends the old-stop cancel in
  the readback path; the cancel is deferred into `_check_timeout` and fires ONLY after `confirm_fn`
  confirms the new stop resting (confirm-then-cancel). Round-1 repro: during the in-flight replace
  sends are `['stop']` only (no cancel); on timeout `stood_down=True`, `resting=95.0`,
  `cancelled_stops=[]` → the kept stop was never cancelled. Invariant `resting_stop ∉ cancelled_stops`
  holds. **New variant** (explicit `"rejected"` mid-ratchet + kill/flatten during a pending confirm):
  old stop kept uncancelled and working in every branch → never naked.
- **F2 (idempotency) — KILLED.** Guard is now `bar_id <= last_bar_processed → hold`. Round-1 repro
  (replay stale `bar_id=1` after bar 2): returns `hold`, resting unchanged at 100.5, `exited=False`
  — the phantom exit is gone. **New variant** (same `bar_id` with a corrupt crash-low payload that
  would phantom-exit if re-stepped): rejected as `hold`, no exit; a genuinely-higher `bar_id` still
  processes and ratchets. Monotonic ordering enforced.
- **F3 (same-bar dual admission) — KILLED.** `admit` now atomically reserves sized risk; a second
  same-bar admit sees reduced headroom via `combined_open_risk = open + reserved`. Round-1 repro
  ($1000 ceiling): `admit A`→4 ($800) then `admit V` sizes 3→**1** ($200); combined **$1000 ≤
  ceiling** (was $1400). **New variant (reserve-leak on rejection):** `release(lane)` fully frees the
  reservation and `open_side` (remaining budget back to $1000, no leak); dup-admit of a
  reserved/held lane is blocked; `admit→on_open` converts the reservation with no double-count.

## New-variant results — all pass (no residual naked/overbook path found)

## Hardenings

- **NaN/inf payload — impossible.** `round_tick` raises on non-finite input; `build_vpc_stop_replace`
  and `build_vpc_entry` fail-closed `(None, error)` on NaN/inf stop or ref; a valid payload's
  `stopPrice` is provably finite. Verified directly.
- **Cold-start warmup gate — works and does not weaken the live default.** `ProfileVEngine` default
  `warmup_bars=120`; `latest_signal` returns `None` while `len(buf) < 120` (verified blocked at
  buf=119; the `< max(2, warmup_bars)` guard admits computation at 120). Parity/replay harnesses pass
  `warmup_bars=0` (legitimate: they start at TRUE history start where the batch is equally cold —
  apples-to-apples), so the live default is untouched. `replay_5m_native` uses `warmup_bars=0`;
  `PaperVpcLane` retains the live default 120.

## Regression status

- Full suite: **942 passed, 1 skipped** (matches expected 942; +11 over round-1's 931). The 1 skip is
  the intended superseded ARM-B stub.
- Parity independently re-verified on the fixed code: streaming `replay_5m_native` vs certified
  `vpc_trades_rich`, full history = **n=408, net 4919.178571 == 4919.178571, 0 per-trade mismatches.**
  Both canaries (1m-truth + 5m-native) remain green in-suite.

## FINAL VERDICT: BUILD-COMPLETE-CERTIFIABLE (as a disarmed Phase-3 build)

All three round-1 defects (F1/F2/F3) are killed against the auditor's own reproductions and one new
variant each; both hardenings do what they claim without weakening the live defaults; no regression
(942/1) and parity remains exact. The lane remains DISARMED and unwired — the legitimately-Phase-4
deferrals from round 1 (locked-config `vm` sizing, `auto_live` registration + `_dp` A+B+V
aggregation, conflict-policy DEC, kill-vs-in-flight-trail semantics, real-broker stop-replace wire
mapping / readback integration, causal-reachability split, ARM-B over real 408 slices, watchdog
paper-shadow acceptance) still gate ARMING and are unaffected by this pass. Certifiable as a build;
NOT yet arm-eligible until those operator-gated Phase-4 items clear `go-live-recert.sh`.
