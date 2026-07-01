"""CONFIGLOCK — version-controlled defaults for safety-critical config.

This file IS committed (unlike config.py, which is gitignored for local/secret posture).
It guarantees a fresh clone / future session resolves the OFFICIAL exit model, never a
silent SINGLE_TARGET fallback (the exact mismatch EXITLOCK caught).

NO secrets, NO credentials, NO URLs in this file — defaults only.
"""

# SINGLE_1R (1RR) is the official live/eval model as of 2026-07-01: full position to a single +1R
# target, shared -1R stop (no partial, no +2R core). PROMOTED from EXIT3 after a definitive 5y real-
# Databento gate (tools_exit_final_compare.py): eval pass 63.1% vs 59.3%, bust 34.4% vs 37.2%, funded
# reach-lock 84.4% vs 79.5%, funded E[payout] $22.1k vs $17.8k (+23.7%) — 1RR wins every business axis.
# Certified causally-clean + IS/OOS/MC-validated. EXIT3_FIXED_PARTIAL (1 MNQ @ +1R, 2 MNQ @ +2R, shared
# stop) is RETAINED as the flag-gated fail-safe fallback. LIVE routing of SINGLE_1R still requires
# single-1r-approved.flag (else fail-safe to EXIT3) AND the live read-back guard — deliberate live-arms.
EXIT_MODEL = "SINGLE_1R"

# Only these may be used for live/paper/controlled execution.
EXIT_MODEL_ALLOWED = {
    "EXIT3_FIXED_PARTIAL",
    "SINGLE_1R",          # now the DEFAULT (see top); still flag-gated for live routing
}

# The always-safe fail-safe target — DECOUPLED from EXIT_MODEL on purpose. It needs no approval flag
# and is eval-buffer-safe, so it is what a live/controlled SINGLE_1R falls back to WITHOUT the approval
# flag. Must NOT be the configured default (else the fail-safe would fail OPEN). Keep it EXIT3.
SAFE_FALLBACK_EXIT_MODEL = "EXIT3_FIXED_PARTIAL"

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


# --- Profile B exit (PROMOTED 2026-06-26) -----------------------------------------------------------
# PARTIAL_1R = 50% @ +1R, 50% @ the FROZEN 1.5R ATR target, shared stop. Validated on real Databento
# (13/13 adversarial battery, validate_b_partial.py): PF 1.20->1.40, maxDD -36->-9R, +59% net / -64% DD
# at 2 MNQ, robust to harsh + partial-fill costs, all 6 yrs improve. The B SIGNAL/stop/1.5R target are
# UNCHANGED — this only splits the exit (adds a +1R partial). Split = exit3_split (50/50; qty=1 -> all-core).
# SINGLE = the prior single-OCO-bracket B exit; kept as the qty=1 fallback + the un-approved-live fallback.
B_EXIT_MODEL = "PARTIAL_1R"
B_EXIT_MODEL_ALLOWED = {"PARTIAL_1R", "SINGLE", "SINGLE_1R"}
B_PARTIAL_APPROVAL_FLAG = "b-exit-partial-approved.flag"   # required to route the partial in LIVE mode


# --- SINGLE_1R exit (PROMOTED TO DEFAULT 2026-07-01; certified causally-clean 2026-06-30) ----------
# Full position to a SINGLE +1R target, shared -1R stop (no partial, no +2R core). Now the default
# EXIT_MODEL (see top of file for the 5y gate numbers). Look-ahead clean + IS/OOS/MC-validated.
# LIVE/controlled routing STILL requires single-1r-approved.flag (else the runner fails SAFE to the
# RETAINED EXIT3 model) — the flag + the live read-back guard are the deliberate live-arm steps.
SINGLE_1R_APPROVAL_FLAG = "single-1r-approved.flag"


def single1r_target(entry, stop, side):
    """Full-qty +1R take-profit price for SINGLE_1R: R = |entry-stop| projected in the trade direction.
    long -> entry + R ; short -> entry - R. (Deliberately NOT the strategy's +2R target.)"""
    r = abs(float(entry) - float(stop))
    d = 1 if side == "long" else -1
    return float(entry) + d * r


def single1r_live_ok(mode="paper", approval_dir=None):
    """May SINGLE_1R route a REAL order in this mode? paper -> yes (dry-run, safe). Anything else
    (live/controlled) -> only if single-1r-approved.flag exists. Never raises. The exit model is
    SELECTED via config.EXIT_MODEL; this only gates whether a live order may use it (else fail-safe)."""
    import os
    if mode == "paper":
        return True
    d = approval_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence", "approvals")
    return os.path.exists(os.path.join(d, SINGLE_1R_APPROVAL_FLAG))


MOMENTUM_APPROVAL_FLAG = "momentum-approved.flag"        # required to ROUTE momentum live
APEX_APPROVAL_FLAG = "apex-approved.flag"                # required to ROUTE a fan-out Apex book live


def resolve_apex_live(mode="paper", approval_dir=None):
    """Should a fan-out Apex book route to the BROKER? paper/dry-run -> yes (dry sender, no broker);
    LIVE -> only if apex-approved.flag exists, else the book runs DRY (logs, no live orders). Never raises."""
    import os
    if mode != "live":
        return True
    d = approval_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence", "approvals")
    return os.path.exists(os.path.join(d, APEX_APPROVAL_FLAG))


def resolve_momentum_live(mode="paper", approval_dir=None):
    """Should the Momentum lane route to the BROKER? paper/dry-run -> yes (to the paper sender, no broker);
    LIVE -> only if the approval flag exists, else SHADOW (model P&L only, no live orders). Never raises."""
    import os
    if mode != "live":
        return True
    d = approval_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence", "approvals")
    return os.path.exists(os.path.join(d, MOMENTUM_APPROVAL_FLAG))


def resolve_b_exit(mode="paper", approval_dir=None):
    """Resolve the Profile B exit model. PARTIAL_1R by default; in LIVE mode it requires the approval
    flag (else fail-safe to the prior SINGLE bracket — never silently change live exec). Never raises."""
    import os
    if B_EXIT_MODEL not in B_EXIT_MODEL_ALLOWED or B_EXIT_MODEL == "SINGLE":
        return "SINGLE"
    if mode == "live":
        d = approval_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence", "approvals")
        if not os.path.exists(os.path.join(d, B_PARTIAL_APPROVAL_FLAG)):
            return "SINGLE"                                # not approved for live -> safe prior bracket
    return "PARTIAL_1R"
