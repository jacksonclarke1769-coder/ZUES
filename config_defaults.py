"""CONFIGLOCK — version-controlled defaults for safety-critical config.

This file IS committed (unlike config.py, which is gitignored for local/secret posture).
It guarantees a fresh clone / future session resolves the OFFICIAL exit model, never a
silent SINGLE_TARGET fallback (the exact mismatch EXITLOCK caught).

NO secrets, NO credentials, NO URLs in this file — defaults only.
"""

# EXIT3_FIXED_PARTIAL is the official live/eval model (1 MNQ @ +1R, 2 MNQ @ +2R, shared
# stop, no trailing, no breakeven). It is the validated, eval-buffer-safe model.
EXIT_MODEL = "EXIT3_FIXED_PARTIAL"

# Only these may be used for live/paper/controlled execution.
EXIT_MODEL_ALLOWED = {
    "EXIT3_FIXED_PARTIAL",
}

# SINGLE_TARGET (full position to one 2R target) is RESEARCH-ONLY. It is retired for live
# eval — it breaches the $2k eval drawdown buffer — and must NEVER be the silent live
# fallback. It may appear only in research/backtest comparison tools and explicit tests.
EXIT_MODEL_RESEARCH_ONLY = {
    "SINGLE_TARGET",
}

# Modes for which an unsafe/unknown exit model must fail closed.
EXECUTION_MODES = {"live", "paper", "controlled"}


def exit3_split(qty):
    """Official Exit #3 integer split: (tp1_qty @ +1R, tp2_qty @ +2R). qty=1 -> (0,1) all-core;
    qty=3 -> (1,2). Version-controlled so a fresh clone never loses it with gitignored config.py."""
    q = int(qty)
    tp1 = q // 2
    return tp1, q - tp1
