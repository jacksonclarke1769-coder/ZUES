# VPC Execution Lane — Phase 3 Build Report

Branch: `vpc-execution-lane` (off `main`). NOT merged, NOT pushed, NOT armed.
Scope: DEC-20260712-RELOCK-V2-SIGNED Phase 3 — build + certification-prep of the VPC
(VWAP-Pullback Continuation) execution lane toward C1 (A $900/cap-6 + VPC $600/cap-3).

> THE LANE IS DISARMED. Nothing here routes to a broker. Live emission requires
> `EMISSION_MODE_ARM_LIVE`, reachable ONLY by an explicit construction that the
> go-live-recert.sh-gated config sets at Phase-4 activation. No file in this repo constructs the
> engine with `arm_live`. Default construction is `EMISSION_MODE_SHADOW` (observe/journal only).

## Constitutional compliance

- Branch-only work; no commits to main; no push; no `go-live-recert.sh` run.
- NOT edited: `go-live-recert.sh`, `config_funded_locked.py`, `config_eval_locked.py`, any
  EXITLOCK/exit-protection logic, watchdog core, `bridge_sender.py`'s send path. The ONLY change to
  pre-existing files are `bridge_traderspost.py` (the PAYLOAD builder module, spec-directed home for
  "additive builders following build_entry()'s fail-closed style") and `auto_live.py` (the D2 lane
  registration, additive + SHADOW-guarded). The `_wire` change is additive: a leading
  `if stop_replace:` branch keyed on an EXPLICIT flag (not the action string), so every pre-existing
  action path (buy/sell/add/exit/cancel) is byte-unchanged — A/B never set `stop_replace=True`
  (proven by `test_vpc_bridge_builders`). `strategy_engine_profileA.py` is byte-unchanged from `main`;
  the full suite proves A behavior is untouched. (NOTE: the earlier `elif action == "stop"` branch was
  REMOVED in D6 — `"stop"` is not a valid TradersPost action, only an orderType.)
- No strategy change: the frozen certified CFG (atr_stop 2.5, trail_atr 5.0, slot 6-66, max 2/day,
  slope 0.3, trend 0.5, daily_stop 120) is IMPORTED from `vpc_apex_eval_sim.CFG`, never redefined
  (`test_vpc_engine_failclosed::test_frozen_cfg_is_the_certified_config`).

## Files added / changed

