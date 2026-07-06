# Wyckoff Playbook -- Strategy Definitions (as coded)

RESEARCH ONLY -- preregistered coarse viability scan. Engine: `wyckoff_engine.py`. Grid runner: `wyckoff_grid.py`. Generated 2026-07-05 22:22:26.535219-04:00.

## Constants (live values from wyckoff_engine.py)

- `TICK` = `0.25`
- `BUFFER_TICKS` = `2`
- `COST_PTS` = `1.2`
- `MAX_HOLD_1M_BARS` = `1440`
- `ATR_LOOKBACK` = `14`
- `RANGE_HEIGHT_ATR_MIN` = `1.5`
- `RANGE_HEIGHT_ATR_MAX` = `8.0`
- `RANGE_MIN_BARS_INSIDE` = `10`
- `RANGE_INSIDE_BAND_FRAC` = `0.1`
- `LOOKBACK_GRID` = `[20, 40]`
- `SPRING_TOUCH_TICKS` = `1`
- `RECLAIM_BARS_GRID` = `[1, 3]`
- `FB_BARS_GRID` = `[2, 4]`
- `SOS_DISP_MIN` = `2`
- `SOS_VARIANT_GRID` = `['mid', 'high']`
- `DS_LOOKBACK` = `20`
- `SOS_WINDOW_BARS` = `20`
- `LPS_WINDOW_BARS` = `12`
- `ENTRY_FILL_WINDOW_BARS` = `12`
- `ABSORPTION_WINDOW_BARS` = `30`
- `ABSORPTION_MIN_TOUCHES` = `3`
- `ABSORPTION_TOUCH_TICKS` = `2`
- `ABSORPTION_COMPRESS_RECENT` = `5`
- `ABSORPTION_COMPRESS_PRIOR` = `20`
- `ABSORPTION_COMPRESS_RATIO` = `0.7`
- `CHOP_WINDOW_BARS` = `30`
- `TREND_LOOKBACK_BARS` = `50`
- `EXIT_TYPES` = `['fixed2r', 'exit3']`
- `W5_EXIT_TYPES` = `['target_or_2r', 'exit3']`
- `VOL_FILTER_GRID` = `[False, True]`
- `RANGE_TF_SIG_COMBOS` = `[('5m', '1m'), ('15m', '1m'), ('15m', '5m'), ('30m', '5m'), ('1h', '5m'), ('1h', '15m'), ('4h', '5m'), ('4h', '15m')]`
- `SESSION_WINDOWS` = `{'asia': ((18, 0), (24, 0)), 'london': ((2, 0), (5, 0)), 'pre_ny': ((8, 0), (9, 30)), 'ny_am': ((9, 30), (11, 30))}`
- `SESSIONS` = `['asia', 'london', 'pre_ny', 'ny_am', '24h-control']`

## RANGE state

