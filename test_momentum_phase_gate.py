"""Momentum phase/firm gate — momentum auto-enables ONLY where the ruleset rewards variance:
Apex EVAL (beat the clock) + MFFU/static FUNDED (no daily limit). It stays OFF where variance is punished:
MFFU/static EVAL (trailing-DD) + Apex FUNDED (the $1k daily-kill). Validated in reports/momentum_edge_upgrade.md."""
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


def test_apex_funded_off():
    ok, why = momentum_active_for_tier("Apex-50K")
    assert ok is False and "daily-kill" in why


def test_unknown_tier_off():
    ok, why = momentum_active_for_tier("nope")
    assert ok is False and "unknown" in why
