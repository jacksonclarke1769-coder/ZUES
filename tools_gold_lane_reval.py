"""GOLD THIRD-LANE — Lane 1: revalidate the vol-gated MR-short (RESEARCH ONLY, not deployed).

Replicates ~/trading-team/backtests/position_sizer.py:22-48 `_gold_daily()` EXACTLY (short-only;
Close > BB(20,2)upper AND RSI(14) > 70; vol-gate stdev(5d logret)/stdev(60d logret) < 0.70; stop
1.5*ATR(14); target 2.25*ATR(14) = 1.5R; EOD flat 15:45 ET; next-bar-open entry; 15m bars built
from 5m RTH data, hours 9-16 America/New_York; cost 0.30pt flat per trade), then:

  (1) CANARY  — reproduce the source's own 2021-2026 numbers from its own data path
                (~/trading-team/data/multi/XAU_5m_rth.csv). STOP if PF drifts >0.1.
  (2) EXTENDED WINDOW — same frozen rules on ~/trading-team/data/nq/XAU_5m_24h_dukascopy.csv
                restricted to the same RTH session, 2019-2026 (2019-2022 = pseudo-OOS, never
                seen by the edge before). Per-year PF/WR/n/totR.
  (3) FUTURES COST LADDER — MGC $10/pt DPP; cost {0.3,0.6,1.0}pt flat x slippage {0,0.1,0.2}pt
                on entry+stop fills only (market-order chase class; target/EOD assumed clean).
  (4) 1M TRUTH (stretch) — re-walk the extended-window trades' EXITS ONLY (entries/signals frozen)
                on real HistData M1 XAUUSD (~/gold-backtest/cache/m1.pkl), stop-first adverse
                tie-break, from entry time to the 15:45 ET flatten. Timestamp convention verified
                empirically against the dukascopy UTC series across DST boundaries: naive HistData
                timestamps are ALREADY America/New_York wall-clock (tz_localize directly, no offset
                shift). Stop/target levels are REBASED to the M1 series' own open at entry_time
                (preserving the frozen ATR-based distances) to avoid re-testing cross-vendor
                absolute-price noise instead of genuine intrabar sequencing.
  (5) VOL-GATE SENSITIVITY — gate threshold {0.60,0.65,0.70,0.75,0.80} on the extended window.
  (6) TRADE STREAM EXPORT — reports/gold_third_lane/gold_stream.csv for the portfolio lane
                (ts ET tz-aware, direction, entry, stop_pts, R, mae_r, risk_usd=stop_pts*$10/MGC).

PRE-REGISTERED PRIORS (printed in the run header, do not move after seeing results):
  - full-sample PF 1.45 is LUMPY: 2023 0.78 / 2024 1.67 / 2025 1.07 / 2026 2.29.
  - ~0.6 tr/wk -> ~2.6 trades/eval -> expected portfolio effect SMALL.
  - 15yr definitive verdict: simple gold strategies are dead after costs. If the extended window
    kills this edge, that IS the expected outcome -- report it plainly, don't rationalise it away.
  - PF > 1.8 full-sample on the extended window -> suspicious -> FREEZE + FLAG, don't ship.

KILL GATES:
  - extended-window full-sample PF < 1.15 at 0.6pt RT  -> KILL
  - 2019-2022 pseudo-OOS PF < 1.0                       -> KILL
  - vol-gate CLIFF (edge only works at exactly 0.70)    -> KILL

RESEARCH ONLY. Modifies nothing in the live bot. No commits.
"""
import os, json, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

NY = "America/New_York"
ORIG_5M_RTH = os.path.expanduser("~/trading-team/data/multi/XAU_5m_rth.csv")
DUKAS_24H = os.path.expanduser("~/trading-team/data/nq/XAU_5m_24h_dukascopy.csv")
M1_CACHE = os.path.expanduser("~/gold-backtest/cache/m1.pkl")
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports", "gold_third_lane")

DPP_MGC = 10.0          # MGC $/pt
STOP_ATR_MULT = 1.5
TGT_ATR_MULT = 2.25     # = 1.5R vs the 1.5*ATR stop
FLAT_ETM = 15 * 60 + 45  # 15:45 ET flatten, minutes-since-midnight
LATE_ETM = 15 * 60 + 45  # no new entries at/after 15:45 (matches source's `etm[i]>=945`... see NOTE)
FAITHFUL_COST = 0.30     # source's own flat per-trade cost (points)
BASE_FUTURES_COST = 0.60  # MGC-realistic RT baseline used for the ladder midpoint
DEFAULT_GATE = 0.70

