"""Tests for tools_doc_consistency.py.

Asserts:
  1. The live repo docs are consistent (scanner returns 0).
  2. A synthetic living .md with a forbidden pattern (SINGLE_1R) and no banner IS flagged.
"""

import os
import sys
import tempfile
import shutil
import importlib

import pytest

# ---------------------------------------------------------------------------
# Import the scanner as a module so we can call scan() directly with a custom
# root, without having to subprocess-spawn it.
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))

# Make sure the repo root is on sys.path so we can import tools_doc_consistency
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import tools_doc_consistency  # noqa: E402  (must be after sys.path patch)


# ---------------------------------------------------------------------------
# Test 1: Real repo docs must be consistent (main() returns 0).
# ---------------------------------------------------------------------------

def test_live_docs_consistent(capsys):
    """tools_doc_consistency.main() must return 0 on the real repo."""
    result = tools_doc_consistency.main()
    captured = capsys.readouterr()
    assert result == 0, (
        f"Doc consistency scanner returned {result} — there are stale-machine "
        f"references in living docs.\n\nScanner output:\n{captured.out}"
    )


# ---------------------------------------------------------------------------
# Test 2: A synthetic living doc with SINGLE_1R and no banner IS flagged.
# ---------------------------------------------------------------------------

def _run_scan_in_tmpdir(md_filename: str, md_content: str):
    """
    Create a temporary directory that looks like the repo root (with just one
    .md file), run tools_doc_consistency.scan() against it, and return the
    (violations, allowed) tuple.

    We monkey-patch tools_doc_consistency.ROOT to point at the temp dir so
    the scanner's os.walk() only sees our synthetic file.
    """
    tmp = tempfile.mkdtemp()
    try:
        md_path = os.path.join(tmp, md_filename)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        original_root = tools_doc_consistency.ROOT
        tools_doc_consistency.ROOT = tmp
        try:
            violations, allowed = tools_doc_consistency.scan()
        finally:
            tools_doc_consistency.ROOT = original_root

        return violations, allowed
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_synthetic_stale_doc_is_flagged():
    """
    A .md file containing SINGLE_1R with no OBSOLETE/SUPERSEDED banner
    must produce at least one violation.
    """
    content = (
        "# My Notes\n\n"
        "The strategy uses SINGLE_1R exits which are great.\n"
    )
    violations, allowed = _run_scan_in_tmpdir("MY_NOTES.md", content)
    assert len(violations) >= 1, (
        "Expected at least one violation for SINGLE_1R in a file without a banner, "
        f"but got 0 violations (allowed={allowed})."
    )
    hits = [v[2] for v in violations]
    assert any("SINGLE_1R" in h for h in hits), (
        f"Expected SINGLE_1R in the violation hits, got: {hits}"
    )


def test_synthetic_stale_doc_with_banner_is_allowed():
    """
    The same SINGLE_1R content IS allowed when the file carries an OBSOLETE banner
    in the first six lines.
    """
    content = (
        "> OBSOLETE — this file describes a retired configuration.\n\n"
        "# My Notes\n\n"
        "The strategy uses SINGLE_1R exits which are great.\n"
    )
    violations, allowed = _run_scan_in_tmpdir("MY_NOTES.md", content)
    assert len(violations) == 0, (
        f"Expected 0 violations for a bannered file, got: {violations}"
    )
