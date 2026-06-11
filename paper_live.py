"""
Paper-LIVE validation mode — DATA ONLY. No broker, no orders, no credentials.

Purpose: run the production SIM bot (bot.SimBot) on realtime-style 5m bars and record
whether real-time behaviour matches the research assumptions (OTE fills, TP/stop touches,
slippage, missed entries, late signals, MFFU rejections). It NEVER sends an order — it
imports only SimBot (which itself imports only the TwoLegBracket state machine, never the
Tradovate client). Fills are SIMULATED from each completed bar's OHLC.

Outputs:
  • paper_fill_log.csv         — one row per signal (the fill-assumption ledger)
  • store state key 'paper'    — the aggregate panel for the dashboard

Feeds (all data-only):
  • ReplayFeed  — replays historical bars as if realtime (credential-free; default)
  • FakeFeed    — yields hand-crafted bars (tests)
  A genuine realtime market-data source would implement the same BarFeed interface; it is
  out of scope here and intentionally NOT wired (no network, no creds, no broker).

Run:  python paper_live.py --start 2025-11-01 --end 2025-12-01
"""
import argparse, csv, os, sys, time
import pandas as pd

from store import Store
from bot import SimBot, NY, FW                  # SimBot imports TwoLegBracket only — no broker client
import config
sys.path.insert(0, os.path.join(FW, "engine"))
import data as D                                # noqa: E402  (local parquet bars — no network)

CSV_COLS = ["date", "direction", "entry", "stop", "tp1", "tp2", "signal_time", "fill_time",
            "tp1_time", "tp2_time", "stop_time", "result_R", "fill_quality", "notes"]
W_FILL, MAX_HOLD, TICK = 12, 48, 0.25


# ----------------------------- feeds (data only) -----------------------------
class BarFeed:
    def __iter__(self):
        raise NotImplementedError


class ReplayFeed(BarFeed):
    """Replays historical 5m bars (load_spine) as completed realtime bars. No creds."""
    def __init__(self, start, end, warmup_days=45, speed=0.0):
        self.start, self.end, self.warmup_days, self.speed = start, end, warmup_days, speed

    def __iter__(self):
        base = D.load_spine("NQ", "5m")
        lo = pd.Timestamp(self.start, tz=NY) - pd.Timedelta(days=self.warmup_days)
        hi = pd.Timestamp(self.end, tz=NY)
        df = base[(base.index >= lo) & (base.index < hi)]
        vals = df[["Open", "High", "Low", "Close"]].values
        idx = df.index
        for i in range(len(df)):
            if self.speed:
                time.sleep(self.speed)
            yield idx[i], float(vals[i, 0]), float(vals[i, 1]), float(vals[i, 2]), float(vals[i, 3])


class FakeFeed(BarFeed):
    """Yields a hand-crafted list of (ts,o,h,l,c) bars — for tests."""
    def __init__(self, bars):
        self.bars = bars

    def __iter__(self):
        yield from self.bars


def _to_et(ts):
    t = pd.Timestamp(ts)
    return t.tz_convert(NY) if t.tzinfo else t.tz_localize("UTC").tz_convert(NY)


def normalize_bars(raw):
    """Tradovate getChart bars -> sorted [(ts_ET, o,h,l,c)]. Tolerant of field naming."""
    out = []
    for b in (raw or []):
        ts = b.get("timestamp") if isinstance(b, dict) else None
        ts = ts or (b.get("t") if isinstance(b, dict) else None)
        if ts is None:
            continue
        try:
            o = float(b.get("open", b.get("o"))); h = float(b.get("high", b.get("h")))
            lo = float(b.get("low", b.get("l"))); c = float(b.get("close", b.get("c")))
        except (TypeError, ValueError):
            continue
        out.append((_to_et(ts), o, h, lo, c))
    out.sort(key=lambda x: x[0])
    return out


