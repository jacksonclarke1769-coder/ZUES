"""Momentum phase/firm gate — momentum auto-enables where the ruleset rewards variance:
Apex EVAL + Apex FUNDED (validated 2026-06-27: momentum HELPS funded under the EOD rule, +54% value) +
MFFU/static FUNDED. It stays OFF on MFFU/static EVAL (trailing-DD punishes variance)."""
from auto_safety import momentum_active_for_tier


def test_mffu_eval_off():
    for t in ("50K-conservative", "50K-balanced"):          # MFFU eval configs
        ok, why = momentum_active_for_tier(t)
        assert ok is False and "trailing" in why


def test_mffu_funded_on():
    for t in ("50K", "150K"):                                # MFFU funded configs
        ok, why = momentum_active_for_tier(t)
        assert ok is True and "income" in why


def test_apex_eval_on():
    ok, why = momentum_active_for_tier("Apex-50K-eval")
    assert ok is True and "clock" in why


def test_apex_funded_on():
    for t in ("Apex-50K", "Apex-50K-scaled"):                # both phases: momentum ON (validated 2026-06-27)
        ok, why = momentum_active_for_tier(t)
        assert ok is True and "VALIDATED" in why


def test_unknown_tier_off():
    ok, why = momentum_active_for_tier("nope")
    assert ok is False and "unknown" in why
