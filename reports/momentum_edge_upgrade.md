# Profile Momentum — edge upgrade (2026-06-27)

**Goal:** raise the continuation model's PF/Sharpe for MFFU, IS/OOS-validated, without breaking the proven years.
**Result:** PF 1.67 → **1.83** (OOS), Sharpe 1.75 → **1.91**, maxDD 677 → **641pt**, every proven year up.
Two robust single-lever changes. Real Databento 5m NQ, executor-faithful next-bar-open fills, costs 0.375pt/side.

## The change
| Param | Was (shipped) | Now |
|---|---|---|
| `confirm_bars` | 3 | **4** |
| `last_entry_slot` | 65 (~15:00 ET) | **72 (~15:30 ET)** |
| k, ND, trend_len, skip | 1.0, 14, 50, 3 | unchanged |

## Before → after (executor-faithful, IS/OOS + per-year)
| Config | FULL PF | OOS PF | Sharpe | maxDD | 2022 / 23 / 24 / 25 / 26 |
|---|---|---|---|---|---|
| Shipped (confirm 3, 15:00) | 1.67 | 1.66 | 1.75 | 677pt | 1.40 / 1.52 / 2.40 / 1.98 / 1.02 |
| **Upgraded (confirm 4, 15:30)** | **1.80** | **1.83** | **1.91** | **641pt** | **1.56 / 1.60 / 2.43 / 2.10 / 1.35** |

+$1,800/MNQ over the window; soft 2026 lifts 1.02 → 1.35 as a *side effect* of two robust levers, NOT a
2026-targeted gate (every prior 2026-targeted gate broke the proven years — see [[project_nq_orb_apex]]).

## Why these two (mechanism + discipline)
- **confirm 3 → 4:** the losers are <30-min whipsaws; a 4th confirmation bar removes more of them at the cost
  of a marginally later entry. Not a fragile spike — confirm 3/4/5 are all fine, 4 is the peak.
- **last-entry 15:00 → 15:30:** the old cutoff discarded profitable late-afternoon continuation entries. It's
  a robust **plateau**, not a spike — every cutoff slot 66–76 (15:00–15:50) scores OOS 1.67–1.76. DD actually
  *drops* because the late trades smooth the curve.
- **Rejected (overfit / DD-breaking):** k≠1.0, ND≠14, trend_len≠50, confirm=2/5, skip≠3, VWAP=on. Two
  refinement loops only (single-lever sweep → plateau/combo validation); no further tuning.

## The MFFU realizability crux — EOD timing
The upgraded edge **requires holding past 14:30 ET.** Re-running the best config force-flattened at each time:

| Momentum flattened at… | PF | Sharpe | Proven years |
|---|---|---|---|
| 14:30 (shared A-guardian) | 1.61 | 1.61 | ✗ breaks (2023→1.27, 2026→0.93) |
| 15:30 / hold-to-close | 1.83 | 1.91 | ✓ all strong |

**Decision (operator):** keep momentum on the shared MFFU account but defer the EOD **backstop** to 15:30 when
the momentum lane is on. Safe because A is flat by 14:30 via its own model and B closes via its own
bracket / max-hold(2h) / RTH-end — a 15:30 backstop is *more* faithful to B's backtest, not less. KILL
flattens (daily-stop / operator / lockout) still fire instantly.

## Implementation + validation
- `profile_momentum_engine.py` — defaults confirm_bars=4, last_entry_slot=72 (docstring updated).
- `verify_momentum_parity.py` — backtest reference updated to confirm 4 / slot≤72; **EXACT parity 0/94,344**.
- `auto_live.py` — when `--profile-momentum` is on, the FlattenGuardian uses a 15:30 Scheduler (half-day
  12:45 unchanged); guardian banner reflects it.
- Tests: `test_momentum_guardian.py` (6) + existing momentum suite green; **full suite 543 passed**.
- Research harnesses: `backtests/nq_momentum_improve.py` (single-lever sweep), `nq_momentum_improve2.py`
  (plateau + combos + EOD-timing). RESEARCH ONLY — engine is the shipped artifact.

## Where it pays — phase/firm gate (momentum trades VARIANCE for income)
Validated on the real combined stacks. Momentum auto-enables ONLY where the ruleset rewards variance:

| Firm · phase | Momentum | Evidence |
|---|---|---|
| **MFFU funded** | ✅ ON | A+B $1,502/mo → **A+B+M $2,001–2,125/mo** (+33–41%), Sharpe 3.11→3.29 |
| MFFU eval | ❌ OFF | pass 83% → 78–82% (wider DD trips the trailing drawdown) |
| **Apex eval** | ✅ ON | pass 69% → **81%** (extra shots beat the 30-day clock; −$700 guard caps the day) |
| Apex funded | ❌ OFF | A2/B1 worst −$948 (0 kill-days) → +1 MNQ → −$1,225 (**1 kill-day = bust**). Needs its own account. |

Implemented as `auto_safety.momentum_active_for_tier(tier)`: the `--profile-momentum` flag *requests* the
lane; the tier (firm + eval/funded) decides if it **arms**. The 15:30 guardian defers only when momentum
actually arms. Tests: `test_momentum_phase_gate.py` (5). MFFU rule = funded-only; Apex eval is the exception.

> Harness note: the first MFFU pass showed momentum adding only ~$154 — a column-mismatch bug
> (`entry_min`/`exit_min`) silently dropped every momentum trade in the concat. Fixed in
> `backtests/nq_momentum_mffu_apex.py`; corrected contribution is +$36k/5yr at 2 MNQ.

## Still in shadow
Momentum remains shadow-by-default in live (no `momentum-approved.flag`). Next: observe the upgraded model
in shadow (now auditable via the ARGUS-M decision log), confirm shadow-vs-backtest behavior, then flag live.
Because MFFU is currently in its EVAL config (50K-balanced), the gate keeps momentum OFF until it's funded.
