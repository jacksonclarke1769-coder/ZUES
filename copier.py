"""Multi-account copier v1 — one signal -> fan out to N accounts (ZEUS-MAX). The engine
(SimBot A + ProfileBEngine) runs ONCE upstream; the copier routes each A/B signal to every
AccountBook with that account's own size (P3 per-account cushion), TradersPost URL, signalId
(per-account dedup), journal, and B tracker.

Design invariants:
  * per-account ISOLATION — one account's send error never blocks the others (try/except per book)
  * send ROTATION — the send order rotates each signal so no account is always first
    (FENRIR-X rate-limit ordering bias); jitter/stagger is a deploy-time add in the sender
  * EXITLOCK still gates EVERY book's entries (each send goes through _live_ok)
  * Profile B NEVER consults D1c (handled upstream; B routes here unconditionally)
  * P3 per-account: v1 uses each book's OWN realized-P&L drawdown (sim-cushion); broker-truth
    balance is v3 (couples with the B1 recon path)
"""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import bridge_traderspost as BP
from p3_brake import P3Brake
from profile_b_tracker import ProfileBPaperTracker
from auto_safety import EVAL_TIERS, FUNDED_TIERS, DailyGuard
from store import Store

DD_ALLOWANCE = {"50K": 2000.0, "150K": 4500.0}   # trailing-DD allowance by account size


def _et_date():
    return datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")).date().isoformat()


class AccountBook:
    """All per-account state. The engine is shared; this is what differs per account."""
    def __init__(self, account_id, firm, tier_name, sender, funded=False, mode="paper",
                 store=None, b_tracker=None):
        self.account_id = account_id
        self.firm = firm
        self.tier_name = tier_name
        self.sender = sender
        self.mode = mode
        self.funded = funded
        self.tier = (FUNDED_TIERS if funded else EVAL_TIERS)[tier_name]
        self.dd = DD_ALLOWANCE[self.tier["account"]]
        self.p3 = P3Brake()
        self.guard = DailyGuard(store or Store())
        self.b_tracker = b_tracker or ProfileBPaperTracker(store, account_id, mode)
        self.realized = 0.0      # cumulative realized P&L (drives the sim-cushion)
        self.peak = 0.0
        self.sent = self.blocked = 0

    def cushion(self):
        """v1 sim-cushion = trailing-DD allowance minus the current drawdown from peak."""
        return self.dd - max(self.peak - self.realized, 0.0)

    def update_pnl(self, delta):
        self.realized += float(delta)
        self.peak = max(self.peak, self.realized)

    def size(self, profile):
        self.p3.update(self.cushion(), self.dd)
        a, b = self.p3.size(self.tier["am"], self.tier["bm"])
        return a if profile == "A" else b

    def daily_stopped(self):
        try:
            return bool(self.guard.is_stopped(self.account_id, _et_date()))
        except Exception:                                # noqa: BLE001
            return False


class MultiAccountCopier:
    def __init__(self, books, logger=None):
        self.books = list(books)
        self.logger = logger
        self._rot = 0

    def _ordered(self):
        """Rotate the send order each signal so no account is always first."""
        n = len(self.books)
        if n == 0:
            return []
        self._rot = (self._rot + 1) % n
        return self.books[self._rot:] + self.books[:self._rot]

    def _dlog(self, **k):
        try:
            if self.logger:
                self.logger.log(k.pop("final_action", "skipped"), **k)
        except Exception:                                # noqa: BLE001
            pass

    # ---- fan-out: Profile A (Exit #3 two-leg) ----
    def route_a(self, sig, ts):
        out = []
        for b in self._ordered():
            try:
                if b.daily_stopped():
                    b.blocked += 1; out.append((b.account_id, "daily_stop")); continue
                qty = b.size("A")
                legs, err = BP.build_entry_exit3(
                    account=b.account_id, strategy="A", setup=sig.get("liq", "sweep-OTE"),
                    signal_ts=sig["ts_signal"], side=sig["side"], qty=qty,
                    entry=float(sig["entry"]), stop=float(sig["stop"]), target=float(sig["target"]),
                    root="MNQ")
                if err:
                    out.append((b.account_id, "build_fail")); continue
                res = b.sender.send_exit3(legs, b.account_id, root="MNQ")
                if res.get("ok") or b.mode != "live":
                    b.sent += 1
                out.append((b.account_id, res.get("reason", "sent")))
                self._dlog(final_action="paper_signal", account=b.account_id, profile="A",
                           bar_ts=str(ts), side=sig["side"], qty_total=qty, braked=b.p3.braked)
            except Exception as e:                       # ISOLATION — one book never breaks the fan-out
                out.append((b.account_id, f"ERROR:{e!r}"))
        return out

    # ---- fan-out: Profile B (single bracket, never D1c) ----
    def route_b(self, sig, ts, bar_i=None):
        out = []
        for b in self._ordered():
            try:
                qty = b.size("B")
                if qty <= 0:
                    b.blocked += 1; out.append((b.account_id, "p3_b0")); continue
                if b.daily_stopped():
                    b.blocked += 1; out.append((b.account_id, "daily_stop")); continue
                payload, err = BP.build_entry(
                    account=b.account_id, strategy="B", setup=sig.get("liq", "orb"),
                    signal_ts=sig["ts_signal"], side=sig["side"], qty=qty,
                    entry=float(sig["entry"]), stop=float(sig["stop"]), target=float(sig["target"]),
                    root="MNQ")
                if err:
                    out.append((b.account_id, "build_fail")); continue
                res = b.sender.send(payload)
                if res.get("sent") or b.mode != "live":
                    b.sent += 1
                    if bar_i is not None:
                        b.b_tracker.on_signal(sig, qty, bar_i, ts)
                out.append((b.account_id, res.get("reason", "sent")))
                self._dlog(final_action="paper_signal", account=b.account_id, profile="B",
                           bar_ts=str(ts), side=sig["side"], qty_total=qty)
            except Exception as e:                       # ISOLATION
                out.append((b.account_id, f"ERROR:{e!r}"))
        return out

    def advance_b(self, bar_i, ts, o, h, l, c):
        for b in self.books:
            try:
                b.b_tracker.on_bar(bar_i, ts, o, h, l, c)
            except Exception:                            # noqa: BLE001
                pass


# ---- registry: build the ZEUS-MAX book set from specs (no secrets in specs; URLs via env) ----
def load_books(specs, mode="paper", store_factory=None):
    """specs: [{account_id, firm, tier, funded, url_env}]. URL read from os.environ[url_env]."""
    from bridge_sender import BridgeSender
    bridge_mode = "live" if mode == "live" else "dry-run"   # bridge knows dry-run/test/live, not "paper"
    books = []
    for s in specs:
        st = (store_factory or Store)()
        sender = BridgeSender(store=st, mode=bridge_mode,
                              live_url=os.environ.get(s.get("url_env", "")) if mode == "live" else None)
        books.append(AccountBook(s["account_id"], s.get("firm", "?"), s["tier"], sender,
                                 funded=s.get("funded", False), mode=mode, store=st))
    return books


# the ZEUS-MAX target set (3 MFFU Pro + 5 Topstep XFA, all 150K). URLs supplied via env at deploy.
ZEUS_MAX_SPECS = (
    [dict(account_id=f"TOPSTEP-150K-{i}", firm="topstep", tier="150K-balanced",
          url_env=f"TP_URL_TOPSTEP_{i}") for i in range(1, 6)] +
    [dict(account_id=f"MFFU-150K-{i}", firm="mffu", tier="150K-balanced",
          url_env=f"TP_URL_MFFU_{i}") for i in range(1, 4)]
)
