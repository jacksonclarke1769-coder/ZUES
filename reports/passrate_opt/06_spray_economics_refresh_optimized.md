# SPRAY-ECONOMICS REFRESH — end-to-end business run-rate under the OPTIMIZED funded stage (honest sim)

**Research / SIM measurement ONLY. READ-ONLY on bot strategy code (imports only). Writes confined to
`research/passrate_opt/` + `reports/passrate_opt/`. NOTHING ARMED. LIVE HOLD remains in force.**

- Harness: `research/passrate_opt/spray_economics_refresh_optimized.py`. JSON:
  `reports/passrate_opt/06_spray_economics_refresh_optimized.json` (determinism md5
  `f228866f0480185a870e2755635ee8b9`, **identical across two runs**).
- **Reuses certified machinery by import, re-models nothing:** the report-05 funded engine
  `funded_stage_opt.py` (`build_vpc`, `build_level_matrix`, `run_pa_diag`, `fixed_size`,
  `cushion_size` — which itself imports the certified VPC signal/fill `honest_eval_engines.py` +
  day-collapse `tools_account_size_research`). Payout RULES unchanged. The report-04 run-rate FORMULA
  is reproduced verbatim (`report04_runrate`). The only new code is the account-**cap renewal** model.
- **Optimized policy = report-05's recommended `cush_3band_XS_S_M`** (cushion-aware sizing:
  1 ct when cushion <$2.5k, 2 ct at $2.5k, 3 ct only when cushion >$5k; withdraw to the $52,100 floor).
- **Fidelity canary (bit-exact to report-05):** pre-opt `$400/cap2` → mean **$2,893** / med **$1,500** /
  bust **53.3%** / life **16.4mo**; opt `cush_3band` → mean **$2,842** / med **$2,362** / bust **0%** /
  closed_max **0%** / **data_end 100%** / life **31.5mo**. Engine faithful.

## ⚠️ CONFIDENCE BANNER (rides every number)

Every Apex rule is **help-center-derived, UNVERIFIED vs a live contract**. Eval front-end is **FROZEN**
(VPC 50K AGGRESSIVE $2000/cap10): honest pass **37.9% rolling / 41.9% Monday-cohort** (report-04
recomputed). Fee **$24.50 promo** / ~**$137 list** (UNVERIFIED); activation **~$130** one-time (UNVERIFIED).
**Apex concurrent-account CAP ~20 is UNVERIFIED** and is the single most decision-relevant unverified input
here. SIM only; funded fills at size unproven live.

### The censoring fact that governs everything below

**100% of optimized PAs end as `DATA_END`** — 0% bust, 0% ladder-cap-close within the observable window.
So "31.5mo life / $2,842 lifetime payout" are **observation-window figures, NOT true closing figures.**
The optimized account's *true* life and *true* lifetime payout are right-censored (longer / larger, unknown).
The task brief's "closes at the 6-payout ~$13k ladder cap at ~31.5mo" is therefore **not what the sim shows** —
no optimized account reaches the cap in-window. **What IS censoring-robust is the per-account monthly
earning RATE** (paid ÷ months observed — numerator and denominator truncate together): opt ≈ **$90/mo per
account** (ratio-of-means $90.2 ≈ mean-of-per-PA $90.9, agreeing because every opt account lives the full
window). The cap model below is built on this robust rate, so the steady-state $/mo rests on firmer ground
than the lifetime totals do.

---

## 1. LEG A — report-04's OWN (uncapped-flow) methodology, applied to the optimized stage

Report-04 run-rate = `evals/mo × [pass × (E[payout] − activation) − fee]` = book each created funded PA's
**whole-life** payout in its creation month. Reproduced verbatim for both stages (promo fee, Monday pass):

| Stage | E[payout] mean / median | **run-rate $/mo — mean** | **run-rate $/mo — median** |
|---|--:|--:|--:|
| pre-opt `$400/cap2` (report-04) | $2,893 / $1,500 | **$4,911** | **$2,381** |
| **opt `cush_3band`** | $2,842 / $2,362 | **$4,818** | **$3,946** |
| Δ | — | **−1.9% (FLAT)** | **+65.7% (UP)** |

