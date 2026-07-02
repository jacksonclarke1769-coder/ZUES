#!/usr/bin/env python3
"""ZEUS documentation consistency scanner (2026-07-02).

Fails if any LIVING doc states an OBSOLETE machine as current fact. Historical documents are
allowed to contain these phrases ONLY when they carry an OBSOLETE/SUPERSEDED banner in their first
~6 lines, or live under an exempt path (reports/, docs/tickets/, memory/, evidence/, the audit
report). This is the reconciliation rule from 2026-07-02, enforced in CI instead of by memory.

Usage:  python3 tools_doc_consistency.py            # scan, exit 1 on violation
        python3 tools_doc_consistency.py --list     # list every hit with its disposition
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# Phrases that describe a PRE-rev-b machine and must never appear as current fact in a living doc.
# (word-boundary / context patterns to avoid false hits on prose like "single" or "B")
FORBIDDEN = [
    (r"\bSINGLE_1R\b", "SINGLE_1R exit (demoted 2026-07-02 — EXIT3 is current)"),
    (r"\bsingle@1R\b", "single@1R exit (superseded by Exit#3)"),
    (r"Profile A \+ B\b", "Profile A+B (B is OFF in the current machine)"),
    (r"\bmomentum lane\b", "momentum lane (OFF in the current machine)"),
    (r"\bA10/B5\b", "A10/B5 sizing (old 21-MNQ book)"),
    (r"\b21 MNQ\b", "21 MNQ (old book; current is size-to-risk $1,200)"),
    (r"\bMFFU\b", "MFFU as firm (current firm is Apex 50K EOD)"),
    (r"\b150K\b", "150K plan (rejected; current is 50K)"),
    (r"HTF[- ]skip", "HTF skip (invalidated 2026-07-02, never armed)"),
    (r"\b63\.1\b", "63.1% pass (invalid SINGLE_1R number)"),
    (r"\b57\.5\b", "57.5% pass (superseded)"),
    (r"\b59\.8\b", "59.8% pass (superseded)"),
    (r"\b86%", "86% pass (fabricated, retired)"),
    (r"\$22\.1k|\$19\.4k", "old funded E[payout] (superseded by ~$12.7k ladder-capped)"),
]

BANNER_RE = re.compile(r"OBSOLETE|SUPERSEDED|INVALIDATED|historical", re.I)

# Living-doc scope: only these top-level docs + docs/ are enforced. Everything else is history.
EXEMPT_DIR_PREFIXES = ("reports/", "docs/tickets/", "memory/", "evidence/", "research/",
                       "backtests/", "dashboard/", ".git/")
EXEMPT_FILES = {"full-audit-2026-07-02.md"}
# These living docs legitimately NAME the old machine as history (audit trail / reconciliation).
# They must still carry the words inside a clearly-historical sentence; we allow them wholesale
# because their entire purpose is to record what changed.
HISTORY_LIVING = {"AGENTS.md"}


def _rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def scan(list_all=False):
    violations, allowed = [], []
    for dirpath, _dirs, files in os.walk(ROOT):
        for fn in files:
            if not fn.endswith(".md"):
                continue
            full = os.path.join(dirpath, fn)
            rel = _rel(full)
            if rel.startswith(EXEMPT_DIR_PREFIXES) or fn in EXEMPT_FILES:
                continue
            try:
                text = open(full, encoding="utf-8").read()
            except Exception:
                continue
            head = "\n".join(text.splitlines()[:6])
            has_banner = bool(BANNER_RE.search(head))
            is_history = fn in HISTORY_LIVING
            for pat, why in FORBIDDEN:
                for m in re.finditer(pat, text):
                    line = text[:m.start()].count("\n") + 1
                    rec = (rel, line, m.group(0), why)
                    if has_banner or is_history:
                        allowed.append(rec)
                    else:
                        violations.append(rec)
    return violations, allowed


def main():
    list_all = "--list" in sys.argv
    violations, allowed = scan(list_all)
    if list_all:
        for rel, line, hit, why in allowed:
            print(f"  ALLOWED  {rel}:{line}  {hit!r} — {why} (under banner/history)")
    for rel, line, hit, why in violations:
        print(f"  VIOLATION {rel}:{line}  {hit!r} — {why}")
    if violations:
        print(f"\n✗ {len(violations)} stale-machine reference(s) in living docs — "
              f"add an OBSOLETE banner or update to the current machine (README.md is truth).")
        return 1
    print(f"✓ docs consistent — no stale-machine claims in living docs "
          f"({len(allowed)} historical reference(s) allowed under banners).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
