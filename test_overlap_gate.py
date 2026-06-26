"""Overlap sizing gate — half-size the 2nd same-direction concurrent trade; fail-safe; restart-safe."""
import pytest
from overlap_gate import OverlapGate


def test_no_concurrent_position_full_size():
    g = OverlapGate()
    assert g.size("A", "long", 4) == (4, False)


def test_same_direction_other_strategy_halves():
    g = OverlapGate()
    g.on_open("A", "long")
    assert g.size("MOM", "long", 2) == (1, True)          # MOM long while A long -> half
    assert g.size("B", "long", 2) == (1, True)


def test_opposite_direction_full_size():
    g = OverlapGate()
    g.on_open("A", "long")
    assert g.size("MOM", "short", 2) == (2, False)         # opposite -> never gated (they never oppose anyway)


def test_self_does_not_gate_itself():
    g = OverlapGate()
    g.on_open("A", "long")
    assert g.size("A", "long", 4) == (4, False)            # A re-entry isn't a cross-strategy stack


def test_any_other_same_dir_triggers():
    g = OverlapGate()
    g.on_open("A", "short"); g.on_open("B", "short")
    assert g.size("MOM", "short", 2) == (1, True)


def test_close_clears_position():
    g = OverlapGate()
    g.on_open("A", "long")
    assert g.size("MOM", "long", 2)[1] is True
    g.on_close("A")
    assert g.size("MOM", "long", 2) == (2, False)          # A flat -> full size again


def test_rounding_floor_min_qty():
    g = OverlapGate()
    g.on_open("A", "long")
    assert g.size("X", "long", 4)[0] == 2                  # 4 -> 2
    assert g.size("X", "long", 2)[0] == 1                  # 2 -> 1
    assert g.size("X", "long", 3)[0] == 1                  # floor(1.5)=1
    assert g.size("X", "long", 1)[0] == 1                  # can't trade <1 micro -> stays 1 (no skip)


def test_disabled_passthrough():
    g = OverlapGate(enabled=False)
    g.on_open("A", "long")
    assert g.size("MOM", "long", 2) == (2, False)


def test_participants_restrict_gating():
    g = OverlapGate(participants={"A", "B", "MOM"})
    g.on_open("A", "long")
    assert g.size("MOM", "long", 2) == (1, True)
    g2 = OverlapGate(participants={"A", "B"})              # MOM not a participant -> not gated
    g2.on_open("A", "long")
    assert g2.size("MOM", "long", 2) == (2, False)


def test_fail_safe_on_bad_input():
    g = OverlapGate()
    g.on_open("A", "long")
    assert g.size("MOM", "long", "bad") == ("bad", False)  # swallowed -> returns base, no crash


def test_halved_counter_and_snapshot_restore():
    g = OverlapGate()
    g.on_open("A", "long")
    g.size("MOM", "long", 2); g.size("B", "long", 2)
    assert g.halved == 2
    snap = g.snapshot()
    g2 = OverlapGate(); g2.restore(snap)
    assert g2.open == {"A": 1} and g2.halved == 2
    assert g2.size("MOM", "long", 2) == (1, True)          # restored state still gates