| File | Role |
|---|---|
| `strategy_engine_vpc.py` (new) | `ProfileVEngine` streaming signal engine (reuses certified `vpc_signals` on a rolling buffer) + `VpcDayGate` (reproduces `simulate_day` taken-trade admission) + fail-closed EMISSION_MODE + `VpcTimestampReconstructionError`/`_derive_vpc_instant`. |
| `vpc_trail_manager.py` (new) | `VpcTrailManager`: live cancel-replace trail order management driving the CANONICAL `vpc_trail.VpcTrail`. Readback path uses CONFIRM-THEN-CANCEL ordering (the old stop is cancelled only after `confirm_fn` confirms the new one resting — F1 fix); cancel-replace timeout/rejection keeps the OLD, never-cancelled, still-working stop; MONOTONIC bar-id guard rejects stale/out-of-order re-delivered bars (F2 fix). Optimistic (default, no-ACK) path carries the inherent webhook-only gap (Phase-4 wire item). |
| `vpc_lane_gate.py` (new) | `VpcLaneRiskBook`: two-lane (A+VPC) risk accounting — per-lane caps (A 6 / VPC 3), per-lane size-to-risk budgets, shared combined-open-risk ceiling with ATOMIC reserve-on-admit (F3 fix: same-bar A+V admits cannot both pass against the same headroom) + `release()`; observational opposite-direction flag. |
| `vpc_journal.py` (new) | `VpcJournal`: four fail-open JSONL journals (signal / fill_intent / missed_fill / rejection). |
| `vpc_paper_harness.py` (new) | `replay_5m_native` (streaming sim-parity harness) + `PaperVpcLane` (end-to-end SimBot paper lane). |
| `bridge_traderspost.py` (edited, ADDITIVE) | `build_vpc_entry`; `build_vpc_stop_replace` (D6 SINGLE-CALL bundled cancel-replace — one payload: valid exit-side action + `orderType:"stop"` + `stopPrice`/`price` + `cancel:true`); `_wire` gains `stop_replace`/`cancel` kwargs + a flag-keyed branch (A/B byte-unchanged). |
| `auto_live.py` (edited, ADDITIVE — D2) | VPC lane construction (`v_engine`/`v_gate`/`v_book`/`v_journal`, SHADOW via `resolve_vpc_emission_mode`); `on_v_signal` (SHADOW-inert; armed branch unreachable); `v_new_day`; `_engine_bar` V dispatch; `_on_missing_cancel_is_safe` V fold-in; `_dp` A+B+V note; `_health_fields`/`_h_status` V surfaces. |
| `config_relock_v2_staged.py` (new — D1) | STAGED re-lock proposal (C1 sizing A $900/cap-6, VPC $600/cap-3; `VPC_LANE_EMISSION_MODE` arming field; applied ONLY via go-live-recert.sh). Schema-compatible with `config_eval_locked.py`. |
| `strategy_engine_vpc.py` (edited — D2) | `resolve_vpc_emission_mode()` — reads the single arming field from the live config (absent today → SHADOW). |
| `vpc_trail_manager.py` (rewritten — D6/D3) | Single-call bundled cancel-replace model (no eager client cancel; `live_stops()` never > 1); `kill_flatten()` + `on_flat_confirmed()` (D3 naked-impossible kill semantics). |
| `vpc_paper_harness.py` (edited — D4) | `arm_b_over_certified_slices()` + `_drive_manager_1m()`: drive the live manager over all 408 certified 1m slices. |
| `test_config_relock_v2_staged.py`, `test_vpc_auto_live_equivalence.py` (new) | D1 schema/disarmed + D2 A/B byte-equivalence + disarmed-chain invariant. |
| `reports/vpc_lane_build/02_reachability.md` (new — D5) | Live-poll reachability + suppression analysis. |
| `test_vpc_trail_parity.py` (edited) | + 5m-native convention canary; + ARM B (live-shaped parity, was the REQUIRED-BEFORE-ARM stub). |
| `test_vpc_signal_parity.py` (new) | raw-trigger parity, taken-trade parity, causality/truncation canary. |
| `test_vpc_engine_failclosed.py`, `test_vpc_trail_manager.py`, `test_vpc_lane_gate.py`, `test_vpc_bridge_builders.py`, `test_vpc_journal.py`, `test_vpc_paper_harness.py` (new) | unit coverage. |

## Parity canary results (BOTH conventions, exact)

- **1m-truth** (live parity TARGET; ARM A, pre-existing, re-verified green): n=408,
  net=+5319.669643pt, PF=1.31759, sample stop-series + whole-stream pnl hashes bit-identical.
- **5m-native** (signed economic basis; new canary): n=408, net=+4919.178571pt (6-dp exact vs
  `VS.vpc_trades_rich`).
- **Streaming engine reproduction (full history, offline)**: `replay_5m_native` over 2022-2026 real
  Databento = n=408, net=+4919.178571pt — EXACT match to the certified batch `backtest()`
  taken-trade ledger. In-suite this is asserted on bounded windows (per-trade entry ts + pnl exact)
  for speed; the full-history run is recorded here as verified.
- **ARM B (live-shaped parity, now BUILT)**: `VpcTrailManager` fed one 1m bar at a time (atr_now
  reconstructed by an independent streaming j5 mapping) yields a stop series + exit identical to the
  sim `walk_1m_trail` across long-stop / short-stop / EOD-runner scenarios.
