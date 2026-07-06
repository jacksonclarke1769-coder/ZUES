# 07 — VPC Execution Lane Requirements (certification-prep spec)

RESEARCH ONLY. LIVE HOLD ACTIVE. This is a documentation/planning artifact only — **no code in this
repo was modified to produce it.** It reads the existing Profile B lane (the closest live precedent
for "a second strategy lane bolted onto Profile A") to scope what a VPC live lane would require.
Nothing here authorizes building it; per E_final_verdict.md item 15, VPC is not eligible to arm and
this is explicitly flagged as a **certification event**, not a routine feature add.

## How the Profile B lane is actually plumbed today (read in full)

- **Engine registration:** `auto_live.py:142` — `self.b_engine = ProfileBEngine()` constructed once in
  `LiveAuto.__init__`, alongside `self.b_tracker` (paper-P&L/journal/Telegram tracker,
  `auto_live.py:143-144`).
- **Bar feed / dispatch:** every closed 5m bar is fanned out to all lanes inside the single
  `_engine_bar()` callback (`auto_live.py:1207-1230`). Order of operations, verbatim:
  1. `runner.bot.process_bar(...)` — Profile A signal path (`auto_live.py:1215`).
  2. `auto.b_engine.add_bar(bts,...)` → `auto.b_engine.latest_signal()` → if not None,
     `auto.on_b_signal(_bsig, bts, _bar["i"])` — **wrapped in its own `try/except`, with the comment
     "B never breaks A"** (`auto_live.py:1216-1224`).
  3. `auto.on_m_bar(bts,...)` — Profile MOMENTUM lane, a no-op unless wired (`auto_live.py:1225`).
  A VPC lane's most natural insertion point is a fourth block in this same function, `try/except`-
  isolated exactly like B and MOMENTUM, so a VPC engine exception can never block Profile A.
- **`on_decision`:** there is no single shared `on_decision` entry point — each lane has its own
  `on_a_signal`-equivalent inline in `process_bar`/`_engine_bar` (A), `on_b_signal`
  (`auto_live.py:478-588`), and `on_m_bar` (`auto_live.py:591+`). A VPC lane would add `on_v_signal`
  following the `on_b_signal` shape.
- **Bracket placement:** `on_b_signal` builds a `b_common` payload dict and dispatches to one of three
  order builders depending on the resolved exit model: `BP.build_entry` (single OCO bracket,
  `order_type="limit"` default, `bridge_traderspost.py:87-108`), `BP.build_entry_exit3` (two-leg
  partial, also `order_type="limit"` default, `bridge_traderspost.py:139+`), or the SINGLE_1R full-qty
  variant (`auto_live.py:519-529`). All three assume a **resting limit order at a known price** — none
  of them model a market-entry-then-manage-a-moving-stop strategy.
- **EXITLOCK:** `runtime_config.resolve_exit_model()` gates which exit model a given `mode` may run,
  independent per profile (A gets `_rxm(self.mode, requested=self.exit_override)`; B has its own
  `resolve_b_exit(self.mode)` from `config_defaults.py:175-185`). Any blocked resolution surfaces as
  `self._dlog("blocked", "exitlock", ...)` for both A (`auto_live.py:460`) and B
  (`auto_live.py:575`) — same pattern, per-profile tag.
- **Telemetry hooks:** `exec_telemetry.py`'s `on_decision`/`on_webhook_result`/`on_fill_confirmed`/
  `on_missed`/`on_cancelled` and `fill_telemetry.py`'s `on_decision`/`on_order_sent`/`on_bar`/
  `on_fill_confirmed`/`on_order_resolved` all take a free-text `strategy=` parameter
  (`exec_telemetry.py:74`, `fill_telemetry.py:132,147,172`) — **already generic across N lanes**, not
  a hardcoded A/B enum.
- **Journal:** both `journal.Journal.log(...)` (`journal.py:80`) and `trade_journal.TradeJournal`
  (`trade_journal.py:72`) take a free-text `profile=` field — already generic.
