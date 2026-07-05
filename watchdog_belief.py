"""WATCHDOG BELIEF BRIDGE — the engine's side of the independent reconciliation watchdog.

This module is the ONLY thing auto_live.py imports for the watchdog. It is deliberately
lightweight (no CDP, no bridge, no heavy deps) so the three guarded engine touches stay cheap
and cannot drag trading-critical imports.

FAIL-CLOSED POLARITY (opposite of fill_telemetry, which is fail-open): the watchdog's whole
job is to eventually BLOCK entries when it is absent. So `watchdog_entry_block()` returns a
BLOCK REASON (truthy) on any doubt (missing/stale watchdog heartbeat, HALT flag present, or an
internal error) — the engine's `killed()` gate treats a truthy return as "no new entries". A
dead watchdog therefore blocks entries; it never touches open positions or exits.

Three things live here, each called from exactly one additive, guarded site in auto_live.py:
  * publish_belief(auto)        -> writes out/watchdog/belief.json (what the engine BELIEVES).
  * watchdog_entry_block(...)   -> the killed() fail-closed gate body (armed by WATCHDOG_ENFORCE).
  * verify_eval_config_hashes() -> arm-time config-integrity check vs evidence/eval_config.sha256.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fill_telemetry import account_tag   # sha1(account)[:8] — NEVER the raw account id

NY = ZoneInfo("America/New_York")

WATCHDOG_DIR = "out/watchdog"
BELIEF_PATH = os.path.join(WATCHDOG_DIR, "belief.json")
HEARTBEAT_PATH = os.path.join(WATCHDOG_DIR, "heartbeat.json")
HALT_FLAG_PATH = os.path.join(WATCHDOG_DIR, "HALT.flag")

# OPERATIONAL CONSTANTS — not research parameters (see watchdog.py for the full block).
WATCHDOG_HEARTBEAT_MAX_AGE_S = 90     # engine entry-gate: a watchdog heartbeat older than this = block

_EVIDENCE_SHA = os.path.join("evidence", "eval_config.sha256")
_GUARDED_CONFIG_FILES = ("config_defaults.py", "auto_safety.py")   # live files the watchdog pins by hash


def _et_date(now_utc=None):
    now_utc = now_utc or datetime.now(timezone.utc)
    return now_utc.astimezone(NY).date().isoformat()


def _atomic_write_json(path, obj):
    """Atomic = write tmp + os.replace, so a watchdog read never sees a half-written belief."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def _registry_sids(auto):
    """Best-effort sids of resting entry legs from the fill-telemetry registry.

    Each EXIT3 entry leg carries its own stopLoss+takeProfit, so a registered resting-entry sid
    IS a bracket sid. LIMITATION (documented, v1): the fill-telemetry registry deregisters a leg
    once its fill confirms, so after a fill the belief carries no sids for the now-open position.
    The watchdog's ORPHAN/UNPROTECTED invariant is written to tolerate this — it keys primarily on
    expected_net vs the panel's working-order COUNT (flat-with-orders / open-with-no-orders), and
    only uses these sids for finer-grained id matching when they are present."""
    entry_sids, bracket_sids = [], []
    ft = getattr(auto, "fill_telem", None)
    reg = getattr(ft, "_registry", None) if ft is not None else None
    if not isinstance(reg, dict):
        return entry_sids, bracket_sids
    for sid, r in list(reg.items()):
        if sid is None:
            continue
        entry_sids.append(str(sid))
        if r.get("stop") is not None or r.get("target") is not None:
            bracket_sids.append(str(sid))
    return entry_sids, bracket_sids


