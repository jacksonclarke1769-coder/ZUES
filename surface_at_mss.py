"""EMIT-002 / FORK-A surface-at-MSS emission path (prereg reports/fork_a/03_build_report.md).

The certified realtime emit (`strategy_engine_profileA.latest_signal` -> `model01.run(realtime=True)`
tail(3) scan) only surfaces a Profile-A OTE trade AFTER model01 finds the FILL bar -- for the
DELAYED class that is ~44 min past the MSS, past the fill window, so a live resting OTE limit can
no longer fill. Fork A (reports/fork_a/01+02) proved the OTE entry/stop/target/direction are
CAUSALLY FINAL at the MSS bar: `imp_hi/imp_lo` are frozen over [sweep_bar, mss_bar], the MSS breaks
on its own close, and 581/581 signals reproduce EXACTLY from data truncated at the MSS bar close.

This module SURFACES that already-final setup at the MSS bar's own close, so the resting OTE limit
is placed ~10 min (median 2 bars) before the historical fill instead of ~44 min after it.

HARD SCOPE: this file changes WHEN/HOW the signal is emitted. It does NOT change the detection math.
Sweep/MSS/displacement/OTE-zone detection is delegated **verbatim** to the frozen
`model01_sweep_mss_fvg._detect()` and the frozen entry/stop/target/risk formulas are copied
byte-for-byte out of `model01.run()`. Nothing here is imported by bot.py / auto_live.py unless an
operator explicitly selects the surface_at_mss emission mode; default behaviour is untouched.

emit-bar semantics (the k-vs-k+1 finding, see build report): a setup's MSS confirms on bar
`mss_bar`'s OWN close (`_detect`'s `c[k] > opp` break). This scanner reaches the sweep bar and
re-detects with the buffer ending EXACTLY at `mss_bar` (n = mss_bar+1), so it emits at **k =
mss_bar** for every gap -- including the 77% of signals with sweep->mss gap==1, which the reuse of
`model01.run(realtime=True)` would only reach at k+1 because of run()'s `while i < n-2` right-edge
guard. Emitting at k is causally clean (proven by the own-canary: identical emission from data
truncated at the mss_bar close) and it is what makes the gap==1 / fill==mss_bar+1 subset rescuable.
"""
import os
import sys

import numpy as np
import pandas as pd

