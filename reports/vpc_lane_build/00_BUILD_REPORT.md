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
  a pre-existing file is `bridge_traderspost.py` (the PAYLOAD builder module, which the spec
  explicitly directs as the home for "additive builders following build_entry()'s fail-closed
  style") — additive only: a new `elif action == "stop"` branch in `_wire` (every pre-existing
  action path is byte-unchanged, proven by `test_vpc_bridge_builders`) plus two new builder
  functions. `strategy_engine_profileA.py` is byte-unchanged from `main` (confirmed via
  `git status`); the full suite proves A behavior is untouched.
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
| `bridge_traderspost.py` (edited, ADDITIVE) | `build_vpc_entry`, `build_vpc_stop_replace`, and an additive `_wire` `"stop"` branch. |
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

## Suite counts (before → after)

- Before (baseline on branch point): **885 passed, 1 skipped** (886 collected).
- After (initial build): 931 passed, 1 skipped.
- After (cross-audit remediation F1/F2/F3 + hardening): **942 passed, 1 skipped** (see
  `reports/vpc_lane_build/full_suite.txt`). VPC adds 51 fast unit tests + the parity/ARM tests; the
  pre-existing 885 remain green (Profile A unaffected). The single pre-existing skip (ARM B stub) is
  retained as a superseded historical scaffold; ARM B itself runs as a passing test.

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

## What REMAINS for MUST-AUDIT / BLOCKS-ARMING (Phase 4, operator-gated — NOT done here)

These are deliberately NOT improvised (risk-rule and locked-config boundaries):

1. **Locked-config sizing (`vm` key)** — adding `vm` sizing to `config_eval_locked.py` /
   `config_funded_locked.py` and the config-hash firewall is FORBIDDEN to edit here; it is a
   go-live-recert.sh-gated change. `VpcLaneRiskBook` reads caps/budget as constructor params so the
   locked config remains the single authority at arm time. BLOCKS-ARMING.
2. **`auto_live.py` lane registration** — the fourth `try/except`-isolated bar-dispatch block,
   `on_v_signal`, `_risk_gate("V", …)` threading, and confirming `_dp` sums A+B+V realized P&L, plus
   flatten-path/dashboard hardcoded-`{A,B}` audits. Additive wiring following Profile B's pattern;
   left OUT so this build cannot alter A behavior. BLOCKS-ARMING.
3. **Conflict-policy DEC** — opposite-direction A+VPC stacking is OBSERVED (not vetoed) by
   `flag_opposite_direction`; whether to block is an explicit operator DEC, not improvised. BLOCKS.
4. **Kill-switch semantics for an in-flight trail** — freeze vs allow tighten-only under kill is a
   new decision; the manager stands down on timeout but the kill interaction is a Phase-4 DEC.
5. **VPC causal-availability reachability (W1/W2-style)** — the truncation canary proves per-signal
   causality; the live-poll-latency reachability split (what fraction of 408 is catchable under real
   staleness gates) is an analysis MUST-TEST not yet run.
6. **Real-broker stop-replace wire field** — `build_vpc_stop_replace`'s `"stop"` payload key is
   CONFIRM-pending (TradersPost exposes only cancel + re-send; Tradovate order API banned on Apex).
   Safety logic is final; the exact wire mapping needs live-doc verification. BLOCKS live routing.
7. **ARM B over real 408-trade 1m slices** — ARM B is built on deterministic scenarios; extending it
   to drive the manager over the certified 408 trades' real 1m data is a MUST-AUDIT follow-up.
8. **Watchdog trail-churn reconciliation** — zero orphan false-positives across a paper-shadow
   session must be demonstrated (the rate-limit + never-naked design bounds it; the paper-shadow
   acceptance run is Phase-4).

Phase-4 activation is operator-gated via `go-live-recert.sh`. This build does NOT arm the lane.
