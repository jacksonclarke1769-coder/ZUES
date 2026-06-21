"""Monday audit orchestrator — A/B P&L split + decision-count split."""
import importlib.util
import json
import os

import trade_results as TR

_MA = os.path.join(os.path.dirname(__file__), "tools", "monday_audit.py")
spec = importlib.util.spec_from_file_location("monday_audit", _MA)
MA = importlib.util.module_from_spec(spec); spec.loader.exec_module(MA)


def test_pnl_split_separates_A_B_and_realised(tmp_path):
    p = str(tmp_path / "tr.csv")
    TR.record("2026-06-22", "paper", "X", "A", "short", 3, 1050.0,
              note="paper · modeled fill", fill_backed=False, path=p)        # A hypothetical
    TR.record("2026-06-22", "paper", "X", "B", "long", 2, 180.0,
              note="paper · Profile B ORB · target", fill_backed=False, path=p)  # B hypothetical
    TR.record("2026-06-22", "live", "X", "A", "short", 3, 900.0,
              note="broker fill confirmed", fill_backed=True, path=p)        # A realised
    s = MA._pnl_split("2026-06-22", path=p)
    assert s["A"]["hypothetical"] == 1050.0 and s["A"]["realised"] == 900.0 and s["A"]["n"] == 2
    assert s["B"]["hypothetical"] == 180.0 and s["B"]["realised"] == 0.0 and s["B"]["n"] == 1


def test_decision_split_counts_A_vs_B(tmp_path):
    d = tmp_path / "logs"; d.mkdir()
    path = d / "2026-06-22.jsonl"
    with open(path, "w") as fh:
        fh.write(json.dumps(dict(final_action="no_signal", profile="A")) + "\n")
        fh.write(json.dumps(dict(final_action="paper_signal", profile="A")) + "\n")
        fh.write(json.dumps(dict(final_action="paper_signal", profile="B")) + "\n")
        fh.write(json.dumps(dict(final_action="ares_blocked", profile="B")) + "\n")
    c = MA._decision_split("2026-06-22", log_dir=str(d))
    assert c["A"]["paper_signal"] == 1 and c["A"]["no_signal"] == 1
    assert c["B"]["paper_signal"] == 1 and c["B"]["ares_blocked"] == 1
