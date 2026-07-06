"""INC-20260707 (pandas-3.0 daily-resample corruption) permanent canary.

pandas 3.x changed `resample(..., origin="start_day", offset="18h")` boundary
behavior, silently corrupting PDH/PDL (Profile A's tier-1 liquidity levels) and
making research streams interpreter-dependent (583 vs 548 trades from identical
code+data). Ground-truth adjudication: pandas 2.3.3 correct 3/3, 3.0.3 wrong.
This test pins the environment: every interpreter that can run this repo's
research or live code must carry pandas 2.x until the resample semantics are
re-certified under a newer major.
"""
import os, subprocess, sys
import pandas as pd


def test_current_interpreter_pandas_major_2():
    assert int(pd.__version__.split(".")[0]) == 2, (
        f"pandas {pd.__version__}: major!=2 — INC-20260707 daily-resample corruption risk")


def test_venv_interpreter_pandas_major_2_if_present():
    vpy = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python3")
    if not os.path.exists(vpy):
        return
    out = subprocess.run([vpy, "-c", "import pandas; print(pandas.__version__)"],
                         capture_output=True, text=True, timeout=60)
    ver = out.stdout.strip()
    assert ver and int(ver.split(".")[0]) == 2, (
        f".venv pandas {ver!r}: major!=2 — INC-20260707 (unpinned upgrade regression)")
