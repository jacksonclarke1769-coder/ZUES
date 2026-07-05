"""Conditional eval-pass forecaster — engine.

Answers the live question the certified pass rate can't: "given I am at $49,404.80 with $1,905
cushion and 19 days left, what is P(pass) / P(bust) / P(expire) and how many days to target?"

METHOD — block-bootstrap replay (NOT a new model):
  The certified 47.8% (cap-10 re-lock 2026-07-05) pass rate is a walk-forward: run the SAME Apex-EOD state machine over the
  machine's real per-day P&L stream (day_rows: realized + marked-trough) from every historical
  start.  This replays that IDENTICAL forward stream onto the CURRENT bankroll and a SHORTENED
  clock instead of a fresh $50k / 30-day start.  step_eval() mirrors tools_account_size_research
  .eval_run() exactly (proven by test_eval_forecast.test_step_matches_harness), and seeding it
  fresh reproduces 47.8/15.9/36.2 (test_calibration_reproduces_certified).

  It invents no distribution.  The only conditioned inputs are the seed balance/threshold (real,
  off the Apex panel) and days-left.  Positive= the day P&L stream is the certified one.

Distribution cache: reports/eval_day_pnl_50k_1200.json  (rebuild via tools_eval_forecast --rebuild).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date

CACHE_PATH = "reports/eval_day_pnl_50k_1200.json"

# Apex 50K EOD constants (must match tools_account_size_research.SPECS['50K'] + config EVAL).
START = 50_000.0
TRAIL = 2_500.0
TARGET = 3_000.0        # pass at START + TARGET = $53,000
LOCK_AT = START + 100.0  # threshold locks here once peak-trail reaches it
EXPIRE_DAYS = 30


@dataclass
class Spec:
    start: float = START
    trail: float = TRAIL
    target: float = TARGET
    lock_at: float = LOCK_AT


def load_distribution(cache_path: str = CACHE_PATH) -> list:
    """Return the certified day stream as [(date, real, trough), ...].  Raises if the cache is
    absent — the caller (tools_eval_forecast) tells the operator to run --rebuild."""
    with open(cache_path) as f:
        blob = json.load(f)
    out = []
    for r in blob["days"]:
        out.append((date.fromisoformat(r["date"]), float(r["real"]), float(r["trough"])))
    return out


def seed_state(balance: float, threshold: float, spec: Spec = Spec()):
    """Derive (peak, locked) consistent with a mid-eval (balance, threshold).

    threshold == start-trail  -> not ratcheted yet, peak = max(start, balance)
    threshold >= lock_at       -> locked (peak irrelevant)
    otherwise                  -> ratcheted, peak = threshold + trail
    """
    if threshold >= spec.lock_at - 1e-9:
        return max(spec.start, balance), True
    if threshold <= spec.start - spec.trail + 1e-9:
        return max(spec.start, balance), False
    return threshold + spec.trail, False


def step_eval(bal, thr, peak, locked, real, trough, elapsed, days_left, spec: Spec = Spec()):
    """Apply ONE eval day.  Mirrors tools_account_size_research.eval_run's loop body EXACTLY.

    Returns (verdict, days, bal, thr, peak, locked) where verdict is one of
    "PASS"/"BUST"/"EXPIRE"/None (None = continue).  `days` is set only on a terminal verdict.
    Order of checks is load-bearing and identical to eval_run.
    """
    if elapsed > days_left:
        return "EXPIRE", days_left, bal, thr, peak, locked
    if bal + min(0.0, trough) <= thr:
        return "BUST", elapsed, bal, thr, peak, locked
    bal += real
    peak = max(peak, bal)
    if not locked:
        thr = max(thr, peak - spec.trail)
        if peak - spec.trail >= spec.lock_at:
            thr = spec.lock_at
            locked = True
    if bal <= thr:
        return "BUST", elapsed, bal, thr, peak, locked
    if bal >= spec.start + spec.target:
        return "PASS", elapsed, bal, thr, peak, locked
    return None, 0, bal, thr, peak, locked


def replay(days: list, start_idx: int, balance: float, threshold: float,
           days_left: int, spec: Spec = Spec()):
    """Replay the real forward day-stream from start_idx onto (balance, threshold), capped at
    days_left calendar days.  Returns (verdict, days_to_terminal)."""
    peak, locked = seed_state(balance, threshold, spec)
    bal, thr = balance, threshold
    start_date = days[start_idx][0]
    for i in range(start_idx, len(days)):
        d, real, trough = days[i]
        elapsed = (d - start_date).days
        verdict, dd, bal, thr, peak, locked = step_eval(
            bal, thr, peak, locked, real, trough, elapsed, days_left, spec)
        if verdict is not None:
            return verdict, dd
    return "INCOMPLETE", None


def valid_starts(days: list, days_left: int) -> list:
    """Indices with at least days_left calendar days of forward history (same filter the
    certification uses, so the estimator is the honest conditional analog)."""
    out, seen = [], set()
    for i, (d, _, _) in enumerate(days):
        if d not in seen and (days[-1][0] - d).days >= days_left:
            seen.add(d)
            out.append(i)
    return out


def pace_verdict(fc: dict):
    """Shared verdict (CLI + dashboard) ordered by the DOMINANT failure mode.
    Returns (level, text) where level in {pass, tight, bust, marginal} for colouring."""
    p, b, x = fc.get("pass_pct"), fc.get("bust_pct"), fc.get("expire_pct")
    med = fc.get("median_days_to_pass")
    if p is None:
        return ("marginal", "insufficient history for this horizon")
    if b >= 35:
        return ("bust", f"BUST RISK LEADS ({b}%) — protect the cushion, don't force size to catch up")
    if x >= p and x >= b:
        return ("tight", f"TIME IS THE ENEMY — EXPIRE ({x}%) is the modal outcome"
                         + (f", passes finish in ~{med}d" if med else "")
                         + "; the lever is SIGNAL FLOW, not size")
    if p >= b and p >= x:
        return ("pass", f"PASS LEADS ({p}%)" + (f", median {med}d" if med else "")
                        + " — take every A signal")
    return ("marginal", f"MARGINAL — pass {p}% / bust {b}% / expire {x}%; supervise, favour survival")


def forecast(days: list, balance: float, threshold: float, days_left: int,
             spec: Spec = Spec()) -> dict:
    """Run the block-bootstrap replay over every valid start.  Returns pass/bust/expire pct,
    median days-to-pass, and n.  Deterministic (no RNG) — the estimator IS the full replay set."""
    starts = valid_starts(days, days_left)
    n = len(starts)
    if n == 0:
        return dict(n=0, pass_pct=None, bust_pct=None, expire_pct=None, median_days_to_pass=None)
    res = [replay(days, s, balance, threshold, days_left, spec) for s in starts]
    npass = sum(1 for v, _ in res if v == "PASS")
    nbust = sum(1 for v, _ in res if v == "BUST")
    nexp = sum(1 for v, _ in res if v == "EXPIRE")
    pass_days = sorted(dd for v, dd in res if v == "PASS")
    med = (pass_days[len(pass_days) // 2] if pass_days else None)
    return dict(
        n=n,
        pass_pct=round(100 * npass / n, 1),
        bust_pct=round(100 * nbust / n, 1),
        expire_pct=round(100 * nexp / n, 1),
        median_days_to_pass=med,
        cushion=round(balance - threshold, 2),
        to_target=round(spec.start + spec.target - balance, 2),
    )
