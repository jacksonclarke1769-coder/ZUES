"""Apex 4.0 EOD 50K-eval mechanics, encoded as executable tests against the certification harness.

Purpose: pin down the exact death/pause/lock rules implemented in tools_account_size_research.py
(day_rows/eval_run) and apex_funded_40.py (daily_series) with SYNTHETIC fixtures, so that any future
edit to those functions that changes Apex-rules behavior (rules drift) breaks this suite loudly —
rather than silently shifting the certified pass/bust numbers.

SPEC 50K referenced throughout (tools_account_size_research.SPECS["50K"]):
  start 50,000  trail 2,500  target 3,000  dll 1,000  stop 550
Initial threshold = start - trail = 47,500. Lock point = start + 100 = 50,100 once
peak - trail >= start + 100 (i.e. peak >= 52,600).

All day/event fixtures are synthetic (built by hand in this file), not loaded from real data.
"""
import pandas as pd

import tools_account_size_research as H
import apex_funded_40 as F

SPEC50 = H.SPECS["50K"]                      # start 50,000 / trail 2,500 / target 3,000 / dll 1,000 / stop 550
EVAL_SPEC = dict(start=SPEC50["start"], trail=SPEC50["trail"], target=SPEC50["target"])

D0 = pd.Timestamp("2024-01-02")
D1 = pd.Timestamp("2024-01-03")
D2 = pd.Timestamp("2024-01-04")


def _ev(ts, pnl, mae):
    return dict(ts=ts, pnl=float(pnl), mae=float(mae))


# ---------------------------------------------------------------------- 1. DLL = pause, not death

def test_dll_clamp_is_a_pause_not_a_death():
    """tools_account_size_research.py:56-78 (day_rows) + :81-101 (eval_run).

    A single-trade day whose marked trough hits -$1,400 (fresh $50k account, ample cushion) is
    clamped by day_rows (:73-74, trough<=-dll) to (real=-1000, trough=-1000) -- the Apex DLL
    flattens the day, it does not bust the eval. Feeding just that one day into eval_run must NOT
    return BUST (single-day series resolves INCOMPLETE, confirming no bust fired). The DLL also
    resets per day: a second consecutive DLL-clamp day still doesn't bust, and the eval can go on to
    PASS normally afterward.
    """
    ev = [_ev(D0, -1400.0, -1400.0)]
    day0 = H.day_rows(ev, SPEC50["stop"], SPEC50["dll"])
    assert day0 == [(D0, -1000.0, -1000.0)]           # clamped to the DLL, not the raw -1400 mark

    # a single DLL day alone must not be classified as a death
    single = H.eval_run(day0, 0, EVAL_SPEC)
    assert single[0] != "BUST"
    assert single == ("INCOMPLETE", None)

    # DLL resets: a second DLL-clamp day, then a day that reaches target -> eval passes through
    days = day0 + [(D1, -1000.0, -1000.0), (D2, 5000.0, 0.0)]
    result = H.eval_run(days, 0, EVAL_SPEC)
    assert result[0] != "BUST"
    assert result == ("PASS", 2)


# ---------------------------------------------------------------------- 2. Only the trailing EOD threshold kills

def test_eod_breach_is_a_death():
    """tools_account_size_research.py:91-92 (bal += real; EOD settle), :97-98 (bal <= thr -> BUST).

    A day whose intraday marked trough stays clear of the threshold (bal + trough > thr) but whose
    settled EOD balance falls to/through the threshold must BUST -- the EOD check, not the intraday
    check, is what fires here.
    """
    days = [(D0, -3000.0, -500.0)]                    # 50000-500=49500 > 47500 (ok); 50000-3000=47000 <= 47500
    result = H.eval_run(days, 0, EVAL_SPEC)
    assert result == ("BUST", 0)


def test_intraday_marked_breach_is_a_death_when_cushion_thin():
    """tools_account_size_research.py:89-90 (bal + min(0, trough) <= thr -> BUST).

    The Apex-flatten-hits-the-floor case: a clamped -$1,000 marked trough on a day where cushion
    (bal - thr) is under $1,000 must BUST via the intraday check -- even though the day's REALIZED
    pnl (+50) would not have busted an EOD-only check. This isolates the intraday branch.
    """
    days = [(D0, -1600.0, -1600.0),                    # settle bal 48400, thr stays 47500 (cushion 900)
            (D1, 50.0, -1000.0)]                       # 48400 - 1000 = 47400 <= 47500 -> BUST intraday
    result = H.eval_run(days, 0, EVAL_SPEC)
    assert result == ("BUST", 1)
    # sanity: if this were EOD-only checked (bal += 50 -> 48450 > 47500), it would NOT bust --
    # proving the death came from the intraday branch specifically.


