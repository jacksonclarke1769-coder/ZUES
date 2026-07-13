# FUNDED-STAGE THROUGHPUT OPTIMUM — Apex 50K, VPC edge FROZEN (honest sim)

**Research / SIM measurement ONLY. READ-ONLY on bot strategy code (imports only). Writes confined to
`research/passrate_opt/` + `reports/passrate_opt/`. NOTHING ARMED. LIVE HOLD remains in force.**

- Harness: `research/passrate_opt/funded_throughput_opt.py`. JSON:
  `reports/passrate_opt/07_funded_throughput_optimum.json` (determinism md5
  `2224be8a4c68b6b379eed235d16269fe`, **identical across two runs**).
- **Reuses certified machinery by import, re-models nothing:** report-05 funded engine
  `funded_stage_opt.py` (`build_vpc`, `build_level_matrix`, `days_for`, `monthly_starts`,
  `run_pa_diag`, `fixed_size`, `cushion_size` — which imports the certified VPC signal/fill
  `honest_eval_engines.py` + day-collapse `tools_account_size_research`). Payout **RULES unchanged**.
  Refund/renewal cost model reproduced verbatim from report-06.
- **Objective (a THROUGHPUT problem):** the $13k ladder caps lifetime payout per PA and a ~20 cap bounds
  the fleet, so maximize **sustainable $/slot-month = `E[paid]/E[life]` net of refund**, SUBJECT TO
  **survival** (per-year median payout > 0 in every start-year, especially 2023).
- **Metric (censoring-robust):** `slot_gross = E[paid]/E[life] = sum(paid)/sum(months)` (numerator and
  denominator right-truncate together at the window). `net_slot = slot_gross − cost_per_funded/E[life]`,
  `cost_per_funded ≈ $188.5` = `(1/0.419)·$24.50 + $130`. `fleet_net = 20 × net_slot`.
- Data: Databento NQ 1m→5m RTH, **401 days 2022-01-14 → 2026-06-19**, 45 rolling monthly starts (≥9mo
  runway). Start-years span **2022–2025** (2026 has no ≥9mo-runway start — see §5).

## ⚠️ CONFIDENCE BANNER (rides every number)

**Every Apex 50K rule is help-center-derived, UNVERIFIED vs a live contract** (ladder `[1.5/1.5/2/2.5/
2.5/3]k=$13k`, `$2,500` trail, `$1,000` DLL, floor `$52,100`/min-req `$52,600`, `5×$250` qual, `50%`
consistency, `30d` payout cadence). The **~20 account cap** and the **true minimum payout interval** are
the two most decision-relevant unverified inputs. SIM only; funded fills at 2-contract size unproven live.

## Fidelity canary (FIRST, before optimizing) — both brackets reproduce

| Bracket | policy | slot_gross | net_slot | fleet net (cap20) | bust% | per-yr median 22/23/24/25 | survives |
|---|---|--:|--:|--:|--:|---|:--:|
| **A** cushion-brake cap≤3 (report-05/06 rec.) | cush3band XS/S/M | **$90.1** | $84.1 | **$1,683** | 0.0 | 4412/2136/2421/1119 | ✓ |
| **B** pre-opt fast | $400/cap2 | **$176.4** | $164.9 | **$3,298** | 53.3 | 1869/**0**/3459/2857 | **✗ (2023 wipe)** |

Both match report-06 Leg B ($1,683 / $3,298) bit-for-bit. Engine faithful. Bracket B is the *pre-opt
trap*: high fair-weather $/mo, **but median $0 in 2023** — uninvestable (correlation-1 fleet wipes together).

---

## THE FRONTIER — survival is a CLIFF, and 2023 is the wall

**Search 1 (STATIC sweep, budget 400→2000 × cap 2→8, 48 cells): 0 of 48 survive.** *Every* static size
≥2 contracts is killed by a **2023 median of $0** (worst-year always 2023). The raw $/slot-max is
`$400/cap5 → $216 net ($4,326 fleet)` but its 2023 median is $0 — the exact pre-opt trap, **REJECTED**.

