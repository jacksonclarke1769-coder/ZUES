# VPC SPRAY-ECONOMICS — Apex 25K vs 50K (cost side + payout side, honest sim)

**Research / SIM measurement ONLY. READ-ONLY on bot strategy code (imports only). Writes confined to
`research/passrate_opt/` + `reports/passrate_opt/`. NOTHING ARMED. LIVE HOLD remains in force.**

- Harness: `research/passrate_opt/vpc_spray_economics.py`. JSON: `reports/passrate_opt/04_spray_economics.json`
  (determinism md5 `c6e8a5a5b82774af7fbf045a51dace43`).
- **Reuses certified machinery by import, re-models nothing:** VPC signal/fill/risk-sizing from
  `research/fork_b/honest_eval_engines.py` (F), day-collapse `day_rows` (ARES $550 stop + tier DLL) from
  `tools_account_size_research` (H), eval rule `eval_one/run_cell` from `vpc_firm_sizing` (S). The only
  new code is `run_pa` — a **faithful, parametrized copy of `apex_funded_40.py:74-113`** (payout rules
  unchanged; only tier constants + the fed VPC stream differ).
- **Fidelity canary:** 50K $600/cap3 rolling → **12.6 / 3.6 / 83.8 / 19d — bit-exact** to the established
  baseline. Engine faithful.
- Data: Databento NQ 1m→5m RTH, 2022-01-14 → 2026-06-19, **408 VPC trades**, net +4,919 pt.

## ⚠️ CONFIDENCE BANNER (rides every number below)

**Every Apex rule here is help-center-derived, NOT read off a live contract**
(`evidence/apex_terms/apex_terms.yaml`: confidence UNVERIFIED, source PENDING). This session web-checked
2026 Apex help-center pages (multi-source): they **corroborate the 50K ladder
[1.5/1.5/2/2.5/2.5/3]k = $13k and the $250 qual-day exactly** as the repo pins them, and give the **25K
ladder as a FLAT $1,000 ×6 = $6,000, $100 qual-day, $500 min withdrawal.** These are used as PRIMARY
inputs (better-sourced than a pure scale-guess) but **remain UNVERIFIED vs a live contract.** The `$8k
funded-value / $131 eval-fee` placeholders from the yaml are NOT used.

## Tier payout constants (help-center-derived; UNVERIFIED)

| | Start | Trail | Payout floor | Min req | DLL | Ladder (6 rungs, then PA CLOSES) | Qual-day | Confidence |
|---|--:|--:|--:|--:|--:|---|--:|---|
| **50K** | 50,000 | 2,500 | 52,100 | 52,600 | 1,000 | 1.5/1.5/2/2.5/2.5/3k = **$13,000** | $250 | help-center **corroborated (multi-source)** |
| **25K** | 25,000 | 1,500 | 26,100 | 26,600 | 500 | **flat $1,000 ×6 = $6,000** | $100 | help-center-derived (single-strength) |

Shared: QUAL_N=5, consistency 50%, payout sweep every ~30d, ARES self-imposed $550 daily realized stop
held IDENTICAL across tiers (harsh on 25K vs its $1,500 trail — pessimistic-leaning for 25K bust).

---

## 1. FUNDED SIZE SWEEP (survival) — pick the conservative size

Payout over rolling monthly funded-PA starts with ≥9-month forward runway (45 starts). Pick rule (stated,
not cherry-picked): among cells within 85% of the max E[paid], take **lowest eval-life bust%**, tie-break
higher E[paid]. **Smallest size busts LEAST** — bigger daily swings trip the tight trailing DD before the
PA locks at start+$100.

**50K pick = $400 budget / cap 2** · **25K pick = $400 budget / cap 4**

