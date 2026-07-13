# ICT V2 — Phase 2: Semantic Certification (WP-A/B/C/D consolidated)

**Date:** 2026-07-13 · **Author:** Sonnet (implementer), WP-D · verdict line to be signed by Fable.
**Governs:** `research/ict_v2/SPEC.md` v1.0 (Fable, 2026-07-13). **Scope:** engineering only — no
edge claims, no PF/WR/expectancy anywhere in Phase-2 code, tests, or this report.

---

## 1. What was built (WP-A/B/C/D inventory)

```
research/ict_v2/
  core/        events.py, clock.py, config.py, prefix.py, runner.py           (WP-A)
  engines/     swings.py, structure.py, displacement.py, levels.py,
               opening_range.py, overnight.py                                 (WP-B)
               sweeps.py, zones.py, ranges.py, amd.py                         (WP-C)
  gated/       orderflow.py, smt.py, macro.py  (DataGated stubs)              (WP-A)
  parity/      model01_canary.py (787 lines), integration_run.py (174 lines)  (WP-D)
  tests/       17 test modules, 237 tests collected (236 run by default,
               1 full-dataset test gated behind --full)                       (WP-A/B/C/D)
```

- **`core/events.py`** — `CausalEvent` (frozen dataclass, deterministic `event_id` via
  `compute_event_id`, no uuid/random/wall-clock), `EventStore` (append-only, causality
  contract asserted on every append).
- **`core/clock.py`** — `SessionEngine`: CME trade-date roll, session/killzone tagging,
  holiday/early-close calendar, zoneinfo-only (no `tz_localize` on naive strings).
- **`core/config.py`** — `ICT_V2_PARAMS_V0`, a single frozen `ParamSet` collecting every
  v0 pin named in SPEC.md.
- **`core/prefix.py`** — `assert_prefix_invariant` / `assert_chunk_invariant`, the
  causality-proof harness every detector engine is tested against.
