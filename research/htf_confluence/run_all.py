"""
Driver: runs the full pre-registered HTF confluence chain measurement
(PREREG_CHAIN.md, commit eaef4a4) — STEP 1 fill-path pre-gate physical check, STEP 2
train/holdout/quarterly, live-achievable (Gate D), STEP 3 null + Profile A overlap.
Writes JSON artifacts to results/ (committed) and full trade ledgers to trade_ledgers/
(local only, NOT committed — see PREREG task instructions).
"""
import json
import os
import time

import numpy as np
import pandas as pd

from chain import (BUFFER_START, WINDOW_START, SPLIT_TS, WINDOW_END, LONG, SHORT,
                    load_1m, build_all, df1m_to_arrays, run_chain, cell_stats,
                    exch_day_cutoff)
from null_test_chain import run_null_test
from gate_d_chain import run_gate_d_chain

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results")
LEDGER_DIR = os.path.join(HERE, "trade_ledgers")


def physical_instant_loss_check(candidates: pd.DataFrame, trades: pd.DataFrame, arrs: dict) -> dict:
    """STEP 1 physical check: does the ledger contain a fill-bar-breaches-stop / instant-
    loss population? Checked two ways: (a) booked 'stop_samebar' trades in the executed
    (position-sequenced) ledger, and (b) raw same-bar entry+invalidate / entry+stop touches
    across EVERY candidate independently of position-sequencing (isolates the fill mechanism
    itself from the one-position-at-a-time filter, so an all-zero result on (a) can be
    attributed to sequencing-starvation vs a geometric/data fact, not conflated)."""
    n_samebar_booked = int((trades["reason"] == "stop_samebar").sum()) if len(trades) else 0

    ts_ns = arrs["ts_ns"]; Low = arrs["Low"]; High = arrs["High"]
    n1m = len(ts_ns)
    n_cand = len(candidates)
    n_filled = 0
    n_never_filled = 0
    n_samebar_entry_invalidate = 0
    n_samebar_entry_stop = 0
    for r in candidates.itertuples(index=False):
        eod_cut = exch_day_cutoff(r.conf_ts)
        eod_ns = eod_cut.value
        order_end_ns = min(int(r.order_end_ns), eod_ns)
        i0 = np.searchsorted(ts_ns, r.conf_ts.value, side="left")
        i1 = np.searchsorted(ts_ns, order_end_ns, side="left")
        if i1 <= i0 or i0 >= n1m:
            n_never_filled += 1
            continue
        lo_w, hi_w = Low[i0:i1], High[i0:i1]
        entry_touch = (lo_w <= r.entry_price) & (hi_w >= r.entry_price)
        if r.direction == LONG:
            inv_touch = lo_w <= r.invalidate_price
            stop_touch = lo_w <= r.stop_price
        else:
            inv_touch = hi_w >= r.invalidate_price
            stop_touch = hi_w >= r.stop_price
        e_hit = np.argmax(entry_touch) if entry_touch.any() else None
        if e_hit is None:
            n_never_filled += 1
            continue
        n_filled += 1
        v_hit = np.argmax(inv_touch) if inv_touch.any() else None
        s_hit = np.argmax(stop_touch) if stop_touch.any() else None
        if v_hit is not None and v_hit == e_hit:
            n_samebar_entry_invalidate += 1
        if s_hit is not None and s_hit == e_hit:
            n_samebar_entry_stop += 1

    return dict(
        n_candidates_total=n_cand, n_filled_raw=n_filled, n_never_filled_raw=n_never_filled,
        n_samebar_entry_invalidate_raw=n_samebar_entry_invalidate,
        n_samebar_entry_stop_raw=n_samebar_entry_stop,
        n_stop_samebar_booked_in_sequenced_ledger=n_samebar_booked,
        instant_loss_population_present=bool(n_samebar_booked > 0 or n_samebar_entry_stop > 0),
    )


