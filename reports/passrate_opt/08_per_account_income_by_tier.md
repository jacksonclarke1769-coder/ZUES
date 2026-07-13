# PER-ACCOUNT FUNDED INCOME by ACCOUNT TIER — can VPC reach $500-1k/mo PER Apex PA? (honest sim)

**Research / SIM measurement ONLY. READ-ONLY on bot strategy code (imports only). Writes confined to
`research/passrate_opt/` + `reports/passrate_opt/`. NOTHING ARMED. LIVE HOLD remains in force.**

- Harness: `research/passrate_opt/per_account_income_by_tier.py`. JSON:
  `reports/passrate_opt/08_per_account_income_by_tier.json` (determinism md5
  `fd84cea56dc547d8743e78289f1c056b`, **identical across two runs**).
- **Reuses certified machinery by import, re-models nothing:** report-05 funded engine
  `funded_stage_opt.py` (`build_vpc`, `days_for`, `monthly_starts`, `run_pa_diag`, `fixed_size`,
  `cushion_size` — which imports the certified VPC signal/fill `honest_eval_engines` + day-collapse
  `tools_account_size_research`). Report-07 net_slot/fleet metric reproduced verbatim. The tier layer only
  **monkeypatches** G's globals (START/TRAIL/FLOOR/MIN_REQ/LOCK_EOD/DLL/ARES_STOP) + passes the tier
  ladder to `run_pa_diag`. **No eval/payout logic re-implemented.**
- Per-tier Apex constants from **`tools_account_size_research.SPECS`** (the codebase's canonical per-tier
  source; its 50K row matches the certified G engine bit-for-bit).
- Data: Databento NQ 1m→5m RTH, 401 days 2022-01-14 → 2026-06-19, ~45 rolling monthly funded-PA starts
  (≥9-month runway). Start-years span **2022–2025** (2026 has no ≥9mo-runway start).

## Fidelity canary (FIRST) — 50K reproduces report-07 exactly
50K brake_cap2: **slot_gross $104.3** (target 104.3), **net@cost-$188.5 = $98.3** (target 98.3), bust 0.0%,
per-year median `{2022:6697, 2023:2382, 2024:3440, 2025:705}` — **bit-exact** to report-07's winner. Engine
faithful; the tier layer is a pure re-parametrization of the reused funded engine.

## Metric
`slot_gross = E[paid]/E[life] = Σpaid/Σmonths` (censoring-robust — numerator+denominator right-truncate
together). `net_slot = slot_gross − cost_per_funded/E[life]`. `fleet_net = 20 × net_slot`. **Posture A** =
max net_slot among configs with per-year median payout > 0 **every** start-year **AND bust ≤ 5%** (the
investable rate). **Posture B** = max net_slot **ignoring** survival (its bust% + 2023 shown). A middle
**A-loose** = median>0 every year but any bust.

---

## THE TIER × POSTURE TABLE ($/slot-month, net of refund; fleet at 20-cap)

| Tier | ladder (lifetime) | **A: survivable (bust~0)** | fleet@20 | A-loose (med>0, any bust) | **B: fair-weather MAX** | B bust% | **B 2023 median** |
|---|---:|---:|---:|---:|---:|---:|---:|
| **50K**  | $13,000  | **$98/mo** (brake_cap2, bust 0) | $1,962 | $98 (bust 0) | **$216/mo** (400/cap5) | 51% | **$0 (WIPE)** |
| **100K** | $17,000* | **$72/mo** (brake_cap2, bust 0) | $1,435 | $72 (bust 0) | **$292/mo** (660/cap8) | 58% | **$0 (WIPE)** |
| **150K** | $22,500* | **$17/mo** (brake_cap3, bust 0) | $351 | **$212** (640/cap2, **bust 24%**) | **$299/mo** (640/cap8) | 56% | **$0 (WIPE)** |

\* 100K/150K ladders are **ESTIMATES** (SPECS: 100K ~$17k, 150K ~$21.5k lifetime; endpoints documented,
middle rungs estimated monotone). The brief's guessed ~$26k/$39k are naive linear scaling — NOT used.

## DIRECT VERDICT — is $500-1,000/mo PER ACCOUNT reachable?

