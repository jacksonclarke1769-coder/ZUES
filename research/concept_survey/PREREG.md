# PREREGISTRATION — ICT Concept Survey (artifact-controlled)

Status: DRAFT pending code-map citations (§6). Statistical protocol in §1–5 is FROZEN as of
2026-07-20 before any survey result is computed. Operator directive: survey ~6 ICT concepts ×
3 TFs × 2 directions as standalone triggers on NQ, last 2 years, and output a ranked shortlist
of statistically-survivable concepts — or an honest "nothing survived."

## 1. Test universe and N accounting

- Concepts (6): FVG, IFVG, Order Block, Breaker Block, Liquidity Sweep/Raid, MSS/BOS.
- Timeframes (3): 1m, 5m, 15m (signal TF; fills always walked on 1m).
- Directions (2): long, short.
- Variants: NONE. One fixed execution template per concept (§3). No entry/stop/target sweeps.
- **N = 6 × 3 × 2 = 36 tested strategies.** This N is fixed now; if any cell is added later it
  must be added to N before its result is looked at.

## 2. Data window and split

- Data: single-vendor Databento NQ 1m (certified file per §6; no other vendor touches any
  number — 241pt cross-vendor basis is a known false-result generator).
- Window: last 2 years of available data, [data_end − 24mo, data_end]. With data ending
  2026-06-22: 2024-06-22 → 2026-06-22.
- Split: **train = first 12 months, holdout = last 12 months.** Walk-forward by quarter inside
  the window is run additionally if the arena supports it cheaply (8 quarters, report per-quarter
  sign stability), but the binary gate is the 12/12 split.
- Selection happens on TRAIN only. Holdout is opened once, after the train ranking is frozen and
  written to disk (train_ranking.json committed before holdout run).

## 3. Fixed execution template (identical for all 36 cells)

- Entry rule per concept: single documented rule, fixed a priori in §6 (e.g. limit at FVG
  midpoint; OB mean-threshold retest; sweep close-back-inside market entry). No alternatives.
- Stop: the concept's structural invalidation (documented per concept in §6), fixed.
- Target: nearest opposite-side liquidity level ≥ 1 ATR away; fallback fixed 2R (OTE-spec
  compatible for comparability).
- One position at a time per cell; signals arriving while in-position are dropped.
- Fills: first-touch on 1m; stop-fills-first on ambiguous 1m bars; $1.00 round-turn cost;
  1-tick adverse slippage on entry and exit.
- Session: 24h detection; no session filter (session filtering would be a hidden variant).
- Max holding: EOD flat at session close of the signal's exchange day (prevents unbounded holds;
  same for all cells).

## 4. Statistical gates (all three required for the word "good")

### Gate A — holdout survival
Rank on train; report holdout as decisive. A cell must show holdout PF > 1.0 AND holdout
expectancy > 0 to proceed to Gate B. Train-strong/holdout-dead cells go to the graveyard,
labeled noise.

### Gate B — multiple-testing correction (Benjamini-Hochberg FDR, q = 0.10)
- Per cell, holdout p-value from a one-sided test that per-trade R expectancy > 0
  (stationary block bootstrap on the holdout trade sequence, 10,000 resamples, block length
  ~ weekly to preserve clustering).
- BH-FDR across all N = 36 cells at q = 0.10. A cell must have p ≤ its BH threshold.
- Report: N, the p-value ladder, the BH cutoff, and how many cells would clear PF > 1.2 under
  the global null (§ Gate C machinery) vs how many did — if close, the survey found nothing.

### Gate C — randomized-entry null (per surviving cell)
- 1,000 null runs: same number of entries, same TF, same direction, same execution template
  (stop distance drawn from the cell's own realized stop-distance distribution; target rule
  identical), but entry bars drawn uniformly at random from the cell's tradeable session bars in
  the holdout window.
- The real cell's holdout total R must exceed the 95th percentile of its null distribution.
  Otherwise: bar-selection luck, graveyard.

