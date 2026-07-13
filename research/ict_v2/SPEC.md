# ICT V2 — Phase 2 Build Spec (v1.0)

**Author:** Fable (Trading CEO) · 2026-07-13 · Governs all Phase-2 builds.
**Canon:** vault `01 Projects/ICT V2/ICT V2 — Implementation Standard.md` (binding) · Charter · DEC-20260713-1840.
**Phase-1 basis:** `reports/ict_v2/01_phase1_implementation_review.md`.

## Mission of Phase 2

Build the **causal event engine**: every ICT concept as a versioned, lifecycle-managed, prefix-invariant event stream. **Engineering only — NO edge claims.** No PF, no win rate, no expectancy, no returns anywhere in Phase-2 code, tests, or reports. Semantic certification is the only output: the code provably implements the declared rules.

## Hard rules (violations = build rejected)

1. **New code only under `research/ict_v2/`**; tests under `research/ict_v2/tests/`. Zero modifications to production modules, `evidence/approvals/`, `.env`, configs, or the frozen framework at `~/trading-team/backtests/ict-nq-framework/` (import/read it, never edit).
2. **Causality contract on every emitted object:** `origin_time ≤ observed_at ≤ confirmed_at ≤ actionable_at` (+ optional `invalidated_at`). Detectors consume bars **incrementally** (streaming-first); a batch runner just feeds bars in order.
3. **Prefix invariance is mandatory and tested** for every detector (harness in `core/prefix.py`).
4. **No silent filters** — engines emit ALL candidates; every terminal outcome is a recorded event (e.g. a sweep that continues = `ACCEPTED_BREAKOUT`, never a discard). Rejections are data.
5. **All parameters in `core/config.py` as a versioned ParamSet** (`ICT_V2_PARAMS_V0`). v0 defaults below are RECORDED CONVENTIONS, not tuned values; no tuning in Phase 2 (surfaces are swept in Phase 5).
6. Full production suite (`python3 -m pytest -q` at repo root) must remain green; run it once at the end of your work package and report the tally.
7. Ambiguity at a strategy/certification boundary → STOP and return `BLOCKED — decision needed`. Do not guess.
8. Match surrounding code style; small clean modules; type hints; no new heavy dependencies (pandas/numpy/stdlib only; pandas is pinned `<3`).

## Data

Reuse the frozen framework's Databento NQ data + loaders (inspect `~/trading-team/backtests/ict-nq-framework/` — engine + models show how 5m/1m frames are loaded; model01 runs 5m signal frame with 1m truth). Import or thin-wrap the loader; never copy-modify data files. All timestamps tz-aware; internal convention: **UTC storage, America/New_York for session logic via zoneinfo** (never string re-localization — the D1c bug class).

## Module layout

```
research/ict_v2/
  __init__.py
  core/
    events.py        # CausalEvent (frozen dataclass), EventStore (append-only)
    clock.py         # SessionEngine: CME calendar, trade date, sessions, killzones, DST
    config.py        # ParamSet ICT_V2_PARAMS_V0, versioning
    prefix.py        # prefix-invariance + chunking-invariance harness
    runner.py        # batch runner: feeds bars sequentially to registered engines
  engines/
    swings.py        # methods A (symmetric), B (directional-change), C (trailing extreme)
    structure.py     # protected swings, BOS / CHoCH / MSS state machine
    displacement.py  # normalized displacement scorer
    levels.py        # level registry + salience COMPONENTS (no weights)
    sweeps.py        # sweep FSM (records SWEPT and ACCEPTED_BREAKOUT)
    zones.py         # FVG / IFVG / OrderBlock / Breaker lifecycles
    ranges.py        # dealing ranges (frozen anchors), premium/discount, OTE bands
    amd.py           # AMD finite-state machine
    opening_range.py # completed OR objects
    overnight.py     # overnight-inventory objects
  gated/
    orderflow.py     # OFI/depth interfaces — STUBS, raise DataGated (Court docket D1)
    smt.py           # formal SMT interface — STUB (ES data-gated)
    macro.py         # point-in-time macro calendar interface + CSV schema, no data yet
  parity/
    model01_canary.py  # reproduce the certified 581 Profile-A signals exactly
  tests/             # one test module per engine + core
```

## Core contracts

### CausalEvent (`core/events.py`)

