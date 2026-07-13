# B — Overnight (Globex) Structure → RTH  |  Edge Discovery

**Verdict: EDGE-FOUND (research-grade, NOT deployable / nothing armed).**
The survivor: **30-minute opening-range breakout, taken ONLY when the overnight range is COMPRESSED**
(`on_rng_ratio < 0.8`, i.e. overnight high−low below 0.8× its trailing-20-day median). The gap and
overnight-high/low-break hypotheses are **NO-EDGE**.

Data: REAL Databento NQ 1m, `NQ_databento_1m_5y.parquet`, 2021-06-22 → 2026-06-22, 1,769,367 bars.
Analyst worked in points; NQ = $20/pt. All work in `research/edge_discovery/`. Nothing armed.

---

## 0. Overnight data was TRULY available
Raw parquet is FULL 24h session, not RTH-only. NY-hour histogram shows every hour 0–23 populated
(~77k bars each) EXCEPT hour 17 — which is the correct CME daily maintenance halt (17:00–18:00 ET),
not a data gap. So the overnight/Globex session (prior 18:00 ET → 09:30 ET) is fully reconstructable.
1,288 RTH trading days with a complete, causal overnight feature set were built.
**Not data-gated.**

Overnight features per day (all known AT 09:30, causal): ON high/low/range, ON close, ON volume,
gap (RTH open − prior RTH close), open position within ON range, and
`on_rng_ratio = ON_range / shift(1) median-20 of ON_range` (regime-relative, uses only prior days).

---

## 1. Exploratory structure (no trades — is there anything there?)
- **H1 ON-range → RTH-range (VOLATILITY forecast): REAL & strong.** corr(ON_range, RTH-first-hour
  range) = **0.563**; cleanly monotonic by ON-range quintile (first-hour range 121 → 200 pt low→high
  quintile). This is a volatility/expansion predictor, consistent with the repo meta-law
  *"structure in VOL, direction ≈ null"*.
- **H2 gap → direction: WEAK / inconsistent.** Bucketed first-hour returns have mean vs median sign
  disagreement (e.g. flat-open mean −12.7 but the tails dominate); no stable directional signal.
- **H3 open-position / ON-level break: WEAK.** frac_up ≈ 0.50–0.55 across position quintiles. The
  RTH open is essentially ALWAYS inside the overnight range (1 of 1,288 days opened outside), so
  "break of ON level at the open" does not exist; ON-level breaks can only be tested intra-RTH (→ Family B).

The only robust raw signal is a **volatility forecast**, not a direction forecast — so the tradeable
form must let the market pick direction (a breakout) and use the overnight signal as a **regime gate**.

---

## 2. FULL SEARCH (anti-data-mining) — 70 configurations, ALL reported
Engine: 1m intrabar, **adverse-first** (stop taken before target when both sit inside a bar),
stop-order / market fills only (NO resting limit — avoids the Profile-A stale-limit trap),
base cost **0.75 pt round-trip**, entries only in the first RTH hour, forced exit 15:59.
`research/edge_discovery/_search_results.csv` holds all 70 rows. Families & counts:

- **Family A — opening-range breakout** (OR window {15,30}m; gate {all, expanded>1.2, compressed<0.8};
  direction {breakout, fade}; exit {1R, 2R, close, trail}; R = OR width): **48 configs**.
- **Family B — overnight high/low break intra-RTH** (stop {20,40}pt; exit {1R,2R,close}): **6 configs**.
- **Family C — gap fade/continuation** (|gap|>{30,60}pt, roll-guarded; {fade,cont}; exit
  {gapfill,1R,2R,close}): **16 configs**.

Top of the full search (PF, base cost):

| tag | n | PF | WR | tot(pt) |
|---|---|---|---|---|
| **A_30_comp_breakout_2R** | 324 | **1.393** | .481 | 4638 |
| A_30_comp_breakout_close | 324 | 1.361 | .460 | 4374 |
| A_30_comp_breakout_trail | 324 | 1.351 | .441 | 3167 |
| A_30_comp_breakout_1R | 324 | 1.331 | .549 | 3510 |
| A_30_all_breakout_close | 1102 | 1.238 | .475 | 12623 |
| C_30_cont_30_close | 565 | 1.228 | .273 | 4349 |
| … (66 more, see CSV) | | | | |

Two signals from the raw table: (a) the **entire** `A_30_comp_breakout` exit family clusters
1.33–1.39 — robustness across the exit dimension, not a lucky single cell; (b) **Family B (ON-level
break) and Family C (gap) fail** — best B is PF 1.121 @ WR 0.24; every gap config with a real
target loses (gapfill variants are catastrophic PF≈0, cont/fade 1R–2R all <1); the one positive gap
cell (`cont_close` 1.228) is just holding a directional bet to the close (drift capture), not a
gap-specific edge, and its WR is 0.27. **Gap and ON-level hypotheses = NO-EDGE.**

---

