"""Profile B parity — the streaming ProfileBEngine must emit 0 signal mismatches vs the
validated batch backtest (b_entries/b_exits) over the full history, the way Profile A was
proven. Runs the harness as a subprocess (it loads 12y of bars). ~15s."""
import os
import subprocess
import sys

import pytest

# dev-only: this parity check loads 12y of parquet history from the research data dir (NOT shipped) and
# needs fastparquet. Skip cleanly on a fresh install — the B engine logic is covered by the other tests.
def _have_parity_prereqs():
    if not os.path.isdir(os.path.expanduser("~/trading-team/backtests/ict-nq-framework")):
        return False                                    # user laptop: no research data -> skip
    for eng in ("pyarrow", "fastparquet"):              # need SOME parquet engine to load the 12y bars
        try:
            __import__(eng)
            return True
        except Exception:
            continue
    return False


@pytest.mark.skipif(not _have_parity_prereqs(),
                    reason="dev-only full-history parity (needs the research backtests data dir + fastparquet)")
def test_profile_b_full_history_parity():
    r = subprocess.run(
        [sys.executable, "tools/check_profile_b_parity.py"],
        capture_output=True, text=True, timeout=180,
        cwd=os.path.dirname(os.path.abspath(__file__)))
    out = r.stdout + r.stderr
    assert "PROFILE B PARITY: 0 MISMATCHES" in out, out[-800:]
    assert "MISMATCHES: 0 " in out, out[-800:]
    assert r.returncode == 0, out[-800:]
