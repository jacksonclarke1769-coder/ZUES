"""test_vpc_journal.py — the four VPC observational journals (signal / fill_intent / missed_fill /
rejection) append JSONL rows and are FAIL-OPEN (a write error never raises into the caller)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from vpc_journal import VpcJournal


def _read(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def test_four_journals_write_rows(tmp_path):
    j = VpcJournal("ACC", "paper", path_dir=str(tmp_path), today="2024-03-01")
    p1 = j.signal(dict(side="long", direction=1, stop_dist=25.0, ts_signal="t",
                       slot=10, atr=10.0, vwap=100.0, emission_mode="shadow"))
    p2 = j.fill_intent(ts_signal="t", side="long", qty=2, entry=100.0, stop=95.0,
                       signal_id="ZB-abc", why="")
    p3 = j.missed_fill(ts_signal="t", side="long", reason="day cap reached")
    p4 = j.rejection(ts_signal="t", side="long", stage="build_entry", error="wrong side")
    for p in (p1, p2, p3, p4):
        assert p is not None and os.path.exists(p)
    sig_rows = _read(p1)
    assert sig_rows[0]["kind"] == "signal" and sig_rows[0]["profile"] == "V"
    assert sig_rows[0]["stop_dist"] == 25.0
    assert _read(p3)[0]["reason"] == "day cap reached"
    assert _read(p4)[0]["stage"] == "build_entry"


def test_journal_is_fail_open(tmp_path, capsys):
    """A write error is swallowed (returns None) and printed loudly — never raised."""
    j = VpcJournal("ACC", "paper", path_dir=str(tmp_path))
    # unknown kind routes through _write's guard -> fail-open (None), no exception
    res = j._write("not_a_kind", dict(x=1))
    assert res is None
    out = capsys.readouterr().out
    assert "WRITE FAILED" in out


def test_appends_multiple_rows(tmp_path):
    j = VpcJournal("ACC", "paper", path_dir=str(tmp_path), today="2024-03-01")
    p = None
    for i in range(3):
        p = j.missed_fill(ts_signal=f"t{i}", side="long", reason="disarmed")
    rows = _read(p)
    assert len(rows) == 3
    assert [r["ts_signal"] for r in rows] == ["t0", "t1", "t2"]