- **Watchdog / position parity:** `check_position_parity(broker_net, belief_expected, grace_active)`
  (`watchdog.py:107`) compares a single **aggregate net position** against a single
  `belief_expected` number published by `watchdog_belief.publish_belief()`
  (`watchdog_belief.py:79-99`), which itself reads `expected_net = rb.expected` from the
  `ReadbackSentinel` (`live_readback.py:117` `on_entry(side, qty)` — accumulates net position
  regardless of which strategy called it). **This is already strategy-agnostic by design** — A, B,
  and MOMENTUM all call the same `readback.on_entry(side, size)` (`auto_live.py:446,559`), and the
  watchdog never needs to know how many lanes exist, only the resulting net. A VPC lane slots in by
  calling the same `on_entry`/`on_partial_or_exit`/`on_flat` methods B already uses.

## The one structural gap that matters most: VPC has no live trailing-stop precedent anywhere

Grep across every live-execution file in this repo for a `trail` implementation outside backtest/
research code returns nothing (`strategy_engine_profileA.py`, `strategy_engine_profileB.py`,
`profile_momentum_engine.py`, `bridge_sender.py`, `bridge_traderspost.py` — zero hits). The closest
precedent, Profile MOMENTUM, is a **flip/flatten** strategy (`build_momentum_entry`,
`bridge_traderspost.py:112-133`: one wide catastrophic protective stop, no fixed target, exits only on
signal flip or EOD — never re-prices the stop). VPC's backtest, by contrast, **re-computes and
ratchets its stop every single closed bar** (`nq_vwap_pullback.py:107-115`: `newstop = peak - trail_atr
* A[j]; stop = max(stop, newstop)`). `bridge_sender.py` has `send`, `send_exit3`, and `flatten`
(cancel+exit) — **no modify/replace/amend-stop function exists anywhere in the order-building or
sending code.** Making VPC's live behaviour match its certified backtest therefore requires either:
(a) a genuinely new cancel-and-resend-stop loop driven off every closed 5m bar (bot-side trail
management, most faithful to the certified logic), or (b) delegating to a broker-native trailing-stop
order type if TradersPost/Tradovate exposes one (unverified in this repo — no existing code path uses
one). **This is new work with no copy-adapt source in the codebase**, unlike everything else in this
table.

## WHAT-EXISTS / MUST-BUILD / MUST-TEST / MUST-AUDIT / BLOCKS-ARMING

