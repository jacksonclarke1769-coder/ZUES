"""Dashboard P&L must EXCLUDE rejected/never-entered rows so a loss that never happened can't
inflate the headline. Regression for 2026-06-29: the rejected Profile A −$2,746 (too_close_to_floor)
sat in the ledger as HYPOTHETICAL and inflated the day to −$3,331 when real exposure was −$585 (B)."""
import csv

import trade_results as TR


def _ledger(tmp_path):
    p = tmp_path / "tr.csv"
    with open(p, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(TR.COLS)
        w.writerow(["2026-06-29", "live", "APEX-50K-EVAL-1", "B", "short", 5, -585.18,
                    "HYPOTHETICAL · paper · Profile B ORB · PARTIAL stop · -1.00R modeled"])
        w.writerow(["2026-06-29", "live", "APEX-50K-EVAL-1", "A", "short", 10, -2746.48,
                    "HYPOTHETICAL · modeled · pending broker recon · rejected_by_mffu:too_close_to_floor|stop"])
    return str(p)


def test_is_rejected_flags_only_never_entered():
    assert TR.is_rejected("rejected_by_mffu:too_close_to_floor")
    assert TR.is_rejected("LIVE BLOCKED: exit model")
    assert not TR.is_rejected("HYPOTHETICAL · Profile B ORB · -1.00R modeled")
    assert not TR.is_rejected("fill-backed · TP hit")


def test_by_day_excludes_rejected(tmp_path):
    day = TR.by_day(path=_ledger(tmp_path), live_only=True)["2026-06-29"]
    assert day["hypothetical_pnl"] == -585.18    # B only — NOT -3331.66
    assert day["pnl"] == 0.0                      # nothing fill-backed yet
    assert day["trades"] == 1                     # the rejected A is not a trade


def test_live_trades_excludes_rejected(tmp_path):
    rows = TR.live_trades(path=_ledger(tmp_path), account="APEX-50K-EVAL-1")
    assert len(rows) == 1 and rows[0]["strategy"] == "B"
    assert sum(r["pnl"] for r in rows) == -585.18