*(Rolling pass: pre $4,432/$2,144 → opt $4,348/$3,560. List fee: pre $4,423 mean → opt $4,330. Full grid in
JSON `legA_report04_uncapped_flow`.)*

**On report-04's own yardstick, optimization HOLDS the mean and LIFTS the median +66%** — purely because it
eliminates the $0-payout accounts (33% → 0%), pulling the median up to near the mean. **But this leg is a
fiction under the Apex account cap** (Leg B), because it assumes you create ~1.65 funded PAs/month
*forever* and that each delivers its lifetime payout instantly.

## 2. LEG B — the honest reality: Apex account CAP renewal steady state

Report-04 omitted the cap. The optimized fleet's unconstrained equilibrium demand is **N\* = creation ×
life = 1.82/mo × 31.5mo ≈ 57 accounts** — nearly **3× a ~20 cap.** So the cap **hard-binds**: accounts
accumulate to 20, then new evals throttle to replace only closers. Renewal-reward steady state (long-run
fleet $/mo = `cap × E[payout]/E[life]`, replacement cost `= (cap/life) × cost-per-funded`), promo fee,
Monday pass, **cap = 20**:

| Stage | slot rate $/mo | **gross $/mo — mean** | (median-band) | replace $/mo | **NET $/mo — mean** | NET median-band |
|---|--:|--:|--:|--:|--:|--:|
| pre-opt `$400/cap2` | $176 | **$3,528** | $1,829 | $230 | **$3,298** | $1,599 |
| **opt `cush_3band`** | $90 | **$1,804** | $1,500 | $120 | **$1,685** | $1,380 |
| Δ | −49% | **−49%** | −18% | — | **−49%** | −14% |

Cap sensitivity (net mean, Monday, promo): **cap10** pre $1,649 / opt $842 · **cap20** pre $3,298 / opt
$1,685 · **cap30** pre $4,947 / opt $2,527. The optimized fleet is ~half the pre-opt fleet at *every* cap.
(Pass rate barely moves Leg B: at the cap, throughput is tiny so eval/activation cost is ~$120/mo either way.)

**Mechanism (the crux):** lifetime payout is ~equal (mean $2,893 pre vs $2,842 opt), but the optimized
account lives **2× longer** (31.5 vs 16.4mo). Through a **fixed number of cap-slots**, monthly cash =
throughput × lifetime-payout, and throughput = slots ÷ life. Doubling life at equal lifetime payout **halves
throughput → halves gross $/mo.** Optimization deliberately sizes down to survive; a hard account cap makes
*throughput*, not survival, the thing that monetizes — so on raw $/mo it costs ~half.

**Caveat on the pre-opt number:** $3,528 is a **fair-weather renewal average** — it assumes every busted
slot is instantly, costlessly refilled with a fresh same-distribution account. In a correlated bad regime
(2023: pre-opt E[paid] ≈ $55, report-04) the whole fleet busts *together* AND evals dry up, so pre-opt's
higher mean is **unrealizable exactly when it matters.** The optimized fleet (bust 0%, 2023 median still
+$2,136 per report-05) **survives that regime.** Its lower mean is far more bankable; the pre-opt mean's own
denominator (fleet-wide ruin) is missing from $3,528.

## 3. RAMP — months to steady state

Fill-to-cap `t* = −life × ln(1 − cap/N*)`, cap 20, Monday pass: **opt fills in ~13.6 months**, pre-opt in
~18.3 months (pre-opt busts empty slots during the ramp, slowing accumulation). Cash **lags account count**
by the first-payout warm-up (first sweep ≥30d + 5 qual-days ≈ 1–2mo), so **full steady-state cash ≈ 14–16
months** for the optimized fleet. Before then the fleet is still filling and earning below steady state.

## 4. FLEET / correlation

