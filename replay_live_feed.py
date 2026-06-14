"""HERMES replay drill — simulated live bar pipeline. REHEARSAL ONLY.

Streams historical bars one-by-one through the UNMODIFIED production paper engine
(paper_live.PaperLiveRunner + bot.SimBot), exactly as a live session would, then runs the
D1c shadow in --replay mode. Everything is isolated:
  store     -> out/replay/replay_paper.db        (never data/paper.db or data/bot.db)
  fills     -> out/replay/paper_fill_log.csv     (never paper_fill_log.csv)
  decisions -> out/replay/d1c_shadow/decisions.csv  (source=replay, trial_eligible=False)
  evidence  -> evidence/replay/<runid>_manifest.json
The official ATHENA trial state is read before/after and the manifest PROVES it unchanged.

CLI:  python3 replay_live_feed.py --start 2025-01-01 --end 2025-03-31 --speed fast
Speeds: instant (0s/bar) · fast (5ms/bar) · realtime (300s/bar = true 5m cadence).
No lookahead: bars are yielded strictly in sequence by paper_live.ReplayFeed; the engine
only ever sees completed bars that have already been emitted.
"""
import argparse, json, os, subprocess, sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPLAY_DIR = os.path.join(HERE, "out", "replay")
EVIDENCE = os.path.join(HERE, "evidence", "replay")
TRIAL_STATE = os.path.join(HERE, "out", "d1c_shadow", "trial_state.json")
NQ1M = os.path.expanduser("~/trading-team/data/nq/NQ_1m_24h.parquet")
SPEEDS = {"instant": 0.0, "fast": 0.005, "realtime": 300.0}


def official_state():
    try:
        with open(TRIAL_STATE) as f:
            s = json.load(f)
        return dict(forward=s.get("forward_decision_count"),
                    production=s.get("production_gate_enabled"))
    except (OSError, ValueError):
        return dict(forward=None, production=None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--speed", choices=list(SPEEDS), default="instant")
    a = ap.parse_args()
    os.makedirs(REPLAY_DIR, exist_ok=True); os.makedirs(EVIDENCE, exist_ok=True)
    runid = pd.Timestamp.now().strftime("%Y%m%dT%H%M%S")

    before = official_state()
    print(f"official ATHENA before replay: forward={before['forward']} "
          f"production_gate={before['production']}")

    # ---- 1) stream bars through the UNMODIFIED production paper engine ----
    from store import Store
    from paper_live import PaperLiveRunner, ReplayFeed
    st = Store(os.path.join(REPLAY_DIR, "replay_paper.db"))   # isolated replay store
    st.reset()
    csv_path = os.path.join(REPLAY_DIR, "paper_fill_log.csv")
    runner = PaperLiveRunner(st, a.start, a.end, csv_path=csv_path)
    feed = ReplayFeed(a.start, a.end, speed=SPEEDS[a.speed])
    nbars = sum(1 for _ in ReplayFeed(a.start, a.end))        # count pass (no engine)
    print(f"streaming {nbars} bars {a.start} -> {a.end} (speed={a.speed})...")
    runner.run(feed)
    sig = pd.read_csv(csv_path) if os.path.exists(csv_path) else pd.DataFrame()
    print(f"paper signals generated: {len(sig)} -> {csv_path}")

    # ---- 2) D1c shadow in replay-isolated mode ----
    r = subprocess.run([sys.executable, os.path.join(HERE, "shadow_d1c.py"),
                        "--bars", NQ1M, "--replay"], capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr); raise SystemExit("shadow replay failed")
    rdec_path = os.path.join(REPLAY_DIR, "d1c_shadow", "decisions.csv")
    rdec = pd.read_csv(rdec_path) if os.path.exists(rdec_path) else pd.DataFrame()

    # ---- 3) evaluator safety: replay rows must not move the official clock ----
    from athena_gate_report import evaluate
    rep_replay = evaluate(rdec) if len(rdec) else {"n_forward": 0, "gate": None, "verdict": "n/a"}
    official_dec = pd.read_csv(os.path.join(HERE, "out", "d1c_shadow", "decisions.csv"))
    rep_official = evaluate(official_dec)
    after = official_state()

    ok = (rep_replay["n_forward"] == 0 and rep_replay["gate"] is None
          and after == before and after["production"] is False)
    manifest = dict(
        runid=runid, mode="HERMES-REPLAY-REHEARSAL",
        config=dict(start=a.start, end=a.end, speed=a.speed),
        bars_replayed=int(nbars),
        paper_signals=int(len(sig)),
        d1c_replay_decisions=int(len(rdec)),
        replay_keep_rate=(round(float((rdec.decision == "KEEP").mean()), 3) if len(rdec) else None),
        replay_fail_open=int(rdec.fail_open.sum()) if len(rdec) else 0,
        replay_gate_eval=dict(n_forward=rep_replay["n_forward"], gate=rep_replay["gate"]),
        official_before=before, official_after=after,
        official_verdict=rep_official["verdict"],
        official_unchanged=bool(after == before),
        isolation_ok=bool(ok))
    mpath = os.path.join(EVIDENCE, f"{runid}_manifest.json")
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps(manifest, indent=2))
    print(f"\nmanifest -> {mpath}")
    print("HERMES DRILL:", "PASS" if ok else "FAIL (isolation violated)")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
