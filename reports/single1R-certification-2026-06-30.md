> ⛔ **OBSOLETE (pre-2026-07-02 machine).** This document describes a configuration/certification
> that was INVALIDATED by the 2026-07-02 audit (5m fill-bar look-ahead) and superseded by
> **ZEUS Production Machine v2026.07.02** — see `AGENTS.md` §"THE SELECTED MACHINE" and
> `reports/apex_validation.json`. Kept for historical reference only.

# single@1R — Pre-Deployment Certification Memo

**Date:** 2026-06-30
**Subject:** Certifying the `single@1R` exit model (replace live `EXIT3_FIXED_PARTIAL` with full-qty single +1R target / same −1R stop) for the ZEUS NQ bot, treated as if deploying tonight.
**Operator ask:** "test single@1R as if it goes live tonight — make sure no look-ahead, no nothing."

---

## TOP-LINE VERDICT: **NOT-CERTIFIED**

The **model is causally clean** and the **edge is robust** (OOS + MC + per-year + cost) — those parts PASS and are reproduced below. But certification fails on **execution-path safety/representability**: `single@1R` **does not exist as a routable config**, there is **no code that builds a full-qty +1R bracket**, and a naive enablement **silently misfires the full position to the +2R target** — the exact `SINGLE_TARGET` failure mode EXITLOCK was built to stop. Per the gate rule, an execution-safety blocker forces NOT-CERTIFIED regardless of the payout numbers.

The good news: there is no look-ahead and no edge failure, so once the +1R routing/config is authored and re-audited, the path to **CERTIFIED-FOR-PAPER-TEST** is short. Live-tonight is not on the table.

---

## 1. LOOK-AHEAD / CAUSALITY VERDICT — **CLEAN (PASS)**

The win/loss assignment for `single@1R` is provably causal on **both** legs and does **not** use the optimistic `mfe_r >= X` shortcut.

- **A-leg.** `a_variant()` (`exit_model_validate.py:54-66`) re-runs the frozen engine `M1.run(feats,"NQ",A_PARAMS["single1"])` with `partial=None, rr=1.0, target_mode="fixed_rr"` (`exit_model_validate.py:46-51`) and reads the engine's own `r_result` (line 64). It stores `mae_r` but **never** uses `mfe_r` to assign the outcome. Inside the engine, `_simulate()` (`models/model01_sweep_mss_fvg.py:445-510`) checks the **stop FIRST** (line 466) and the **target LAST** (line ~499), inside a strictly **forward-only** loop `for x in range(fill, last)`. Same-bar stop+target collisions therefore resolve to the **loss** (conservative). Verified: 0 of the +1R wins had `mae_r <= -1.0`.
- **B-leg.** `b_sim()/walk()` (`exit_model_validate.py:70-154`) is a bar walk that checks **stop before partial before target** (lines 91-104), with an RTH-close timeout in between; resolves cleanly to `{+1R, −1R}` plus rare timeouts. Forward-only from `fill` (`range(fill, min(fill+24,n))`).
- **Entry fills** are strictly **after** the signal bar (A: `mss_bar+1..`; B: `gi+1..`, `exit_model_validate.py:137`), so no future bar enters a same-bar decision. Indicators are backward-looking (ATR `rolling(14).mean()`).

**Documentation defect (CONCERN/low, does not affect numbers).** The module docstring (`exit_model_validate.py:3,6-8`) *describes* the optimistic shortcut ("a trade reaches +XR iff its max-favorable-excursion `mfe_r` >= X") that the code **does not use**. The code is correct; the comment is stale and could mislead a future reviewer into "simplifying" toward the shortcut and regressing the safety property. **Action: fix the docstring** to state "A re-derives via engine re-run with `partial=None`, fixed-RR target".

---

## 2. RE-DERIVATION / BRACKET FIDELITY — **PASS**

The deployed-size sanity tie-out reproduces the locked baseline exactly:
`[sanity] A-incumbent + B-single1.5R (=deployed) pass% = 57.5` — matches the validated 57.5% Apex EOD baseline. Trade counts: A incumbent 705 / single1 748 / single15 727; B 1024; mm-days 515; bars 2021-06-22→2026-06-22 (353,952 1m→5m). The single@1R order is structurally one OSO bracket (`build_entry` returns one payload with `stopLoss`+`takeProfit`, `bridge_traderspost.py:105-106`), so no half-built/stale-leg state is possible — **but that builder does not target +1R** (see §6).

---

## 3. EVAL ROBUSTNESS — **PASS (edge), with per-year & momentum caveats**

Reproduced from `exit_model_validate.py` (real Databento, A10/B5/mm6, EOD rule):

| variant | FULL | IS 21-24 | OOS 25-26 | totR | A_maxDD(R) | MC med | MC p5 | MC p95 |
|---|---|---|---|---|---|---|---|---|
| INCUMBENT 50/50 | 59.3 | 57.0 | 64.9 | 321 | −12.9 | 59.6 | 51.7 | 66.8 |
| **single@1R** | **63.1** | 59.7 | **71.4** | **383** | **−9.3** | 64.6 | **57.8** | 71.2 |