### Gate D (deployability, not significance) — live-achievable
Surviving cells re-run through the working freshness gate / emission path (certified walker).
Report live-achievable holdout stats and R-weighted suppression. A cell whose surviving edge is
entirely in suppressed trades is flagged NOT deployable as-is (note emit-at-fill recoverability).

## 5. Outputs

1. Ranked survivor shortlist (may be empty — acceptable).
2. Per-cell table: n, WR, PF, total R, expectancy, avg win/loss × {TRAIN | HOLDOUT |
   LIVE-ACHIEVABLE holdout} + null verdict + FDR clearance.
3. Correlation matrix: survivors' daily-R series vs each other AND vs Profile A / OTE frozen
   edges (fill-day overlap + return correlation). Decorrelation ranks above solo PF in the final
   ordering.
4. Graveyard list with cause of death (holdout collapse / null-indistinguishable / FDR miss).
5. Plain-language verdict. Commit + push; audit note in the register; vault BT note.

## 6. Concept definitions and code citations — FROZEN 2026-07-20, before any run

Shared fixed parameters (a priori, apply to all cells, never tuned):
- Swing pivots: fractal left=3 / right=3, confirmed only (known at pivot bar + 3 closes) —
  smc3/model01 convention.
- ATR: ATR(14) on the signal TF.
- Gap-size floor (FVG/IFVG): gap height ≥ 0.25 × ATR — tick-noise floor, set from instrument
  microstructure, not from this data.
- Displacement: candle body ≥ 2.0 × trailing-20 mean body (primitives.displacement_strength
  convention, fixed at 2.0).
- Limit-entry working-order lifetime: cancel after 20 signal-TF bars unfilled, or on structural
  invalidation, or EOD — whichever first.
- EOD flat: 16:55 ET on the signal's exchange day.
- Zone re-use: each detected zone (FVG/IFVG/OB/Breaker) trades at most once, first touch.

Per concept (detection cite → fixed entry → structural stop):

1. **FVG** — `apex-bot-share/engine/primitives.py:75 fvgs()` (causal, known at candle-3 close,
   form_idx). Entry: limit at gap midpoint (50%). Stop: 1 tick beyond far gap edge (gap fully
   closed = invalidation). Long = bullish gap, short = bearish.
2. **IFVG** — inversion logic per `backtests/zeus-occ-optimize/smc3/ifvg_probe.py` (causal
   close-through gates) / `zeus-ict-causal-v04/mirror.py:~565`. An FVG (rule 1 incl. size floor)
   whose far edge is closed through inverts; entry: limit at the inverted gap midpoint on retest
   from the inversion side. Stop: 1 tick beyond the opposite edge. Long = inverted bearish gap.
3. **Order Block** — `apex-bot-share/models/model01_sweep_mss_fvg.py:431–439` definition: last
   opposing candle immediately before a displacement candle (2.0× rule). Known at displacement
   bar close. Entry: limit at OB 50%. Stop: 1 tick beyond OB extreme. Long = bullish
   displacement after bearish OB candle.
4. **Breaker Block** — ⚠ NO existing causal detector in the library (survey finding). Implemented
   NEW for this survey, a priori, from the standard ICT definition: an Order Block (rule 3)
   whose extreme is later closed through (OB fails) within 100 signal-TF bars becomes a breaker
   in the breakout direction; entry: limit at breaker 50% on retest. Stop: 1 tick beyond the
   opposite breaker edge. Disclosed as newly written; no tuning.
5. **Liquidity Sweep/Raid** — `apex-bot-share/engine/primitives.py:94 sweep_of_level()`: wick
   ≥ 1 tick beyond the most recent confirmed swing level, close back inside within ≤ 3 bars.
   Entry: market at reclaim-bar close. Stop: 1 tick beyond the sweep extreme. Long = sweep of
   swing low.
