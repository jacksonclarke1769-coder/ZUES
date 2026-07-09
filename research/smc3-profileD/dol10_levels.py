"""
Causal DOL (draw-on-liquidity) level construction for the SMC3 exit-model
audit (STEP 2 of the 10_dol_exit_audit spec).

Research-only.  Read-only reuse of `confirmed_pivots` from
`../sweep_engine.py` and `resample_ohlc` from `../engine.py` -- NEITHER FILE
IS MODIFIED.  Everything new lives in this directory.

HEADLINE causal DOL source set (exactly the operator-hardened list):
  1. PDH / PDL   -- previous ET-calendar-day high/low.  Known at that day's
                    close boundary (next ET midnight, a safe upper bound).
  2. PWH / PWL   -- previous ET trading-WEEK high/low.  Known only after
                    that week has closed (boundary = next Monday 00:00 ET).
  3. ONH / ONL   -- overnight-session (18:00 ET prior day -> 09:30 ET) high
                    /low.  Known only once the overnight session completes
                    (boundary = 09:30 ET that day).
  4. PSH / PSL   -- prior 18:00-ET-anchored 24h session high/low (matches
                    sweep_engine.prior_levels' convention).  Known once that
                    session closes (boundary = next 18:00 ET).
  5. Confirmed 1H swing H/L  -- ta.pivothigh/low(L,L) on 60m bars, confirmed
                    L bars later (lag enforced).  Pool search for the
                    NEAREST still-unswept level (not just the latest pivot).
  6. Confirmed 4H swing H/L  -- same construction on 240m bars.
  7. Equal highs/lows -- >=2 confirmed 1H pivots of the same type within 4
                    ticks; becomes a DOL from the SECOND pivot's own
                    confirmation instant onward.
  8. HTF pocket  -- SMC3's own 60m confirmed-pivot level (pivot len 3,
                    ffill carry-forward) -- i.e. "already-known active
                    liquidity pockets" = literally the model's own
                    buySideLevel/sellSideLevel arrays, recomputed here with
                    the identical construction smc3_engine.py uses
                    internally (no import of private engine state; this
                    is a byte-for-byte parallel calc so nothing in
                    smc3_engine.py needs to change further).

NOT in the headline set (kept as a separately-labeled variant only,
per the operator's hardening note): `session_so_far` -- the running
high/low of the CURRENT 18:00-anchored session, using only bars strictly
BEFORE the entry bar.  Never mixed into the headline nearest-DOL pool.

Causality contract: every source's per-1m-bar array is constructed via
searchsorted on a CLOSED boundary timestamp array (mirrors
request.security(lookahead_off) / sweep_engine.prior_levels), with an
in-code assert that the boundary used is <= the query bar's open time.
Every candidate returned by `nearest_causal_dol` additionally satisfies
`target_known_at <= entry_time` (checked, not assumed) -- callers must
still assert this per-trade (dol10_pathstats.py does).
"""
from __future__ import annotations

import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import resample_ohlc  # noqa: E402
from sweep_engine import confirmed_pivots  # noqa: E402  (read-only reuse)

TICK = 0.25
NS_MIN = 60_000_000_000
NS_HOUR = 3600_000_000_000
NS_DAY = 24 * NS_HOUR


# --------------------------------------------------------------------------- #
# Generic "prior completed group" stepper (mirrors sweep_engine.prior_levels)
# --------------------------------------------------------------------------- #
def _prior_from_groups(vals_hi: np.ndarray, vals_lo: np.ndarray,
                       close_ns: np.ndarray, query_open_ns: np.ndarray):
    """For each query bar's OPEN ns, return (hi, lo, known_at_ns) of the most
    recently COMPLETED group (close_ns <= query_open_ns).  Asserts causality."""
    k = np.searchsorted(close_ns, query_open_ns, side="right") - 1
    ok_idx = np.clip(k, 0, len(close_ns) - 1)
    hi = np.where(k >= 0, vals_hi[ok_idx], np.nan)
    lo = np.where(k >= 0, vals_lo[ok_idx], np.nan)
    known = np.where(k >= 0, close_ns[ok_idx], -1)
    ok = (k < 0) | (close_ns[ok_idx] <= query_open_ns)
    assert ok.all(), "prior-group lookahead violation"
    return hi, lo, known