| static | net_slot | fleet | bust% | 2023 median | survives |
|---|--:|--:|--:|--:|:--:|
| 400/cap5 (raw $/slot-max) | $216 | $4,326 | 51.1 | **$0** | ✗ |
| 400/cap2 (=bracket B) | $165 | $3,298 | 53.3 | **$0** | ✗ |
| 700/cap2 | $98 | $1,970 | 71.1 | **$0** | ✗ |
| 2000/cap8 | $166 | $3,313 | 82.2 | **$0** (all years $0) | ✗ |

**Search 2/2b (DYNAMIC cushion bands, conservative→aggressive):** every band that escalates to **cap ≥4**
when the cushion fattens also busts 2023 (worst-year $0). The only survivors size down to ~1 contract when
the cushion is thin — which is exactly what 2023 forces all year. **The single survivable lever against
2023 is “shrink to ~1 ct when cushion is thin.”** Given that, the question becomes: *how much may we
escalate when cushion is fat, before it breaks survival?*

| dynamic band (cushion→ct) | net_slot | fleet | bust% | worst-yr median | survives |
|---|--:|--:|--:|--:|:--:|
| **brake_cap2** — 1ct <$3k, 2ct ≥$3k | **$98.3** | **$1,967** | **0.0** | **$705** | **✓ WINNER** |
| fat_cap5_at_12k (≡cap2: $12k trigger never fires) | $98.3 | $1,967 | 0.0 | $705 | ✓ |
| brake_cap3 (1/2/3ct at 0/2.5k/5k) | $76.9 | $1,539 | 0.0 | $964 | ✓ |
| band_cap4_mild (escalates to cap4) | $72.2 | $1,444 | 37.8 | **$0** | ✗ |
| band_cap6_fast / aggro_cap8 | $101–114 | $2,024–2,276 | 76–80 | **$0** | ✗ |

**Two clean mechanism findings:** (1) **cap-2 beats cap-3** ($98.3 vs $76.9, +28%): stepping to a 3rd
contract at $5k cushion *lowers* the rate — the larger size occasionally triggers a consistency reset or a
deeper drawdown that stalls banking. (2) **Escalation beyond cap-2 never triggers anyway** — because
withdraw-to-floor sweeps balance back to $52,100, the cushion rarely exceeds ~$3–4k, so a cap-5-at-$12k
band is *bit-identical* to the cap-2 brake. The withdraw-to-floor policy structurally caps useful size at
~2 contracts.

## Search 3 — COLLECT-AND-CLOSE is UNOBSERVABLE at any surviving sizing

**closed_max% = 0.0 and time-to-collect-ladder = censored (None) for EVERY survivor**, at every cadence.
No survivable account banks all 6 rungs within the 4.4-year window; survivors end 100% `DATA_END`
(right-censored). Only the wipe-prone big sizes ever reach the ladder cap (e.g. 400/cap5 closes 13%) — and
they fail survival. **The task’s “collect $13k fast, then the PA closes, turn the slot over” premise is
falsified for survivable sizings:** survival forces sizing so small that the ladder is never completed
in-sample. Survivors monetize via a **steady per-slot RATE**, not via ladder-completion turnover. Time-to-
collect and “true account life” are unobserved — which is exactly why the censoring-robust rate is the
only defensible metric (§5).

## The one survival-safe throughput lever: banking CADENCE (UNVERIFIED)

Faster banking cannot raise bust (it only removes stranded balance sooner) but collects rungs sooner →
higher rate. It is **gated on the true Apex minimum payout interval** (modeled 30d; some 2026 plans
advertise ~weekly).

| policy | cad30 (rule) | cad14 | cad7 | worst-yr @cad7 |
|---|--:|--:|--:|--:|
| **brake_cap2** | **$98.3** | $93.8 | **$107.0** ($2,140 fleet) | $1,593 |
| brake_cap3 | $76.9 | $88.5 | $101.3 ($2,026 fleet) | **$2,017** |
| cap1_flat | $71.3 | $74.1 | $94.8 | $599 |

Cadence is non-monotonic (qual-day/consistency resets) but **cad7 dominates and lifts the worst-year floor**
(brake_cap3@cad7 posts the highest floor, $2,017). If the real interval is ~weekly, step the winner to
cad7 → **$107/slot, $2,140 fleet**.

---

## RECOMMENDED FUNDED SIZING

