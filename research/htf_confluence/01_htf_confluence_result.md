# HTF confluence chain — measurement result

Pre-registration: `PREREG_CHAIN.md`, commit `eaef4a4` (frozen 2026-07-20, before any result was
computed or seen). This run implements exactly that spec — zero threshold changes, no combination
search. Code: `chain.py` (detectors + adapted walker), `self_test_chain.py` (shift-invariance),
`test_fill_sequencing_chain.py` (fill-path regression), `null_test_chain.py` (Step 3a),
`gate_d_chain.py` (live-achievable), `run_all.py` (driver). Artifacts: `results/01_result.json`
(committed); `trade_ledgers/*.json` (local only, not committed, per task instructions).

## Verdict: **INSUFFICIENT-N**

Holdout n = 7 (< the pre-registered floor of 30). Per PREREG_CHAIN.md's own gate ("a high-PF /
low-n result is INSUFFICIENT, not an edge"), no significance claim can be made regardless of the
PF/expectancy numbers below. At the observed holdout firing rate (7.0 trades/yr) reaching n≥30
would need **~4.3 years** of holdout data — i.e. essentially the entire remaining useful life of
this single 5-year dataset, so this chain cannot be adequately measured on the available history
without either accepting a materially longer holdout or changing the chain (which this
pre-registration does not permit). This is reported as the frozen-chain outcome, not worked
around.

Two secondary facts corroborate that this is a real thinness problem, not a hidden edge being
masked: (a) holdout total R does **not** beat the null 95th percentile (real +2.42R vs null p95
+3.07R, 90.3rd percentile of the null distribution — see Step 3), and (b) train and holdout point
in opposite directions (train PF 0.50 / −1.04R vs holdout PF 3.37 / +2.42R) on 6 and 7 trades
respectively, which at this n is exactly the kind of sign flip pure variance produces.

---

## Step 1 — fill-path pre-gate

**Regression test** (`test_fill_sequencing_chain.py`, adapted from
`concept_survey/test_fill_sequencing.py`), run against `chain.run_chain` directly: **2/2 PASS**.
- Synthetic bar spanning both the proximal-edge entry and the structural stop → booked
  `reason='stop_samebar'`, R < 0 (filled-then-stopped, never cancelled).
- Synthetic bar touching the distal-edge invalidation strictly before the entry is ever touched →
  correctly a real cancel (0 trades) — confirms the gate is checking the right convention, not
  "always book a trade."

**Shift-invariance self-test** (`self_test_chain.py`, self_test.py pattern): full-buffer run vs.
an 8,000-1m-bar-truncated run, 3-day safety margin. **3/3 detectors PASS byte-identical**
(1H bias: 14,351/14,351 keys match; 15m sweep: 180/180; combined sweep+FVG+displacement
candidates: 41/41). No lookahead in any HTF detector used by this chain.

**Physical check — reported honestly, with the reconciling evidence, per the task's mandatory
gate**: the literal check (does the ledger contain a fill-bar-breaches-stop / instant-loss
population?) comes back **zero** on the real ledger:

| population checked | n |
|---|---|
| `stop_samebar` trades in the position-sequenced full-2y ledger (n=13 trades) | 0 |
| same-bar entry+distal-invalidate touch, across **all 41 raw candidates** (bypassing the one-position-at-a-time filter, so sequencing-starvation is ruled out as the cause) | 0 |
| same-bar entry+structural-stop touch, across all 41 raw candidates | 0 |

This is literally the pattern PREREG_CHAIN.md calls "the bug fingerprint," and by the letter of
the pre-registration this run does **not** proceed to trust a performance number on the strength
of Step 1 alone. Two independent pieces of evidence establish this is **not** the survey's
same-bar-cancellation bug and is instead a structural/geometric fact about this specific chain,
not a masking defect:

1. The regression test above exercises the *identical* code path (`run_chain`) on a synthetic bar
   engineered to touch both prices and it books the loss correctly — the mechanism that would be
   silently deleting these trades if present is demonstrably absent from the code.
2. Unlike Fork-A / the concept-survey's single-level FVG/OB/Breaker setups (where the resting
   limit and its invalidation are typically one tick apart), this chain's own construction places
   **three distinct, well-separated prices** in play: the proximal entry (candle-3 edge), the
   distal invalidation (candle-1 edge, further away), and the true structural stop (the sweep
   extreme, further still, beyond the distal edge). For a single 1-minute NQ bar to touch the
   entry and then also breach the stop, price would need to travel through the entire remaining
   FVG *and* past the sweep extreme within 60 seconds — a magnitude of move essentially absent
   from 1m NQ bars at the risk sizes this chain draws (double-digit points; see `risk_pts` in the
   ledger). Zero occurrences in a 41-candidate / 13-trade sample is the expected outcome of this
   geometry, not evidence of a masking bug.

