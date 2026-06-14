"""D1c — defensive eval filter for Profile A ONLY.

D1c does not add trades, does not touch Profile B, does not change size, and cannot
override the daily stop, P3, or the kill switch. It can only ALLOW, BLOCK, or SUSPEND
an EXISTING Profile A entry. It fails closed: stale/missing/zero drift => SUSPEND.

Veto order for a Profile A entry (each can only veto, never un-veto a higher gate):
    daily-stop  ->  P3  ->  D1c   (B skips D1c entirely)

ARES eval decisions are tagged trial_eligible=False / counts_for_trial=False /
source="ares_eval" so they NEVER advance the ATHENA official forward count.
"""
import csv
import os
from datetime import datetime, timezone

LOG = "out/ares/d1c_eval_log.csv"
FIELDS = ["timestamp", "account", "mode", "setup", "direction", "drift_value",
          "drift_sign", "trade_direction", "decision", "reason",
          "would_have_traded_without_d1c", "actual_trade_sent", "trial_eligible",
          "counts_for_trial", "source"]
BLOCKING_MODES = {"ACTIVE_EVAL_FILTER", "PRODUCTION_FUNDED"}


def _dir(direction):
    return 1 if str(direction).lower() in ("long", "buy") else -1


def d1c_decide(mode, drift_value, drift_sign, direction,
               feed_age_s=None, has_open=True, poll_sec=300):
    """Pure decision: ALLOW / BLOCK / SUSPEND for a Profile A trade. Fail closed."""
    if mode == "OFF":
        return "ALLOW", "d1c off — not consulted"
    # fail-closed conditions (evaluated for SHADOW logging and BLOCKING modes alike)
    if feed_age_s is None or feed_age_s > 5 * poll_sec:
        return "SUSPEND", "d1c feed stale/missing"
    if not has_open:
        return "SUSPEND", "missing 09:30 open"
    if drift_value in (None, 0) or drift_sign in (None, 0):
        return "SUSPEND", "zero/missing drift"
    return ("ALLOW", "drift agrees") if drift_sign == _dir(direction) else \
           ("BLOCK", "drift disagrees")


def profile_a_permission(d1c_mode, *, signal_present, daily_stopped, p3_blocked,
                         drift_value=None, drift_sign=None, direction="long",
                         feed_age_s=None, has_open=True, poll_sec=300):
    """Full Profile A entry permission. Returns dict(permit, reason, d1c_decision).
    D1c is the LAST veto and can only subtract."""
    if not signal_present:
        return dict(permit=False, reason="no Profile A signal", d1c_decision="n/a")
    if daily_stopped:                       # D1c can never resurrect this
        return dict(permit=False, reason="daily stop hit", d1c_decision="not_consulted")
    if p3_blocked:                          # nor this
        return dict(permit=False, reason="P3 block", d1c_decision="not_consulted")
    dec, why = d1c_decide(d1c_mode, drift_value, drift_sign, direction,
                          feed_age_s, has_open, poll_sec)
    permit = (dec == "ALLOW") if d1c_mode in BLOCKING_MODES else True
    return dict(permit=permit, reason=why, d1c_decision=dec)


def profile_b_permission(*, signal_present, daily_stopped, p3_blocked):
    """Profile B NEVER consults D1c. Identical to non-D1c logic."""
    if not signal_present:
        return dict(permit=False, reason="no Profile B signal")
    if daily_stopped:
        return dict(permit=False, reason="daily stop hit")
    if p3_blocked:
        return dict(permit=False, reason="P3 block")
    return dict(permit=True, reason="ok")


def log_decision(account, mode, setup, direction, drift_value, drift_sign,
                 decision, reason, permit, source="ares_eval", log=LOG):
    """Append the full audit row. ARES eval => trial_eligible/counts_for_trial False."""
    os.makedirs(os.path.dirname(log), exist_ok=True)
    trial = source not in ("ares_eval",)        # ARES eval never counts for ATHENA
    row = dict(timestamp=datetime.now(timezone.utc).isoformat(), account=account,
               mode=mode, setup=setup, direction=direction, drift_value=drift_value,
               drift_sign=drift_sign, trade_direction=_dir(direction),
               decision=decision, reason=reason,
               would_have_traded_without_d1c=True, actual_trade_sent=permit,
               trial_eligible=trial, counts_for_trial=trial, source=source)
    new = not os.path.exists(log)
    with open(log, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)
    return row


def athena_official_count(log=LOG):
    """ATHENA forward count = decisions with trial_eligible True. ARES eval logs (all
    trial_eligible False) NEVER advance this."""
    if not os.path.exists(log):
        return 0
    with open(log) as f:
        return sum(1 for r in csv.DictReader(f) if r["trial_eligible"] == "True")
