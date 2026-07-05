"""CONFIGLOCK — version-controlled defaults for safety-critical config.

This file IS committed (unlike config.py, which is gitignored for local/secret posture).
It guarantees a fresh clone / future session resolves the OFFICIAL exit model, never a
silent SINGLE_TARGET fallback (the exact mismatch EXITLOCK caught).

NO secrets, NO credentials, NO URLs in this file — defaults only.
"""

# EXIT3_FIXED_PARTIAL is the official live/eval model as of 2026-07-02 (Phase-3 re-certification on
# 1m-TRUTH fills, tools_phase3_config_sweep.py). The 2026-07-01 SINGLE_1R promotion was an artifact of
# the 5m fill-bar target look-ahead (audit F1/F2): its gate numbers (63.1% etc.) are INVALID. On 1m
# truth, A Exit#3 PF 1.237/+75R beats A single@1R 1.135/+46R, and the selected machine
# (A10 Exit#3 + D1c, size-to-risk $1200 [DLL re-lock 2026-07-02b], B off, mm0) re-certifies
# at pass 47.8% / bust 15.9% (DLL-honest; cap-10 re-lock 2026-07-05; old $1600/57.7%/17.7% superseded — DLL unmodeled).
EXIT_MODEL = "EXIT3_FIXED_PARTIAL"

# Only these may be used for live/paper/controlled execution.
EXIT_MODEL_ALLOWED = {
    "EXIT3_FIXED_PARTIAL",
    "SINGLE_1R",          # demoted 2026-07-02 (F1 artifact); still flag-gated if selected
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


# --- Daily loss stop, authored in POINTS × CONTRACTS (self-imposed ARES stop; Apex has NO hard DLL) ----
# daily_stop_$ = DAILY_STOP_POINTS × DAILY_STOP_CONTRACTS × POINT_VALUE_MNQ.  275 × 1 × $2 = $550.
# FIXED-dollar semantics (Option A): a constant $ cap, just expressed transparently in points. NOT
# book-scaled (that would let a bigger book lose more $/day against the tight eval trailing DD).
POINT_VALUE_MNQ = 2.0                # $/index-point/MNQ contract (fixed contract spec; full NQ = 20.0)
DAILY_STOP_POINTS = 275              # the point budget
DAILY_STOP_CONTRACTS = 1             # reference contracts

# --- PROSPECTIVE risk gate (2026-07-02 audit R1) ------------------------------------------------
# The $550 daily stop is retrospective (books on exits) — it cannot stop concurrent A+B brackets
# from stacking more open risk than the account's remaining trailing-DD cushion. These gates act
# BEFORE an order is sent. They only ever BLOCK/reduce risk (fail-closed; never add exposure).
A_STOP_CAP_PTS = 0           # DISABLED 2026-07-02: on 1m-truth fills the 80pt hard cap costs ~14pp
                             # of eval pass (59.5->45.2%) — the "zero expectancy cost" finding was an
                             # artifact of the biased 5m fills. Superseded by A_RISK_BUDGET_USD sizing.
A_RISK_BUDGET_USD = 1200     # size-to-risk (DLL-recert 2026-07-02): operator confirmed Apex 50K EOD
                             # eval enforces a $1,000 Daily Loss Limit; $1,600 allowed a single A-trade
                             # excursion to cross the DLL. $1,200 dominated $1,600 in the DLL re-lock;
                             # both rows were cap-40-simmed, corrected machine numbers in
                             # reports/risk_arithmetic_reconciliation_2026-07-05.md (cap-10 re-lock 2026-07-05).
                             # Source: reports/account_size_research_2026-07-02.json row "50K@1200";
                             # harness tools_account_size_research.py. OLD value $1,600 (phase3_selected,
                             # tools_phase3_config_sweep.py, 57.7%/17.7%) SUPERSEDED — DLL unmodeled.
OPEN_RISK_CUSHION_FRAC = 0.9  # open+new bracket risk must fit inside this fraction of the live cushion

# --- Execution slippage tripwire (SLIP-class halt) — spec docs/specs/slippage_tripwire_spec.md ---
# The certified 47.8% pass (cap-10 re-lock 2026-07-05) rests on backtest fills assuming ~0 entry slippage. This watches REAL
# fill quality off exec_telemetry and, when entries systematically fill worse than modeled (or aren't
# filling at all), ALERTS and — in halt mode — latches the read-back sentinel HALT (entries frozen,
# NEVER flatten; brackets stay). Default OFF; --slip-tripwire arms it, --slip-mode picks alert/halt.
# 1R = A_RISK_BUDGET_USD ($1,200); slippage_R is signed +worse. Sensitivity anchor: tools_exec_report
# models -0.05R/trade expectancy cost, so the 0.10R mean-halt cap is ~2x that band.
SLIP_TRIPWIRE_ENABLED = False   # master default OFF (runner --slip-tripwire overrides)
SLIP_TRIPWIRE_MODE   = "alert"  # "off" | "alert" (compute+alert, never halt) | "halt" (also latch sentinel)
SLIP_WARMUP_MIN      = 5        # no action of any kind before this many resolved fills
SLIP_WINDOW_N        = 10       # rolling window of most-recent FILLED entries for the mean test
SLIP_MEAN_R_HALT     = 0.10     # mean entry slippage over window > this (R) -> HALT   (~$120/trade tax)
SLIP_SINGLE_R_ALERT  = 0.25     # any single fill worse than this (R)        -> ALERT  (~$300 on entry)
SLIP_SINGLE_R_HALT   = 0.50     # any single fill worse than this (R)        -> HALT   (half the risk)
SLIP_MISS_WINDOW_N   = 10       # rolling window of resolved A signals for the miss-rate test
SLIP_MISS_RATE_HALT  = 0.40     # MISSED / (FILLED+MISSED) over window > this -> HALT (edge never captured)


def slip_tripwire_cfg():
    """The tripwire thresholds as a plain dict (what slip_tripwire.evaluate() consumes)."""
    return dict(
        warmup_min=SLIP_WARMUP_MIN,
        window_n=SLIP_WINDOW_N,
        mean_r_halt=SLIP_MEAN_R_HALT,
        single_r_alert=SLIP_SINGLE_R_ALERT,
        single_r_halt=SLIP_SINGLE_R_HALT,
        miss_window_n=SLIP_MISS_WINDOW_N,
        miss_rate_halt=SLIP_MISS_RATE_HALT,
    )


def daily_stop_dollars(points=None, contracts=None, point_value=POINT_VALUE_MNQ):
    """The daily-stop dollar cap from the points × contracts authoring. Whole-dollar -> int for clean
    display + byte-identical downstream ($550 as before, now derived not magic)."""
    p = DAILY_STOP_POINTS if points is None else points
    c = DAILY_STOP_CONTRACTS if contracts is None else contracts
    d = float(p) * float(c) * float(point_value)
    return int(d) if d == int(d) else d


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


# --- HTF alignment skip filter (shadow-only; default OFF until paper-forward gate) ---------------
# When True: A entries with htf15+htf1h+htf4h (signed by trade direction) <= -2 are blocked
# (logged to ARGUS as d1c_blocked with reason="htf_alignment ... <= -2").
# ARMED ONLY after paper-forward gate passes (>= 20 A signals with live classification matching
# backtest, 0-mismatch parity). DO NOT set True without operator approval + Fable re-lock.
HTF_SKIP_ENABLED = False
