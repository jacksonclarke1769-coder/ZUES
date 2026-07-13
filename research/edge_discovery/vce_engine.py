"""
vce_engine.py — VOLATILITY COMPRESSION -> EXPANSION BREAKOUT (NQ, HONEST edge-discovery).

REAL DATABENTO NQ FUTURES ONLY. RTH 5m built by resampling RTH 1m (T.load_1m_rth) so the
5m signal grid and the 1m fill-truth escalation share one byte-identical source.

Family: detect a low-volatility COIL (compression) then trade the range EXPANSION breakout
with a STOP order (both sides). Fill at the trigger price (buy-stop/sell-stop), NOT a resting
limit (avoids the Profile-A stale-limit mirage). Conservative intrabar: adverse-first (stop
before target on same bar). EOD flat.

This module = engine + feature build. The sweep driver + gauntlet live in vce_sweep.py.
"""
import os, sys, warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
sys.path.insert(0, os.path.expanduser("~/trading-team/backtests"))
sys.path.insert(0, os.path.expanduser("~/trading-team/bot/nq-liq-bot"))
import tools_vpc_1m_truth as T
import nq_vwap_pullback as v

NY = "America/New_York"
TICK = 0.25
RT_COST = v.RT_COST          # 0.75 pt round trip (0.375/side) — the pinned honest cost
POINT_USD = 20.0             # NQ $ per point (1 contract)


# ---------------------------------------------------------------------------------------------
# DATA
# ---------------------------------------------------------------------------------------------
def load_5m_rth():
    """RTH 5m by resampling the SAME RTH 1m Databento source (T.load_1m_rth)."""
    d1 = T.load_1m_rth()  # cols: open,high,low,close,volume,date  (NY tz, 09:30-15:59)
    o = d1["open"].resample("5min", label="left", closed="left").first()
    h = d1["high"].resample("5min", label="left", closed="left").max()
    l = d1["low"].resample("5min", label="left", closed="left").min()
    c = d1["close"].resample("5min", label="left", closed="left").last()
    vol = d1["volume"].resample("5min", label="left", closed="left").sum()
    df = pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c, "Volume": vol}).dropna(subset=["Open"])
    df["date"] = df.index.normalize()
    df["slot"] = df.groupby("date").cumcount()
    return df, d1