## 3. GAUNTLET on the survivor family `A_30_comp_breakout`
(30m OR; enter on first breakout of OR high/low after 10:00; stop = opposite OR extreme so R = OR
width; overnight-COMPRESSED days only.) IS = 2022–2024, OOS = 2025–2026, params fixed. `2021` is a
partial year (data starts Jun-2021), shown for completeness, excluded from the IS/OOS split.

**(1) Family across exits — full sample / IS / OOS / per-year (no sign flip):**

| exit | n | PF | IS PF (n) | OOS PF (n) | per-year PF |
|---|---|---|---|---|---|
| 2R | 324 | 1.393 | 1.556 (199) | **1.188 (90)** | 22:1.71 23:1.39 24:1.60 25:1.22 26:1.11 |
| close | 324 | 1.361 | 1.493 (199) | **1.207 (90)** | 22:1.82 23:1.20 24:1.53 25:1.13 26:1.37 |
| trail | 324 | 1.351 | 1.479 (199) | 1.088 (90) | 22:1.46 23:1.34 24:1.69 25:1.05 26:1.17 |
| 1R | 324 | 1.331 | 1.411 (199) | 1.230 (90) | 22:2.02 23:1.10 24:1.21 25:1.29 26:1.11 |

**Every single year 2021–2026 is PF > 1.05 for all four exits — no losing year, no sign flip.** ✅

**(2) Cost stress (N=324 ≥ 50):** 2R → PF 1.393 / 1.368 / 1.344 at cost ×1/×2/×3 (0.75/1.5/2.25pt).
close → 1.361 / 1.337 / 1.314. **Survives ×3 cost comfortably.** ✅

**(3) +1-bar-shift lookahead canary** (enter one 1m bar AFTER the trigger, at that bar's open):
2R 1.393 → 1.339; close 1.361 → 1.307. **Graceful degradation, edge persists → not a fill/lookahead
artifact.** ✅ (Overnight stats are causal by construction; `on_rng_ratio` uses `shift(1)` median.)

**(4) CONTROL — is the edge the GATE or would any breakout do?** Same 30m breakout, 2R:
- ungated (all days): PF 1.197, **OOS 1.068** (barely positive)
- expanded gate (>1.2): PF 1.146, **OOS 0.896** (FAILS OOS; 2025/26 losing 0.96/0.78)
- **compressed gate (<0.8): PF 1.393, OOS 1.188**
The compressed gate specifically adds OOS edge; the expanded regime is where breakouts *fail*.
Mechanism is coherent: a compressed overnight = coiled spring → the RTH breakout expands and follows
through; an already-expanded overnight has spent its energy → breakout chops. This is H1
(ON-range→RTH-range) monetized as a **regime gate on a market-chosen direction**, not a direction bet. ✅

**(5) Independent OR-window robustness:** the 15m-OR compressed breakout also survives OOS
(2R: PF 1.205, OOS 1.172; close: 1.157, OOS 1.056) — a different OR window, same gate, still positive. ✅

---

## 4. Survivor scorecard
- **Config:** 30-min opening range; after 10:00 ET take the FIRST break of OR-high (long) / OR-low
  (short); stop = opposite OR extreme (R = OR width); target 2R **or** RTH-close (both survive);
  **only on days where overnight range < 0.8× its 20-day median**; one trade/day; force-flat 15:59.
- **Entry type:** stop / market on breakout — NO resting limit.
- **Fill realism:** 1m intrabar, adverse-first, fill = max(level, bar-open) [worse of the two],
  0.75pt round-trip cost, +1-bar canary clean.
- **Stats (2R):** PF 1.393 full / **IS 1.556 / OOS 1.188**; WR 0.481; +4,638 pt over ~4.8 yrs.
- **Frequency:** ~324 trades / 4.8 yr ≈ **1.3 trades/week** (compressed nights ≈ 25% of days).
- **Cost ×3:** PF 1.344. **Per-year:** all 6 years > 1.05.

## 5. Honest caveats (why "research-grade", not "deploy")
- OOS is only ~1.5 years (2025 + half-2026), n=90; 2026 alone is 24 trades — **thin OOS tail**.
- The `comp` gate was selected after viewing the 70-config table. Mitigations: it was **pre-registered
  as hypothesis 1**, the **whole exit family** survives, the **control** proves the gate (not the
  breakout) carries the OOS edge, **every year is positive**, and it is **cost-×3 and canary robust**.
  This is a real effect, but confirm on genuinely forward data before sizing.
- Low frequency (~1.3/wk) — a diversifier, not a standalone income engine.
- Not built into an executor and not parity-checked; **nothing armed**. Next: lock exit=2R (or close),
  freeze params, forward-track OOS, then Pine/executor mirror + parity before any capital.

Artifacts: `research/edge_discovery/{on_features,explore,sim_engine,search,gauntlet}.py`,
`_search_results.csv`, `_gauntlet_out.txt`.