| Area | WHAT-EXISTS (copy-adapt source) | MUST-BUILD | MUST-TEST | MUST-AUDIT | BLOCKS-ARMING? |
|---|---|---|---|---|---|
| Signal parity | `test_signal_parity.py` pattern: live engine bar-by-bar vs full-history backtest, exact-match assertion | `ProfileVEngine` class (streaming `add_bar`/`latest_signal`, modelled on `ProfileBEngine`'s pure bar-state design, `strategy_engine_profileB.py:16-88`) that reproduces `vpc_signals()`+`simulate_day()` incrementally | A `test_vpc_signal_parity.py` analogous to `test_signal_parity.py`/`test_profile_b_parity.py` — live streaming engine vs `nq_vwap_pullback.backtest()` over the same window, zero-mismatch assertion | Confirm the streaming re-implementation preserves the exact `armed_long`/`armed_short` state-machine semantics (multi-bar arm-then-trigger, `nq_vwap_pullback.py:63-74`) — a subtle re-implementation bug here is the single highest-risk defect class (cf. the D1c timestamp bug) | **YES** |
| Causal timestamp proof | `vpc_apex_eval_sim.py:48,73` already derives `ts=idx[ei]` from the tz-aware index, never a date+time string — the exact pattern INC-20260706-1141 mandates (INC-20260706-1141:30) | Nothing new — the live engine must inherit this discipline: signal timestamps come from the bar's own tz-aware index/argument to `add_bar(ts,...)`, **never** reconstructed via `f"{date} {time}"` string parsing (the defect class that hit `strategy_engine_profileA.latest_signal()`, `strategy_engine_profileA.py:61,68`) | A dedicated tz-integrity/timestamp-source assertion test for the VPC engine, following the incident's own prevention item: *"Add a tz-integrity assertion (string-time vs index-time equality) test class for every timestamp handoff"* (INC-20260706-1141:33) | Confirm `ProfileVEngine.latest_signal()` never touches `.astype(str)` or re-localizes a parsed string anywhere in its implementation | **YES — this is the exact defect class that produced the current LIVE HOLD; non-negotiable** |
| Entry/stop/target order types | `build_entry`/`build_entry_exit3` (limit-bracket, A/B pattern, `bridge_traderspost.py:87,139`); `build_momentum_entry` (market-entry, one wide stop, no target, `bridge_traderspost.py:112-133`) — the closer analog for VPC's *entry* leg only | A new order-building path: **market entry** (like MOMENTUM) but **with an initial protective stop AND a live-managed trailing stop** (unlike MOMENTUM's static wide stop) — no existing function does both. Likely needs a new `build_vpc_entry` (market fill, initial `entry ∓ 2.5×ATR` stop) plus a new stop-replace mechanism (see gap above) | Compare live fill price vs modelled next-bar-open assumption (the A6 "chase-class" stress already quantifies the risk this test should re-verify live, A6_salvage_fill_slippage_stress.md:115-126,150) | Confirm the live order never silently degrades to a resting limit at the signal-bar close price (that would NOT match the certified next-bar-open market fill and would invalidate the backtest-live correspondence) | **YES** |
| Sizing/cap enforcement | `_tier_spec(tier)` returns a dict keyed by profile letter (`am`, `bm`, `mm`) consumed via `spec.get("bm", 0)` fallback pattern (`auto_live.py:39,332,495`) — trivially extends to a `vm` key | Add a `vm` (or similar) key to the tier spec tables in `config_eval_locked.py`/`config_funded_locked.py` and thread it through `_tier_spec`/`self.p3.size(...)` the same way B's `bm` is threaded | Confirm P3-brake sizing (`self.p3.size(spec["am"], spec.get("bm", 0))`) is extended correctly to a 3-way size call without silently zeroing V under existing 2-arg signatures | Re-verify the `A_RISK_BUDGET_USD=1200` comment in `config_defaults.py:105-112` is stale (superseded by INC-20260706-1141 per the incident itself) before using it as a VPC sizing anchor | **YES — sizing budget must be re-derived on the honest baseline, not copied from the stale $1,200 comment** |
| Max-2/day | Already enforced **inside VPC's own backtest** (`taken >= max_trades` check, `nq_vwap_pullback.py:90`, locked `max_trades=2`) | The live `ProfileVEngine` must carry the identical per-day counter/reset-on-new-day state (straightforward copy-adapt of the backtest's own `taken`/day-loop logic into the streaming class) | Parity test (above) inherently covers this — a live engine that fires a 3rd same-day signal would show up as a parity mismatch | None beyond the parity test | No (covered by parity test) |
| Conflict rules with A | **None exist today** — A and B currently run fully independently with no direction-conflict logic; `overlap_gate.OverlapGate.on_open("A"/"B", direction)` (`overlap_gate.py:15,52`) tracks concurrent-open state for monitoring/overlap accounting but does not appear (from what was read) to block opposite-direction stacking | A same-instrument (MNQ, netting account) same-direction-vs-opposite-direction policy decision: does VPC size ADD to an open Profile A position (compounding directional risk) or does the account's native netting silently offset it (reducing effective size without either strategy's model accounting for the other)? This is a **business/risk decision**, not a coding task | A combined-position simulation (opposite-direction A+VPC same-instant) to quantify how often this occurs and what netting does to each strategy's own P&L attribution | Decide and document whether `on_v_signal` should consult `self.overlap` to block/flag opposite-direction stacking, mirroring how `overlap_gate` is already fed by A and B | **YES — undocumented policy gap, must be an explicit DEC before arming** |
| $550 daily-stop sharing | Retrospective daily-stop check already spans "concurrent A+B brackets" by design intent, per the audit-R1 comment: *"The $550 daily stop is retrospective (books on exits) — it cannot stop concurrent A+B brackets from stacking more open risk than the account's remaining trailing-DD cushion"* (`config_defaults.py:99-101`); the PROSPECTIVE risk gate (`_risk_gate`) is called per-lane before every A and B order (`auto_live.py`, e.g. B at line ~495-503) | Thread the same `_risk_gate("V", ...)` call into `on_v_signal`, exactly as B does at `auto_live.py:499` — mechanically a copy | Confirm the retrospective `$550` circuit-breaker check (`auto_live.py:1284-1291`, `_dp <= -abs(auto.daily_stop)`) already sums ALL profiles' realized P&L for the day (need to verify `_dp`'s computation includes a V leg once wired — not confirmed in this reading, flagged as MUST-VERIFY) | Verify the cushion-fit prospective gate (`OPEN_RISK_CUSHION_FRAC`, `config_defaults.py:113`) correctly sums A+B+V *open* risk, not just the lane being sized | **YES — must verify `_dp` aggregation before arming a 3rd lane** |
| DLL/EOD interaction | `apex_eval_eod.eval_eod` (EOD-drawdown ratchet, imported by every VPC eval-sim harness, `vpc_apex_eval_sim.py:17`) already models VPC trades exactly as it models A trades — no VPC-specific DLL logic needed at the sim level | Live-side: confirm the live EOD-flatten (`flatten_guardian.py`/`ops_flatten.py`, not read in this pass) flattens ALL open lanes, not just A/B by name | A live-mode dry run confirming a VPC position gets flattened by the existing EOD-flatten path without name-specific logic excluding it | Grep the flatten path for any hardcoded `"A"`/`"B"` profile-name filtering that would silently skip a `"V"` position | **YES if flatten logic is profile-name-filtered — unverified in this reading, must check before arming** |
| Funded-mode config | `config_funded_locked.py` tier dicts (`"Apex-50K"`, `"Apex-50K-scaled"`) key sizing by `am`/`bm`/`mm` (`config_funded_locked.py:29-32`) — same `vm`-key extension as sizing above | Add funded-mode `vm` sizing to the locked funded tier dicts, informed by the honest funded-combined result (`A@250/4 + VPC@200/2 → $8,567 E[payout], 0% observed bust`, C_combined_portfolio_test.md:36) rather than the earlier (now-superseded) $10,510/16.7%-bust `VPC@300/2` cell | Re-run `tools_recert_funded.py`-pattern funded lifecycle sim with the exact locked live sizing before promoting | Confirm funded config hash discipline (`test_funded_config_firewall.py`) covers the new `vm` keys once added — i.e. the firewall test must be extended to fingerprint the new config surface | **YES** |
| Telemetry/journals (fill/missed-fill/rejection) | Already generic (`strategy=`/`profile=` free-text fields throughout `exec_telemetry.py`, `fill_telemetry.py`, `journal.py`, `trade_journal.py` — see citations above) | Nothing new — call the existing hooks with `strategy="V"` (or similar tag), following the exact call shape `on_b_signal` uses (`auto_live.py:444-475` A / `551-588` B) | Confirm dashboard/report aggregation code doesn't hardcode an `{"A","B"}` set anywhere that would silently drop a V-tagged record (not verified in this reading — flag as MUST-CHECK, likely in `dashboard/` or `dashboard-v3/`) | Grep dashboard code for hardcoded profile enumerations before wiring V's telemetry | **YES if dashboard hardcodes {A,B} — unverified, must check** |
| Watchdog invariants (position parity, 2→3 lanes) | Already lane-agnostic by design — `check_position_parity` compares one aggregate net vs one `belief_expected` (`watchdog.py:107`, `watchdog_belief.py:89`), fed by a shared `ReadbackSentinel.on_entry` that all lanes already call (`live_readback.py:117`) | Nothing structural — VPC calls `readback.on_entry(side, size)` / `on_partial_or_exit` / `on_flat` exactly as B does | A watchdog-replay test (`test_watchdog_replay.py` pattern) exercising a 3-lane (A+B+V) concurrent-position scenario to confirm the aggregate-net invariant still holds under 3-way netting on one instrument | Confirm no hidden assumption of "at most 2 concurrent lanes" anywhere in belief-state code (not found in this reading, but not exhaustively checked) | No (structurally already generalized), but the replay test itself should be run before arming |
| Kill switch | `self.killed()` check gates both A and B entries identically (`on_b_signal`'s `kill = self.killed(); if kill: ...`, `auto_live.py:485-488`; A's equivalent not shown here but same pattern implied by symmetry) | Nothing new — `on_v_signal` calls the same `self.killed()` gate | Confirm a kill-switch event during an OPEN VPC trailing-stop-management cycle correctly halts further stop updates too (not just new entries) — this is a genuinely new question because VPC, unlike A/B, has ongoing post-entry order activity (stop replacement), which the kill-switch was designed around "block new entries," not "stop managing an open trade's stop" | Explicitly decide: does kill-switch also freeze VPC's live trailing-stop updates (leaving a static stop) or does trail management continue even under kill (since it only ever tightens risk, never adds exposure)? | **YES — new decision, not covered by existing kill-switch semantics** |
| Dry-run/replay/paper-shadow harnesses | `paper_live.py`, `shadow_ledger.py`, `profile_b_tracker.ProfileBPaperTracker` (B's own paper-P&L/calendar tracker, imported at `auto_live.py:143`) — strong precedent for a `ProfileVPaperTracker` | A `ProfileVPaperTracker` (copy-adapt of `ProfileBPaperTracker`) for shadow/paper P&L before any live routing, plus a VPC row in whatever `replay_ab_12mo.py`-style multi-week replay harness is used pre-arming | A dry-run/paper period (ATHENA-II-style forward gates, referenced generally in the vault for other candidates) before live sizing — E_final_verdict.md's own recommended next action is re-lock certification, not immediate arming (E_final_verdict.md:63-68) | Confirm the paper tracker's fill-timing model matches the certified next-bar-open market-fill assumption (not a limit-fill assumption, unlike B's tracker which may assume B's limit-style fills — unverified, must check `ProfileBPaperTracker`'s fill logic before copying it verbatim) | **YES — must exist before any live routing per the operator's own stated gate** |
| Live-readiness checklist | `E_final_verdict.md:45-49` (answer 15) already states the operator-level checklist explicitly: live `latest_signal()` fix → re-lock certification of the chosen config → new DEC + explicit approval → "VPC live integration additionally needs execution-path work (second strategy lane in auto_live — it once existed for Profile B; certification event)" | This document IS the first draft of that execution-path scoping; the remaining checklist items are the operator's/Fable's, not a mechanical build task | N/A (checklist, not code) | N/A | **YES — every item above is subordinate to this checklist; nothing here is a green light** |