- **ARM B over the REAL certified 408-trade 1m slices (D4, NOW BUILT)**: driving the LIVE
  `VpcTrailManager` over ALL 408 certified trades' real 1m slices (via
  `vpc_paper_harness.arm_b_over_certified_slices`, using the canonical 408 from
  `tools_vpc_1m_truth.vpc_1m_truth_trades` — no re-implementation of admission, only the deterministic
  per-trade 1m-slice geometry re-derived) yields a stop series + exit that match the certified sim
  `walk_1m_trail` (the ledger's `stop_path_new` / `exit_reason_new`) **BIT-FOR-BIT on every trade:
  408/408 match, 0 mismatches, 0 skipped.** Guarded as a `@pytest.mark.slow` test
  (`test_vpc_trail_parity.test_arm_b_over_certified_408_slices`).

## Suite counts (before → after)

- Before (baseline on branch point): **885 passed, 1 skipped** (886 collected).
- After (initial build): 931 passed, 1 skipped.
- After (cross-audit remediation F1/F2/F3 + hardening): 942 passed, 1 skipped.
- After (Phase-4 arming deferrals D1–D6): **962 passed, 1 skipped**. The pre-existing 885 remain
  green (Profile A unaffected — the full suite is green, no original test failed). New/changed tests:
  `test_config_relock_v2_staged.py` (D1, 6), `test_vpc_auto_live_equivalence.py` (D2, 8), the D3 kill
  tests + D6 single-call/no-double-stop tests in `test_vpc_trail_manager.py` and
  `test_vpc_bridge_builders.py`, and the D4 slow test
  `test_vpc_trail_parity.test_arm_b_over_certified_408_slices` (which ran and passed: 408/408). The
  single pre-existing skip (ARM B stub) is retained as a superseded historical scaffold.

## Cross-audit remediation (see `reports/vpc_lane_build/01_CROSS_AUDIT.md`)

The independent adversarial cross-audit returned FIX-REQUIRED with three reproduced defects in the
(disarmed) order-management layer; all three are now fixed on this branch, plus the two hardening
notes. This corrects two previously over-claimed lines in this report (the unqualified "never leaves
naked" and "one step per bar … test-covered" claims):

- **F1 — readback cancel-before-confirm (naked + false belief).** The `confirm_fn` path previously
  cancelled the OLD stop eagerly in `_issue_replace`, then on timeout "kept the last resting stop" —
  an order already cancelled. FIXED: confirm-then-cancel — the old stop is cancelled ONLY after
  `confirm_fn` confirms the new one resting; on timeout OR rejection the OLD (never-cancelled, still
  working) stop is kept, alerted, and the position stands down. New invariant test asserts the
  believed-resting stop is never in `cancelled_stops`. (The default optimistic no-ACK path was
  audited SOUND under its own model; its inherent webhook gap remains a Phase-4 wire item.)
- **F2 — idempotency guard bypassed by out-of-order bars (phantom exit).** The guard was
  `bar_id == last_bar_processed` (blocks only the immediately-preceding id). FIXED: monotonic guard
  rejects any `bar_id <= last_bar_processed`, so a reconnect-replayed / out-of-order stale bar cannot
  re-step the trail. The audit's exact phantom-exit reproduction now returns `hold`.
- **F3 — admit checked but did not reserve (same-bar overbook).** `admit()` read live headroom and
  booked nothing, so same-bar A+V both passed against the same ceiling ($1400 vs $1000). FIXED:
  atomic reserve-on-admit (`reserved` ledger counted in `combined_open_risk`) + `release()`;
  `on_open` converts the reservation without double-booking. New same-bar dual-admission test asserts
  the ceiling holds.
- **Hardening — `round_tick` NaN.** Now raises on non-finite prices; VPC builders fail closed
  (no `stopPrice: nan` payload).
- **Hardening — cold-start warmup gate.** `ProfileVEngine` refuses emission until its buffer holds
  `WARMUP_BARS` (≥1 RTH session) continuous bars, mirroring tv_feed's warmup discipline — closing the
  audit's diagnosed cold-buffer artifact. Parity/replay harnesses (which start from a genuine cold
  history start, matched against an equally-cold batch) construct with `warmup_bars=0`.

## doc-2 (07_...requirements.md) checklist coverage

MUST-BUILD / MUST-TEST ticked by this build:
- Signal parity: `ProfileVEngine` streaming `add_bar`/`latest_signal` reproducing
  `vpc_signals`+`simulate_day` → `test_vpc_signal_parity` (raw-trigger + taken-trade, zero-mismatch
  on window; full history verified offline). ✔
- Causal-availability truncation: `test_vpc_signal_parity::test_causality_truncation_canary`. ✔
- Causal timestamp proof: `_derive_vpc_instant` + `VpcTimestampReconstructionError` →
  `test_vpc_engine_failclosed::test_timestamp_reconstruction_fails_closed`. ✔
- Entry/stop order type (market entry + managed stop): `build_vpc_entry` + `VpcTrailManager`. ✔
- Max-2/day: `VpcDayGate` (covered by taken-trade parity). ✔
- $550 daily-stop sharing / combined open risk: `VpcLaneRiskBook` combined-ceiling admission. ✔
  (LIVE `_dp` aggregation across A+B+V in `auto_live.py` is a Phase-4 wiring/MUST-AUDIT item — see
  below; this build implements the lane's OWN gate additively, not the LiveAuto wiring.)
- Telemetry/journals: `VpcJournal` (4 fail-open journals). ✔
- Dry-run/replay/paper harness: `PaperVpcLane` + `replay_5m_native`. ✔
- Disarmed-by-default + fail-closed construction: `test_vpc_engine_failclosed`. ✔
- Trail cancel-replace incl. timeout: `test_vpc_trail_manager`. ✔

## Phase-4 arming deferrals D1–D6 — COMPLETED on this branch (still DISARMED)

All six are additive, guarded, and preserve the disarmed chain + the A-unaffected property (885
originals green). None arms the lane; none edits a forbidden file (go-live-recert.sh /
config_eval_locked.py / config_funded_locked.py / EXITLOCK / watchdog core / bridge_sender send path).

- **D1 — Staged locked-config artifact.** `config_relock_v2_staged.py` — the C1 sizing block (A
  $900/cap-6, VPC $600/cap-3, shared $550 ceiling; `RELOCK_DEC="DEC-20260712-RELOCK-V2-SIGNED"`) in
  the SAME schema/style as `config_eval_locked.py`, with a STAGED-PROPOSAL header stating it applies
  ONLY via go-live-recert.sh. Validation test `test_config_relock_v2_staged.py` asserts
  schema-compatibility with the locked file (mechanical swap), the C1 values, and that the arming
  field `VPC_LANE_EMISSION_MODE` exists ONLY in the staged file (absent from the locked config → the
  resolver resolves SHADOW today), and that no live path imports the staged file.
- **D2 — `auto_live` lane registration (additive).** VPC lane constructed in `__init__` (SHADOW via
  `strategy_engine_vpc.resolve_vpc_emission_mode()`, which reads a field the live config does not
  define → always SHADOW today); a fifth `try/except`-isolated bar-dispatch block in `_engine_bar`
  (V never breaks A/B); `on_v_signal` (SHADOW-inert — journals + returns, touching no sender / risk
  book / ledger / readback / A-B state; the armed branch is structurally present but UNREACHABLE);
  `_dp` documented as already A+B+V (ledger `day_entered_pnl` is strategy-agnostic, and V records
  nothing in SHADOW); flatten path (`_on_missing_cancel_is_safe`) folds in the V lane; dashboard/
  status (`_health_fields`, `_h_status`) surface the V lane. Byte-equivalence for A/B proved by the
  full suite + `test_vpc_auto_live_equivalence.py`.
- **D3 — Kill-switch semantics for an in-flight trail.** `VpcTrailManager.kill_flatten()` +
  `on_flat_confirmed()`: a kill/flatten (even mid-confirm) NEVER cancels the believed-resting stop
  first — it market-flattens, and the leftover resting stop is cleaned up ONLY after the readback
  confirms flat (naked-impossible). Tests: kill during pending confirm, kill during ratchet,
  naked-impossible assertion, idempotency (`test_vpc_trail_manager.py`).
- **D4 — ARM B over the real 408-trade 1m slices.** 408/408 bit-for-bit match vs `walk_1m_trail`,
  0 mismatches, 0 skipped (see the Parity section above); slow-marked test.
- **D5 — VPC live-poll reachability.** `reports/vpc_lane_build/02_reachability.md`: grounded in the
  emission path. Lag class = one-poll detection lag ≤ `poll_sec` (20–60s), bounded well inside the
  5m next-bar-open target, with NO per-signal staleness veto (VPC does not consult D1c → it LACKS
  A's surface-lag suppression class). The only VPC-specific gate is the cold-start warmup
  (`WARMUP_BARS=120`), which is bounded and NON-systematic: zero suppression in steady-state
  continuous operation (matches the certified n=408), biting only on a mid-session fresh restart (a
  runbook item, not an edge haircut). No suppression class that changes certified steady-state
  expectations exists.
- **D6 — Real-broker stop-replace wire field (mid-flight correction).** The TradersPost webhook
  reference (docs.traderspost.io, verbatim-verified 2026-07-12) invalidated the old two-payload
  design: `"stop"` is NOT a valid action (only an orderType — on the Tradovate BETA integration an
  unsupported action SILENTLY falls back to the strategy default), and TradersPost does NOT OCO-link
  a stop added to an open position (so place-then-cancel risks two un-linked live stops =
  double-fill). REWRITTEN: `build_vpc_stop_replace` now emits ONE bundled payload — a valid
  exit-side action (`sell` to protect a long / `buy` to protect a short) + `orderType:"stop"` +
  `stopPrice`/`price` + `cancel:true` — the documented server-sequenced cancel-replace that FAILS
  THE WHOLE trade on cancel/timeout (old stop stands, nothing changed → never-naked). The trail
  manager sends ONCE per ratchet; the eager client-side cancel path is GONE; `live_stops()` proves
  the model never holds two live stops (new no-double-stop invariant test). Docstrings corrected.
  **WIRE STATUS: docs-verified but the Tradovate-BETA specifics — whether `cancel:true` targets only
  the stop leg vs the whole position, partial-fill races, any rate ceiling — remain UNKNOWN pending
  the operator's TradersPost support ticket. The lane CANNOT arm on docs alone; the paper shadow +
  the ticket answer are the closing evidence.** BLOCKS live routing.

## What REMAINS before ARMING (operator-gated, NOT done here — with owners)

1. **Wire-field confirm (D6 close-out)** — the single-call bundled-cancel semantics are docs-verified
   but the Tradovate-BETA specifics need the operator's **TradersPost support ticket** answer (+ a
   paper-shadow observation). Owner: **operator** (raise the ticket) → then Sonnet applies any
   mapping delta under a spec. BLOCKS live routing.
2. **Watchdog trail-churn / paper-shadow acceptance** — zero orphan false-positives across a
   paper-shadow session must be demonstrated (the rate-limit + never-naked + no-double-stop design
   bounds it; the acceptance RUN is Phase-4). Owner: **operator-supervised paper-shadow run** →
   Fable reviews the acceptance. BLOCKS-ARMING.
3. **Conflict-policy DEC** — opposite-direction A+VPC stacking is OBSERVED (not vetoed) by
   `flag_opposite_direction`; whether to block is an explicit **operator DEC**, not improvised. Owner:
   **operator DEC** → Sonnet encodes the chosen policy. BLOCKS-ARMING.
4. **Locked-config promotion** — promoting `config_relock_v2_staged.py` (incl. the `vm`/`VPC_LANE_*`
   keys and the config-hash firewall extension) into `config_eval_locked.py` /
   `config_funded_locked.py` is a **go-live-recert.sh-gated** act, FORBIDDEN to perform here. Owner:
   **operator** (run go-live-recert.sh). BLOCKS-ARMING.

Phase-4 activation is operator-gated via `go-live-recert.sh`. This build does NOT arm the lane.
