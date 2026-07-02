"""
Sentinel exit-accounting tests (P-sentinel-exit-accounting).

Tests that:
  1. A long-10 resolution clears expected to 0 (no false MISSING/DIRECTION noise on next poll).
  2. A stop-out followed by an opposite-side B entry produces the correct expected (no false DIRECTION_MISMATCH).
  3. The guardian on_flatten_ok callback resets expected to 0.
  4. The double-decrement clamp never crosses zero into a phantom opposite-sign position.

These tests use the sentinel / guardian APIs directly; the wiring in _record_resolved / _engine_bar
is exercised by the suite's other integration tests.
"""
import pytest
from unittest.mock import MagicMock
import trade_results
from live_readback import ReadbackSentinel
from flatten_guardian import FlattenGuardian


# ---------------------------------------------------------------------------
# Helper: mirror the guard+clamp logic from _record_resolved so the tests are
# honest about what the implementation does, not just that the sentinel API works.
# ---------------------------------------------------------------------------
def _apply_a_exit(sentinel, direction, qty, notes=None):
    """Apply an A-row resolution the same way _record_resolved does:
    rejected/blocked guard first, then the signed decrement with the clamp guard."""
    nz = ",".join(notes) if isinstance(notes, (list, tuple)) else (notes or "")
    if trade_results.is_rejected(nz):
        return                       # gate stopped the send: on_entry never fired -> no decrement
    signed_delta = -qty if direction == "long" else qty
    if abs(sentinel.expected) >= qty:
        sentinel.on_partial_or_exit(signed_delta)
    else:
        sentinel.on_flat()   # clamp: never leave a phantom opposite sign


# ---------------------------------------------------------------------------
# 1. Long entry → full resolution → expected == 0
# ---------------------------------------------------------------------------
def test_a_long_exit_clears_expected():
    """entry long 10 → resolved → expected returns to 0 (no MISSING/DIRECTION noise)."""
    s = ReadbackSentinel("APEX1")
    s.on_entry("long", 10)
    assert s.expected == 10
    _apply_a_exit(s, "long", 10)
    assert s.expected == 0


# ---------------------------------------------------------------------------
# 2. Stop-out → opposite-side B entry → expected == −5 (not the false +5 vs −5 mismatch)
# ---------------------------------------------------------------------------
def test_stop_out_then_b_short_no_direction_mismatch():
    """entry long 10 → stop-out resolved → B short 5 entry → expected == −5."""
    s = ReadbackSentinel("APEX1")
    s.on_entry("long", 10)
    assert s.expected == 10
    _apply_a_exit(s, "long", 10)   # A stop-out
    assert s.expected == 0
    # B signals short (via on_b_signal → readback.on_entry)
    s.on_entry("short", 5)
    assert s.expected == -5        # clean −5, not the stale +10 → +5 scenario


# ---------------------------------------------------------------------------
# 3. Guardian EOD/kill flatten → on_flatten_ok fires → expected == 0
# ---------------------------------------------------------------------------
def test_guardian_flatten_ok_resets_sentinel():
    """After a successful guardian flatten, on_flatten_ok is called → expected == 0."""
    s = ReadbackSentinel("APEX1")
    s.on_entry("long", 10)
    assert s.expected == 10

    mock_sender = MagicMock()
    mock_sender.flatten.return_value = {"ok": True, "cancel": {}, "exit": {}}
    mock_store = MagicMock()
    mock_store.get_state.return_value = None

    g = FlattenGuardian("APEX1", sender=mock_sender, store=mock_store,
                        on_flatten_ok=s.on_flat)
    g._flatten("EOD")
    assert s.expected == 0


def test_guardian_flatten_fail_does_not_reset_sentinel():
    """A failed guardian flatten (ok=False) must NOT call on_flatten_ok."""
    s = ReadbackSentinel("APEX1")
    s.on_entry("long", 10)

    mock_sender = MagicMock()
    mock_sender.flatten.return_value = {"ok": False, "cancel": {}, "exit": {}}
    mock_store = MagicMock()
    mock_store.get_state.return_value = None

    g = FlattenGuardian("APEX1", sender=mock_sender, store=mock_store,
                        on_flatten_ok=s.on_flat)
    g._flatten("EOD")
    assert s.expected == 10   # unchanged: flatten didn't succeed


# ---------------------------------------------------------------------------
# 4. Double-decrement guard: never crosses zero into a phantom opposite sign
# ---------------------------------------------------------------------------
def test_double_decrement_clamp_prevents_phantom_sign():
    """Second decrement on an already-flat expected uses on_flat(), never goes negative."""
    s = ReadbackSentinel("APEX1")
    s.on_entry("long", 10)
    _apply_a_exit(s, "long", 10)   # first exit: expected → 0
    assert s.expected == 0
    _apply_a_exit(s, "long", 10)   # second exit (double-decrement): clamp → on_flat()
    assert s.expected == 0         # NOT −10


def test_short_double_decrement_clamp():
    """Same guard for a short entry: second decrement stays at 0, not +10."""
    s = ReadbackSentinel("APEX1")
    s.on_entry("short", 10)
    assert s.expected == -10
    _apply_a_exit(s, "short", 10)  # first exit: expected → 0
    assert s.expected == 0
    _apply_a_exit(s, "short", 10)  # second exit: clamp → on_flat()
    assert s.expected == 0         # NOT +10


# ---------------------------------------------------------------------------
# 5. Rejected/blocked rows must NOT touch expected (they never called on_entry)
# ---------------------------------------------------------------------------
def test_rejected_row_does_not_decrement_expected():
    """A resolved row with a rejected note must NOT change expected while a real
    +10 expectation is outstanding (else: false ORPHAN BLACK -> flatten of healthy position)."""
    s = ReadbackSentinel("APEX1")
    s.on_entry("long", 10)                       # the REAL open A position
    assert s.expected == 10
    # a gate-rejected 10-qty row resolves — tracker rows carry a `notes` LIST (paper_live)
    _apply_a_exit(s, "long", 10, notes=["rejected_by_mffu:too_close_to_floor"])
    assert s.expected == 10                      # untouched: no phantom decrement


def test_blocked_row_does_not_decrement_expected():
    """Same guard for the 'blocked' marker (is_rejected matches both)."""
    s = ReadbackSentinel("APEX1")
    s.on_entry("short", 5)
    _apply_a_exit(s, "short", 5, notes=["blocked:daily_stop"])
    assert s.expected == -5                      # untouched


# ---------------------------------------------------------------------------
# 6. on_flatten_ok=None (default) does not error
# ---------------------------------------------------------------------------
def test_guardian_no_callback_is_safe():
    """FlattenGuardian with no on_flatten_ok does not error on successful flatten."""
    mock_sender = MagicMock()
    mock_sender.flatten.return_value = {"ok": True, "cancel": {}, "exit": {}}
    mock_store = MagicMock()
    mock_store.get_state.return_value = None

    g = FlattenGuardian("APEX1", sender=mock_sender, store=mock_store)
    g._flatten("EOD")   # must not raise
