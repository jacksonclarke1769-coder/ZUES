# Profile C (PD/FVG) — Strategy Definition (as coded)

**NOTE:** this is a **distinct lineage** from the pre-existing `profileC_research.py` /
`profileC_validate.py` files in `~/trading-team/backtests/ict-nq-framework/` (those are a
gap-fill / gap-go / overnight-fade / ORB-fade scan, unrelated). This document describes
the "PD-array -> sweep -> displacement -> FVG" concept implemented in the NEW files
`pdc_engine.py` and `pdc_grid.py` (same directory), written for this task only.

Engine source of truth: `~/trading-team/backtests/ict-nq-framework/pdc_engine.py`.
Every rule below is a direct restatement of what is coded there (line references as of
this run); nothing here is aspirational.

## Long chain (short is the exact mirror image — bearish PD FVG above price, prior swing
high swept, bearish displacement, bearish FVG, DISC = 50-79% retracement of the leg
measured from the low)

### 1. HTF PD ARRAY (stage 1) — `pd_zone_arrays`, `merge_pd_zone`
- The PD-timeframe frame is a causal resample of the 5m spine (`engine/data.py resample`),
  or the ICT day (`engine/data.py daily`, 18:00 ET anchor) for PD=`D`.
- A PD bullish FVG is a 3-candle gap on the PD-timeframe (`primitives.fvgs`: `c1.high < c3.low`).
- **"Unmitigated" as coded:** only the MOST RECENTLY FORMED bullish PD FVG is tracked at
  any time (not a stack of every simultaneously-active zone below price) — a deliberate,
  documented simplification. It is held forward from its own formation bar, and cleared
  back to inactive (NaN) the first time a later PD bar's CLOSE trades back through the
  zone's bottom (full invalidation). It becomes "known" at that PD bar's own CLOSE, then
  merged onto the signal-TF frame via `merge_asof(direction="backward")` after shifting
  the PD index forward by one PD period — identical convention to
  `engine/htf.py add_htf_swings`. No look-ahead.
- "Active" = the current signal-TF bar's Low trades into `[zone_bottom, zone_top]`.

### 2. Liquidity sweep inside the zone
- The swept level is the causal prior confirmed swing low:
  `primitives.last_known_swings(left=2, right=2)` (as specified).
- The swing level must itself sit inside `[zone_bottom, zone_top]` (the liquidity being
  run is located inside the PD array).
