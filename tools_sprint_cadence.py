"""EVAL-SIZING SPRINT — cadence/recycle/start-timing (2026-07-05).

RESEARCH ONLY. SIM CONDITIONAL — replay of one historical path. Modifies NOTHING existing;
new tool only. Reuses (by import, never copies):
  - tools_sim_parity_check.load_rows / group_by_day  (trade-level replay, canary-exact)
  - tools_sim_parity_check.SPEC_50K / CAP / BUDGET_FIXED / EXPIRE_DAYS  (the deployed cap-10 config)
  - eval_forecast.load_distribution / replay / valid_starts  (the certified conditional forecaster,
    reused verbatim for workstream 1G rule R3 — no reimplementation of the forecast math)

CANARY (mandatory, checked first in main()): the plain baseline replay (no recycle, no start-timing
change — i.e. simulate() with no callbacks, over the same "starts" filter as
tools_sim_parity_check.run_config) must reproduce the certified cap-10 row EXACTLY:
pass 47.8 / bust 15.9 / expire 36.2 / median 16d, n=395. If it does not match, the script aborts
before writing any report (do not trust downstream numbers built on an unverified replay).

engine: `simulate()` below is a generalization of tools_sim_parity_check.simulate_start that
decouples the eval's start day from the historical A-signal-day list (unique_days is a SPARSE list
of days that actually carried an A trade, not a full trading calendar) so that:
  (a) 1H can start the clock on a calendar day with no signal that day (dead-clock burn), and
  (b) 1G can install per-trade / per-day "should I stop trading now" hooks (on_trade / on_day_close)
      without touching the certified bookkeeping order (day-trough DLL clamp -> bust check -> EOD
      ratchet/lock -> bust check -> pass check), which is copied verbatim from
      tools_account_size_research.eval_run / tools_sim_parity_check.simulate_start.

Workstreams:
  1G — RECYCLE RULES (rules.py-style R0-R4): when to abandon a live attempt early, official funnel
       (PASS/BUST/EXPIRE/ABANDONED, mutually exclusive) + counterfactual ("would have been" =
       the R0 baseline outcome for that same start, since abandonment never changes trades already
       taken) + BUSINESS view (stationary per-slot-year approximation: attempts/yr = 365.25 /
       mean-occupancy-days; funded/yr = attempts/yr * pass%; fee drag both columns).
  1H — ACCOUNT-START TIMING: 7 start policies over the trailing-24-month window (+ full-history
       cross-check), funnel %, median days-to-first-trade (dead-clock burn), fee-adjusted E[$]/attempt
       and per-year (attempts/yr taken from the OBSERVED start count in-window, not assumed).
  3A — CADENCE / SLOT MODEL: N parallel slots (restart-on-death, N in {1,2,3,4}) plus three fixed-
       injection cadences (1/wk, 1/5td, 2/wk, no capping) over the trailing 24 months, using the
       actual historical outcome sequence (OVERLAP CAVEAT: this is a replay of ONE historical path —
       slots/attempts starting near the same calendar date share the same trade stream and will
       cluster, they are NOT independent draws). Also months-to-20-PA-cap (funded accounts assumed
       to occupy an Apex account slot for ~16 months post-pass; active eval slots always count).

Fee/funded constants (per tools_eval_sizing_sweep.py FUNDED_GROSS/ACTIVATION_FEE, vault Funded
Funnel 2026-07-05 — LOW-CONFIDENCE): funded net $12,728 (= $12,827 gross - $99 activation), eval fee
STICKER $131 (both fee columns are reported everywhere below; the $30 PROMO column is LOW-CONF
per task spec and flagged as such in every table/report it appears in).
"""
import os
import sys
import csv
import json
import time
import warnings
from collections import defaultdict

warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tools_sim_parity_check as P     # load_rows, group_by_day, SPEC_50K, CAP, BUDGET_FIXED, EXPIRE_DAYS
import eval_forecast as EF             # load_distribution, replay, valid_starts (reused, not copied)
import market_calendar as MC           # is_trading_day, is_market_holiday

