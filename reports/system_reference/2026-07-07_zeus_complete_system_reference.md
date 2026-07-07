---
title: "ZEUS — Complete System Reference (Code-Level)"
date: 2026-07-07
status: reference
tags: [reference, system, code, profile-a, vpc, d1c, eval, funded, watchdog, graveyard]
---

# ZEUS — Complete System Reference (Code-Level)

> Everything ZEUS is, how each piece is defined **in code**, and everything we tried and killed. Every parameter and rule below was extracted directly from the source files (file:line cited), not from memory. **LIVE HOLD ACTIVE — nothing is armed.** All performance numbers are the post-incident *honest* numbers (the pre-2026-07-06 "certified" numbers were invalidated by the D1c look-ahead, INC-20260706-1141).

Repos: live/research code `~/trading-team/bot/nq-liq-bot`; engine `~/trading-team/backtests/ict-nq-framework`; VPC engine `~/trading-team/backtests/nq_vwap_pullback.py`; research stores `~/trading-team/research/`. Instrument: NQ futures traded as **MNQ** (micro, $2/pt).

---

## 0. What ZEUS is

A fully-instrumented Apex prop-firm trading business on NQ. Four layers:
1. **Edges** — signal engines that fire trades (Profile A live; VPC certified-not-wired; Profile B ORB live-wired).
2. **Business simulators** — an eval funnel and a funded funnel that turn a trade stream into pass/bust/expire and $ paid.
3. **Live execution + safety** — `auto_live` → TradersPost → Tradovate, wrapped in a fail-closed watchdog, fail-open telemetry, and hash-locked configs.
4. **Research engines** — causal feature stores + canary discipline that discover and kill edges.

The through-line is **honesty enforcement**: 1m-truth fills, adverse-first ordering, permanent canaries, and a `gate.sh` of ~857 tests. Four distinct defect classes were caught by canaries this week before any dollar moved (§9).

---

## 1. THE LIVE EDGE — Profile A (ICT OTE liquidity-raid continuation)

**Status: LIVE-ROUTED, FROZEN.** Engine `models/model01_sweep_mss_fvg.py` (labeled "the frozen Profile A model", `strategy_engine_profileA.py:15`; `config.py:34` = "PROFILE A v2 (frozen, validated)"). **Honest performance: PF 1.237 unfiltered / 1.361 with D1c, WR 44.9%, ~2.24 trades/week, 705 raw signals / 583 D1c-kept over 5 years.**

### The signal pipeline (sweep → MSS → displacement → FVG/OTE → entry)

**(a) Liquidity sweep** (`model01._detect()` 375-399). Levels, tiered by significance (`LEVELS_LONG/SHORT`, lines 39-40):
```
tier 1 = prior-week high/low (pwh/pwl)
tier 2 = prior-day high/low (pdh/pdl)
tier 3 = Asia high/low, London high/low, 1H swing high/low
```
Sweep = the low over `[i-2 .. i]` breaks **≥1 tick below** a level AND the **current bar closes back above** it (long; short symmetric). `TICK=0.25`. Highest tier wins on simultaneous sweeps.

**(b) Market-structure shift** (`_detect()` 400-410). Within `W_MSS=12` bars (1h) of the reclaim, the 5m close must break back through the most-recent opposing **causal 3-left/3-right fractal swing** (`primitives.last_known_swings(df,3,3)`). No MSS in-window → no trade.

**(c) Displacement gate** (411-415). Between sweep and MSS there must be ≥1 bar of ≥1.5× trailing-20-bar-average body in the trade direction (`primitives.displacement_strength(df,20)`, buckets 1/2/3 at 1.5×/2.0×/2.5×). Else rejected.

**(d) Entry — OTE 0.705** (425-430; the live `entry_type`). Impulse leg = high/low from sweep bar to MSS bar. Long entry = `impulse_high − 0.705 × (impulse_high − impulse_low)` (a 70.5% discount retrace); short = mirror. A resting limit at that level must fill within `W_FILL=12` bars (1h) of the MSS bar or the setup is dropped. (`ote_depth=0.705`, `config.py:41`.)

