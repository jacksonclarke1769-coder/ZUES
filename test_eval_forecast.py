"""Tests for the conditional eval-pass forecaster.

The load-bearing test is test_step_matches_harness: my step_eval/replay must be byte-for-byte
equivalent to tools_account_size_research.eval_run, because that is what makes the forecast a
faithful conditional of the certified 47.8/15.9 (cap-10 re-lock 2026-07-05) — not a new, uncertified model.
"""
import os
import random
from datetime import date, timedelta

import pytest

import eval_forecast as EF

HAS_CACHE = os.path.exists(EF.CACHE_PATH)


# ---------------------------------------------------------------- fidelity vs the harness

def _synthetic_days(seq, base=date(2024, 1, 1)):
    """Turn a list of (real, trough) into a day stream with one calendar day per entry."""
    return [(base + timedelta(days=i), float(r), float(tr)) for i, (r, tr) in enumerate(seq)]


def _harness_eval_run(days, s0, spec):
    """Re-implementation-free reference: call the REAL eval_run from the certification harness."""
    import tools_account_size_research as H
    hspec = dict(start=spec.start, trail=spec.trail, target=spec.target)
    # eval_run needs tz-aware normalized timestamps for (d - t0).days; build them.
    import pandas as pd
    hd = [(pd.Timestamp(d).tz_localize("America/New_York"), r, tr) for d, r, tr in days]
    return H.eval_run(hd, s0, hspec)


def test_step_matches_harness():
    """replay() seeded FRESH must equal eval_run() on the same day sequence, for many randoms."""
    spec = EF.Spec()
    rng = random.Random(42)
    for _ in range(300):
        seq = [(rng.uniform(-1500, 2000), -abs(rng.uniform(0, 1600))) for _ in range(rng.randint(3, 40))]
        days = _synthetic_days(seq)
        s0 = rng.randint(0, len(days) - 1)
        # fresh seed = start balance, start-trail threshold, full 30-day clock -> mirrors eval_run
        mine = EF.replay(days, s0, spec.start, spec.start - spec.trail, EF.EXPIRE_DAYS, spec)
        ref = _harness_eval_run(days, s0, spec)
        # verdict must match; INCOMPLETE maps through identically
        assert mine[0] == ref[0], f"verdict mismatch {mine} vs {ref} at s0={s0}"
        if ref[0] in ("PASS", "BUST"):
            assert mine[1] == ref[1], f"day mismatch {mine} vs {ref}"


# ---------------------------------------------------------------- seed_state

def test_seed_state_fresh_unlocked():
    peak, locked = EF.seed_state(50_000, 47_500)
    assert peak == 50_000 and locked is False


def test_seed_state_ratcheted():
    # floor at 49,000 => peak was 51,500, not yet locked
    peak, locked = EF.seed_state(50_800, 49_000)
    assert peak == pytest.approx(51_500) and locked is False


def test_seed_state_locked():
    peak, locked = EF.seed_state(52_000, 50_100)
    assert locked is True


# ---------------------------------------------------------------- degenerate cases

def test_already_at_target_all_pass():
    days = _synthetic_days([(0, 0)] * 40)
    # balance already >= start+target: first non-losing day resolves PASS
    fc = EF.forecast(days, EF.START + EF.TARGET, EF.START - EF.TRAIL, 30)
    assert fc["pass_pct"] == 100.0


def test_at_floor_all_bust():
    days = _synthetic_days([(0, -1)] * 40)  # any marked loss trips the floor
    fc = EF.forecast(days, 47_500.0, 47_500.0, 30)
    assert fc["bust_pct"] == 100.0


def test_all_winning_days_pass_fast():
    days = _synthetic_days([(800, -50)] * 40)
    fc = EF.forecast(days, EF.START, EF.START - EF.TRAIL, 30)
    assert fc["pass_pct"] == 100.0
    assert fc["median_days_to_pass"] <= 5


def test_all_losing_days_bust():
    days = _synthetic_days([(-600, -700)] * 40)
    fc = EF.forecast(days, EF.START, EF.START - EF.TRAIL, 30)
    assert fc["bust_pct"] == 100.0


# ---------------------------------------------------------------- monotonicity

def _mixed_days(n=120, seed=7):
    rng = random.Random(seed)
    return _synthetic_days([(rng.gauss(300, 1200), -abs(rng.gauss(400, 500))) for _ in range(n)])


def test_longer_clock_never_raises_expire():
    """Per-path invariant on a FIXED start set: extending the clock can only convert EXPIREs into
    terminal PASS/BUST, never create them. (P(pass) itself is NOT monotonic in days-left — more
    time also means more bust exposure, and each horizon selects a different valid-start set, which
    is why we hold the start set fixed here.)"""
    days = _mixed_days(n=200)
    starts = EF.valid_starts(days, 25)          # valid at the longer horizon
    def expire_count(dl):
        return sum(1 for s in starts if EF.replay(days, s, 49_400, 47_500, dl)[0] == "EXPIRE")
    assert expire_count(25) <= expire_count(10)


def test_more_cushion_never_raises_bust():
    days = _mixed_days()
    b_thin = EF.forecast(days, 49_400, 48_500, 20)["bust_pct"]   # cushion 900
    b_fat = EF.forecast(days, 49_400, 46_500, 20)["bust_pct"]    # cushion 2900
    assert b_fat <= b_thin


def test_forecast_is_deterministic():
    days = _mixed_days()
    a = EF.forecast(days, 49_400, 47_500, 19)
    b = EF.forecast(days, 49_400, 47_500, 19)
    assert a == b


# ---------------------------------------------------------------- calibration (needs the real cache)

@pytest.mark.skipif(not HAS_CACHE, reason="certified day cache absent (run --rebuild)")
def test_calibration_reproduces_certified():
    """Seeded FRESH (start balance, start-trail floor, 30 days), the forecast must reproduce the
    locked 47.8/15.9/36.2 (cap-10 re-lock 2026-07-05) within rounding — proof it's the certified
    machine, conditioned."""
    days = EF.load_distribution()
    fc = EF.forecast(days, EF.START, EF.START - EF.TRAIL, EF.EXPIRE_DAYS)
    assert fc["pass_pct"] == pytest.approx(47.8, abs=0.3)
    assert fc["bust_pct"] == pytest.approx(15.9, abs=0.3)
    assert fc["expire_pct"] == pytest.approx(36.2, abs=0.3)