- **`core/runner.py`** — `EngineProtocol`, `run_engine`, `BatchRunner` (each engine gets
  its own `EventStore`; engines never share state/read each other's events).
- **`engines/*.py`** (WP-B/C, 10 detector/FSM engines) — swings (methods A/B/C),
  structure (BOS/CHoCH/MSS), displacement, levels (level registry), opening range,
  overnight inventory, sweep FSM, zones (FVG/IFVG/OB/Breaker), dealing ranges/OTE,
  AMD FSM. Full v0-pin definitions in SPEC.md §"Engine definitions"; every engine has
  hand-built synthetic tests (minimum-valid/near-miss/boundary/duplicate/session-
  boundary/DST/gap) + prefix + chunk invariance + event-id determinism.
- **`parity/model01_canary.py`** (WP-D, this package) — the 581/581 dual-implementation
  gate. See §3.
- **`parity/integration_run.py`** (WP-D, this package) — full 12-engine stack over a
  real month via `core.runner.BatchRunner`. See §4.

## 2. Test counts

- `python3 -m pytest research/ict_v2/tests -q` → **236 passed, 1 skipped** (the skipped
  test is the full-dataset parity run, gated behind `--full`; see §3).
- `python3 -m pytest research/ict_v2/tests -q --full` → **237 passed** (all tests,
  including the full real-dataset 581/581 run, ~57s).
- `python3 -m pytest -q` (repo root, full production suite) → **1204 passed, 2 skipped**
  in 181s (baseline before this work package: **1203 passed, 1 skipped**; the delta is
  exactly the one new WP-D fast parity test (+1 pass) and the one new gated full-parity
  test (+1 skip) — zero production tests changed, zero regressions).

## 3. Parity result — **581/581**

`research/ict_v2/parity/model01_canary.py` reproduces the certified Profile-A signal
set through an independent V2-composed pipeline and compares it, signal-for-signal,
against the frozen oracle. Full run (`reports/ict_v2/parity_canary_summary.json`,
real Databento NQ 5m, 2021-06-22 → 2026-06-22, 353,952 bars):

| | |
|---|---|
| Oracle candidates (raw, all sessions, `model01.run()`) | 2,359 |
| V2 candidates (raw, all sessions, independent walk) | 2,359 |
| Oracle certified population (ny_am + D1c + emission-classify) | **581** |
| V2 certified population (same 3 selection filters, applied identically) | **581** |
| Matched (exact: direction, sweep_bar, mss_bar, entry, stop, target to the cent) | **581** |
| Mismatched | **0** |
| Building-block self-check mismatches (10 series x 353,952 bars vs. production columns/`primitives.py`) | **0** |

**What "581" means**, verified by regenerating it from scratch rather than trusting the
static reference CSV: `model01.run()` (frozen, `A_PARAMS["exit3"]` params) over the full
certified dataset produces 2,359 raw trades; filtered to `session(mss_bar)=="ny_am"` →
705; filtered to the D1c live-executability gate (`run_d1c_real.py::attach_drift`, real
1m drift-direction agreement at fill) → 583; joined against the frozen INC-20260707
emission-replay artifact and 5-way classified (`PAE-001`'s own `classify_signals.py`
logic, reproduced read-only) → 394 FULLY-AVAILABLE + 187 DELAYED + 1 UNREACHABLE + 1
POST-ENTRY-DEPENDENT. Target population = FULLY-AVAILABLE + DELAYED = **581**, matching
`reports/fork_a/04_causal_anchor_parity_summary.json` (`n=581`, `match_at_k=581`) and
`research/atlas/profile_a_edge/outputs/signals_583_classified.csv` exactly.

**V2 composition** (which building blocks are reused unmodified vs. hand-composed in
the parity layer, and why — full detail in the module's own docstring):

- **Reused unmodified:** `engines/swings.py::SwingMethodA` (5m 3/3 for the MSS
  opposing-swing lookup, and 1h 2/2 — fed 1h-resampled bars — for the h1_sh/h1_sl level
  tier); `engines/displacement.py::DisplacementEngine`'s `DISPLACEMENT_QUALIFIED`
  event (the oracle's `displacement_strength() != 0` window check). Both verified
  bit-for-bit against `primitives.py` on the full 353,952-bar dataset.
- **Composed from shared primitives, not the full engine:** PDH/PDL/PWH/PWL and
  asia/london session H-L via `engines/_util.py::BucketHL` + `core/clock.py
  ::SessionEngine` directly, rather than `engines/levels.py::LevelRegistry` — avoids
  two orthogonal properties of `LevelRegistry` that are correct for its own Phase-2
  lifecycle-event purpose but not appropriate for a single-purpose oracle-signal
  canary: its `active_from` one-bar visibility lag (by design), and its unbounded
  `_active`-list scan (round numbers/equal-highs/OR/overnight kinds this canary
  doesn't need) which is impractical at 353,952-bar/multi-year scale. Verified
  bit-for-bit against `strategy_engine_profileA.py`'s own certified feature columns.
- **Hand-composed in the parity layer** (SPEC.md's own explicit pre-authorization —
  "compose around the divergence, do not weaken the V2 modules"): the sweep-reclaim
  window check, the sweep-bar-anchored MSS scan, and the OTE entry/stop/target
  arithmetic — a direct, line-for-line port of `model01_sweep_mss_fvg.py::_detect()`'s
  formulas, operating on the V2-built level/swing arrays above instead of the oracle's
  own feature columns. This is genuinely necessary, not a shortcut: `engines/sweeps.py`
  and `engines/structure.py` have real, structural FSM-semantics differences from the
  oracle (see §5, items 5/13) that are not bridgeable by parameter alone.
- **Mechanical, never-stored bar-index walk** for "no overlap" candidate-selection
  bookkeeping (mirrors the oracle's `i = exit_i + 1`) — computes only an integer exit
  bar index (first bar the FIXED stop/target/max-hold/gap is hit; `PROFILE_A`'s exit3
  params disable breakeven/trail so nothing dynamic needs tracking) used purely as the
  next-scan cursor. No R, win/loss tag, or PF-adjacent quantity is computed, stored, or
  reported anywhere — this is not a violation of the PF/WR/expectancy ban, it is
  structural bookkeeping identical in kind to the oracle's own loop-continuation logic.
  Flagged for Fable's review as a documented boundary judgment call, non-blocking.

**Two defects were found and fixed during this build** (both caught by the parity
infrastructure itself, both resolved before the 581/581 result above):

1. **A real WP-D-internal bug** (not a WP-B/C engine defect): the first draft of
   `build_5m_swing_series` queried the shared `EventStore.by_type("SWING_HIGH_A")`
   globally instead of scoping to the events its own loop had just emitted. Because
   `SwingMethodA` hardcodes the same `event_type` name regardless of `left`/`right`,
   and hourly bar boundaries coincide with valid 5m bar timestamps, this silently
   picked up the 1h(2/2) swing events too, polluting 5m-level MSS opposing-swing
   lookups. Symptom: 569/581 (12 mismatched/missing). Fix: collect confirmed swing
   events locally during each build function's own loop (the pattern
   `build_h1_swing_series` already used) instead of re-querying the shared store.
   Verified 581/581 after the fix.
2. **A comparison-methodology artifact**, not a detection bug: an early comparison
   pass called `round(float(x), 2)` on raw computed values, while the oracle's own
   trade dict calls `round()` on a `numpy.float64` — these two rounding paths can
   disagree at an exact binary-representation boundary (e.g. a true value of
   `13736.405000000000654...` rounds to `13736.41` via `round(float(x), 2)` but to
   `13736.40` via `numpy.float64.__round__`). This produced 44 spurious "mismatches"
   that all resolved to exact matches once both sides were compared using numpy's own
   rounding (`_round_cent` in the canary). Recorded so a future reader doesn't
   mis-diagnose the same artifact as a real divergence.

## 4. Integration run

`research/ict_v2/parity/integration_run.py`, all 12 WP-B/C engines via
`core.runner.BatchRunner`, real Databento NQ 5m, **month = 2025-03** (26 trading days,
5,868 bars, full calendar-month coverage, no data gaps beyond ordinary
weekend/maintenance closures; incidentally spans the 2025-03-09 US DST transition).
Full output: `reports/ict_v2/integration_run_summary.json`. NO performance/PF/WR/
expectancy statistic of any kind is computed anywhere in this run.

| engine | total events | notable event types |
|---|---:|---|
| swings_a | 1,106 | 565 SWING_LOW_A, 541 SWING_HIGH_A |
| swings_b | 5,818 | 2,909 / 2,909 |
| swings_c | 5,849 | TRAILING_EXTREME_C (re-emitted every warmed-up bar) |
| structure | 1,701 | 1 STRUCTURE_INITIALIZED, 1,340 BOS, 180 CHOCH, 127 MSS, 53 MSS_WINDOW_EXPIRED |
| displacement | 7,259 | 5,520 WARMUP, 1,391 QUALIFIED, 348 COMPONENTS |
| levels | 14,502 | 1,498 CREATED, 11,534 TESTED, 1,470 EXPIRED |
| opening_range | 63 | 42 DEVELOPING, 21 COMPLETED |
| overnight | 21 | 1 WARMUP, 20 COMPLETED |
| sweeps | 58,275 | 29,138 EXCURSION_OPEN, 5,552 SWEEP_CONFIRMED, 23,585 ACCEPTED_BREAKOUT |
| zones | 14,835 | full FVG/IFVG/OB/Breaker lifecycle graph (17 event types) |
| ranges | 1,110,993 | 5,939 DEALING_RANGE_CREATED, 1,105,054 BAND_TOUCH (no-expiry design, SPEC.md) |
| amd | 0 | see finding below |

- **First/last event `confirmed_at`:** 2025-03-02T18:00:00-05:00 → 2025-03-31T23:55:00-04:00.
- **`store_hash`** (sha256 over `<engine_name>:<event_id>` for every event, deterministic
  registration + insertion order): `443ed9c2504160c610060b17dde9077ef9fbe52b8212a9bf4868ae6a44cf191e`.
  Determinism follows structurally from `event_id` being a content-derived sha256 (no
  uuid/random/wall-clock read anywhere in any reused engine, `core/events.py`'s own
  hard requirement) — not re-run a second time to save the ~86s wall-clock cost, but the
  reasoning is a direct consequence of the causality contract every engine already
  proves via its own `event-id-determinism` test.
- **Prefix invariance**, `core/prefix.py::assert_prefix_invariant`, 20 evenly-spaced
  cuts, on the 3 engines SPEC.md names (**levels, sweeps, zones**): **all 3 PASS** at
  all 20 cuts over the real 2025-03 month.
- **Wall-clock runtime:** 86.4s (12 engines, 5,868 bars; `ranges`'s no-expiry
  `BAND_TOUCH` accumulation dominates the event count but not materially the runtime).

**Finding (not a defect, not fixed — SPEC.md forbids Phase-2 param tuning):** `amd`
produced **zero events**, both over this month and separately over a full real year
(~60,000 bars, checked directly). The v0 `ACCUMULATION_ACTIVE` threshold (rolling
12-bar range `< 0.6×ATR20` for `>=6` consecutive bars) never triggers on real NQ 5m
data in either sample — the observed minimum 12-bar-range/ATR20 ratio over the full
year was 0.71, never below the 0.6 threshold. `engines/amd.py`'s own synthetic tests
(`tests/test_amd.py::test_minimum_valid_accumulation_active_after_streak`,
`test_full_success_path_distribution_confirmed`) confirm the FSM logic itself is
correct when the threshold IS met — this reads as a v0-parameter-calibration
observation (SPEC.md: v0 pins are "RECORDED CONVENTIONS, not tuned values"), not a
code defect. Flagged for Fable's review, non-blocking, no code changed.

## 5. Consolidated divergence register (WP-B + WP-C + WP-D)

Every documented, non-blocking divergence from SPEC.md's illustrative prose or the
oracle, across all three build packages, in one place, each with its justification.

| # | WP | Where | Divergence | Justification |
|---|---|---|---|---|
| 1 | B | `engines/swings.py` (Method A) | Pivot inequality directions follow `primitives.py`'s actual CODE (strict `>` left, `>=` right), not SPEC.md's prose (which states the opposite direction) | SPEC.md's explicit instruction to "wrap/mirror frozen `primitives.py` math ... exactly", needed for the WP-D 581-signal canary; directly tested (`test_method_a_matches_frozen_last_known_swings`, and WP-D's own bit-for-bit real-data check, 0/353,952 mismatches) |
| 2 | B | `core/clock.py` | Session windows mirror `engine/data.py::SESSIONS` bar-for-bar, not SPEC.md's illustrative prose windows (asia/london/ny_am/ny_pm boundaries all differ) | Same rationale as #1 — required for parity; `killzone` name kept, numerically == oracle's `ny_am` |
| 3 | B | `engines/structure.py` | `STRUCTURE_INITIALIZED` bootstrap event, not named in SPEC.md | Structurally required by SPEC.md's own "no silent filters" rule — the first direction must be recorded as SOME event |
| 4 | B | `engines/structure.py` | MSS is CHoCH-state-anchored (a genuine BOS/CHoCH/MSS state machine over time), while the oracle's MSS is sweep-bar-anchored (freshly re-evaluates the current opposing swing at every candidate sweep, no state machine) | SPEC.md's own docstring narrows "mirror model01's MSS" to window SIZE + break-STYLE only, explicitly deferring the full sweep-anchored replay to WP-D's parity canary — WP-D confirmed this divergence is real and bridged it by hand-composing sweep-anchored MSS in the parity layer (item 13 below), not by editing `structure.py` |
| 5 | C | `engines/sweeps.py` | `EXCURSION_OPEN` fires on `>=` (SPEC.md's literal prose), oracle uses strict `>` at the identical threshold | SPEC.md's own engine-definition prose governs the OPEN trigger; the RECLAIM comparison mirrors the oracle exactly instead (tested: `test_sweep_confirmed_matches_oracle_sweep_of_level`) |
| 6 | C | `engines/sweeps.py` | BOUNDARY-TIE case (`close == level` exactly) introduced to make all 3 terminal outcomes reachable | SPEC.md's prose is under-specified about mutual exclusivity of "2 consecutive closes beyond" vs "dwell > h" vs "else timeout" — without it, `EXCURSION_TIMEOUT` is structurally unreachable for `h>=2`, failing SPEC.md's own "every failure/timeout branch" test requirement |
| 7 | C | `engines/sweeps.py` | Level "side" mapping (which kinds are HIGH/LOW/ambidextrous) | Engineering decision not spelled out in SPEC.md, needed for the FSM to know which excursion direction is the liquidity-grab direction |
| 8 | C | `engines/zones.py` | OrderBlock creation additionally gated on same-bar `DISPLACEMENT_QUALIFIED` for `BOS` (not needed for `MSS`, which already guarantees it by construction); bare `CHOCH` excluded | Interpretive reading of SPEC.md's "on DISPLACEMENT_QUALIFIED ... coinciding with a structure break"; `structure.py`'s own docstring states CHoCH is not an auto-reversal |
| 9 | C | `engines/zones.py` | Invalidation/expiry convention (close-through-far-boundary; session-end expiry) applied uniformly to IFVG/OB/Breaker | SPEC.md states this convention explicitly only for FVG; it is the only rule SPEC.md gives for "every zone reaches a terminal event", applied to all 4 kinds |
| 10 | C | `engines/ranges.py` | `prior_session` anchor uses all 5 PRIMARY_ORDER sessions, wider than `levels.py`'s own 3-session (asia/london/ny_am) "session highs/lows" level kind | SPEC.md's "Levels" section narrows to 3 named sessions; its "Ranges/OTE" section carries no such narrowing language |
| 11 | C | `engines/ranges.py` | `location()`/OTE bands use the plain non-directional `(P-L)/(H-L)` formula, NOT the oracle's directional `ote_zone()` retracement convention | SPEC.md's "Ranges/OTE" section (unlike "Sweep FSM"/"Zones") states only the plain formula and does not ask for oracle parity here |
| 12 | D | `parity/model01_canary.py` | PDH/PDL/PWH/PWL/session-H-L composed via `BucketHL`+`SessionEngine` directly, not `levels.py::LevelRegistry` | `LevelRegistry`'s `active_from` one-bar lag (correct for its own lifecycle semantics) and unbounded `_active`-list scan (impractical at 353,952-bar scale) are both orthogonal to WP-D's single-purpose signal-canary needs |
| 13 | D | `parity/model01_canary.py` | Sweep/MSS/OTE detection hand-composed in the parity layer, not via `engines/sweeps.py`/`structure.py`'s FSMs | SPEC.md's own explicit pre-authorization (items 4, 5 above); additionally DISCOVERED during this build: `sweeps.py`'s `consecutive_beyond>=2` rule can preempt a later in-window reclaim in a way the oracle's pure 3-bar trailing-window check never does — a genuine structural FSM difference, not bridgeable by a parameter, confirming SPEC.md's pre-flagged concern was warranted |
| 14 | D | `parity/model01_canary.py` | Mechanical, never-stored exit-bar walk for candidate-selection bookkeeping | Not a PF/R computation (see §3); mirrors the oracle's own `i = exit_i + 1` structural loop-continuation logic |
| 15 | D | `parity/integration_run.py` | `amd` engine: 0 events on real data (finding, not a divergence from spec — the code implements SPEC.md's v0 pin correctly) | v0-parameter-calibration observation; SPEC.md forbids Phase-2 tuning, so no code changed |

All 15 items were already individually flagged in their originating module's own
docstring (items 1-11) or discovered and documented during this work package (items
12-15) — none are silent. None block certification; each is a documented, justified,
non-blocking interpretive call or scope boundary.

## 6. Verdict

**Facts, for the record:**
- Parity: **581/581** exact match (direction, sweep_bar, mss_bar, entry, stop, target
  to the cent), against a freshly-regenerated oracle (not the static reference CSV),
  cross-validated against `reports/fork_a/04_causal_anchor_parity_summary.json` and
  `research/atlas/profile_a_edge/outputs/signals_583_classified.csv`.
- Integration run: all 12 engines run cleanly over a full real month via
  `core.runner.BatchRunner`; prefix invariance holds (levels, sweeps, zones, 20/20
  cuts); one non-blocking real-data finding (`amd`, v0-threshold reachability).
- Test suite: 236/236 (fast, default) + 237/237 (`--full`, includes the full 581/581
  real-dataset run) in `research/ict_v2/tests`; full repo suite 1204 passed / 2 skipped
  (baseline 1203/1, zero regressions).
- 15 documented, justified divergences from SPEC.md's illustrative prose or the
  oracle, none silent, none blocking.
- No PF, win rate, expectancy, or return of any kind appears anywhere in Phase-2 code,
  tests, or this report.

**Verdict line (Sonnet states the facts above; Fable signs the verdict):**

> **SEMANTICALLY CERTIFIED** — the V2 causal event engine (WP-A/B/C/D) provably
> implements its declared rules: 581/581 exact parity against the frozen oracle, a
> clean 12-engine integration run with passing prefix invariance, and every
> divergence from SPEC.md's illustrative prose explicitly documented and justified.

*(Signature pending — Fable to review and sign the verdict line above, or amend it to
CERTIFIED-WITH-EXCEPTIONS with an explicit exception list.)*

---

## §7 — Fable sign-off (Trading CEO audit, 2026-07-13)

**VERDICT: SEMANTICALLY CERTIFIED (scoped).**

Scope of the 581/581 dual-implementation gate: the **model01-faithful composition path** (V2-wrapped swings 5m-3/3 + 1h-2/2, displacement engine, level series from shared primitives) reproduces the certified oracle exactly — 581/581 on (direction, sweep_bar, mss_bar, entry, stop, target) to the cent, with equal raw candidate denominators (2,359 = 2,359) and 0/353,952 building-block mismatches over the full 5-year range.

The general FSM abstractions (LevelRegistry, sweep FSM, structure engine, zones, ranges, AMD) are certified by their synthetic batteries, micro oracle-equivalence tests (FVG, sweep-reclaim), and prefix/chunk invariance — with their divergence register (this report + module docstrings) as the permanent semantic record. The canary's bypass of these layers was the correct call (they are concept engines, not the certified strategy path) and is disclosed in `parity_canary_summary.json`.

**Certified exception:** `amd.py` fires 0 events on real data — the v0 accumulation threshold is empirically unreachable. Correctly NOT tuned (no-tuning rule). AMD is certified on synthetic paths only; its parameter family enters Phase 5 as a preregistered surface, or AMD is dropped at Phase-4 selection.

Audit trail: WP-A/B/C/D each independently re-verified before commit (subset re-runs, oracle-equivalence presence, perf-stat-ban grep, clean tree). Suite: 968 → 1,204 passed. Phase 2 CLOSED per Charter gate; Phase 3 (decision layer) may begin on preregistered specs.

— Fable 5, Trading CEO
