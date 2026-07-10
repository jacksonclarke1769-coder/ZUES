"""
Profile A LIVE engine. Reuses the EXACT validated backtest code (ict-nq-framework)
on a rolling 5m bar buffer, so live signals == backtested signals (zero drift).

Flow: the bot feeds each CLOSED 5m bar via add_bar(); latest_signal() rebuilds the
causal feature frame on the buffer, runs the frozen Profile A model, and returns a
signal ONLY if a fresh entry fills at the most recent bar. The bot sizes (eval vs
funded), places the Tradovate OSO bracket, and persists the trade to the store.
"""
import os, sys
import pandas as pd, numpy as np
FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
sys.path.insert(0, os.path.join(FW, "engine")); sys.path.insert(0, os.path.join(FW, "models"))
import data as D, htf, trade_log as TL          # noqa
import model01_sweep_mss_fvg as M1              # the frozen Profile A model

NY = "America/New_York"
BUFFER_DAYS = 35   # enough history for weekly/daily/4H/1H context + sessions

PROFILE_A = dict(entry_type="ote", sessions={"asia", "london", "ny_am", "ny_lunch", "ny_pm"},
                 target_mode="fixed_rr", rr=2.0,
                 partial=[(1, 0.5)])   # Exit #3 (frozen v2): bank 50% at +1R, hold 50% to +2R


class TimestampReconstructionError(Exception):
    """BROKEN-PLUMBING invariant, not an ordinary no-signal condition — must escape
    latest_signal() uncaught so the caller (bot.py) fails closed rather than trade on an
    unknown instant.

    A correctly-derived ny_am fill ALWAYS has a valid `fill_bar` positional index into a
    tz-aware NY `feats.index` landing inside the 09:30-16:00 ET session. Any of the three
    conditions below is impossible for a real fill and means the plumbing between model01
    and the engine is broken (same defect class as INC-20260706-1141: re-localizing a
    UTC-wall-clock date/time string as NY silently shifts the instant ~4h)."""

    def __init__(self, fill_bar, index_len, derived_instant):
        self.fill_bar = fill_bar
        self.index_len = index_len
        self.derived_instant = derived_instant
        super().__init__(
            f"cannot reconstruct fill instant: fill_bar={fill_bar!r} index_len={index_len!r} "
            f"derived_instant={derived_instant!r}"
        )


def _derive_fill_instant(feats_index, fill_bar):
    """PURE: the fill's true instant is feats_index[fill_bar] — NEVER the date/time strings
    model01 also emits (those are calendar-date keys for shadow_ledger/review_week only;
    re-parsing them re-localizes a UTC-wall-clock reading as NY and shifts the instant ~4h).

    fill_bar is a valid positional index into feats_index because model01 emits it from a
    reset_index()'d frame that preserves row order (frozen, self-contained — no threading
    through emission required). Raises TimestampReconstructionError (never returns None) on:
      * fill_bar out of range for feats_index
      * feats_index not tz-aware NY at that position
      * the derived instant falling outside the 09:30-16:00 ET session
    These are broken-plumbing invariants; the caller must NOT catch this and continue."""
    fb = int(fill_bar)
    n = len(feats_index)
    if not (0 <= fb < n):
        raise TimestampReconstructionError(fill_bar=fb, index_len=n, derived_instant=None)
    ets = feats_index[fb]
    if ets.tzinfo is None or NY not in str(ets.tzinfo):
        raise TimestampReconstructionError(fill_bar=fb, index_len=n, derived_instant=None)
    ny_ets = ets.tz_convert(NY)
    mins_of_day = ny_ets.hour * 60 + ny_ets.minute
    if not (9 * 60 + 30 <= mins_of_day <= 16 * 60):
        raise TimestampReconstructionError(fill_bar=fb, index_len=n, derived_instant=ny_ets)
    return ny_ets


# EMIT-001 (prereg/EMIT-001.md, DEC-20260711-EMIT-001): the emission-path repair. DEFAULT
# mode is byte-identical to certified current behaviour; the new mode is inert until an
# operator explicitly constructs ProfileAEngine(..., emission_mode="emit_at_fill") -- no
# existing call site (bot.py, auto_live.py, every tools_*/apex_*/replay_* harness) passes
# this kwarg, so every one of them is completely unaffected by this change.
EMISSION_MODE_CERTIFIED_GATE = "certified_gate"   # DEFAULT — unchanged: tail(3) + <=10min freshness
EMISSION_MODE_EMIT_AT_FILL = "emit_at_fill"        # new — drops the poll-time freshness gate only
EMISSION_MODES = {EMISSION_MODE_CERTIFIED_GATE, EMISSION_MODE_EMIT_AT_FILL}


