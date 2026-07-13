# RULE-OUT-2023 / MAX-PROFIT — Apex 50K funded, VPC edge FROZEN (honest sim)

**Research / SIM measurement ONLY. READ-ONLY on bot strategy code (imports only). Writes confined to
`research/passrate_opt/` + `reports/passrate_opt/`. NOTHING ARMED. LIVE HOLD remains in force.**

- Harness: `research/passrate_opt/rule_out_2023.py`. JSON:
  `reports/passrate_opt/09_rule_out_2023_maxprofit.json` (determinism md5
  `5c3e3df4880a16b0e16f92be47f89caa`, **identical across two runs**).
- **Reuses certified machinery BY IMPORT, re-models nothing:** report-05 funded engine
  `funded_stage_opt.py` (`build_vpc`, `days_for`, `run_pa_diag`, `cushion_size`, `fixed_size`,
  `monthly_starts` — which import the certified VPC signal/fill `honest_eval_engines.py` +
  day-collapse `tools_account_size_research`) and report-07 `funded_throughput_opt.py`
  (`metrics`, `COST_PER_FUNDED≈$188.5`, `build_fast_matrix`, `ACCOUNT_CAP=20`). Payout RULES
  unchanged. The stand-down filter is applied **only** through `size_fn` + an added zero-P&L `HALT`
  level in the mats dict; `run_pa_diag` is untouched.
- **Canary reproduces report-07 bit-for-bit:** bracket A (cushion-brake) net **$84.1** / fleet
  **$1,683**; bracket B ($400/cap2 fast) net **$164.9** / fleet **$3,298** / **2023 median $0**.
- Data: Databento NQ 1m→5m RTH, 401 days 2022-01-14 → 2026-06-19, 45 monthly starts. Per-year =
  by **start-year**. `net_slot = E[paid]/E[life] − cost/E[life]` (censoring-robust rate).

## ⚠️ CONFIDENCE BANNER (rides every number)
Every Apex 50K rule is help-center-derived, **UNVERIFIED vs a live contract** (ladder $13k, $2,500
trail, $1,000 DLL, floor/min-req, 5×$250 qual, 50% consistency, 30d cadence, ~20 account cap). SIM
only; 2-contract funded fills unproven live.

---

## PART 1 — WHAT MADE 2023 BAD (day-level, cap-2 funded reference)

2023 was **not a crash — it was a grinding, sustained bleed** that outlasted the account's drawdown
budget. At the funded cap-2 reference:

| Year | sum P&L | max intra-yr DD | worst 20-day window | avg win | gain/loss | win-rate | trading days |
|---|--:|--:|--:|--:|--:|--:|--:|
| 2022 | $5,087 | −$2,012 | — | $478 | 1.86 | — | 86 |
| **2023** | **$848** | **−$3,924** | **−$2,805** | **$326** | **1.53** | **41.4%** | 87 |
| 2024 | $4,635 | −$2,698 | — | $390 | 1.69 | — | 93 |
| 2025 | $4,617 | −$2,229 | — | $366 | 1.64 | — | 85 |

**The killer:** 2023's −$3,924 intra-year drawdown **exceeds the $2,500 trailing threshold** — so a
funded account sized to earn (cap-2+) gets liquidated before it can bank cushion. The damage is a
**6-month cluster, not one day**: after a good Q1 (Jan +$1,185, Mar +$1,961), the edge bled
**Apr −$101, May −$201, Jun −$445, Jul −$266, Aug −$1,593, Sep −$618** (cap-2). Mechanism: the edge
had its **weakest follow-through of any year** — smallest avg win ($326), lowest gain/loss (1.53),
lowest win-rate (41.4%). Trade frequency was normal (87 days). VWAP-pullback continuation simply
barely worked in a flat/chop 2023; the whole year netted +$848/cap-2 vs ~$4.6–5.1k elsewhere.

## PART 2 — DETECTABILITY: does a CAUSAL stand-down avoid 2023? **NO.**

Built a causal equity-curve stand-down: signal = trailing-K P&L of the strategy's own **1-contract
reference equity curve** (exogenous to account sizing, read only through day *i−1* → fully causal),
one rule (K, threshold); when it fires, **HALT** (zero-P&L day) or shrink to 1ct. Grid: K∈{10,20,30},
threshold∈{0,−$300,−$600}, plus drawdown-mode and a shrink variant — **21 filters** on the two
$0-in-2023 traps.

**Result: 0 of 21 filters fix 2023 while keeping ≥70% of good-year profit.**

