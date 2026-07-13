# Fork-A — slip_ticks reconciliation (live vs certified) + fill-realization gate

Branch `model01-surface-mss`. Read-only analysis; no config touched (PROFILE_A is protected —
any change requires re-certification). This is the "slip reconciliation" arming pre-gate.

## TOP-LINE FINDING: the live config silently trades at slip=2; everything was certified at slip=8.

`strategy_engine_profileA.py` passes bare `PROFILE_A` to the emitter on BOTH paths:
- live surface path: `SM.latest_mss_emission(feats, PROFILE_A)`  (line 129)
- certified default path: `M1.run(feats, "NQ", PROFILE_A, realtime=True)`  (line 156)

`PROFILE_A` (line 20) sets **no** `slip_ticks`, so it inherits model01's module default
`slip_ticks=2` (`SLIP = 2*TICK`, 0.5 pt). But every certification and honest number was computed
with an explicit **`slip_ticks: 8`** override (2.0 pt):
- `apex_sim.py:46`, `apex_eval_deployed.py:58`, `replay_eval30.py:16`, `apex_joint_bar_sim.py:34`
- fork_a honest numbers: `PARAMS = {**DEFAULT_PARAMS, **A_PARAMS["exit3"]}` and
  `A_PARAMS["exit3"]` sets `slip_ticks=8`. So **PF 1.3507 / ~1.18 durable are the slip-8 numbers.**

=> The edge numbers are NOT optimistic on slip (good — they use the conservative 8). The problem is
the reverse: **the LIVE engine emits at a different slip (2) than anything that was certified.**

## Why slip is not just a cost knob here — it moves the emitted limit price

The emitted entry is `entry = ez + d*SLIP` (`surface_at_mss.py:103`). In the certified backtest the
FILL TRIGGER is a touch of the raw OTE level `ez` (`l[m] <= ez` for longs); `SLIP` only worsens the
recorded fill PRICE. But LIVE we post a resting limit at the emitted `entry`, so slip decides WHERE
the limit sits:
- slip=8 (certified): long limit at `ez + 2.0pt` — sits **higher**, fills **earlier/easier**.
- slip=2 (live):      long limit at `ez + 0.5pt` — sits **1.5pt deeper**, fills **harder**.

So running live at slip=2 posts a limit 1.5 pt tighter than the certified fill assumption. Net
effect vs the certified numbers: **fewer fills (more fragile), better price when filled.** Either
way the live fill distribution is NOT the one that was certified — the N≥30 live-fill test would be
measuring a config that was never certified.

## Reconciliation decision required (operator)

**Recommended: pin the live emission to `slip_ticks=8` so live == certified exactly.**
- Mechanically: emit with `{**PROFILE_A, "slip_ticks": 8}` on lines 129 and 156 (or set
  `slip_ticks=8` inside `PROFILE_A`). Add a canary asserting the live emission params carry slip==8
  so this can never silently drift again.
- This is a strategy-config change to a protected file → requires re-running `apex_validation.json`
  and confirming numbers are unchanged (they should be — the certified runs already used 8, so this
  merely makes the code default match what was always certified). Treat as a bug-fix-to-parity, not
  a new config.
- Posting convention to document: the bot posts the resting limit at the emitted `entry` (ez+2.0pt);
  because a real limit fills at-or-better, live slip should be ≤ certified — the existing
  `slip_tripwire.py` (SLIP-class halt) measures this and halts if mean entry slip degrades.

**Alternative (rejected): re-certify the whole edge at slip=2.** Tighter limit → lower fill rate →
would require re-running the full holdout/robustness stack AND still leaves live fill-fragility
worse than the slip-8 picture. No benefit; more work; abandons the conservative haircut.

## This is the pre-gate, not the gate

Fixing slip makes live emissions comparable to certified. It does NOT prove the limit fills. The
decisive evidence remains **N≥30 live OTE-limit fills** measured against the certified fill rate,
with `slip_tripwire` watching entry-slip and the fill/no-fill count watching fill-fragility
(PF→1.08 at 20% winner-miss, →0.94 at 30%). Paper-shadow spec (next) defines how to accumulate that
count without capital: run the surface emission live-shadow, post nothing, log every would-be
resting-limit and whether price traded through it at the certified level within the fill window.

## Status
Nothing armed. LIVE HOLD active. No code changed by this analysis. The slip pin + canary is a
scoped, re-certification-gated change for the operator to authorize; it is the first of the three
remaining arming gates (slip pin → paper shadow → N≥30 live fills).
