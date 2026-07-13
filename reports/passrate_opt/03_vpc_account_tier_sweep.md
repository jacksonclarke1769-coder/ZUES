# VPC eval PASS-RATE — ACCOUNT-SIZE TIER × FIRM × SIZING (honest sim)

**Research / sim measurement ONLY. READ-ONLY bot strategy code (imports only). Writes confined to `research/passrate_opt/` + `reports/passrate_opt/`. Nothing armed. LIVE HOLD remains in force.**

- Harness: `research/passrate_opt/vpc_account_tier_sweep.py` — **REUSES `vpc_firm_sizing.run_cell / eval_one / per_year_passes` VERBATIM by import.** The tier layer only sets the module globals `START`/`TARGET` and passes tier-scaled `dd`/`dll`. **No eval logic re-implemented.**
- JSON: `reports/passrate_opt/03_vpc_account_tier_sweep.json` · determinism md5 **`7a58a9565246b5ff747f3c1c48b07312`** (identical over two runs).
- Data: Databento NQ 1m→5m RTH, window **2022-01-01 → 2026-06-22**. 408 VPC trades, net +4,919 pt.
- ARES self-imposed daily realized stop **$550**, held IDENTICAL across firms AND tiers (certified machinery). The VPC $ event stream is **tier-invariant** (same budget/cap → same $ P&L); only START/TARGET/DD/DLL change per tier.

## (a) Fidelity canary — reproduced EXACTLY

50K Apex $600/cap3 through this tier harness → **PASS 12.6 / BUST 3.6 / EXPIRE 83.8 / median 19d** — bit-exact match to the established honest baseline and the 01 sweep. Engine faithful; the tier layer is a pure parametrization of the reused eval rule.

## Tier / firm $ table (verification status)

| Tier | Start | Target | Apex trail | others trail (Topstep/MFFU/Bulenox/ETF) | Apex DLL | Bulenox DLL |
|---|---:|---:|---:|---|---:|---:|
| 25K | 25,000 | 1,500 | 1,500 | 1,500 / 1,500 / 1,500 / 1,500 | 500 | 550 |
| 50K | 50,000 | 3,000 | 2,500 | 2,000 / 2,000 / 2,500 / 2,000 | 1,000 | 1,100 |
| 100K | 100,000 | 6,000 | 3,000 | 3,000 / 3,000 / 3,000 / 3,000 | 2,000 | 2,200 |
| 150K | 150,000 | 9,000 | 5,000 | 4,500 / 4,500 / 4,500 / 4,500 | 3,000 | 3,300 |

**Verification:** Apex column = **Apex's PUBLISHED per-tier target/trail** (best-verified here; re-confirm before commitment). The **50K row of every firm = the certified 01 anchor** (canary). **All other non-Apex cells use STANDARD 6%-target scaling with sub-linearly-scaled trail and are UNVERIFIED.** ETF_Static $ are the least trustworthy (static archetype). **Topstep has no real 25K tier — its 25K row is an EXTRAPOLATION (double-flagged).** Target scales 6%-linearly (×6 from 25K→150K) while trail scales only ×3 → **bigger tiers get a structurally wider floor relative to distance**, which drives the results below.

Firm-invariant rules (unchanged from 01): Apex 30-day clock / min-days 1 / no consistency · Topstep min-5 / 50% consistency · MFFU-Builder min-2 / none · Bulenox min-1 / none · ETF-Static min-5 / none / STATIC floor.

## (b) Per-tier best cell, each firm (native metric: raw pass% for Apex clock, resolved% for unlimited)

| Tier | Firm | best cell | native pass% | raw pass% | BUST% | median d | CEN% |
|---|---|---|---:|---:|---:|---:|---:|
| 25K | Apex | $1200/cap10 | 42.3 | 42.3 | 52.1 | 5 | 0 |
| 25K | Topstep | $600/cap8 | 41.3 | 40.1 | 57.1 | 50 | 2.7 |
| 25K | MFFU | $600/cap6 | 52.4 | 51.9 | 47.1 | 17 | 1.0 |
| 25K | Bulenox | $600/cap3 | 55.9 | 55.4 | 43.6 | 21 | 1.0 |
| 25K | ETF-Static | $600/cap3 | 60.1 | 58.6 | 38.9 | 27 | 2.5 |
| 50K | Apex | $2000/cap10 | 37.9 | 37.9 | 47.2 | 8 | 0 |
| 50K | Topstep | $600/cap8 | 47.8 | 45.9 | 50.1 | 64 | 4.0 |
| 50K | MFFU | $600/cap8 | 50.5 | 48.6 | 47.6 | 49 | 3.7 |
| 50K | Bulenox | $600/cap8 | 64.6 | 61.1 | 33.4 | 57 | 5.5 |
| 50K | ETF-Static | $600/cap6 | 65.9 | 62.6 | 32.4 | 61 | 5.0 |
| 100K | Apex | $2000/cap10 | 22.3 | 22.3 | 57.7 | 12 | 0 |
| 100K | Topstep | $600/cap8 | 57.0 | 50.9 | 38.4 | 145 | 10.7 |
| 100K | MFFU | $600/cap8 | 57.0 | 50.9 | 38.4 | 140 | 10.7 |
| 100K | Bulenox | $600/cap8 | 57.0 | 50.9 | 38.4 | 140 | 10.7 |
| 100K | ETF-Static | $600/cap8 | 81.6 | 72.8 | 16.5 | 165 | 10.7 |
| 150K | Apex | $2000/cap10 | 14.4 | 14.4 | 26.9 | 18 | 0 |
| 150K | Topstep | $600/cap6 | 84.4 | 70.3 | 13.0 | 337 | 16.7 |
| 150K | MFFU | $600/cap6 | 84.4 | 70.3 | 13.0 | 337 | 16.7 |
| 150K | Bulenox | $600/cap6 | 84.4 | 70.3 | 13.0 | 337 | 16.7 |
| 150K | ETF-Static | $600/cap8 | 93.7 | 78.1 | 5.2 | 343 | 16.7 |

