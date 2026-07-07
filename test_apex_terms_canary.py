"""APEX COUNTERPARTY-TERMS CANARY — read-only drift instrumentation on Apex 50K rule constants.

This test file changes NOTHING behavioral. It only:
  1. Asserts the live code constants (apex_funded_40.py, tools_account_size_research.py) still
     equal the pinned snapshot in evidence/apex_terms/apex_terms.yaml (DRIFT GUARD). If Apex
     ever changes a real rule and the operator re-pins the yaml, every simulator still using the
     OLD number fails this test immediately — that failure is the intended forcing function
     (see evidence/apex_terms/apex_terms_review.md).
  2. Asserts the yaml snapshot matches its recorded SHA256 (HASH-INTEGRITY), mirroring
     test_eval_config_firewall.py's shasum mechanism.
  3. PASSES but loudly prints every UNVERIFIED/PLACEHOLDER entry so those known gaps ($8k/$131
     funded-value/fee placeholder; PENDING source citations on every Apex rule) stay visible
     rather than silently forgotten (PLACEHOLDER-VISIBILITY).
  4. WARNS (never fails) if any sibling apex_*.py file has independently re-declared one of these
     constants with a DIFFERENT literal than the pinned snapshot — a bonus partial-update drift
     catch, since these constants are duplicated as literals across ~10 files (see the yaml's
     `findings.duplication` section).

Model: test_eval_config_firewall.py (drift + hash-integrity mechanism) and
test_d1c_timestamp_canary.py (permanent regression-canary style / naming).

This test is READ-ONLY: it imports apex_funded_40 and tools_account_size_research only to read
their module-level constants. It does not call, patch, or execute any of their sizing/simulation
functions, and it does not modify any file the task marks forbidden (config_*.py, strategy_*.py,
drift_gate.py, watchdog.py, apex_funded_40.py, tools_account_size_research.py).
"""
import glob
import hashlib
import os
import re
import warnings

import apex_funded_40 as FUNDED40
import tools_account_size_research as ACCT

_HERE = os.path.dirname(os.path.abspath(__file__))
_TERMS_DIR = os.path.join(_HERE, "evidence", "apex_terms")
_YAML_FILE = os.path.join(_TERMS_DIR, "apex_terms.yaml")
_SHA_FILE = os.path.join(_TERMS_DIR, "apex_terms.sha256")


# ── minimal, schema-specific YAML reader ──────────────────────────────────────────────
# This repo's requirements.txt does not include PyYAML, and adding a new dependency is out of
# scope for a read-only canary. apex_terms.yaml has one fixed, hand-authored shape (a top-level
# `constants:` block of 2-space-indented keys, each with scalar or flow-list `value:` /
# `confidence:` / `source:` lines) — this parser reads exactly that shape and nothing more. It is
# NOT a general YAML parser.
def _parse_apex_terms_yaml(path):
    constants = {}
    cur = None
    in_constants = False
    with open(path) as f:
        for raw in f:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped == "constants:":
                in_constants = True
                continue
            if in_constants and stripped in ("findings:",):
                break
            if not in_constants:
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent == 2 and stripped.endswith(":"):
                cur = stripped[:-1]
                constants[cur] = {}
                continue
            if cur is None:
                continue
            m = re.match(r"^(value|confidence|source|value_note|lifetime_cap|rungs):\s*(.*)$", stripped)
            if not m:
                continue
            key, val = m.group(1), m.group(2).strip()
            if key == "value" and val.startswith("["):
                items = val.strip("[]").split(",")
                constants[cur][key] = [float(x.strip()) for x in items if x.strip()]
            elif key in ("value", "lifetime_cap", "rungs"):
                try:
                    constants[cur][key] = float(val) if ("." in val) else int(val)
                except ValueError:
                    constants[cur][key] = val
            else:
                constants[cur][key] = val.strip('"')
    return constants


def _terms():
    return _parse_apex_terms_yaml(_YAML_FILE)