single@1R **beats** incumbent on FULL (+3.8pp), OOS (+6.5pp), MC p5 (+6.1pp), totR (+62R), and A maxDD (−9.3 vs −12.9R). All exactly as claimed.

**Per-year (`exit_model_adversarial.py`):** single@1R wins 2022 (+7.3), 2023 (+1.2), 2024 (+2.5), 2025 (+7.0), 2026 (+5.2) but **LOSES 2021 by −2.4pp (51.6 vs 49.2, n=124)** — the single losing year, smallest sample. Worst 80-start rolling window single 27.5% **beats** incumbent 25.0%.

**Cost robustness:** edge **widens** under harsher costs — Δfull +3.8 → +4.3 (+1tk) → +5.2 (+2tk +$4cm); OOS stays +4.7 to +7.1pp. Not a frictionless artifact.

**Momentum caveat (CONCERN/medium).** The mm-OFF **survival** lead (+14.2pp reach-lock) collapses to **parity** mm-ON (79.2% vs 79.8%, −0.6pp) and reverses in 2 of 4 full years (2022, 2024) and IS. It still holds OOS (+5.6pp) and MC p5 (+4.8pp). **Certify single@1R on the payout edge, not a survival edge, once momentum is live.** The **payout** edge survives momentum: E[pay/acct] $23.7k vs $19.4k (+22%) mm-ON.

---

## 4. FUNDED ROBUSTNESS (with momentum) — **PASS (payout), CONCERN (cum. DD & daily-kill)**

- **Payout edge holds mm-ON:** point +22.1%, IS +25%, OOS +11%, MC p5 +41%; single1 wins every payout year. mm-OFF the lead is +40% (E[pay] $17.2k vs $12.3k).
- **$1k daily-kill (CONCERN/medium, exit-agnostic).** Momentum roughly **doubles** kill-risk-day frequency for **both** exit models (realized ≤−$1000 days: incumbent 28→65, single1 27→61). single1 is marginally **safer** on every census metric (61 vs 65 realized; 97 vs 124 intraday-trough). The "+kill ~88% hardkill" figure is an **over-harsh upper bound** (momentum modeled as one un-interruptible daily-aggregate event, `apex_eval_deployed.py:146-169`), not a literal prediction. **Caveat:** at mm6 a single 120pt momentum stop = $1,440 > $1,000, so a stopped momentum position alone can breach the soft $1k DLL — **funded momentum sizing must be re-examined separately**, independent of the exit-model choice.
- **Cumulative funded maxDD (CONCERN/low).** The one direction single is worse: P1 A4/B2 −$4,035 vs −$3,707 (+$328); P2 A6/B3 −$5,921 vs −$5,429 (+$492). This is a 5y cumulative grind (the +1R cap removes +2R recovery winners), ~9% of base, within n-difference — **not** a single-session bust. single had **fewer** floor touches (0 vs 2 at P2).

---

## 5. TAIL RISK — **PASS (single-session), CONCERN (structural daily-stop)**