SPEC = P.SPEC_50K
CAP = P.CAP
BUDGET = P.BUDGET_FIXED
EXPIRE_DAYS = P.EXPIRE_DAYS

FUNDED_GROSS = 12_827.0
ACTIVATION_FEE = 99.0
FUNDED_NET = FUNDED_GROSS - ACTIVATION_FEE      # 12,728.0
FEE_STICKER = 131.0
FEE_PROMO = 30.0                                # LOW-CONF (per task spec)
PA_LIFE_DAYS = 16 * 30                           # "funded accts live ~16mo" -> ~480 calendar days
PA_CAP = 20                                      # Apex account cap (incl. active evals)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "reports", "eval_passrate_sprint")
FRAME = "SIM CONDITIONAL — replay of one historical path"


# ================================================================== shared engine
def simulate(days_trades, unique_days, start_date, cap=CAP, on_trade=None, on_day_close=None,
             max_days=EXPIRE_DAYS):
    """Generalized trade-level replay of ONE eval attempt starting its clock at an arbitrary
    calendar `start_date` (need not be a day with a signal). Plain baseline sizing throughout
    (fixed $1,200 / cap-10, no cushion/P3 gates) — bookkeeping order copied verbatim from
    tools_sim_parity_check.simulate_start / tools_account_size_research.eval_run.

    on_trade(state) -> True to abandon (stop taking NEW trades from this instant; trades already
        taken today still settle). state has: bal, thr, day_real, elapsed, streak (consecutive
        losing trades, 0-based running count), cushion (intraday bal - thr, post-trade).
    on_day_close(state) -> True to abandon at this day's EOD (state: bal, thr, elapsed — the
        day's post-ratchet settled values). Checked only if the day did not already terminate
        (BUST/PASS) and no on_trade abandonment fired today.

    Returns dict(verdict, days, abandon_day, first_trade_day). verdict in
    {"PASS","BUST","EXPIRE","ABANDONED","INCOMPLETE"}.
    """
    sb, tr, tg = SPEC["start"], SPEC["trail"], SPEC["target"]
    stop, dll = SPEC["stop"], SPEC["dll"]
    thr, bal, peak, locked = sb - tr, sb, sb, False
    abandon_day, first_trade_day = None, None
    loss_streak = 0
    state = {}

    for d in unique_days:
        if d < start_date:
            continue
        elapsed = (d - start_date).days
        if elapsed > max_days:
            return dict(verdict="EXPIRE", days=max_days, abandon_day=abandon_day,
                        first_trade_day=first_trade_day)

        day_real, day_trough, day_stopped, abandoned = 0.0, 0.0, False, False
        for t in days_trades[d]:
            if day_stopped or abandoned:
                break
            risk1 = t["risk_usd"]
            q = min(cap, int(BUDGET // risk1))
            if q < 1:
                continue
            if first_trade_day is None:
                first_trade_day = d
            pnl = t["R"] * risk1 * q
            mae = min(0.0, t["mae_r"]) * risk1 * q
            day_trough = min(day_trough, day_real + mae)
            day_real += pnl
            loss_streak = loss_streak + 1 if pnl < 0 else 0
            if day_real <= -stop:
                day_stopped = True
            state.update(bal=bal, thr=thr, day_real=day_real, elapsed=elapsed,
                        streak=loss_streak, cushion=(bal + day_real) - thr)
            if on_trade is not None and on_trade(state):
                abandoned = True
                abandon_day = elapsed

        if day_trough <= -dll:
            real, trough = -dll, -dll
        else:
            real, trough = day_real, day_trough
        if bal + min(0.0, trough) <= thr:
            return dict(verdict="BUST", days=elapsed, abandon_day=abandon_day,
                        first_trade_day=first_trade_day)
        bal += real
        peak = max(peak, bal)
        if not locked:
            thr = max(thr, peak - tr)
            if peak - tr >= sb + 100.0:
                thr = sb + 100.0
                locked = True
        if bal <= thr:
            return dict(verdict="BUST", days=elapsed, abandon_day=abandon_day,
                        first_trade_day=first_trade_day)
        if bal >= sb + tg:
            return dict(verdict="PASS", days=elapsed, abandon_day=abandon_day,
                        first_trade_day=first_trade_day)
        if abandoned:
            return dict(verdict="ABANDONED", days=elapsed, abandon_day=abandon_day,
                        first_trade_day=first_trade_day)
        if on_day_close is not None:
            state.update(bal=bal, thr=thr, elapsed=elapsed)
            if on_day_close(state):
                return dict(verdict="ABANDONED", days=elapsed, abandon_day=elapsed,
                            first_trade_day=first_trade_day)
    return dict(verdict="INCOMPLETE", days=None, abandon_day=abandon_day,
                first_trade_day=first_trade_day)


def valid_start_indices(unique_days):
    """Same filter as tools_sim_parity_check.run_config: only starts with >EXPIRE_DAYS of runway
    left in the dataset (so INCOMPLETE never happens on a real attempt)."""
    last_day = unique_days[-1]
    return [i for i, d in enumerate(unique_days) if (last_day - d).days > EXPIRE_DAYS]


def canary(days_trades, unique_days):
    """Mandatory canary: plain simulate() with no callbacks must match the certified cap-10 row."""
    starts = valid_start_indices(unique_days)
    res = [simulate(days_trades, unique_days, unique_days[i]) for i in starts]
    n = len(res)
    p = round(100 * sum(1 for r in res if r["verdict"] == "PASS") / n, 1)
    b = round(100 * sum(1 for r in res if r["verdict"] == "BUST") / n, 1)
    x = round(100 * sum(1 for r in res if r["verdict"] == "EXPIRE") / n, 1)
    pass_days = [r["days"] for r in res if r["verdict"] == "PASS"]
    md = int(np.median(pass_days)) if pass_days else 0
    ok = (p == P.CANARY_EXPECT["pass_pct"] and b == P.CANARY_EXPECT["bust_pct"] and
          x == P.CANARY_EXPECT["exp_pct"] and md == P.CANARY_EXPECT["med_days"] and
          n == P.CANARY_EXPECT["n"])
    return dict(pass_pct=p, bust_pct=b, exp_pct=x, med_days=md, n=n, ok=ok), res, starts


# ================================================================== 1G — recycle rules
def make_r1(): return lambda st: st["streak"] >= 3
def make_r2(): return lambda st: st["streak"] >= 2 and st["cushion"] < 700.0


def make_r3(ef_days, valid_starts_cache):
    def fast_forecast(balance, threshold, days_left):
        if days_left not in valid_starts_cache:
            valid_starts_cache[days_left] = EF.valid_starts(ef_days, days_left)
        starts = valid_starts_cache[days_left]
        if not starts:
            return None, None
        res = [EF.replay(ef_days, s, balance, threshold, days_left) for s in starts]
        n = len(res)
        pass_pct = 100 * sum(1 for v, _ in res if v == "PASS") / n
        exp_pct = 100 * sum(1 for v, _ in res if v == "EXPIRE") / n
        return pass_pct, exp_pct

    def r3(st):
        days_left = EXPIRE_DAYS - st["elapsed"]
        if days_left <= 0:
            return False
        pass_pct, exp_pct = fast_forecast(st["bal"], st["thr"], days_left)
        if pass_pct is None:
            return False
        return pass_pct < 10.0 and exp_pct > 70.0
    return r3


def make_r4(): return lambda st: st["elapsed"] >= 20 and (st["bal"] - SPEC["start"]) < 0


def run_1g(days_trades, unique_days, baseline_res, starts):
    ef_days = EF.load_distribution()
    valid_starts_cache = {}
    rules = {
        "R0 none (baseline)": (None, None),
        "R1 stop after 3 consecutive A losses": (make_r1(), None),
        "R2 stop after 2 consecutive losses AND cushion<$700": (make_r2(), None),
        "R3 stop when P(pass)<10% AND P(expire)>70%": (None, make_r3(ef_days, valid_starts_cache)),
        "R4 stop after day 20 if pnl<0": (None, make_r4()),
    }
    rows = []
    for label, (on_trade, on_day_close) in rules.items():
        if on_trade is None and on_day_close is None:
            res = baseline_res
        else:
            res = [simulate(days_trades, unique_days, unique_days[i],
                            on_trade=on_trade, on_day_close=on_day_close) for i in starts]
        n = len(res)
        n_pass = sum(1 for r in res if r["verdict"] == "PASS")
        n_bust = sum(1 for r in res if r["verdict"] == "BUST")
        n_exp = sum(1 for r in res if r["verdict"] == "EXPIRE")
        n_aband = sum(1 for r in res if r["verdict"] == "ABANDONED")
        pass_pct, bust_pct, exp_pct, aband_pct = (round(100 * x / n, 1)
                                                   for x in (n_pass, n_bust, n_exp, n_aband))

        # counterfactual for the abandoned subset: what the SAME start would have resolved to
        # under R0 (baseline never abandons — trades before the trigger are identical either way)
        aband_idx = [i for i, r in zip(starts, res) if r["verdict"] == "ABANDONED"]
        cf = [baseline_res[starts.index(i)] for i in aband_idx]
        cf_pass = sum(1 for r in cf if r["verdict"] == "PASS")
        cf_bust = sum(1 for r in cf if r["verdict"] == "BUST")
        cf_exp = sum(1 for r in cf if r["verdict"] == "EXPIRE")
        forgone_pass_pct = round(100 * cf_pass / n, 1) if n else 0.0

        # occupancy: for ABANDONED, the slot frees at the abandon day; else the terminal day
        occ_days = [(r["abandon_day"] if r["verdict"] == "ABANDONED" else
                     (r["days"] if r["days"] is not None else EXPIRE_DAYS)) for r in res]
        mean_days = float(np.mean(occ_days))
        attempts_per_year = 365.25 / mean_days if mean_days > 0 else 0.0
        funded_per_year = attempts_per_year * pass_pct / 100.0
        e_per_attempt_gross = pass_pct / 100.0 * FUNDED_NET
        for fee_label, fee in (("sticker_131", FEE_STICKER), ("promo_30_LOWCONF", FEE_PROMO)):
            rows.append(dict(
                rule=label, fee_col=fee_label, n=n,
                pass_pct=pass_pct, bust_pct=bust_pct, exp_pct=exp_pct, abandoned_pct=aband_pct,
                cf_would_pass_pct=round(100 * cf_pass / max(1, len(cf)), 1) if cf else 0.0,
                cf_would_bust_pct=round(100 * cf_bust / max(1, len(cf)), 1) if cf else 0.0,
                cf_would_expire_pct=round(100 * cf_exp / max(1, len(cf)), 1) if cf else 0.0,
                forgone_pass_pct_of_all_starts=forgone_pass_pct,
                mean_occupancy_days=round(mean_days, 1),
                attempts_per_slot_year=round(attempts_per_year, 2),
                funded_per_slot_year=round(funded_per_year, 3),
                e_per_attempt=round(e_per_attempt_gross - fee, 0),
                e_per_slot_year=round(funded_per_year * FUNDED_NET - attempts_per_year * fee, 0),
            ))
    return rows


# ================================================================== 1H — start timing
def trading_day_list(d0, d1):
    days = pd.date_range(d0.tz_localize(None) if d0.tzinfo else d0,
                          d1.tz_localize(None) if d1.tzinfo else d1, freq="D")
    return [d for d in days if MC.is_trading_day(d.date())]


def week_holiday(monday_naive):
    return any(MC.is_market_holiday((monday_naive + pd.Timedelta(days=k)).date()) for k in range(5))


def start_dates_for_policies(unique_days, window_start, window_end, tz):
    """Build start-date lists for each 1H policy, localized to `tz` to match unique_days."""
    tdl = trading_day_list(window_start, window_end)
    tdl_naive = [d.normalize() for d in tdl]
    policies = {}

    policies["every Monday"] = [d for d in tdl_naive if d.weekday() == 0]
    policies["every Tuesday"] = [d for d in tdl_naive if d.weekday() == 1]
    policies["Monday+Thursday staggered pairs"] = [d for d in tdl_naive if d.weekday() in (0, 3)]
    policies["every 5 trading days"] = tdl_naive[::5]

    d0 = window_start.tz_localize(None) if window_start.tzinfo else window_start
    every7, cur = [], d0.normalize()
    while cur <= (window_end.tz_localize(None) if window_end.tzinfo else window_end):
        every7.append(cur)
        cur = cur + pd.Timedelta(days=7)
    policies["every 7 calendar days"] = every7

    # skip holiday-shortened weeks: like "every Monday" but the whole ISO week is dropped if any
    # weekday Mon-Fri that week is a market holiday.
    skip_starts = []
    for d in tdl_naive:
        if d.weekday() != 0:
            continue
        if not week_holiday(d):
            skip_starts.append(d)
    policies["skip holiday-shortened weeks"] = skip_starts

    # signal-triggered: per ISO week in-window, start = trading day immediately BEFORE the week's
    # first kept-signal day (from unique_days). One start per week that has >=1 signal.
    ud_naive = [(d.tz_localize(None) if d.tzinfo else d) for d in unique_days]
    ud_in_win = [d for d in ud_naive if window_start.tz_localize(None) <= d <= window_end.tz_localize(None)] \
        if window_start.tzinfo else [d for d in ud_naive if window_start <= d <= window_end]
    by_week = defaultdict(list)
    for d in ud_in_win:
        by_week[(d.isocalendar()[0], d.isocalendar()[1])].append(d)
    sig_starts = []
    all_td_idx = {d: k for k, d in enumerate(tdl_naive)}
    for wk in sorted(by_week):
        first_sig = min(by_week[wk])
        # previous trading day before first_sig, from the full trading-day list
        prior = [d for d in tdl_naive if d < first_sig]
        if prior:
            sig_starts.append(prior[-1])
        else:
            sig_starts.append(first_sig)
    policies["signal-triggered (day before week's first A signal)"] = sig_starts

    if tz is not None:
        for name in policies:
            policies[name] = [d.tz_localize(tz) if d.tzinfo is None else d for d in policies[name]]
    return policies


def run_1h(days_trades, unique_days, window_label, window_start, window_end):
    tz = unique_days[0].tzinfo
    last_day = unique_days[-1]
    policies = start_dates_for_policies(unique_days, window_start, window_end, tz)
    years = (window_end - window_start).days / 365.25
    rows = []
    for name, starts in policies.items():
        # keep only starts with full runway left in the dataset (avoid INCOMPLETE)
        starts = [d for d in starts if (last_day - d).days > EXPIRE_DAYS]
        if not starts:
            continue
        res = [simulate(days_trades, unique_days, d) for d in starts]
        n = len(res)
        n_pass = sum(1 for r in res if r["verdict"] == "PASS")
        n_bust = sum(1 for r in res if r["verdict"] == "BUST")
        n_exp = sum(1 for r in res if r["verdict"] == "EXPIRE")
        pass_pct, bust_pct, exp_pct = (round(100 * x / n, 1) for x in (n_pass, n_bust, n_exp))
        dead = [(r["first_trade_day"] - s).days for r, s in zip(res, starts)
                if r["first_trade_day"] is not None]
        n_no_trade = sum(1 for r in res if r["first_trade_day"] is None)
        med_dead = int(np.median(dead)) if dead else None
        attempts_per_year_observed = n / years if years > 0 else 0.0
        e_gross = pass_pct / 100.0 * FUNDED_NET
        for fee_label, fee in (("sticker_131", FEE_STICKER), ("promo_30_LOWCONF", FEE_PROMO)):
            rows.append(dict(
                window=window_label, policy=name, fee_col=fee_label, n=n,
                pass_pct=pass_pct, bust_pct=bust_pct, exp_pct=exp_pct,
                median_days_to_first_trade=med_dead, n_never_traded=n_no_trade,
                starts_per_year_observed=round(attempts_per_year_observed, 1),
                e_per_attempt=round(e_gross - fee, 0),
                e_per_year=round((e_gross - fee) * attempts_per_year_observed, 0),
            ))
    return rows


# ================================================================== 3A — cadence / slot model
def chain_fixed_cadence(days_trades, unique_days, starts_all, window_end):
    """Fixed-injection cadence: start a NEW independent attempt on every scheduled date regardless
    of whether earlier attempts have finished (no slot cap) — models the concurrency the business
    WOULD need at that cadence. Returns list of (start, end, verdict)."""
    last_day = unique_days[-1]
    out = []
    for s in starts_all:
        if (last_day - s).days <= EXPIRE_DAYS:
            continue
        r = simulate(days_trades, unique_days, s)
        end = s + pd.Timedelta(days=r["days"] if r["days"] is not None else EXPIRE_DAYS)
        out.append((s, end, r["verdict"]))
    return out


def peak_concurrency(intervals):
    events = []
    for s, e, _ in intervals:
        events.append((s, 1))
        events.append((e, -1))
    events.sort(key=lambda x: (x[0], -x[1]))
    cur = peak = 0
    for _, delta in events:
        cur += delta
        peak = max(peak, cur)
    return peak


def chain_maintain_n(days_trades, unique_days, n_slots, window_start, window_end):
    """restart-on-death: N slots, each immediately starts a fresh attempt the calendar day after its
    previous attempt terminates (PASS/BUST/EXPIRE). Slots are staggered by 2 trading days at
    inception so they are not exact clones of one another (OVERLAP CAVEAT: same historical trade
    stream underlies every slot — this is a replay of one path, not independent trials)."""
    tdl = trading_day_list(window_start, window_end + pd.Timedelta(days=EXPIRE_DAYS))
    tdl = [d.tz_localize(unique_days[0].tzinfo) for d in tdl]
    last_day = unique_days[-1]
    attempts = []
    for slot in range(n_slots):
        cur = tdl[min(slot * 2, len(tdl) - 1)]
        while cur <= window_end and (last_day - cur).days > EXPIRE_DAYS:
            r = simulate(days_trades, unique_days, cur)
            days_used = r["days"] if r["days"] is not None else EXPIRE_DAYS
            end = cur + pd.Timedelta(days=days_used)
            attempts.append(dict(slot=slot, start=cur, end=end, verdict=r["verdict"]))
            cur = end + pd.Timedelta(days=1)
    return attempts


def months_to_cap(attempts, n_slots, window_start, window_end):
    """Project month-by-month headcount = n_slots (active evals, always occupied under
    restart-on-death) + funded accounts still within their ~16mo PA life; return first month index
    (0-based from window_start) where headcount would exceed PA_CAP, or None if never within the
    simulated + 16mo-pad horizon."""
    passes = [a["end"] for a in attempts if a["verdict"] == "PASS"]
    horizon_end = window_end + pd.Timedelta(days=EXPIRE_DAYS + PA_LIFE_DAYS)
    m = 0
    cur = window_start
    while cur <= horizon_end:
        alive_pa = sum(1 for p in passes if p <= cur < p + pd.Timedelta(days=PA_LIFE_DAYS))
        headcount = n_slots + alive_pa
        if headcount > PA_CAP:
            return m
        cur = cur + pd.Timedelta(days=30)
        m += 1
    return None


def run_3a(days_trades, unique_days, window_start, window_end):
    tz = unique_days[0].tzinfo
    tdl_naive = trading_day_list(window_start, window_end)
    tdl = [d.tz_localize(tz) for d in tdl_naive]
    months = (window_end - window_start).days / 30.44
    last_day = unique_days[-1]
    rows = []

    # fixed-injection cadences (no slot cap; report peak concurrency needed)
    cadences = {
        "1 start/week": [d for d in tdl if d.weekday() == 0],
        "1 per 5 trading days": tdl[::5],
        "2/week": [d for d in tdl if d.weekday() in (0, 3)],
    }
    for name, starts in cadences.items():
        attempts = chain_fixed_cadence(days_trades, unique_days, starts, window_end)
        n = len(attempts)
        n_pass = sum(1 for _, _, v in attempts if v == "PASS")
        fees = n * FEE_STICKER
        peak = peak_concurrency(attempts)
        rows.append(dict(
            config=f"fixed cadence: {name}", n_slots="uncapped", n_starts=n,
            funded_accounts=n_pass, funded_per_month=round(n_pass / months, 3) if months else 0.0,
            fees_per_funded_sticker=round(fees / n_pass, 0) if n_pass else None,
            peak_concurrent_slots_needed=peak, months_to_20cap=None,
        ))

    # maintain-N-active (restart-on-death), N=1..4
    prev_fpm = None
    for n_slots in (1, 2, 3, 4):
        attempts = chain_maintain_n(days_trades, unique_days, n_slots, window_start, window_end)
        n = len(attempts)
        n_pass = sum(1 for a in attempts if a["verdict"] == "PASS")
        fpm = round(n_pass / months, 3) if months else 0.0
        fees = n * FEE_STICKER
        mtc = months_to_cap(attempts, n_slots, window_start, window_end)
        marginal = round(fpm - prev_fpm, 3) if prev_fpm is not None else None
        rows.append(dict(
            config=f"maintain-N-active restart-on-death N={n_slots}", n_slots=n_slots,
            n_starts=n, funded_accounts=n_pass, funded_per_month=fpm,
            fees_per_funded_sticker=round(fees / n_pass, 0) if n_pass else None,
            peak_concurrent_slots_needed=n_slots,
            months_to_20cap=mtc, marginal_funded_per_month_vs_prev_n=marginal,
        ))
        prev_fpm = fpm
    return rows


# ================================================================== I/O
def write_csv_md(rows, name, title, notes):
    if not rows:
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUT_DIR, f"{name}.csv")
    md_path = os.path.join(OUT_DIR, f"{name}.md")
    # ordered union of keys across all rows (not every row shares every column, e.g. fixed-cadence
    # rows in 3A have no marginal_funded_per_month_vs_prev_n)
    fieldnames = []
    for r in rows:
        for k in r:
            if k not in fieldnames:
                fieldnames.append(k)
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        w.writeheader()
        w.writerows(rows)
    with open(md_path, "w") as f:
        f.write(f"# {title}\n\n**{FRAME}**\n\n")
        for n in notes:
            f.write(f"- {n}\n")
        f.write("\n")
        f.write("| " + " | ".join(fieldnames) + " |\n")
        f.write("|" + "|".join(["---"] * len(fieldnames)) + "|\n")
        for r in rows:
            f.write("| " + " | ".join(str(r.get(k, "")) for k in fieldnames) + " |\n")
    print(f"  [saved] {csv_path}")
    print(f"  [saved] {md_path}")


# ================================================================== main
def main():
    t0 = time.time()
    print("loading frames + locked A stream (exit3 + D1c, 1m truth)…", flush=True)
    rows = P.load_rows()
    days_trades, unique_days = P.group_by_day(rows)
    print(f"  n_trades={len(rows)} n_signal_days={len(unique_days)} "
          f"span={unique_days[0].date()}..{unique_days[-1].date()} "
          f"({time.time() - t0:.1f}s)", flush=True)

    print("\nCANARY (plain baseline, no recycle / no start-timing change — must match certified "
          "cap-10 row EXACTLY):", flush=True)
    can, baseline_res, starts = canary(days_trades, unique_days)
    print(f"  got:      pass={can['pass_pct']} bust={can['bust_pct']} exp={can['exp_pct']} "
          f"med={can['med_days']}d n={can['n']}")
    print(f"  expected: pass={P.CANARY_EXPECT['pass_pct']} bust={P.CANARY_EXPECT['bust_pct']} "
          f"exp={P.CANARY_EXPECT['exp_pct']} med={P.CANARY_EXPECT['med_days']}d "
          f"n={P.CANARY_EXPECT['n']}")
    if not can["ok"]:
        print("\n[CANARY MISMATCH] STOPPING — generalized simulate() does not reproduce the "
              "certified row. Not writing any report.", flush=True)
        return
    print("[canary OK]\n", flush=True)

    last_day = unique_days[-1]
    tz = last_day.tzinfo
    window_end = last_day - pd.Timedelta(days=EXPIRE_DAYS)
    window_start_24mo = window_end - pd.Timedelta(days=730)
    window_start_full = unique_days[0]

    # ---------------- 1G
    print("1G — recycle rules …", flush=True)
    rows_1g = run_1g(days_trades, unique_days, baseline_res, starts)
    write_csv_md(rows_1g, "recycle_rules", "1G — Recycle / Abandonment Rules", [
        "R0 = baseline (never abandons); R1-R4 abandonment triggers checked live during the "
        "replay; R0's own row IS every other rule's counterfactual ('would have been'), since "
        "trades already taken before an abandonment trigger are identical to the baseline path.",
        "Official funnel (pass_pct/bust_pct/exp_pct/abandoned_pct) is mutually exclusive per rule.",
        "cf_* columns = outcome distribution of ONLY the abandoned subset had they NOT abandoned "
        "(the R0 result for those same starts). forgone_pass_pct_of_all_starts = the 3-loss-style "
        "recoveries given up, as a % of ALL starts under that rule.",
        "Business view (stationary per-slot-year approximation): attempts/slot-year = 365.25 / "
        "mean occupancy days (occupancy = abandon day if ABANDONED else natural terminal day); "
        "funded/slot-year = attempts/slot-year * pass%; e_per_slot_year nets fees at that cadence. "
        "Two fee_col rows per rule: sticker $131 and LOW-CONF promo $30.",
    ])

    # ---------------- 1H
    print("1H — account-start timing …", flush=True)
    rows_1h = run_1h(days_trades, unique_days, "last-24mo", window_start_24mo, window_end)
    rows_1h += run_1h(days_trades, unique_days, "full-history", window_start_full, window_end)
    write_csv_md(rows_1h, "account_start_timing", "1H — Account-Start Timing Policies", [
        "window='last-24mo' is the primary comparison; window='full-history' is the corroboration "
        "check across the whole ~5yr dataset.",
        "median_days_to_first_trade = dead-clock burn (calendar days from the eval's clock-start "
        "to its first actual A trade); n_never_traded = starts with no A signal before the "
        "30-day clock (or dataset) ran out.",
        "starts_per_year_observed is measured directly from the in-window start count (not "
        "assumed from the policy's nominal cadence), so it already reflects holiday gaps etc.",
        "Two fee_col rows per policy: sticker $131 and LOW-CONF promo $30.",
    ])

    # ---------------- 3A
    print("3A — cadence / slot model …", flush=True)
    rows_3a = run_3a(days_trades, unique_days, window_start_24mo, window_end)
    write_csv_md(rows_3a, "attempt_cadence", "3A — Attempt Cadence / Slot Model", [
        "Trailing-24-month window. OVERLAP CAVEAT: every slot/cadence replays the SAME historical "
        "A-trade stream, so overlapping attempts are correlated / clustered outcomes, not "
        "independent trials — read this as one historical path, not a Monte Carlo.",
        "Fixed-cadence rows (1/wk, 1/5td, 2/wk) are UNCAPPED (a new attempt starts on schedule "
        "regardless of whether earlier ones finished) — peak_concurrent_slots_needed is how many "
        "slots that cadence would actually require, not an assumed N.",
        "maintain-N-active rows are restart-on-death (an attempt is replaced the calendar day "
        "after it terminates PASS/BUST/EXPIRE) at a FIXED slot count N=1..4, staggered 2 trading "
        "days apart at inception so slots are not exact clones.",
        "months_to_20cap: month index (0-based from window start) at which projected headcount "
        "(N active eval slots + funded accounts still within their ~16mo PA life) would exceed "
        "Apex's 20-account cap; None = not reached within the simulated + 16mo-pad horizon.",
        "marginal_funded_per_month_vs_prev_n = funded/month(N) - funded/month(N-1), the requested "
        "marginal value of each additional slot.",
    ])

    print(f"\ndone in {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