# ── 1. DRIFT GUARD ─────────────────────────────────────────────────────────────────────
def test_apex_funded_40_constants_match_pinned_snapshot():
    T = _terms()
    checks = [
        ("start_50k",              FUNDED40.START,       "apex_funded_40.py START"),
        ("eod_trail",               FUNDED40.TRAIL,       "apex_funded_40.py TRAIL"),
        ("lock_trigger_eod_peak",   FUNDED40.LOCK_EOD,    "apex_funded_40.py LOCK_EOD"),
        ("payout_floor",            FUNDED40.PAYOUT_FLOOR, "apex_funded_40.py PAYOUT_FLOOR"),
        ("min_req",                 FUNDED40.MIN_REQ,     "apex_funded_40.py MIN_REQ"),
        ("qual_day",                FUNDED40.QUAL_DAY,    "apex_funded_40.py QUAL_DAY"),
        ("qual_n",                  FUNDED40.QUAL_N,      "apex_funded_40.py QUAL_N"),
        ("consistency",             FUNDED40.CONSISTENCY, "apex_funded_40.py CONSISTENCY"),
        ("payout_cadence_days",     FUNDED40.PAYOUT_EVERY_D, "apex_funded_40.py PAYOUT_EVERY_D"),
    ]
    for key, live_val, loc in checks:
        pinned = T[key]["value"]
        assert live_val == pinned, (
            f"DRIFT: constant '{key}' — live {loc} = {live_val!r}, "
            f"pinned evidence/apex_terms/apex_terms.yaml = {pinned!r}. "
            "If this is a deliberate, audited Apex terms change, re-pin apex_terms.yaml "
            "(re-hash apex_terms.sha256) per apex_terms_review.md — this is a re-cert event, "
            "not a silent edit. If not, revert the code change."
        )

    # ladder is a list — compare element-wise
    pinned_ladder = T["payout_ladder"]["value"]
    assert list(FUNDED40.LADDER) == pinned_ladder, (
        f"DRIFT: constant 'payout_ladder' — live apex_funded_40.py LADDER = {list(FUNDED40.LADDER)!r}, "
        f"pinned = {pinned_ladder!r}."
    )

    # DLL / DAILY_STOP are stored SIGNED in apex_funded_40.py (negative) but as positive
    # magnitudes in both the yaml snapshot and tools_account_size_research.SPECS — normalize by
    # comparing magnitudes, and document the sign convention explicitly here.
    pinned_dll = T["dll_50k"]["value"]
    assert abs(FUNDED40.DLL) == pinned_dll, (
        f"DRIFT: constant 'dll_50k' (magnitude) — live apex_funded_40.py DLL = {FUNDED40.DLL!r} "
        f"(magnitude {abs(FUNDED40.DLL)!r}), pinned = {pinned_dll!r}."
    )
    pinned_stop = T["bot_daily_stop"]["value"]
    assert abs(FUNDED40.DAILY_STOP) == pinned_stop, (
        f"DRIFT: constant 'bot_daily_stop' (magnitude) — live apex_funded_40.py DAILY_STOP = "
        f"{FUNDED40.DAILY_STOP!r} (magnitude {abs(FUNDED40.DAILY_STOP)!r}), pinned = {pinned_stop!r}."
    )


def test_tools_account_size_research_constants_match_pinned_snapshot():
    T = _terms()
    spec50 = ACCT.SPECS["50K"]
    checks = [
        ("start_50k",       spec50["start"],  "tools_account_size_research.py SPECS['50K']['start']"),
        ("eod_trail",       spec50["trail"],  "tools_account_size_research.py SPECS['50K']['trail']"),
        ("profit_target",   spec50["target"], "tools_account_size_research.py SPECS['50K']['target']"),
        ("dll_50k",         spec50["dll"],    "tools_account_size_research.py SPECS['50K']['dll']"),
        ("bot_daily_stop",  spec50["stop"],   "tools_account_size_research.py SPECS['50K']['stop']"),
        ("eval_expiry_days", ACCT.EXPIRE_DAYS, "tools_account_size_research.py EXPIRE_DAYS"),
    ]
    for key, live_val, loc in checks:
        pinned = T[key]["value"]
        assert live_val == pinned, (
            f"DRIFT: constant '{key}' — live {loc} = {live_val!r}, "
            f"pinned evidence/apex_terms/apex_terms.yaml = {pinned!r}."
        )

    pinned_ladder = T["payout_ladder"]["value"]
    assert [float(x) for x in spec50["ladder"]] == pinned_ladder, (
        f"DRIFT: constant 'payout_ladder' — live SPECS['50K']['ladder'] = {spec50['ladder']!r}, "
        f"pinned = {pinned_ladder!r}."
    )

    # MAX_A_QTY is NOT an Apex-published counterparty term (it's this repo's own internal
    # research ceiling on A-size, unrelated to any Apex rule) — it has no entry in the
    # STEP-2 pin list handed down for this task, but the task spec explicitly asked for it to
    # be imported/asserted here for canary completeness, so it is pinned in the yaml with
    # confidence: INTERNAL (distinct from UNVERIFIED/PLACEHOLDER) to keep the honesty
    # distinction clean. Flagged in the task report for auditor sign-off.
    pinned_max_qty = T["max_a_qty"]["value"]
    assert ACCT.MAX_A_QTY == pinned_max_qty, (
        f"DRIFT: constant 'max_a_qty' — live tools_account_size_research.py MAX_A_QTY = "
        f"{ACCT.MAX_A_QTY!r}, pinned = {pinned_max_qty!r}."
    )


