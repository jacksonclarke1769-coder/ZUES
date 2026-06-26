"""
FAN-OUT SECONDARY BOOK — route the SAME engine signals to ANOTHER account (e.g. Apex) at its own size,
rules, and webhook. The primary (MFFU, in auto_live.LiveAuto) computes A/B/Momentum ONCE and resolves
P&L; each SecondaryBook just sizes + routes those signals to its own sender, and derives its own day P&L
by SCALING the primary's resolved-trade R to its size (same trade, different size) to drive its daily-stop
and the Apex $1k daily-kill guard. One brain, many hands.

A signal -> Exit#3 split bracket at `am`.  B signal -> partial split at `bm`.  Momentum -> its own executor
at `mm`. Apex firms get the ApexDailyKill guard (flatten + halt the book before the day breaches the kill).
Per-book ISOLATION: every route is try/except so one book can never break another or the primary. The
primary's trades/sizing/webhook are NOT touched. RESEARCH-WIRED — routes only when its sender is live+approved.
"""
from __future__ import annotations

import pandas as pd
import bridge_traderspost as BP

NY = "America/New_York"
MNQ = 2.0


class SecondaryBook:
    def __init__(self, account, tier, sender, mode, notify=None, basis_offset=0.0, label=None):
        self.account = account
        self.tier = tier
        self.sender = sender
        self.mode = mode
        self.notify = notify
        self.basis = float(basis_offset)
        self.label = label or account
        self.am = int(tier.get("am", 0)); self.bm = int(tier.get("bm", 0)); self.mm = int(tier.get("mm", 0))
        self.daily_stop = float(tier.get("daily_stop", 0) or 0)
        self.day = None; self.day_pnl = 0.0; self.halt = False; self.halt_reason = ""
        self.sent = self.blocked = 0
        # Apex $1k daily-kill guard (flatten + halt before the kill)
        self.kill = None
        if tier.get("firm") == "apex" and tier.get("dll"):
            from apex_daily_kill import ApexDailyKill
            self.kill = ApexDailyKill(dll=tier["dll"], margin=tier.get("kill_margin", 0.85), label=self.label)
        # Momentum lane (own executor at this book's size, gated by this book's halt)
        self.m_exec = None
        if self.mm > 0:
            from profile_momentum_live import MomentumExecutor
            self.m_exec = MomentumExecutor(account, sender, base_qty=self.mm, stop_pts=120.0, mode=mode,
                                           notify=notify, basis_offset=basis_offset,
                                           killed=lambda: ("book halted" if self.halt else None))

    # ---- day roll / state ----
    def _roll(self, ts):
        t = pd.Timestamp(ts)
        d = (t.tz_convert(NY) if t.tzinfo else t).date()
        if d != self.day:
            self.day = d; self.day_pnl = 0.0; self.halt = False; self.halt_reason = ""

    def halted(self):
        return self.halt

    # ---- routing (same signals, this book's size + webhook) ----
    def route_a(self, sig, ts):
        try:
            self._roll(ts)
            if self.halt or self.am <= 0:
                self.blocked += 1; return
            legs, err = BP.build_entry_exit3(
                account=self.account, strategy="A", setup=sig.get("liq", "sweep-OTE"),
                signal_ts=sig["ts_signal"], side=sig["side"], qty=self.am,
                entry=float(sig["entry"]) + self.basis, stop=float(sig["stop"]) + self.basis,
                target=float(sig["target"]) + self.basis, root="MNQ",
                mode_meta=dict(mode="ARES", book=self.label))
            if err:
                print(f"[book {self.label}] A legs not built: {err}", flush=True); return
            res = self.sender.send_exit3(legs, self.account, root="MNQ")
            if res.get("ok") or self.mode != "live":
                self.sent += 1
                if self.notify is not None:
                    self.notify.signal("A", sig["side"], self.am, float(sig["entry"]),
                                       float(sig["stop"]), float(sig.get("target") or 0), self.mode)
        except Exception as e:                              # noqa: BLE001 — a book never breaks the primary
            print(f"[book {self.label}] route_a error (ignored): {e!r}", flush=True)

    def route_b(self, sig, ts):
        try:
            self._roll(ts)
            if self.halt or self.bm <= 0:
                self.blocked += 1; return
            legs, err = BP.build_entry_exit3(            # B is now a partial split too (50%@1R / 50%@1.5R)
                account=self.account, strategy="B", setup=sig.get("liq", "orb"),
                signal_ts=sig["ts_signal"], side=sig["side"], qty=self.bm,
                entry=float(sig["entry"]) + self.basis, stop=float(sig["stop"]) + self.basis,
                target=float(sig["target"]) + self.basis, root="MNQ",
                mode_meta=dict(mode="ARES", book=self.label))
            if err or self.bm < 2:                          # qty=1 -> single bracket fallback
                payload, e2 = BP.build_entry(
                    account=self.account, strategy="B", setup=sig.get("liq", "orb"),
                    signal_ts=sig["ts_signal"], side=sig["side"], qty=self.bm,
                    entry=float(sig["entry"]) + self.basis, stop=float(sig["stop"]) + self.basis,
                    target=float(sig["target"]) + self.basis, root="MNQ", order_type="limit",
                    mode_meta=dict(mode="ARES", book=self.label))
                if e2:
                    print(f"[book {self.label}] B not built: {e2}", flush=True); return
                self.sender.send(payload)
            else:
                self.sender.send_exit3(legs, self.account, root="MNQ")
            self.sent += 1
            if self.notify is not None:
                self.notify.signal("B", sig["side"], self.bm, float(sig["entry"]),
                                   float(sig["stop"]), float(sig.get("target") or 0), self.mode)
        except Exception as e:                              # noqa: BLE001
            print(f"[book {self.label}] route_b error (ignored): {e!r}", flush=True)

    def route_m(self, sig, ts):
        try:
            self._roll(ts)
            if self.m_exec is not None:
                self.m_exec.on_signal(sig, ts)
        except Exception as e:                              # noqa: BLE001
            print(f"[book {self.label}] route_m error (ignored): {e!r}", flush=True)

    # ---- P&L feed from the primary's resolved trades (same trade -> scale to THIS book's size) ----
    def on_resolved(self, profile, r, risk, ts):
        """Primary resolved a trade. Scale R to this book's size, update day P&L, enforce daily-stop + kill."""
        try:
            self._roll(ts)
            qty = {"A": self.am, "B": self.bm, "M": self.mm}.get(str(profile).upper(), 0)
            if qty <= 0:
                return
            self.day_pnl += float(r) * float(risk) * MNQ * qty
            if self.daily_stop and self.day_pnl <= -self.daily_stop and not self.halt:
                self.halt = True; self.halt_reason = "daily-stop"
            if self.kill is not None and self.kill.update(self.day, self.day_pnl):
                self.halt = True; self.halt_reason = "apex daily-kill"
                self._flatten(ts, "apex_kill_guard")
        except Exception as e:                              # noqa: BLE001
            print(f"[book {self.label}] on_resolved error (ignored): {e!r}", flush=True)

    def _flatten(self, ts, reason):
        try:
            payload, err = BP.build_flatten(account=self.account, reason=reason)
            if not err:
                self.sender.send(payload)
            if self.m_exec is not None:
                self.m_exec.eod_flat(ts, ref=None)
            print(f"[book {self.label}] FLATTEN ({reason}) — day P&L ${self.day_pnl:,.0f}", flush=True)
        except Exception as e:                              # noqa: BLE001
            print(f"[book {self.label}] flatten error (ignored): {e!r}", flush=True)
