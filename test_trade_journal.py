"""Trade journal — correct learning labels + post-exit 'stopped early' detection."""
import json
import pytest
from trade_journal import TradeJournal, classify


def test_classify_labels():
    assert classify("target", 1.5, False, False, 8)[0] == "WIN_CLEAN"
    assert classify("eod", 1.4, True, False, 40)[0] == "WIN_RUNNER"
    assert classify("stop", -1.0, True, False, 12)[0] == "LOSS_GAVEBACK"   # reached +1R then reversed
    assert classify("stop", -1.0, False, False, 2)[0] == "LOSS_WHIPSAW"    # quick reversal
    assert classify("stop", -1.0, False, False, 30)[0] == "LOSS_WRONG"     # never got going
    assert classify("eod", -0.4, False, False, 50)[0] == "LOSS_FADE"


def test_on_resolved_writes_and_labels(tmp_path):
    j = TradeJournal("MFFU-50K-1", "live", path_dir=str(tmp_path), today="2026-06-24")
    rec = j.on_resolved("B", "short", 2, 29603, 29664.5, 29510.7, 29664.5, "stop", -1.0, -246,
                        ts="2026-06-24 10:20:00-04:00", hold_bars=1)
    assert rec["tag"] == "LOSS_WHIPSAW" and "WHIPSAW" in rec["why"]
    lines = (tmp_path / "2026-06-24.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    d = json.loads(lines[0])
    assert d["profile"] == "B" and d["R"] == -1.0 and d["entry"] == 29603.0


def test_post_exit_stopped_early(tmp_path):
    """A short stops out, then price falls to the target a few bars later -> 'stopped early' flag."""
    j = TradeJournal("A1", "live", path_dir=str(tmp_path), today="2026-06-24", post_exit_bars=10)
    j.on_resolved("B", "short", 2, 29603, 29664.5, 29510.7, 29664.5, "stop", -1.0, -246,
                  ts="2026-06-24 10:20:00-04:00", hold_bars=1)
    assert len(j.watching) == 1
    j.on_bar(high=29660, low=29600)        # target 29510.7 not hit yet
    assert j.watching[0]["rec"]["post_exit"] is None
    j.on_bar(high=29560, low=29478)        # low pierces 29510.7 -> target would've hit
    assert not j.watching                  # watch resolved
    note = j.entries[0]["post_exit"]
    assert note and "STOPPED EARLY" in note and "right direction" in note


def test_post_exit_expires_without_hit(tmp_path):
    j = TradeJournal("A1", "live", path_dir=str(tmp_path), today="2026-06-24", post_exit_bars=2)
    j.on_resolved("B", "long", 2, 29600, 29540, 29700, 29540, "stop", -1.0, -240,
                  ts="2026-06-24 11:00:00-04:00", hold_bars=4)
    j.on_bar(high=29560, low=29545); j.on_bar(high=29555, low=29548)   # never reaches 29700
    assert not j.watching and j.entries[0]["post_exit"] is None        # expired, no false flag