def test_no_other_death_path_exists():
    """tools_account_size_research.py:81-101 (eval_run) -- static shape check.

    Exactly two `return "BUST"` statements exist in eval_run: the intraday marked-breach check
    (:89-90) and the EOD-settle check (:97-98). If a third death path is ever added, this test
    forces an explicit acknowledgement here.
    """
    import inspect
    src = inspect.getsource(H.eval_run)
    assert src.count('return "BUST"') == 2


# ---------------------------------------------------------------------- 3. Clamp-before-check ordering

def test_clamp_runs_before_intraday_check():
    """tools_account_size_research.py:73-76 (DLL clamp in day_rows) precedes :89 (intraday check
    in eval_run) -- day_rows always clamps first, eval_run only ever sees the clamped trough.

    A day marked -$1,400 with $1,200 cushion (bal - thr = 1,200) SURVIVES once clamped to -$1,000
    (Apex flattens at -1k before the floor is reached) but would BUST if eval_run ever saw the raw,
    unclamped -$1,400 mark. This is the hierarchy proof: clamp-then-check, not check-then-clamp.
    """
    days_clamped = [(D0, -1300.0, -1300.0),            # settle bal 48700, thr stays 47500 (cushion 1200)
                    (D1, -1000.0, -1000.0)]             # 48700 - 1000 = 47700 > 47500 -> survives
    days_raw = [(D0, -1300.0, -1300.0),
                (D1, -1400.0, -1400.0)]                 # 48700 - 1400 = 47300 <= 47500 -> would BUST
    clamped_result = H.eval_run(days_clamped, 0, EVAL_SPEC)
    raw_result = H.eval_run(days_raw, 0, EVAL_SPEC)
    assert clamped_result[0] != "BUST"
    assert clamped_result == ("INCOMPLETE", None)
    assert raw_result == ("BUST", 1)


# ---------------------------------------------------------------------- 4. Internal $550 blocker ordering

def test_internal_stop_blocks_later_trades_full_loser():
    """tools_account_size_research.py:62-63 (if r["stopped"]: continue), :66-67 (stop trips at
    real <= -stop).

    Trade 1 (-600, a full loser past the $550 stop) trips `stopped`; trade 2 (+400) in the same day
    must be SKIPPED entirely -- day real must be -600, not -200 (which is what you'd get if trade 2
    were wrongly allowed to net against it).
    """
    ev = [_ev(D0, -600.0, -600.0), _ev(D0, 400.0, 0.0)]
    days = H.day_rows(ev, SPEC50["stop"], SPEC50["dll"])
    assert days == [(D0, -600.0, -600.0)]


def test_internal_stop_is_retrospective_cumulative():
    """tools_account_size_research.py:65-67 -- the stop check runs AFTER accumulating each trade's
    pnl into `real`, so it is retrospective on the cumulative total, not on the individual trade.

    Trade 1 (-400) alone does not trip the -$550 stop; trade 2 (-400) is therefore still processed
    and both trades land in full (cumulative -800 trips `stopped` only after trade 2 has already been
    counted) -- the day's real is -800, the full compounded loss, not clipped mid-trade.
    """
    ev = [_ev(D0, -400.0, -400.0), _ev(D0, -400.0, -400.0)]
    days = H.day_rows(ev, SPEC50["stop"], SPEC50["dll"])
    assert days == [(D0, -800.0, -800.0)]


# ---------------------------------------------------------------------- 5. Three-layer hierarchy

def test_three_layer_hierarchy_on_full_loser_survives():
    """tools_account_size_research.py:62-67 (internal $550 stop blocks the recovery trade),
    :73-76 (DLL clamp), :89-90/:97-98 (eval_run death checks) -- walks all three layers on one
    fixture, fresh $50k account.

    A day: trade 1 pnl=-1200 (a full loser, past both the $550 stop AND the $1,000 DLL); trade 2
    pnl=+5000 (would fully recover the day) MUST be skipped by the internal stop (day_rows never
    lets it in). The day is then DLL-clamped to (real=-1000, trough=-1000) -- NOT the raw -1200,
    and certainly not the +5000-recovered figure. Finally the eval survives because the trailing
    floor is untouched: 50,000 - 1,000 = 49,000 > 47,500.
    """
    ev = [_ev(D0, -1200.0, -1200.0), _ev(D0, 5000.0, 0.0)]
    day0 = H.day_rows(ev, SPEC50["stop"], SPEC50["dll"])
    assert day0 == [(D0, -1000.0, -1000.0)]            # internal stop blocked +5000, THEN DLL clamped

    result = H.eval_run(day0, 0, EVAL_SPEC)
    assert result[0] != "BUST"
    assert result == ("INCOMPLETE", None)
    assert SPEC50["start"] - 1000.0 == 49_000.0 > SPEC50["start"] - SPEC50["trail"]   # 49,000 > 47,500