| filter on c2_static | halt % days | 2023 med (base $0) | good-yr net (base $143.6) | keep |
|---|--:|--:|--:|--:|
| trailK10 / thr −$300 | 25% | **$0** (unfixed) | $162.9 | 1.13 |
| trailK10 / thr $0 (only one that lifts 2023) | 42% | $1,500 | $52.8 | **0.37** |
| drawdown −$2,500 | 0% | $0 | $143.6 | 1.00 |
| trailK20 / thr −$300 shrink-to-1ct | 26% | $0 | $81.4 | 0.57 |

**The tension is fundamental and not fixable by tuning:** 2023's slow bleed is *ex-ante
indistinguishable* from the choppy stretches that **precede** every good year's payday (Jul-2022
+$2,082, Jul-2024 +$3,643, Oct-2025 +$3,282). To halt hard enough to dodge 2023 (threshold $0, 42%
of days out) you also sit out that pre-explosion chop → good-year net collapses $143.6→$52.8. To keep
the good years you barely halt → 2023 stays a $0 wipe. Every filter is dominated by the no-filter
survivor. (Stacking a *mild* filter on the already-surviving cushion-brake nudges 2023 $2,382→$4,230
at ~flat good-year net, but that config **already** survives 2023 without any regime theory.)

**The one thing that survives 2023 is NOT a regime filter** — it is the report-07 cushion-brake
(1ct when cushion <$3k, 2ct above): a same-account *solvency* rule that fires identically every year.
It posts **positive 2023** (median $2,382, net_slot **+$72.9**, 0% bust) by simply being small when
thin — exactly what 2023 forces all year.

## PART 3 — MAX PROFIT ex-2023, and its TRUE 2023 COST (never hidden)

Ranked all static budget×cap + dynamic configs by `net_slot` over **{2022,2024,2025} only**:

| config | net/slot ex-2023 | fleet ex-2023 (cap 20) | **its 2023: median / bust% / zero%** |
|---|--:|--:|:--|
| **1100/cap8 (ex-2023 MAX)** | **$235.6** | **$4,712** | **$0 / 100% / 91.7%** — total fleet wipe |
| 400/cap5 | $230.6 | $4,612 | $0 / 100% / 83.3% |
| 400/cap4 | $230.7 | $4,614 | $0 / 100% / 83.3% |
| — survivor: **cap-2 cushion-brake** | $109.5 (good yrs) | $2,190 | **$2,382 / 0% / — (SURVIVES)** |

The ex-2023 maximum (**$235.6/slot, $4,712 fleet**) is **2.4× the survivor** — but in 2023 that exact
sizing **busts 100% of accounts** ($0 median, 91.7% pay nothing). Every config that beats the ~$98–110
survivor requires accepting a 2023 fleet wipe. Crucially, the survivor already earns **positive** in
2023 (+$72.9/slot), so *including* 2023 only drags it $109.5→$98.3 (~$11/slot, ~$220/mo fleet) — a
modest cost, not a wipe. Ruling out 2023 buys the survivor almost nothing; it only "helps" the
aggressive sizings, and only by pretending their 100%-bust year away.

## VERDICT — (B) FAIR-WEATHER BET

**No robust causal filter avoids 2023** (0/21; the mechanism is a slow bleed indistinguishable ex-ante
from good-year chop). Therefore any profit above the ~$98–110/slot cushion-brake survivor **requires
accepting the 2023 wipe**. The rosy ex-2023 number is **$235.6/slot ($4,712/mo fleet, 1100/cap8)** —
and its honest 2023 consequence is a **100% fleet bust, $0 median, 91.7% zero**. This is a bet that a
2023-type flat/low-follow-through regime won't recur, on a correlation-1 fleet that would wipe
together if it did. The only durable answer remains the report-07 cushion-brake (**$98.3/slot, $1,967
fleet, 0% bust, positive every year incl. 2023 $2,382**) — which needs no 2023 exclusion.

## Caveats
1. **Censoring**: life unobserved for survivors — all figures rest on the censoring-robust rate
   `E[paid]/E[life]`, not lifetime totals.
2. **ALL Apex rules UNVERIFIED**; ~20 cap scales every fleet figure linearly.
3. **Single-year filter = overfit risk on ONE event.** Held the filter to sane behaviour in all four
   years, not just dodging 2023 — it fails that bar (guts good years), which is *why* the verdict is
   fair-weather, not real. 2026 unobservable (<9mo runway). SIM only; nothing armed.