Rolling trailing-`lookback` (range_tf bars, lookback in {20,40}) highest-high / lowest-low. Valid only if height in [1.5, 8] x ATR14(range_tf) AND >=10 of the `lookback` bars are 'inside' the range. DOCUMENTED ASSUMPTION: 'inside' = fully contained within the inner 80% band [lo+0.1*height, hi-0.1*height] -- the literal reading (bars vs the SAME window's own rolling max/min) is a tautology (every bar in a rolling-max/min window trivially satisfies Low>=lo and High<=hi), so a non-tautological inner-band containment test is used instead, exactly as implemented in `wyckoff_engine.range_arrays`.

## Events (signal_tf, completed bars only)


WYCKOFF PLAYBOOK — one shared, causal state machine over a (range_tf, signal_tf)
pair. RESEARCH ONLY (preregistered coarse viability scan). Copies the proven
patterns from `pdc_engine.py` (built the previous session, same directory):
its 1m-truth fill walker (entry touch at 1m, NO same-bar entry+target for
touch-based fills, stop-first every subsequent bar), its `assert_causal`
poison-the-future canary + no-same-bar structural check, its ORB-convention
costs (~1.2pt round-turn), and its kill-gate / report machinery (see
`wyckoff_grid.py`).

RANGE (per range_tf, per lookback in {20, 40}): rolling trailing-`lookback`
range_tf highest-high / lowest-low. Valid only if
  height in [1.5, 8] x ATR14(range_tf)                              AND
  >= 10 of the `lookback` range_tf bars are "inside" the range.
DOCUMENTED ASSUMPTION (the brief does not pin down a precise "inside" test,
and the literal reading -- comparing bars against the SAME window's own
rolling max/min -- is a tautology, since every bar in a rolling-max/min
window trivially satisfies Low>=lo and High<=hi by construction). "Inside"
is therefore defined here as fully contained within the INNER 80% band
[lo + 0.1*height, hi - 0.1*height] -- i.e. bars that do not merely sit at the
window's own extremes -- a genuine (non-tautological) consolidation measure.

Events, all on signal_tf using ONLY completed bars (decision stamped at the
triggering bar's own CLOSE; the resulting order/entry may only act from the
NEXT instant onward):
  SPRING       = Low < range_low - 1 tick, then Close reclaims (> range_low)
                 within {1,3} signal_tf bars (reused `primitives.sweep_of_level`
                 semantics, side="sell").
  UPTHRUST     = mirror, side="buy" against range_high.
  SOS          = |displacement_strength| >= 2, sign up, Close > midpoint
                 (variant: > range_high).
  SOW          = mirror, sign down, Close < midpoint (variant: < range_low).
  LPS          = first pullback bar after SOS whose Low touches the broken
                 level (midpoint or range_high, whichever SOS variant fired) --
                 entry is a resting LIMIT at that level, order live only from
                 the LPS bar's own close onward (DOCUMENTED assumption: fill
                 window = ENTRY_FILL_WINDOW_BARS signal_tf bars, matching this
                 repo's `model01`/`pdc_engine` W_FILL=12 convention).
  LPSY         = mirror of LPS (rally touching the broken level, short entry).
  FAILED BREAKOUT = Close beyond range_high/range_low then Close back inside
                 within {2,4} signal_tf bars (used by W5 only).
  ABSORPTION   = >=3 touches (Low <= range_low + 2 ticks, OR High >=
                 range_high - 2 ticks; 2-tick touch tolerance is a documented
                 assumption) of ONE side within a trailing 30 signal_tf-bar
                 window, AND compression: mean bar range of the last 5 bars
                 < 0.7x mean bar range of the PRIOR 20 bars (i.e. bars
                 [t-24, t-5)).
  CHOP         = valid range with no |displacement| >= 2 in the trailing 30
                 signal_tf bars. NO-TRADE state: recorded (diagnostic %) not
                 traded, per the brief.

TREND CONTEXT (W7/W8 only): sign of the range_tf 50-bar Close-vs-time-index
OLS slope, evaluated on the 50 range_tf bars immediately BEFORE the current
rolling range window began (i.e. ending at t-lookback). Computed exactly via
the causal identity sign(slope) = sign(cov(time_index, Close)) since
var(time_index) > 0 always -- no curve-fit approximation, just an O(n)
rolling-covariance shortcut to a real OLS slope sign.

FILLS AT 1m TRUTH (mandatory, `_walk_1m`): three fill styles --
  "market" : next-bar-open entries (W1/W2/W5). Entry price = that signal_tf
             bar's actual 1m Open. Because entry occurs at the true instant
             the bar opens, the ENTIRE bar's subsequent excursion is causally
             AFTER entry -- so, unlike limit/stop fills, same-bar stop AND
             target checks are both allowed from the fill bar onward. This is
             a deliberate, documented departure from pdc_engine's stricter
             touch-based convention, justified by the different fill
             mechanism (see module docstring above).
  "limit"  : resting limit at a fixed price (W3/W4/W7/W8 LPS/LPSY entries).
             Touch-fill, `pdc_engine`-identical convention: fill bar may only
             be stopped out that same bar, target/partial checks begin the
             bar AFTER the fill bar.
  "stop"   : resting stop order at a fixed trigger price beyond the range
             (W6 absorption->breakout). Same touch-fill / same-bar convention
             as "limit".
Stop-first on every bar after the fill bar, in all three styles.

COSTS: flat 1.2pt round-turn (ORB-recert convention), applied as cost_R =
COST_PTS / risk_points, deducted from every trade's gross R.

STOP CONVENTION (all models): beyond the model's own "triggering extreme"
(documented per-model below) + 2 ticks.


## Models (stop = beyond the triggering extreme +2 ticks; entries only after the triggering bar's own close)

### W1
spring->long on reclaim (next-bar-open market fill). Stop beyond the spring low.

```
W1 (direction=+1, spring->long on reclaim) / W2 (direction=-1,
upthrust->short on reclaim). Entry = next signal_tf bar's OPEN (market).
Stop = beyond the spring/upthrust extreme + 2 ticks. vol_filter (W11,
W1 only per brief) requires the spring bar's own Volume >= 1.5x its
trailing-20-bar average.
```

### W2
upthrust->short mirror of W1.

### W3
spring->SOS->LPS limit-entry long (resting limit at the broken midpoint/high, live from the LPS bar's close, fill window=12 signal_tf bars).

```
W3 (direction=+1, spring->SOS->LPS limit-entry long) / W4 (direction=-1,
mirrored short, upthrust->SOW->LPSY). Entry = resting LIMIT at the broken
level (midpoint or range_high/low per sos_variant), live from the LPS/LPSY
bar's own close. Stop = beyond the LPS/LPSY pullback extreme + 2 ticks.
```

### W4
mirrored short (upthrust->SOW->LPSY).

### W5
failed-breakout re-entry: trade back INTO the range toward the midpoint (next-bar-open market), target = nearer of midpoint or 2R, or Exit#3 variant.

```
Failed-breakout re-entry (both directions in one pass): Close beyond
range_high/range_low then Close back inside within `fb_bars`. Trades BACK
into the range toward the midpoint (next-bar-open, market). Target =
midpoint or 2R, whichever is nearer (or Exit#3, gridded separately).
Stop = beyond the trapped breakout extreme + 2 ticks.
```

### W6
absorption->breakout: resting stop-order at the OPPOSITE (breakout) extreme from the pressured/absorbed side.

```
ABSORPTION -> breakout stop-order at the pressured side's OPPOSITE
extreme (>=3 touches of range_low + compression => expect breakout UP,
buy-stop resting above range_high; mirror for range_high touches). Stop-
loss = beyond the pressured-side extreme (the absorption zone itself) +
2 ticks.
```

### W7
reaccumulation: range formed after an up-leg (trend-context gate) -> SOS breakout up -> LPS entry, long. No spring/upthrust prerequisite (unlike W3).

```
W7 (direction=+1, reaccumulation: range after up-leg -> SOS breakout ->
LPS entry long) / W8 (direction=-1, redistribution mirror). No spring/
upthrust prerequisite (unlike W3/W4) -- gated instead on TREND CONTEXT
(50-bar range_tf close-slope sign, before range formation) matching
`direction`.
```

### W8
redistribution mirror of W7 (down-leg trend context -> SOW breakout down -> LPSY entry, short).

### W11
volume overlay variant flag on W1/W3 ONLY: spring bar's own Volume >= 1.5x its trailing-20-bar average (average excludes the spring bar itself). Reported as model tag 'W1+W11' / 'W3+W11'.

### W12
composite: constructed ONLY IF >=2 of W1-W8 have a SURVIVOR family (see kill gates below); otherwise 'components dead, composite not constructed'.

## Grids run per model (per range_tf/sig_tf combo x lookback x session)

- **W1**: detect-grid = [{'reclaim_bars': 1, 'vol_filter': False}, {'reclaim_bars': 1, 'vol_filter': True}, {'reclaim_bars': 3, 'vol_filter': False}, {'reclaim_bars': 3, 'vol_filter': True}]  |  exit_types = ['fixed2r', 'exit3']
- **W2**: detect-grid = [{'reclaim_bars': 1}, {'reclaim_bars': 3}]  |  exit_types = ['fixed2r', 'exit3']
- **W3**: detect-grid = [{'reclaim_bars': 1, 'sos_variant': 'mid', 'vol_filter': False}, {'reclaim_bars': 1, 'sos_variant': 'mid', 'vol_filter': True}, {'reclaim_bars': 1, 'sos_variant': 'high', 'vol_filter': False}, {'reclaim_bars': 1, 'sos_variant': 'high', 'vol_filter': True}, {'reclaim_bars': 3, 'sos_variant': 'mid', 'vol_filter': False}, {'reclaim_bars': 3, 'sos_variant': 'mid', 'vol_filter': True}, {'reclaim_bars': 3, 'sos_variant': 'high', 'vol_filter': False}, {'reclaim_bars': 3, 'sos_variant': 'high', 'vol_filter': True}]  |  exit_types = ['fixed2r', 'exit3']
- **W4**: detect-grid = [{'reclaim_bars': 1, 'sos_variant': 'mid'}, {'reclaim_bars': 1, 'sos_variant': 'high'}, {'reclaim_bars': 3, 'sos_variant': 'mid'}, {'reclaim_bars': 3, 'sos_variant': 'high'}]  |  exit_types = ['fixed2r', 'exit3']
- **W5**: detect-grid = [{'fb_bars': 2}, {'fb_bars': 4}]  |  exit_types = ['target_or_2r', 'exit3']
- **W6**: detect-grid = [{}]  |  exit_types = ['fixed2r', 'exit3']
- **W7**: detect-grid = [{'sos_variant': 'mid'}, {'sos_variant': 'high'}]  |  exit_types = ['fixed2r', 'exit3']
- **W8**: detect-grid = [{'sos_variant': 'mid'}, {'sos_variant': 'high'}]  |  exit_types = ['fixed2r', 'exit3']

## Preregistered priors (printed per brief, NOT re-derived here)

- Reversal class (W1/W2/W5-adjacent) previously LOSES on NQ (turtle-soup PF 0.84-0.91; breakout-failure family dead <=0.98) -- source: `project_ict_nq` memory / prior sessions.
- Chasing-class entries net-negative.
- Compression/regime classification previously dead.

## Kill gates (mechanical)

- PF < 1.15 after costs -> REJECTED
- < 4/6 last full years positive -> REJECTED
- < 0.5 trades/wk -> REJECTED (too thin)
- canary fail -> DEAD
- PF > 1.8 anywhere -> freeze + flag for auditor (not optimized)
- NY-AM survivors: trade-day overlap % vs certified Profile A stream (`tools_sim_parity_check.load_rows`); overlap > 60% -> NOT-A-LANE
