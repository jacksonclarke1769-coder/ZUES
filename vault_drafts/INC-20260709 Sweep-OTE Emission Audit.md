# INC-20260709 — Sweep→Displacement/OTE Emission-Path Audit (MEASUREMENT ONLY)

**Verdict: LIVE-ACHIEVABLE EDGE = INTACT** (not bottlenecked, not near-breakeven). Opposite of Profile A (INC-20260707).
**Scope:** measurement only — no strategy/param change, no fix, no arming. LIVE HOLD remains ACTIVE.
**Artifacts (outside this repo, in the research tree):**
`~/trading-team/backtests/zeus-occ-optimize/reports/inc_sweep_emission_audit/00_RESULT.md` (+ `emission_audit_sweep.py`).

## Why it does NOT replicate Profile A
The sweep→OTE strategy is a **standalone backtest** (`backtests/zeus-occ-optimize/sweep_engine.py`), **not wired into `ProfileAEngine`/`model01`**. Profile A's surface-lag (trade surfaces to `tr` only after `_simulate` resolves exit, ~35min) has **no analogue** here — there is no live emission engine yet. The only live risk is the intrinsic confirmation→fill gap; the entry is a **resting OTE limit** (not market-on-surface), which does not go stale in the book.

## Numbers (single-vendor Databento, 10-min gate reused from `databento_emission_replay.py:188`, tz-aware both sides)
- **Gap** t_confirmed(=close of displacement bar d)→t_fill: median 5m, p90 12m, all fills ≤15m except 1 session-gap outlier. No-lookahead asserted (min gap 0.00m).
- **Partition (R-weighted):** FULL 789/PF1.248/51.3R → **LIVE-ACHIEVABLE 673/PF1.262/42.4R** · SUPPRESSED 116/PF1.178/8.9R (70W/46L = winner-heavy by count but LOW-PF).
- **Live-achievable re-cert:** IS 478/PF1.123 · **OOS 195/PF1.524** · WR IS57.9%→OOS62.1% (load-bearing OOS-stable WR SURVIVES). Per-yr 2021 1.40/2022 1.31/2023 0.89⚠/2024 1.02/2025 1.42/2026 1.73.
- **Three-column:** removing the suppressed tail nudges PF UP (1.248→1.262) and costs −17% R — the gate removes a low-PF mixed tail, NOT the winners (contrast Profile A 1.237→1.037).
- **Suppressed winners: RECOVERABLE** — all 70 have setup fully confirmed at bar d ≤ t_fill (asserted; 3 hand-traces in 00_RESULT.md). Emit-at-d-close would recover them if ever wired live (shared infra), but recovery is optional upside, not a rescue.
- **Decorrelation w/ Profile A:** sweep 474 fill-days vs PA 452; **only 198 shared (42%) → 276 sweep-only days.** Adds coverage on days A is idle → attacks the expire/frequency problem; value independent of solo PF.

## Follow-ups (NOT done — measurement task only)
Deploy target = static-DD / no-expiry firm at 1 NQ (Apex 30-day = frequency-starved, prior sim). Options: FTMO-const verification · DD-reduction overlay · Pine build + forward test. No arming.