| Tier · pick | bust% | CLOSED_MAX% | $0-payout% | E[paid] mean | median | p25 | p75 | E[#payouts] | mean life (mo) |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| **50K $400/cap2** | 53.3 | 4.4 | 33.3 | **$2,893** | $1,500 | $0 | $3,000 | 1.73 | 16.4 |
| **25K $400/cap4** | 64.4 | 4.4 | 48.9 | **$1,544** | $947 | $0 | $3,000 | 1.56 | 12.5 |

*(Full 15-cell sweeps per tier in the JSON `funded_sweep`.)* Even the safest size busts the funded PA
**53% (50K) / 64% (25K)** of the time — the honest cost of a tight trailing-DD account with a real-but-thin
edge. ~⅓–½ of funded PAs pay **$0** (bust before the first eligible sweep).

### Per-year E[paid] mean — payout is regime-clustered (correlation-1 evidence)

| Tier | 2022 | 2023 | 2024 | 2025 |
|---|--:|--:|--:|--:|
| 50K | $5,318 | **$55** | $3,542 | $2,581 |
| 25K | $2,917 | **$246** | $1,712 | $1,222 |

**2023 is nearly payout-dead across BOTH tiers** — a bad edge-year starves the whole fleet at once. The
mean E[paid] is carried by strong years; a spray started into a 2023-like regime yields almost nothing.

### 25K ladder sensitivity (the single weakest input) — LOW impact

| 25K ladder variant | qual-day | E[paid] mean | median | bust% | CLOSED_MAX% |
|---|--:|--:|--:|--:|--:|
| **web flat $6,000** (PRIMARY) | $100 | **$1,544** | $947 | 64.4 | 4.4 |
| task-scaled $6,500 | $250 | $1,450 | $0 | 62.2 | 4.4 |
| task-scaled $6,500 | $100 | $1,490 | $750 | 62.2 | 4.4 |
| flat $6,000 | $250 | $1,510 | $0 | 64.4 | 4.4 |

**E[paid] mean moves only $1,450–$1,544 across every ladder × qual-day variant.** Because funded PAs bust
long before reaching the high rungs (E[#payouts] ≈ 1.5), the ladder-cap uncertainty barely touches the
answer. The flagged weakest input is **not** the binding risk — survival + rules-verity + live-fills are.

---

## 2. COST SIDE — eval fee, attempts-per-funded, activation

Pass rates recomputed here (not quoted) via the certified eval rule. **Full-window** = rolling Apex-clock
starts, 2022–2026. **Recent-regime** = eval started every Monday over the past 24 months (N=93 cohorts, 2
censored), honest censoring for starts within 30d of data-end.

| Eval config | full-window pass% | recent-regime pass% | eval bust% (full) | median days |
|---|--:|--:|--:|--:|
| **25K balanced** $1,200/cap3 | 41.3 | **47.3** | 23.6 | 13 |
| **50K best** (pass≥bust) $1,500/cap4 | 24.6 | **34.4** | 23.8 | 15 |
| **50K aggressive** $2,000/cap10 | 37.9 | **41.9** | 47.2 | 8 |

> **HONEST CORRECTION:** recent-regime pass is **HIGHER** than full-window for every config (N=93, only 2
> censored) — the past-24mo VPC regime is **favorable, not softer**. The prior "recent ~32–36%, softer"
> caveat is **not supported** for VPC in this window. (My 25K full-window 41.3% matches report 03 exactly;
> the task-brief's "47.3% full-window" was in fact the recent-regime figure, mislabeled.)

Cost/funded-PA = attempts × eval-fee + activation, attempts = 1/pass. Promo fee **$24.50** (operator-anchored,
UNVERIFIED); list-price scenario ~**$107 (25K) / $137 (50K)** (UNVERIFIED); activation **~$130 one-time**
(UNVERIFIED).

| Eval config | promo cost/funded (full → recent) | list cost/funded (full → recent) |
|---|--:|--:|
| 25K balanced | $189 → $182 | $389 → $356 |
| 50K best | $230 → $201 | $687 → $528 |
| 50K aggressive | $195 → $189 | $492 → $457 |

---

## 3. HEAD-TO-HEAD — 25K vs 50K (promo fee $24.50, recent-regime pass)

| Metric | **25K balanced** | **50K best** (1500/cap4) | **50K aggressive** (2000/cap10) |
|---|--:|--:|--:|
| E[payout]/PA — mean | $1,544 | **$2,893** | **$2,893** |
| E[payout]/PA — median | $947 | $1,500 | $1,500 |
| recent-regime eval pass% | 47.3 | 34.4 | 41.9 |
| cost per funded PA | $182 | $201 | $189 |
| **NET E[$]/PA — mean** | $1,362 | **$2,692** | **$2,704** |
| **NET E[$]/PA — median** | $765 | ~$1,299 | ~$1,311 |
| break-even pass% (mean · median) | 1.7 · 3.0 | 0.9 · 1.8 | 0.9 · 1.8 |
| **run-rate $/mo — mean** (recent) | $2,792 | $4,013 | **$4,911** |
| **run-rate $/mo — median** (recent) | $1,568 | $1,936 | **$2,381** |

Run-rate = one Monday eval/week (4.33/mo) × [pass × (E[payout] − activation) − fee]. **Median run-rate ≈
half the mean** — because ~⅓–½ of funded PAs pay $0, the mean is inflated by the right-tail CLOSED_MAX
cap-hitters. Use the **median** column for any survival/cash-flow decision.

At **list-price** fees the ranking is unchanged (50K aggressive net mean $2,402/PA, run-rate/mo mean $3,944
/ median $1,894; 25K net mean $1,155/PA). Full table in JSON `synthesis.list`.

### Verdict

**50K wins on net E[$]/PA and on per-month run-rate — mean AND median — at both fee levels.** Mechanism:
the 50K funded PA's E[payout] (~$2,893 mean) is ~1.9× the 25K's (~$1,544), driven by the **$13k ladder cap
vs $6k** and a larger funded position that survives the proportionally-wider $2,500 trail better than 25K's
$1,500 trail (which the fixed $550 ARES stop bites harder against). 50K's eval passes *less* often (higher
cost/funded), but the payout per funded PA is large enough that net E[$] and run-rate both favor it. Among
50K configs, **aggressive $2,000/cap10 edges best $1,500/cap4** on run-rate: it passes the eval more often
(41.9 vs 34.4%) at identical payout, and on a 30-day clock an eval bust just costs the fee.

**Break-even pass rate is trivially low** (0.9–1.7% mean at promo; 5–7.6% at list) — far below the 34–47%
actual. **The eval cost is not the binding constraint;** the payout side (and its verity) is.

---

## 4. CAVEATS (every number rides these)

1. **ALL Apex rules UNVERIFIED — help-center-derived, no live contract read.** The 50K ladder/qual-day are
   multi-source web-corroborated; the whole payout side still assumes they are exact. If the true trail is
   tighter or the ladder smaller, the 50K win (which rests on E[payout]) shrinks or inverts.
2. **25K ladder is single-strength-sourced** (web help-center: flat $6k). *But* sensitivity shows E[paid]
   moves only $1,450–$1,544 across all variants — PAs bust before high rungs bind, so this is **low-impact**.
3. **Payout is a wasting asset.** Each PA busts, or hits the $13k/$6k cap after 6 payouts, then **CLOSES** —
   E[payout] is a whole-life figure (mean life 12–16 mo), not a recurring annuity. A new PA needs a new eval
   + new activation.
4. **SIM, not live.** Funded fills AT SIZE are unproven — the exact open risk. Per-trade sequential marking
   is mildly optimistic vs the true joint intraday tick path. N≥30 live-fill parity still gates everything.
5. **Correlation-1.** A fleet's PAs bust together in bad regimes, and eval passes dry up in the SAME regime
   (2023 E[paid] ≈ $55/$246 — near-dead across both tiers). The mean **hides clustered drawdown**; median
   run-rate (~½ of mean) is the honest cash-flow.
6. **Recent-regime is FAVORABLE, not softer** (finding, not assumption): past-24mo Monday cohorts pass
   HIGHER than full-window. Do not assume a soft-regime discount for VPC in this window — but this is a
   backward-looking property and does not forecast the next regime.

## Single biggest confidence risk

**The entire 50K-wins result rests on the payout side, which is UNVERIFIED help-center rules × unproven
live fills at the funded size.** If either the real Apex trailing-DD/ladder is tighter than modeled, or the
VPC edge degrades on live funded-size fills, E[payout] collapses and the whole ranking is void. Verify the
live 50K contract terms and run N≥30 live-fill parity before treating any dollar figure as decision-grade.
