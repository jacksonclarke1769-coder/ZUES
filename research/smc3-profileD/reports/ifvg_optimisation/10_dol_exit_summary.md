# 10 — DOL Exit-Model Audit: Summary

Research-only. Entries FROZEN (`smc3_engine.py` default `Config()`, entry logic
untouched — only the exit rule varies). n = 5,056 closed baseline trades
(NQ 1m, 2021-06-23 → 2026-06-22, $2.50/side + 1 tick adverse per fill).
Code: `dol10_levels.py` (causal DOL construction), `dol10_walker.py` (generic
bar-walk exit resolver), `dol10_pathstats.py` (Step 1), `dol10_battery.py`
(Step 3, 34 models), `dol10_stress.py` (Step 4 stress). Data:
`10_path_stats.csv`, `10_dol_exit_audit.csv`, `10_dol_exit_stress.csv`.

## 1. Touch-probability ladder (THE core diagnostic)

P(price reaches +xR BEFORE the frozen stop), walked bar-by-bar from the
1m bar after entry, horizon 4,000 bars (~2.8 days), stop-first-within-a-bar:

| rung | ALL (n=5056) | breakeven threshold | NY-AM 09:30-12:00 (n=1255) |
|---|---|---|---|
| +0.5R | 66.9% | 66.7% | 66.9% |
| +1.0R | 50.4% | 50.0% | 52.1% |
| +1.5R | 41.0% | 40.0% | 42.0% |
| +2.0R | 34.3% | 33.3% | 35.2% |
| +3.0R | 25.3% | 25.0% | 25.3% |

**Every single rung sits within ~0.1-1.0 percentage point of its own
risk:reward breakeven threshold** (1/(1+R)). P(+2.0R)=34.3% is a near-exact
match to the live fixed-2R baseline's realized WR (34.36%) — not a
coincidence, a confirmation that the touch distribution and the realized
trade outcomes agree. This is the "entry is intrinsically breakeven at
every rung" signature the spec called out: no fixed-R re-target (1R, 1.5R,
2.5R, 3R, or any DOL-implied distance) has a built-in statistical edge here
— any positive-looking model below is winning (if at all) on WHICH bars/years
it fires in and on DOL-selection idiosyncrasy, not on a genuine
edge in the raw MFE distribution.

Per-year ladders (P(+2R)): 2021 33.6% · 2022 33.9% · 2023 33.1% · 2024 37.0%
· 2025 34.6% · 2026 33.1% — flat across 6 years, reinforcing "no regime
where the raw touch-ladder clears breakeven by a real margin."

## 2. Causal DOL coverage & timing (all trades, headline set pooled)