- **Single-session bust (the gate's core question): single@1R is never worse.** Worst single day single −$3,894 vs inc −$4,348; worst intraday excursion single −$4,130 vs inc −$4,434; funded P2 ZERO sessions ≤−$2,500 floor vs inc 2. Eval cumulative maxDD single −$7,753 vs inc −$9,506.
- **Rolling windows:** only the tightest 5-day window favors incumbent (−$166, sub-$200); 10/20-day and overall maxDD favor single.
- **Daily-stop structural (CONCERN/medium, both variants).** The −$550 daily stop is checked **before each new event and only drops subsequent entries** (`apex_eval_deployed.py:174-187`); it does **not** truncate an in-flight loss. At 10 MNQ a single A-leg loss is ~$2–4k, so worst days blow through to ~−$3.9–4.8k under **both** models (single gentler). Apex has **no native daily loss limit** (`funded_rules.py:11`); the $1k DLL is a soft internal control. **Pre-existing property, not a single@1R regression** — flag for operator awareness.

---

## 6. EXECUTION-PATH READINESS — **FAIL (BLOCKERS)**

This is the reason for NOT-CERTIFIED. Three reproduced blockers:

1. **`single@1R` is not a routable config.** `'SINGLE_1R' in EXIT_MODEL_ALLOWED` → **False** (`config_defaults.py:15-17`, allowlist = `{EXIT3_FIXED_PARTIAL}`). B tokens = `{PARTIAL_1R, SINGLE}` only. The nearest existing token `SINGLE_TARGET` is full-qty to **2R**, research-only and live-blocked. `resolve_exit_model('live'/'paper'/'controlled')` with `EXIT_MODEL='SINGLE_1R'` → **ConfigLockError "unknown EXIT_MODEL"** (reproduced); with `'SINGLE_TARGET'` → **ConfigLockError "research-only"**. The stack fails **closed** — good — but it means **deploying tonight is impossible as-specified.**

2. **No +1R full-qty build path.** The only single-leg builder is `build_entry`, and the A `else` branch (`auto_live.py:233-240`) passes `common['target'] = sig['target']` = the strategy **2R** price (`strategy_engine_profileA.py:21`, `rr=2.0`). The +1R price is computed **only** inside `build_entry_exit3` (`bridge_traderspost.py:151`, `tp1_target = entry + d*R`) as the TP1 partial leg. **No caller passes `target=entry±1R` at full qty.** A grep for `+ d * R` returns only that one line.

3. **Misfire trap (CONCERN/high).** Reproduced directly: a +1R-intended A long (entry 20000, stop 19900, strategy target 20200) routed through the `else` branch returns `takeProfit.limitPrice = 20200` → **R-of-target = 2.0 at full qty** (intended +1R = 20100), and `r_target` absent from meta. So a config-only enablement (add token to allowlist + set `EXIT_MODEL`, **without** authoring the +1R branch) would **silently send the full position to +2R** — the `SINGLE_TARGET@2R` model that breaches the $2k eval buffer and that EXITLOCK exists to prevent. The bridge exit-model flag backstop is currently **off/satisfied** (`evidence/approvals/exit-model-approved.flag` present), so the **only** remaining guard is CONFIGLOCK's EXIT3 default.

**Exactly what must be built & approved before paper-test:**
- Define a new `SINGLE_1R` token; add to `EXIT_MODEL_ALLOWED` **and** author its build path (a full-qty `build_entry` call with `target = entry ± 1·R`, `r_target=1.0`).
- Add an explicit A routing branch in `auto_live.py` that computes the +1R target — do **not** fall through the `else` to `sig['target']` (2R).
- Mirror for B if B is to move to single@1R (B `else` currently routes 1.5R, `auto_live.py:324-329`).
- Populate ledger/decision-log TP fields + `r_target=1.0` for the single fill (CONCERN/low: `auto_live.py:267-277` A and `:354-363` B leave tp fields None/blank under a single order; dashboard TP1/TP2 attribution would be empty).
- Re-run the EXITLOCK/CONFIGLOCK test batteries and a dry-run OSO proof on the new branch.
- Keep the bridge exit-model flag backstop **armed** during rollout.

---

## 7. REGIME DURABILITY — **ADEQUATE**

Edge present in 5 of 6 calendar years (2022-2026), strengthens under cost, OOS (2025-26) is the **strongest** window (+6.5pp), worst rolling window beats incumbent, MC p5 beats. The single soft spot is **2021** (−2.4pp, n=124, smallest sample) and the **momentum-ON survival parity**. No regime where single@1R is materially worse on a tail metric. Durable enough to paper-test; not a reason to block.

---

## RANKED BLOCKER / CONCERN LIST

| # | Severity | Item | Bearing |
|---|---|---|---|
| 1 | **BLOCKER** | `single@1R` not a routable config token (`config_defaults.py:15-17`) | Cannot deploy as-specified |
| 2 | **BLOCKER** | No code builds a full-qty +1R bracket; only +1R-as-TP1-partial exists | Cannot deploy as-specified |
| 3 | **CONCERN/high** | Naive enablement silently misfires full qty to +2R (the SINGLE_TARGET trap) | Must author +1R branch, keep backstop armed |
| 4 | CONCERN/medium | Momentum erases the survival lead to parity (still ahead OOS/MC p5) | Certify on payout edge, not survival |
| 5 | CONCERN/medium | Momentum ~2x daily-kill-day rate (exit-agnostic); mm6 120pt stop = $1,440 > $1k | Re-examine funded momentum sizing separately |
| 6 | CONCERN/medium | −$550 daily stop doesn't cap a day's loss (both variants); worst day ~−$4–4.8k | Operator awareness; not a single@1R regression |
| 7 | CONCERN/low | Funded cumulative maxDD ~9% deeper for single (+$328/+$492) | n-plausible grind; single better single-session |
| 8 | CONCERN/low | Ledger/dashboard TP attribution blank under single fill | Wire `r_target=1.0` + tp fields with the new branch |
| 9 | CONCERN/low | Validator docstring describes the optimistic shortcut the code doesn't use | Fix comment to prevent future regression |

---

## PRECISE NEXT STEP

**Do NOT enable single@1R tonight in any form.** Author the `SINGLE_1R` token + a dedicated +1R full-qty build/route path (§6), re-run EXITLOCK/CONFIGLOCK batteries + a dry-run OSO proof confirming `takeProfit = entry ± 1·R` at full qty, fix the validator docstring, then re-submit for certification. Only after that build passes does single@1R become eligible for **paper-test behind EXITLOCK** (never straight to live). The edge is real and clean; the gate fails purely on the missing, safe execution path.