Given n is already disqualifying on Step 4's own terms (7 < 30), no performance number in this
report is being relied on as a significance claim either way — the physical-check finding is
surfaced in full per the mandatory reporting instruction, not smoothed over.

---

## Step 2 — train / holdout / quarterly / live-achievable

Raw-backtest and live-achievable (5m-poll emulation + 10-min `certified_gate` staleness,
Gate D methodology adapted from `concept_survey/gate_d.py`) figures, per window:

| window | n | WR | PF | total R | expectancy | avg win | avg loss | live n | live PF | live totR | live expectancy | suppressed (R-wtd) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TRAIN (2024-06-22 → 2025-06-22) | 6 | 0.500 | 0.504 | −1.039 | −0.173 | 0.352 | −0.698 | 4 | 0.262 | −1.546 | −0.387 | 16.1% |
| HOLDOUT (2025-06-22 → 2026-06-22) | 7 | 0.857 | 3.372 | +2.415 | +0.345 | 0.572 | −1.019 | 7 | 3.372 | +2.415 | +0.345 | 0.0% |
| Full 2y | 13 | 0.692 | 1.434 | +1.350 | +0.104 | 0.496 | −0.778 | 11 | 1.279 | +0.869 | +0.079 | 6.4% |

Certified-gate literal staleness (fill instant >10 min old at the earliest 5m poll) was 0.0% R-
weighted in every window — consistent with `gate_d.py`'s own structural note: this chain's
signals are clean single-instant confirmations (limit resting from the FVG's own candle-3 close),
so the maximum possible poll latency is under 5 minutes, always below the 10-min threshold. The
substantive live-vs-raw effect is the poll-delay order-timing shift itself (`poll_ts` vs
`conf_ts`): it cost train 2 of 6 trades (both `poll_after_order_end` — the 5m poll landed after
the arm window had already closed) and cost nothing in holdout.

Quarterly walk-forward (8 equal ~91-day quarters spanning the full 2y window, matching
`run_train.py`/`run_holdout.py`'s own quarter convention):

| quarter | n | totR |
|---|---|---|
| 2024-06-22 → 2024-09-21 | 1 | −1.016 |
| 2024-09-21 → 2024-12-21 | 1 | +0.012 |
| 2024-12-21 → 2025-03-22 | 4 | −0.036 |
| 2025-03-22 → 2025-06-22 | 0 | 0.000 |
| 2025-06-22 → 2025-09-21 | 1 | +0.506 |
| 2025-09-21 → 2025-12-21 | 1 | +0.171 |
| 2025-12-21 → 2026-03-22 | 2 | +0.440 |
| 2026-03-22 → 2026-06-22 | 3 | +1.299 |

Zero to four trades per quarter — this chain fires far too rarely for a quarter-level pattern to
mean anything; it is listed for completeness, not interpreted.

---

## Step 3(a) — null (randomized-entry test)

Methodology: 1,000 runs; each run draws the same number of entries as the real window's trade
count, from the **same bias/session-eligible bars** — i.e. bars where the 1H bias (Condition 1)
equals the entry's own direction (176,989 LONG-eligible / 105,449 SHORT-eligible 1m bars in
holdout) — with the entry's own direction preserved (matching the real long/short split), the
same pooled stop-distance distribution (real trades' `risk_pts`, drawn with replacement), the
same target rule (nearest opposite liquidity ≥1×ATR(15m) else 2R fallback, via the identical
`_nearest_target` helper) and the same costs ($1 round-turn, 1-tick slip). One position at a time,
EOD flat, across both directions. No additional session-hours filter beyond the bias gate itself
is applied (documented resolution — the chain has no stated trading-hours restriction beyond
EOD-flat; sweeps/FVGs may form at any hour, matching `chain.py`'s own detectors).

| window | n_draws | n_runs | real totR | null p95 | null mean | null median | beats null 95th? | real's percentile in null dist |
|---|---|---|---|---|---|---|---|---|
| TRAIN | 6 | 1000 | −1.039 | +2.633 | −0.046 | −0.102 | **NO** | 28.8th |
| HOLDOUT | 7 | 1000 | +2.415 | +3.069 | +0.002 | +0.016 | **NO** | 90.3th |

Holdout does **not** clear the pre-registered null bar (95th percentile) — it lands at the 90.3rd
percentile of the null distribution, i.e. a randomized-entry strategy drawing from the same
bias-eligible bars, with the same stop-size distribution and the same target rule, beats the real
chain's holdout total R about 1 run in 10. This is consistent with — not contradicting — the
n-adequacy verdict: at n=7 the null test itself has essentially no power to distinguish a real
edge from noise either way.

---

## Step 3(b) — Profile A overlap (holdout window)

`research/atlas/profile_a_edge/outputs/signals_583_classified.csv` (`achievable == True`,
restricted to the holdout window; note this file lives at
`/Users/jacksonclarke/trading-team/research/atlas/profile_a_edge/outputs/` — the repo-relative
path in the task does not exist under `bot/nq-liq-bot/`; resolved to the actual file, matching
`concept_survey/correlate.py`'s own `PA_CSV` constant).

- Profile A: 74 achievable signals across 69 distinct trading days in holdout.
- This chain: 7 trades across 7 distinct trading days in holdout.
- **Fill-day Jaccard (trading dates): 4 / 72 = 0.0556.** Only 4 of the chain's 7 firing days
  overlap with a Profile-A trading day; **3 of 7 (43%) fire on days Profile A has zero signals
  at all.**
- On the 4 shared days, this chain's mean daily R (+0.575) exceeds Profile A's mean daily R on
  those same days (−0.132); over the full holdout window, this chain's overall expectancy
  (+0.345/trade) also exceeds Profile A's (+0.128/trade).

Per PREREG_CHAIN.md's own scoring rule ("valuable ONLY if (a) higher holdout expectancy than A on
shared setups OR (b) fires on different days"), **both (a) and (b) point toward the chain not
being a redundant re-sample of Profile A** — it is largely decorrelated (low Jaccard, days with
zero A activity) and, on the handful of days it does share, out-expectancies A. However this
descriptive comparison rests on **n=4 shared days / n=7 total chain trades** and cannot itself
carry a "REAL & ADDITIVE" conclusion — it is reported as a directional, low-power observation
consistent with (not proof of) decorrelation, subordinate to the disqualifying Step 4 n-floor.

---

## Step 4 — n-adequacy (the binding gate)

- Pre-registered floor: n ≥ 30 in holdout.
- Observed: **n = 7**.
- Firing rate: 7.0 trades/year (holdout window ≈ 1.00 yr).
- Years of holdout data needed to reach n ≥ 30 at this rate: **≈ 4.3 years** — more than 4× the
  entire holdout window, and close to the full 5-year span of the available Databento history.

**Verdict: INSUFFICIENT-N.** No REAL/REAL-REDUNDANT/NULL claim is licensed by this sample; the
chain fires far too rarely (5-condition AND-chain: 1H bias agreement AND a single-15m-bar sweep
AND a same-bar reclaim AND a displacement-gated FVG within an 8-bar arm window AND bias still
agreeing at FVG confirmation) for this instrument/window to produce a statistically usable holdout
sample. This is filed in the graveyard: this exact frozen chain is not to be re-tested on this
same data without a materially longer holdout or a new pre-registration with its own fresh
holdout.

---

## Documented literal-reading resolutions (frozen, not tuned)

1. **FVG proximal/distal edge.** The prereg's bullish-case parenthetical ("the gap's
   lower/top-of-lower-candle edge") is geometrically inconsistent with its own decisive clause
   ("i.e. the edge price first re-touches on the return") — candle-1's high is the *far* edge on
   a bullish retracement (price returns down from above and reaches candle-3's low first).
   Resolved via the unambiguous, standard-ICT clause: **proximal = the edge belonging to
   candle-3** (first touched on the return), **distal = the edge belonging to candle-1**
   (reached only if the gap fully fills). Symmetric for bearish.
2. **Bias-gate scope.** Condition 1 is checked at the sweep bar's close and again at the FVG's
   candle-3 close (setup formation); **not** re-checked a third time at the moment the resting 1m
   limit fills (entry is order mechanics for an already-validated setup).
3. **"Next 8 15m bars"** read as 8 bar-count (not clock-elapsed time); "(2 hours)" is the
   normal-case equivalent, not an independent constraint.
4. **"Prior RTH session"** pool = the most recently *closed* RTH session's H/L, known from that
   session's 16:00 ET close; used both as the Condition-2 sweep pool and, on the opposite side,
   as one of the two Condition-5 target-liquidity pools (the other being confirmed 15m opposing
   swings).
5. Window-boundary timestamps are UTC calendar timestamps matching the data's own UTC index
   (same resolution as `concept_survey/survey_engine.py`'s own documented choice).

## Artifacts

- `chain.py` — detectors (1H bias, 15m sweep, 15m FVG+displacement, candidate build) + adapted
  walker (`run_chain`).
- `self_test_chain.py` — shift-invariance self-test (3/3 PASS).
- `test_fill_sequencing_chain.py` — fill-path regression (2/2 PASS, pytest-collectible).
- `null_test_chain.py` — Step 3(a) randomized-entry null.
- `gate_d_chain.py` — Step 2 live-achievable (Gate D) re-walk.
- `run_all.py` — driver; writes `results/01_result.json` (committed).
- `trade_ledgers/*.json` — full per-window trade ledgers + all 41 raw candidates (**local only,
  not committed**).
- `PREREG_CHAIN.md` — the frozen spec (commit `eaef4a4`), unmodified.