**NO. At no tier and no posture does per-account income reach $500/mo — let alone $1,000/mo.**
- **Survivably (bust~0, positive every year incl 2023): best is 50K at $98/slot-mo.** $500 is 5× away.
- **Fair-weather ceiling (ignoring survival): ~$300/slot-mo (150K, 660/cap8)** — and it **wipes to $0
  median in 2023 at 56% bust.** Still below $500, and uninvestable.
- The absolute maximum net_slot found in **any** of 159 configs across all three tiers is **$299** — the
  edge's raw monthly $-throughput per PA is physically bounded well under $500 before bust eats it.

**The operator's hypothesis (a bigger account's bigger DD + bigger ladder unlocks $500-1k/mo) is REFUTED.**
Bigger tiers make the survivable rate **WORSE, not better**: 50K $98 → 100K $72 → 150K $17. The
2023-survival constraint forces sizing down to ~1 contract when the cushion is thin (all of 2023), and on
a bigger account the payout floor/MIN_REQ scales up faster ($52.6k → $103.1k → $154.1k) than the per-
contract edge — so at that forced 1-contract size the bigger account almost never triggers a banked rung.
The wider DD only helps the **fair-weather** rate (150K $299 vs 50K $216), and that rate is the exact
correlation-1 fleet-wipe trap (median $0 in 2023) that report-07 already rejected.

**The one middle case:** 150K at **$212/slot-mo survives every year in the median — but at 24% bust**
(≈1-in-4 accounts wipe). That is a semi-fair-weather posture, still < $500, and not bust~0.

## COST TO OBTAIN each tier (the ROI kills bigger tiers twice)

`cost_per_funded = (1/pass_rate)·eval_fee + activation`. Pass rates = report-03 aggressive; eval-fee ladder
`$25/$50/$85` promo (**FLAGGED, unverified**); activation `$130` held (**may scale, FLAGGED**).

| Tier | eval pass% | E[evals]→1 funded | eval $ | + activation | **cost/funded** | survivable $/slot-mo | payback |
|---|---:|---:|---:|---:|---:|---:|---:|
| 50K  | 38% | 2.6 | $66  | $130 | **$196** | $98 | ~2.0 mo |
| 100K | 22% | 4.5 | $227 | $130 | **$357** | $72 | ~5.0 mo |
| 150K | 14% | 7.1 | $607 | $130 | **$737** | $17 | ~43 mo |

Bigger tiers cost **1.8×/3.8×** more to stand up **and** yield a **lower** survivable rate — payback time
explodes. On a survivable basis the 150K is economically absurd (43-month payback on the refill cost alone).

## §5 — Biggest honest caveats

1. **SINGLE BIGGEST CAVEAT — the 100K/150K ladders are ESTIMATES and the tier DD/DLL disagree across
   sources.** SPECS (used) says 150K trail $4,000 / DLL $2,000 / ladder $21.5k; report-03's table says
   trail $5,000 / DLL $3,000; funded_rules.py says trail $5,000. If the real 150K ladder were the brief's
   guessed $39k, the survivable rate would scale ~1.7× (→ ~$30, still nowhere near $500) and fair-weather
   ~$500 — but that fair-weather still wipes 2023 and costs 3.8× the eval. **No tier/ladder assumption in
   the plausible range flips the verdict to "$500/mo survivably".** Verify the live 100K/150K contract
   (ladder, trail, DLL, MIN_REQ) before any of these dollar figures is decision-grade.
2. **ALL Apex rules help-center-derived, UNVERIFIED vs a live contract; SIM fills.** The ~20 account cap
   scales every fleet figure linearly; funded fills at multi-contract size are unproven live.
3. **Censoring is total for survivors** (100% DATA_END, 0% ladder-close): lifetime totals unobserved, so
   all figures rest on the censoring-robust rate. **2026 is not survival-testable** (no ≥9mo-runway start);
   the real fair-weather stress, 2023, IS tested — and every fair-weather config wipes there.
4. **Size headroom scaled by the trailing-DD ratio** f=trail/2500 (50K 1.0 / 100K 1.2 / 150K 1.6) — the DD
   is the hard bust cap. DLL/ARES give ~2× daily headroom; the tighter trail ratio was used (conservative,
   flagged). The qualitative verdict is robust to this scaling: raising f only raises the fair-weather
   rate (which still wipes 2023), never the bust~0 survivable rate above ~$100.
