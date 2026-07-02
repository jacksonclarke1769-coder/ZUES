> ⛔ **OBSOLETE (pre-2026-07-02 machine).** This document describes a configuration/certification
> that was INVALIDATED by the 2026-07-02 audit (5m fill-bar look-ahead) and superseded by
> **ZEUS Production Machine v2026.07.02** — see `AGENTS.md` §"THE SELECTED MACHINE" and
> `reports/apex_validation.json`. Kept for historical reference only.

# Candidate Validation & Stress-Test Decision Memo — 2026-06-30

ZEUS NQ bot. Three candidates evaluated against the frozen live config under the required method
(IS/OOS time-split + 2nd split for stability, block-bootstrap MC ≥1000 paths with median/p5/p95),
then run through an independent adversarial stress-test. **Deploy bar = beats incumbent IN-SAMPLE
AND OUT-OF-SAMPLE AND at MC p5 AND survives the adversarial battery.** Anything less graduates to
PAPER-TEST at most. No live change is greenlit off backtest alone.

Incumbent live config (config_defaults.py): `EXIT3_FIXED_PARTIAL` — split into 2 OSO legs, shared
FIXED stop, scalp@+1R + core@+2R (Profile A) / +1.5R (Profile B); no trail/BE. Deployed stacks:
EVAL A10/B5/mm6; FUNDED P1 A4/B2/mm2 → P2 A6/B3/mm6.

---

## Summary table

| # | Candidate | Metric | Incumbent | Cand IS | Cand OOS | MC median / p5 / p95 | Validation | Stress-test | **FINAL VERDICT** |
|---|-----------|--------|-----------|---------|----------|----------------------|------------|-------------|-------------------|
| 1 | single@1R eval exit | Eval PASS% (EOD, A10/B5/mm6) | 59.3% full | 59.7 / 58.8(alt) | 71.4 / 67.5(alt) | 64.6 / 57.8 / 71.2 | deploy | keep-incumbent (unreproduced + un-run break-tests) | **NEEDS-MORE → re-run to completion, then PAPER-TEST** |
| 2 | A3/B1/mm0 phase-1 grind | P(reach lock), funded 18mo | 79.8% full / 89.3% OOS | 80.0 / 71.9(alt) | 100 / 100(alt) | 87.2 / 86.0 / 88.3 | deploy | keep-incumbent (breaks 2021 regime; OOS ≈1 path) | **KEEP-INCUMBENT** |
| 3 | B-partial fidelity (reporting) | Eval PASS% reported | 57.5% (understated) | 59.8 / — | 65.8 / 62.0(alt) | 59.5 / 52.5 / 67.8 | deploy | deploy (reproduced exactly + battery passed) | **DEPLOY (reporting fix, zero live-exec risk)** |

---

## Candidate 1 — single@1R eval exit (full position to fixed +1R, shared −1R stop)

**Incumbent:** EXIT3_FIXED_PARTIAL 50/50 (A: 0.5@+1R + 0.5@+2R; B: 0.5@+1R + 0.5@+1.5R), config-locked.
**Metric:** Apex-50K eval PASS% (EOD-drawdown, A10/B5/mm6, $550 daily stop, 30-day clock), real
Databento NQ, ~1183 rolling 1-per-trading-day evals.

- **IS:** 59.7% (2021-24) vs incumbent 57.0%; alt-IS 58.8 vs 56.0 — beats on both.
- **OOS:** 71.4% (2025-26) vs 64.9%; alt-OOS 67.5 vs 62.7 — beats on both, by a large +6.5pt headline.
- **MC (1200 paths, 10-day blocks):** median 64.6 / p5 57.8 / p95 71.2; candidate p5 (57.8) ≈ incumbent
  median — clears the p5 bar on the validation run.
- Also improves total-R (383 vs 321 @ size 1) and A-leg max DD (−9.3R vs −12.9R) → not buying WR with expectancy.
- Mechanism (plausible, not artifact): eval must reach +$3k before the $2.5k EOD trail busts within
  30d; the tighter +1R target hits far more often → steadier climb, smaller DD, fewer busts, faster
  passes. The config-lock's stated fear was WIDE targets (single@2R = worst, 52.2%, −18.4R DD, breaches
  buffer); single@1R is the opposite (tighter, lower DD).

**Stress-test outcome — KEEP-INCUMBENT (unconfirmed, not refuted):** the adversarial reviewer could
NOT independently reproduce the result inside the compute window — the 1200-path MC across 4 variants
was still running at finalize, so not one reproduced number (not even the 57.5% sanity gate) was
personally seen. The decisive break-tests were **written but un-run**:
`exit_model_adversarial.py` (per-calendar-year pass% incumbent vs candidate, worst 80-start rolling
window, cost/slippage +1tk/+2tk+commission, bucket sample sizes). The reviewer DID audit the method
as sound — `exit_model_validate.py:46-66` re-simulates A through the validated engine
(`model01_sweep_mss_fvg.py:_simulate:445-507`), `b_sim:70-154` replicates the deployed B bar-walk
(matching `apex_eval_deployed.py:116-135`), EOD rule reused correctly (`apex_eval_eod.py:eval_eod:25-52`),
and the sanity anchor (A-incumbent + B-single1.5R == 57.5%) is the right gate.