# ---------------------------------------------------------------------- 6. Ratchet + lock

def test_ratchet_locks_at_start_plus_100_and_never_rises_further():
    """tools_account_size_research.py:92-96 (peak ratchet + lock).

    thr ratchets to (peak - trail) on every EOD balance high until peak >= start + trail + 100
    (52,600), at which point thr locks at exactly start + 100 (50,100) and MUST NOT ratchet further
    even as peak keeps rising. Target is set artificially high in this fixture (spec6) to isolate
    the ratchet/lock mechanism from the PASS check, which is orthogonal to it.
    """
    spec6 = dict(start=SPEC50["start"], trail=SPEC50["trail"], target=10_000_000.0)
    days = [
        (D0, 2600.0, 0.0),     # bal 50000->52600: peak-trail=50100 >= start+100 -> LOCK at 50100
        (D1, 7400.0, 0.0),     # bal 52600->60000: peak rises but thr is locked, stays 50100
        (D2, -5000.0, -5000.0),  # bal 60000->55000: 55000 > 50100 (locked) -> survives.
    ]                          # (if thr had kept ratcheting, it would be 60000-2500=57500 and BUST here)
    result = H.eval_run(days, 0, spec6)
    assert result[0] != "BUST"
    assert result == ("INCOMPLETE", None)


# ---------------------------------------------------------------------- 7. PASS immediate

def test_pass_fires_immediately_no_other_requirement():
    """tools_account_size_research.py:99-100 (bal >= sb + tg -> PASS).

    A day series reaching bal >= start + target PASSes on that very day, with the day count of that
    day -- no month-end, no minimum trading-day count, no additional gate.
    """
    days = [(D0, 5000.0, 0.0)]                          # 50000+5000=55000 >= 53000
    result = H.eval_run(days, 0, EVAL_SPEC)
    assert result == ("PASS", 0)


# ---------------------------------------------------------------------- 8. EXPIRE

def test_expire_after_30_days_without_target_or_bust():
    """tools_account_size_research.py:27-28 (EXPIRE_DAYS = 30), :87-88 ((d - t0).days > EXPIRE_DAYS
    -> EXPIRE).

    A day series that never reaches target and never busts, run past 30 calendar days from the
    start day, classifies as EXPIRE (fee-only drag is implicit here -- flat $0 days -- no balance
    assertion needed, only the terminal classification).
    """
    base = D0
    days = [(base + pd.Timedelta(days=i), 0.0, 0.0) for i in range(40)]
    result = H.eval_run(days, 0, EVAL_SPEC)
    assert result == ("EXPIRE", H.EXPIRE_DAYS)


# ---------------------------------------------------------------------- 9. Funded-harness DLL consistency

def test_funded_harness_clamps_realized_but_not_trough():
    """apex_funded_40.py:55-71 (daily_series day collapse).

    Current behavior: when a day's marked trough breaches the $1,000 DLL, daily_series clamps the
    day's REALIZED pnl to the DLL (-1000) but leaves `trough` UNCLAMPED (still the raw, more
    negative mark, e.g. -1200 here). This is CONSERVATIVE relative to the certification eval
    harness (tools_account_size_research.day_rows, :73-76), which clamps BOTH real and trough to
    -dll -- i.e. the funded model reports a worse (more negative) marked low than the eval harness
    would for an identical trade sequence. This is intentional per the module docstring (:9-11,
    "conservative approximation") -- asserting current behavior only, NOT changing the harness.
    """
    rows = [dict(ts=D0, R=-12.0, risk_usd=100.0, mae_r=-12.0)]   # -> pnl=-1200, mae=-1200 at a_size=1
    out = F.daily_series(rows, a_size=1, budget_per_ct=160.0)
    assert out == [(D0, -1000.0, -1200.0)]                       # real clamped to DLL, trough left raw

    # contrast with the eval harness on the identical raw trade: BOTH real and trough get clamped
    ev = [_ev(D0, -1200.0, -1200.0)]
    eval_day = H.day_rows(ev, SPEC50["stop"], SPEC50["dll"])
    assert eval_day == [(D0, -1000.0, -1000.0)]
    assert out[0][2] < eval_day[0][2]              # funded harness's trough is MORE negative (conservative)