FW = os.path.expanduser("~/trading-team/backtests/ict-nq-framework")
for _p in (os.path.join(FW, "engine"), os.path.join(FW, "models")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import primitives as P            # noqa: E402  frozen
import model01_sweep_mss_fvg as M1  # noqa: E402  frozen detection math


def _preamble(feats, params):
    """VERBATIM subset of model01.run()'s array construction (model01 lines 111-175) needed to
    call the frozen _detect() and reproduce run()'s entry/stop/target/session gates. Sets the M1
    module globals (TICK/PT_USD/SLIP/BUFFER/COMM) exactly as run() does so _detect + the fixed_rr
    formula below see identical values. Read-only w.r.t. model01."""
    M1.TICK, M1.PT_USD = M1.SPECS.get("NQ", (0.25, 20.0))
    p = {**M1.DEFAULT_PARAMS, **(params or {})}
    M1.SLIP = p["slip_ticks"] * M1.TICK
    M1.BUFFER = 2 * M1.TICK
    M1.COMM = p["comm"]
    df = feats.reset_index().rename(columns={"index": "ts", "timestamp": "ts"})
    o, h, l, c = (df[x].values for x in ["Open", "High", "Low", "Close"])
    n = len(df)
    ds = P.displacement_strength(df, 20)
    sh_at, sl_at, _, _ = P.last_known_swings(df, 3, 3)
    fv = P.fvgs(df)
    fdir = np.zeros(n); ftop = np.full(n, np.nan); fbot = np.full(n, np.nan)
    for _, r in fv.iterrows():
        ii = int(r.form_idx); fdir[ii] = r.direction; ftop[ii] = r.top; fbot[ii] = r.bottom
    fmid = (ftop + fbot) / 2

    def col(name):
        return df[name].values if name in df.columns else np.full(n, np.nan)

    spec_long = p["levels_long"] or M1.LEVELS_LONG
    spec_short = p["levels_short"] or M1.LEVELS_SHORT
    L = {nm: col(nm) for nm, _, _ in spec_long}
    Sx = {nm: col(nm) for nm, _, _ in spec_short}
    sess = df["session"].values if "session" in df.columns else np.array([""] * n)
    mins = pd.DatetimeIndex(df["ts"]).hour * 60 + pd.DatetimeIndex(df["ts"]).minute
    mins = mins.values
    t0 = M1._hhmm(p["t_start"]) if p["t_start"] else None
    t1 = M1._hhmm(p["t_end"]) if p["t_end"] else None
    return dict(o=o, h=h, l=l, c=c, n=n, ds=ds, sh_at=sh_at, sl_at=sl_at,
                fdir=fdir, fmid=fmid, fbot=fbot, ftop=ftop, L=L, Sx=Sx,
                spec_long=spec_long, spec_short=spec_short, et=p["entry_type"],
                sess=sess, mins=mins, t0=t0, t1=t1, p=p)


def _allowed_trigger(pre, i):
    """model01.run()'s allowed_trigger(i), copied verbatim (Profile A: no t-window, no sb_only)."""
    p = pre["p"]
    if pre["t0"] is not None and not (pre["t0"] <= pre["mins"][i] < pre["t1"]):
        return False
    if p["sb_only"]:
        return False  # in_sb_am not needed for Profile A (sb_only is always False here)
    return pre["sess"][i] in p["sessions"]


def _emission_from_setup(pre, setup, sweep_bar):
    """Reproduce model01.run()'s post-detect entry/stop/target/risk gates VERBATIM (model01
    lines 199-273 for the Profile-A fixed_rr/OTE path) from a _detect() setup tuple. Returns an
    emission dict, or None if run() would have rejected the setup (degenerate/too-wide risk, tier,
    or ny_am session filter -- matching classify_signals.py:94 `session == "ny_am"`)."""
    p = pre["p"]
    d, sweep_px, lvl_nm, tier, tier_pts, mss_bar, ez, zlo, zhi, disp = setup
    if tier not in p["tiers"]:
        return None
    # ny_am session filter is applied on the MSS bar, exactly as the certified 581 were selected.
    if pre["sess"][mss_bar] != "ny_am":
        return None
    entry = ez + d * M1.SLIP
    stop = (sweep_px - M1.BUFFER) if d > 0 else (sweep_px + M1.BUFFER)
    risk = (entry - stop) if d > 0 else (stop - entry)
    if risk <= 2 * M1.TICK:                 # degenerate / too tight (run() line 246)
        return None
    if risk > 0.012 * entry:                # stop-too-wide guard (run() line 249)
        return None
    target = entry + d * p["rr"] * risk     # fixed_rr (Profile A target_mode); run() line 272
    return dict(direction=("long" if d > 0 else "short"),
                entry=round(entry, 2), stop=round(stop, 2), target=round(target, 2),
                rr=float(p["rr"]), risk_pts=round(float(risk), 2),
                sweep_bar=int(sweep_bar), mss_bar=int(mss_bar),
                liq_swept=lvl_nm, disp_strength=int(abs(disp)),
                session=str(pre["sess"][mss_bar]))


def _detect_at(pre, i):
    """Long-first, then short -- run()'s exact _detect ordering (model01 lines 185-187)."""
    p = pre["p"]
    setup = None
    if 1 in p["dirs"]:
        setup = M1._detect(i, +1, pre["l"], pre["h"], pre["c"], pre["o"],
                           pre["L"], pre["spec_long"], pre["sl_at"], pre["sh_at"], pre["ds"],
                           pre["fdir"], pre["fmid"], pre["fbot"], pre["ftop"], pre["et"], p["ote_depth"])
    if setup is None and -1 in p["dirs"]:
        setup = M1._detect(i, -1, pre["l"], pre["h"], pre["c"], pre["o"],
                           pre["Sx"], pre["spec_short"], pre["sl_at"], pre["sh_at"], pre["ds"],
                           pre["fdir"], pre["fmid"], pre["fbot"], pre["ftop"], pre["et"], p["ote_depth"])
    return setup


def _anchor_from_run(feats, params):
    """No-overlap free bar = 1 + the exit_bar of the last CERTIFIED trade that completes strictly
    before the current (last) bar, taken DIRECTLY from the frozen model01.run() so the trade
    timeline and exit bars are byte-identical to the certified backtest. run() spans ALL sessions and
    its no-overlap (`i = exit_i + 1`) chains across them, so this anchor -- not a ny_am-only view --
    is what makes the surfaced sweep match run()'s pairing. Causal: every returned trade exits before
    `last` (the current setup's fill is after `last`, so run(realtime=True) reserves it and it is NOT
    in the trade list). Returns None when run() takes no prior trade -> the whole W_MSS window is free.
    """
    tr = M1.run(feats, "NQ", params, realtime=True)
    if tr is None or not len(tr):
        return None
    return int(tr["exit_bar"].max()) + 1


def _reject_jump(pre, i, setup):
    """model01.run()'s advance for an EARLIER setup (its MSS confirms before `last`), copied
    VERBATIM (run() lines 229-250) so the march lands on the SAME sweep bar run() pairs with the MSS
    at `last`. For the Profile-A config the only active rejections are the fill window (`i =
    mss_bar+1`) and the two risk guards (`i = fill+1`); the other gates (tier/first-presented/smt/
    daily-fvg/wdraw/dbias/pd/liquidity-target/require-draw) are all off for these params. An ACCEPTED
    earlier trade would complete before `last` and is therefore excluded up front by the no-overlap
    anchor (start_bar), so the accept branch is unreachable with a correct anchor; it advances past
    the fill as a fail-safe (never observed across the certified set). Returns run()'s next `i`."""
    p = pre["p"]
    n = pre["n"]
    h, l = pre["h"], pre["l"]
    d, sweep_px, lvl_nm, tier, tier_pts, mss_bar, ez, zlo, zhi, disp = setup
    fill = None
    for m in range(mss_bar + 1, min(mss_bar + 1 + M1.W_FILL, n)):
        if d > 0 and l[m] <= ez:
            fill = m; break
        if d < 0 and h[m] >= ez:
            fill = m; break
    if fill is None:
        return mss_bar + 1                       # run() line 242 (fill window past edge / no retrace)
    entry = ez + d * M1.SLIP
    stop = (sweep_px - M1.BUFFER) if d > 0 else (sweep_px + M1.BUFFER)
    risk = (entry - stop) if d > 0 else (stop - entry)
    if risk <= 2 * M1.TICK:                       # run() line 246-247 (degenerate / too tight)
        return fill + 1
    if risk > 0.012 * entry:                      # run() line 249-250 (stop-too-wide guard)
        return fill + 1
    return fill + 1                               # accepted earlier trade: excluded by anchor (fail-safe)


def latest_mss_emission(feats, params=None, start_bar=None):
    """REALTIME surface-at-MSS emit. Given the rolling 5m feature buffer whose LAST row is the
    just-closed bar, return the OTE resting-limit emission (entry/stop/target/direction) for a
    Profile-A setup whose MSS confirms on THAT last bar, or None. Uses only bars <= the last bar
    (== <= mss_bar); no post-MSS information anywhere. emit-bar = mss_bar (k).

    SWEEP PAIRING (parity fix, reports/fork_a/03_build_report.md): when several sweeps co-confirm an
    MSS at `last`, model01.run() pairs a SPECIFIC one determined by its sequential scan -- it resumes
    at the no-overlap free bar (one past the prior trade's exit) and then advances past EARLIER setups
    exactly by run()'s reject-jumps (`i = mss_bar+1` when the FVG never fills, `i = fill+1` when the
    stop is degenerate/too-wide). A naive ascending "first sweep whose MSS==last" scan picks an
    earlier phantom sweep run() actually skipped, giving a different impulse leg (this was the 25/581
    sweep_ok=FALSE defect). We therefore REPLAY run()'s scan: start at the free bar and march with
    run()'s exact reject-jumps until the first sweep whose MSS confirms on `last` -- that IS run()'s
    pick -- and emit it at k (the mss_bar close), never k+1.

    `start_bar` (optional) = the no-overlap free bar (one past the prior position's exit). Uses only
    PAST position state (the prior trade has already exited by `last`) -- no future information. When
    None it is derived from the frozen model01.run() trade timeline (`_anchor_from_run`), so the
    stateless live path and the truncation canary both reproduce run()'s pairing self-containedly;
    the live bot may also pass its real flat-since bar."""
    pre = _preamble(feats, params)
    n = pre["n"]
    if n < 3:
        return None
    last = n - 1
    if start_bar is None:
        start_bar = _anchor_from_run(feats, pre["p"])
    # March run()'s exact scan from the no-overlap free bar. The sweep for an MSS at `last` lives in
    # [last-W_MSS, last-1]; a free bar earlier than that just means the window is fully free, but a
    # reject-jump originating before the window can still skip a within-window phantom, so we honour
    # the true free bar rather than clamping up to the window edge.
    lo = max(2, int(start_bar)) if start_bar is not None else max(2, last - M1.W_MSS)
    i = lo
    while i < last:
        if not _allowed_trigger(pre, i):
            i += 1; continue
        setup = _detect_at(pre, i)
        if setup is None:
            i += 1; continue
        if setup[3] not in pre["p"]["tiers"]:      # tier gate (run() line 200)
            i += 1; continue
        mss_bar = setup[5]
        if mss_bar == last:                        # run()'s paired sweep for the MSS confirming at k
            return _emission_from_setup(pre, setup, i)
        if mss_bar > last:                         # unreachable (MSS window <= last); guard
            i += 1; continue
        i = _reject_jump(pre, i, setup)            # earlier setup -> advance exactly as run() would
    return None


def scan_all_mss_emissions(feats, params=None):
    """OFFLINE parity/verification: emulate streaming by asking, for every bar, "did a Profile-A
    OTE setup's MSS confirm on THIS bar?" -- i.e. call latest_mss_emission on the buffer truncated
    at each bar. Returns a DataFrame of every surface-at-MSS emission keyed by mss_bar. This is the
    causal image of the live path (each row uses only bars <= its own mss_bar). No no-overlap /
    one-position gating (the live bot enforces that separately); this is the raw emission stream."""
    pre = _preamble(feats, params)
    n = pre["n"]
    rows = []
    seen = set()
    # A setup's MSS confirms at `last` with sweep in [last-W_MSS, last-1]; walk last forward.
    for last in range(2, n):
        i_start = max(2, last - M1.W_MSS)
        for i in range(i_start, last):
            if not _allowed_trigger(pre, i):
                continue
            setup = _detect_at(pre, i)
            if setup is None:
                continue
            if setup[5] != last:
                continue
            emis = _emission_from_setup(pre, setup, i)
            if emis is not None and last not in seen:
                seen.add(last)
                rows.append(emis)
            break
    return pd.DataFrame(rows)
