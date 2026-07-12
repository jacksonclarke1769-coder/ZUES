"""
Profile V (VPC — VWAP-Pullback Continuation) LIVE signal engine.

Mirrors ProfileAEngine's discipline exactly, on the frozen VPC strategy (NO strategy change):
reuses the EXACT certified signal generator `nq_vwap_pullback.vpc_signals` on a rolling 5m bar
buffer, so live signals == backtested signals (zero drift). The certified CFG is frozen and
imported from `vpc_apex_eval_sim.CFG` (atr_stop 2.5, trail_atr 5.0, slot 6-66, max 2/day,
slope 0.3, trend 0.5, daily_stop 120) — this module NEVER redefines it.

Flow (per closed 5m bar):
  add_bar(ts,o,h,l,c,v) buffers the bar; latest_signal() recomputes the causal feature frame on
  the buffer, steps the SAME armed_long/armed_short state machine `vpc_signals` uses, and returns
  an ENTRY signal ONLY at the moment a trigger fires on the just-closed bar (fill intended at the
  NEXT bar's open — market entry, matching the certified backtest). Raw-trigger emission only;
  taken-trade admission (one-at-a-time, max 2/day, 120pt daily stop) lives in the lane execution
  layer (VpcDayGate below), exactly as Profile B emits raw breaks and the tracker admits them.

DISARMED BY DEFAULT (fail-closed): live emission requires an explicit EMISSION_MODE. Construction
with an unknown mode raises ValueError (never silently trades) — mirroring
strategy_engine_profileA.py's EMIT-001 pattern. The default mode is `shadow` (observe/journal, no
live routing). `arm_live` is the ONLY mode a live router may act on, and it is set only by the
go-live-recert.sh-gated config flag at Phase-4 activation. Nothing in this repo constructs this
engine with `arm_live` today.

CAUSALITY: the signal at bar i is a pure function of bars <= i (proven by the truncation canary
in test_vpc_signal_parity.py). Timestamps come ONLY from the tz-aware buffer index via
`_derive_vpc_instant` — never re-parsed strings (the INC-20260706-1141 defect class).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests/ict-nq-framework"))

import nq_vwap_pullback as v          # v.features, v.vpc_signals  (frozen certified generator)
import vpc_apex_eval_sim as VS        # VS.CFG  (frozen certified config — never redefined here)

NY = "America/New_York"
BUFFER_BARS = 220        # ~2.5 RTH sessions: enough for continuous ATR warmup + same-day VWAP/vwap6
# COLD-START WARMUP GATE (mirrors tv_feed's warmup discipline): the engine REFUSES to emit a signal
# until its buffer holds at least this many CONTINUOUS bars (~1.5 RTH sessions). A fresh-process
# intraday cold-start recomputes rolling(14) ATR on an incomplete buffer, so its early-session
# signals can diverge from the continuously-computed certified batch until the buffer is warm (the
# cross-audit's diagnosed "cold-buffer artifact"). Live construction uses this default; parity/replay
# harnesses that start from TRUE history start (where batch is equally cold — an apples-to-apples
# comparison) pass warmup_bars=0.
WARMUP_BARS = 120

# Frozen signal-side kwargs, taken verbatim from the certified CFG (no local copy of the numbers).
_SIG_KW = {k: VS.CFG[k] for k in ("atr_stop", "slot_min", "slot_max", "slope_mult", "trend_mult")
           if k in VS.CFG}


# ---- EMISSION MODE (fail-closed, disarmed-by-default) --------------------------------------------
EMISSION_MODE_SHADOW = "shadow"        # DEFAULT — compute + journal, NO live routing
EMISSION_MODE_PAPER = "paper"          # paper harness may act (SimBot fills), never touches a broker
EMISSION_MODE_ARM_LIVE = "arm_live"    # ONLY a live router may act — set ONLY by go-live-recert gate
EMISSION_MODES = {EMISSION_MODE_SHADOW, EMISSION_MODE_PAPER, EMISSION_MODE_ARM_LIVE}


class VpcTimestampReconstructionError(Exception):
    """BROKEN-PLUMBING invariant (NOT an ordinary no-signal), same class as
    strategy_engine_profileA.TimestampReconstructionError: it must escape latest_signal() uncaught
    so the caller fails closed rather than trade on an unknown instant. A real VPC trigger ALWAYS
    has a valid positional index into a tz-aware NY buffer landing inside 09:30-16:00 ET."""

    def __init__(self, bar_pos, index_len, derived_instant):
        self.bar_pos = bar_pos
        self.index_len = index_len
        self.derived_instant = derived_instant
        super().__init__(
            f"cannot reconstruct VPC signal instant: bar_pos={bar_pos!r} index_len={index_len!r} "
            f"derived_instant={derived_instant!r}"
        )


def _derive_vpc_instant(buf_index, bar_pos):
    """PURE: the signal-bar instant is buf_index[bar_pos] — NEVER a re-parsed date/time string
    (re-localizing a UTC wall-clock reading as NY silently shifts ~4h; that is INC-20260706-1141).
    Raises VpcTimestampReconstructionError (never returns None) on out-of-range, non-tz-aware-NY, or
    out-of-session positions. The caller MUST NOT catch this and continue."""
    bp = int(bar_pos)
    n = len(buf_index)
    if not (0 <= bp < n):
        raise VpcTimestampReconstructionError(bar_pos=bp, index_len=n, derived_instant=None)
    ets = buf_index[bp]
    if ets.tzinfo is None or NY not in str(ets.tzinfo):
        raise VpcTimestampReconstructionError(bar_pos=bp, index_len=n, derived_instant=None)
    ny_ets = ets.tz_convert(NY)
    mins = ny_ets.hour * 60 + ny_ets.minute
    if not (9 * 60 + 30 <= mins <= 16 * 60):
        raise VpcTimestampReconstructionError(bar_pos=bp, index_len=n, derived_instant=ny_ets)
    return ny_ets


class ProfileVEngine:
    """Streaming VPC signal engine. add_bar() every closed 5m RTH bar; latest_signal() returns a
    raw VPC entry trigger dict once, at the bar it fires, or None. Pure (no I/O, no orders)."""

    def __init__(self, emission_mode=None, warmup_bars=None):
        mode = emission_mode or EMISSION_MODE_SHADOW
        if mode not in EMISSION_MODES:          # fail closed on an unknown mode — never silently trade
            raise ValueError(f"unknown VPC EMISSION_MODE={mode!r}; must be one of {EMISSION_MODES}")
        self.emission_mode = mode
        self.warmup_bars = WARMUP_BARS if warmup_bars is None else int(warmup_bars)
        self.buf = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
        self.buf.index = pd.DatetimeIndex([], tz=NY)
        # armed state machine — identical semantics to vpc_signals' per-day loop
        self.cur_day = None
        self.armed_long = False
        self.armed_short = False
        self.emitted_ts = set()          # signal-bar instants already surfaced (dedup)
        self.signals = []                # audit trail of emitted raw triggers

    @property
    def armed(self):
        return self.armed_long or self.armed_short

    def add_bar(self, ts, o, h, l, c, v_vol=0):
        ts = pd.Timestamp(ts)
        ts = ts.tz_convert(NY) if ts.tzinfo else ts.tz_localize("UTC").tz_convert(NY)
        self.buf.loc[ts] = [o, h, l, c, v_vol]
        self.buf = self.buf[~self.buf.index.duplicated(keep="last")].sort_index()
        if len(self.buf) > BUFFER_BARS:
            self.buf = self.buf.iloc[-BUFFER_BARS:]

    def _day_features(self):
        """Recompute the CERTIFIED feature frame (v.features) on the buffer and return the current
        day's group. Causal: v.features uses only backward-looking ops (grouped-by-date cumulative
        VWAP, rolling(14) ATR, shift(6) vwap6) so values at bar i never depend on bars > i."""
        base = self.buf.copy()
        base["date"] = base.index.normalize()
        base["slot"] = base.groupby("date").cumcount()
        feats = v.features(base)
        last_day = base["date"].iloc[-1]
        g = feats[feats["date"] == last_day].sort_values("slot").reset_index(drop=False)
        return g, last_day

    def latest_signal(self):
        """Return a raw VPC entry trigger dict if the just-closed bar fired one, else None.

        The returned dict: side, direction(1/-1), stop_dist(pts), entry_bar_offset (=+1, next
        bar's open is the fill), ts_signal (signal-bar ISO instant), atr, vwap. The caller sizes,
        builds the market-entry payload (bridge.build_vpc_entry), and hands the trail manager the
        stop_dist. Raw emission only — day admission (max 2/day etc.) is VpcDayGate's job."""
        if len(self.buf) < max(2, self.warmup_bars):   # COLD-START WARMUP GATE — refuse until warm
            return None
        g, day = self._day_features()
        if day != self.cur_day:               # new RTH day -> reset the armed state machine
            self.cur_day = day
            self.armed_long = False
            self.armed_short = False
        n = len(g)
        i = n - 1                              # the just-closed bar within today
        slot = int(g["slot"].iloc[i])
        C = g["Close"].values; Vw = g["vwap"].values; O = g["dayopen"].values; A = g["atr"].values
        V6 = g["vwap6"].values; Lo = g["Low"].values; Hi = g["High"].values
        # ---- verbatim transcription of vpc_signals' per-bar loop body (arm + trigger) ----
        if not (_SIG_KW["slot_min"] <= slot <= _SIG_KW["slot_max"]):
            return None
        if np.isnan(A[i]) or np.isnan(V6[i]):
            return None
        slope_ok = abs(Vw[i] - V6[i]) >= _SIG_KW["slope_mult"] * A[i]
        ext_ok = abs(C[i] - O[i]) >= _SIG_KW["trend_mult"] * A[i]
        vol_ok = (A[i] / C[i]) >= 0.0          # vol_gate is 0.0 in the certified CFG (no-op)
        gates = slope_ok and ext_ok and vol_ok
        up = gates and (C[i] > Vw[i]) and (Vw[i] > V6[i]) and (C[i] > O[i])
        dn = gates and (C[i] < Vw[i]) and (Vw[i] < V6[i]) and (C[i] < O[i])
        if up and Lo[i] <= Vw[i]:
            self.armed_long = True
        if dn and Hi[i] >= Vw[i]:
            self.armed_short = True
        trig = None
        if self.armed_long and up and C[i] > Vw[i] and Lo[i] > Vw[i] * 0.9995:
            trig = (1, _SIG_KW["atr_stop"] * A[i]); self.armed_long = False
        elif self.armed_short and dn and C[i] < Vw[i] and Hi[i] < Vw[i] * 1.0005:
            trig = (-1, _SIG_KW["atr_stop"] * A[i]); self.armed_short = False
        if trig is None:
            return None
        d, stop_dist = trig
        # tz-aware instant of the SIGNAL bar (fill is next bar's open) — fail-closed on broken index
        buf_pos = len(self.buf) - 1
        ets = _derive_vpc_instant(self.buf.index, buf_pos)
        key = ets.isoformat()
        if key in self.emitted_ts:
            return None
        self.emitted_ts.add(key)
        sig = dict(side="long" if d == 1 else "short", direction=int(d),
                   stop_dist=float(stop_dist), entry_bar_offset=1,
                   ts_signal=key, slot=slot, atr=float(A[i]), vwap=float(Vw[i]),
                   ref_close=float(C[i]), profile="V", emission_mode=self.emission_mode)
        self.signals.append(dict(sig))
        return sig


class VpcDayGate:
    """Reproduces `simulate_day`'s TAKEN-trade admission exactly (one position at a time, max 2/day,
    120pt daily circuit-breaker), decoupled from signal generation the same way Profile B's tracker
    admits raw breaks. The signal engine emits raw triggers; this gate decides which become live
    entries — so (engine triggers -> gate) reproduces `backtest()`'s taken-trade ledger.

    Feed each trigger to `admit(entry_slot)`: returns True if the certified sim would TAKE it.
    Call `on_resolved(pnl_pts, exit_slot)` when a taken trade closes so busy_until / day_pnl track
    exactly as simulate_day's loop does. `new_day()` on each RTH day roll."""

    def __init__(self):
        self.max_trades = int(VS.CFG["max_trades"])
        self.daily_stop = float(VS.CFG["daily_stop"])
        self.new_day()

    def new_day(self):
        self.busy_until = -1
        self.taken = 0
        self.day_pnl = 0.0

    def admit(self, entry_slot):
        """Mirror of simulate_day's per-signal filter, in loop order:
          if ei<=busy_until or taken>=max_trades: skip ; if daily_stop tripped: STOP (block rest)."""
        if entry_slot <= self.busy_until or self.taken >= self.max_trades:
            return False
        if self.daily_stop and self.day_pnl <= -self.daily_stop:
            return False
        return True

    def on_resolved(self, pnl_pts, exit_slot):
        self.busy_until = int(exit_slot)
        self.taken += 1
        self.day_pnl += float(pnl_pts)
