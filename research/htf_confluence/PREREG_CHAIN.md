# PRE-REGISTRATION — HTF confluence chain (bias → HTF sweep → HTF FVG → 1m entry)

**FROZEN 2026-07-20, before any result is computed or seen.** This file is the pre-registration.
It is committed as its own commit BEFORE the test run. Every threshold below is a single a-priori
value chosen from ICT convention / a discretionary trader's stated rules — NONE chosen by looking
at results. No combination search, no threshold tuning on this data. If any value "feels wrong"
after results are seen, that is a NEW pre-registered hypothesis for a SEPARATE run with its own
holdout — never an edit to this file.

Provenance of the discipline: [[AUDIT-20260720-0941]] (survey fill-bug: 19 fake survivors),
concept-survey graveyard (SURVEY-ICT-001, 0/36), Profile A frozen edge (model01_sweep_mss_fvg).

## Instrument, data, window
- NQ, single-vendor Databento: `data/real_futures/NQ_databento_1m_5y.parquet` (bar-open UTC,
  2021-06-23 → 2026-06-22). NO mixed-vendor `data/nq/` set, NO Dukascopy (241pt basis rule).
- Window: last 2 years = 2024-06-22 → 2026-06-22. Split: train 2024-06-22→2025-06-22, holdout
  2025-06-22→2026-06-22. **Holdout is the verdict.** Chain is frozen, so train is observe-only,
  not for tuning.
- All timestamps tz-aware; session/EOD via zoneinfo America/New_York.

## The chain — ONE direction of trade per bar, all 5 conditions required, in this time order

### Condition 1 — HTF bias filter (timeframe: 1H)
- Rule: bias is LONG when 1H close > 1H EMA(50) AND the most recent confirmed 1H swing structure
  is higher-high/higher-low (last confirmed 1H BOS was bullish); SHORT is the mirror. If the two
  disagree (EMA says one, BOS says other) → NO BIAS → no trades that bar.
- Frozen values: EMA length = **50** on **1H**; swing = fractal **left=3/right=3** confirmed
  pivots (house convention); BOS = 1H close beyond the most recent confirmed opposing 1H swing.
- Only longs in LONG bias, only shorts in SHORT bias.
- Rationale for 1H (a priori): the operator said "HTF bias"; 1H is the standard ICT HTF-bias
  timeframe for an intraday model feeding a 1m entry, and Profile A itself is bias-free — using
  1H here makes this chain genuinely different from A on condition 1, not a re-label. (Note: the
  ATLAS finding that 1H is INVERTED as a *continuation* filter is about a different construction;
  this chain uses 1H bias to gate a *reversal-after-sweep*, the opposite context — stated so the
  choice is on record, not tuned.)

### Condition 2 — HTF liquidity sweep (timeframe: 15m)
- Pool: the **prior RTH session** high and low (yesterday's 09:30–16:00 ET range extremes).
- Sweep = a 15m bar whose wick trades **≥ 1 tick beyond** the pool level and then **closes back
  inside** (close on the inside of the swept level) within that same 15m bar. In LONG bias we
  require a sweep of the prior-session LOW (sell-side liquidity taken, reversal up); in SHORT
  bias, a sweep of the prior-session HIGH.
- The setup ARMS only after such a sweep; it is valid for the next **8** 15m bars (2 hours) or
  until invalidated, whichever first.
- Frozen values: pool = prior RTH session H/L; beyond = ≥1 tick; reclaim = same-bar close inside;
  arm-window = 8 bars.

### Condition 3 — HTF FVG / imbalance (timeframe: 15m), the operator's "FVG size" filter
- After the sweep (Condition 2), a **displacement** must create a 15m Fair Value Gap in the bias
  direction within the arm-window: a 3-candle gap where candle-1 and candle-3 do not overlap
  (bullish: low[candle3] > high[candle1]; bearish mirror), the gap becoming known at candle-3
  close (causal).
- **Minimum size threshold (frozen a priori): gap height ≥ 0.5 × ATR(14) of the 15m timeframe.**
  This is the single FVG-size value; it is NOT swept.
- Displacement gate: candle-2 (the gap-creating candle) body ≥ **1.5 ×** the trailing-20 mean 15m
  body (a priori, standard displacement definition).

### Condition 4 — 1m entry
- Scale to 1m. Entry = a **limit at the 15m FVG proximal edge** (the near edge of the gap in trade
  direction: bullish = the gap's lower/top-of-lower-candle edge the price returns down to; i.e.
  the edge price first re-touches on the return). ONE trigger, frozen: proximal edge (not 50%, not
  distal).
- Working-order lifetime: the limit is live until filled, until the FVG is fully filled through
  its distal edge (invalidation), until the arm-window expires, or EOD — whichever first.

### Condition 5 — Stop / target
- Stop: **1 tick beyond the sweep extreme** (the wick low/high that took the liquidity in
  Condition 2) — structural invalidation.
- Target: nearest opposite-side liquidity ≥ 1 × ATR(14, 15m) away (prior-session opposite
  extreme / confirmed 15m opposing swing); fallback fixed **2R** if none qualifies. (OTE-spec
  convention, for comparability with Profile A.)
- One position at a time. Signals arriving while in-position are dropped. EOD flat 16:55 ET.

## Fills (certified, not re-invented)
First-touch on 1m; **stop-first on any bar including the fill bar** (same-bar entry+stop =
filled-then-stopped, loss booked — the survey-bug convention); $1.00 round-turn; 1-tick adverse
slip each side. Walker: the certified single-vendor Databento path
(`tools_1m_truth_recert.walk_1m` conventions / the concept-survey engine already audited against
the same-bar bug). NO fresh scorer.

## Gates for the word "REAL" (all mandatory)
1. **Fill-path pre-gate** (Step 1): same-bar regression passes + instant-loss population exists in
   this chain's ledger. No performance number trusted until this passes.
2. **Holdout**: holdout PF>1 and expectancy>0 (train observe-only).
3. **Null**: chain beats a randomized-entry null on the same bars in the same bias/session context
   (real total R > null 95th percentile).
4. **n-adequacy**: n stated explicitly; a high-PF / low-n result is INSUFFICIENT, not an edge.
   Pre-registered adequacy floor: **n ≥ 30 in holdout** to even attempt a significance claim;
   below that the verdict is INSUFFICIENT-N regardless of PF.
5. **vs Profile A**: fill-day / trade overlap with the frozen Profile A OTE stream
   (`research/atlas/profile_a_edge/outputs/signals_583_classified.csv`). Valuable ONLY if (a)
   higher holdout expectancy than A on shared setups (quality filter) OR (b) fires on different
   days (decorrelation). Otherwise = worse-sampled Profile A subset → REDUNDANT.

## Verdict space (exactly one, no forced winner)
REAL & ADDITIVE · REAL BUT REDUNDANT · INSUFFICIENT-N · NULL. A NULL result is documented in the
graveyard so this exact chain is never re-tested.

## What this run may NOT do
No combination search. No threshold tuning on this data. No strategy change to frozen edges. No
arming. LIVE HOLD ACTIVE. Any post-hoc "what if the FVG floor were 0.4×ATR" is a separate
pre-registered run, not an edit here.
