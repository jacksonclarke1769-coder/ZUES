# HEIMDALL-RECONNECT — Heartbeat + Dead-Man Monitor
_2026-06-15 · infrastructure only_

## Purpose
Prove the live process's *nervous system* is alive. A frozen runner, crashed thread, or silent
stall must turn the dashboard RED and block new entries — never trade through a dead process.

## Heartbeat (`heimdall_monitor.write_heartbeat`)
- Path: **`out/heimdall/heartbeat.json`** (atomic write via temp + `os.replace` — readers never see
  a half-written file).
- Written **every guardian tick (~20s)** by `FlattenGuardian` — the feed-INDEPENDENT timer thread.
  So the heartbeat keeps updating even when the bar feed is stale (process alive, feed dead are
  distinct), and stops only if the whole process freezes/crashes.
- Fields: `ts`, `pid`, `account`, `guardian` (armed), `data_state`, `data_ready`, `last_bar`,
  `last_bar_age_s`, `reset_count`, `reconnecting`, `last_webhook`, `flatten_fired`, plus static
  meta (`mode`, `tier`, `d1c_mode`, `execution`).

## Dead-man (`heimdall_monitor.deadman_status`)
Reads the heartbeat and returns `{state, age_s, reason, alive}` by age:
| Age | State | alive | Effect |
|---|---|---|---|
| ≤ 60s (`WARN_S`) | **OK** | true | normal |
| 60–180s | **WARN** | true | lagging — surfaced, still operating |
| > 180s (`RED_S`) | **RED** | false | stalled → block entries + dashboard RED |
| no heartbeat | **RED** | false | not running / never started (dashboard not-green, not RED) |

`age_s is None` distinguishes **never ran** (absent) from **stalled** (present-but-old) — the
dashboard only goes RED on a *running process that stalled*, not on an idle/not-deployed bot.

## What it detects
Frozen process · crashed runner · stalled main loop (heartbeat stops) · silent stall. Combined with
`data_state`, also: stale feed (heartbeat fresh but `data_state=RED`), reconnect churn (`reset_count`).

## Where it blocks risk
- **Entry gate** (`entry_ready`): no new entries unless data GREEN **and** dead-man alive.
- **Dashboard** (`zeus_server`): GREEN requires `dm_ok`; a stale (present) heartbeat → **RED**.
- **Full-auto preflight** (`auto_safety.full_auto_preflight`): FAILS unless dead-man alive **and**
  `data_state == GREEN` — so full auto cannot arm without a live heartbeat + stable data.

## Optional kill-flatten
The guardian's kill path (lockout / operator kill / daily-stop) already fires a flatten. A
heartbeat-based external kill (separate watchdog process) is a future hardening; today the dead-man
**blocks new risk** and turns the surface RED, and the wall-clock EOD flatten still fires
independently of the feed.

## Tests
Heartbeat write/read; dead-man OK/WARN/RED + missing; entry-gate blocks on YELLOW and on dead
dead-man; dashboard RED on stale heartbeat; dashboard not-green when heartbeat missing; preflight
fails on stale/absent heartbeat; guardian stays armed + keeps writing heartbeat across a reconnect.
(`test_heimdall_monitor.py`, `test_flatten_guardian.py`, `test_apollo_gate.py`.)