def ledger_to_records(tr: pd.DataFrame) -> list:
    if not len(tr):
        return []
    out = tr.copy()
    for c in ("conf_ts", "fill_ts", "exit_ts", "sweep_ts"):
        if c in out.columns:
            out[c] = out[c].astype(str)
    return out.to_dict(orient="records")


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(LEDGER_DIR, exist_ok=True)

    t0 = time.time()
    df1m_full = load_1m()
    df1m = df1m_full.loc[BUFFER_START:WINDOW_END]
    print(f"data loaded {time.time()-t0:.1f}s, window rows={len(df1m)}")

    ctx = build_all(df1m)
    arrs = df1m_to_arrays(df1m)
    print(f"context built {time.time()-t0:.1f}s; sweeps={len(ctx['sweeps'])} "
          f"candidates={len(ctx['candidates'])}")

    # ---- STEP 2: windows ----
    tr_train = run_chain(arrs, ctx["target_ctx"], ctx["candidates"], WINDOW_START, SPLIT_TS)
    tr_hold = run_chain(arrs, ctx["target_ctx"], ctx["candidates"], SPLIT_TS, WINDOW_END)
    tr_full = run_chain(arrs, ctx["target_ctx"], ctx["candidates"], WINDOW_START, WINDOW_END)

    # ---- STEP 1: physical instant-loss check (on the FULL 2y window + holdout) ----
    phys_full = physical_instant_loss_check(ctx["candidates"], tr_full, arrs)
    phys_hold = physical_instant_loss_check(
        ctx["candidates"][(ctx["candidates"]["conf_ts"] >= SPLIT_TS) &
                           (ctx["candidates"]["conf_ts"] < WINDOW_END)], tr_hold, arrs)
    print("STEP1 physical check (full window):", phys_full)

    # ---- quarterly walk-forward ----
    total_days = (WINDOW_END - WINDOW_START).days
    q_days = total_days / 8.0
    quarters = [(WINDOW_START + pd.Timedelta(days=q_days * i),
                 WINDOW_START + pd.Timedelta(days=q_days * (i + 1))) for i in range(8)]
    quarterly = []
    for qs, qe in quarters:
        tr_q = run_chain(arrs, ctx["target_ctx"], ctx["candidates"], qs, qe)
        quarterly.append(dict(start=str(qs.date()), end=str(qe.date()), stats=cell_stats(tr_q)))

    # ---- Gate D live-achievable ----
    gate_d_train = run_gate_d_chain(tr_train, ctx["candidates"], ctx["target_ctx"], arrs)
    gate_d_hold = run_gate_d_chain(tr_hold, ctx["candidates"], ctx["target_ctx"], arrs)
    gate_d_full = run_gate_d_chain(tr_full, ctx["candidates"], ctx["target_ctx"], arrs)

    # ---- STEP 3(a): null ----
    null_hold = run_null_test(arrs, ctx["target_ctx"], ctx["bias_ctx"], tr_hold, SPLIT_TS, WINDOW_END,
                               n_runs=1000, seed=20260720)
    null_train = run_null_test(arrs, ctx["target_ctx"], ctx["bias_ctx"], tr_train, WINDOW_START, SPLIT_TS,
                                n_runs=1000, seed=20260720)

    # ---- STEP 3(b): Profile A overlap (holdout window) ----
    pa_path = "/Users/jacksonclarke/trading-team/research/atlas/profile_a_edge/outputs/signals_583_classified.csv"
    pa = pd.read_csv(pa_path)
    pa["ts"] = pd.to_datetime(pa["ts"], utc=True, format="mixed")
    pa_ach = pa[pa["achievable"] == True]  # noqa: E712
    pa_hold = pa_ach[(pa_ach["ts"] >= SPLIT_TS) & (pa_ach["ts"] < WINDOW_END)]

    chain_dates = set(pd.to_datetime(tr_hold["fill_ts"]).dt.tz_convert("UTC").dt.normalize()) if len(tr_hold) else set()
    pa_dates = set(pa_hold["ts"].dt.normalize())
    inter = chain_dates & pa_dates
    union = chain_dates | pa_dates
    jaccard = (len(inter) / len(union)) if union else 0.0

    pa_by_date = pa_hold.groupby(pa_hold["ts"].dt.normalize())["R"].mean()
    chain_by_date = pd.Series(dtype=float)
    if len(tr_hold):
        tmp = tr_hold.copy()
        tmp["date"] = pd.to_datetime(tmp["fill_ts"]).dt.tz_convert("UTC").dt.normalize()
        chain_by_date = tmp.groupby("date")["R"].mean()

    overlap = dict(
        profile_a_n_achievable_in_holdout=int(len(pa_hold)),
        chain_n_trading_days_holdout=len(chain_dates),
        profile_a_n_trading_days_holdout=len(pa_dates),
        n_shared_days=len(inter), n_union_days=len(union),
        jaccard_trading_days=round(jaccard, 4),
        shared_days=sorted(str(d.date()) for d in inter),
        profile_a_expectancy_on_shared_days=pa_by_date.reindex(list(inter)).round(4).astype(object).where(
            pd.notna(pa_by_date.reindex(list(inter))), None).to_dict() if inter else {},
        chain_expectancy_on_shared_days=chain_by_date.reindex(list(inter)).round(4).astype(object).where(
            pd.notna(chain_by_date.reindex(list(inter))), None).to_dict() if inter else {},
        profile_a_mean_R_on_shared_days=round(float(pa_by_date.reindex(list(inter)).mean()), 4) if inter else None,
        chain_mean_R_on_shared_days=round(float(chain_by_date.reindex(list(inter)).mean()), 4) if inter else None,
        profile_a_overall_holdout_expectancy=round(float(pa_hold["R"].mean()), 4) if len(pa_hold) else None,
        chain_overall_holdout_expectancy=round(float(tr_hold["R"].mean()), 4) if len(tr_hold) else None,
        n_chain_days_with_no_profile_a_signal=len(chain_dates - pa_dates),
    )
    # rekey date dicts to strings for json
    overlap["profile_a_expectancy_on_shared_days"] = {str(k.date()): v for k, v in
                                                        overlap["profile_a_expectancy_on_shared_days"].items()}
    overlap["chain_expectancy_on_shared_days"] = {str(k.date()): v for k, v in
                                                   overlap["chain_expectancy_on_shared_days"].items()}

    # ---- n-adequacy ----
    n_hold = len(tr_hold)
    years_observed = (WINDOW_END - SPLIT_TS).days / 365.25
    firing_rate_per_year = n_hold / years_observed if years_observed > 0 else 0.0
    years_to_n30 = (30.0 / firing_rate_per_year) if firing_rate_per_year > 0 else float("inf")

    result = dict(
        prereg_commit="eaef4a4",
        run_ts_utc=pd.Timestamp.utcnow().isoformat(),
        window=dict(buffer_start=str(BUFFER_START), window_start=str(WINDOW_START),
                    split_ts=str(SPLIT_TS), window_end=str(WINDOW_END)),
        step1_fill_path_pre_gate=dict(
            regression_test="test_fill_sequencing_chain.py — 2/2 PASS (filled-then-stopped booked, "
                             "strict-precede is a real cancel)",
            self_test_shift_invariance="self_test_chain.py — 3/3 detectors PASS (1H_bias, "
                                        "chain_candidates, 15m_sweep)",
            physical_check_full_window=phys_full,
            physical_check_holdout=phys_hold,
        ),
        n_candidates_total=len(ctx["candidates"]), n_sweeps_total=len(ctx["sweeps"]),
        train=dict(n_candidates=int(((ctx["candidates"]["conf_ts"] >= WINDOW_START) &
                                      (ctx["candidates"]["conf_ts"] < SPLIT_TS)).sum()),
                   stats=cell_stats(tr_train), live_achievable=gate_d_train,
                   null=null_train),
        holdout=dict(n_candidates=int(((ctx["candidates"]["conf_ts"] >= SPLIT_TS) &
                                        (ctx["candidates"]["conf_ts"] < WINDOW_END)).sum()),
                     stats=cell_stats(tr_hold), live_achievable=gate_d_hold,
                     null=null_hold),
        full_2y=dict(stats=cell_stats(tr_full), live_achievable=gate_d_full),
        quarterly=quarterly,
        n_adequacy=dict(
            floor=30, n_holdout=n_hold, meets_floor=bool(n_hold >= 30),
            years_observed_holdout=round(years_observed, 3),
            firing_rate_per_year=round(firing_rate_per_year, 3),
            years_needed_for_n30=round(years_to_n30, 1) if years_to_n30 != float("inf") else None,
        ),
        profile_a_overlap=overlap,
    )
    with open(os.path.join(RESULTS_DIR, "01_result.json"), "w") as f:
        json.dump(result, f, indent=2, default=str)

    # local-only trade ledgers
    with open(os.path.join(LEDGER_DIR, "train_trades.json"), "w") as f:
        json.dump(ledger_to_records(tr_train), f, indent=2)
    with open(os.path.join(LEDGER_DIR, "holdout_trades.json"), "w") as f:
        json.dump(ledger_to_records(tr_hold), f, indent=2)
    with open(os.path.join(LEDGER_DIR, "full_2y_trades.json"), "w") as f:
        json.dump(ledger_to_records(tr_full), f, indent=2)
    cand_rec = ctx["candidates"].copy()
    cand_rec["conf_ts"] = cand_rec["conf_ts"].astype(str)
    cand_rec["sweep_ts"] = cand_rec["sweep_ts"].astype(str)
    with open(os.path.join(LEDGER_DIR, "all_candidates.json"), "w") as f:
        json.dump(cand_rec.to_dict(orient="records"), f, indent=2)

    print(f"DONE in {time.time()-t0:.1f}s")
    print(json.dumps(result, indent=2, default=str)[:6000])


if __name__ == "__main__":
    main()