# --------------------------------------------------------------------------- #
# 1) PDH/PDL -- ET calendar day
# --------------------------------------------------------------------------- #
def _pdh_pdl(df1m: pd.DataFrame, t_open_ns: np.ndarray):
    et = df1m.index.tz_convert("America/New_York")
    et_date = pd.Series(et.date, index=df1m.index)
    day_hi = df1m.groupby(et_date)["high"].max()
    day_lo = df1m.groupby(et_date)["low"].min()
    d_index = pd.to_datetime([str(d) for d in day_hi.index])
    day_close_ns = (d_index.tz_localize("America/New_York").tz_convert("UTC")
                    .view("int64") + np.int64(24) * 3600 * 1_000_000_000)
    return _prior_from_groups(day_hi.to_numpy(float), day_lo.to_numpy(float),
                              np.asarray(day_close_ns, dtype="int64"), t_open_ns)


# --------------------------------------------------------------------------- #
# 2) PWH/PWL -- ET trading week (Mon-Sun buckets), known after that week closes
# --------------------------------------------------------------------------- #
def _pwh_pwl(df1m: pd.DataFrame, t_open_ns: np.ndarray):
    et = df1m.index.tz_convert("America/New_York")
    et_date = pd.Series(et.date, index=df1m.index)
    monday = pd.to_datetime(et_date) - pd.to_timedelta(pd.to_datetime(et_date).dt.weekday, unit="D")
    wk_hi = df1m.groupby(monday.values)["high"].max()
    wk_lo = df1m.groupby(monday.values)["low"].min()
    mondays = pd.to_datetime(wk_hi.index)
    # week closes at the START of the following Monday (00:00 ET) -- safe
    # upper bound (real futures week ends Fri ~17:00 ET, this is generous)
    next_monday = mondays + pd.Timedelta(days=7)
    wk_close_ns = np.asarray(next_monday.tz_localize("America/New_York").tz_convert("UTC")
                             .view("int64"), dtype="int64")
    order = np.argsort(wk_close_ns)
    return _prior_from_groups(wk_hi.to_numpy(float)[order], wk_lo.to_numpy(float)[order],
                              wk_close_ns[order], t_open_ns)


# --------------------------------------------------------------------------- #
# 3) ONH/ONL -- overnight session [prior 18:00 ET, 09:30 ET), known at 09:30 ET
# --------------------------------------------------------------------------- #
def _onh_onl(df1m: pd.DataFrame, t_open_ns: np.ndarray):
    et = df1m.index.tz_convert("America/New_York")
    tod_min = np.asarray(et.hour) * 60 + np.asarray(et.minute)
    date = np.asarray(et.date)
    is_over = (tod_min >= 18 * 60) | (tod_min < 9 * 60 + 30)
    # bars after 18:00 belong to the NEXT calendar day's overnight window;
    # bars before 09:30 belong to the SAME calendar day's overnight window
    over_day = date.copy()
    later = tod_min >= 18 * 60
    over_day[later] = (pd.to_datetime(date[later]) + pd.Timedelta(days=1)).date
    g = pd.DataFrame({"day": over_day, "high": df1m["high"].to_numpy(float),
                      "low": df1m["low"].to_numpy(float)})[is_over]
    on_hi = g.groupby("day")["high"].max()
    on_lo = g.groupby("day")["low"].min()
    d_index = pd.to_datetime([str(d) for d in on_hi.index])
    close_ts = d_index.tz_localize("America/New_York") + pd.Timedelta(hours=9, minutes=30)
    close_ns = np.asarray(close_ts.tz_convert("UTC").view("int64"), dtype="int64")
    order = np.argsort(close_ns)
    return _prior_from_groups(on_hi.to_numpy(float)[order], on_lo.to_numpy(float)[order],
                              close_ns[order], t_open_ns)


# --------------------------------------------------------------------------- #
# 4) PSH/PSL -- 18:00-ET-anchored 24h session (matches sweep_engine convention)
# --------------------------------------------------------------------------- #
def _psh_psl(df1m: pd.DataFrame, t_open_ns: np.ndarray):
    et = df1m.index.tz_convert("America/New_York")
    et_shift = et - pd.Timedelta(hours=18)
    sess_date = pd.Series(et_shift.date, index=df1m.index)
    ss_hi = df1m.groupby(sess_date)["high"].max()
    ss_lo = df1m.groupby(sess_date)["low"].min()
    s_index = pd.to_datetime([str(d) for d in ss_hi.index])
    sess_close_ns = np.asarray((s_index + pd.Timedelta(days=1)).tz_localize("America/New_York")
                     .tz_convert("UTC").view("int64") + np.int64(18) * 3600 * 1_000_000_000, dtype="int64")
    return _prior_from_groups(ss_hi.to_numpy(float), ss_lo.to_numpy(float),
                              sess_close_ns, t_open_ns)