Frozen dataclass: `event_id` (deterministic hash of type+instrument+origin+rule_version — NO uuid/random), `event_type`, `instrument`, `timeframe`, `origin_time`, `observed_at`, `confirmed_at`, `actionable_at`, `invalidated_at: Optional`, `price_low/price_high: Optional`, `rule_version`, `param_version`, `source_event_ids: tuple`, `attributes: Mapping`. Lifecycle changes append NEW events (`*_INVALIDATED`, `*_TESTED`, …) referencing the original via `source_event_ids`; never mutate. EventStore: append-only list + index by type/time; `history_through(T)` returns events with `confirmed_at <= T`.

### Prefix-invariance harness (`core/prefix.py`)

`assert_prefix_invariant(engine_factory, bars, cuts)`: for each cut T (default: 200 evenly-spaced + session boundaries), run a fresh engine over `bars[:T]`; its emitted history must equal the full run's `history_through(bars[T-1].close_time)`. Also `assert_chunk_invariant`: 1-bar-at-a-time vs random-chunk feeds produce identical stores.

### SessionEngine (`core/clock.py`)

zoneinfo `America/New_York`. Sessions v0 (must mirror model01's conventions where they exist — verify against its session tagging): `asia` 18:00–03:00 ET, `london` 03:00–08:00, `ny_am` 08:00–12:00 with killzone 09:30–11:30, `ny_pm` 12:00–16:00, overnight = 18:00→09:30. CME trade date (18:00 ET roll), maintenance break 17:00–18:00, holidays + early closes: reuse the bot's existing trading-calendar module if importable read-only, else a small static table 2021–2026 sourced from it. Every window derived from tz-aware ops; **grep-able ban on `tz_localize` over naive wall-clock strings.**

## Engine definitions (v0 pins)

**Swings** — A: pivot high `H_i ≥ max(left l)` and `> max(right r)`, l=r=3 default; `origin=i`, `confirmed_at=close(i+r)`. Reuse/wrap frozen `primitives.py` math where possible (import, don't copy). B: running extreme confirmed on reversal ≥ `max(8 ticks, 0.25×ATR20)`; confirmed at the reversal bar close. C: trailing extreme over last 20 completed bars (a level, not a pivot — distinct event type).

**Structure** — protected swing state per direction from method-A swings; `BOS` = 5m close beyond protected level in-state-direction; `CHoCH` = first counter-state close-break → state `TRANSITIONAL` (not auto-reversal); `MSS` = CHoCH ∧ displacement-qualified within 12 bars (mirror model01's MSS for the parity canary: close beyond most-recent opposing confirmed swing, W_MSS=12). Wick-vs-close is a param (`break_type`, v0=close).

**Displacement** — per completed bar emit score components: `body_vs_tod = |C−O| / σ_TOD`, `range_vs_atr = (H−L)/ATR20`, `close_location = (C−L)/(H−L)` directional, `volume_z` (20-bar). σ_TOD = median |5m return| for that time-slot over trailing 20 sessions (warmup: emit `DISPLACEMENT_WARMUP` events, never fabricate). Qualifying event `DISPLACEMENT_QUALIFIED` at v0 threshold body ≥1.5× mean-20 body (V1 convention, keeps parity). OFI/depth/spread fields present but `None` + flagged `data_gated`.

**Levels** — registry objects: PDH/PDL, PWH/PWL, session highs/lows (asia/london/ny_am prior), overnight H/L, completed OR H/L, confirmed method-A swings, equal highs/lows (≥2 extremes within 2 ticks, ≥5 bars apart, ≤3 sessions old; level price = outermost), round numbers (multiples of 100; 50 as param). Fields: `created_at/active_from/test_count/last_test_at/expires_at` (v0: 2 sessions for intraday levels, 5 for weekly) + **salience components recorded raw** (timeframe class, age, prominence = distance to nearest higher extreme, test count, roundness flag, equality count). NO salience weights in Phase 2. A touch (trade within 1 tick) emits `LEVEL_TESTED` and increments `test_count`.

**Sweep FSM** — per active level: `EXCURSION_OPEN` when trade goes ≥1 tick beyond; then within `h=3` bars (param family {1,3,6}): close back inside → `SWEEP_CONFIRMED` (rejection rule `close_back_inside` v0; variants enumerated but not all built); 2 consecutive closes beyond OR dwell > h bars → `ACCEPTED_BREAKOUT`; else `EXCURSION_TIMEOUT`. All three recorded with excursion depth (ticks), duration, and reclaim speed in attributes — these feed Phase 3.

**Zones** — FVG: bullish `Low_C > High_A`, zone `[High_A, Low_C]`, min 4 ticks v0, `origin=B`, `confirmed_at=close(C)`; lifecycle `CREATED/TESTED/INVALIDATED/EXPIRED` (invalidation v0 = close through far boundary; expiry 20 bars… v0=full session, param). IFVG: created ONLY at FVG invalidation event; the full label graph is recorded (every FVG's terminal state is an event — no silent drops). OrderBlock: on `DISPLACEMENT_QUALIFIED`+MSS/BOS, scan back ≤10 bars for last opposing candle; `origin=that candle`, **`created_at=confirmed_at of the qualifying event`**; zone = full candle range v0 (body as param); `first_eligible_retest_at > created_at` enforced structurally. Breaker: created at OB invalidation (close through far boundary). Overlap/dedup: zones from the same qualifying impulse share an `impulse_id` attribute (confluence must count an impulse once — enforced later, recorded now).

**Ranges/OTE** — DealingRange objects from whitelisted anchors only: completed prior session, completed prior day, latest completed method-B leg. Frozen at creation; re-anchoring = new object. Emit `location(P)=(P−L)/(H−L)` on demand; OTE band [0.62, 0.79] + two control bands [0.38,0.55] and [0.80,0.97] emitted alongside (controls for Phase 5; no interpretation now).

**AMD FSM** — `SEARCH` → `ACCUMULATION_ACTIVE` when rolling 12-bar range < 0.6×ATR20 for ≥6 bars (range then FROZEN) → `EXCURSION` on boundary break → `MANIPULATION_CANDIDATE` if reclaim within 6 bars → `DISTRIBUTION_CONFIRMED` on opposite `DISPLACEMENT_QUALIFIED` within 12 bars. Every state has a timeout → `AMD_FAILED_<state>`. Retrospective labelling structurally impossible (each transition is an event at its own confirmed_at).

**Opening range** — 09:30–09:45 ET v0 (duration param {5,15,30}); `OR_COMPLETED` event at 09:45 close carries final H/L; running values are separate `OR_DEVELOPING` events explicitly flagged.

**Overnight inventory** — at 09:30: overnight H/L/range, gap vs prior RTH close, overnight net return.

## Parity canary (`parity/model01_canary.py`) — the dual-implementation gate

Run the V2 pipeline (swings A 3/3, model01-matching params) over the certified Profile-A dataset and reproduce the **581 certified signals** exactly: sweep bar, MSS bar, entry/stop/target/direction to the cent. Oracle: frozen `model01._detect` / fork_a's `verify_surface_at_mss.py` outputs (`reports/fork_a/` artifacts). Mismatches = build defect (or documented, justified semantic difference — each one listed explicitly in the Phase-2 report; target 581/581).

## Test requirements (per engine)

Synthetic bars (hand-built, deterministic): minimum valid case · near-miss · boundary equality · duplicate extremes · session boundary · DST transition day · gap/missing bar. Plus: prefix invariance (every engine) · chunk invariance (every engine) · event-id determinism · no-mutation (store append-only) · `actionable_at ≥ confirmed_at` asserted globally in EventStore. Zone/FSM engines: full lifecycle walk incl. every failure/timeout branch.

## Work packages (build order)

- **WP-A (foundations):** `core/*` complete + package skeleton + `gated/*` stubs + tests. Everything else depends on the contracts here — build them exactly as specified.
- **WP-B (detectors):** `engines/swings.py`, `structure.py`, `displacement.py`, `levels.py`, `opening_range.py`, `overnight.py` + tests.
- **WP-C (state machines/zones):** `engines/sweeps.py`, `zones.py`, `ranges.py`, `amd.py` + tests.
- **WP-D (certification):** `parity/model01_canary.py` (581/581), integration run over ≥1 full month of real 5m data (event counts + store hash recorded, NO performance stats), full-suite green, Phase-2 report at `reports/ict_v2/02_phase2_semantic_certification.md`.

Each WP ends with: its tests green, full repo suite tally reported, ≤200-word summary + file paths.
