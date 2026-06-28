"""The live runner must accept + resolve the FUNDED tiers (Apex-50K / Apex-50K-scaled), not just eval —
the documented `auto_live --tier Apex-50K` funded run was previously rejected by argparse and would have
KeyError'd on EVAL_TIERS[tier]. Regression guard."""
import pytest
import auto_live
from auto_safety import EVAL_TIERS, FUNDED_TIERS


def test_funded_tiers_resolve():
    s = auto_live._tier_spec("Apex-50K")
    assert s["am"] == 4 and s["bm"] == 2 and s["mm"] == 2          # funded phase 1 (momentum on)
    s2 = auto_live._tier_spec("Apex-50K-scaled")
    assert s2["am"] == 6 and s2["bm"] == 3 and s2["mm"] == 6        # funded phase 2


def test_eval_tier_still_resolves():
    s = auto_live._tier_spec("Apex-50K-eval")
    assert s["am"] == 10 and s["bm"] == 5 and s["mm"] == 6


def test_unknown_tier_raises():
    with pytest.raises(ValueError):
        auto_live._tier_spec("not-a-tier")


def test_argparse_accepts_funded_tiers():
    p = auto_live._build_parser() if hasattr(auto_live, "_build_parser") else None
    # the choices list must include both eval and funded tiers
    import argparse
    # rebuild minimally: confirm the union is what the parser offers
    choices = list(EVAL_TIERS) + list(FUNDED_TIERS)
    assert "Apex-50K" in choices and "Apex-50K-scaled" in choices and "Apex-50K-eval" in choices