# --------------------------------------------------------------------------- #
# 5/6) Confirmed swing pools (1H / 4H) -- nearest still-unswept level search
# --------------------------------------------------------------------------- #
def _swing_pool(df1m: pd.DataFrame, tf_min: int, piv_len: int):
    ex = resample_ohlc(df1m, tf_min)
    E_open_ns = ex.index.view("int64").astype("int64")
    tf_ns = np.int64(tf_min) * 60 * 1_000_000_000
    E_close_ns = E_open_ns + tf_ns
    Eh = ex["high"].to_numpy(float); El = ex["low"].to_numpy(float)
    is_ph, is_pl = confirmed_pivots(Eh, El, piv_len)
    ph_idx = np.where(is_ph)[0]; ph_price = Eh[ph_idx]; ph_conf = ph_idx + piv_len
    pl_idx = np.where(is_pl)[0]; pl_price = El[pl_idx]; pl_conf = pl_idx + piv_len
    ph_known = E_close_ns[np.clip(ph_conf, 0, len(E_close_ns) - 1)]
    pl_known = E_close_ns[np.clip(pl_conf, 0, len(E_close_ns) - 1)]
    o = np.argsort(ph_known); ph_price, ph_known = ph_price[o], ph_known[o]
    o = np.argsort(pl_known); pl_price, pl_known = pl_price[o], pl_known[o]
    return dict(ph_price=ph_price, ph_known=ph_known, pl_price=pl_price, pl_known=pl_known)


def _nearest_above(pool_price, pool_known, entry_price, entry_time_ns):
    m = (pool_known <= entry_time_ns) & (pool_price > entry_price)
    if not m.any():
        return np.nan, -1
    idx = np.argmin(pool_price[m])
    cand_price = pool_price[m][idx]; cand_known = pool_known[m][idx]
    return float(cand_price), int(cand_known)


def _nearest_below(pool_price, pool_known, entry_price, entry_time_ns):
    m = (pool_known <= entry_time_ns) & (pool_price < entry_price)
    if not m.any():
        return np.nan, -1
    idx = np.argmax(pool_price[m])
    cand_price = pool_price[m][idx]; cand_known = pool_known[m][idx]
    return float(cand_price), int(cand_known)


# --------------------------------------------------------------------------- #
# 7) Equal highs/lows -- >=2 confirmed 1H pivots (same type) within 4 ticks
# --------------------------------------------------------------------------- #
def _equal_hl_pool(pool_1h: dict, tol_pts: float = 4 * TICK):
    def _cluster(price, known):
        out_price, out_known = [], []
        for j in range(1, len(price)):
            # nearest earlier pivot (by confirm time) within tolerance
            prior = price[:j]
            if len(prior) == 0:
                continue
            diffs = np.abs(prior - price[j])
            i = np.argmin(diffs)
            if diffs[i] <= tol_pts:
                out_price.append((prior[i] + price[j]) / 2.0)
                out_known.append(known[j])   # known at the 2nd (later) pivot's confirm time
        if not out_price:
            return np.array([]), np.array([], dtype="int64")
        arr_p = np.array(out_price); arr_k = np.array(out_known, dtype="int64")
        o = np.argsort(arr_k)
        return arr_p[o], arr_k[o]

    eh_price, eh_known = _cluster(pool_1h["ph_price"], pool_1h["ph_known"])
    el_price, el_known = _cluster(pool_1h["pl_price"], pool_1h["pl_known"])
    return dict(ph_price=eh_price, ph_known=eh_known, pl_price=el_price, pl_known=el_known)


# --------------------------------------------------------------------------- #
# 8) HTF pocket -- SMC3's own 60m confirmed pivot (len 3), ffill carry-forward
#    Byte-parallel to smc3_engine's buySideLevel/sellSideLevel construction.
# --------------------------------------------------------------------------- #
def _htf_pocket(df1m: pd.DataFrame, t_open_ns: np.ndarray, piv_len: int = 3):
    from smc3_engine import _pivot, _ffill, _step_idx, _gather  # local, read-only reuse
    htf = resample_ohlc(df1m, 60)
    htf_open_ns = htf.index.view("int64").astype("int64")
    htf_close_ns = htf_open_ns + np.int64(60) * NS_MIN
    ph = _pivot(htf["high"].to_numpy(float), piv_len, piv_len, high=True)
    pl = _pivot(htf["low"].to_numpy(float), piv_len, piv_len, high=False)
    buy_side = _ffill(ph)   # confirmed pivot HIGH  (liquidity above)
    sell_side = _ffill(pl)  # confirmed pivot LOW   (liquidity below)
    idx60 = _step_idx(htf_close_ns, t_open_ns)
    above = _gather(idx60, buy_side)
    below = _gather(idx60, sell_side)
    src_close = np.where(idx60 >= 0, htf_close_ns[np.clip(idx60, 0, None)], -1)
    ok = (idx60 < 0) | (src_close <= t_open_ns)
    assert ok.all(), "htf-pocket lookahead violation"
    known = np.where(idx60 >= 0, src_close, -1)
    return above, below, known