## Effort classification: copy-adapt vs genuinely new

**Copy-adapt from Profile B's lane (low effort, established pattern):**
- Engine construction + `try/except`-isolated bar dispatch in `_engine_bar()`.
- `on_v_signal` skeleton (kill-switch gate, entry-gate check, P3-brake sizing, prospective risk gate,
  `_dlog` audit trail) — structurally identical to `on_b_signal` (`auto_live.py:478-588`).
- Telemetry/journal calls (`strategy=`/`profile=` are already free-text).
- Sizing-tier key extension (`vm` alongside `am`/`bm`/`mm`).
- Watchdog/readback integration (`on_entry`/`on_partial_or_exit`/`on_flat` — already lane-agnostic).
- Paper/shadow tracker (`ProfileBPaperTracker` → `ProfileVPaperTracker`).

**Genuinely new (no existing live-code precedent, real engineering + certification work):**
1. **Live ATR-trailing-stop management** — the single biggest new piece. Nothing in
   `bridge_sender.py`/`bridge_traderspost.py` modifies a working stop order; VPC's certified edge
   depends on ratcheting the stop every closed 5m bar. This needs either a new modify/replace-order
   function or a broker-native trailing-stop integration, neither of which exists today.
2. **Market-entry order building with a *managed* (not static) protective stop** — `build_entry`/
   `build_entry_exit3` assume limit/resting orders; `build_momentum_entry` is market but has a single
   static stop and no target. VPC needs a genuinely new combination.
3. **Same-instrument opposite-direction conflict policy between A and VPC** — no existing code
   arbitrates this; it is an explicit risk/business decision, not a coding gap.
4. **Kill-switch semantics for an in-flight trailing-stop strategy** — existing kill-switch design
   assumes "block new entries," which is insufficient for a strategy with ongoing post-entry order
   activity.
5. **A VPC-specific signal-parity test** (mechanical to write, but a new artifact, not a copy of an
   existing passing test — it must be built and must pass before arming, per the exact same discipline
   that caught the A `latest_signal()` timestamp defect).

Everything else in the table is straightforward extension of an existing, working pattern (B's lane).
The trailing-stop live-management piece is the one item that has no analog anywhere in this codebase
and should be scoped/estimated as its own sub-project before any VPC arming timeline is set.
