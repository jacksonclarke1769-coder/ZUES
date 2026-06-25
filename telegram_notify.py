"""
Telegram notifications for the live bot — SIGNALS (on send) + OUTCOMES (modeled, feed-based).

Fail-safe, zero-dependency (urllib only). Reads TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID from the
environment (secrets — never committed). No-op if either is unset, so it can't break a live run.

NOTE on outcomes: the bot has NO broker read-back, so an "outcome" is the bot's MODELED result
(when the live feed hits the TP/stop/EOD level) — NOT a confirmed Tradovate fill. Every outcome
message is tagged "(modeled — confirm in Tradovate)" so it is never mistaken for the real P&L.
"""
from __future__ import annotations

import json
import os
import urllib.request

API = "https://api.telegram.org/bot{token}/sendMessage"


class Telegram:
    def __init__(self, token=None, chat_id=None, label="", opener=None):
        self.token = token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID")
        self.label = (label + "\n") if label else ""
        self.enabled = bool(self.token and self.chat_id)
        self.sent = self.failed = 0
        self._opener = opener or urllib.request.urlopen   # injectable for tests

    # ---- core sender (never raises into the engine) ----
    def send(self, text):
        if not self.enabled:
            return False
        try:
            payload = json.dumps({"chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
                                  "disable_web_page_preview": True}).encode()
            req = urllib.request.Request(API.format(token=self.token), data=payload,
                                         headers={"Content-Type": "application/json"})
            with self._opener(req, timeout=10) as r:
                ok = getattr(r, "status", 200) == 200
                self.sent += int(ok); self.failed += int(not ok)
                return ok
        except Exception as e:                                # noqa: BLE001 — notifications must never break trading
            self.failed += 1
            print(f"[telegram] send failed: {type(e).__name__}: {e}", flush=True)
            return False

    def info(self, text):
        return self.send(text)

    # ---- formatters ----
    @staticmethod
    def _dir(side):
        return "🟢 LONG" if str(side).lower() in ("long", "buy") else "🔴 SHORT"

    def signal(self, profile, side, qty, entry, stop, target, mode):
        live = "LIVE" if mode == "live" else "PAPER"
        tgt = f" · tgt {target:.2f}" if target else ""
        return self.send(f"<b>📨 Profile {profile} — {self._dir(side)} {qty} MNQ</b>  [{live}]\n"
                         f"{self.label}entry {entry:.2f} · stop {stop:.2f}{tgt}")

    def outcome(self, profile, side, rr, pnl, reason, mode):
        em = "✅" if (pnl or 0) > 1e-6 else ("❌" if (pnl or 0) < -1e-6 else "➖")
        live = "LIVE" if mode == "live" else "PAPER"
        return self.send(f"<b>{em} Profile {profile} {str(side).upper()} — {reason}</b>  [{live}]\n"
                         f"{self.label}{rr:+.2f}R · ${pnl:+,.0f}  <i>(modeled — confirm in Tradovate)</i>")