A **single** funded lane earns only the per-account rate **≈ $90/mo (opt)** — trivial standalone; the spray
is a business only as a **fleet of ~cap parallel lanes.** Correlation-1 (one edge): all lanes co-move.
- **Pre-opt:** lanes bust *together* — a correlated fleet-wipe that permanently empties slots and can't be
  refilled mid-regime. The $3,528/mo hides this ruin tail.
- **Opt:** bust ~0% → **no joint-wipe tail** (its single biggest advantage). Payouts still co-move on
  *timing* (a weak edge-year starves every lane at once), but the ruin axis is genuinely de-correlated:
  report-05 shows the optimized policy posts a **positive median in all four calendar years**
  ($1,119–$4,412), where pre-opt was wiped in 2023.

---

## VERDICT — did optimization RAISE $/mo, or buy STABILITY?

**It bought STABILITY. It did NOT raise sustainable $/mo.**

- On report-04's own uncapped yardstick: **mean run-rate FLAT** (−2%), **median UP +66%** — but that
  yardstick is unachievable under the Apex account cap.
- Under the honest cap-renewal model the optimized fleet delivers **~$1,685/mo net mean / ~$1,380 median-band
  at cap 20** (ranges: **$842–$2,527 net mean across cap 10–30**), which is **~half** the pre-opt fleet's
  fair-weather $3,298/mo — because 2× account life at equal lifetime payout **halves throughput** through a
  fixed slot count.
- What optimization unambiguously delivers: **bust 53% → 0%, life 16 → 31.5mo, $0-accounts 33% → 0%, a
  positive median every calendar year, and elimination of the correlated fleet-wipe tail** that makes the
  pre-opt mean a fair-weather illusion. It converts a churning, ruin-prone, $0-heavy fleet into a slow,
  survivable, every-year-positive annuity of long-lived accounts — at roughly half the fair-weather gross.

**Net:** the pre-opt "$4,911/mo" was never real (uncapped-churn illusion the ~20 cap forbids; and
correlated busts forbid the capped $3,528 too). Optimization trades ~half the fair-weather throughput for
**bankable, near-certain survival.** That is a robustness win, not an income raise.

## 5. CAVEATS (every number rides these)

1. **ALL Apex rules UNVERIFIED — help-center-derived, no live contract.** The **account cap itself (~20)**
   is unverified and is the hinge of Leg B; a different cap scales every Leg-B number linearly (§2 grid).
2. **Optimized life & lifetime payout are 100% right-CENSORED** (data_end 100%): "31.5mo / $2,842" are
   observation-window figures, not closing figures. The per-account rate (~$90/mo) is censoring-robust and
   is what the cap model uses — but the *lifetime totals* and the "closes at the ladder cap" framing are not
   observed.
3. **SIM, not live.** Funded fills AT the cushion-scaled size are unproven — the exact open risk. N≥30
   live-fill parity still gates everything.
4. **Historically ⅓ of pre-opt accounts paid $0**; the optimized policy removes that in-sample, but the edge
   is **regime-dependent** (recent 2025–26 VPC pass ~32–52% by half; a 2023-like edge-year starves all lanes
   at once even at bust 0%).
5. **Correlation-1.** Single-lane $/mo is trivial (~$90); the business is the fleet, and the fleet co-moves.
   Bust-correlation is neutralized by the optimized policy; payout-timing correlation is not.
6. **Determinism:** identical md5 `f228866f0480185a870e2755635ee8b9` across two runs.

## Single biggest honest caveat

**The whole Leg-B comparison hinges on two unverified inputs — the Apex ~20 account cap and the optimized
account's *true* (censored) life — neither read off a live contract nor observed to completion.** If the true
cap is much higher, the throughput ceiling relaxes and optimization's median-lift (Leg A) starts to dominate;
if the true optimized life is even longer than 31.5mo, throughput falls further and the stability-not-income
verdict strengthens. Verify the live 50K contract terms **and the account cap**, and run N≥30 live-fill
parity, before treating any dollar figure as decision-grade.
