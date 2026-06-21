"""Profile B parity — the streaming ProfileBEngine must emit 0 signal mismatches vs the
validated batch backtest (b_entries/b_exits) over the full history, the way Profile A was
proven. Runs the harness as a subprocess (it loads 12y of bars). ~15s."""
import os
import subprocess
import sys

import pytest


def test_profile_b_full_history_parity():
    r = subprocess.run(
        [sys.executable, "tools/check_profile_b_parity.py"],
        capture_output=True, text=True, timeout=180,
        cwd=os.path.dirname(os.path.abspath(__file__)))
    out = r.stdout + r.stderr
    assert "PROFILE B PARITY: 0 MISMATCHES" in out, out[-800:]
    assert "MISMATCHES: 0 " in out, out[-800:]
    assert r.returncode == 0, out[-800:]
