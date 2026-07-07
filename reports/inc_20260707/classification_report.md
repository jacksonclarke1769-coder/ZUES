# INC-20260707 — Classification of the 23 missing trades (partition + quantification)
**Read-only analysis. No gate change, no re-cert, no arming. LIVE HOLD ACTIVE.** Measurement: analysis_inc0707_missing.py (6,453-poll instrumented replay, 2025-06-01..2025-12-01) + raw table reports/inc_20260707/missing_classification_raw.csv.

## Step 1/2 — THE PARTITION (core deliverable)
**0 RECOVERABLE / 23 IRREDUCIBLE.** (per the honest rule, ambiguous → irreducible.)

Why: a trade is dropped when its true fill instant is >10min before the poll first surfaces it in `tr.tail(3)`. Measured staleness of the 23:
- min 15m · p25 30m · **median 35m** · p75 45m · max 45m
- **exactly 1** trade in the 10–15min "one-poll-late" zone (and 15min is already OUTSIDE the 10min window); **20 of 23 are >20min.**
- corr(staleness, hold_time) = **0.07** → NOT hold-time-driven (refutes the surface-at-exit hypothesis); mean staleness 35m vs mean hold 128m.

**Mechanism:** the ~35min delay is intrinsic to when `model01.run(realtime=True)` makes a *completed* Profile A setup visible in `tr.tail(3)` — a function of the engine's realtime surface/reservation logic, NOT of poll frequency (5min granularity) and NOT of hold time. **A poll-cadence change recovers ZERO of the 23.** Resolution 1 ("tighten the poll to recover trades") is therefore a non-option: there is nothing poll-recoverable to recover.

To trade any of the 23, the engine would have to *surface them at fill time* (a deeper realtime-emit change, frozen-strategy-adjacent) AND it would have to be proven that live could actually fill them at knowable-time prices — a separate, hard, unproven question. Not a cadence tweak; out of scope here.

## Step 3 — Quantification
**Backtest-scored R (trustworthy — the model's own scoring):**
| set | n | totR (bt) | PF | WR |
|---|---|---|---|---|
| [1] 48 live-achievable (matched) | 48 | **+19.39** | 2.655 | 45.8% |
| [2] 48 + RECOVERABLE (recoverable=0 → == [1]) | 48 | +19.39 | 2.655 | 45.8% |
| [3] ALL 71 at backtest price — **FICTIONAL / NOT-ACHIEVABLE** | 71 | +26.98 | 2.326 | 49.3% |
| the 23 irreducible (backtest-scored) | 23 | +7.60 | 1.879 | — |

Reading: the old certification implied 71 trades (+26.98R); **live can only reach the 48 (+19.39R). The +7.6R the 23 "add" is fictional — trades live cannot enter.** Distributions [1] and [2] are identical because the recoverable bucket is empty.

**1m-TRUTH R — NOT REPORTED (data-quality hold):** the analysis script's `r_1mtruth` column is UNRELIABLE — it scored the 48 matched trades at PF 0.05 / 3% WR with 16/48 non-fills, flatly inconsistent with certified Profile A (PF 1.237). That is a broken `walk_1m` integration in the ad-hoc analysis script, not a real result; reporting it would be false-confidence. **The honest 1m-truth distribution of the 48 must be produced by the certified pipeline (the re-cert follow-up), not this script.** This does NOT affect the partition (which is pure timing arithmetic) or the resolution (0 recoverable regardless of R).

## Recommendation (data-grounded)
1. **Recover nothing.** 0 of the 23 are poll-cadence-recoverable; the resolution-1 framing does not apply.
2. **Re-certify on the 48 live-achievable set** (resolution 2) — the honest certified trade set is exactly what the live engine emits. The 23 irreducible are **excluded, not chased**; forcing them would book fills live cannot achieve.
3. The deeper "why 35min surface delay / could an emit-on-fill engine change legitimately recover any of them" is a SEPARATE investigation, gated behind proving live-fillability — do not conflate with the re-cert.

Follow-ups (gated on this partition, NOT started here): (a) the re-cert on the 48 via the certified 1m-truth pipeline; (b) fix the analysis script's walk_1m or discard it; (c) optional engine-surface-timing investigation. LIVE HOLD ACTIVE.

## Addendum — full per-trade detail + refined mechanism (from the instrumented replay)
For all 23, `first_surface_poll == first_tail3_poll` exactly — a trade enters `tr` already inside the last-3-rows window `latest_signal()` inspects, so tail(3)-clustering is RULED OUT (0 cases), as is buffer-edge non-surfacing (0). The single distinguishing fact: the row simply does not exist in `tr` yet at fill time — it appears 15–45 min (3–9 bars) later, already past the 10-min gate, and staleness only grows once the key is fixed, so that first appearance is the only chance it gets.

**Leading mechanism hypothesis (evidence-consistent, NOT certified — for the follow-up):** `model01.run(realtime=True)`'s sequential no-overlap scan (`i = exit_i + 1`) combined with the pending-setup reservation `break`s whenever an *earlier, still-unresolved* setup's MSS/fill window (up to W_MSS/W_FILL = 12 bars = 60 min each) hasn't had enough buffer bars to resolve — blocking the scan from reaching a later, already-fillable trade until the earlier window elapses. That would produce exactly this fixed 3–9-bar detection lag, uncorrelated with the trade's own hold time. Confirming it needs engine tracing (out of scope for classification).

**r_1mtruth reconfirmed unreliable:** the raw table's 1m-truth column shows the 23 missing at near-uniform −1.0 (all stop-outs) AND the 48 matched at PF 0.05 / 3% WR / 16 non-fills — two independent implausibilities vs certified Profile A (PF 1.237). The walk_1m integration in the analysis script is misconfigured; the honest 1m-truth distribution is deferred to the certified re-cert pipeline. Full 23-row staleness/hold/R table: reports/inc_20260707/missing_classification_raw.csv.