**Cap-2 cushion brake, withdraw-to-floor, 30d cadence (verified-rule):**
1. **Trade 1 contract** (≈$400 risk budget) whenever cushion (balance − liquidation threshold) **< $3,000**.
2. **Step to 2 contracts** (≈$550 budget) once cushion **≥ $3,000** (i.e. a rung already banked).
3. **Never exceed 2 contracts.** (Cap-3+ either doesn’t trigger under withdraw-to-floor or lowers the rate.)
4. **Withdraw maximally to the $52,100 floor** every eligible sweep; no buffer above floor.
5. If the true Apex payout interval is faster than 30d, **use it** (cad7 → $107/slot) — the only lever
   that raises throughput without breaking survival.

| Metric | RECOMMENDED cap-2 brake | vs cushion-brake cap≤3 | vs pre-opt (bracket B) |
|---|--:|---|---|
| **sustainable $/slot-month (net)** | **$98.3** | **+17%** vs $84.1 (+28% like-for-like fast-levels $76.9) | $164.9 **but $0 in 2023** |
| **fleet $/mo at cap 20 (net)** | **$1,967** | +$284 vs $1,683 | $3,298 (fair-weather illusion) |
| bust% | **0.0** | = 0.0 | 53.3 |
| per-year median 2022/23/24/25 | 6697 / **2382** / 3440 / 705 | all-year positive | wiped 2023 |
| worst-year median | **$705 (2025)** | vs $1,119 | **$0 (2023)** |
| E[paid] mean / life | $3,289 / 31.5mo (censored) | — | $2,893 / 16.4mo |
| time-to-collect ladder | **unobserved (0% close, censored)** | same | 4.4% close |

**The recommended cap-2 brake beats the report-05/06 cushion-brake by +17% net $/slot-month (+$284/mo
fleet at cap 20) at identical 0% bust and a positive median in every observed year — including 2023
($2,382).** It captures the fast rate that static 700/cap2 also shows ($98) **without** that static
config’s 71% bust and 2023 wipe, because it shrinks to 1 contract exactly when 2023 demands it. It remains
a fraction of the pre-opt trap’s $165/slot fair-weather rate — but that rate is unbankable (correlated
2023 fleet-wipe). If the true payout interval is weekly, cad7 lifts it to **$107/slot ($2,140 fleet)**.

## Anti-overfit / robustness / determinism

- **Full 48-cell static + 8 dynamic + 4 escalate-when-fat + 12 cadence configs in the JSON.** The winner is
  chosen as **max net_slot among survivors** (per-year median > 0 every start-year), not raw max.
- **Per-year hold-out:** the winner posts a positive median in **all four observed years** (2022–2025);
  every rejected higher-rate config concentrates into 2022/24/25 and posts **$0 in 2023**.
- **Determinism:** identical md5 `2224be8a4c68b6b379eed235d16269fe` across two runs.

## §5 — Biggest honest caveats

1. **CENSORING is total for survivors.** 100% `DATA_END`, 0% ladder-close: “31.5mo life / $3,289 lifetime /
   time-to-collect” are **not observed** — they are right-censored by the 2026-06-19 window. Only the
   **rate** `E[paid]/E[life]` is censoring-robust (numerator+denominator truncate together), so all $/slot
   and fleet figures rest on the rate, not on lifetime totals. The throughput framing (“collect fast then
   close”) is *unobservable* at survivable sizing.
2. **2026 cannot be survival-tested.** No 2026 start has ≥9mo forward data; at 150–120d runway the 2026
   median is **$0 — a truncation artifact** (2026 accounts can’t bank a median payout in <6mo), not a wipe.
   The real fair-weather stress, **2023, is passed ($2,382 median)**. Treat “survives every year 2022–2026”
   as **verified 2022–2025; 2026 unobservable**.
3. **ALL Apex rules UNVERIFIED** — help-center-derived, no live contract. The **~20 cap** scales every fleet
   figure linearly; the **true payout interval** gates the single throughput lever (cad7 = +9%). Verify the
   live 50K contract terms **and the account cap**, and run **N≥30 live-fill parity at 2 contracts**, before
   treating any dollar figure as decision-grade. SIM only; nothing armed.