def test_funded_40_lock_eod_and_min_req_share_same_value():
    """apex_funded_40.py deliberately reuses LOCK_EOD's value for MIN_REQ (both = start+trail+100
    for the 50K account) — pin that this is still true, so a future edit that only bumps one of
    the two doesn't silently break the (currently accidental) equality this snapshot documents."""
    assert FUNDED40.LOCK_EOD == FUNDED40.MIN_REQ


# ── 2. HASH-INTEGRITY ──────────────────────────────────────────────────────────────────
def test_apex_terms_yaml_matches_recorded_sha256():
    with open(_YAML_FILE, "rb") as f:
        actual = hashlib.sha256(f.read()).hexdigest()
    with open(_SHA_FILE) as f:
        line = f.readline().strip()
    recorded = line.split()[0] if line else None
    assert actual == recorded, (
        "evidence/apex_terms/apex_terms.yaml contents no longer match "
        "evidence/apex_terms/apex_terms.sha256. APEX TERMS CANARY: the pinned snapshot changed — "
        "re-hash via `shasum -a 256 evidence/apex_terms/apex_terms.yaml > "
        "evidence/apex_terms/apex_terms.sha256` and re-run this canary; a snapshot change is a "
        "re-cert event (see evidence/apex_terms/apex_terms_review.md)."
    )


# ── 3. PLACEHOLDER-VISIBILITY (always PASSES; loud, non-failing) ──────────────────────
def test_placeholder_and_unverified_entries_stay_visible(capsys):
    T = _terms()
    placeholders = sorted(k for k, v in T.items() if v.get("confidence") == "PLACEHOLDER")
    unverified = sorted(k for k, v in T.items() if v.get("confidence") == "UNVERIFIED")

    lines = ["", "=" * 78,
             "APEX TERMS CANARY — PLACEHOLDER / UNVERIFIED VISIBILITY (informational, not a failure)",
             "=" * 78]
    lines.append(f"PLACEHOLDER entries ({len(placeholders)}) — NOT real Apex numbers, "
                 "never treat as authoritative:")
    for k in placeholders:
        lines.append(f"  - {k} = {T[k]['value']!r}  (source: {T[k].get('source', 'PENDING')})")
    lines.append(f"UNVERIFIED entries ({len(unverified)}) — Apex rule, source PENDING "
                 "(help-center-derived, not confirmed against a live contract):")
    for k in unverified:
        lines.append(f"  - {k} = {T[k]['value']!r}")
    lines.append("Re-verify all of the above per evidence/apex_terms/apex_terms_review.md "
                 "before any arming / re-certification event.")
    lines.append("=" * 78)
    banner = "\n".join(lines)

    print(banner)
    warnings.warn(
        f"APEX TERMS CANARY: {len(placeholders)} PLACEHOLDER + {len(unverified)} UNVERIFIED "
        "entries remain unconfirmed against a live Apex contract — see printed banner / "
        "evidence/apex_terms/apex_terms_review.md.",
        UserWarning,
    )

    # this is visibility, not a regression gate: must always PASS as long as the expected
    # placeholder/unverified entries are still marked (i.e. haven't been silently upgraded
    # to a confidence level that would hide them from this banner without a real re-verify).
    assert "funded_value_placeholder" in placeholders
    assert "eval_fee_placeholder" in placeholders
    assert len(unverified) >= 10   # every Apex-rule entry currently pinned

    captured = capsys.readouterr()
    assert "PLACEHOLDER" in captured.out