class ProfileAEngine:
    def __init__(self, strat_cfg, emission_mode=None):
        self.c = strat_cfg
        self.buf = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        self.buf.index = pd.DatetimeIndex([], tz=NY)
        self.acted_ts = set()        # fill timestamps already turned into orders
        mode = emission_mode or EMISSION_MODE_CERTIFIED_GATE
        if mode not in EMISSION_MODES:      # fail closed on an unknown mode, never silently trade
            raise ValueError(f"unknown EMISSION_MODE={mode!r}; must be one of {EMISSION_MODES}")
        self.emission_mode = mode

    def add_bar(self, ts, o, h, l, c, v=0):
        """ts: tz-aware ET (or UTC) timestamp of the CLOSED 5m bar."""
        ts = pd.Timestamp(ts);  ts = ts.tz_convert(NY) if ts.tzinfo else ts.tz_localize("UTC").tz_convert(NY)
        self.buf.loc[ts] = [o, h, l, c, v]
        self.buf = self.buf[~self.buf.index.duplicated(keep="last")].sort_index()
        cutoff = self.buf.index.max() - pd.Timedelta(days=BUFFER_DAYS)
        self.buf = self.buf[self.buf.index >= cutoff]

    def _features(self):
        base = self.buf.copy()
        df = D.tag_sessions(base)
        df = htf.add_daily_weekly(df)
        df = htf.add_session_levels(df)
        df = htf.add_htf_swings(df, base, "1h", "h1", 2, 2)
        df = htf.add_htf_swings(df, base, "4h", "h4", 2, 2)
        df.index.name = "timestamp"
        return df

    def latest_signal(self):
        """Return a fresh entry signal dict if Profile A just filled on the last bar."""
        if len(self.buf) < 2000:                 # need warmup (~1 week of 5m bars min)
            return None
        try:
            feats = self._features()
            tr = M1.run(feats, "NQ", PROFILE_A, realtime=True)   # pending-setup reservation -> no phantom signals
        except Exception:
            return None
        if not len(tr):
            return None
        recent = self.buf.index.max()
        # a fresh fill = a trade whose fill timestamp is the most recent 1-2 bars, NY-AM, unacted.
        # The fill's true instant comes ONLY from feats.index[fill_bar] (_derive_fill_instant) —
        # this sits OUTSIDE the try/except above BY DESIGN: an out-of-range fill_bar or a broken
        # index here is broken plumbing (must escape to bot.py), never an ordinary no-signal.
        for _, t in tr.tail(3).iterrows():
            if t["session"] != "ny_am":
                continue
            ets = _derive_fill_instant(feats.index, t["fill_bar"])
            key = ets.isoformat()
            if key in self.acted_ts:
                continue
            if ets > recent:
                continue    # unreachable by model01's own construction; causal safety net, not a gate
            # EMIT-001: certified_gate (DEFAULT) keeps the ORIGINAL <=10min poll-time freshness
            # requirement byte-for-byte. emit_at_fill drops ONLY that poll-time staleness check —
            # every other condition above (ny_am session, acted_ts dedup, ets<=recent causal
            # guard, tail(3) scan window) is untouched, so a signal is emitted the moment it is
            # discovered fresh OR the moment the (unchanged, frozen) model01 scan finally surfaces
            # it in tail(3) — never gated on how much wall-clock time elapsed since its true fill.
            if self.emission_mode == EMISSION_MODE_CERTIFIED_GATE:
                emit = (recent - ets) <= pd.Timedelta(minutes=10)
            else:
                emit = True
            if emit:
                self.acted_ts.add(key)
                d = 1 if t["direction"] == "long" else -1
                return dict(side=t["direction"], entry=float(t["entry"]), stop=float(t["stop"]),
                            target=float(t["target"]), rr=float(t["rr"]), liq=t["liq_swept"],
                            ts_signal=key, emission_mode=self.emission_mode)
        return None

    def in_entry_window(self, ts):
        e = pd.Timestamp(ts).tz_convert(NY) if pd.Timestamp(ts).tzinfo else pd.Timestamp(ts)
        m = e.hour * 60 + e.minute
        return self.c["nyam_start_min"] <= m < self.c["nyam_end_min"]

    def flat_time(self, ts):
        e = pd.Timestamp(ts).tz_convert(NY) if pd.Timestamp(ts).tzinfo else pd.Timestamp(ts)
        return (e.hour * 60 + e.minute) >= self.c["flat_min"]