PRIORS = """PRE-REGISTERED PRIORS
  full-sample PF 1.45 is LUMPY: 2023 0.78 / 2024 1.67 / 2025 1.07 / 2026 2.29 (per-year honesty is the point)
  ~0.6 tr/wk -> ~2.6 trades/eval -> expected portfolio effect SMALL
  15yr definitive verdict: simple gold strategies are dead after costs -- if the extended window
    kills this edge, that IS the expected outcome; report plainly
  PF > 1.8 full-sample -> suspicious -> FREEZE + FLAG
KILL GATES: extended-window full PF < 1.15 @ 0.6pt RT | 2019-2022 pseudo-OOS PF < 1.0 | vol-gate cliff
"""

# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _rth_15m_from_5m(x):
    """x: DataFrame indexed by tz-aware America/New_York DatetimeIndex, cols Open/High/Low/Close.
    Mirrors _gold_daily()'s own pipeline exactly: resample 5m->15m, then filter hour in [9,16)."""
    g = x.resample("15min").agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"}).dropna()
    g = g[(g.index.hour >= 9) & (g.index.hour < 16)]
    return g


def load_original_15m():
    """Canary data path: the exact file/pipeline position_sizer.py:_gold_daily() uses."""
    x = pd.read_csv(ORIG_5M_RTH, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert(NY)
    x = x[["Open", "High", "Low", "Close"]].astype(float)
    return _rth_15m_from_5m(x)


def load_extended_15m(start="2019-01-01", end="2026-12-31"):
    """Extended window: 5m 24h dukascopy -> RTH-filter (hour 9-16 NY, same convention as the
    source's own pre-filtered RTH file) -> resample to 15m -> re-filter (belt & suspenders, same
    as source)."""
    x = pd.read_csv(DUKAS_24H)
    x["timestamp"] = pd.to_datetime(x["timestamp"], utc=True)
    x = x.set_index("timestamp").tz_convert(NY)
    x = x[["Open", "High", "Low", "Close"]].astype(float)
    x = x[(x.index.hour >= 9) & (x.index.hour < 16)]
    g = _rth_15m_from_5m(x)
    g = g.loc[start:end]
    return g


_M1_NY_CACHE = None


def load_m1_ny():
    """HistData M1 XAUUSD, converted to tz-aware America/New_York. Verified empirically against
    the dukascopy UTC 5m series across 8 dates spanning 2019-2023, incl. either side of US DST
    changeovers (2021-03-15 pre-change, 2019-04-08 post-change, etc): naive HistData timestamps are
    ALREADY America/New_York wall-clock (i.e. they follow the US DST calendar, not a fixed UTC-5 --
    a first-pass fixed +5h/UTC test looked plausible on 2 sample dates but a wider date sweep showed
    the best-fit offset flips between +4h and +5h exactly at DST boundaries -> direct tz_localize is
    correct). Residual mean |Close diff| ~$0.2-$1.7/date after the fix = ordinary cross-vendor quote
    noise (different feed), not a timestamp bug."""
    global _M1_NY_CACHE
    if _M1_NY_CACHE is not None:
        return _M1_NY_CACHE
    m1 = pd.read_pickle(M1_CACHE)
    m1 = m1.copy()
    m1.index = m1.index.tz_localize(NY, ambiguous="NaT", nonexistent="NaT")
    m1 = m1[~m1.index.isna()]
    m1 = m1.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"})
    _M1_NY_CACHE = m1
    return m1


# ---------------------------------------------------------------------------
# Strategy (frozen rules, faithful reproduction of _gold_daily)
# ---------------------------------------------------------------------------

def run_trades(g, cost_rt=FAITHFUL_COST, slip=0.0, vol_gate=DEFAULT_GATE,
               stop_mult=STOP_ATR_MULT, tgt_mult=TGT_ATR_MULT):
    """Returns a DataFrame of trades (one row per short entry), columns:
    entry_time, day, entry, stop, target, exit, exit_reason, stop_pts, pnl_pts, mae_pts, mae_r.
    Faithful to _gold_daily(): stop checked before target within the same bar (adverse-first)."""
    c = g.Close
    ma = c.rolling(20).mean()
    sd = c.rolling(20).std()
    ub = ma + 2 * sd
    d = c.diff()
    up = d.clip(lower=0).rolling(14).mean()
    dn = (-d.clip(upper=0)).rolling(14).mean()
    rsi = 100 - 100 / (1 + up / dn)
    tr = pd.concat([g.High - g.Low, (g.High - c.shift()).abs(), (g.Low - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    dc = c.resample("D").last().dropna()
    lr = np.log(dc).diff()
    vr = lr.rolling(5).std() / lr.rolling(60).std()
    g = g.copy()
    g["vr"] = g.index.normalize().map(vr.shift(1).to_dict())

    H = g.High.values; L = g.Low.values; C = c.values; O = g.Open.values
    dts = g.index.normalize().values
    etm = (g.index.hour * 60 + g.index.minute).values
    RSI = rsi.values; UB = ub.values; ATR = atr.values; VR = g["vr"].values
    n = len(g); out = []; cur = None; traded_today = False

    for i in range(60, n - 1):
        if dts[i] != cur:
            cur = dts[i]
            traded_today = False
        if traded_today or etm[i] >= LATE_ETM or np.isnan(ATR[i]) or np.isnan(VR[i]) or VR[i] >= vol_gate:
            continue
        if not (C[i] > UB[i] and RSI[i] > 70):
            continue

        e = O[i + 1] - slip           # short entry: chase-slippage worsens the fill (sells lower)
        stop = e + stop_mult * ATR[i]
        tgt = e - tgt_mult * ATR[i]
        j = i + 1
        xp = None
        reason = None
        mae = 0.0
        while j < n and dts[j] == dts[i]:
            mae = max(mae, H[j] - e)
            if H[j] >= stop:
                xp = stop + slip      # stop-out is also a market chase, worsens the fill
                reason = "stop"
                break
            if L[j] <= tgt:
                xp = tgt
                reason = "target"
                break
            if etm[j] >= FLAT_ETM:
                xp = C[j]
                reason = "eod"
                break
            j += 1
        if xp is None:
            xp = C[min(j, n - 1)]
            reason = "eod_tail"

        stop_pts = stop_mult * ATR[i]
        pnl_pts = (e - xp) - cost_rt
        out.append(dict(entry_time=g.index[i + 1], day=cur, entry=e, stop=stop, target=tgt,
                         exit=xp, exit_reason=reason, stop_pts=stop_pts, pnl_pts=pnl_pts,
                         mae_pts=mae, mae_r=mae / stop_pts if stop_pts > 0 else np.nan))
        traded_today = True

    return pd.DataFrame(out)


def pf_wr(trades, pnl_col="pnl_pts"):
    if len(trades) == 0:
        return dict(n=0, pf=np.nan, wr=np.nan, totR=0.0)
    w = trades[trades[pnl_col] > 0]
    l = trades[trades[pnl_col] <= 0]
    lsum = abs(l[pnl_col].sum())
    pf = w[pnl_col].sum() / lsum if lsum > 0 else np.inf
    return dict(n=len(trades), pf=pf, wr=len(w) / len(trades), totR=trades[pnl_col].sum())


def per_year_table(trades, pnl_col="pnl_pts"):
    rows = []
    if len(trades) == 0:
        return pd.DataFrame(rows)
    t = trades.copy()
    t["year"] = pd.DatetimeIndex(t.entry_time).year
    for y, grp in t.groupby("year"):
        m = pf_wr(grp, pnl_col)
        rows.append(dict(year=y, **m))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 1m truth re-walk (exits only; entries/signals frozen)
# ---------------------------------------------------------------------------

def rewalk_1m(trades, cost_rt=FAITHFUL_COST):
    m1 = load_m1_ny()
    out = []
    for _, tr in trades.iterrows():
        start = tr.entry_time                                  # already tz-aware (America/New_York)
        day = pd.Timestamp(tr.day).tz_localize(start.tz)        # tr.day lost tz via .values normalize()
        end = day + pd.Timedelta(hours=15, minutes=45)
        try:
            window = m1.loc[start:end]
        except KeyError:
            window = pd.DataFrame()
        if len(window) == 0:
            out.append(dict(entry_time=tr.entry_time, exit=tr.exit, exit_reason=tr.exit_reason + "_nodata",
                             pnl_pts=tr.pnl_pts, stop_pts=tr.stop_pts))
            continue
        # HistData M1 is a DIFFERENT vendor from the dukascopy series the 15m signals/levels were
        # built on -- absolute price levels drift a few points between vendors (verified: mean
        # |Close diff| ~$0.4-$1.4). Comparing dukascopy-anchored stop/target against raw M1
        # High/Low would just be re-testing vendor-offset noise, not sequencing. Rebase: anchor
        # the frozen ATR-based stop/target DISTANCES (relative, not absolute) to the M1 series'
        # own open at entry_time, so only the exit SEQUENCING is being re-walked at 1m, not the
        # entry level.
        m1_anchor = window.Open.iloc[0]
        stop_dist = tr.stop - tr.entry
        tgt_dist = tr.entry - tr.target
        m1_stop = m1_anchor + stop_dist
        m1_tgt = m1_anchor - tgt_dist
        xp = None; reason = None
        for ts, row in window.iterrows():
            if row.High >= m1_stop:
                xp = m1_stop; reason = "stop"; break
            if row.Low <= m1_tgt:
                xp = m1_tgt; reason = "target"; break
        if xp is None:
            xp = window.Close.iloc[-1]; reason = "eod"     # already in m1's own (rebased) scale
        pnl_pts = (m1_anchor - xp) - cost_rt
        out.append(dict(entry_time=tr.entry_time, exit=xp, exit_reason=reason,
                         pnl_pts=pnl_pts, stop_pts=tr.stop_pts))
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUTDIR, exist_ok=True)
    print(PRIORS)
    report = {"priors": PRIORS.strip()}

    # ---- (1) CANARY ----
    print("== (1) CANARY: reproduce _gold_daily() on its own data path ==")
    g0 = load_original_15m()
    canary_trades = run_trades(g0, cost_rt=FAITHFUL_COST, vol_gate=DEFAULT_GATE)
    canary_full = pf_wr(canary_trades)
    canary_years = per_year_table(canary_trades)
    print(f"  n={canary_full['n']}  PF={canary_full['pf']:.3f}  WR={canary_full['wr']:.3f}")
    print(canary_years.to_string(index=False))

    claimed = {2023: 0.78, 2024: 1.67, 2025: 1.07, 2026: 2.29}
    mismatches = []
    yr_lookup = {int(r.year): r.pf for r in canary_years.itertuples()}
    for y, claim in claimed.items():
        actual = yr_lookup.get(y, np.nan)
        if np.isnan(actual) or abs(actual - claim) > 0.10:
            mismatches.append((y, claim, actual))
    canary_pf_claim = 1.45
    full_mismatch = abs(canary_full["pf"] - canary_pf_claim) > 0.10
    canary_ok = (not mismatches) and (not full_mismatch)
    print(f"  CANARY VERDICT: {'MATCH (proceed)' if canary_ok else 'MATERIAL MISMATCH -- STOP'}")
    report["canary"] = dict(full=canary_full, per_year=canary_years.to_dict("records"),
                             claimed=claimed, mismatches=mismatches, ok=bool(canary_ok))
    if not canary_ok:
        print("STOPPING: canary reproduction drifted from prior art by >0.1 PF. Not proceeding.")
        _write(report)
        return

    # ---- (2) EXTENDED WINDOW ----
    print("\n== (2) EXTENDED WINDOW: 2019-2026 on frozen rules (faithful cost=0.30) ==")
    gx = load_extended_15m("2019-01-01", "2026-12-31")
    ext_trades = run_trades(gx, cost_rt=FAITHFUL_COST, vol_gate=DEFAULT_GATE)
    ext_full = pf_wr(ext_trades)
    ext_years = per_year_table(ext_trades)
    print(f"  n={ext_full['n']}  PF={ext_full['pf']:.3f}  WR={ext_full['wr']:.3f}  totR={ext_full['totR']:.1f}pts")
    print(ext_years.to_string(index=False))

    pseudo_oos = ext_trades[pd.DatetimeIndex(ext_trades.entry_time).year <= 2022]
    pseudo_oos_m = pf_wr(pseudo_oos)
    print(f"  2019-2022 pseudo-OOS: n={pseudo_oos_m['n']}  PF={pseudo_oos_m['pf']:.3f}  WR={pseudo_oos_m['wr']:.3f}")

    # extended-window full PF at 0.6pt RT (kill-gate reference)
    ext_trades_06 = run_trades(gx, cost_rt=BASE_FUTURES_COST, vol_gate=DEFAULT_GATE)
    ext_full_06 = pf_wr(ext_trades_06)
    print(f"  @0.6pt RT (kill-gate ref): PF={ext_full_06['pf']:.3f}  n={ext_full_06['n']}")

    report["extended_window"] = dict(full_faithful=ext_full, per_year=ext_years.to_dict("records"),
                                      pseudo_oos_2019_2022=pseudo_oos_m, full_at_06rt=ext_full_06)

    # ---- (3) FUTURES COST LADDER ----
    print("\n== (3) FUTURES COST LADDER (MGC $10/pt) ==")
    ladder_rows = []
    for cost in (0.3, 0.6, 1.0):
        for slip in (0.0, 0.1, 0.2):
            tr = run_trades(gx, cost_rt=cost, slip=slip, vol_gate=DEFAULT_GATE)
            m = pf_wr(tr)
            ladder_rows.append(dict(cost_rt=cost, slip=slip, **m))
            print(f"  cost={cost:.1f} slip={slip:.1f}  n={m['n']}  PF={m['pf']:.3f}  WR={m['wr']:.3f}  totR={m['totR']:.1f}pts")
    ladder_df = pd.DataFrame(ladder_rows)
    report["cost_ladder"] = ladder_df.to_dict("records")

    # ---- (4) 1M TRUTH ----
    print("\n== (4) 1M TRUTH: re-walk extended-window exits on real M1 (entries/signals frozen) ==")
    m1_status = "ATTEMPTED"
    try:
        m1_ny = load_m1_ny()
        cov_ok = m1_ny.index.min() <= pd.Timestamp("2019-01-01", tz=NY) and m1_ny.index.max() >= pd.Timestamp("2025-12-31", tz=NY)
        if not cov_ok:
            raise RuntimeError(f"M1 cache coverage insufficient: {m1_ny.index.min()} -> {m1_ny.index.max()}")
        rewalked = rewalk_1m(ext_trades, cost_rt=FAITHFUL_COST)
        rw_full = pf_wr(rewalked)
        nodata_n = rewalked.exit_reason.str.endswith("_nodata").sum()
        print(f"  1m-rewalk: n={rw_full['n']}  PF={rw_full['pf']:.3f}  WR={rw_full['wr']:.3f}  (nodata trades: {nodata_n})")
        print(f"  5m-native (same trade set, same cost): PF={ext_full['pf']:.3f}  WR={ext_full['wr']:.3f}")
        shift = rw_full["pf"] - ext_full["pf"]
        print(f"  PF shift (1m truth - 5m native): {shift:+.3f}")
        report["one_min_truth"] = dict(status="OK", rewalked_full=rw_full, five_m_native=ext_full,
                                        pf_shift=shift, nodata_trades=int(nodata_n),
                                        timestamp_convention="HistData M1 naive timestamps are ALREADY "
                                        "America/New_York wall-clock (follow US DST calendar directly, no "
                                        "offset shift needed); verified via an 8-date sweep 2019-2023 spanning "
                                        "DST boundaries vs the dukascopy UTC series (a first-pass fixed-UTC-5 "
                                        "test looked plausible on 2 dates but broke down elsewhere -- best-fit "
                                        "offset flips +4h/+5h exactly at DST changeovers). Stop/target rebased "
                                        "to the M1 series' own entry-time open (relative ATR distances "
                                        "preserved) to avoid cross-vendor absolute-price noise.")
    except Exception as ex:
        m1_status = f"NOT WIREABLE CLEANLY: {ex}"
        print(f"  {m1_status}")
        print("  CAVEAT: this report's numbers are 5m-native. Per the VPC precedent, 5m-native -> "
              "1m-truth historically shifted PF by only ~+0.02 (mild); treat that as the best available "
              "prior for how much confidence to place in the 5m-native numbers above.")
        report["one_min_truth"] = dict(status=m1_status)

    # ---- (5) VOL-GATE SENSITIVITY ----
    print("\n== (5) VOL-GATE SENSITIVITY (extended window, faithful cost) ==")
    gate_rows = []
    for gate in (0.60, 0.65, 0.70, 0.75, 0.80):
        tr = run_trades(gx, cost_rt=FAITHFUL_COST, vol_gate=gate)
        m = pf_wr(tr)
        gate_rows.append(dict(gate=gate, **m))
        print(f"  gate={gate:.2f}  n={m['n']}  PF={m['pf']:.3f}  WR={m['wr']:.3f}")
    gate_df = pd.DataFrame(gate_rows)
    pf_at_70 = gate_df.loc[gate_df.gate == 0.70, "pf"].iloc[0]
    others = gate_df.loc[gate_df.gate != 0.70, "pf"]
    cliff = bool((others < 1.0).all() and pf_at_70 >= 1.15) if len(others) else False
    print(f"  CLIFF CHECK (edge only at exactly 0.70): {'CLIFF -- KILL' if cliff else 'plateau/gradual (pass)'}")
    report["vol_gate_sensitivity"] = dict(rows=gate_df.to_dict("records"), cliff=cliff)

    # ---- (6) TRADE STREAM EXPORT ----
    print("\n== (6) TRADE STREAM EXPORT (portfolio lane: faithful frozen rules, gate=0.70) ==")
    stream = ext_trades.copy()
    stream_out = pd.DataFrame({
        "ts": pd.DatetimeIndex(stream.entry_time),
        "direction": "short",
        "entry": stream.entry,
        "stop_pts": stream.stop_pts,
        "R": stream.pnl_pts / stream.stop_pts,
        "mae_r": stream.mae_r,
        "risk_usd": stream.stop_pts * DPP_MGC,
    })
    stream_path = os.path.join(OUTDIR, "gold_stream.csv")
    stream_out.to_csv(stream_path, index=False)
    print(f"  wrote {stream_path} ({len(stream_out)} trades)")

    # ---- KILL-GATE VERDICTS ----
    print("\n== KILL-GATE VERDICTS ==")
    kg_extended_06 = ext_full_06["pf"] < 1.15
    kg_pseudo_oos = pseudo_oos_m["pf"] < 1.0 if pseudo_oos_m["n"] > 0 else True
    kg_cliff = cliff
    print(f"  extended-window PF<1.15 @0.6RT: {'KILL' if kg_extended_06 else 'pass'} (PF={ext_full_06['pf']:.3f})")
    print(f"  2019-2022 pseudo-OOS PF<1.0:    {'KILL' if kg_pseudo_oos else 'pass'} (PF={pseudo_oos_m['pf']:.3f}, n={pseudo_oos_m['n']})")
    print(f"  vol-gate cliff:                 {'KILL' if kg_cliff else 'pass'}")
    freeze_flag = ext_full["pf"] > 1.8
    print(f"  full-sample PF>1.8 (freeze+flag): {'FLAG' if freeze_flag else 'no'} (PF={ext_full['pf']:.3f})")
    report["kill_gates"] = dict(extended_06_kill=bool(kg_extended_06), pseudo_oos_kill=bool(kg_pseudo_oos),
                                 cliff_kill=bool(kg_cliff), freeze_flag_pf_gt_1_8=bool(freeze_flag))

    _write(report, ext_years=ext_years, canary_years=canary_years, ladder_df=ladder_df, gate_df=gate_df)
    print(f"\nDone. Reports in {OUTDIR}/")


def _md_table(df):
    """Tiny markdown-table renderer (avoids a hard dependency on `tabulate`)."""
    if df is None or len(df) == 0:
        return ""
    cols = list(df.columns)

    def fmt(v):
        if isinstance(v, float):
            return f"{v:.4f}" if np.isfinite(v) else str(v)
        return str(v)

    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(fmt(row[c]) for c in cols) + " |")
    return "\n".join(lines)


def _write(report, ext_years=None, canary_years=None, ladder_df=None, gate_df=None):
    json_path = os.path.join(OUTDIR, "01_edge_revalidation.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    csv_path = os.path.join(OUTDIR, "01_edge_revalidation.csv")
    frames = []
    if canary_years is not None and len(canary_years):
        cy = canary_years.copy(); cy["section"] = "canary_per_year"; frames.append(cy)
    if ext_years is not None and len(ext_years):
        ey = ext_years.copy(); ey["section"] = "extended_per_year"; frames.append(ey)
    if ladder_df is not None and len(ladder_df):
        ld = ladder_df.copy(); ld["section"] = "cost_ladder"; frames.append(ld)
    if gate_df is not None and len(gate_df):
        gd = gate_df.copy(); gd["section"] = "vol_gate_sensitivity"; frames.append(gd)
    if frames:
        pd.concat(frames, ignore_index=True, sort=False).to_csv(csv_path, index=False)

    md_path = os.path.join(OUTDIR, "01_edge_revalidation.md")
    with open(md_path, "w") as f:
        f.write("# Gold Third-Lane -- Lane 1: Edge Revalidation\n\n")
        f.write("RESEARCH ONLY. Not deployed. Modifies nothing existing.\n\n")
        f.write("```\n" + PRIORS + "```\n\n")

        canary = report.get("canary", {})
        f.write("## (1) Canary\n\n")
        if canary:
            f.write(f"n={canary['full']['n']} PF={canary['full']['pf']:.3f} WR={canary['full']['wr']:.3f} "
                    f"-- verdict: {'MATCH' if canary['ok'] else 'MISMATCH (STOPPED)'}\n\n")
            if canary_years is not None and len(canary_years):
                f.write(_md_table(canary_years) + "\n\n")
        if not canary.get("ok", False):
            f.write("**STOPPED after canary mismatch. No further sections run.**\n")
            return

        ew = report.get("extended_window", {})
        f.write("## (2) Extended Window (2019-2026, faithful rules, cost=0.30pt)\n\n")
        f.write(f"n={ew['full_faithful']['n']} PF={ew['full_faithful']['pf']:.3f} "
                f"WR={ew['full_faithful']['wr']:.3f} totR={ew['full_faithful']['totR']:.1f}pts\n\n")
        if ext_years is not None and len(ext_years):
            f.write(_md_table(ext_years) + "\n\n")
        po = ew["pseudo_oos_2019_2022"]
        f.write(f"2019-2022 pseudo-OOS: n={po['n']} PF={po['pf']:.3f} WR={po['wr']:.3f}\n\n")
        f.write(f"@0.6pt RT (kill-gate reference): PF={ew['full_at_06rt']['pf']:.3f} n={ew['full_at_06rt']['n']}\n\n")

        f.write("## (3) Futures Cost Ladder (MGC $10/pt)\n\n")
        if ladder_df is not None and len(ladder_df):
            f.write(_md_table(ladder_df) + "\n\n")

        f.write("## (4) 1M Truth\n\n")
        omt = report.get("one_min_truth", {})
        if omt.get("status") == "OK":
            f.write(f"1m-rewalk PF={omt['rewalked_full']['pf']:.3f} vs 5m-native PF={omt['five_m_native']['pf']:.3f} "
                    f"(shift {omt['pf_shift']:+.3f}); nodata trades={omt['nodata_trades']}\n\n")
            f.write(f"Timestamp convention: {omt['timestamp_convention']}\n\n")
        else:
            f.write(f"Status: {omt.get('status')}\n\n")

        f.write("## (5) Vol-Gate Sensitivity\n\n")
        if gate_df is not None and len(gate_df):
            f.write(_md_table(gate_df) + "\n\n")
        f.write(f"Cliff verdict: {'CLIFF (KILL)' if report['vol_gate_sensitivity']['cliff'] else 'plateau/gradual (pass)'}\n\n")

        f.write("## Kill-Gate Verdicts\n\n")
        kg = report["kill_gates"]
        f.write(f"- extended-window PF<1.15 @0.6RT: {'KILL' if kg['extended_06_kill'] else 'pass'}\n")
        f.write(f"- 2019-2022 pseudo-OOS PF<1.0: {'KILL' if kg['pseudo_oos_kill'] else 'pass'}\n")
        f.write(f"- vol-gate cliff: {'KILL' if kg['cliff_kill'] else 'pass'}\n")
        f.write(f"- full-sample PF>1.8 (freeze+flag): {'FLAG' if kg['freeze_flag_pf_gt_1_8'] else 'no'}\n")


if __name__ == "__main__":
    main()