**Reasoning / reconciliation:** the design is faithful and the mechanism is economically sound, but a
clean one-directional sweep across all four bars off a **single historical realization** is exactly the
pattern that demands per-year decomposition — and that decomposition has not been produced. Under the
explicit rule ("keep-incumbent if you cannot independently reproduce the OOS edge") the bar is not met.
This is a config-LOCKED safety setting; it does not graduate on plausible-but-unverified.

**FINAL VERDICT: NEEDS-MORE** (do not flip live).
**Next step:** run `exit_model_validate.py` to completion AND `exit_model_adversarial.py` (~7-10 min each).
Promote to PAPER-TEST only if ALL hold: (a) 57.5% sanity gate reproduces; (b) single@1R wins EVERY
individual calendar year vs incumbent; (c) survives +2tk + commission; (d) MC p5 still beats incumbent
median. Even then: PAPER-TEST first, then route through EXITLOCK/operator approval. **Scope:** EVAL-phase
target only — keep B PARTIAL_1R for the FUNDED phase (config_defaults.py:44).

---

## Candidate 2 — A3/B1/mm0 phase-1 grind (replace deployed A4/B2/mm2)

**Metric:** P(reach lock) — Apex 50K funded, EOD-drawdown, 18mo horizon, POST fixed A6/B3/mm6.

- **IS:** 80.0% (split1 2021-24) vs 77.8; 71.9 (split2 2021-23) vs 71.3 — marginal beat.
- **OOS:** 100% (both splits) vs 89.3 / 92.1 — decisive on paper.
- **MC (2000 paths, 20-bday blocks, paired):** median 87.2 / p5 86.0 / p95 88.3; paired ΔP(lock) p5 = **+3.4pt > 0**.
- Income cost ≈ zero: E[payout|funded] −$151 full; MC ΔE[payout] mean +$160, p5 −$678 / p95 +$1,007 (CI straddles 0).
- Full-history confirms operator claim: lock 83.5 vs 79.8 (+3.7pt), median days-to-lock 93 vs 39 (2.4× slower).

**Stress-test outcome — KEEP-INCUMBENT (two hard breaks):** harness reproduced exactly
(`p1_grind_validate.py`), but adversarial decomposition (`p1_grind_stress.py`, `p1_grind_stress2.py`)
found the edge is **regime-conditional** and the decisive OOS evidence is statistically empty:

