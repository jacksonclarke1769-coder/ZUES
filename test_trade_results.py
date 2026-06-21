"""Tests for the dashboard P&L calendar ledger (trade_results) — pure, no network/orders."""
import trade_results as TR


def test_pnl_from_r():
    # 3 MNQ, 40pt risk, +1.5R win -> 1.5 * 40 * $2 * 3 = $360
    assert TR.pnl_from_r(1.5, 100.0, 60.0, 3) == 360.0
    # -1R loss -> -$240
    assert TR.pnl_from_r(-1.0, 100.0, 60.0, 3) == -240.0
    # short geometry (entry below stop) uses abs distance
    assert TR.pnl_from_r(1.0, 60.0, 100.0, 2) == 160.0
    # unfilled/unresolved -> None (no position, no P&L)
    assert TR.pnl_from_r(None, 1, 2, 3) is None


def test_record_and_by_day(tmp_path):
    p = str(tmp_path / "tr.csv")
    TR.record("2026-06-16", "paper", "MFFU-50K-1", "A", "short", 3, 1400, "tp", path=p)
    TR.record("2026-06-16", "paper", "MFFU-50K-1", "A", "long", 3, -240, "stop", path=p)
    TR.record("2026-06-17", "live", "MFFU-50K-1", "A", "long", 3, 360, "tp", path=p)
    agg = TR.by_day(path=p)
    assert agg["2026-06-16"]["pnl"] == 1160.0       # 1400 - 240
    assert agg["2026-06-16"]["trades"] == 2
    assert agg["2026-06-16"]["mode"] == "paper"
    assert agg["2026-06-17"]["pnl"] == 360.0
    assert agg["2026-06-17"]["mode"] == "live"      # any live trade -> LIVE day


def test_by_day_missing_file(tmp_path):
    assert TR.by_day(path=str(tmp_path / "nope.csv")) == {}


def test_record_resolved_incremental(tmp_path):
    """Mirrors the auto_live loop: tracker rows accrue over bars; record_resolved appends
    only newly-resolved ones and returns a high-water mark so nothing double-counts."""
    p = str(tmp_path / "tr.csv")
    rows = []
    # bar 1: one resolved win, one still-open (result_R None)
    rows.append(dict(date="2026-06-16", direction="short", entry=100.0, stop=140.0,
                     result_R=1.5, notes=["tp1_tp2"]))
    rows.append(dict(date="2026-06-16", direction="long", entry=100.0, stop=80.0,
                     result_R=None, notes=["open"]))
    n = TR.record_resolved(rows, 0, "live", "MFFU-50K-1", 3, path=p)
    assert n == 2                                   # both consumed (one skipped as unresolved)
    # the open trade resolves later
    rows[1]["result_R"] = -1.0
    n = TR.record_resolved(rows, n, "live", "MFFU-50K-1", 3, path=p)
    assert n == 2                                   # nothing new appended yet (watermark held)
    # bar 3: a brand-new resolved trade arrives
    rows.append(dict(date="2026-06-17", direction="long", entry=100.0, stop=60.0,
                     result_R=1.0, notes=[]))
    n = TR.record_resolved(rows, n, "live", "MFFU-50K-1", 3, path=p)
    assert n == 3
    agg = TR.by_day(path=p)
    # CONFIGLOCK: record_resolved rows are MODELED (not broker-confirmed) -> hypothetical, NOT realised.
    # 06-16: only the +1.5R win was recorded (1.5*40*2*3 = 360); the late-resolved one was past the watermark
    assert agg["2026-06-16"]["pnl"] == 0.0                   # realised stays 0 until broker recon
    assert agg["2026-06-16"]["hypothetical_pnl"] == 360.0
    assert agg["2026-06-16"]["mode"] == "live"
    assert agg["2026-06-17"]["hypothetical_pnl"] == 240.0    # 1.0*40*2*3, modeled
