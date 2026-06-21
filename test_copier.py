"""Multi-account copier v1 — fan-out, per-account sizing/P3, rotation, isolation,
per-account dedup, daily-stop, EXITLOCK per book."""
import os
import pytest

import bridge_sender
from bridge_sender import BridgeSender
from store import Store
from journal import Journal
from copier import AccountBook, MultiAccountCopier, load_books, ZEUS_MAX_SPECS

A_SIG = dict(side="short", entry=21000.0, stop=21020.0, target=20960.0, ts_signal="t", liq="pdh")
B_SIG = dict(side="long", entry=21000.0, stop=20975.0, target=21037.5, ts_signal="tb", liq="orb")


class SpySender:
    def __init__(self, mode="dry-run", fail=False):
        self.mode = mode; self.fail = fail; self.exit3 = []; self.singles = []
    def send_exit3(self, legs, account, root="MNQ"):
        if self.fail: raise RuntimeError("boom")
        self.exit3.append((account, legs)); return dict(ok=True)
    def send(self, payload, **k):
        if self.fail: raise RuntimeError("boom")
        self.singles.append(payload); return dict(sent=True)


def _book(tmp_path, acct, tier="150K-balanced", funded=False, fail=False, mode="dry-run"):
    st = Store(str(tmp_path / f"{acct}.db"))
    return AccountBook(acct, "topstep", tier, SpySender(mode, fail), funded=funded, mode=mode, store=st)


# ---- fan-out + per-account sizing ----
def test_a_fans_out_to_all_books(tmp_path):
    books = [_book(tmp_path, "T1"), _book(tmp_path, "T2"), _book(tmp_path, "M1")]
    cop = MultiAccountCopier(books)
    res = cop.route_a(A_SIG, "t")
    assert len(res) == 3
    for b in books:
        assert len(b.sender.exit3) == 1                  # each account got the A order
        legs = b.sender.exit3[0][1]
        assert sum(L["qty"] for L in legs) == 8          # 150K-balanced A8 -> split 4+4

def test_b_fans_out_single_bracket(tmp_path):
    books = [_book(tmp_path, "T1"), _book(tmp_path, "T2")]
    cop = MultiAccountCopier(books)
    cop.route_b(B_SIG, "t")
    for b in books:
        assert len(b.sender.singles) == 1
        assert b.sender.singles[0]["quantity"] == 4      # 150K-balanced B4

def test_per_account_distinct_signalids(tmp_path):
    books = [_book(tmp_path, "T1"), _book(tmp_path, "T2")]
    MultiAccountCopier(books).route_a(A_SIG, "t")
    ids = [b.sender.exit3[0][1][0]["payload"]["extras"]["signalId"] for b in books]
    assert len(set(ids)) == 2                            # per-account dedup keys differ


# ---- P3 per-account ----
def test_p3_brakes_only_the_drawn_down_book(tmp_path):
    healthy = _book(tmp_path, "T1"); drawn = _book(tmp_path, "T2")
    drawn.update_pnl(-2800)                              # 150K dd 4500 -> cushion 1700 < 1800 -> braked
    cop = MultiAccountCopier([healthy, drawn])
    cop.route_a(A_SIG, "t")
    assert sum(L["qty"] for L in healthy.sender.exit3[0][1]) == 8    # full
    assert sum(L["qty"] for L in drawn.sender.exit3[0][1]) == 4      # max(8//2,1)=4 braked
    assert drawn.p3.braked and not healthy.p3.braked

def test_p3_brake_zeros_b_on_drawn_book(tmp_path):
    drawn = _book(tmp_path, "T2"); drawn.update_pnl(-2800)
    cop = MultiAccountCopier([drawn])
    cop.route_b(B_SIG, "t")
    assert drawn.sender.singles == [] and drawn.blocked == 1         # B=0 when braked


# ---- rotation ----
def test_send_order_rotates(tmp_path):
    books = [_book(tmp_path, "T1"), _book(tmp_path, "T2"), _book(tmp_path, "T3")]
    cop = MultiAccountCopier(books)
    first = [cop.route_a(dict(A_SIG, ts_signal=f"s{i}"), "t")[0][0] for i in range(3)]
    assert len(set(first)) == 3                          # the first-sent account rotates across signals


# ---- isolation ----
def test_one_book_failure_does_not_block_others(tmp_path):
    good1 = _book(tmp_path, "T1"); bad = _book(tmp_path, "T2", fail=True); good2 = _book(tmp_path, "T3")
    res = dict(MultiAccountCopier([good1, bad, good2]).route_a(A_SIG, "t"))
    assert "ERROR" in res["T2"]
    assert len(good1.sender.exit3) == 1 and len(good2.sender.exit3) == 1   # others still sent


# ---- daily stop per book ----
def test_daily_stop_skips_only_that_book(tmp_path, monkeypatch):
    b1 = _book(tmp_path, "T1"); b2 = _book(tmp_path, "T2")
    monkeypatch.setattr(b1, "daily_stopped", lambda: True)
    MultiAccountCopier([b1, b2]).route_a(A_SIG, "t")
    assert b1.sender.exit3 == [] and len(b2.sender.exit3) == 1


# ---- EXITLOCK gates every book (real sender, live, no flag) ----
def test_exitlock_blocks_every_book_live(tmp_path):
    d = tmp_path / "approvals"; d.mkdir(); (d / "traderspost-approved.flag").write_text("x")
    bridge_sender.APPROVAL_DIR = str(d)                  # flag dir WITHOUT exit-model-approved.flag
    books = []
    for acct in ("T1", "T2"):
        st = Store(str(tmp_path / f"{acct}.db"))
        snd = BridgeSender(store=st, journal=Journal(str(tmp_path / f"{acct}j.db")),
                           mode="live", live_url="https://x/wh")
        books.append(AccountBook(acct, "topstep", "150K-balanced", snd, mode="live", store=st))
    res = dict(MultiAccountCopier(books).route_a(A_SIG, "t"))
    assert all(r == "ENTRY_ABORTED" for r in res.values())   # core leg blocked by exit-model gate


# ---- registry ----
def test_zeus_max_specs_is_8x150k():
    assert len(ZEUS_MAX_SPECS) == 8
    assert sum(s["firm"] == "topstep" for s in ZEUS_MAX_SPECS) == 5
    assert sum(s["firm"] == "mffu" for s in ZEUS_MAX_SPECS) == 3
    assert all(s["tier"] == "150K-balanced" for s in ZEUS_MAX_SPECS)

def test_load_books_paper(tmp_path):
    books = load_books([dict(account_id="T1", firm="topstep", tier="50K-conservative")],
                       mode="paper", store_factory=lambda: Store(str(tmp_path / "s.db")))
    assert len(books) == 1 and books[0].tier["am"] == 3
