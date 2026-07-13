# FUNDED (PA) STAGE OPTIMIZATION — Apex 50K, VPC edge FROZEN (honest sim)

**Research / SIM measurement ONLY. READ-ONLY on bot strategy code (imports only). Writes confined to
`research/passrate_opt/` + `reports/passrate_opt/`. NOTHING ARMED. LIVE HOLD remains in force.**

- Harness: `research/passrate_opt/funded_stage_opt.py`. JSON: `reports/passrate_opt/05_funded_stage_optimization.json`
  (determinism md5 `13a0985433c868e2ba0f48d6cc6d0deb`, **identical across two runs**).
- **Reuses certified machinery by import, re-models nothing:** VPC signal/fill/size-to-risk from
  `research/fork_b/honest_eval_engines.py` (F: `databento_5m_rth`, `v.features`, `vpc_trades_rich`,
  `vpc_events_risk`); day-collapse `day_rows` (ARES $550 stop + Apex $1k DLL) from
  `tools_account_size_research` (H). The **only** new code is `run_pa_diag` — a faithful, instrumented +
  parametrized copy of `apex_funded_40.py:74-113 run_pa`. Payout RULES unchanged; sizing/withdrawal POLICY
  parametrized; per-sweep block diagnostics added without touching the decision path.
- **Objective: MEDIAN payout per funded 50K PA** (⅓–½ currently pay $0, so mean is misleading). Mean reported too.
- Data: Databento NQ 1m→5m RTH, **401 trading days 2022-01-14 → 2026-06-19**, 45 rolling monthly PA
  starts with ≥9-month forward runway. All size levels share the identical date set (VPC always takes ≥1 ct).

## ⚠️ CONFIDENCE BANNER (rides every number)

**Every Apex 50K rule here is help-center-derived, NOT read off a live contract**
(`evidence/apex_terms/apex_terms.yaml`: confidence UNVERIFIED). Multi-source 2026 help-center pages
corroborate the ladder `[1.5/1.5/2/2.5/2.5/3]k = $13k` (6 rungs then PA CLOSES), `$250` qual-day, `5`
qual-days, `50%` consistency, `$2,500` trail, `$1,000` DLL, floor `$52,100` / min-req `$52,600`. The
`PAYOUT_EVERY_D = 30` withdrawal cadence is the **single most decision-relevant unverified rule** — see Lever 3.

## Fidelity canary (FIRST, before optimizing)

Baseline **$400 budget / cap2, cadence 30** reproduces report-04 **bit-exact**: mean **$2,893** /
median **$1,500** / $0-payout **33.3%** / bust **53.3%** / CLOSED_MAX **4.4%** / E[#payouts] 1.73 / life 16.4mo.
Engine faithful.

---

## STEP 1 — DIAGNOSIS: why funded PAs die (baseline $400/cap2)

Buckets partition **all** 45 PAs (mutually exclusive, priority-ordered for $0 lives):

| Bucket | % of PAs | median death (mo) | meaning |
|---|--:|--:|---|
| **(d) below MIN_REQ at every sweep** | **33.3%** | **4.6** | reached a 30d sweep but balance NEVER ≥ $52,600, then busted young — **the $0 bucket** |
| (partial) paid > 0, not capped | 62.2% | 16.9 | banked ≥1 rung then busted / ran out of data |
| (e) CLOSED_MAX (6 rungs ≈ $13k) | 4.4% | 48.5 | success |
| (a) bust before any sweep | 0.0% | — | — |
| **(b) blocked by 50% consistency** | **0.0%** | — | min+qual met, one big day ≥50% of profit |
| (c) short on 5×$250 qual days | 0.0% | — | — |

**Dominant failure = bucket (d): 33.3% of PAs bust YOUNG (~4.6 mo) having never lifted balance above
MIN_REQ.** The account is a wasting asset that dies before it can lock in the trailing-DD floor and bank.
**The task's two hypothesized culprits are REFUTED:** the 50%-consistency block is **0.0%** (max 6.7% across
*any* size in Lever 4) and qual-day shortfall is **0.0%**. The gain lives entirely in **surviving long
enough to bank** — i.e. in SIZING, not in consistency/qual handling.

