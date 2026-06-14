"""TradingViewFeed — DATA-ONLY realtime 5m bars from a logged-in TradingView chart over CDP.

Reads the active chart's main-series bars via the Chrome DevTools Protocol (localhost:9222) —
the same read path the TradingView MCP uses. NO broker, NO orders, NO credentials. Unlike the
Dukascopy CFD proxy this is the REAL CME contract (e.g. CME_MINI:NQ1!) → ZERO basis vs the
Tradovate/TradersPost execution price.

Prereq: Chrome running with --remote-debugging-port=9222 and a logged-in TradingView chart on
NQ 5m. Launch with `trading-team/tools/launch-tv-chrome.sh` (persistent logged-in profile).

FAIL-CLOSED: connect() refuses to start unless the active chart is an NQ 5-minute chart, so the
bot can never be fed the wrong symbol or timeframe.

Interface mirrors paper_live.BarFeed (duck-typed): connect() -> contract dict, history() -> list
of (ts_ET, o, h, l, c) (forming last bar dropped), live() -> generator of newly-CLOSED bars.
"""
import json
import time as _t

import pandas as pd

NY = "America/New_York"

_CHART = "window.TradingViewApi._activeChartWidgetWV.value()"
_BARS = _CHART + "._chartWidget.model().mainSeries().bars()"


def _read_bars_js(limit):
    """JS that returns the loaded main-series bars as [[time,o,h,l,c,vol], ...] (newest last)."""
    limit = int(limit)
    return (
        "(function(){var b=%s;"
        "if(!b||typeof b.lastIndex!=='function')return null;"
        "var out=[];var e=b.lastIndex();var s=Math.max(b.firstIndex(),e-%d+1);"
        "for(var i=s;i<=e;i++){var v=b.valueAt(i);"
        "if(v)out.push([v[0],v[1],v[2],v[3],v[4],v[5]||0]);}return out;})()"
        % (_BARS, limit)
    )


def _to_et(unix_ts):
    t = int(unix_ts)
    if t > 1_000_000_000_000:        # milliseconds -> seconds
        t //= 1000
    return pd.Timestamp(t, unit="s", tz="UTC").tz_convert(NY)


class _CDP:
    """Minimal synchronous Chrome DevTools Protocol channel (Runtime.evaluate only)."""

    def __init__(self, host="localhost", port=9222, timeout=10):
        self.host, self.port, self.timeout = host, port, timeout
        self.ws = None
        self._id = 0

    def _find_chart_target(self):
        import requests
        r = requests.get("http://%s:%d/json/list" % (self.host, self.port), timeout=self.timeout)
        for t in r.json():
            if t.get("type") == "page" and "tradingview.com/chart" in (t.get("url") or ""):
                return t
        raise RuntimeError(
            "No TradingView chart tab found on CDP :%d — run trading-team/tools/launch-tv-chrome.sh "
            "and open an NQ 5m chart." % self.port)

    def connect(self):
        import websocket  # websocket-client
        target = self._find_chart_target()
        # suppress_origin: Chrome (>=111) rejects CDP websockets carrying a browser Origin header
        # unless --remote-allow-origins is set; sending no Origin (like node's ws) is accepted.
        self.ws = websocket.create_connection(
            target["webSocketDebuggerUrl"], timeout=self.timeout, max_size=None,
            suppress_origin=True)
        return target

    def eval(self, expression, await_promise=False):
        if self.ws is None:
            self.connect()
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({
            "id": mid, "method": "Runtime.evaluate",
            "params": {"expression": expression, "returnByValue": True,
                       "awaitPromise": await_promise},
        }))
        while True:                                   # skip async protocol events (no id)
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                break
        if "error" in msg:
            raise RuntimeError("CDP error: %s" % msg["error"])
        res = msg.get("result", {})
        if res.get("exceptionDetails"):
            exc = res["exceptionDetails"]
            desc = (exc.get("exception") or {}).get("description") or exc.get("text") or "eval error"
            raise RuntimeError("JS eval error: %s" % desc)
        return res.get("result", {}).get("value")

    def close(self):
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None


