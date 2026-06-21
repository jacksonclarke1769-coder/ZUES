"""P3 brake — thresholds, hysteresis latch, sizing, fail-safe, restart."""
from p3_brake import P3Brake

DD = 2000.0          # 50K trailing-DD allowance ; on=$800, off=$1200


def test_brake_on_below_40pct():
    b = P3Brake()
    assert b.update(cushion=799, dd_allowance=DD) is True
    assert b.braked is True

def test_brake_off_at_or_above_60pct():
    b = P3Brake(braked=True)
    assert b.update(cushion=1200, dd_allowance=DD) is False

def test_hysteresis_holds_in_band():
    b = P3Brake()
    b.update(799, DD)                       # ON
    assert b.update(1000, DD) is True       # in [800,1200) -> HOLD braked
    b.update(1200, DD)                      # OFF
    assert b.update(1000, DD) is False      # in band -> HOLD unbraked

def test_sizing_braked_halves_A_and_zeros_B():
    b = P3Brake(braked=True)
    assert b.size(4, 2) == (2, 0)
    assert b.size(3, 2) == (1, 0)           # max(3//2,1)=1
    assert b.size(1, 1) == (1, 0)           # never below 1 A

def test_sizing_normal_is_full():
    b = P3Brake(braked=False)
    assert b.size(2, 1) == (2, 1)

def test_failsafe_bad_dd_brakes():
    assert P3Brake().update(cushion=5000, dd_allowance=0) is True
    assert P3Brake().update(cushion=5000, dd_allowance=None) is True
    assert P3Brake().update(cushion=None, dd_allowance=DD) is True

def test_snapshot_restore():
    b = P3Brake(); b.update(700, DD)
    s = b.snapshot()
    assert P3Brake.from_snapshot(s).braked is True