**(e) Entry/stop/target geometry** (243-273):
```
entry  = OTE level + d*SLIP            # slippage applied AGAINST the trade
stop   = swept_extreme ∓ BUFFER        # BUFFER = 2 ticks (0.5pt) beyond the pierced high/low
risk   = |entry − stop|
target = entry + d * rr * risk         # rr = 2.0 → +2R (fixed_rr mode)
```
Rejection guards: `risk ≤ 0.5pt` (degenerate) or `risk > 1.2% of price` (stop too wide).

**(f) Session gating.** NY-AM 09:30–11:30 ET is enforced **live**, not in the engine: `latest_signal()` filters `session != "ny_am"` (`strategy_engine_profileA.py:66`); `in_entry_window()` checks `nyam_start_min=570 / nyam_end_min=690`; flat by `flat_min=870` (14:30 ET).

**(g) Trade emission** (301-323): emits `date`/`time` as **strings** from the fill timestamp, plus `entry/stop/target/rr/direction/liq_swept/sweep_bar/mss_bar/fill_bar/exit_bar`. One position at a time (`i = exit_i + 1`). The string `date`/`time` emission was the root of the live `latest_signal()` defect — **FIXED 2026-07-07** (commit fafe12d; §9.1).

### The parameter dicts (verbatim)

`PROFILE_A` (`strategy_engine_profileA.py:20-22`):
```python
PROFILE_A = dict(entry_type="ote", sessions={"asia","london","ny_am","ny_lunch","ny_pm"},
                 target_mode="fixed_rr", rr=2.0, partial=[(1, 0.5)])   # Exit#3
```
`config.STRAT` (`config.py:34-53`, the live parameter block): `ote_depth=0.705`, `nyam_start_min=570`, `nyam_end_min=690`, `flat_min=870`, `rr=2.0`, `exit_scheme="exit3"`, `partial=[(1.0,0.5)]`, `stop_buffer_tk=2`, `sweep_levels=[asia_high, asia_low, london_high, london_low, pdh, pdl, pwh, pwl, h1_sh, h1_sl]`, `news_blackout=True` (±15/30min around CPI/NFP/FOMC).

### Exit#3 (the live exit)
Defined by `partial=[(1,0.5)]` + `rr=2.0`: **50% of size banks at +1R, 50% rides to +2R, both share one stop at swept-extreme+2tk** → max win 1.5R combined, max loss −1R. Live name `EXIT_MODEL="EXIT3_FIXED_PARTIAL"` (`config.py:56`); integer split `exit3_split(qty)` → `(qty//2 @ +1R, remainder @ +2R)` (`config.py:64-66`). No trail, no breakeven.