*(Full 25 budget×cap cells per tier×firm — 500 cells — in the JSON `grid`.)*

## (c) The tier effect splits by firm archetype — OPPOSITE directions

**On Apex (the ONLY firm with a real 30-day clock, and the best-verified $):** SMALLER tier passes **HIGHER AND QUICKER**.

| Apex tier | MAX-pass cell | pass% | bust% | median d | best pass≥bust cell | pass% | bust% | median d |
|---|---|---:|---:|---:|---|---:|---:|---:|
| **25K** | $1200/cap10 | **42.3** | 52.1 | **5** | $1200/cap3 | **41.3** | 23.6 | **13** |
| 50K | $2000/cap10 | 37.9 | 47.2 | 8 | $1500/cap4 | 24.6 | 23.8 | 15 |
| 100K | $2000/cap10 | 22.3 | 57.7 | 12 | — (none) | — | — | — |
| 150K | $2000/cap10 | 14.4 | 26.9 | 18 | $900/cap8 | 2.8 | 1.0 | 23 |

The fixed-$ VPC edge reaches the smaller $1,500 target in fewer trades, so more starts beat the 30-day clock. **25K Apex $1200/cap3 = 41.3% pass / 23.6% bust / 13d median (p25–p75 6–21)** is the clean confirmation of the brief's hypothesis: highest pass among pass≥bust cells that resolve in <30 days, on the most-verified firm.

**On UNLIMITED firms (no clock):** the effect INVERTS — LARGER tier passes far HIGHER but MUCH slower. 150K ETF 93.7% / Bulenox-MFFU-Topstep 84.4% resolved, but **median 337–343 days and 16.7% censored** (many starts can't resolve within the 4.5-yr window). Smaller tier trades pass% for speed: 25K ETF 60.1% but median 27d. With infinite time, the structurally wider 150K floor rarely trips — you "eventually" pass given ~1 year of continued edge. That is high pass but terrible cash-flow, and it leans entirely on the unverified sub-linear trail scaling.

## (d) Rankings

**RANK A — MAX pass% (native):** dominated by 150K unlimited cells. #1 **150K ETF_Static $600/cap8 → 93.7% resolved (78.1% raw) / 5.2% bust / median 343d / 16.7% censored.** Verified-archetype peer: **150K Bulenox/MFFU/Topstep $600/cap6 → 84.4% resolved / 13.0% bust / 337d.**

**RANK B — pass≥bust AND median <30 days (high-and-quick):** dominated by **25K Apex**. Standout **25K Apex $1200/cap3 (≡$1500/$2000 cap3) → pass 41.3% / bust 23.6% / median 13–14d (p25–p75 6–21).** Fastest safe-ish: 25K Apex $900/cap6 → 41.0 / 40.0 / 8d (but bust≈pass, thin margin).

**RANK C — pass-per-day (pass≥bust):** 25K Apex $900/cap6 = 5.13 pass-pts/day (#1), then a run of 25K Apex cells; best unlimited entry is 25K Bulenox $600/cap8 (3.16/day, 53.7% pass / 17d).

## (e) Per-year concentration (headline cells) — NO single-year >50%

| cell | 2022 | 2023 | 2024 | 2025 | 2026 | max share |
|---|--:|--:|--:|--:|--:|--:|
| 25K Apex $1200/cap3 | 40 | 23 | 38 | 39 | 21 | 24.8% |
| 150K Bulenox $600/cap6 | 84 | 37 | 93 | 68 | 0 | 33.0% |
| 150K ETF $600/cap8 | 86 | 66 | 93 | 68 | 0 | 29.7% |

Passes spread across all years; no single-year concentration. **But the 150K cells register 0 passes in 2026** — every 2026 start is censored because its ~337-day median exceeds the remaining runway. The 150K "high pass" is real only for start-years with a full forward year of data; it is NOT a property that a start beginning today could realize inside the sample.

## (f) HONEST CAVEATS

1. **The bigger-tier-passes-higher result rides entirely on UNVERIFIED sub-linear trail scaling.** Target scales 6%-linearly, trail only ×3 across 25K→150K (standard prop scaling, but only **Apex's** numbers are published). If any firm's true 150K trail is tighter (or target higher), the 93.7%/84.4% collapse. ETF_Static $ are the least trustworthy of all.
2. **150K "pass" is a ~1-year, cash-flow-dead outcome.** Median 337–343 days + 16.7% censored. It relies on the VPC edge persisting for a full year per attempt — an assumption the 2026 zeros directly expose. Not a fast, robust eval; a slow accretion bet on edge durability.
3. **Topstep has no real 25K tier** — that row is an extrapolation. Most non-Apex, non-50K $ are standard-scaled, not confirmed.
4. **ARES $550 daily stop is fixed across tiers** — proportionally much harsher on a 25K (vs its $1,500 trail) than on a 150K. Smaller-tier bust% is therefore, if anything, pessimistic-leaning on this axis, while its speed advantage is genuine.
5. **Still sim, not live.** Faithful next-5m-open VPC fills + certified day-collapse; per-trade sequential marking is mildly optimistic vs the true joint intraday tick path. Measures eval-CARRY only, NOT stress-certification for arming. N≥30 live-fill parity still gates everything.
6. **Fast cells run bust-heavy.** 25K Apex clock cells sit at bust 23–52%; on a 30-day clock a bust ≈ losing only the eval fee, but flagged.
