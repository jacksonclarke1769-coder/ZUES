"""EVAL CONFIG FIREWALL — the live-eval machine's certified constants are locked separately
from routine research and must not drift silently. Mirrors test_funded_config_firewall.py,
extended to the eval machine (Apex-50K-eval, DEC-20260705-1102).

Three checks, all must pass:

1. The certified SCALAR constants in `config_defaults.py` (the live values) must equal the
   frozen, provenance-carrying snapshot in `config_eval_locked.py`, AND
   `auto_safety.EVAL_TIERS["Apex-50K-eval"]` (the live tier row) must deep-equal
   `config_eval_locked.EVAL_TIERS_APEX_ROW`. Any commit that touches live eval sizing / exit
   model / daily stop breaks this test UNLESS `config_eval_locked.py` is updated in the SAME
   commit — the audited, provenance-carrying act the firewall exists to force.

2. `config_eval_locked.py` itself must match its recorded SHA256 in
   `evidence/eval_config.sha256`, so changing the locked file also requires touching the sha
   file in the same commit (a second, loud, greppable trip-wire).

3. The COMPANION hashes recorded in `evidence/eval_config.sha256` for the live files
   (`config_defaults.py`, `auto_safety.py`) must match those files' current contents. This is
   the same recorded set the WATCHDOG's CONFIG INTEGRITY invariant recomputes at runtime; the
   test keeps the recorded hashes honest so a legitimate config edit forces a same-commit
   re-record (which is itself the certification hand-off the watchdog then trusts).
"""
import hashlib
import os

import auto_safety
import config_defaults as CD
import config_eval_locked as LOCKED

_HERE = os.path.dirname(os.path.abspath(__file__))
_SHA_FILE = os.path.join(_HERE, "evidence", "eval_config.sha256")


def _recorded_hashes():
    """Parse evidence/eval_config.sha256 (shasum -a 256 format) -> {basename: hexdigest}."""
    out = {}
    with open(_SHA_FILE) as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            digest, name = ln.split()
            out[os.path.basename(name)] = digest
    return out


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def test_live_eval_constants_match_locked_snapshot():
    assert CD.EXIT_MODEL == LOCKED.EXIT_MODEL
    assert CD.A_RISK_BUDGET_USD == LOCKED.A_RISK_BUDGET_USD
    assert CD.A_STOP_CAP_PTS == LOCKED.A_STOP_CAP_PTS
    assert CD.DAILY_STOP_POINTS == LOCKED.DAILY_STOP_POINTS
    assert CD.POINT_VALUE_MNQ == LOCKED.POINT_VALUE_MNQ
    assert auto_safety.EVAL_TIERS["Apex-50K-eval"] == LOCKED.EVAL_TIERS_APEX_ROW, (
        "auto_safety.EVAL_TIERS['Apex-50K-eval'] has drifted from "
        "config_eval_locked.EVAL_TIERS_APEX_ROW. If this is a deliberate, audited eval "
        "re-certification, update config_eval_locked.py (and evidence/eval_config.sha256) in "
        "the SAME commit. If not, this is unauthorized drift into the live eval machine — revert."
    )


def test_locked_file_matches_recorded_sha256():
    recorded = _recorded_hashes()
    actual = _sha256(os.path.join(_HERE, "config_eval_locked.py"))
    assert actual == recorded.get("config_eval_locked.py"), (
        "config_eval_locked.py contents no longer match evidence/eval_config.sha256. "
        "EVAL_CONFIG firewall: eval constants changed — requires eval re-certification + "
        "operator approval (see config_eval_locked.py header)."
    )


def test_companion_live_file_hashes_match_recorded():
    recorded = _recorded_hashes()
    for name in ("config_defaults.py", "auto_safety.py"):
        actual = _sha256(os.path.join(_HERE, name))
        assert actual == recorded.get(name), (
            f"{name} no longer matches its recorded hash in evidence/eval_config.sha256. "
            "This is the same recorded set the watchdog's CONFIG INTEGRITY invariant checks; "
            "a legitimate config change must re-record it in the SAME commit (eval re-cert)."
        )
