"""Shadow stop-cap overlay — observe-only: correct cap scoping (A only), tally, fail-safe."""
import json
import pytest
from shadow_overlay import ShadowOverlay


def _ov(tmp_path):
    return ShadowOverlay(cap_pts=80.0, path=str(tmp_path / "shadow.jsonl"))


def test_profile_a_wide_stop_would_skip(tmp_path):
    ov = _ov(tmp_path)
    row = ov.record("A", "long", entry=20000, stop=19900, r=-1.0, pnl=-200,  # 100pt > 80 cap
                    reason="stop", ts="2026-06-25 10:00:00-04:00")
    assert row["risk_pts"] == 100.0 and row["cap_keep"] is False and row["would_skip"] is True


def test_profile_a_tight_stop_kept(tmp_path):
    ov = _ov(tmp_path)
    row = ov.record("A", "short", entry=20000, stop=20050, r=2.0, pnl=400,   # 50pt <= 80 cap
                    reason="target", ts="2026-06-25 10:05:00-04:00")
    assert row["cap_keep"] is True and row["would_skip"] is False


def test_profile_b_never_capped(tmp_path):
    ov = _ov(tmp_path)
    row = ov.record("B", "short", entry=20000, stop=20200, r=-1.0, pnl=-200,  # 200pt but B is out of scope
                    reason="stop", ts="2026-06-25 10:10:00-04:00")
    assert row["cap_keep"] is True and row["would_skip"] is False


def test_summary_baseline_vs_capped(tmp_path):
    ov = _ov(tmp_path)
    ov.record("A", "long", 20000, 19980, 2.0, 400, "target", "2026-06-25 10:00:00-04:00")   # 20pt keep, win
    ov.record("A", "short", 20000, 20100, -1.0, -200, "stop", "2026-06-25 10:20:00-04:00")  # 100pt skip, loss
    ov.record("A", "long", 21000, 20985, 1.5, 300, "target", "2026-06-26 10:00:00-04:00")   # 15pt keep, win
    s = ov.summary()
    assert s["baseline"]["n"] == 3 and s["capped"]["n"] == 2           # one A skipped
    assert s["skipped_n"] == 1 and s["skipped_R"] == -1.0             # the wide-stop loser excluded
    assert s["capped"]["totUSD"] == 700 and s["baseline"]["totUSD"] == 500
    # worst day = worst daily SUM: 06-25 nets +400-200=+200 (baseline); capped drops the -200 -> 06-25=+400,
    # so worst capped day is 06-26 (+300). Removing the wide-stop loser lifts the worst day +200 -> +300.
    assert s["worst_day_baseline"] == 200.0 and s["worst_day_capped"] == 300.0


def test_persists_to_disk_and_loads(tmp_path):
    from shadow_overlay import load
    p = str(tmp_path / "shadow.jsonl")
    ov = ShadowOverlay(cap_pts=80.0, path=p)
    ov.record("A", "long", 20000, 19900, -1.0, -200, "stop", "2026-06-25 10:00:00-04:00")
    rows = load(p)
    assert len(rows) == 1 and rows[0]["would_skip"] is True
    assert ShadowOverlay.summarize(rows)["skipped_n"] == 1


def test_record_never_raises(tmp_path):
    ov = _ov(tmp_path)
    assert ov.record("A", "long", None, "bad", "x", None, "stop", "ts") is None   # swallowed


def test_tg_summary_empty_and_populated(tmp_path):
    ov = _ov(tmp_path)
    assert "no Profile A trades" in ov.tg_summary()
    ov.record("A", "long", 20000, 19980, 2.0, 400, "target", "2026-06-25 10:00:00-04:00")
    assert "Baseline" in ov.tg_summary() and "Capped" in ov.tg_summary()
