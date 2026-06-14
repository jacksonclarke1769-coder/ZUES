"""
Profile A v2 — SIM-ONLY orchestration loop.

Wires four already-tested, frozen pieces together. Nothing here changes any of them:
    ProfileAEngine  (strategy_engine_profileA)  -> signal generation (parity-verified)
    TwoLegBracket   (tradovate_client)          -> simulated Exit #3 order state
    MFFUState       (mffu_state)                 -> MFFU Core 50K account / risk gate
    Store           (store)                      -> dashboard / event persistence

SIM ONLY. This module imports ONLY the TwoLegBracket *state machine* from tradovate_client
— never TradovateClient — so it has no auth, no REST/WS, no order endpoints. There is no
live trading path or flag; live order placement is structurally impossible from here.

Fills are simulated from bar OHLC with the backtest's conservative stop-first convention.
Run:  python bot.py --start 2025-10-20 --end 2025-12-01
"""
import argparse, os, sys
import pandas as pd

from store import Store
from mffu_state import MFFUState, MFFUConfig, EVALUATION, FUNDED, PAYOUT_ELIGIBLE, FAILED
from tradovate_client import TwoLegBracket            # state machine ONLY — no broker client
import config

FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
sys.path.insert(0, os.path.join(FW, "engine")); sys.path.insert(0, os.path.join(FW, "models"))
import data as D                                       # noqa: E402  (SIM bar source)
from strategy_engine_profileA import ProfileAEngine, NY  # noqa: E402

LIVE_ENABLED = False                                   # hard, permanent: this file never trades live
# Poll latest_signal() 09:30..13:35 ET. The realtime reservation can emit a ny_am signal
# late (after an earlier pending setup resolves), so the window must extend past 11:30 —
# this matches the proven parity harness (DEC_MIN_HI) so the signal list is identical.
DECISION_END_MIN = 13 * 60 + 35


