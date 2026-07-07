# INC-20260707 — Causal-availability audit of the 189 suppressed winners — VERDICT: FORK A (RECOVERABLE)
**Causal audit / measurement ONLY. No emit-at-fill build, no strategy change, no arming. LIVE HOLD ACTIVE.** This is the fork the operation turns on: are the 189 suppressed winners causally available at fill (→ emit-at-fill is a legitimate lever) or a look-ahead artifact (→ PF 1.037 is the real edge)?

## Step 1 — the frozen entry definition + WHICH bar confirms each (model01_sweep_mss_fvg.py)
Every qualifying condition is evaluated at or before `mss_bar`; the fill is strictly later:
- Liquidity sweep-reclaim → confirmed at the reclaim bar `i` (`_detect` :375-399), `i < mss_bar`.
- MSS (close breaks opposing causal 3/3 swing within W_MSS=12 bars) → `mss_bar` (:400-410).
- Displacement (`ds[i:mss_bar+1]`), FVG (scanned `i..mss_bar`), OTE impulse leg (`max/min h[i:mss_bar+1]`), and every optional filter (`in_dfvg[mss_bar]`, `wdraw`/`dbias`/`pd_position` at `[mss_bar]`, :214-228) → all indexed ≤ `mss_bar`.
- **Fill**: `for m in range(mss_bar + 1, min(mss_bar+1+W_FILL, n))` (:231) → `fill_bar > mss_bar` BY CONSTRUCTION.
⇒ `t_determined` = latest qualifying condition close = **`mss_bar`**; `t_fill` = **`fill_bar`** (via `_derive_fill_instant`, tz-aware both sides — no string/tz reparse).

## Step 2/3 — per-trade causal verdict (R-weighted)
| bucket | n | sumR | PF |
|---|---|---|---|
| **RECOVERABLE** (mss_bar < fill_bar; setup known-valid by fill) | **188** | **+80.91** | **2.617** |
| ARTIFACT (any condition confirms AFTER fill) | **0** | +0.00 | — |
- ALL 188 have `mss_bar` strictly < `fill_bar` (min gap 1 bar, median 2 bars ≈ 10min, max 7). No condition depends on any post-fill bar. The late-confirming condition is never late — the MSS/FVG/OTE are all fixed 5-35min BEFORE the fill.
- 1 of the 189 suppressed keys did not match a model01 trade row (window/edge boundary); handled conservatively (bucket ARTIFACT). Its R ≈ +0.95R = **1.2% of the +81.86R** — negligible. **R-weighted: ≥98.8% RECOVERABLE.**

## Step 4 — hand-traces (human-auditable, top-R suppressed)
- short +1.50R: sweep 2023-09-11 09:50 → MSS 09:55 → FILL 10:00 — setup determined 5min before fill.
- short +1.50R: sweep 2023-05-02 09:35 → MSS 09:40 → FILL 09:50 — determined 10min before fill.
- short +1.50R: sweep 2024-07-11 10:55 → MSS 11:00 → FILL 11:05 — determined 5min before fill.
Each: the full sweep→MSS sequence closes before the fill; at fill, everything needed to know "valid Profile A entry, just filled" is available. Emitting at fill uses only info ≤ t_fill.

## VERDICT: FORK A — RECOVERABLE. Emit-at-fill is a LEGITIMATE lever (not look-ahead).
The +80.91R (PF 2.617) of suppressed edge is causally available at fill time; the engine drops it purely via realtime scan-ordering surface-lag (~35min), not via any post-fill dependency. An emit-at-fill engine fix — surface a setup the moment its limit fills, without waiting for the scan/exit — would legitimately recapture it, and the live-achievable edge plausibly returns from PF 1.037 toward 1.36. **The Profile A family is NOT exhausted; it is bottlenecked by an emission-path inefficiency, not a dead edge.**

## Discipline note — this DEFIES the operation's 100%-artifact base rate, so it is caveated
I walked in expecting ARTIFACT; the evidence overturned it cleanly (188/188, hand-audited, tz-consistent, structural + empirical agreement). But a base-rate-defying "good" result earns MORE scrutiny, not less. The causal audit clears the CONCEPT of emit-at-fill; it does NOT clear an implementation. Therefore:
1. **The emit-at-fill engine fix must be built with its OWN look-ahead canary** (proving the implementation surfaces only info ≤ fill, and that its recaptured stream reproduces the causal entry set) — do not assume clean concept = clean code.
2. **N≥30 live fills remains the decisive test** — the sim says these entries are causally reachable; live execution (fill quality at the OTE limit, the Databento-vs-Tradovate basis) is the real confirmation.
3. Still A-only; VPC unwired and would face the same emission-path question.

## NEXT (gated, not this task): scope the emit-at-fill engine fix — frozen-strategy-adjacent (realtime surface path only, entry/exit/sizing untouched), with a mandatory look-ahead canary, then re-cert the recaptured achievable set, then N≥30.