class TradingViewFeed:
    """Realtime 5m bars off a live TradingView chart via CDP. Data only — never sends orders."""

    MIN_WARMUP_DAYS = 14          # hard minimum: 2 full trading weeks (prev-week levels)

    def __init__(self, poll_sec=20, warmup=5000, expect_root="NQ", expect_res="5",
                 host="localhost", port=9222, cdp=None,
                 warmup_source="dukascopy", warmup_days=45, auto_basis=True,
                 duka_feed=None):
        self.poll = int(poll_sec)
        self.warmup = int(warmup)
        self.expect_root = str(expect_root).upper()
        self.expect_res = str(expect_res)
        self.cdp = cdp or _CDP(host, port)
        self.seen = set()
        self.symbol = None
        self.resolution = None
        # --- warmup-depth controls ---
        self.warmup_source = warmup_source     # "dukascopy" (deep, basis-aligned) | "tradingview" (chart cache)
        self.warmup_days = int(warmup_days)
        self.auto_basis = bool(auto_basis)
        self._duka_feed = duka_feed            # injectable for tests
        self.basis = 0.0                       # pts added to Dukascopy warmup to match CME frame
        # --- health / liveness tracking ---
        self.reset_count = 0
        self.first_bar_ts = None
        self.last_bar_ts = None

    def _track(self, bars):
        for ts, *_ in bars:
            if self.first_bar_ts is None or ts < self.first_bar_ts:
                self.first_bar_ts = ts
            if self.last_bar_ts is None or ts > self.last_bar_ts:
                self.last_bar_ts = ts

    def connect(self):
        self.cdp.connect()
        sym = self.cdp.eval(_CHART + ".symbol()")
        res = self.cdp.eval(_CHART + ".resolution()")
        if sym is None:
            raise RuntimeError("TradingView chart API not ready (symbol() == null) — chart still loading?")
        self.symbol, self.resolution = str(sym), str(res)
        root_ok = self.expect_root in self.symbol.upper()
        res_ok = self.resolution == self.expect_res
        if not (root_ok and res_ok):
            raise RuntimeError(
                "REFUSED (fail-closed): active TradingView chart is %s @ %sm, expected %s @ %sm. "
                "Switch the chart to NQ 5m and restart — the bot must not trade off the wrong symbol."
                % (self.symbol, self.resolution, self.expect_root, self.expect_res))
        return dict(name=self.symbol, id=self.symbol, resolution=self.resolution,
                    source="tradingview-cdp")

    def _fetch(self, limit):
        raw = self.cdp.eval(_read_bars_js(limit))
        out = []
        for row in (raw or []):
            try:
                out.append((_to_et(row[0]), float(row[1]), float(row[2]),
                            float(row[3]), float(row[4])))
            except (TypeError, ValueError, IndexError):
                continue
        out.sort(key=lambda x: x[0])
        return out

    def history(self):
        """Warmup buffer. Default source = Dukascopy (deep, current, basis-aligned to the CME
        frame); falls back to the chart's own loaded bars if warmup_source='tradingview'."""
        if self.warmup_source == "dukascopy":
            bars = self._dukascopy_warmup()
        else:
            bars = self._fetch(self.warmup)
            bars = bars[:-1] if bars else []     # drop the possibly-forming last bar
        for ts, *_ in bars:
            self.seen.add(ts.isoformat())
        self._track(bars)
        return bars

    def _measure_basis(self, tv_bars, duka_bars):
        """Median (TV_close - Duka_close) over overlapping timestamps. 0.0 if no overlap."""
        dmap = {ts.isoformat(): c for (ts, o, h, l, c) in duka_bars}
        diffs = sorted(ctv - dmap[ts.isoformat()]
                       for (ts, o, h, l, ctv) in tv_bars if ts.isoformat() in dmap)
        return float(diffs[len(diffs) // 2]) if diffs else 0.0

    def _dukascopy_warmup(self):
        """Deep warmup from Dukascopy (credential-free, current), offset to the CME (TV) frame."""
        duka = self._duka_feed
        if duka is None:
            from paper_live import DukascopyLiveFeed
            duka = DukascopyLiveFeed(warmup_days=self.warmup_days)
        duka.connect()
        d_bars = duka.history()                   # [(ts_ET,o,h,l,c)], current, ~warmup_days deep
        tv_bars = self._fetch(self.warmup)        # chart's loaded bars (recent overlap) for basis
        self.basis = self._measure_basis(tv_bars, d_bars) if self.auto_basis else 0.0
        b = self.basis
        return [(ts, o + b, h + b, l + b, c + b) for (ts, o, h, l, c) in d_bars]

    def live(self):
        """Infinite generator of newly-CLOSED 5m bars (closed once now >= bar_open + 5m)."""
        while True:
            try:
                bars = self._fetch(50)
                now = pd.Timestamp.now("UTC")
                for ts, o, h, l, c in bars:
                    key = ts.isoformat()
                    if key not in self.seen and now >= ts.tz_convert("UTC") + pd.Timedelta(minutes=5):
                        self.seen.add(key)
                        self._track([(ts, o, h, l, c)])
                        yield ts, o, h, l, c
            except Exception as e:
                self.reset_count += 1
                print("[tvfeed] poll error: %s — reconnecting (#%d)" % (e, self.reset_count), flush=True)
                self.cdp.close()
            _t.sleep(self.poll)

    def data_status(self, now=None):
        """Computed liveness/readiness snapshot. DATA_READY is conservative & fail-closed."""
        import os
        now = now or pd.Timestamp.now("UTC")
        span_days = 0
        if self.first_bar_ts is not None and self.last_bar_ts is not None:
            span_days = (self.last_bar_ts - self.first_bar_ts).days
        warmup_ok = span_days >= self.MIN_WARMUP_DAYS
        stale_secs = None
        stale = True
        if self.last_bar_ts is not None:
            stale_secs = (now - self.last_bar_ts.tz_convert("UTC")).total_seconds()
            stale = stale_secs > 900            # >15m since last bar
        # real-time CME entitlement CANNOT be auto-verified -> require explicit operator confirm
        realtime_confirmed = os.environ.get("TV_REALTIME_CONFIRMED") == "1"
        no_reset = self.reset_count == 0
        data_ready = bool(warmup_ok and realtime_confirmed and (not stale) and no_reset)
        reasons = []
        if not warmup_ok:
            reasons.append("warmup %dd < %dd min" % (span_days, self.MIN_WARMUP_DAYS))
        if not realtime_confirmed:
            reasons.append("real-time CME entitlement UNVERIFIED (set TV_REALTIME_CONFIRMED=1 to confirm)")
        if stale:
            reasons.append("stale bars (last %s)" % (("%ds" % int(stale_secs)) if stale_secs is not None else "none"))
        if not no_reset:
            reasons.append("%d connection reset(s) this session" % self.reset_count)
        return dict(
            source="tradingview-cdp (warmup:%s)" % self.warmup_source,
            symbol=self.symbol, resolution=self.resolution,
            bars=len(self.seen), span_days=span_days, warmup_ok=warmup_ok,
            realtime_confirmed=realtime_confirmed, stale=stale, reset_count=self.reset_count,
            basis=round(self.basis, 3),
            first_bar=str(self.first_bar_ts), last_bar=str(self.last_bar_ts),
            DATA_READY=data_ready, reasons=reasons)
