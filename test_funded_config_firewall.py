"""FUNDED CONFIG FIREWALL — funded-phase constants are certified separately from eval-sizing
research and must not drift silently. Two checks, both must pass:

1. `auto_safety.FUNDED_TIERS` (the live constant) must deep-equal `config_funded_locked.
   FUNDED_TIERS` (the frozen, provenance-carrying snapshot) exactly, key for key, tier for
   tier. Any future commit that touches live funded sizing (deliberately or as collateral
   damage from an eval-sizing change) breaks this test UNLESS `config_funded_locked.py` is
   updated in the SAME commit — which is the audited, provenance-carrying act the firewall
   exists to force.

2. `config_funded_locked.py` itself must match a recorded SHA256 (`evidence/
   funded_config.sha256`), so changing the locked file also requires touching the sha file
   in the same commit — a second, loud, greppable signal (this is a deliberate two-file
   trip-wire; see the file's own header for why the hash excludes itself instead of trying
   to self-reference).
"""
import hashlib
import os

import auto_safety
import config_funded_locked as LOCKED

_HERE = os.path.dirname(os.path.abspath(__file__))
_SHA_FILE = os.path.join(_HERE, "evidence", "funded_config.sha256")
_LOCKED_FILE = os.path.join(_HERE, "config_funded_locked.py")


def test_live_funded_tiers_match_locked_snapshot():
    assert auto_safety.FUNDED_TIERS == LOCKED.FUNDED_TIERS, (
        "auto_safety.FUNDED_TIERS has drifted from config_funded_locked.FUNDED_TIERS. "
        "If this is a deliberate, audited funded re-certification, update "
        "config_funded_locked.py (and its evidence/funded_config.sha256) in the SAME "
        "commit. If not, this is unauthorized drift into live funded behavior — revert."
    )


def test_locked_file_matches_recorded_sha256():
    with open(_LOCKED_FILE, "rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    with open(_SHA_FILE) as f:
        recorded = f.read().strip()
    assert actual == recorded, (
        "config_funded_locked.py contents no longer match evidence/funded_config.sha256. "
        "FUNDED_CONFIG firewall: funded constants changed — requires funded "
        "re-certification + operator approval (see config_funded_locked.py header)."
    )