- Headline causal DOL exists at entry: **5,052 / 5,056 (99.9%)**. Sources:
  PDH/PDL, prior-week H/L, overnight H/L, prior-session H/L, confirmed 1H
  swing, confirmed 4H swing, equal H/L (1H pool, ≥2 confirmed pivots ≤4
  ticks), HTF pocket (SMC3's own 60m/3-3 confirmed level). Session-so-far
  H/L is tracked but excluded from this headline pool per the hardened spec.
- Avg nearest-DOL distance: **1.126R**.
- DOL hit before stop: **69.7%**. DOL hit before the fixed 2R target: **84.5%**.
  2R hit before DOL (among trades with a DOL): 12.6%. Neither DOL nor 2R
  reached before the stop/horizon: 28.6%.
- DOL distance buckets: <0.5R 62.3% · 0.5-1R 13.6% · 1-2R 10.4% · 2-3R 4.6%
  · >3R 9.2%. **The pooled "nearest of everything" DOL is usually VERY close**
  (62% of the time <0.5R away) — this is why targeting it directly
  (`dol_nearest_any`) performs WORSE than baseline (see §3): it's a tight
  scalp target, hit often but for very little R, while the stop still
  costs a full -1R.
- Causality: **0 artifacts** — every per-source array is built via
  searchsorted on a CLOSED boundary (day/week/overnight/session close, or
  pivot-confirmation-bar close for 1H/4H/equal-H/L/HTF-pocket) with an
  in-code `assert known_at <= entry_time` that holds for all 5,052 DOL-bearing
  trades (checked, not assumed). The 4 trades (0.08%) with no headline
  candidate are a legitimate "no liquidity level found" state, not a
  causality violation.

## 3. Headline 7-model comparison (operator-mandated set)

| # | model | n | WR% | PF(R) | avgR | ex-2024 avgR | ex-Fri avgR | yrs+/6 | artifacts |
|---|---|---|---|---|---|---|---|---|---|
| H1 | fixed 2R (baseline) | 5056 | 34.4 | 0.985 | −0.0106 | −0.0287 | −0.0339 | 2 | 0 |
| H2 | nearest causal DOL (any source, pooled) | 4957 | 60.7 | 0.843 | −0.0496 | −0.0524 | −0.0570 | 0 | 0 |
| H3 | TP1@1R + TP2@nearest-DOL | 4957 | 45.9 | 0.878 | −0.0469 | −0.0569 | −0.0584 | 0 | 0 |
| H4 | DOL only if 0.75R≤dist≤3R (skip else) | 995 | 42.0 | 0.916 | −0.0512 | −0.0856 | −0.0394 | 2 | 0 |
| H5 | skip if no valid DOL exists | 4957 | 60.7 | 0.843 | −0.0496 | −0.0524 | −0.0570 | 0 | 0 |
| H6 | skip if DOL<0.5R | 1824 | 39.9 | 0.861 | −0.0885 | −0.0876 | −0.0888 | 1 | 0 |
| H7 | skip if DOL>3R | 4570 | 64.9 | 0.862 | −0.0361 | −0.0472 | −0.0413 | 1 | 0 |

**H5 is mechanically identical to H2** (only 4/5056 trades, 0.08%, have no
DOL, so "use DOL, else nothing" and "skip if no DOL" produce the same
population and the same numbers here — reported honestly rather than
padding the table with a duplicate-looking-different row).

**Every one of the mandated headline-7 models is negative** (avgR and
ex-2024 avgR both < 0), including the frozen 2R baseline itself. None
clears any promotion bar. The pooled "nearest of any source" DOL target
(H2/H5/H3/H4) is *worse* than doing nothing different (H1) — it's biased
toward very-close, low-value levels (§2).

## 4. Where the ONLY positive signal in the whole battery comes from

Outside the mandated headline-7, three **single-source-only** DOL models
(family "#4 DOL targets", not the pooled-nearest family) are the only
ex-2024-positive rows in the entire 34-model battery:

| model | n | WR% | PF(R) | avgR | ex-2024 avgR | ex-Fri avgR | yrs+/6 | long/short avgR | NY-AM avgR (ex-2024) |
|---|---|---|---|---|---|---|---|---|---|
| dol_htf_pocket_only (SMC3's own 60m/3-3 level) | 3773 | 21.7 | 1.103 | +0.0842 | +0.0873 | +0.0937 | 5/6 | +0.114 / +0.058 | +0.019 (−0.037) |
| dol_prior_session_only (18:00-ET PSH/PSL) | 3033 | 14.4 | 1.037 | +0.0327 | +0.0122 | +0.0483 | 4/6 | +0.097 / −0.019 | −0.0001 (−0.141) |
| dol_PDH_PDL_only | 3185 | 15.6 | 1.028 | +0.0250 | +0.0144 | +0.0401 | 4/6 | +0.085 / −0.025 | +0.063 (−0.099) |

Top 5 by ex-2024 avgR overall: the three rows above, then
`dol_session_so_far_only` (non-headline variant; ex-2024 avgR −0.0285,
NEGATIVE) and `fixed_2R_baseline` (ex-2024 avgR −0.0287, NEGATIVE) — i.e.
**only 3 of the 34 exit models are ex-2024-positive at all**, and only
one of them (`dol_htf_pocket_only`) is positive in a clear majority of
years (5/6) and on both the ex-2024 and ex-Friday cuts simultaneously.

## 5. Stress test (top 3 rows: 2x costs, −0.01R slip, −0.02R slip)

| model | variant | n | avgR | avgR_ex2024 | PF(R) |
|---|---|---|---|---|---|
| dol_htf_pocket_only | base | 3773 | +0.0842 | +0.0873 | 1.103 |
| dol_htf_pocket_only | 2x costs | 3773 | +0.0701 | +0.0733 | 1.084 |
| dol_htf_pocket_only | −0.01R slip | 3773 | +0.0569 | +0.0601 | 1.068 |
| dol_htf_pocket_only | **−0.02R slip** | 3773 | **+0.0296** | **+0.0329** | **1.034** |
| dol_PDH_PDL_only | base | 3185 | +0.0250 | +0.0144 | 1.028 |
| dol_PDH_PDL_only | 2x costs | 3185 | +0.0107 | +0.0002 | 1.012 |
| dol_PDH_PDL_only | −0.01R slip | 3185 | **−0.0027** | **−0.0132** | 0.997 |
| dol_PDH_PDL_only | −0.02R slip | 3185 | −0.0304 | −0.0408 | 0.967 |
| dol_prior_session_only | base | 3033 | +0.0327 | +0.0122 | 1.037 |
| dol_prior_session_only | 2x costs | 3033 | +0.0183 | **−0.0020** | 1.020 |
| dol_prior_session_only | −0.01R slip | 3033 | +0.0048 | −0.0155 | 1.005 |
| dol_prior_session_only | −0.02R slip | 3033 | −0.0230 | −0.0432 | 0.976 |
| fixed_2R_baseline (reference) | all variants | 5056 | negative throughout | negative throughout | <1.0 |

`dol_htf_pocket_only` is the ONLY row that stays positive (avgR and
ex-2024 avgR both) under every stress test. `dol_PDH_PDL_only` flips
negative at just −0.01R extra slip. `dol_prior_session_only` flips
ex-2024-negative at 2x costs alone.

## 6. Direct answer to the framing question

**Was 2R structurally wrong (DOL beats it on the same entries), or is the
entry itself edgeless (no exit model goes ex-2024-positive)?**

Mostly the latter, with one narrow, fragile exception:

- The raw touch-ladder (§1) shows the entry has **no built-in
  risk:reward edge at ANY rung** — every threshold sits within ~1pp of its
  own breakeven, in every year. That is direct, entry-level evidence the
  setup is not mis-targeted so much as **intrinsically ~coin-flip**, which
  independently corroborates BASELINE.md's read of the frozen 2R model.
- Of the 34 exit models tested (including the 7 mandated headline
  models), **31 are ex-2024-negative** at PF(R)<1.0, i.e. changing HOW you
  exit does not, in general, rescue this entry set — consistent with
  "no exit model can save an edgeless entry."
- **But** it is not perfectly clean: 3 single-source DOL models
  (SMC3's own 60m HTF pocket, prior-session H/L, PDH/PDL) ARE ex-2024- and
  mostly-multi-year-positive, and the best of them
  (`dol_htf_pocket_only`, PF 1.103, avgR +0.084, 5/6 years, survives 2x
  costs and −0.02R slip) is a genuine, causally-clean, cost-surviving
  signal — **it just never reaches PF(R)>1.20** at any stress level, so it
  fails the promotion bar on magnitude, not on robustness. This reads as
  "2R was somewhat structurally wrong in that a *specific, farther, more
  selective* DOL (not the naive 'nearest of everything' pool) does better
  than the frozen fixed target" — but the improvement is modest (PF
  ~1.10, not >1.20) and concentrated in a narrower trade population
  (3,773/5,056, 75% of the frozen set) rather than a full-set rescue.
- The pooled "nearest causal DOL (any source)" — which is what most
  practitioners would build first, and is the mandated H2/H5 — is
  actually **worse** than the frozen baseline, because pooling makes the
  target too close, too often (62% of pooled-nearest DOLs are <0.5R away).
  Selectivity (a single, farther, structurally-meaningful source) matters
  more than "nearest wins."
- NY-AM does **not** carry the (small) edge found here: all three
  candidate models are ex-2024-NEGATIVE on the NY-AM subset (−0.037,
  −0.141, −0.099 respectively) — the modest edge, where it exists, is
  coming from other session hours, not the NY-AM window flagged as a
  research lead in `00_current_state.md`.

## Caveats

- **n differs per model** by design (sequential single-position replay):
  longer-holding exit rules (higher fixed-R, DOL-conditional skips) block
  more subsequent entries via `busy_until`, and skip-rules (no DOL /
  DOL-out-of-range) additionally drop individual trades. Reported per
  model in `10_dol_exit_audit.csv` (`n_skipped_rule`, `n_skipped_busy`).
- **Time/failure family** (15/30/60min, NY-AM-end, session-close,
  opposite-DOL-swept) uses the frozen **2R** price as "target," per the
  most literal reading of the spec (this family is listed separately from
  the DOL-target families); a DOL-targeted variant of the same time-caps
  was not run.
- **Equal-H/L pool** is built only from the 1H confirmed-pivot pool (not
  also 4H/daily) — a narrower construction than "any timeframe."
- **Confirmed 1H/4H generic swings** use pivot length 2 (standard
  convention), distinct from SMC3's own HTF-pocket source (60m, pivot
  length 3 — the model's own internal level, recomputed byte-parallel to
  `smc3_engine.py`, not re-imported, so nothing in `smc3_engine.py` needed
  further changes beyond the one additive `entry_idx` field).
- **Weekly/overnight/daily close boundaries** use conservative (generous,
  not tight) safe upper bounds (next-Monday 00:00 ET / 09:30 ET / next ET
  midnight) — consistent with the existing `sweep_engine.prior_levels`
  convention in this repo; real weekly close (~Fri 17:00 ET) is a bit
  earlier, so PWH/PWL becomes "known" slightly later than strictly
  necessary (conservative direction, not a lookahead risk).
- **Horizon = 4,000 1m bars** (~2.8 days) for both the path-stats walk and
  every exit-battery model; `pct_horizon_timeout` is ≤0.8% for every model
  tested (0% for most) — the horizon is not a binding constraint for the
  overwhelming majority of trades.
- **Sunday-session small-n**: all 3 positive single-source models show
  outsized avgR on Sunday-entry trades (n=80-103, avgR +0.63 to +0.95) —
  flagged as a possible small-sample skew, not separately corrected for or
  excluded from the headline numbers above.
- **Partial-tranche costs** are charged per-tranche (each exit fill pays
  its own $2.50 + 1 tick), a conservative (not generous) assumption for
  every partial/hybrid model.
- **NY-AM columns in the battery** are a slice of the ALL-SESSION frozen
  entry set (entries whose entry_time falls in 09:30-12:00 ET), not a
  separate entry-restricted re-run — not directly comparable 1:1 to the
  dedicated NY-AM-restricted-entry Candidate 2 in `00_current_state.md`
  (which re-runs the engine with `useSession=True`, changing which trades
  get blocked by concurrent open positions).
- Files changed/added are all inside `smc3/`; the only change to an
  existing file is one additive field (`entry_idx`) in `smc3_engine.py`'s
  `_finish()` return dict — verified byte-identical baseline metrics
  (n=5056, WR 34.36%, PF 1.036, totalR −52.9) before and after.
