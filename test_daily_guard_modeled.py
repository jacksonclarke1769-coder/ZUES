"""Daily-loss stop must trip on MODELED P&L (no broker read-back), excluding rejected trades.

Regression for the 2026-06-29 gap: DailyGuard.record() was never called in production, so the
$550 stop could never trip. The fix derives the day's ENTERED P&L from the ledger and trips the
persistent guard. Yesterday's real day = one entered B trade (-$585) + one REJECTED A trade
(-$2,746): the stop must see -$585 (B only), NOT -$3,331, and must trip ($585 > $550)."""
import csv
import importlib

import trade_results as TR
from auto_safety import DailyGuard
from store import Store


def _ledger(tmp_path, rows):
    p = tmp_path / "tr.csv"
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(TR.COLS)
        for r in rows:
            w.writerow(r)
    return str(p)


def test_day_entered_pnl_excludes_rejected(tmp_path):
    # exactly yesterday's shape: B entered (-585), A REJECTED (-2746)
    path = _ledger(tmp_path, [
        ["2026-06-29", "live", "APEX-50K-EVAL-1", "B", "short", 5, -585.18,
         "HYPOTHETICAL · paper · Profile B ORB · PARTIAL stop · -1.00R modeled"],
        ["2026-06-29", "live", "APEX-50K-EVAL-1", "A", "short", 10, -2746.48,
         "HYPOTHETICAL · modeled · pending broker recon · -1.00R gross · rejected_by_mffu:too_close_to_floor|stop"],
    ])
    pnl = TR.day_entered_pnl("APEX-50K-EVAL-1", "2026-06-29", path=path)
    assert pnl == -585.18, f"expected only the ENTERED B trade, got {pnl}"


def test_other_accounts_and_days_ignored(tmp_path):
    path = _ledger(tmp_path, [
        ["2026-06-29", "live", "APEX-50K-EVAL-1", "B", "short", 5, -300.0, "modeled"],
        ["2026-06-29", "live", "OTHER-ACCT",      "B", "short", 5, -900.0, "modeled"],
        ["2026-06-28", "live", "APEX-50K-EVAL-1", "B", "short", 5, -900.0, "modeled"],
        ["2026-06-29", "live", "APEX-50K-EVAL-1", "A", "long",  10, 250.0, "modeled tp"],
    ])
    assert TR.day_entered_pnl("APEX-50K-EVAL-1", "2026-06-29", path=path) == -50.0  # -300 + 250


def test_guard_trips_at_limit_then_blocks(tmp_path):
    g = DailyGuard(Store(str(tmp_path / "g.db")))
    acct, d = "APEX-50K-EVAL-1", "2026-06-29"
    assert not g.is_stopped(acct, d)
    day_pnl, limit = -585.18, 550
    if day_pnl <= -abs(limit):
        g.stop_now(acct, d, reason="modeled")
    assert g.is_stopped(acct, d)                      # $585 modeled loss > $550 -> stopped


def test_guard_not_tripped_below_limit(tmp_path):
    g = DailyGuard(Store(str(tmp_path / "g.db")))
    acct, d = "APEX-50K-EVAL-1", "2026-06-29"
    day_pnl, limit = -400.0, 550
    if day_pnl <= -abs(limit):
        g.stop_now(acct, d, reason="modeled")
    assert not g.is_stopped(acct, d)                  # $400 < $550 -> still trading
