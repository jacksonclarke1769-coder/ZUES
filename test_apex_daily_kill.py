"""Apex daily-kill guard — flattens once before the $1k kill, halts the day, resets daily, restart-safe."""
import pytest
from apex_daily_kill import ApexDailyKill


def test_no_trip_above_threshold():
    g = ApexDailyKill(dll=1000)                     # salvage at -$850
    assert g.update("2026-06-29", -500) is False
    assert g.halted("2026-06-29") is False


def test_trips_once_at_salvage_threshold():
    g = ApexDailyKill(dll=1000, margin=0.85)
    assert g.update("2026-06-29", -849) is False    # just above -$850
    assert g.update("2026-06-29", -900) is True     # crosses -> FLATTEN
    assert g.halted("2026-06-29") is True
    assert g.update("2026-06-29", -1500) is False   # already tripped today -> no second flatten


def test_resets_next_day():
    g = ApexDailyKill(dll=1000)
    g.update("2026-06-29", -900)
    assert g.halted("2026-06-29") is True
    assert g.halted("2026-06-30") is False          # new day -> fresh
    assert g.update("2026-06-30", -200) is False


def test_scales_with_account_dll():
    g = ApexDailyKill(dll=2000)                      # 150K -> salvage at -$1,700
    assert g.update("2026-06-29", -1500) is False
    assert g.update("2026-06-29", -1750) is True


def test_update_never_raises_on_bad_input():
    g = ApexDailyKill(dll=1000)
    assert g.update("2026-06-29", "bad") is False    # swallowed


def test_built_from_apex_tier_configs():
    # the eval tier flattens TIGHT (~-$700) for max pass-rate; funded looser (~-$850)
    from auto_safety import EVAL_TIERS, FUNDED_TIERS
    ev = EVAL_TIERS["Apex-50K-eval"]; fd = FUNDED_TIERS["Apex-50K"]
    ge = ApexDailyKill(dll=ev["dll"], margin=ev["kill_margin"])
    gf = ApexDailyKill(dll=fd["dll"], margin=fd["kill_margin"])
    assert ge.kill_at == -700.0 and gf.kill_at == -850.0
    assert ge.update("2026-06-29", -699) is False and ge.update("2026-06-29", -701) is True


def test_snapshot_restore():
    g = ApexDailyKill(dll=1000)
    g.update("2026-06-29", -900)
    g2 = ApexDailyKill(dll=1000); g2.restore(g.snapshot())
    assert g2.halted("2026-06-29") is True           # restored as killed-out for that day
    assert g2.halted("2026-06-30") is False