# ── 4. CROSS-FILE CONSISTENCY (bonus drift catch; WARN only, never fails) ─────────────
_ALIAS_TO_TERM = {
    "START": ("start_50k", False),
    "SB": ("start_50k", False),
    "TRAIL": ("eod_trail", False),
    "LOCK_EOD": ("lock_trigger_eod_peak", False),
    "FLOOR": ("locked_floor", False),
    "EXPIRE": ("eval_expiry_days", False),
    "EXPIRE_DAYS": ("eval_expiry_days", False),
    "DAILY_STOP": ("bot_daily_stop", True),   # signed -> compare magnitude
}
# apex_funded_40.py and tools_account_size_research.py are the canonical sources already
# checked directly above; test_apex_terms_canary.py itself and any non-apex_*.py file are
# excluded by the glob below.
_EXCLUDE = {"apex_funded_40.py"}


def _scan_literal_assignment(line):
    """Match `NAME[, NAME...] = val[, val...]` (tuple or single assignment of numeric
    literals, Python underscore-grouping allowed, optional trailing comment). Returns
    {name: float} for every NAME found, or {} if the line doesn't match."""
    m = re.match(r"^\s*([A-Z][A-Z0-9_]*(?:\s*,\s*[A-Z][A-Z0-9_]*)*)\s*=\s*([^\n#]+?)\s*(?:#.*)?$", line)
    if not m:
        return {}
    names = [n.strip() for n in m.group(1).split(",")]
    raw_vals = m.group(2)
    # split top-level commas only (values here are always flat numeric literals, no nested
    # brackets in the assignments this scanner targets)
    vals = [v.strip() for v in raw_vals.split(",")]
    if len(names) != len(vals):
        return {}
    out = {}
    for n, v in zip(names, vals):
        v = v.rstrip(",")
        try:
            out[n] = float(v.replace("_", ""))
        except ValueError:
            return {}
    return out


def test_cross_file_apex_constant_literals_no_silent_drift():
    """WARN (never fail) if any sibling apex_*.py file has independently re-declared
    START/TRAIL/LOCK_EOD/FLOOR/EXPIRE/DAILY_STOP with a literal that disagrees with the pinned
    snapshot. These constants are duplicated across ~10 files (see apex_terms.yaml
    findings.duplication) — this is a best-effort partial-update drift catch, not a guarantee
    (it only catches the specific assignment-statement shapes these files currently use)."""
    T = _terms()
    candidates = sorted(set(glob.glob(os.path.join(_HERE, "apex_*.py"))) | {os.path.join(_HERE, "_fleet_5yr.py")})
    mismatches = []
    scanned_files = []
    for path in candidates:
        base = os.path.basename(path)
        if base in _EXCLUDE or not os.path.isfile(path):
            continue
        scanned_files.append(base)
        with open(path, errors="ignore") as f:
            for lineno, line in enumerate(f, start=1):
                found = _scan_literal_assignment(line)
                for name, val in found.items():
                    if name not in _ALIAS_TO_TERM:
                        continue
                    term_key, is_signed = _ALIAS_TO_TERM[name]
                    pinned = T[term_key]["value"]
                    live = abs(val) if is_signed else val
                    if live != pinned:
                        mismatches.append(
                            f"{base}:{lineno}  {name} = {val!r} (as {'magnitude' if is_signed else 'value'} "
                            f"{live!r}) != pinned {term_key} = {pinned!r}"
                        )

    if mismatches:
        msg = ("APEX TERMS CANARY — cross-file literal DRIFT detected (partial-update risk; "
               "WARN only, does not fail this test):\n  " + "\n  ".join(mismatches))
        print("\n" + msg)
        warnings.warn(msg, UserWarning)
    else:
        print(f"\nAPEX TERMS CANARY — cross-file scan of {len(scanned_files)} sibling apex_*.py "
              f"file(s) found no literal disagreement with the pinned snapshot: {scanned_files}")

    # always passes — this check is a WARN-only bonus catch, per task spec
    assert True