class LiveBarFeed(BarFeed):
    """DATA-ONLY realtime 5m bars from a Tradovate (sim) account.

    Uses the Tradovate client for MARKET DATA ONLY — authenticate + resolve_front_month +
    get_bars. It never calls, references, or imports any order-placement method. Option A:
    live bars in, fills simulated locally from OHLC, nothing sent to the broker.
    """
    def __init__(self, cfg=config, poll_sec=20, warmup=12000, root=None):
        from tradovate_client import TradovateClient        # data client (read-only use below)
        self.cli = TradovateClient(cfg.TRADOVATE, cfg.HOSTS)
        self.poll = poll_sec; self.warmup = warmup
        self.root = root or getattr(cfg, "SYMBOL_ROOT", "MNQ")
        self.cid = None; self.seen = set()

    def connect(self):
        self.cli.authenticate()                              # market-data auth (mdAccessToken)
        contract = self.cli.resolve_front_month(self.root)
        if not contract:
            raise RuntimeError(f"could not resolve front-month for {self.root}")
        self.cid = contract["id"]
        return contract

    def history(self):
        """Warmup: recent completed bars to fill the engine buffer before going live."""
        bars = normalize_bars(self.cli.get_bars(self.cid, unit="MinuteBar", size=5, count=self.warmup))
        for ts, *_ in bars:
            self.seen.add(ts.isoformat())
        return bars[:-1] if bars else []                     # drop the possibly-forming last bar

    def live(self):
        """Infinite generator of newly-CLOSED 5m bars (a 5m bar is closed once now >= ts+5m)."""
        import time as _t
        while True:
            try:
                bars = normalize_bars(self.cli.get_bars(self.cid, unit="MinuteBar", size=5, count=50))
                now = pd.Timestamp.now("UTC")
                for ts, o, h, lo, c in bars:
                    key = ts.isoformat()
                    if key not in self.seen and now >= ts.tz_convert("UTC") + pd.Timedelta(minutes=5):
                        self.seen.add(key); yield ts, o, h, lo, c
            except Exception as e:
                print(f"[livefeed] poll error: {e}", flush=True)
            _t.sleep(self.poll)


class DukascopyLiveFeed(BarFeed):
    """CREDENTIAL-FREE near-live 5m bars from Dukascopy — NQ CFD proxy (the exact basis the
    backtest was validated on). ~few-minute delayed; irrelevant for fill-assumption validation
    (we only process COMPLETED bars). No API key, no broker, no orders."""
    def __init__(self, poll_sec=60, warmup_days=40, instrument=None):
        import dukascopy_python as dk
        from dukascopy_python.instruments import INSTRUMENT_IDX_AMERICA_E_NQ_100 as NQ
        self.dk = dk
        self.inst = instrument or NQ
        self.poll = poll_sec
        self.warmup_days = warmup_days
        self.seen = set()

    def connect(self):
        return dict(name="NQ (Dukascopy IDX CFD)", id="IDX_AMERICA_E_NQ_100")   # no auth needed

    def _fetch(self, start, end):
        df = self.dk.fetch(self.inst, self.dk.INTERVAL_MIN_5, self.dk.OFFER_SIDE_BID, start, end)
        out = []
        for ts, row in df.iterrows():
            out.append((_to_et(ts), float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])))
        out.sort(key=lambda x: x[0])
        return out

    def history(self):
        from datetime import datetime, timedelta
        end = datetime.utcnow(); start = end - timedelta(days=self.warmup_days)
        bars = self._fetch(start, end)
        for ts, *_ in bars:
            self.seen.add(ts.isoformat())
        return bars[:-1] if bars else []

    def live(self):
        import time as _t
        from datetime import datetime, timedelta
        while True:
            try:
                end = datetime.utcnow(); start = end - timedelta(hours=8)
                now = pd.Timestamp.now("UTC")
                for ts, o, h, l, c in self._fetch(start, end):
                    key = ts.isoformat()
                    if key not in self.seen and now >= ts.tz_convert("UTC") + pd.Timedelta(minutes=5):
                        self.seen.add(key); yield ts, o, h, l, c
            except Exception as e:
                print(f"[dukalive] poll error: {e}", flush=True)
            _t.sleep(self.poll)