def add_atr(df, n=14):
    """Continuous causal ATR (identical formula to nq_vwap_pullback.features)."""
    df = df.copy()
    pc = df["Close"].shift(1)
    tr = np.maximum(df.High - df.Low, np.maximum((df.High - pc).abs(), (df.Low - pc).abs()))
    df["atr"] = tr.rolling(n, min_periods=n // 2).mean()
    return df


def day_blocks(df):
    """Pre-split into per-day numpy blocks for fast repeated sweeps.
    Also carries a global causal ATR-percentile reference (trailing across the continuous series)."""
    df = df.sort_index()
    blocks = []
    for d, g in df.groupby("date"):
        g = g.sort_values("slot")
        blocks.append(dict(
            date=pd.Timestamp(d),
            O=g.Open.values.astype(float), H=g.High.values.astype(float),
            L=g.Low.values.astype(float), C=g.Close.values.astype(float),
            A=g.atr.values.astype(float),
            ts=g.index.values,
        ))
    return blocks


# ---------------------------------------------------------------------------------------------
# ENGINE  (single config, conservative 5m adverse-first)
# ---------------------------------------------------------------------------------------------
def run_config(blocks, detector="ratio", W=6, c=1.0, p=0.30, atr_lb=100,
               trig_tk=1, E=6, smin=3, smax=60, last_entry=72,
               exit_mode="R", Rmult=2.0, trail_atr=2.0, stop_side="coil",
               max_trades=3, shift=0, return_trades=False):
    """
    detector: 'ratio'  coil_range <= c*ATR[i]
              'pctile' ATR[i] <= p-quantile of trailing atr_lb ATRs (causal)
    W        : coil window (bars)
    trig_tk  : trigger ticks beyond coil edge (buy/sell stop offset)
    E        : bars after coil in which a breakout is accepted
    stop_side: 'coil' -> stop at opposite coil edge; R=entry-stop
    exit_mode: 'R' fixed Rmult target (stop-first same-bar) | 'trail' ATR trail
    shift    : +k look-ahead CANARY (shift signal decision forward k bars = cheat); edge must NOT jump
    """
    trades = []
    # global ATR series for percentile detector (causal quantile over trailing window across days)
    if detector == "pctile":
        allA = np.concatenate([b["A"] for b in blocks])
    for b in blocks:
        O, H, L, C, A = b["O"], b["H"], b["L"], b["C"], b["A"]
        n = len(C)
        if n < W + 2:
            continue
        # causal per-bar ATR percentile within this day's trailing context (prior bars of the day
        # plus the day's own history is short; use a rolling window over the day's ATR incl. prior).
        busy_until = -1
        taken = 0
        i = 0
        # detection index is shifted by `shift` for the canary (uses FUTURE info when shift>0)
        while i < n - 1:
            di = i + shift                      # bar whose CLOSE we (illegally, if shift>0) inspect
            if di >= n:
                break
            if not (smin <= i <= smax) or i <= busy_until or taken >= max_trades:
                i += 1; continue
            if di - W + 1 < 0 or np.isnan(A[di]):
                i += 1; continue
            lo = di - W + 1
            coil_high = H[lo:di + 1].max()
            coil_low = L[lo:di + 1].min()
            crange = coil_high - coil_low
            if crange <= 0:
                i += 1; continue
            if detector == "ratio":
                is_coil = crange <= c * A[di]
            else:  # pctile: ATR[di] in bottom p of trailing atr_lb bars (causal within day arrays;
                   # uses this day's ATR history which already embeds prior-day continuity via cont. ATR)
                w0 = max(0, di - atr_lb + 1)
                ref = A[w0:di + 1]
                ref = ref[~np.isnan(ref)]
                if len(ref) < 20:
                    i += 1; continue
                is_coil = A[di] <= np.quantile(ref, p)
            if not is_coil:
                i += 1; continue
            # armed: buy/sell stop
            trig = trig_tk * TICK
            long_trig = coil_high + trig
            short_trig = coil_low - trig
            # scan forward for breakout (entry bar strictly AFTER the detection bar i)
            entry = None; d = 0; ej = None
            for j in range(i + 1, min(i + 1 + E, n)):
                hitL = H[j] >= long_trig
                hitS = L[j] <= short_trig
                if hitL and hitS:
                    # ambiguous on 5m -> conservative: skip (resolved on 1m for survivors only)
                    ej = j; d = 0; break
                if hitL:
                    entry = long_trig; d = 1; ej = j; break
                if hitS:
                    entry = short_trig; d = -1; ej = j; break
            if d == 0:
                i = (ej + 1) if ej is not None else (i + 1)
                continue
            # stop / R
            if stop_side == "coil":
                stop = coil_low if d == 1 else coil_high
            else:
                stop = entry - d * Rmult * 0.0  # unused branch
            R = abs(entry - stop)
            if R <= 0:
                i += 1; continue
            target = entry + d * Rmult * R if exit_mode == "R" else None
            # walk exit from entry bar ej onward, adverse-first
            exit_px = None; xi = n - 1
            peak = entry
            for k in range(ej, n):
                # gap check on entry bar: if bar k already beyond, still use bar extremes
                if exit_mode == "R":
                    if d == 1:
                        if L[k] <= stop:  # stop first (adverse-first)
                            exit_px = stop; xi = k; break
                        if H[k] >= target:
                            exit_px = target; xi = k; break
                    else:
                        if H[k] >= stop:
                            exit_px = stop; xi = k; break
                        if L[k] <= target:
                            exit_px = target; xi = k; break
                else:  # trail
                    if d == 1:
                        if L[k] <= stop:
                            exit_px = stop; xi = k; break
                        peak = max(peak, H[k])
                        ns = peak - trail_atr * A[k]
                        stop = max(stop, ns) if not np.isnan(A[k]) else stop
                    else:
                        if H[k] >= stop:
                            exit_px = stop; xi = k; break
                        peak = min(peak, L[k])
                        ns = peak + trail_atr * A[k]
                        stop = min(stop, ns) if not np.isnan(A[k]) else stop
            if exit_px is None:
                exit_px = C[n - 1]; xi = n - 1
            pnl = d * (exit_px - entry) - RT_COST
            trades.append(dict(date=b["date"], dir=d, entry=entry, exit=exit_px,
                               R=R, pnl=pnl, dur=xi - ej, ei=ej, xi=xi))
            busy_until = xi
            taken += 1
            i = xi + 1
        # end day
    tdf = pd.DataFrame(trades)
    if return_trades:
        return tdf
    return tdf


# ---------------------------------------------------------------------------------------------
# STATS
# ---------------------------------------------------------------------------------------------
def stats(t, cost_mult=1.0):
    """PF/WR/expR/net given a cost multiplier applied on top of the baked RT_COST."""
    if t is None or len(t) == 0:
        return dict(n=0, pf=np.nan, wr=np.nan, net=0.0, expR=np.nan, maxdd=np.nan)
    pnl = t["pnl"].values.copy()
    if cost_mult != 1.0:
        pnl = pnl - (cost_mult - 1.0) * RT_COST      # add extra cost on top
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    pf = gp / gl if gl > 0 else np.inf
    wr = (pnl > 0).mean() * 100
    net = pnl.sum()
    expR = (pnl / t["R"].values).mean()
    eq = np.cumsum(pnl); dd = np.maximum.accumulate(eq) - eq
    return dict(n=len(pnl), pf=pf, wr=wr, net=net, expR=expR, maxdd=dd.max())