# --------------------------------------------------------------------------- #
# session-so-far H/L (SEPARATE, non-headline variant)
# --------------------------------------------------------------------------- #
def _session_so_far(df1m: pd.DataFrame, t_open_ns: np.ndarray):
    et = df1m.index.tz_convert("America/New_York")
    et_shift = et - pd.Timedelta(hours=18)
    sess_date = pd.Series(et_shift.date, index=df1m.index)
    hi = df1m["high"].to_numpy(float); lo = df1m["low"].to_numpy(float)
    dfh = pd.DataFrame({"sess": sess_date.to_numpy(), "high": hi, "low": lo})
    # shift(1) then cummax/cummin within the session -> STRICTLY prior bars only
    run_hi = dfh.groupby("sess")["high"].apply(lambda s: s.shift(1).cummax()).to_numpy()
    run_lo = dfh.groupby("sess")["low"].apply(lambda s: s.shift(1).cummin()).to_numpy()
    known = t_open_ns.copy()   # conservative: known as of this bar's own open
    return run_hi, run_lo, known


# --------------------------------------------------------------------------- #
# Master builder
# --------------------------------------------------------------------------- #
class DolLevels:
    """Holds every per-1m-bar source array + provides nearest_causal_dol()."""
    def __init__(self, df1m: pd.DataFrame):
        t_open_ns = df1m.index.view("int64").astype("int64")
        self.t_open_ns = t_open_ns
        self.PDH, self.PDL, self.PDH_known = _pdh_pdl(df1m, t_open_ns)
        _, _, self.PDL_known = self.PDH, self.PDL, self.PDH_known  # same known array (day)
        self.PWH, self.PWL, self.PW_known = _pwh_pwl(df1m, t_open_ns)
        self.ONH, self.ONL, self.ON_known = _onh_onl(df1m, t_open_ns)
        self.PSH, self.PSL, self.PS_known = _psh_psl(df1m, t_open_ns)
        self.pool_1h = _swing_pool(df1m, 60, 2)
        self.pool_4h = _swing_pool(df1m, 240, 2)
        self.pool_eq = _equal_hl_pool(self.pool_1h)
        self.htf_above, self.htf_below, self.htf_known = _htf_pocket(df1m, t_open_ns, piv_len=3)
        self.sf_hi, self.sf_lo, self.sf_known = _session_so_far(df1m, t_open_ns)

    def headline_candidates(self, bar_i: int, entry_price: float, entry_time_ns: int, is_long: bool):
        """Return list of (price, type, known_at_ns) candidates from the
        HEADLINE causal set only (session_so_far excluded)."""
        cands = []
        if is_long:
            for val, kn, tag in [
                (self.PDH[bar_i], self.PDH_known[bar_i], "PDH"),
                (self.PWH[bar_i], self.PW_known[bar_i], "PWH"),
                (self.ONH[bar_i], self.ON_known[bar_i], "ONH"),
                (self.PSH[bar_i], self.PS_known[bar_i], "PSH"),
                (self.htf_above[bar_i], self.htf_known[bar_i], "htf_pocket"),
            ]:
                if np.isfinite(val) and val > entry_price and kn >= 0 and kn <= entry_time_ns:
                    cands.append((float(val), tag, int(kn)))
            p, k = _nearest_above(self.pool_1h["ph_price"], self.pool_1h["ph_known"], entry_price, entry_time_ns)
            if np.isfinite(p):
                cands.append((p, "confirmed_1H", k))
            p, k = _nearest_above(self.pool_4h["ph_price"], self.pool_4h["ph_known"], entry_price, entry_time_ns)
            if np.isfinite(p):
                cands.append((p, "confirmed_4H", k))
            p, k = _nearest_above(self.pool_eq["ph_price"], self.pool_eq["ph_known"], entry_price, entry_time_ns)
            if np.isfinite(p):
                cands.append((p, "equal_highs", k))
        else:
            for val, kn, tag in [
                (self.PDL[bar_i], self.PDH_known[bar_i], "PDL"),
                (self.PWL[bar_i], self.PW_known[bar_i], "PWL"),
                (self.ONL[bar_i], self.ON_known[bar_i], "ONL"),
                (self.PSL[bar_i], self.PS_known[bar_i], "PSL"),
                (self.htf_below[bar_i], self.htf_known[bar_i], "htf_pocket"),
            ]:
                if np.isfinite(val) and val < entry_price and kn >= 0 and kn <= entry_time_ns:
                    cands.append((float(val), tag, int(kn)))
            p, k = _nearest_below(self.pool_1h["pl_price"], self.pool_1h["pl_known"], entry_price, entry_time_ns)
            if np.isfinite(p):
                cands.append((p, "confirmed_1H", k))
            p, k = _nearest_below(self.pool_4h["pl_price"], self.pool_4h["pl_known"], entry_price, entry_time_ns)
            if np.isfinite(p):
                cands.append((p, "confirmed_4H", k))
            p, k = _nearest_below(self.pool_eq["pl_price"], self.pool_eq["pl_known"], entry_price, entry_time_ns)
            if np.isfinite(p):
                cands.append((p, "equal_lows", k))
        return cands

    def nearest_causal_dol(self, bar_i: int, entry_price: float, entry_time_ns: int, is_long: bool):
        """(target_price, target_type, target_known_at_ns) of the NEAREST
        headline causal DOL, or (nan, 'none', -1) if no candidate exists.
        Also returns artifact=True if any candidate violated causality
        (should never trigger given the asserts upstream; defensive only)."""
        cands = self.headline_candidates(bar_i, entry_price, entry_time_ns, is_long)
        artifact = any(kn > entry_time_ns for _, _, kn in cands)
        cands = [c for c in cands if c[2] <= entry_time_ns]
        if not cands:
            return np.nan, "none", -1, artifact
        if is_long:
            best = min(cands, key=lambda c: c[0])
        else:
            best = max(cands, key=lambda c: c[0])
        return best[0], best[1], best[2], artifact

    def source_target(self, source: str, bar_i: int, entry_price: float,
                      entry_time_ns: int, is_long: bool):
        """Single-source DOL target (price, known_at_ns) for the exit-battery
        families #4 ("X only").  NaN/-1 if unavailable, behind price, or
        would violate causality (defensive; should never trigger)."""
        if source == "pdh_pdl":
            val = self.PDH[bar_i] if is_long else self.PDL[bar_i]
            kn = self.PDH_known[bar_i]
        elif source == "prior_session":
            val = self.PSH[bar_i] if is_long else self.PSL[bar_i]
            kn = self.PS_known[bar_i]
        elif source == "htf_pocket":
            val = self.htf_above[bar_i] if is_long else self.htf_below[bar_i]
            kn = self.htf_known[bar_i]
        elif source == "confirmed_1h":
            pool = self.pool_1h
            fn = _nearest_above if is_long else _nearest_below
            key = "ph" if is_long else "pl"
            val, kn = fn(pool[f"{key}_price"], pool[f"{key}_known"], entry_price, entry_time_ns)
        elif source == "confirmed_4h":
            pool = self.pool_4h
            fn = _nearest_above if is_long else _nearest_below
            key = "ph" if is_long else "pl"
            val, kn = fn(pool[f"{key}_price"], pool[f"{key}_known"], entry_price, entry_time_ns)
        elif source == "equal_hl":
            pool = self.pool_eq
            fn = _nearest_above if is_long else _nearest_below
            key = "ph" if is_long else "pl"
            val, kn = fn(pool[f"{key}_price"], pool[f"{key}_known"], entry_price, entry_time_ns)
        else:
            raise ValueError(f"unknown source {source}")
        if not np.isfinite(val) or kn < 0 or kn > entry_time_ns:
            return np.nan, -1
        if is_long and val <= entry_price:
            return np.nan, -1
        if (not is_long) and val >= entry_price:
            return np.nan, -1
        return float(val), int(kn)

    def session_so_far_dol(self, bar_i: int, entry_price: float, is_long: bool):
        """SEPARATE non-headline variant: session-so-far H/L, only if still
        un-swept (above/below entry as appropriate)."""
        if is_long:
            v = self.sf_hi[bar_i]
            if np.isfinite(v) and v > entry_price:
                return float(v), "session_so_far_high", int(self.sf_known[bar_i])
        else:
            v = self.sf_lo[bar_i]
            if np.isfinite(v) and v < entry_price:
                return float(v), "session_so_far_low", int(self.sf_known[bar_i])
        return np.nan, "none", -1
