"""ATHENA shadow mode — D1c runs SIDE-BY-SIDE with production logic. ZERO production impact.

For every Profile A signal in paper_fill_log.csv, replays the day's 1m bars through the
production DriftGate and records what D1c WOULD have done. Produces:
  out/d1c_shadow/decisions.csv   — one row per signal: drift, decision, both books
  out/d1c_shadow/status.json     — keep-rate + HEIMDALL status (heimdall can ingest this
                                   file as an extra snapshot field when D1c is enabled)
  daily parity line per run      — CME-vs-research decision agreement tracking (Phase 4)

EOD usage:    python3 shadow_d1c.py --bars <1m parquet/csv> [--log paper_fill_log.csv]
Live usage:   in the paper runner, after an A signal/fill event:
                  gate.on_session_open(...) / gate.on_bar_close(...) per 1m bar
                  shadow_log(gate, signal)   # log-only; never touches order flow
"""
import argparse, json, os
import pandas as pd

from drift_gate import DriftGate

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "out", "d1c_shadow")
TRIAL_STATE = os.path.join(OUTDIR, "trial_state.json")


def load_trial_state():
    try:
        with open(TRIAL_STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        # fail-safe defaults: nothing counts forward, production OFF
        return {"trial_start_et": "2026-06-13T00:00:00",
                "production_gate_enabled": False, "shadow_gate_enabled": True,
                "gates": {"gate1": 10, "gate2": 20, "final": 30}}


def load_bars(path):
    df = pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_convert("America/New_York").tz_localize(None)
    return df


def _reference_decision(db, d0930, ts, direction):
    """Independent reference implementation (audited research formula, numpy-free):
    drift = close(last bar stamped < ts) - 09:30 open; keep iff sign matches direction.
    Returns (keep_ref, fresh) where fresh = last bar within 3 minutes of ts."""
    prior = db[db.index < ts]
    if not len(prior):
        return False, False
    drift = prior.close.iloc[-1] - db.open.iloc[0]
    fresh = (ts - prior.index[-1]).total_seconds() <= 180
    d = 1 if direction == "long" else -1
    return (drift > 0 and d == 1) or (drift < 0 and d == -1), fresh


def shadow_day(bars, day, signals):
    """Replay one day's 1m bars; return decision rows for that day's signals.
    Dual implementation: production DriftGate vs audited reference formula.
    fail_open = gate KEEP where fresh-feed reference says SUSPEND (must NEVER happen)."""
    d0930 = day.replace(hour=9, minute=30)
    db = bars[(bars.index >= d0930) & (bars.index < day.replace(hour=16, minute=0))]
    if not len(db) or db.index[0] != d0930:
        return [dict(signal_time=s.signal_time, direction=s.direction, drift=None,
                     decision="SUSPEND(no-0930-bar)", reference="SUSPEND", agree=True,
                     fresh=False, fail_open=False) for s in signals.itertuples()]
    rows = []
    for s in signals.itertuples():
        g = DriftGate(enabled=True)
        g.on_session_open(d0930, db.open.iloc[0])
        ts = pd.Timestamp(s.fill_time).tz_localize(None) if pd.notna(s.fill_time) else \
             pd.Timestamp(s.signal_time).tz_localize(None)
        for t, c in db.close.items():
            if t >= ts:
                break
            g.on_bar_close(t, c)
        dec = bool(g.allows(s.direction, now=ts))
        ref, fresh = _reference_decision(db, d0930, ts, s.direction)
        # parity is judged on fresh feed; on stale feed the gate is REQUIRED to be stricter
        agree = (dec == ref) if fresh else (dec is False or dec == ref)
        rows.append(dict(signal_time=s.signal_time, fill_time=s.fill_time,
                         direction=s.direction, drift=g.drift(),
                         decision="KEEP" if dec else "SUSPEND",
                         reference="KEEP" if ref else "SUSPEND",
                         agree=bool(agree), fresh=bool(fresh),
                         fail_open=bool(dec and not ref and fresh),
                         result_R=getattr(s, "result_R", None)))
    return rows


REPLAY_OUTDIR = os.path.join(HERE, "out", "replay", "d1c_shadow")
REPLAY_LOG = os.path.join(HERE, "out", "replay", "paper_fill_log.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", required=True, help="1m bars parquet/csv (ET)")
    ap.add_argument("--log", default=None)
    ap.add_argument("--replay", action="store_true",
                    help="HERMES rehearsal mode: isolated outputs, rows stamped "
                         "source=replay + trial_eligible=False (NEVER counts for ATHENA)")
    a = ap.parse_args()
    outdir = REPLAY_OUTDIR if a.replay else OUTDIR
    log = a.log or (REPLAY_LOG if a.replay else os.path.join(HERE, "paper_fill_log.csv"))
    os.makedirs(outdir, exist_ok=True)
    bars = load_bars(a.bars)
    sig = pd.read_csv(log)
    sig["day"] = pd.to_datetime(sig.date)
    all_rows = []
    for day, g in sig.groupby("day"):
        all_rows += shadow_day(bars, day, g)
    dec = pd.DataFrame(all_rows)
    st = load_trial_state()
    t0 = pd.Timestamp(st["trial_start_et"])
    if a.replay:
        # HARD ISOLATION: replay rows can never be eligible, whatever their timestamps.
        dec["source"] = "replay"
        dec["trial_eligible"] = False
        dec["counts_for_trial"] = False
        path = os.path.join(outdir, "decisions.csv")
        dec.to_csv(path, index=False)
        kept = int((dec.decision == "KEEP").sum())
        rstat = dict(asof=str(pd.Timestamp.now()), mode="REPLAY-REHEARSAL",
                     replay_decisions=int(len(dec)), kept=kept,
                     keep_rate=(round(kept / len(dec), 3) if len(dec) else None),
                     agreement=(round(float(dec.agree.mean()), 4) if len(dec) else None),
                     fail_open_events=int(dec.fail_open.sum()) if len(dec) else 0,
                     counts_for_trial=False)
        with open(os.path.join(outdir, "status.json"), "w") as f:
            json.dump(rstat, f, indent=2)
        print(f"REPLAY shadow: {len(dec)} decisions · kept {kept} · "
              f"fail_open {rstat['fail_open_events']} · counts_for_trial=False -> {path}")
        return
    dec["source"] = dec.signal_time.apply(
        lambda x: "forward_paper" if pd.Timestamp(x).tz_localize(None) >= t0 else "backfill")
    dec["trial_eligible"] = dec.source == "forward_paper"
    path = os.path.join(OUTDIR, "decisions.csv")
    dec.to_csv(path, index=False)
    fwd = dec[dec.trial_eligible]
    kept = (dec.decision == "KEEP").sum()
    kr = kept / len(dec) if len(dec) else None
    fkr = (fwd.decision == "KEEP").mean() if len(fwd) else None
    gates = st.get("gates", {"gate1": 10, "gate2": 20, "final": 30})
    nxt = next(((g, n) for g, n in sorted(gates.items(), key=lambda kv: kv[1])
                if len(fwd) < n), None)
    # replay (HERMES rehearsal) summary — separate pipeline, surfaced read-only
    replay_n, replay_last = 0, None
    try:
        with open(os.path.join(REPLAY_OUTDIR, "status.json")) as f:
            rs = json.load(f)
        replay_n, replay_last = int(rs.get("replay_decisions", 0)), rs.get("asof")
    except (OSError, ValueError):
        pass
    try:
        from athena_gate_report import evaluate
        verdict = evaluate(dec, None, bool(st.get("production_gate_enabled", False)))["verdict"]
    except Exception as e:                       # status must still write if evaluator breaks
        verdict = f"evaluator-error: {e}"
    status = dict(asof=str(pd.Timestamp.now()),
                  challenger_status=st.get("challenger_status", "CHALLENGER / PAPER ONLY"),
                  champion=st.get("champion", "ZEUS-MAX"),
                  production_gate_enabled=bool(st.get("production_gate_enabled", False)),
                  shadow_gate_enabled=bool(st.get("shadow_gate_enabled", True)),
                  forward_decisions=int(len(fwd)),
                  official_forward_count=int(len(fwd)),
                  backfilled_decisions=int(len(dec) - len(fwd)),
                  backfilled_decision_count=int(len(dec) - len(fwd)),
                  replay_decision_count=replay_n,
                  replay_mode_active=bool(replay_n),
                  replay_last_run=replay_last,
                  replay_note="REPLAY = REHEARSAL ONLY — never counts toward ATHENA gates",
                  current_athena_verdict=verdict,
                  next_gate=(f"{nxt[0]} at {nxt[1]}" if nxt else "FINAL reached"),
                  next_official_gate=(f"{nxt[0]} at {nxt[1]}" if nxt else "FINAL reached"),
                  n_signals=int(len(dec)), kept=int(kept),
                  keep_rate=(round(kr, 3) if kr is not None else None),
                  forward_keep_rate=(round(float(fkr), 3) if fkr is not None else None),
                  agreement=(round(float(dec.agree.mean()), 4) if len(dec) else None),
                  fail_open_events=int(dec.fail_open.sum()) if len(dec) else 0,
                  heimdall=("RED(fail-open)" if len(dec) and dec.fail_open.any() else
                            "WARMUP" if len(fwd) < 30 else
                            ("OK" if 0.45 <= fkr <= 0.80 else "YELLOW")))
    with open(os.path.join(OUTDIR, "status.json"), "w") as f:
        json.dump(status, f, indent=2)
    # keep trial_state forward counter in sync (single writer: this script)
    st["forward_decision_count"] = int(len(fwd))
    st["backfilled_decisions"] = int(len(dec) - len(fwd))
    with open(TRIAL_STATE, "w") as f:
        json.dump(st, f, indent=2)
    print(f"shadow decisions: {len(dec)} total · FORWARD {len(fwd)} (clock) · "
          f"backfilled {len(dec) - len(fwd)} (pipeline proof only)")
    print(f"status: {status['heimdall']} · next gate: {status['next_gate']}  -> {path}")


if __name__ == "__main__":
    main()