- Sweep test (parameterised `primitives.sweep_of_level` logic): the anchor bar's Low must
  pierce the swing level by **>= penetration ticks** (grid: **{1 tick, 3 ticks}**), and
  price must close back above the level within **<=3 bars** of the piercing bar
  (`SWEEP_MAX_BARS=3`, matching the brief's reuse of `sweep_of_level(..., max_bars=3)`).
  The sweep extreme recorded for the stop is `min(Low)` over the piercing-to-reclaim
  window.

### 3. Displacement + FVG (within <=6 signal-TF bars of the reclaim)
- Window: `[reclaim_bar, reclaim_bar + 6]` (`DISP_WINDOW_BARS = 6`, per brief).
- Displacement: `primitives.displacement_strength` magnitude code, threshold grid
  **{>=1 (1.5x trailing-20 avg body), >=2 (2.0x)}**.
- The displacement must be present among the **FVG's own 3 forming candles**
  (`[form_idx-2, form_idx-1, form_idx]`) so the qualifying impulse is the one that
  actually creates the gap, not merely present somewhere in the window.
- The bullish FVG itself is `primitives.fvgs` (3-candle gap, `direction=+1`), first
  candidate found chronologically inside the window.

### 4. DISC flag (optional filter, grid {off, on})
- Impulse range = `[min(Low), max(High)]` over `[reclaim_bar, found_bar]`.
- `frac = (imp_hi - fvg_mid) / (imp_hi - imp_lo)` — retracement-from-the-high, OTE-style.
- DISC satisfied if `0.50 <= frac <= 0.79` (the brief's "50-79% discount of the
  displacement range"). When DISC is required and not satisfied, the setup is rejected
  (not merely flagged) — matching "record whether ... " being operationalised as a
  variant-grid ON/OFF filter for the viability scan, per the task's variant-grid wording.

### 5. Entry
- Two styles (grid): **top-edge / first-touch** (limit at the FVG's top edge, the side
  price approaches from as it retraces) and **mid / 50%** (consequent-encroachment,
  `fvg_mid`).
- Entry may only occur on 1m bars strictly AFTER the FVG-forming 3rd candle's own CLOSE
  (`fvg_ts = signal_bar_open + signal_period`).
- Entry-fill window: **12 signal-TF bars** from that close
  (`ENTRY_FILL_WINDOW_BARS = 12`). **Documented assumption** — the brief specifies the
  entry mechanics but not an explicit fill-expiry; 12 bars matches this repo's existing
  `models/model01_sweep_mss_fvg.py` `W_FILL=12` convention. If the limit never touches
  within the window, no trade is recorded (setup expires).

### 6. Stop
- Sweep extreme (the piercing-to-reclaim window's worst excursion) **+/- 2 ticks**
  (`BUFFER_TICKS = 2`), matching this repo's `model01_sweep_mss_fvg.py BUFFER` convention.

### 7. Exits (both computed, grid)
- **fixed2r**: target at entry +/- 2R.
- **exit3**: 50% off at +1R, 50% off at +2R, shared -1R stop (no breakeven move,
  no trail) — matches the bot's live "Exit#3" convention by name only; this research
  engine implements the plain 50/50 partial split, not the live routing logic.

## FILLS AT 1m TRUTH (mandatory, non-negotiable)
- All signal generation (zone, sweep, displacement, FVG, DISC) happens on the causal
  signal-TF arrays only (never on 1m data), except when the signal TF itself IS 1m
  (the `(15m, 1m)` combo).
- Every entry and exit is walked bar-by-bar on the 1m NQ spine
  (`engine/data.py load_spine("NQ","1m")`, 2013-12-31 -> 2026-05-25, 24h ET).
- Limit fills occur on touch: Low<=entry (long) / High>=entry (short), fill AT the
  limit price (no extra slippage modelled per-fill; slippage is folded into the flat
  1.2pt cost below, per the brief's cost convention).
- **NO SAME-BAR ENTRY+TARGET**: on the 1m bar where the limit fills, ONLY the stop may
  also be checked that same bar (a target/partial hit on the fill bar is never
  recognised). From the bar after the fill onward, **stop is checked before
  target/partials every bar** ("stop-first").
- Max hold: capped at 24h of 1m bars (1440 bars) from the fill bar. **Documented
  assumption** — the brief does not specify a max hold; this exists only to terminate
  degenerate opens and matches this codebase's existing "timeout at last bar"
  convention (e.g. `model01_sweep_mss_fvg._simulate`).

## Costs
- Flat **1.2pt round-turn** (ORB-recert convention: 0.45 commission + 0.25 retest-entry
  slippage + 0.25 exit slippage + buffer), applied in points per trade, deducted from
  the trade's R: `cost_R = 1.2 / risk_points`.

## One-position-at-a-time / no overlap
- After a trade (or an expired, unfilled setup), the outer signal-TF scan advances past
  the FVG-forming bar AND past the trade's actual 1m exit timestamp (mapped back to the
  first signal-TF bar strictly after it) before it will look for the next setup — no
  overlapping positions, matching every other model in this codebase
  (`model01_sweep_mss_fvg.py`: `i = exit_i + 1`).

## Preregistered matrix (exact, not expanded)
- **PD x signal combos:** `{(1h,5m), (1h,15m), (4h,5m), (4h,15m), (15m,1m), (30m,5m),
  (D,5m), (D,15m)}` — 8.
- **Sessions:** NY-AM entry window 09:30-11:30 ET, London 02:00-05:00 ET,
  Asia 18:00-00:00 ET, 24h-control — 4.
- **Penetration ticks:** {1, 3} — 2.
- **Displacement threshold:** {>=1 (1.5x), >=2 (2.0x)} — 2.
- **DISC:** {off, on} — 2.
- **Entry style:** {top, mid} — 2.
- **Exit type:** {fixed2r, exit3} — 2.
- Total: 8 x 4 x 2 x 2 x 2 x 2 x 2 = **1024 fully-specified backtest cells** (both
  directions run together inside every cell; long/short split reported separately for
  survivors).

## Kill gates (mechanical, applied per FAMILY = pd_tf x sig_tf x session, using the
best-PF variant within that family's 32-cell variant sub-grid)
1. **PF < 1.15** after cost -> REJECTED.
2. **Positive in < 4 of the last 6 full calendar years (2020-2025)** -> REJECTED (only
   evaluated for families that already cleared gate 1 and have data in >=4 of those years).
3. **< 0.5 trades/week** (against the full 646.9-week data span) -> REJECTED.
4. **Canary FAIL** (poison-the-future or same-bar-fill) -> DEAD (would apply globally;
   see `02_timeframe_matrix.md` / this report's canary section — both configurations
   tested PASSED).
5. **NY-AM trade-day overlap > 60%** with the certified Profile A stream -> NOT-A-LANE
   (flagged, not PF-rejected — may still matter as an entry filter for the B-workstream).
6. **Any single cell with PF > 1.8** -> STOP optimising that cell, flag for auditor
   (prior: bug), reported separately, not chased further.

See `02_timeframe_matrix.md`/`.csv` for every cell, `04_standalone_results.md`/`.csv`
for full detail on any family that survived all gates or was flagged NOT-A-LANE, and the
main run report for the canary PASS/FAIL detail, NY overlap number, runtime, and
firewall before/after.
