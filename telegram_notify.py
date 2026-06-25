"""
Telegram notifications for the live bot — SIGNALS (on send) + OUTCOMES (modeled, feed-based).

Fail-safe, zero-dependency (urllib only). Reads TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID from the
environment (secrets — never committed). No-op if either is unset, so it can't break a live run.

NOTE on outcomes: the bot has NO broker read-back, so an "outcome" is the bot's MODELED result
(when the live feed hits the TP/stop/EOD level) — NOT a confirmed Tradovate fill. Every outcome
message is tagged "(modeled — confirm in Tradovate)" so it is never mistaken for the real P&L.
"""
from __future__ import annotations

import os

try:
    import requests          # already a bot dependency (bridge_sender/tradovate_client); handles TLS via certifi
except ImportError:          # pragma: no cover
    requests = None

API = "https://api.telegram.org/bot{token}/sendMessage"


class Telegram:
    def __init__(self, token=None, chat_id=None, label="", poster=None):
        self.token = token if token is not None else os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID")
        self.label = (label + "\n") if label else ""
        self.enabled = bool(self.token and self.chat_id)
        self.sent = self.failed = 0
        self._post = poster or (requests.post if requests else None)   # injectable for tests

    # ---- core sender (never raises into the engine) ----
    def send(self, text):
        if not self.enabled or self._post is None:
            return False
        try:
            r = self._post(API.format(token=self.token),
                           json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
                                 "disable_web_page_preview": True}, timeout=10)
            ok = getattr(r, "status_code", 200) == 200
            self.sent += int(ok); self.failed += int(not ok)
            if not ok:
                print(f"[telegram] HTTP {getattr(r, 'status_code', '?')}: {getattr(r, 'text', '')[:200]}", flush=True)
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

    def health(self, mode, account, tier, fields, window="NY-AM 09:30–11:30 ET"):
        head = "✅ <b>ARES LIVE &amp; HEALTHY</b>" if mode == "live" else "🟡 <b>ARES PAPER (dry-run)</b>"
        body = "\n".join(f"• {k}: {v}" for k, v in fields.items())
        return self.send(f"{head}\n<b>{account}</b> · {tier}\n{body}\nWatching {window} — 📨 on every signal.")

    def heartbeat(self, when_et, data_state, sent_a, sent_b, blocked, d1c_status, extra=""):
        dg = "✅" if data_state == "GREEN" else "🔴"
        tail = f" · {extra}" if extra else ""
        return self.send(f"💓 <b>ARES alive</b> · {when_et}\n"
                         f"• Data: {dg} {data_state} · D1c: {d1c_status}\n"
                         f"• Trades today: {sent_a + sent_b} (A:{sent_a} B:{sent_b}) · blocked: {blocked}{tail}")

    def outcome(self, profile, side, rr, pnl, reason, mode):
        em = "✅" if (pnl or 0) > 1e-6 else ("❌" if (pnl or 0) < -1e-6 else "➖")
        live = "LIVE" if mode == "live" else "PAPER"
        return self.send(f"<b>{em} Profile {profile} {str(side).upper()} — {reason}</b>  [{live}]\n"
                         f"{self.label}{rr:+.2f}R · ${pnl:+,.0f}  <i>(modeled — confirm in Tradovate)</i>")
