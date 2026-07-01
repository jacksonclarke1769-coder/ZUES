"""Daily stop authored in POINTS × CONTRACTS (Option A): $550 = 275 × 1 × $2 — derived, not a magic
number. Downstream $ is byte-identical to the old literal 550 (guard behavior unchanged)."""
import config_defaults as CD
import auto_safety as AS


def test_daily_stop_dollars_derivation():
    assert CD.daily_stop_dollars(275, 1, 2.0) == 550
    assert CD.daily_stop_dollars() == 550                          # defaults: 275 × 1 × $2
    assert (CD.DAILY_STOP_POINTS, CD.DAILY_STOP_CONTRACTS, CD.POINT_VALUE_MNQ) == (275, 1, 2.0)


def test_apex_tiers_use_the_derived_stop():
    assert AS.EVAL_TIERS["Apex-50K-eval"]["daily_stop"] == 550
    assert AS.FUNDED_TIERS["Apex-50K"]["daily_stop"] == 550
    assert AS.FUNDED_TIERS["Apex-50K-scaled"]["daily_stop"] == 550
    # it's the DERIVED value, not a hand-typed literal
    assert AS.APEX_DAILY_STOP == CD.DAILY_STOP_POINTS * CD.DAILY_STOP_CONTRACTS * CD.POINT_VALUE_MNQ


def test_point_budget_scales_dollars():
    assert CD.daily_stop_dollars(250, 1) == 500                    # tighten the budget -> $500
    assert CD.daily_stop_dollars(100, 5) == 1000                   # 100 pts × 5 contracts
    assert isinstance(CD.daily_stop_dollars(), int)               # whole dollars stay int (clean display)
