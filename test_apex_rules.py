"""Tests for the Apex trailing-threshold model (funded_rules) — pure, no network/orders."""
import funded_rules as FR


def acct(size="50K"):
    return FR.ApexAcct(FR.APEX_ACCOUNTS[size])


def test_initial_threshold():
    a = acct("50K")
    assert a.threshold == 47_500          # start 50,000 - trailing 2,500
    assert not a.breached and not a.locked


def test_trailing_ratchets_on_unrealized_high():
    a = acct("50K")
    a.mark(51_000)                         # equity peak 51,000
    assert a.peak == 51_000
    assert a.threshold == 48_500           # 51,000 - 2,500, not yet locked
    assert not a.locked


def test_threshold_locks_at_start_plus_100():
    a = acct("50K")
    a.mark(52_600)                         # start + trailing + 100 = lock point
    assert a.locked
    assert a.threshold == 50_100           # start + 100
    a.mark(60_000)                         # further highs do NOT move a locked threshold
    assert a.threshold == 50_100


def test_breach_when_equity_touches_threshold():
    a = acct("50K")
    a.mark(47_500)                         # equity hits the initial threshold
    assert a.breached


def test_apex_giveback_killer():
    # The Apex-specific risk: a trade that runs +$3,000 then closes -$1,000 BREACHES a 50K,
    # because the floor ratcheted to the +$100 lock (50,100) and the give-back to 49,000 is below it
    # — even though realized loss is only $1k and the starting cushion was $2.5k.
    a = acct("50K")
    a.apply_trade(pnl=-1_000, mfe=3_000, mae=-1_000)
    assert a.locked and a.breached
    assert a.threshold == 50_100


def test_small_giveback_survives_when_not_locked():
    a = acct("50K")
    a.apply_trade(pnl=-1_000, mfe=1_000, mae=-1_000)   # peak 51,000 -> floor 48,500; settle 49,000
    assert not a.breached
    assert a.threshold == 48_500 and a.bal == 49_000


def test_pass_target():
    a = acct("50K")
    a.apply_trade(pnl=3_000, mfe=3_000, mae=0.0)       # +$3,000 = target
    assert a.passed and not a.breached


def test_consistency_rule():
    assert FR.consistency_ok([100, 100, 100, 100]) is True       # 25% max day
    assert FR.consistency_ok([500, 100, 100, 100]) is False      # ~62% in one day
    assert FR.consistency_ok([-50, -50]) is None                 # no profit -> n/a
