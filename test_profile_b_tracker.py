"""Profile B paper-P&L tracker — limit fill on retest, stop-first exit resolution,
cancel on no-fill, and recording to the calendar (as hypothetical paper P&L)."""
import trade_results as TR
from profile_b_tracker import ProfileBPaperTracker

SIG = dict(side="long", entry=100.0, stop=98.0, target=103.0)   # risk 2, target +1.5R


def _trk(tmp_path, qty=1):
    return ProfileBPaperTracker(store=None, account="MFFU-50K-1", mode="paper",
                                dpp=2.0, path=str(tmp_path / "tr.csv")), str(tmp_path / "tr.csv")


def test_fill_then_target_records_win(tmp_path):
    t, p = _trk(tmp_path)
    t.on_signal(SIG, qty=1, bar_i=0, ts="2026-06-22 09:45")
    t.on_bar(1, "2026-06-22 09:50", 100, 101, 99, 100)          # retest 100 -> filled
    t.on_bar(2, "2026-06-22 09:55", 101, 104, 100, 103)         # hits target 103
    assert t.closed == 1
    row = t.recorded[0]
    # gross 3pt, net 3-0.75=2.25, $ = 2.25 * 2 * 1
    assert round(row["pnl"], 2) == 4.5
    day = TR.by_day(p)["2026-06-22"]
    assert day["pnl"] == 0.0 and day["hypothetical_pnl"] == 4.5  # paper -> hypothetical


def test_fill_then_stop_records_loss(tmp_path):
    t, p = _trk(tmp_path)
    t.on_signal(SIG, qty=1, bar_i=0, ts="2026-06-22 09:45")
    t.on_bar(1, "2026-06-22 09:50", 100, 101, 99, 100)          # filled
    t.on_bar(2, "2026-06-22 09:55", 100, 100, 97, 98)           # hits stop 98 (stop-first)
    assert t.closed == 1
    assert round(t.recorded[0]["pnl"], 2) == -5.5               # (-2-0.75)*2*1


def test_no_fill_cancels(tmp_path):
    t, p = _trk(tmp_path)
    t.on_signal(SIG, qty=1, bar_i=0, ts="2026-06-22 09:45")
    for i in range(1, 9):                                        # never retests 100 (stays 101-105)
        t.on_bar(i, f"2026-06-22 10:{i:02d}", 103, 105, 101, 104)
    assert t.closed == 0 and t.recorded == []                   # window expired -> no trade


def test_stop_first_when_both_hit_same_bar(tmp_path):
    t, p = _trk(tmp_path)
    t.on_signal(SIG, qty=1, bar_i=0, ts="2026-06-22 09:45")
    t.on_bar(1, "2026-06-22 09:50", 100, 101, 99, 100)          # filled
    t.on_bar(2, "2026-06-22 09:55", 100, 104, 97, 100)          # bar spans stop AND target
    assert round(t.recorded[0]["pnl"], 2) == -5.5               # stop wins (conservative)


def test_qty_scales_pnl(tmp_path):
    t, p = _trk(tmp_path)
    t.on_signal(SIG, qty=2, bar_i=0, ts="2026-06-22 09:45")     # 2 MNQ
    t.on_bar(1, "2026-06-22 09:50", 100, 101, 99, 100)
    t.on_bar(2, "2026-06-22 09:55", 101, 104, 100, 103)
    assert round(t.recorded[0]["pnl"], 2) == 9.0                # 4.5 * 2 contracts


def test_eod_close_resolves(tmp_path):
    t, p = _trk(tmp_path)
    t.on_signal(SIG, qty=1, bar_i=0, ts="2026-06-22 09:45")
    t.on_bar(1, "2026-06-22 09:50", 100, 101, 99, 100)          # filled
    t.on_bar(2, "2026-06-22 16:05", 100, 102, 99, 101)          # post-RTH -> EOD close at 101
    assert t.closed == 1 and t.recorded[0]["pnl"] != 0
