"""Fan-out INTEGRATION — A/B/Momentum signals routed by the live LiveAuto reach the Apex SecondaryBook at
Apex size + webhook; the primary (MFFU) is unchanged; the journal feeds the book's scaled P&L (kill-guard)."""
import pandas as pd
import pytest

from auto_live import LiveAuto
from bridge_sender import BridgeSender
from store import Store
from journal import Journal
from fanout_book import SecondaryBook
from trade_journal import TradeJournal
from auto_safety import EVAL_TIERS

A_SIG = dict(side="short", entry=30654.83, stop=30771.50, target=30421.49,
             ts_signal="2026-06-30T13:46:00+00:00", liq="pdh")
B_SIG = dict(side="long", entry=30000.0, stop=29950.0, target=30075.0,
             ts_signal="2026-06-30T13:50:00+00:00", liq="orb", profile="B")


def _cap_sender(tmp_path, name):
    s = BridgeSender(store=Store(str(tmp_path / f"{name}s.db")), journal=Journal(str(tmp_path / f"{name}j.db")), mode="dry-run")
    cap = []; _o = s.send
    s.send = lambda p, **k: (cap.append(p), _o(p, **k))[1]
    return s, cap


def test_signals_fan_out_to_apex_book_at_apex_size(tmp_path):
    ps, pcap = _cap_sender(tmp_path, "p")
    auto = LiveAuto("MFFU-50K-1", "50K-balanced", "paper", Store(str(tmp_path / "st.db")),
                    Journal(str(tmp_path / "jj.db")), ps, 700, d1c_mode="OFF")
    auto.cushion_fn = lambda: (1500.0, 2000.0)
    bs, bcap = _cap_sender(tmp_path, "b")
    auto.books.append(SecondaryBook("APEX-50K-1", EVAL_TIERS["Apex-50K-eval"], bs, "paper"))

    auto.on_decision(A_SIG, True, "placed", pd.Timestamp(A_SIG["ts_signal"]))
    assert sum(p["quantity"] for p in pcap) == 4              # primary MFFU A4 (unchanged)
    assert sum(p["quantity"] for p in bcap) == 8              # Apex book A8
    assert all(p["extras"]["account"] == "APEX-50K-1" for p in bcap)

    pcap.clear(); bcap.clear()
    auto.on_b_signal(B_SIG, pd.Timestamp(B_SIG["ts_signal"]))
    assert sum(p["quantity"] for p in pcap) == 2              # MFFU B2
    assert sum(p["quantity"] for p in bcap) == 4              # Apex book B4


def test_primary_unaffected_with_no_books(tmp_path):
    ps, pcap = _cap_sender(tmp_path, "p")
    auto = LiveAuto("MFFU-50K-1", "50K-balanced", "paper", Store(str(tmp_path / "st.db")),
                    Journal(str(tmp_path / "jj.db")), ps, 700, d1c_mode="OFF")
    auto.cushion_fn = lambda: (1500.0, 2000.0)
    auto.on_decision(A_SIG, True, "placed", pd.Timestamp(A_SIG["ts_signal"]))
    assert sum(p["quantity"] for p in pcap) == 4 and auto.books == []   # MFFU alone, untouched


def test_journal_feeds_book_kill_guard(tmp_path):
    bs, bcap = _cap_sender(tmp_path, "b")
    book = SecondaryBook("APEX-50K-1", EVAL_TIERS["Apex-50K-eval"], bs, "paper")
    j = TradeJournal("MFFU-50K-1", "paper", path_dir=str(tmp_path)); j.books = [book]
    # A stop-out: r=-1, |entry-stop|=44 -> at the book's A8 that's -1*44*2*8 = -$704 -> crosses the -$700 kill
    j.on_resolved("A", "long", 4, 20000, 19956, 20088, 19956, "stop", -1.0, -352, "2026-06-30 10:00:00-04:00")
    assert book.halted() and "kill" in book.halt_reason
    assert any(p.get("action") == "exit" for p in bcap)       # book flattened the Apex account