---

## STEP 2 — LEVERS (marginal median gain of each)

### Lever 1 — STATIC sizing sweep (8 budgets × 6 caps, 48 cells)

The raw median-maximizer is **$400/cap6 → median $2,725 / mean $4,183**, but at **48.9% bust** and a $0
year (see anti-overfit). The decisive, robust finding is the opposite of "size up":

| Static policy | median | mean | bust% | $0% | CLOSED_MAX% | life mo |
|---|--:|--:|--:|--:|--:|--:|
| baseline $400/cap2 | $1,500 | $2,893 | 53.3 | 33.3 | 4.4 | 16.4 |
| $400/cap6 (raw med-max) | $2,725 | $4,183 | 48.9 | 44.4 | 13.3 | 18.6 |
| $300/cap3 | $2,686 | $3,302 | 26.7 | 13.3 | 0.0 | 22.7 |
| **cap1-flat (any budget)** | **$2,421** | $2,435 | **0.0** | **0.0** | 0.0 | **31.5** |

**Sizing DOWN is the highest-impact lever.** A flat 1-contract funded PA **never busts** and banks a
**$2,421 median (+61% vs $1,500)** with mean essentially unchanged ($2,435 vs $2,893). The baseline's
problem was never payout-when-it-works — it was the 53% bust rate killing PAs at ~4.6 mo. Cutting size
converts the wasting asset from "bust 53%, median $1,500" to "bust 0%, median $2,421, lives 31.5 mo."

### Lever 2 — DYNAMIC cushion-aware sizing (the "P3 cushion brake")

Size = f(cushion = balance − liquidation threshold): tiny when thin, larger when fat. Best deployable:

| Cushion policy (bands on cushion→level; XS=300/1 S=400/2 M=700/3 L=1100/4) | median | mean | bust% | $0% | life mo |
|---|--:|--:|--:|--:|--:|
| **cush_3band XS/S/M** (0/2.5k/5k) | **$2,362** | $2,842 | **0.0** | **0.0** | 31.5 |
| cush_brake XS/M (0/3k) | $2,265 | $2,322 | 0.0 | 0.0 | 31.5 |
| cush_4band XS/S/M/L (raw med-max) | $3,000 | $2,801 | 28.9 | 26.7 | 24.5 |

The 3-band brake **matches the baseline mean ($2,842 vs $2,893) while lifting median $1,500→$2,362
(+57%), cutting bust 53%→0%, and doubling life** — by sizing up only when the cushion is fat (rungs
already secured) it keeps a little right-tail the pure cap1-flat gives up. The 4-band that reaches for
$3,000 median does so by over-sizing → 28.9% bust and a $0 year (rejected below).

### Lever 3 — WITHDRAWAL policy (bank sooner / to the floor)

On $400/cap6, sweeping the cadence (bank sooner reduces stranded balance at bust):

| Cadence | median | mean | note |
|---|--:|--:|---|
| 30d (modeled rule) | $2,725 | $4,183 | default |
| 14d | $2,767 | $4,475 | marginal |
| **7d** | **$4,578** | **$5,213** | **+68% median vs 30d — but UNVERIFIED rule** |
| 1d | $2,188 | $4,614 | non-monotonic (qual-day/consistency resets) |

**Banking sooner is enormously impactful ($2,725→$4,578 at 7d) — because PAs bust, stranded balance is
pure loss.** BUT this rides entirely on the true Apex minimum-payout interval, which is **UNVERIFIED**.
Some 2026 Apex plans advertise ~8-day payout cycles; if real, this is the #1 lever. Under the modeled 30d
rule it is locked. **Floor buffer: leaving any cushion above the $52,100 floor strictly HURTS** (each
$250 buffer costs ~$250 median) — confirming *bank maximally to the floor*.

### Lever 4 — CONSISTENCY management — NON-ISSUE