6. **MSS/BOS** — `model01_sweep_mss_fvg.py:400–410` / `smc3_engine.py:217–240`: close beyond the
   most recent confirmed opposing swing (3/3 pivots). Entry: market at break-bar close. Stop:
   1 tick beyond the origin swing (last confirmed same-side swing preceding the break).

Data note (from code map): `apex-bot-share/engine/data.py::load_spine` points at the MIXED-vendor
`data/nq/` set — the survey harness must NOT use it. Load
`data/real_futures/NQ_databento_1m_5y.parquet` (2021-06-23 → 2026-06-22, 1,769,367 1m bars,
bar-open UTC index; same file certified in smc3/BASELINE.md and zeus-ict-causal-v04/SPEC.md)
directly and resample 5m/15m causally (label=left, closed=left, signal known at bar close).
Fill-walk machinery: reuse `zeus-occ-optimize/engine.py` intrabar stop-first conventions /
smc3 `run_backtest` helpers — no fresh fill semantics.

Prior-graveyard context (not re-tested here, cited for interpretation): smc3 sweep→BOS/FVG
composite = structurally breakeven on this exact data (BASELINE.md PF 1.036, −52.9R total);
IFVG close-through probe = KILL (no speed gradient). The survey measures the STANDALONE concepts
under a different, fixed template — results may legitimately differ; neither cites the other as
its verdict.

## 7. Certified machinery bindings (from code map, 2026-07-20)

- **Data loader (single-vendor rule):** `bot/nq-liq-bot/apex_eval_eod_databento.load_databento_5m`
  + 1m truth via `bot/nq-liq-bot/tools_1m_truth_recert.py` (`walk_1m`). NO `htf.build_features`,
  NO `D.load_spine` (Dukascopy) anywhere in the survey — the ~241pt cross-vendor basis
  (INC-20260707-freshness-gate-emission-gap.md §"1m-TRUTH WALK ISOLATION", vault) produced the
  PF-0.05 artifact; single vendor end-to-end is a hard rule.
- **Walker reference:** `bot/nq-liq-bot/databento_emission_replay.py` — pattern for
  surfaced/stale/suppressed classification; survey Gate D reuses its decision logic, not a fresh
  scorer.
- **Freshness gate (Gate D rule):** `strategy_engine_profileA.py: latest_signal()` lines 153–196,
  certified_gate mode = emit only if (poll bar − true fill instant) ≤ 10 min, session ny_am,
  acted_ts dedup. Survey applies the same 10-min staleness test to each cell's signals (session
  restriction reported both ways: gate-faithful ny_am-only AND all-session, labeled clearly,
  since new concepts are not a priori ny_am strategies).
- **Emit-at-fill context:** EMIT-001 (research/atlas/prereg/EMIT-001.md, DEC-20260711-EMIT-001) —
  suppressed-but-recoverable flagging per directive uses its G-gate vocabulary.
- **Correlation ledgers (deliverable 3):**
  Profile A OTE: `research/atlas/profile_a_edge/outputs/signals_583_classified.csv` (ts, R,
  achievable, class); honest stream `research/honest_numbers/honest_A_stream_real.json`;
  VPC/ProfileB: `research/regime_edge_stacking/scripts/build_vpc_ledger.py` /
  `build_sweep_ote_ledger.py` outputs.
- **Register/commit:** survey report → `~/trading-team/reports/concept_survey/NN_*.md`
  (path-referenced convention), commit+push in `bot/nq-liq-bot` (remote ZUES.git) for any code
  living there, vault: audit note in `05 Audits/` + row in `00 Command Centre/Experiment
  Registry.md` + BT note in `03 Backtests/`.

## Anti-patterns bound to this run (from the directive)

No train/full-window leaderboard as findings; no per-concept tuning; no concept composites; no
TradingView-script logic or results; no number without holdout+null+FDR context; no fresh scorer;
no cross-vendor data; survey only — no arming, no changes to frozen edges, no LIVE HOLD change.
