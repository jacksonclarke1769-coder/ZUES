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


# ---- PARTIAL_1R (50% @ +1R, 50% @ 1.5R target, shared stop) ----
# SIG: entry 100, stop 98 (risk 2 = -1R), tp1 102 (+1R), target 103 (+1.5R).

def test_partial_win_banks_1R_then_target(tmp_path):
    t, p = _trk(tmp_path)
    t.on_signal(SIG, qty=2, bar_i=0, ts="2026-06-22 09:45", partial=True)
    t.on_bar(1, "2026-06-22 09:50", 100, 101, 99, 100)          # filled at 100
    t.on_bar(2, "2026-06-22 09:55", 101, 104, 100, 103)         # hits tp1 102 AND target 103
    assert t.closed == 1
    # blended gross = 0.5*(102-100) + 0.5*(103-100) = 2.5pt; net 2.5-0.75=1.75; $ = 1.75*2*2
    assert round(t.recorded[0]["pnl"], 2) == 7.0
    assert "PARTIAL 1R+target" in t.recorded[0]["note"]

def test_partial_giveback_banks_1R_then_stop(tmp_path):
    t, p = _trk(tmp_path)
    t.on_signal(SIG, qty=2, bar_i=0, ts="2026-06-22 09:45", partial=True)
    t.on_bar(1, "2026-06-22 09:50", 100, 101, 99, 100)          # filled
    t.on_bar(2, "2026-06-22 09:55", 100, 102.5, 100, 102)       # banks 50% @ tp1 102 (no stop/target)
    assert t.open[0]["remaining"] == 0.5 and t.open[0]["realized_pts"] == 1.0
    t.on_bar(3, "2026-06-22 10:00", 101, 101, 97, 98)           # remaining 50% stops at 98
    # blended gross = 0.5*(+2) + 0.5*(-2) = 0pt; net -0.75; $ = -0.75*2*2 = -3.0  (vs single -1R = -11.0)
    assert t.closed == 1 and round(t.recorded[0]["pnl"], 2) == -3.0
    assert "PARTIAL 1R+stop" in t.recorded[0]["note"]

def test_partial_full_loss_when_never_reaches_1R(tmp_path):
    t, p = _trk(tmp_path)
    t.on_signal(SIG, qty=2, bar_i=0, ts="2026-06-22 09:45", partial=True)
    t.on_bar(1, "2026-06-22 09:50", 100, 101, 99, 100)          # filled
    t.on_bar(2, "2026-06-22 09:55", 100, 100, 97, 98)           # stops before reaching +1R
    # no partial banked -> full -1R, identical to single bracket: (-2-0.75)*2*2 = -11.0
    assert round(t.recorded[0]["pnl"], 2) == -11.0

def test_partial_requires_qty_2(tmp_path):
    t, p = _trk(tmp_path)
    t.on_signal(SIG, qty=1, bar_i=0, ts="2026-06-22 09:45", partial=True)   # qty=1 -> no partial
    assert t.open[0]["partial"] is False
    t.on_bar(1, "2026-06-22 09:50", 100, 101, 99, 100)
    t.on_bar(2, "2026-06-22 09:55", 101, 104, 100, 103)         # single win +1.5R
    assert round(t.recorded[0]["pnl"], 2) == 4.5                # full 1.5R, no partial


# ---- persistence (restart-safe) ----
def test_open_watch_survives_restart(tmp_path):
    from store import Store
    st = Store(str(tmp_path / "s.db")); p = str(tmp_path / "tr.csv")
    t = ProfileBPaperTracker(st, "MFFU-50K-1", "paper", dpp=2.0, path=p)
    t.on_signal(SIG, qty=1, bar_i=0, ts="2026-06-22 09:45")
    t.on_bar(1, "2026-06-22 09:50", 100, 101, 99, 100)          # FILLED, not yet resolved
    assert len(t.open) == 1 and t.open[0]["filled"] == 1
    t2 = ProfileBPaperTracker(st, "MFFU-50K-1", "paper", dpp=2.0, path=p)   # "restart"
    assert len(t2.open) == 1 and t2.open[0]["filled"] == 1      # watch restored
    t2.on_bar(2, "2026-06-22 09:55", 101, 104, 100, 103)        # resolves in the restored tracker
    assert t2.closed == 1


def test_no_double_record_across_restart(tmp_path):
    import csv
    from store import Store
    st = Store(str(tmp_path / "s.db")); p = str(tmp_path / "tr.csv")
    t = ProfileBPaperTracker(st, "MFFU-50K-1", "paper", dpp=2.0, path=p)
    t.on_signal(SIG, qty=1, bar_i=0, ts="2026-06-22 09:45")
    t.on_bar(1, "2026-06-22 09:50", 100, 101, 99, 100)
    t.on_bar(2, "2026-06-22 09:55", 101, 104, 100, 103)         # resolved + recorded
    assert t.closed == 1
    # restart with a STALE snapshot that still has the resolved watch -> must NOT re-record
    t2 = ProfileBPaperTracker(st, "MFFU-50K-1", "paper", dpp=2.0, path=p)
    t2.open = [dict(side="long", d=1, entry=100.0, stop=98.0, target=103.0, qty=1,
                    sbar=0, ts="2026-06-22 09:45", filled=1)]
    t2.on_bar(2, "2026-06-22 09:55", 101, 104, 100, 103)        # key dedup blocks the re-record
    n = sum(1 for _ in csv.DictReader(open(p)))
    assert n == 1                                              # exactly one B row, not two