Pure 50%-consistency block never exceeds **6.7%** at any size (0% at the recommended sizes). Refuted as a
material failure mode; no special payout-timing handling is warranted. Keeping cap ≤3 keeps it ~0% for free.

### Lever 5 — BANK-AND-DE-RISK — REJECTED

"Ride big to N rungs then coast small" (18 configs) **loses**: best is median **$0** / mean $2,245 /
bust 66.7%. The big base busts before banking, and the small coast can't reach later rungs' 5-qual-day +
MIN_REQ gate → stranded. Do NOT de-risk after banking.

---

## RECOMMENDED FUNDED-MANAGEMENT PLAYBOOK

Anti-overfit **robustness gate**: reject any policy whose per-year median hits $0 (single-year
concentration). This **rejects both raw median-maximizers** — $400/cap6 (2023 median $0) and cush_4band
(2022 median $0).

| Policy | median | mean | bust% | per-year median (2022/23/24/25) | gate |
|---|--:|--:|--:|---|:--:|
| baseline $400/cap2 | $1,500 | $2,893 | 53.3 | 1869 / **0** / 3459 / 2857 | ✗ |
| cush_4band (raw med-max) | $3,000 | $2,801 | 28.9 | **0** / 3000 / 4678 / 1500 | ✗ |
| **cap1-flat** | **$2,421** | $2,435 | 0.0 | 4258 / 2319 / 2390 / 881 | ✓ |
| **cush_3band XS/S/M (RECOMMENDED)** | **$2,362** | $2,842 | 0.0 | 4412 / 2136 / 2421 / 1119 | ✓ |
| cush_3band + cad14 (unverified upside) | $2,719 | $3,267 | 0.0 | 5672 / 2806 / 2983 / 1144 | ✓ |

**PLAYBOOK (deployable, 30d rule):**
1. **Funded size = cushion-aware brake, cap ≤ 3.** Trade ~1 ct (≈$300–400 risk budget) when cushion
   (balance − liquidation threshold) is thin (<$2.5k); step to 2 ct at ~$2.5k cushion; 3 ct only when
   cushion is fat (>$5k, i.e. rungs already banked). Never exceed cap 3.
2. **Withdraw maximally to the $52,100 floor** every eligible sweep — no buffer above floor.
3. **Bank as often as the real Apex rule allows** (model uses 30d; if the true interval is ~weekly, use it
   — it is the single biggest upside).
4. **No consistency games, no de-risk-after-banking** — both proven inert/harmful.

**Result vs $1,500 baseline median:** **median E[payout] ≈ $2,362 (+57%)** deployably, or **≈$2,719
(+81%)** if faster banking is permitted — with **mean essentially unchanged (~$2,842)**, **bust cut from
53% → 0%**, life 16 → 31.5 mo, and **a positive median in every calendar year** (baseline was wiped in 2023).
The cap1-flat variant ($2,421 median, dead-simple) is the ultra-robust fallback.

## Anti-overfit / determinism

- This is a **management policy, not an edge parameter** — no VPC signal/fill/threshold was touched.
- The recommended policy **pays in all 4 calendar years** ($1,119–$4,412); the rejected median-maximizers
  concentrate into one year. Full 48-cell static sweep + all lever sweeps are in the JSON.
- **Determinism:** identical md5 `13a0985433c868e2ba0f48d6cc6d0deb` across two runs.

## Biggest honest caveat

**Everything rides on UNVERIFIED help-center Apex rules × unproven live fills at funded size.** The single
highest-*potential* lever (withdrawal cadence: +68% median at 7d vs 30d) is entirely gated on the true
minimum-payout interval, which is not read off a live contract. And the whole "size down to survive" result
assumes the modeled $2,500 trail / $1,000 DLL / $52,600 lock are exact — a tighter real trail would push the
optimum even smaller, a looser one would reopen the aggressive sizes. Verify the live 50K contract terms and
run N≥30 live-fill parity before treating any dollar figure as decision-grade.