- **BREAK 1 — loses the one adverse year, badly.** Per-start P(lock) by exact start-year: **2021 cand
  0.0% vs inc 22.6% (Δ−22.6pt, N=124)**; 2022 +13.7; 2023 tie; 2024 +5.8; 2025 +10.7. In 2021-start
  accounts the smaller A3/B1 size cannot reach the +$2,600 EOD lock before the 2021→22 adverse regime
  catches the still-live $2.5k trail — it banks NO floor. The deploy thesis ("smaller grind survives
  better") INVERTS in the only sustained-adverse regime in-sample. Fails the explicit per-year gate.
- **BREAK 2 — OOS rests on ~1 independent path.** 178 OOS-split1 starts span only 264 calendar days; at
  an 18mo (540d) lifecycle that is **1 non-overlapping account** (split2 OOS = 2). The 100% vs 89.3% is
  one lucky pass through the strong-trend 2025-26 regime — the single-path artifact the brief warned of.
- Worst rolling window (W=100): cand 8.0% vs inc 55.0% (Δ−47pt) in 2021-H2; 13-18% of all rolling windows have cand < inc.
- Non-breaks: cost actually WIDENS the gap in cand's favor (cand 83.5 vs inc 75.7 at +1tk+comm); MC paired
  Δp5 survives block-lengthening (+3.6 → +4.7pt at 20→120d). **But** the block-bootstrap reshuffles a
  predominantly benign 2022-25 history and structurally CANNOT regenerate a sustained 18mo adverse regime
  — so the MC p5 gate MASKS the 2021 failure rather than refuting it. p5 is necessary, not sufficient here.

**Reasoning:** income is neutral (no $ reason to swap), and swapping a deployed config bets the next
18mo resemble benign 2023-25, not adverse 2021-22. A candidate that goes to 0% lock in the only stress
regime, with OOS resting on a single path, does not graduate to replace a live config — regardless of a
technically-passing MC p5 that is blind to that regime by construction.

**FINAL VERDICT: KEEP-INCUMBENT** (deployed A4/B2/mm2 stands for phase-1).
**Next step:** NO ACTION on live config. If pursued later, A3/B1 needs (a) a regime-conditional stress
(survive a synthetic 2022-style bear) and (b) more independent OOS paths before it can even reach
paper-test. Promising in benign regimes; not robust.

---

## Candidate 3 — Profile-B partial fidelity correction (reporting, not optimization)

**What it is:** the deployed bot ALREADY runs Profile B as the partial (config_defaults.py:
`B_EXIT_MODEL='PARTIAL_1R'`, `exit3_split(5)=(2,3)` → 2 MNQ@+1R + 3 MNQ@+1.5R, shared 1R stop). The eval
harness/dashboard, however, models B as a full-size single 1.5R target, so it **under-reports** the
deployed pass-rate. This candidate points the harness at the real partial. **Live execution does not change.**

**Metric:** Apex-50K EOD eval PASS% for deployed A10/B5/mm6, real Databento NQ 1m→5m 2021-06..2026-06,
rolling 1-eval/day starts.

- **Incumbent (single-1.5R stand-in):** 57.5% full — reproduced EXACTLY in both validation and stress
  runs, confirming harness fidelity (this is the understated dashboard number).
- **Candidate (real partial):** 59.8% full (+2.3pp). IS +2.7/+3.5pp (split1/2). OOS 65.8 vs 64.6 (+1.2pp)
  / 62.0 vs 60.9 (+1.0pp) — beats in BOTH OOS windows.
- **MC (paired):** candidate median 58.5/59.5/60.1 (5/10/20d) vs incumbent 56.9/58.0/58.2; candidate
  absolute p5 51.7/52.5/53.1 **exceeds incumbent p5 50.1/50.8/51.0 in ALL three block sizes**.

**Stress-test outcome — DEPLOY (independently reproduced + adversarial battery passed):**
`bpartial_fidelity.py` reproduced exactly (incumbent 57.5 / candidate 59.8); `bpartial_adversarial.py`:

- **Per-year:** candidate beats incumbent in **5 of 6 calendar years** (2021 +5.6, 2022 +1.7, 2023 +4.1,
  2024 +0.8, 2025 +2.1pp). Lone loss 2026 −1.0pp (67.0 vs 68.0) is literally ONE extra bust on n=97
  (half-year), and flips to 0.0 at +1tk+comm. **BUST% is LOWER for the candidate in EVERY year.**
- **Cost/slippage:** full-history Δ INVARIANT at +2.3pp across B_COST 0.75/1.00/1.25 — cost is per-contract
  and identical in both arms, cancels in the paired diff. Edge is the variance/MAE structure, not a thin
  cost-fragile margin.
- **Mechanical prior (clincher):** banking 2/5 at +1R raises realized B P&L $24,370→$35,415 (+45%) and
  reduces summed MAE −$146,158→−$121,798 (~17% gentler). On an EOD rule that busts on bal+MAE
  (apex_eval_eod.py:47), both effects push pass UP; the only downside (slower target reach / expiry) is
  small and net-dominated.
- **Caveat (honest):** paired ΔMC p5 is +0.0/+0.3pp at 10/20d but dips to −0.2pp at the 5d block — i.e.
  in the worst ~5% of short-block resamples the partial is fractionally behind. This is re-timestamping
  noise: reducing position size after a +1R partial cannot mechanically increase drawdown.

**Reasoning:** this is a **fidelity correction**, not a config change. The action risk ≈ zero (reporting
only). It is mechanically grounded, cost-invariant, OOS-confirmed in both windows, wins 5/6 years, and
its absolute MC p5 beats the incumbent in all blocks. It clears the bar precisely because the "change"
carries no live-execution risk.

**FINAL VERDICT: DEPLOY (reporting fix).**
**Next step:** point the eval harness/dashboard at the partial-B model (`bpartial_fidelity.b_events_partial`)
so the deployed A10/B5/mm6 stack reports ~59.6-59.8% (≈58-60% MC median) instead of the understated 57.5%.
No change to live execution. Update the dashboard's published eval pass-rate accordingly.

---

## Honesty / sample-size caveats (all candidates)

- All three rest on a **single ~5-year historical realization** (real Databento, 2021-06..2026-06). MC is
  block-bootstrap over that one path; it cannot manufacture an unseen regime. Per-year decomposition is the
  real robustness check — it sank Candidate 2 and validated Candidate 3.
- Candidate 1's headline edge is genuinely promising but was **NOT independently reproduced this session**;
  treat its OOS/MC numbers as claimed-not-confirmed until the two harnesses finish.
- Per-trade sequential give-back on the intraday-liquidation leg is a deployed proxy (slightly optimistic),
  applied identically to every variant — relative rankings are fair, absolute levels carry a small upward bias.
- Funded lifecycle (Candidate 2) assumes EOD rule inherits from eval and has no 30-day clock — confirm vs contract.
- **No live change is greenlit off backtest alone.** The only action taken here is a zero-risk reporting fix.

## Bottom line / actions

1. **single@1R (eval exit): NEEDS-MORE.** Re-run validation + adversarial to completion; if it wins every
   calendar year and survives costs, graduate to PAPER-TEST (not live), then EXITLOCK/operator approval.
2. **A3/B1/mm0 (phase-1 grind): KEEP-INCUMBENT.** No action. Breaks in the only adverse regime (0% vs 22.6%
   in 2021) and OOS is ~1 path. Deployed A4/B2/mm2 stays.
3. **B-partial fidelity: DEPLOY (reporting).** Repoint harness/dashboard to the partial-B model; corrected
   deployed pass-rate ≈ 59.6-59.8%, not 57.5%. No live-execution change.
