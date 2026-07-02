> ⛔ **OBSOLETE (pre-2026-07-02 machine).** This document describes a configuration/certification
> that was INVALIDATED by the 2026-07-02 audit (5m fill-bar look-ahead) and superseded by
> **ZEUS Production Machine v2026.07.02** — see `AGENTS.md` §"THE SELECTED MACHINE" and
> `reports/apex_validation.json`. Kept for historical reference only.

# ZEUS NQ Bot — Full Strategy Audit

**Date:** 2026-06-30  •  **Scope:** Fidelity (bot vs backtest), Integrity (look-ahead / overfit / regime / realism), Optimality (eval / Phase 1 / Phase 2 configs + exit model)  •  **Evidence base:** existing validated harnesses on real Databento ~5y NQ 1m (`run_d1c_real`); cited as `file:line`.

---

## 1. VERDICT

**(i) Does the bot faithfully reflect the validated strategy?**
**Mostly yes — with one material modelling gap that runs in the operator's favour.** The entry/signal layer is faithful and look-ahead-clean (Profile A OTE, Profile B ORB, Momentum signal math all reproduce the deployed logic; see §2 info findings). The one real fidelity defect is that the **eval harness models Profile B as a single 1.5R bracket, while the live bot runs the validated PARTIAL_1R exit** (50% @ +1R, 50% @ +1.5R). Because the partial *reduces* B drawdown and lifts PF (1.20→1.40, maxDD −36R→−9R per research), the stored 57.5%/68% eval pass-rates **understate** the deployed config — a conservative error, not a risk-creating one. Three lower-severity momentum modelling gaps (overlap gate, 120pt cat-stop, cost convention) also make the backtest a mild *pessimistic* bound on momentum.

**(ii) Is there anything wrong with the strategy itself?**
**The edges are real, causal, and low-degrees-of-freedom — but two integrity flags are material.** (a) **Momentum is extreme-right-tail dependent**: the top ~20% of trades produce ~97% of profit; it loses on <30-min whipsaws (65% of trades, WR 11%) and wins almost entirely on >2h runners (PF 51.6 on that bucket). Its PF/Sharpe rest on a thin runner tail and collapse in regimes that suppress runners (2026 pre-upgrade PF 1.02). **And it is currently ARMED on the Apex funded account** (`auto_safety.py:91-95`, A4/B2/mm2 & A6/B3/mm6), mitigated only by the $550 daily stop + P3 brake — more aggressive than the audit recommendation. (b) **A4/B2/mm2's funded survival edge is sourced from the least-trustworthy stream** (the daily-aggregate momentum proxy): mm0 → mm2 lifts lock 68.8%→79.8%, and the proxy structurally cannot model the intraday $1k daily-kill that `auto_safety.py:82` itself warns is fatal. Profile A and B themselves are clean, frozen-param, all-years-positive (B only via its partial overlay).