class SimBot:
    def __init__(self, store, cfg=config, mffu=None, cost_per_contract=0.0, verbose=False, on_decision=None):
        assert not LIVE_ENABLED, "bot.py is SIM-only"
        self.st = store
        self.cfg = cfg
        self.on_decision = on_decision     # optional observer(sig, placed:bool, reason, ts) — paper-live hook
        self.pv = cfg.POINT_VALUE
        self.cost = cost_per_contract
        self.verbose = verbose
        self.mffu = mffu or MFFUState(MFFUConfig.from_config_modules(cfg.EVAL, cfg.PAYOUT, cfg.SAFETY, cfg.STRAT))
        self.engine = ProfileAEngine(cfg.STRAT)
        self.active = None                             # TwoLegBracket or None
        self.trade = None                              # dict of the working trade
        self.cur_day = None
        self.last_close = None
        self.trade_from = None                         # warmup cutoff (no trading before)
        self.bseq = 0
        self.signals = []                              # engine signals (pre-gate) — for parity test
        self._bracket_actions_seen = 0

    # ---------------- sizing / helpers ----------------
    def _qty(self):
        return self.cfg.SIZING["eval_qty"] if self.mffu.phase == EVALUATION else self.cfg.SIZING["fund_qty"]

    def _news(self, ts):
        return False                                   # placeholder — real econ-calendar feed plugs in here

    def _mins(self, ts):
        return ts.hour * 60 + ts.minute

    def _ev(self, level, msg):
        self.st.log(level, msg)
        if self.verbose:
            print(f"[{level}] {msg}")

    def _persist(self):
        self.st.set_state(
            mffu_snapshot=self.mffu.snapshot(),
            bracket_snapshot=(self.active.snapshot() if self.active else None),
            trade_snapshot=self.trade,
            cur_day=str(self.cur_day) if self.cur_day else None,
            **self.mffu.status())

    def _clear_active(self):
        self.active = None
        self.trade = None
        self._bracket_actions_seen = 0

    # ---------------- per-bar pipeline ----------------
    def process_bar(self, ts, o, h, l, c):
        # VULCAN P8 defense-in-depth: refuse duplicate / out-of-order bars at the engine
        # boundary (feeds already dedupe; this makes a feed glitch harmless here too).
        last = getattr(self, "last_bar_ts", None)
        if last is not None and ts <= last:
            return
        self.last_bar_ts = ts
        if self.trade_from is not None and ts < self.trade_from:
            self.engine.add_bar(ts, o, h, l, c)        # warmup only — fill the buffer, no trading
            return
        self._roll_day(ts)
        self.engine.add_bar(ts, o, h, l, c)
        if self.active is not None:
            self._sim_fills(ts, o, h, l, c)
        if self.active is not None and self.trade["filled"] > 0 and self.mffu.should_flatten_now(ts):
            self._flatten(c, ts, "eod_flat")
        # poll the engine EVERY decision bar so the signal list matches the backtest 1:1;
        # _consider records the signal first, then acts only if flat + risk-allowed.
        if self.cfg.STRAT["nyam_start_min"] <= self._mins(ts) <= DECISION_END_MIN:
            sig = self.engine.latest_signal()
            if sig:
                self._consider(sig, ts, o, h, l, c)
        self.last_close = c

    def _roll_day(self, ts):
        day = ts.date()
        if self.cur_day is None:
            self.cur_day = day
        elif day != self.cur_day:
            self._eod(ts)
            self.cur_day = day

    # ---------------- signal -> risk gate -> place ----------------
    def _consider(self, sig, ts, o, h, l, c):
        self.signals.append(dict(ts_signal=sig["ts_signal"], side=sig["side"],
                                 entry=round(float(sig["entry"]), 2), stop=round(float(sig["stop"]), 2),
                                 target=round(float(sig["target"]), 2), liq=sig.get("liq")))
        self._ev("signal", f"{sig['side']} entry {sig['entry']:.2f} stop {sig['stop']:.2f} "
                           f"tgt {sig['target']:.2f} liq {sig.get('liq')}")
        risk = abs(sig["entry"] - sig["stop"]) * self.pv * self._qty()
        ok, reason = self.mffu.can_open_trade(ts=ts, in_news_blackout=self._news(ts), trade_risk=risk)
        if self.active is not None:
            ok, reason = False, "position_open"
        if not ok:
            self._ev("risk_rejected", f"{reason} (signal {sig['side']} @ {sig['entry']:.2f})")
            if self.on_decision:
                self.on_decision(sig, False, reason, ts)
            return
        self._place(sig, ts)
        self._sim_fills(ts, o, h, l, c)                # try to fill the entry on this (the fill) bar
        self._persist()
        if self.on_decision:
            self.on_decision(sig, True, "placed", ts)

    def _place(self, sig, ts):
        self.bseq += 1
        action = "Buy" if sig["side"] == "long" else "Sell"
        qty = self._qty()
        b = TwoLegBracket(f"SIM-{self.bseq}", action, qty, sig["entry"], sig["stop"],
                          tp2_px=sig["target"], contract_id=getattr(self.cfg, "SYMBOL_ROOT", "MNQ"))
        b.start()
        self.active = b
        self._bracket_actions_seen = 0
        self.trade = dict(side=sig["side"], dirn=(1 if action == "Buy" else -1), qty=qty,
                          entry=b.entry_px, stop=b.stop_px, tp1=b.tp1_px, tp2=b.tp2_px,
                          tp1_alloc=qty // 2, tp2_alloc=qty - qty // 2,
                          filled=0, tp1_done=0, tp2_done=0, stop_done=0,
                          realized=0.0, mae=0.0, mfe=0.0, age=0, exit_px=b.entry_px,
                          ts_entry=str(ts), liq=sig.get("liq"))
        self._drain(b)
        self._ev("entry_placed", f"{sig['side']} {qty} limit {b.entry_px:.2f} stop {b.stop_px:.2f} "
                                 f"TP1 {b.tp1_px:.2f} TP2 {b.tp2_px:.2f}")

    # ---------------- OHLC fill simulation ----------------
    def _sim_fills(self, ts, o, h, l, c):
        b, tr = self.active, self.trade
        if b is None:
            return
        d = tr["dirn"]
        # mark excursions (points)
        tr["mfe"] = max(tr["mfe"], (h - tr["entry"]) if d > 0 else (tr["entry"] - l))
        tr["mae"] = max(tr["mae"], (tr["entry"] - l) if d > 0 else (h - tr["entry"]))
        # ---- entry (resting limit) ----
        if tr["filled"] == 0:
            hit = (l <= tr["entry"]) if d > 0 else (h >= tr["entry"])
            if hit:
                b.on_fill("ENTRY", tr["qty"]); self._drain(b)
                self.mffu.record_trade_open(tr["qty"], tr["entry"], tr["stop"], ts)
                tr["filled"] = tr["qty"]; tr["ts_entry"] = str(ts)
                self._ev("entry_filled", f"{tr['side']} {tr['qty']} @ {tr['entry']:.2f}")
            else:
                tr["age"] += 1
                if tr["age"] > 12 or self.engine.flat_time(ts):     # OTE limit expired unfilled
                    b.cancel_entry(); self._drain(b)
                    self._ev("cancelled", "entry limit expired unfilled")
                    self._clear_active()
                return
        # ---- exits (stop-first, then targets) ----
        rem = tr["qty"] - tr["tp1_done"] - tr["tp2_done"] - tr["stop_done"]
        if rem <= 0:
            return
        stop_hit = (l <= tr["stop"]) if d > 0 else (h >= tr["stop"])
        if stop_hit:
            self._fill_leg("STOP", tr["stop"], rem, ts)
        else:
            tp1_hit = (h >= tr["tp1"]) if d > 0 else (l <= tr["tp1"])
            if tp1_hit and tr["tp1_done"] == 0 and tr["tp1_alloc"] > 0:
                self._fill_leg("TP1", tr["tp1"], tr["tp1_alloc"], ts)
            rem = tr["qty"] - tr["tp1_done"] - tr["tp2_done"] - tr["stop_done"]
            tp2_hit = (h >= tr["tp2"]) if d > 0 else (l <= tr["tp2"])
            if rem > 0 and tp2_hit and tr["tp2_done"] == 0:
                self._fill_leg("TP2", tr["tp2"], rem, ts)
        # ---- mark-to-market for intraday breach (worst case) ----
        if self.active is not None:
            rem = tr["qty"] - tr["tp1_done"] - tr["tp2_done"] - tr["stop_done"]
            if rem > 0:
                worst = l if d > 0 else h
                unreal = tr["realized"] + (worst - tr["entry"]) * d * rem * self.pv
                self.mffu.update_unrealized(unreal)
                if self.mffu.breached:
                    self._ev("breach", f"equity touched floor {self.mffu.floor:.0f}")
                    self._flatten(worst, ts, "breach")

    def _fill_leg(self, role, px, qty, ts):
        b, tr = self.active, self.trade
        b.on_fill(role, qty); self._drain(b)
        pnl = (px - tr["entry"]) * tr["dirn"] * qty * self.pv - self.cost * qty
        tr["realized"] += pnl
        tr["exit_px"] = px
        tr[{"STOP": "stop_done", "TP1": "tp1_done", "TP2": "tp2_done"}[role]] += qty
        self._ev(role.lower() + "_filled", f"{qty} @ {px:.2f}  legPnL ${pnl:+.0f}")
        rem = tr["qty"] - tr["tp1_done"] - tr["tp2_done"] - tr["stop_done"]
        if rem <= 0:
            self._finalize(px, ts, "exit3")

    def _drain(self, b):
        """Log any new bracket intents (stop reductions, cancels) since the last event."""
        for a in b.actions[self._bracket_actions_seen:]:
            if a["op"] == "MODIFY" and a["role"] == "STOP":
                self._ev("stop_reduced", f"stop qty -> {a['qty']}")
            elif a["op"] == "CANCEL":
                self._ev("cancelled", f"{a['role']} cancelled")
        self._bracket_actions_seen = len(b.actions)

    # ---------------- closing / flatten / EOD ----------------
    def _flatten(self, px, ts, reason):
        tr = self.trade
        rem = tr["qty"] - tr["tp1_done"] - tr["tp2_done"] - tr["stop_done"]
        if rem > 0:
            tr["realized"] += (px - tr["entry"]) * tr["dirn"] * rem * self.pv - self.cost * rem
            tr["stop_done"] += rem                     # treat the residual as closed
            tr["exit_px"] = px
        if self.active:
            for r, o in list(self.active.working_orders().items()):
                self._ev("cancelled", f"{r} cancelled ({reason})")
        self._finalize(px, ts, reason)

    def _finalize(self, exit_px, ts, reason):
        tr = self.trade
        if tr["filled"] > 0:
            self.mffu.record_trade_close(tr["realized"], ts)
            self.st.add_trade(ts_entry=tr["ts_entry"], ts_exit=str(ts), direction=tr["side"],
                              phase=self.mffu.phase, qty=tr["qty"], entry_px=round(tr["entry"], 2),
                              stop_px=round(tr["stop"], 2), exit_px=round(exit_px, 2),
                              pnl_usd=round(tr["realized"], 2),
                              pnl_pts=round(tr["realized"] / (self.pv * max(tr["qty"], 1)), 2),
                              reason=reason, mae_pts=round(tr["mae"], 2), mfe_pts=round(tr["mfe"], 2),
                              account="SIM")
            self.st.add_equity(str(ts), round(self.mffu.balance, 2), round(self.mffu.eod_hwm, 2),
                               round(self.mffu.floor, 2), self.mffu.phase)
            self._ev("trade_closed", f"{reason} pnl ${tr['realized']:+.0f} bal ${self.mffu.balance:,.0f} "
                                     f"phase {self.mffu.phase}")
        self._clear_active()
        self._persist()

    def _eod(self, ts):
        if self.active is not None and self.trade["filled"] > 0:
            self._flatten(self.last_close, ts, "eod_force")
        elif self.active is not None:
            self.active.cancel_entry(); self._clear_active()
        evs = self.mffu.end_of_day_update(ts)
        for e in evs:
            self._ev("eod_event", e)
        if self.mffu.phase == PAYOUT_ELIGIBLE:
            amt = self.mffu.request_payout()
            if amt > 0:
                self._ev("payout", f"withdrew ${amt:,.0f} (total ${self.mffu.total_paid:,.0f})")
        self.st.add_equity(str(ts) + " EOD", round(self.mffu.balance, 2), round(self.mffu.eod_hwm, 2),
                           round(self.mffu.floor, 2), self.mffu.phase)
        self._ev("eod_update", f"bal {self.mffu.balance:,.0f} floor {self.mffu.floor:,.0f} "
                               f"hwm {self.mffu.eod_hwm:,.0f} phase {self.mffu.phase}")
        self._persist()

    def final_eod(self, ts):
        self._eod(ts)

    # ---------------- crash / restart recovery ----------------
    @classmethod
    def restore(cls, store, cfg=config, **kw):
        bot = cls(store, cfg=cfg, **kw)
        snap = store.get_state("mffu_snapshot")
        if snap:
            bot.mffu = MFFUState.from_snapshot(snap)
        bsnap = store.get_state("bracket_snapshot")
        if bsnap:
            bot.active = TwoLegBracket.from_snapshot(bsnap)
        bot.trade = store.get_state("trade_snapshot")
        cd = store.get_state("cur_day")
        if cd:
            bot.cur_day = pd.Timestamp(cd).date()
        return bot