def publish_belief(auto, path=BELIEF_PATH, now_utc=None):
    """Snapshot what the ENGINE believes and write it atomically for the watchdog to reconcile.

    Best-effort and defensive: reads only already-computed engine state (no gates re-entered, no
    orders touched). The single call site in auto_live is itself wrapped in try/except; this inner
    guard is belt-and-braces so a belief-write error can never bubble into the order path."""
    try:
        now_utc = now_utc or datetime.now(timezone.utc)
        account = getattr(auto, "account", None)
        rb = getattr(auto, "readback", None)
        expected_net = int(getattr(rb, "expected", 0) or 0) if rb is not None else 0
        entry_sids, bracket_sids = _registry_sids(auto)
        try:
            import trade_results
            day_pnl = float(trade_results.day_entered_pnl(account, _et_date(now_utc)))
        except Exception:   # noqa: BLE001 — ledger unreadable must not block the belief snapshot
            day_pnl = None
        belief = {
            "ts_utc": now_utc.isoformat(),
            "account_tag": account_tag(account),
            "expected_net": expected_net,
            "open_entry_sids": entry_sids,
            "claimed_bracket_sids": bracket_sids,
            "day_internal_pnl": day_pnl,
            "engine_pid": os.getpid(),
        }
        _atomic_write_json(path, belief)
        return belief
    except Exception as e:   # noqa: BLE001 — belief publishing is observational; NEVER raise into the engine
        print(f"[watchdog-belief] ⚠ publish_belief error: {e!r}", flush=True)
        return None


def _heartbeat_age_s(path, now_utc):
    try:
        with open(path) as f:
            hb = json.load(f)
    except Exception:   # noqa: BLE001 — missing/corrupt heartbeat -> unknown age
        return None
    ts = hb.get("ts")
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now_utc - dt).total_seconds()
    except Exception:   # noqa: BLE001
        return None


def watchdog_entry_block(hb_path=HEARTBEAT_PATH, halt_path=HALT_FLAG_PATH,
                         now_utc=None, max_age_s=WATCHDOG_HEARTBEAT_MAX_AGE_S):
    """FAIL-CLOSED entry gate body (armed only when WATCHDOG_ENFORCE=1 — the caller checks the env).

    Returns a BLOCK-REASON string when new entries must be refused, or None when they may proceed.
    Blocks when the watchdog heartbeat is missing/stale (>max_age_s) OR the watchdog raised HALT —
    a dead watchdog blocks new entries, never positions/exits. fail-closed BY DESIGN."""
    now_utc = now_utc or datetime.now(timezone.utc)
    try:
        if os.path.exists(halt_path):
            return "watchdog HALT.flag present"
        age = _heartbeat_age_s(hb_path, now_utc)
        if age is None:
            return "watchdog heartbeat missing/unreadable"
        if age > max_age_s:
            return f"watchdog heartbeat stale {age:.0f}s > {max_age_s}s"
        return None
    except Exception as e:   # noqa: BLE001 — even a gate ERROR must fail closed (block), never permit
        return f"watchdog gate error (fail-closed): {e!r}"


def _recorded_config_hashes(sha_path):
    out = {}
    with open(sha_path) as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            digest, name = ln.split()
            out[os.path.basename(name)] = digest
    return out


def verify_eval_config_hashes(repo_dir=None, sha_path=None):
    """Recompute config_defaults.py + auto_safety.py hashes vs evidence/eval_config.sha256.

    Returns (ok, mismatches). Used by the arm-time preflight (auto_live) AND the watchdog's
    CONFIG INTEGRITY invariant. A missing evidence file or unreadable target is itself a mismatch
    (fail-closed): we cannot certify integrity we cannot read."""
    repo_dir = repo_dir or os.path.dirname(os.path.abspath(__file__))
    sha_path = sha_path or os.path.join(repo_dir, _EVIDENCE_SHA)
    mismatches = []
    try:
        recorded = _recorded_config_hashes(sha_path)
    except Exception as e:   # noqa: BLE001
        return False, [f"cannot read {sha_path}: {e!r}"]
    for name in _GUARDED_CONFIG_FILES:
        want = recorded.get(name)
        if want is None:
            mismatches.append(f"{name}: no recorded hash")
            continue
        try:
            with open(os.path.join(repo_dir, name), "rb") as f:
                got = hashlib.sha256(f.read()).hexdigest()
        except Exception as e:   # noqa: BLE001
            mismatches.append(f"{name}: unreadable ({e!r})")
            continue
        if got != want:
            mismatches.append(f"{name}: hash drift")
    return (len(mismatches) == 0), mismatches