### The live engine wrapper — `ProfileAEngine`
`_features()` (40-48) rebuilds the causal frame each call (sessions + daily/weekly HTF + session levels + 1H/4H swings). `latest_signal()` (50-75) runs the frozen model in realtime mode and returns a fresh fill if one printed in the last ~10 min in NY-AM and is unacted. **✅ FIXED 2026-07-07 (§9.1, commit fafe12d): reconstruction now derives the instant from `feats.index[fill_bar]` via `_derive_fill_instant()` (raise-don't-parse, typed `TimestampReconstructionError`, 09:30-16:00 assert, permanent canary). The prior string re-localization was the same class as INC-20260706-1141.**

---

## 2. THE SECOND EDGE — VPC (VWAP-Pullback Continuation)

**Status: CERTIFIED (1m-truth clean), Phase-0 sim-only, NOT live-wired** (needs a trailing-stop execution lane that doesn't exist — §5.6, and the VPC-lane design docs). Engine `~/trading-team/backtests/nq_vwap_pullback.py`. **Honest: PF 1.29 native / 1.318 at 1m truth, 408 trades 2022-2026, ~1.8/wk, 5/5 years positive, corr +0.11 with A, fires on 225 days A sleeps.**

### Signal (`vpc_signals()`, lines 38-75)
Trend gate `up` requires: slope/extension/vol gates pass, **close on trend side of VWAP**, **VWAP itself trending same way** (`vwap > vwap_6bars_ago`), and close beyond day-open. Then a two-step trigger:
- **Arm**: trend intact AND the bar's low/high actually **pierces VWAP** (the pullback touch).
- **Fire**: a later bar re-establishes trend AND **closes back through VWAP** with a ~5bp buffer. Entry queued for next bar (no lookahead), direction ±1, initial stop = `atr_stop × ATR`.

### Locked production config (NOT the engine defaults)
`nq_vpc_final.py:8` = `tools_vpc_1m_truth.py:146 LOCKED_CFG`:
```python
CFG = dict(atr_stop=2.5, trail_atr=5.0, slot_min=6, slot_max=66, max_trades=2,
           slope_mult=0.3, trend_mult=0.5, daily_stop=120)
```
→ 2.5×ATR initial stop, **5.0×ATR trailing stop**, window **slot 6 = 10:00 ET to slot 66 = 15:00 ET**, max 2 trades/day, 120pt daily circuit-breaker. (The engine module's bare defaults 1.5/60/2.0 are only for its own param-sweep — do not confuse.)

### The canonical trail — `vpc_trail.py` (Phase-0 build this session)
The trail extracted into ONE function both the sim and (future) live manager call. `VpcTrail.step(bar_low, bar_high, bar_close, atr_now)`:
1. **Adverse-first**: check `bar_low ≤ stop` (long) against the stop set on the *previous* bar → exit before any update.
2. **Close-referenced high-water**: `peak = max(peak, bar_close)` (never the intrabar high — this is the anti-Asian-Range-artifact property).
3. **One-directional ratchet** with runtime assert: `stop = max(stop, peak − 5×ATR)`, can only tighten.
`walk_1m_trail()` drives it bar-by-bar with a causal 5m-ATR step-function (ATR from the last *completed* 5m bar). **Parity canary `test_vpc_trail_parity.py`** proves bit-identical reproduction (n=408, +5319.67pt, PF 1.318) and is in `gate.sh`; a live-shaped ARM B is stubbed REQUIRED-BEFORE-ARM.

---

## 3. THE FILTER & THE FILL CONVENTION

### D1c — the drift gate (Profile A only, zero-parameter)
**Live gate** `drift_gate.py allows()` (55-72): a Profile A entry may work only while `sign(last_completed_1m_close − 09:30_open) == trade_direction`. `drift==0` → disagreement (blocked). **Fail-closed**: missing session-open/last-close, or feed staleness > `stale_after_s+60`, forces suspend. Default `enabled=False` (status-quo). Keep-rate monitored in a 45–80% band (validated era 62%). **Phase-split doctrine (proven this session): D1c is a FUNDED filter, not an eval filter** — unfiltered A dominates the eval funnel (frequency beats the +0.12 PF); D1c-kept A is what funded survival needs.

**Research attachment `run_d1c_real.attach_drift()` (42-114) — POST-FIX.** Derives each trade's evaluation timestamp from `fill_index[fill_bar]` (tz-aware), **raises rather than parsing** date/time strings, and hard-asserts the derived time sits in 09:30–16:00 ET. This is the INC-20260706-1141 fix; the removed string-parse fallback was the look-ahead.

### The 1m-truth exit walker — `tools_1m_truth_recert.walk_1m()` (72-113)
The honesty-critical fill convention every certified number passes through:
- **Fill**: a resting limit fills only if the 1m slice of the certified 5m fill bar actually trades to the entry.
- **Stop-first adverse ordering**: on every bar (including the fill bar) the stop is checked before any partial/target.
- **F1 same-bar guard**: no target/partial may fill on the fill bar itself (kills the entry-bar look-ahead that inflated PF; was booking 25–42% of wins on the fill bar).
- **`A_SLIP = 0.5pt`** penalty on every stop exit (fills always slip against you).
- **Exit#3** walked via `partials=[(+1R,0.5)]` + `+2R` target; **Fixed-1.5R** (research-comparison only, `tools_salvage_funded_exits.walk_fixed_r(1.5)`) walked as full-size single +1.5R target, same stop geometry. Timeout → mark-to-close at the window's last 1m bar.

---

## 4. THE BUSINESS SIMULATORS

### Eval funnel — `tools_account_size_research.py`
**`build_events(rows, budget, max_qty)`** (43-53): per trade `q = min(spec_max, MAX_A_QTY=40, floor(budget/risk_usd))`; event `pnl = R × risk_usd × q`. **`day_rows(ev, 550, 1000)`** (56-78): accumulates daily P&L; once realized ≤ **−$550** no more trades that day; independently, if the intrabar **trough ≤ −$1,000 (DLL)** the whole day is force-flattened at −$1,000 (honest, pessimistic — a recovering day is still cut). **`eval_run(days, s0, spec)`** (81-101): 30-day clock (`EXPIRE_DAYS=30`); threshold starts at start−trail ($47,500); trails EOD peak; **once EOD peak ≥ $52,600 the floor LOCKS at $50,100**; PASS at start+target ($53,000), BUST on threshold breach (intraday trough-aware), EXPIRE at 30 days. `SPECS["50K"]`: start 50,000 / trail 2,500 / target 3,000 / dll 1,000 / stop 550 / ladder [1500,1500,2000,2500,2500,3000] / max_qty 60. Eligible starts = one per unique trading day with >30d forward runway (~525).

### Funded funnel — `apex_funded_40.py run_pa()` (74-112)
Survival + payout lifecycle at funded size. Same trail/lock/DLL as eval, plus the payout ladder: every 30 days, if **eligible** (balance ≥ $52,600 MIN_REQ, ≥5 qualifying $250+ days since last payout, positive cumulative profit, and **no single day ≥50% of that profit** — CONSISTENCY 0.50), sweep `min(next_ladder_rung, balance − $52,100_floor)`; after all 6 rungs (~$13k lifetime) the account **CLOSED_MAX**. `tools_recert_funded.py` generalizes sizing to independent `(budget, cap)` and imports `run_pa` unmodified (canary-verified identical). **Overlapping monthly starts → ~4-5 effective independent samples → wide CI on all funded numbers (E[paid]/bust are model-observed).**

### Apex rule constants (help-center-derived, flagged VERIFY-vs-contract)
30-day eval expiry · $2,500 EOD trail (locks at start+$100) · $1,000 DLL (day-flatten, not death) · $550 bot-internal daily stop (0.55× DLL) · size-to-risk `q=min(cap, floor(budget/risk))` · 6-rung payout ladder · qualifying-day $250×5 · consistency 0.50 · payout every 30d.

### Pinned business formulas
`funded_per_slot_year = 365.25/mean_days_per_attempt × pass_count/eligible` (`tools_opt_sizing_grid.py:214`) · `attempts_per_pass = eligible/pass_count` · `E$ = pass% × funded_value − fees` (the $8,000/$131 pair is an explicit **placeholder** pending the honest funded value).

---

## 5. LIVE EXECUTION & SAFETY STACK

### 5.1 Execution chain
`bot.py SimBot.process_bar()` runs the engine per bar and calls `_consider()` in the 09:30–13:35 window, gating on `mffu.can_open_trade(news_blackout, risk)`. `auto_live.py LiveAuto.on_decision()` (266) resolves the D1c gate → risk gate → exit model → builds Exit#3 legs → `sender.send_exit3()`. **Multiple lanes are wired**: `on_decision` (Profile A), `on_b_signal` (Profile B / ORB), `on_m_bar` (Profile MOMENTUM scaffolding). Chain: `auto_live → TradersPost webhook → Tradovate`.

### 5.2 Bridge — `bridge_sender.py` (NO order-modify primitive)
Only three order ops exist: `send()` (idempotent by signalId, live-gated by approval flags), `send_exit3()` (fail-closed: validates both legs carry stop+target, sends CORE/TP2 first then TP1, half-built → `flatten()`+INCIDENT), `flatten()` (cancel-all-working then exit). **No modify/replace/amend** — this is why VPC's trailing stop needs a new client-side cancel-replace lane (§5.6).

### 5.3 Watchdog — `watchdog.py` (independent, fail-CLOSED, dumb authority)
Separate process; imports ONLY `flatten`/`cancel` builders (AST-test-enforced — it can never open/resize/unprotect). Invariants: **A** position parity (broker_net == belief, 90s in-flight grace) · **B** orphan/unprotected brackets → flatten+halt · **C** flat-time (14:31 ET / 12:46 half-day) → flatten · **D** feed liveness (180s stale) → halt or flatten · **E** config integrity (live hash vs `evidence/eval_config.sha256`) → halt · **F** daily-loss truth (broker equity vs belief, ±$10). Constants: `LOOP_OPEN_S=10`, `INFLIGHT_GRACE_S=90`, `ACTION_REFIRE_S=300` (once-per-incident). `watchdog_belief.py`: engine publishes belief.json; **a dead/stale (>90s) watchdog or a HALT.flag blocks new entries** (fail-closed) — but never touches positions.

### 5.4 Telemetry (fail-OPEN) vs config locks (fail-CLOSED)
`fill_telemetry.py`: async queue, never blocks orders; records DECISION/ORDER_SENT/TOUCH/FILL_CONFIRMED; tracks **touch-without-fill** (the 15% kill line) and needs **N≥30 fills** before a real live/sim parity read exists. `config_eval_locked.py`/`config_funded_locked.py`: frozen snapshots, hash-pinned, fail-closed. `runtime_config.resolve_exit_model()` raises unless the model is approved.

### 5.5 Canary / test inventory (`gate.sh`, ~857 tests, stages a–e)
Permanent guards: `test_d1c_timestamp_canary.py` + `test_no_future_d1c_attachment.py` (D1c look-ahead) · `test_vpc_trail_parity.py` (trail bit-identity) · `test_env_pandas_canary.py` (pandas major==2) · `test_tools_sim_parity_check.py` (engine parity) · `test_funded_config_firewall.py` + `test_eval_config_firewall.py` (hash locks). Gate: (a) full pytest, (b/c) funded hash, (d/e) eval hash + 3 pinned config files.

### 5.6 The VPC live-lane gap (designed, not built)
`reports/vpc_lane/` holds the DESIGN-ONLY scope + Phase-0 canonical trail + carry-forward register. Three live-boundary blockers recorded (watchdog/trail-churn reconciliation GATING; cancel-replace in-flight timeout → hard-flatten; live-shaped parity ARM B) and a **sequencing gate: live wiring is blocked until Profile A clears N≥30 live fills** (A calibrates fill parity on the easy static-stop case first).

---

## 6. RESEARCH INFRASTRUCTURE

**Feature stores** (`research/nq_pattern_discovery/`, mirrored in `research/es_edge_expansion/`): `features_daily.py` (PDH/PDL, gap, ATR-pctile, causal-at-10:00/10:30 regime labels), `features_intraday.py` (causal VWAP, trend slope, compression, d1c_drift), `canary_causality_check.py` (recomputes 20 random rows from truncated data — stops on look-ahead). **HTF engine** (`engine/htf.py`): PDH/PDL/PWH/PWL + developing day hi/lo via causal cummax/cummin + `merge_asof` backward (no look-ahead); `add_session_levels` broadcasts Asia/London/NY ranges only post-close. **primitives.py**: swings, `displacement_strength(20)`, 3-candle FVGs, `sweep_of_level`, OTE helper. **Honest-stream plumbing**: `tools_sim_parity_check.load_rows()` (canonical honest A, n=583, PF 1.361, folds the live cushion-gate + P3-brake), `tools_vpc_1m_truth.py` (the VPC 1m re-walk), `tools_salvage_vpc_reeval.py` (A+VPC portfolio join), `tools_opt_*.py` (the optimisation lanes).

---

## 7. THE GRAVEYARD — everything killed, with code location

| Family | Code | Verdict | Why |
|---|---|---|---|
| **Old certified machine** | (D1c research attach) | ⛔ INVALIDATED | Timestamp look-ahead (INC-1141): 47.8%/PF2.31/$12.7k were fiction |
| **Profile C (PD/FVG)** | `profileC_research.py` (C1 gapfill…C6 pdhpdl) | ⛔ DEAD | 0/32 families / 1,024 cells; PF<1.0 OOS; A-in-disguise |
| **Wyckoff playbook** | `tools_wyckoff_a_tags.py` (tags-only) | ⛔ NO EDGE | 398/400 dead; "no filter beats flat size" (now 9 replications) |
| **Gold vol-gated MR-short** | `tools_gold_lane_reval.py` + `position_sizer.py:22-48` | ⛔ DEAD | PF 1.45 was a 2023-26 window artifact; ext-window 0.94 @MGC, 5/8 losing yrs |
| **ES A-port** | `kronos_validate_*.py` | ⛔ DEAD | PF 0.718, neg 11/13 yrs — NQ-specific |
| **ES-ORB incumbent** | `lane_b_m4.py` | ⛔ CORRECTED | claimed PF 1.22 → honest 0.871 at 1m truth |
| **ES 14-model register** | `lane_a/b/c/d_*.py` (M1–M14) | ⛔ KILLED | ~5,000 cells; M1 ES-VPC dominated in portfolio; M8 watchlist-only-with-real-CME-data; CFD-proxy caveat |
| **NQ discovery (14 families)** | `nq_pattern_discovery/` | ⛔ NULL | no new edge; VWAP-fade retired by mechanism (extensions continue 11/11 yrs); stat-scan 21 vs ~794 under null |
| **Others** | various | ⛔ | Asian-Range (intrabar artifact PF2.03→0.9), high-WR MR (neg-skew trap), 5%/week (math-impossible), gold-BB-fade (margin artifact), YM 1.14/RTY 0.707, crude/crypto/FX/multi-pair |

**Live-adjacent survivors:** Profile A (live), Profile B / ORB (live-wired, overlay-safe per `reports/profile_b_overlay_research.md`), VPC (certified, not wired).

---

## 8. THE HONEST NUMBERS & THE STAGED DECISION

**Eval re-lock candidate (DRAFT, unsigned):** A @$900/cap-6 + VPC @$600/cap-3 → **37.4% pass / 18.0 bust / 44.6 expire**, flip 0.068R, funded/slot-yr 5.89, ~$2,861/attempt. Watch row A900/6+VPC700/3 (39.3/19.6/41.1, PROMOTABLE-PENDING-OPERATOR). **Funded survival machine:** kept-A 300/4 + VPC 150/1 → ~$9.0k E[paid], 2.4% bust. Exit choice Exit#3-vs-Fixed-1.5R is a separate certification item (1.5R +8% totR on honest stream). A-only sizing: cap-6 defensible; the expire-as-loss rescore showed the sim optimum runs to the grid boundary but it's fill-blind and statistically unresolvable from cap-6 at effective-N≈22 — any rightward move is N≥30-live-fill-gated.

**Validated by exhaustion across 3 instruments** — NQ (discovery null), gold (revalidation kill), ES (14-model kill) all confirm 37.4% is the honest frontier.

---

## 9. THE FOUR DEFECT CLASSES CAUGHT (each now a permanent canary)

1. **D1c timestamp look-ahead (INC-20260706-1141)** — research attach evaluated drift 4-5h after the fill. Fixed (index-derived, raise-don't-parse) + 2 canaries. **Live sibling in `latest_signal()` — FIXED 2026-07-07 (commit fafe12d): index-derived, typed-raise vs None (broken≠empty), permanent canary incl. DST edges. Arming blocker removed. NOTE: the ~4h shift meant the 10-min freshness gate was never meaningfully exercised — it becomes load-bearing on first real fill flow, watch early in N≥30.**
2. **Direction confound** — pooled context stats on a directional strategy (the VWAP-slope "PF 2.52") → mandatory interaction check.
3. **Denominator artifact (DEC-20260706-1108)** — pass% up while pass-count down → count-basis rule.
4. **Dependency drift (INC-20260706-1627)** — unpinned pandas 3.0.3 corrupted the 18:00-anchored daily resample → a ghost 548-trade stream. Pinned + gate canary.

---

## 10. STATUS MAP

| Component | Status |
|---|---|
| Profile A engine | LIVE-ROUTED, FROZEN |
| Profile B (ORB) | LIVE-WIRED, overlay-safe |
| VPC | CERTIFIED, Phase-0 sim-only, NOT wired |
| VPC live trail lane | DESIGNED, not built (gated on A N≥30 fills) |
| D1c live gate | causal, correct, `enabled=False` default |
| `latest_signal()` timestamp fix | **FIXED 2026-07-07** (fafe12d; index-derived, typed-raise, canaried) |
| Eval/funded simulators | built, canary-gated |
| Watchdog / telemetry / config locks | built, tested |
| Re-lock DEC | DRAFT, unsigned |
| LIVE HOLD | **ACTIVE — nothing armed** |

*Numbers trace to `reports/` in the bot repo; the pre-2026-07-06 "certified" numbers are invalidated history. This page is a reference snapshot as of 2026-07-07.*