# ----------------------------- SIM driver -----------------------------
def run_sim(start="2025-10-20", end="2025-12-01", reset=True, warmup_days=45,
            db_path=None, cost=0.0, verbose=False):
    st = Store(db_path or config.DB_PATH)
    if reset:
        st.reset()
    bot = SimBot(st, cost_per_contract=cost, verbose=verbose)
    bot.trade_from = pd.Timestamp(start, tz=NY)
    base = D.load_spine("NQ", "5m")
    lo = pd.Timestamp(start, tz=NY) - pd.Timedelta(days=warmup_days)
    hi = pd.Timestamp(end, tz=NY)
    df = base[(base.index >= lo) & (base.index < hi)]
    vals = df[["Open", "High", "Low", "Close"]].values
    idx = df.index
    st.log("info", f"SIM start {start}..{end} ({len(df)} bars incl warmup)")
    for i in range(len(df)):
        bot.process_bar(idx[i], vals[i, 0], vals[i, 1], vals[i, 2], vals[i, 3])
    if bot.cur_day is not None:
        bot.final_eod(idx[-1])
    st.log("info", f"SIM done. phase={bot.mffu.phase} balance=${bot.mffu.balance:,.0f} "
                   f"signals={len(bot.signals)} trades={len(st.trades())}")
    return bot


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Profile A v2 SIM-only bot (no live trading).")
    ap.add_argument("--start", default="2025-10-20")
    ap.add_argument("--end", default="2025-12-01")
    ap.add_argument("--cost", type=float, default=0.0, help="$/contract round-turn cost in SIM")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    bot = run_sim(a.start, a.end, cost=a.cost, verbose=a.verbose)
    print(f"SIM complete: phase={bot.mffu.phase} balance=${bot.mffu.balance:,.0f} "
          f"signals={len(bot.signals)} trades={len(bot.st.trades())}")