# ----------------------------- fill-assumption tracker -----------------------------
class PaperTracker:
    """Independent ledger of 'did the research assumption hold in realtime'. It watches
    each signal's subsequent bars and records OTE/TP/stop touches, fill quality, slippage,
    and the Exit #3 result_R — separately from the bot's own SIM fills."""

    def __init__(self, cfg=config, csv_path="paper_fill_log.csv"):
        self.cfg = cfg
        self.csv_path = csv_path
        self.open = []        # open watches (dicts)
        self.rows = []        # finalized rows (dicts)

    # ---------- watch creation ----------
    def add_watch(self, sig, idx, ts, o, h, l, c, rejected=None, late=False):
        d = 1 if sig["side"] == "long" else -1
        entry, stop = float(sig["entry"]), float(sig["stop"])
        risk = abs(entry - stop)
        tp1 = round(entry + d * risk, 2)
        tp2 = round(float(sig.get("target", entry + d * 2 * risk)), 2)
        notes = []
        if rejected:
            notes.append(f"rejected_by_mffu:{rejected}")
        if late:
            notes.append("late_signal_after_window")
        w = dict(date=str(ts)[:10], side=sig["side"], dirn=d, entry=entry, stop=stop, tp1=tp1, tp2=tp2,
                 risk=risk, signal_time=str(ts), sig_idx=idx, rejected=rejected, late=late,
                 status="PENDING", age=0, held=0, fill_idx=None, fill_time="", tp1_done=False,
                 tp1_time="", tp2_time="", stop_time="", fill_quality="", result_R=None,
                 slippage_pts=0.0, last_close=c, notes=notes)
        self.open.append(w)
        self._advance(w, idx, ts, o, h, l, c)        # check the signal bar immediately

    # ---------- per-bar advance ----------
    def on_bar(self, idx, ts, o, h, l, c):
        for w in list(self.open):
            self._advance(w, idx, ts, o, h, l, c)

    def _advance(self, w, idx, ts, o, h, l, c):
        if w["status"] == "CLOSED":
            return
        d, entry, stop = w["dirn"], w["entry"], w["stop"]
        w["last_close"] = c
        m = ts.hour * 60 + ts.minute
        if w["status"] == "PENDING":
            w["age"] += 1
            touched = (l <= entry) if d > 0 else (h >= entry)
            if touched:
                w["status"] = "FILLED"; w["fill_idx"] = idx; w["fill_time"] = str(ts)
                through = (l < entry) if d > 0 else (h > entry)
                gap = (o < entry) if d > 0 else (o > entry)
                w["fill_quality"] = "gap" if gap else ("clean" if through else "touch")
                if w["fill_quality"] == "touch":
                    w["notes"].append("touch_only_fill_miss_risk")
                if gap:
                    w["notes"].append("entry_gap")
                self._exits(w, idx, ts, o, h, l, c)
            elif w["age"] > W_FILL or m > self.cfg.STRAT["nyam_end_min"]:
                w["fill_quality"] = "missed"; w["result_R"] = None
                w["notes"].append("entry_expired_unfilled")
                self._finalize(w)
            return
        # FILLED
        w["held"] += 1
        self._exits(w, idx, ts, o, h, l, c)
        if w["status"] != "CLOSED" and (w["held"] > MAX_HOLD or m >= self.cfg.STRAT["flat_min"]):
            risk = w["risk"]
            if w["tp1_done"]:
                w["result_R"] = round(0.5 * 1.0 + 0.5 * ((c - entry) * d / risk), 3)
            else:
                w["result_R"] = round((c - entry) * d / risk, 3)
            w["notes"].append("eod_flat")
            self._finalize(w)

    def _exits(self, w, idx, ts, o, h, l, c):
        d, entry, stop, tp1, tp2, risk = w["dirn"], w["entry"], w["stop"], w["tp1"], w["tp2"], w["risk"]
        stop_hit = (l <= stop) if d > 0 else (h >= stop)
        if stop_hit:
            gap = (o < stop) if d > 0 else (o > stop)
            w["slippage_pts"] = round(abs(o - stop), 2) if gap else TICK   # est: gap-through vs ~1 tick
            w["stop_time"] = str(ts)
            sl = w["slippage_pts"] / risk
            if w["tp1_done"]:
                w["result_R"] = round(0.5 * 1.0 + 0.5 * (-1.0 - sl), 3); w["notes"].append("tp1_then_stop")
            else:
                w["result_R"] = round(-1.0 - sl, 3); w["notes"].append("stop")
            self._finalize(w); return
        if not w["tp1_done"]:
            if (h >= tp1) if d > 0 else (l <= tp1):
                w["tp1_done"] = True; w["tp1_time"] = str(ts)
        if w["tp1_done"] and ((h >= tp2) if d > 0 else (l <= tp2)):
            w["tp2_time"] = str(ts); w["result_R"] = 1.5; w["notes"].append("tp1_tp2")
            self._finalize(w)

    def _finalize(self, w):
        w["status"] = "CLOSED"
        if w in self.open:
            self.open.remove(w)
        self.rows.append(dict(date=w["date"], direction=w["side"], entry=w["entry"], stop=w["stop"],
                              tp1=w["tp1"], tp2=w["tp2"], signal_time=w["signal_time"], fill_time=w["fill_time"],
                              tp1_time=w["tp1_time"], tp2_time=w["tp2_time"], stop_time=w["stop_time"],
                              result_R=w["result_R"], fill_quality=w["fill_quality"],
                              notes="|".join(w["notes"]), slippage_pts=w["slippage_pts"]))
        self._write_csv()

    def finalize_open(self, ts):
        """Close any still-open watches at end of run (eod)."""
        for w in list(self.open):
            d, entry, risk = w["dirn"], w["entry"], w["risk"]
            if w["status"] == "FILLED":
                c = w["last_close"]
                if w["tp1_done"]:
                    w["result_R"] = round(0.5 + 0.5 * ((c - entry) * d / risk), 3)
                else:
                    w["result_R"] = round((c - entry) * d / risk, 3)
                w["notes"].append("eod_flat_runend")
            else:
                w["fill_quality"] = w["fill_quality"] or "missed"; w["result_R"] = None
                w["notes"].append("unresolved_at_runend")
            self._finalize(w)

    # ---------- persistence ----------
    def _write_csv(self):
        with open(self.csv_path, "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=CSV_COLS, extrasaction="ignore")   # slippage_pts kept off the CSV
            wr.writeheader()
            for r in self.rows:
                wr.writerow(r)

    def metrics(self):
        rows = self.rows
        total = len(rows)
        filled = [r for r in rows if r["fill_quality"] not in ("missed", "")]
        missed = total - len(filled)
        nf = max(1, len(filled))
        tp1 = sum(1 for r in filled if r["tp1_time"])
        tp2 = sum(1 for r in filled if r["tp2_time"])
        stop = sum(1 for r in filled if r["stop_time"])
        res = [r["result_R"] for r in filled if r["result_R"] is not None]
        pos = sum(x for x in res if x > 0); neg = sum(x for x in res if x < 0)
        pf = round(pos / abs(neg), 3) if neg < 0 else float("inf")
        exp = round(sum(res) / len(res), 4) if res else 0.0
        avg_stop = round(sum(abs(r["entry"] - r["stop"]) for r in rows) / max(1, total), 1)
        slips = [r["slippage_pts"] for r in filled if r["stop_time"]]
        avg_slip = round(sum(slips) / len(slips), 3) if slips else 0.0
        touch = sum(1 for r in filled if "touch_only_fill_miss_risk" in r["notes"])
        return dict(total_paper_signals=total, filled_paper_trades=len(filled), missed_paper_trades=missed,
                    tp1_hit_pct=round(100 * tp1 / nf, 1), tp2_hit_pct=round(100 * tp2 / nf, 1),
                    stop_hit_pct=round(100 * stop / nf, 1), est_PF=pf, est_expectancy_R=exp,
                    avg_stop_size_pts=avg_stop, avg_slippage_est_pts=avg_slip,
                    touch_only_fills=touch, late_signals=sum(1 for r in rows if "late_signal" in r["notes"]),
                    mffu_rejected=sum(1 for r in rows if "rejected_by_mffu" in r["notes"]))

    def persist(self, store):
        store.set_state(paper=self.metrics())

    # ---------- snapshot / restart ----------
    def snapshot(self):
        return dict(open=self.open, rows=self.rows, csv_path=self.csv_path)

    @classmethod
    def from_snapshot(cls, s, cfg=config):
        t = cls(cfg=cfg, csv_path=s.get("csv_path", "paper_fill_log.csv"))
        t.open = s.get("open", [])
        t.rows = s.get("rows", [])
        return t


# ----------------------------- runner -----------------------------
class PaperLiveRunner:
    def __init__(self, store, start, end, csv_path="paper_fill_log.csv", cfg=config, tracker=None):
        self.st = store
        self.cfg = cfg
        self.start = start
        self.tracker = tracker or PaperTracker(cfg, csv_path)
        self.bot = SimBot(store, cfg=cfg, on_decision=self._on_decision)
        self.bot.trade_from = pd.Timestamp(start, tz=NY) if start not in (None, "live") else None
        self._cur = None

    def _on_decision(self, sig, placed, reason, ts):
        idx, o, h, l, c = self._cur
        m = ts.hour * 60 + ts.minute
        late = m > self.cfg.STRAT["nyam_end_min"]
        self.tracker.add_watch(sig, idx, ts, o, h, l, c,
                               rejected=(None if placed else reason), late=late)

    def run(self, feed):
        i = 0
        last_ts = None
        for ts, o, h, l, c in feed:
            tradable = ts >= self.bot.trade_from
            if tradable:
                self.tracker.on_bar(i, ts, o, h, l, c)        # advance existing watches
                self._cur = (i, o, h, l, c)
            self.bot.process_bar(ts, o, h, l, c)              # may fire _on_decision -> add_watch
            if tradable:
                self.tracker.persist(self.st)
            last_ts = ts
            i += 1
        if self.bot.cur_day is not None:
            self.bot.final_eod(last_ts)
        self.tracker.finalize_open(last_ts)
        self.tracker.persist(self.st)
        self.st.set_state(paper_tracker_snapshot=self.tracker.snapshot())
        return self

    @classmethod
    def restore(cls, store, start, end, cfg=config):
        snap = store.get_state("paper_tracker_snapshot")
        tracker = PaperTracker.from_snapshot(snap, cfg) if snap else None
        runner = cls(store, start, end, cfg=cfg, tracker=tracker)
        bsnap = store.get_state("mffu_snapshot")
        if bsnap or store.get_state("bracket_snapshot"):
            runner.bot = SimBot.restore(store, cfg=cfg, on_decision=runner._on_decision)
            runner.bot.trade_from = pd.Timestamp(start, tz=NY)
        return runner


def run_paper(start="2025-11-01", end="2025-12-01", reset=True, csv_path="paper_fill_log.csv", speed=0.0):
    st = Store(getattr(config, "PAPER_DB_PATH", "data/paper.db"))   # separate DB — never touches the backtest
    if reset:
        st.reset()
    runner = PaperLiveRunner(st, start, end, csv_path=csv_path)
    runner.run(ReplayFeed(start, end, speed=speed))
    return runner


def _drive_live(feed, st, csv_path, banner):
    """Shared DATA-ONLY live loop: warm up the engine on recent history, then feed each newly
    completed bar; simulate fills locally; persist after every bar. NOTHING sent to a broker."""
    runner = PaperLiveRunner(st, "live", "live", csv_path=csv_path)
    bot, tracker = runner.bot, runner.tracker
    bot.trade_from = pd.Timestamp.now("UTC").tz_convert(NY)
    hist = feed.history()
    for ts, o, h, l, c in hist:
        bot.process_bar(ts, o, h, l, c)                      # ts < trade_from -> warmup only, no trading
    st.set_state(live=dict(connected=True, paper=True, mode=banner))
    print(f"[paper-live] {banner}\n[paper-live] warmed up on {len(hist)} bars · going live · Ctrl+C to stop", flush=True)
    i = len(hist)
    try:
        for ts, o, h, l, c in feed.live():
            runner._cur = (i, o, h, l, c)
            tracker.on_bar(i, ts, o, h, l, c)
            bot.process_bar(ts, o, h, l, c)
            tracker.persist(st)
            st.set_state(paper_tracker_snapshot=tracker.snapshot(), live_last_bar=str(ts))
            bot._persist()
            i += 1
            print(f"[paper-live] {ts}  signals={len(bot.signals)}  ledger={len(tracker.rows)}  open={len(tracker.open)}", flush=True)
    except KeyboardInterrupt:
        print("\n[paper-live] stopping (Ctrl+C)…", flush=True)
    finally:
        tracker.finalize_open(pd.Timestamp.now("UTC").tz_convert(NY))
        tracker.persist(st)
        st.set_state(paper_tracker_snapshot=tracker.snapshot(),
                     live=dict(connected=False, paper=True, mode=banner + " (stopped)"))
        print(f"[paper-live] stopped · ledger {len(tracker.rows)} rows · state -> {st.path}", flush=True)
    return runner


def run_paper_live(cfg=config, csv_path="paper_fill_log.csv", poll_sec=20, warmup=12000, reset=True):
    """OPTION A — DATA-ONLY live via Tradovate market data. NOTHING sent to the broker."""
    st = Store(getattr(cfg, "PAPER_DB_PATH", "data/paper.db"))
    if reset:
        st.reset()
    feed = LiveBarFeed(cfg, poll_sec=poll_sec, warmup=warmup)
    contract = feed.connect()
    print(f"[paper-live] Tradovate connected · account {feed.cli.account_id} · contract {contract.get('name')}", flush=True)
    return _drive_live(feed, st, csv_path, "Tradovate market-data (data-only)")


def run_paper_dukascopy(csv_path="paper_fill_log.csv", poll_sec=60, warmup_days=40, reset=True):
    """OPTION A — CREDENTIAL-FREE near-live via Dukascopy (NQ CFD proxy). No keys, no broker."""
    st = Store(getattr(config, "PAPER_DB_PATH", "data/paper.db"))
    if reset:
        st.reset()
    feed = DukascopyLiveFeed(poll_sec=poll_sec, warmup_days=warmup_days)
    print("[paper-live] Dukascopy near-live · NQ CFD proxy · no credentials · DATA-ONLY", flush=True)
    return _drive_live(feed, st, csv_path, "Dukascopy near-live (CFD proxy · ~min delayed · data-only)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Profile A v2 PAPER-LIVE validation (data-only, no orders).")
    ap.add_argument("--live", action="store_true", help="Tradovate market data, real time (needs creds)")
    ap.add_argument("--duka", action="store_true", help="Dukascopy near-live, credential-free (NQ CFD proxy)")
    ap.add_argument("--start", default="2025-11-01")
    ap.add_argument("--end", default="2025-12-01")
    ap.add_argument("--csv", default="paper_fill_log.csv")
    ap.add_argument("--poll", type=int, default=20, help="live poll seconds")
    ap.add_argument("--warmup", type=int, default=12000, help="live warmup bars")
    ap.add_argument("--speed", type=float, default=0.0, help="seconds between bars (0 = as fast as possible)")
    a = ap.parse_args()
    if a.duka:
        run_paper_dukascopy(csv_path=a.csv, poll_sec=a.poll)
        raise SystemExit(0)
    if a.live:
        run_paper_live(csv_path=a.csv, poll_sec=a.poll, warmup=a.warmup)
        raise SystemExit(0)
    r = run_paper(a.start, a.end, csv_path=a.csv, speed=a.speed)
    m = r.tracker.metrics()
    print("PAPER-LIVE complete (data-only, no orders).")
    print(f"  signals={m['total_paper_signals']} filled={m['filled_paper_trades']} missed={m['missed_paper_trades']}")
    print(f"  TP1 {m['tp1_hit_pct']}% · TP2 {m['tp2_hit_pct']}% · stop {m['stop_hit_pct']}% · "
          f"est_PF {m['est_PF']} · exp {m['est_expectancy_R']}R")
    print(f"  avg_stop {m['avg_stop_size_pts']}pt · late {m['late_signals']} · mffu_rejected {m['mffu_rejected']}")
    print(f"  ledger -> {a.csv}")
