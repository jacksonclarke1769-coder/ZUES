"""Same-bar fill-convention regression tests for tools_1m_truth_recert.walk_1m.

Provenance: retroactive fill-path audit of the FORK-A walker (2026-07-20), ordered after the
ICT concept survey caught a same-bar bug elsewhere (survey commit 652fdbf; vault
AUDIT-20260720-0941): a walker that CANCELS an order when entry and stop are touched on the
same 1m bar — instead of booking a filled-then-stopped loss — silently deletes the instant-loss
population and manufactures fictional edge that passes every statistical gate.

House convention (the correct one, locked here): a bar covering both entry-fill and stop is
scored FILLED-THEN-STOPPED (stop-first, loss booked, slip applied). Target/partials are never
credited on the fill bar. Do not "fix" these tests toward cancelling or skipping same-bar
trades — that was the bug.
"""
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools_1m_truth_recert as T1M


class FakeMap:
    """Minimal synthetic 1m frame implementing the M1Map interface walk_1m needs."""

    def __init__(self, H, L, C):
        self.H = np.array(H, float)
        self.L = np.array(L, float)
        self.C = np.array(C, float)
        self.ts1 = np.arange(len(H)).astype("datetime64[m]")

    def window(self, i5, n):
        return i5, min(i5 + n * 5, len(self.H))


def test_same_bar_entry_and_stop_books_loss_long():
    # long: entry 100, stop 99. Bar 0 touches both (H=101, L=98.5) -> filled-then-stopped.
    mp = FakeMap(H=[101, 104], L=[98.5, 100.5], C=[100, 104])
    r = T1M.walk_1m(mp, 0, +1, entry=100.0, stop=99.0, target=103.0,
                    partials=[], max_5m_bars=1)
    assert r is not None, "same-bar entry+stop was skipped/cancelled (the survey bug class)"
    assert r[0] < -0.9, f"same-bar stop not booked as a loss (realized={r[0]:.3f}R)"


def test_same_bar_entry_and_stop_books_loss_short():
    mp = FakeMap(H=[101.5, 99], L=[99.5, 97], C=[100, 98])
    r = T1M.walk_1m(mp, 0, -1, entry=100.0, stop=101.0, target=97.0,
                    partials=[], max_5m_bars=1)
    assert r is not None and r[0] < -0.9, f"short same-bar stop mis-scored (r={r})"


def test_fill_bar_target_not_credited():
    # fill bar touches entry AND target but not stop -> target must NOT be credited that bar.
    mp = FakeMap(H=[102, 100.4], L=[99.9, 100.0], C=[101, 100.2])
    r = T1M.walk_1m(mp, 0, +1, entry=100.0, stop=98.0, target=101.5,
                    partials=[], max_5m_bars=1)
    win_R = (101.5 - 100.0) / 2.0
    assert r is not None
    assert abs(r[0] - win_R) > 1e-9, (
        f"target credited on the fill bar (r={r[0]:.3f}R) — violates the conservative convention")


def test_stop_beats_target_on_same_later_bar():
    # after a clean fill, a later bar touching both stop and target must score stop-first.
    mp = FakeMap(H=[100.6, 103.0], L=[99.9, 97.5], C=[100.2, 99.0])
    r = T1M.walk_1m(mp, 0, +1, entry=100.0, stop=98.0, target=102.0,
                    partials=[], max_5m_bars=1)
    assert r is not None and r[0] < -0.9, f"ambiguous later bar not scored stop-first (r={r})"