**(iii) Are we using the best config for eval / Phase 1 / Phase 2?**
- **EVAL: KEEP.** A10/B5/mm6 is the validated pass-rate AND cost-to-fund optimum (57.5% Databento / 59.5% proxy; both engines rank it #1; near-zero 2.9% expire beats the 30-day clock). The contract cap never binds. No grid config beats it.
- **PHASE 1 (grind to lock): CHANGE-AND-TEST.** Deployed A4/B2/mm2 maximises *E[payout]* ($19,419) but only 79.8% lock. **A3/B1/mm0** reaches 83.5% lock at ~equal payout ($19,268, −0.8%) and **halves prelock-bust 31.8%→16.8% with zero momentum-proxy dependence** — at the cost of ~2.4× slower lock (med 93d vs 39d). This is a survival-vs-speed tradeoff, not strict Pareto dominance. Worth testing before deploying.
- **PHASE 2 (harvest, floor locked): KEEP.** A6/B3/mm6 post-lock is where the payout is harvested; do not move the harvest into Phase 1.
- **EXIT MODEL (cross-cutting): TEST.** The incumbent EXIT3 (50/50 @1R/2R) is dominated on this 5y path by **single@1R** (eval pass 60.6% vs 57.5%, maxDD −28%) for the eval drawdown-survival game, and by **single@1.5R** (totR +25%, highest expR) for the funded income game. The 2R core is the weak leg (single@2R is worst non-trail, PF 1.25). Validate IS/OOS + joint-bar before touching the config-locked EXIT3.

**Bottom line:** The bot is a faithful, causally-clean implementation of validated edges. EVAL sizing is genuinely optimal. The actionable items are (a) re-running the eval harness with B's real partial to recalibrate economics, (b) reconsidering momentum's live arming on funded, (c) testing the A3/B1 grind and the single@1R/1.5R exits before any config change.

---

## 2. FIDELITY FINDINGS (bot vs backtest) — ranked by severity

### F1 [HIGH→true MEDIUM, CONFIRMED] Profile B live exit (PARTIAL_1R) ≠ backtest b_events (single 1.5R)
- **Gap:** Live B (B5) routes `BP.build_entry_exit3` — 50% @ +1R, 50% @ +1.5R ATR on a shared stop (`config_defaults.py:44` `B_EXIT_MODEL='PARTIAL_1R'`; `resolve_b_exit` `:73-83` gated on `b-exit-partial-approved.flag` which **is present**; `auto_live.py:307-321`; `profile_b_tracker.py:94-170`). The eval harness `apex_eval_deployed.b_events()` (`:116-134`) resolves a **single** stop-first/1.5R-target bracket with **no** +1R partial. `apex_eval_eod_databento.py:44` calls `H.b_events(df5)`, so the 57.5%/68% figures use the non-deployed B exit.
- **Direction:** Conservative — the validated partial cuts B drawdown and raises PF, so the stored pass-rate **understates** the deployed config. No capital-risk exposure created. B is only 5 of 21 MNQ, bounding magnitude.
- **Fix:** Add a PARTIAL_1R branch to `b_events()` mirroring `profile_b_tracker._record_partial`; re-run `apex_eval_eod_databento.py`. Expect printed pass-rate ≥ 57.5%. Recalibrates spray/EV economics.

### F2 [MEDIUM, unverified] Half-overlap gate unmodeled in backtest; live applies it to Momentum only
- Live wires `OverlapGate(factor=0.5, participants={A,B,M})` (`auto_live.py:558`) but only momentum reads it (`profile_momentum_live.py:108-109`); A/B only feed it (`auto_live.py:249,334`), never downsized. Backtest holds M=6 fixed (`apex_eval_deployed.py:32,140-163`). Live also fires A/B `on_close` only at ET rollover (`auto_live.py:421-424`), so the gate treats A/B as open all day and **over-halves** momentum vs reality.
- **Fix:** Model the gate in `m_events` (halve M 6→3 on same-direction A/B-open days) OR document the backtest as a pessimistic upper bound; separately fix live A/B `on_close` to fire at trade resolution.

### F3 [MEDIUM, unverified] Live momentum 120pt cat-stop absent in backtest m_events
- Live builds momentum entry with `stop_pts=120` broker cat-stop (`profile_momentum_live.py:112-114`); `m_events` marks pure close-to-close with no stop and feeds the **uncapped** intraday trough as `mae` to the trailing-DD test (`apex_eval_deployed.py:140-163,192`). Backtest can register momentum losses/drawdowns larger than the live cap.
- **Fix:** Cap each day's momentum loss and trough at ~ −120pt × M_SIZE × DPP (+ slippage) in `m_events`.

### F4 [LOW, unverified] Momentum cost convention differs (per-flip 1.0pt vs per-round-turn 0.75pt)
- `apex_eval_deployed.py:35,157-159` charges `flips × 1.0 × M_SIZE`; live charges 0.75pt round-turn per episode (`profile_momentum_live.py:23,42-44`). Backtest **overstates** momentum cost.
- **Fix:** Standardise on 0.75pt round-turn per realised episode in `m_events`.

### F5 [LOW, unverified] Profile B max-hold off-by-one
- Backtest closes at `C[fill+23]` (`apex_eval_deployed.py:118,129`); live times out at `fill+24` (`profile_b_tracker.py:104,112`, mh=24). Negligible P&L; align tracker to `filled+23`.

### F6 [INFO, confirmed] Entry/signal layer is faithful
- ORB window/levels/ATR(14)/break/stop/target/6-bar retest all match (`strategy_engine_profileB.py:12-83` vs `apex_eval_deployed.py:77-136`); momentum signal math is the same `compute()` (`profile_momentum_engine.py:58-87`); sizes A10/B5/M6 match the deployed tier (`auto_safety.py:36`). **No change to entry/signal layer.**

### Cross-source agreement [INFO] Both data sources rank deployed config #1
- Dukascopy proxy (`apex_eval_eod.py:124`) puts A10/B5/mm6 top of the EOD-real column (59.5%), same monotone shape; Databento 57.5% is canonical (proxy ~2pp optimistic). No data-source ambiguity.

---

## 3. INTEGRITY FINDINGS (look-ahead / overfit / regime / realism)

### I1 [HIGH, CONFIRMED] Momentum is extreme-right-tail dependent — top ~20% of trades = ~97% of profit
- Reproduced via `nq_momentum_forensics.py`: <30min bucket n=1047 (64.5%), WR 11%, PF 0.05, −22,707pts; >2h bucket n=256, WR 90%, PF **51.57**, +30,429pts; top 20% = 97% of gross win. Strip the runner tail and momentum is a losing strategy. Structural, not a parameter artifact — confirm 3→4 trims whipsaws but does not broaden the profit distribution. Per-year concentrates (2024 2.43 vs 2026 1.35; 2026 pre-upgrade 1.02 — one-sided short squeeze). `profile_momentum_live.py:28` stop-only/no-target → structurally a runner-capture engine.
- **Live-risk correction (raises urgency):** Momentum is **NOT gated off on Apex funded** as the recommendation assumed — `auto_safety.py:91-95` returns active=True for funded; `momentum-approved.flag` exists. The tail-fragile lane is live on the $2k EOD trailing-DD funded account, mitigated only by $550 daily stop + P3 brake.
- **Recommendation:** Run a Monte-Carlo / trade-shuffle to size the tail risk **before** relying on momentum's funded contribution; treat its PF as tail-fragile, not steady. Reconsider arming it on funded.

### I2 [HIGH, CONFIRMED] A4/B2/mm2 funded survival edge rests on the least-trustworthy stream (momentum proxy)
- `apex_p1_grind_sweep.py`: A4/B2/mm0 68.8%/$17,020 → A4/B2/mm2 79.8%/$19,419 (+11pt, +$2,399) → A4/B2/mm6 67.0%/$15,656. The only changed variable is the momentum stream. That stream is daily-aggregate (`apex_eval_deployed.m_events` emits ONE event/day vs per-trade A/B), self-labelled the weakest component. Two refutations *strengthen* the flag: (a) `auto_safety.py:82` explicitly says momentum should be **OFF** on funded because "the $1k daily-kill makes one bad momentum day fatal" — a direct contradiction with the deployed mm2; (b) the daily-aggregate proxy delivers a whole day's loss as a single end-of-day event, evaluated *after* the daily-stop gate, so it **cannot** model the intraday $1k kill it warns about — understating real bust risk.
- **Recommendation:** Discount A4/B2/mm2's headline. If momentum is doubted, deployed reverts to ~68% lock — worse than A3/B1's ~83% on the trustworthy A+B streams. Validate the funded momentum proxy on per-trade data before relying on the +11pt.

### I3 [MEDIUM, disclosed] Daily-$550 stop & rolling eval mark full-trade PnL at FILL time
- `apex_eval_deployed.py:167-197` orders events by fill ts and applies each trade's *entire* realized pnl (known only at exit) at the fill slot. On A+B+M overlap days the halt/equity gate at time T can depend on a trade that fills before T but resolves after — future info in the GATE (not in whether a signal fires). Harness discloses this as "slightly OPTIMISTIC." Bounded to cross-profile overlap days; expect a small downward correction to 57.5%, not a regime change.
- **Recommendation:** Quantify by re-marking with EXIT timestamps; keep the disclosure prominent.

### I4 [MEDIUM, unverified] Profile A edge concentrated in 10:00-10:30 ET; live trades a dead 11:00-11:30 sub-window
- `profile_a_overlay_research.md:104-107`: 09:30-10:00 PF 1.69/53.2R; 10:00-10:30 PF 2.09/85.5R; **11:00-11:30 PF 1.18/+4.6R (negative in several years)**. Period-concentration fragility — capital risk deployed in a no-edge window.
- **Recommendation:** Paper-test trimming new A entries after ~11:00 ET (overlay: expR 0.285→0.312, DD −6.6R, 85% of trades kept). Do not over-trim to only 10:00-10:30 (that would itself overfit).

### I5 [MEDIUM, unverified] Profile B raw 1.5×ATR target is on a degrading slope; robustness depends entirely on the partial overlay
- `profile_b_overlay_research.md:132-141`: PF degrades monotonically as target widens (1.25 PF 1.34 → 1.5-BASE 1.20 → 2.0 1.04); 1.5×ATR base is **negative in 2021** (−1.1R), barely positive 2022 (+1.0R). The deployed PARTIAL_1R restores robustness (PF 1.40, maxDD −9.3R, all 6 years positive). B's all-years-positive claim rests on the overlay, not the raw signal.
- **Recommendation:** Ensure PARTIAL_1R is armed live (needs `b-exit-partial-approved.flag`, else falls back to the fragile SINGLE bracket). Treat any fallback to SINGLE as a robustness regression. **Note this directly connects to fidelity finding F1** — the live partial is exactly what the eval harness fails to model.

### I6 [LOW, unverified] Latest momentum upgrade rescued the weakest year
- The 2026-06-27 upgrade (confirm 3→4, last-entry 15:00→15:30) is plateau-robust (confirm 3/4/5 all fine; cutoff slots 66-76 OOS 1.67-1.76) — good discipline. But the same change lifted 2026 from PF 1.02→1.35; improving the weakest year is the overfitting signature even when claimed as a side-effect.
- **Recommendation:** Accept (plateau evidence genuine) but **freeze now** (two refinement loops = stated limit). Forward-track 2026+ momentum PF in shadow before arming; if 2026 reverts toward 1.0 the lever was partly fitted.

### Integrity — clean (INFO, audited)
- **No look-ahead** in any signal generator: model01 detects sweep-reclaim on close, scans MSS/fill on later bars (`model01_sweep_mss_fvg.py:179-243,417-431`); B fills a resting limit at a later retest bar; momentum applies the i-1 decision to the i-1→i return.
- **Swing pivots** confirmed with correct right-bar lag (`primitives.py:36-55`); HTF gets an additional +period shift — no fractal leak.
- **Daily/weekly/session levels** forward-stamped (+1day/+7day, merge_asof backward); session levels use cummax/cummin so a developing level is mathematically un-sweepable (`htf.py:37-80`).
- **Momentum features** prior-day-only (rolling.mean().shift(1), 50d trend shift(1)) (`profile_momentum_engine.py:62-86`).
- **Native 5m data** — no 1m→5m label/closed misalignment (`paper_live.py:154`, `data.py:64-83`).
- **EOD ratchet correct** — ratchets only on end-of-day balance, no intrabar (`apex_eval_eod.py:38-44`).
- **ApexAcct path model** (adverse-before-favourable, `funded_rules.py:65-75`) is disclosed; conservative on give-back, mildly optimistic if a trade ran favourable first. Acceptable; optional mfe-first "pessimistic" mode would bracket the true bust rate.
- **Low degrees of freedom** — params are round/canonical ICT values, not optimizer outputs (OTE 0.705 frozen, mean fill 0.697 std 0.006 — nothing to tune; W_MSS/W_FILL/MAX_HOLD = 1h/1h/4h; B OR=15min, ATR(14), 1.0/1.5×; momentum nd14/k1/trend50/confirm4). Limits overfitting surface.
- **Exit#3 chosen for drawdown-safety, not return** — full-1.5R scores higher (203.3R) but breaches the $2k buffer; Exit#3 keeps DD 24-41% lower. Anti-overfit constraint, correctly applied. Document so it is never "optimized away."
- **B target NOT re-fitted** to the higher-scoring 1.25×ATR (PF 1.34) — disciplined freeze; only the +1R partial bolted on.
- **Portfolio per-year eval pass stable**: 2021:53.2 / 2022:48.3 / 2023:60.2 / 2024:55.8 / 2025:63.2 / 2026:68.0 (ALL 57.5%). No single-year dependence; worst year still a coin-flip-plus. The old 81%/86% claim is **mathematically dead** (best year is 68.0%). Dashboard must cite ~57.5% (full) / ~68% (last 12mo), never 81/86%.

---

## 4. OPTIMALITY

### EVAL — **KEEP A10/B5/mm6**
| | Pass | Bust | Exp | Cost-to-fund |
|---|---|---|---|---|
| **A10/B5/mm6 (DEPLOYED)** | **57.5%** | 39.6% | 2.9% | **$60.9 (min)** |
| 8/4/5 | 56.2% | — | 8.2% | $62.3 |
| 12/6/7 | 52.0% | — | — | $67.3 |
| 14/7/8 | 49.3% | 50.7% | — | $71.0 |
| 6/3/4 | 52.7% | — | 21.6% | — |
- Deployed config is the pass-rate **and** cost-to-fund optimum within the validated grid (`apex_eval_eod_databento.py:64-68`). EV is monotone in pass-rate (eval cost & funded value are size-invariant), so pass-rate peak = EV peak. Near-zero 2.9% expire correctly beats the 30-day clock; downsizing reintroduces severe clock-drag (6/3/4=21.6% exp, 4/2/2=63.2%). Contract cap (10 minis = 100 MNQ) never binds (deployed = 21 MNQ = 2.1 minis). Both data sources rank it #1. **Recommendation: no resize.**

### PHASE 1 (grind to lock) — **CHANGE-AND-TEST → A3/B1/mm0**
| Config | Lock | Med days-to-lock | E[payout] | Prelock-bust | Momentum dependence |
|---|---|---|---|---|---|
| **A4/B2/mm2 (DEPLOYED)** | 79.8% | **39d** | **$19,419** | 31.8% | YES (+11pt from proxy) |
| **A3/B1/mm0 (candidate)** | **83.5%** | 93d | $19,268 (−0.8%) | **16.8%** | NO |
| A2/B1/mm0 (max-survival) | 87.8% | 147d | $18,925 (−2.5%) | ~12% | NO |
| A6/B3/mm0 (too big) | 68.0% | 33d | $16,267 | 32.4% | — |
- Reproduced exactly across two engines (`apex_funded_combined_test.py`, `apex_optimize_eod.py`). **A3/B1/mm0 is the efficient survival pick**: +3.7pt lock, halves prelock-bust, removes momentum-proxy dependence, at ~equal payout. **NOT strict Pareto dominance** — it is ~2.4× slower to lock (93d vs 39d) and −0.8% payout; honest framing is survival/robustness-vs-speed at ~breakeven total payout. A2/B1/mm0 if you want ~88% survival for −2.5% payout. A1/B1 adds only ~1pt survival but blows days-to-lock to 260d — don't go below A2/B1. **Do not grind larger than deployed** — A5/B3, A6/B3 are strictly worse on both objectives; the harvest belongs in Phase 2.
- **Recommendation:** TEST A3/B1/mm0 via `apex_funded_eod_databento.py` and adopt for Phase 1 if the priority is reaching lock / surviving to Phase 2 (the stated objective). Keep A4/B2/mm2 only if the objective is purely E[payout] and you trust the momentum proxy.

### PHASE 2 (harvest, floor locked) — **KEEP A6/B3/mm6**
- The floor is locked, so trailing-DD risk is gone and the harvest happens here. Phase 2 should size up; Phase 1 should not. Payout parity for the A3/B1 grind itself depends on mm6 post-lock (A3/B1 with mm0 throughout drops to $15,305, −21%) — i.e. momentum dependence is removed only from the *pre-lock* grind, not the payout phase. **Recommendation: no change.**

### EXIT MODEL (cross-cutting) — **TEST single@1R (eval) and single@1.5R (funded)**
| Variant | Eval pass | A-leg expR | PF | maxDD | totR |
|---|---|---|---|---|---|
| **Incumbent 50/50 @1R/2R** | 57.5% | 0.185 | 1.47 | 12.9R | 130.5 |
| **single@1R** | **60.6%** | 0.199 | **1.50** | **9.3R** | 149.1 |
| **single@1.5R** | 59.5% | **0.224** | 1.46 | 12.4R | **163.0 (+25%)** |
| single@2R (weak leg) | 54.8% | — | 1.25 | — | — |
| floor@2R + ATR2x trail | 58.1% | 0.205 | **1.54** | — | — |
| ATR2x trail | 47.3% | — | 1.11 | 36.2R | — |
| BE@1R + 50/50 | 57.6% | 0.160↓ | 1.41 | — | — |
- Reproduced exactly via `exit_optimality.py` (re-runs the real `model01._simulate`, not MFE/MAE estimation — correct method for path-dependent exits; incumbent reproduces the 57.5/39.6/2.9/7 baseline to the decimal). The 2R core is the weak leg; banking at 1R or pulling to 1.5R is strictly better. **single@1R Pareto-dominates** the incumbent (every metric); single@1.5R wins on pass/expR/totR but PF marginally lower (1.46 vs 1.47) — not strict domination.
- **What actually backfires:** TRAILING, not partials. ATR2x/3x and swing-trail destroy the edge via whipsaw on a 5m OTE entry (PF 1.03-1.22, maxDD up to 50.4R). The "early-exits backfire" memory note is **refuted** for Profile A — it is trailing that backfires; scope that note to its original Profile-B context. The only defensible trail is floor@2R-then-trail (PF 1.54) but it underperforms single@1R/1.5R on pass-rate for added complexity. **Breakeven is neutral-to-harmful** (BE@1R full position: expR collapses 0.185→0.106, maxDD blows to 24.0R) — the "no breakeven" design choice is confirmed correct. Wider targets (2.5R/3R) and ride-more 33/67 splits all underperform.
- **Caveats:** single-realization full-history numbers; no IS/OOS or year-by-year shown; a +3.1pp eval-pass edge over one 5y path is real but modest. The per-trade give-back model is mildly optimistic on the intraday-liquidation leg.
- **Recommendation:** Treat the exit as phase-specific — **single@1R for the EVAL sprint** (drawdown-survival: +3.1pp pass, −28% A-leg DD, strengthens the EXITLOCK buffer rationale), **single@1.5R for FUNDED income** (totR +25%, highest expectancy). Validate at A10/B5 sizes, IS/OOS, with B's real PARTIAL_1R exit (F1) and the joint-bar harness (`apex_joint_bar_sim.py`) **before** touching the config-locked EXIT3. Do not deploy blind.

---

## 5. RANKED ACTION LIST (highest impact first)

1. **[FIX] Re-run `apex_eval_eod_databento.py` with a PARTIAL_1R branch in `b_events()`** (F1) — the deployed eval pass-rate is currently understated; recalibrate spray/EV economics on the true B exit. Low effort, directly corrects the headline number used for capital decisions.
2. **[FIX] Reconcile momentum's live arming on Apex FUNDED** (I1+I2) — `auto_safety.py:91-95` arms mm on funded while `auto_safety.py:82` says it must be OFF ("one bad momentum day fatal"). Resolve the internal contradiction; the tail-fragile lane is live on the $2k EOD account with only $550-stop + P3 as backstop. Run the Monte-Carlo / trade-shuffle tail-risk sizing that has not yet gated the arming.
3. **[TEST] A3/B1/mm0 for Phase 1** via `apex_funded_eod_databento.py` (Optimality §4) — +3.7pt lock, halves prelock-bust, removes proxy dependence at ~equal payout; the survival-optimal pick for the stated "reach lock" objective. Decide explicitly on the speed cost (93d vs 39d).
4. **[TEST] single@1R (eval) / single@1.5R (funded) exit** via `exit_optimality.py` + IS/OOS + `apex_joint_bar_sim.py` (Optimality §4) — incumbent EXIT3 is dominated on this 5y path; validate robustness before touching the config-locked model.
5. **[FIX] Validate the funded momentum proxy on per-trade data** (I2) — the +11pt funded survival the deployment leans on comes from a daily-aggregate stream that cannot model the intraday $1k kill; the proxy likely *understates* momentum bust risk on a shared funded account.
6. **[FIX] Model momentum's 120pt cat-stop and overlap gate in `m_events`** (F2, F3) — makes bust/drawdown attribution faithful; currently the backtest is a pessimistic bound that lets momentum register losses larger than the live cap and over/under-sizes on overlap days.
7. **[FIX] Quantify the fill-time gating bias** (I3) — re-mark eval with exit timestamps; expect a small downward correction to 57.5% (not a regime change). Keep the disclosure on the dashboard.
8. **[TEST] Paper-test trimming Profile A entries after ~11:00 ET** (I4) — the 11:00-11:30 sub-window is a no-edge slice of deployed capital risk; overlay shows expR 0.285→0.312, DD −6.6R, 85% of trades kept. Do not over-trim.
9. **[FIX] Dashboard hygiene** — cite ~57.5% (full) / ~68% (last 12mo) eval pass; the 81%/86% figures are dead. Standardise the momentum cost convention (F4) and align B max-hold off-by-one (F5) — both negligible-P&L but worth aligning.
10. **[FIX] Freeze the momentum upgrade and shadow-track 2026+** (I6) — accept the plateau-robust confirm 3→4 / 15:30 change but stop iterating; if 2026 PF reverts toward 1.0 the lever was partly fitted.

---

### Honesty notes on uncertainty
- The optimality numbers are **single-realization full-history** Databento runs — no Monte-Carlo / IS-OOS split on the exit and Phase-1 candidates yet. Treat the +3.1pp / +3.7pt deltas as real but modest and confirm before deploying.
- The CONFIRMED findings were independently re-run; the LOWER-SEVERITY findings (F2-F5, I3-I6) are **unverified** and carry that caveat.
- Where the bot is faithful and near-optimal, this report says so plainly: **EVAL sizing is genuinely optimal; the entry/signal layer is clean and causal; param degrees-of-freedom are low.** The real work is the B-partial harness fix, the momentum-on-funded decision, and validating the two config candidates.
