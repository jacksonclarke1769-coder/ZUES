# HEIMDALL-RECONNECT — Reset-Tolerant Data Readiness
_2026-06-15 · infrastructure only · Profile A/B/D1c/sizing untouched_

## Problem
A single harmless feed reset previously tripped `DATA_READY=false` permanently (any reset →
not-ready). Too brittle for unattended auto — but uncertainty must still block risk.

## Solution — tri-state data health (`tv_feed.data_state`)
| State | Meaning | New entries |
|---|---|---|
| **GREEN** | fully ready | allowed |
| **YELLOW** | recovered from a reset, stabilizing — OR currently reconnecting | **blocked** until stable |
| **RED** | stale / broken / too many resets / untrusted basis / no data | **blocked** |

`DATA_READY` (full-auto gate) = `data_state == GREEN` **AND** real-time CME entitlement confirmed.

## State logic (in order)
1. no bars yet → **RED**
2. last bar older than `STALE_RED_S` (300s) → **RED** (stale)
3. warmup span < 14 days → **RED**
4. basis untrusted (dukascopy warmup, no confident/cached basis) → **RED**
5. `reset_count` > `MAX_RESETS` (10) → **RED** (pipeline broken)
6. currently reconnecting → **YELLOW**
7. reset happened and `bars_since_reset` < `STABILITY_BARS` (3) → **YELLOW** (stabilizing)
8. else → **GREEN**

## Stability window
After any reset: `last_reset_ts` set, `bars_since_reset` zeroed, `_reconnecting=True`. On the next
successful fetch `_reconnecting` clears (→ YELLOW). Each accepted monotonic bar increments
`bars_since_reset`; once it reaches **3 fresh bars with monotonic timestamps and no oversize gap**,
state returns to **GREEN** and entries resume. A short reset therefore costs only ~3 bars of YELLOW,
not the whole session — but a real stall stays RED.

## Bar hygiene on reconnect (`tv_feed._classify` + `live()`)
Every candidate bar is classified before use:
- **dup** (timestamp already seen) → skipped
- **unclosed** (`now < open + resolution`) → skipped
- **ooo** (timestamp ≤ last emitted) → rejected, `out_of_order` counter++
- **ok** → emitted; gap beyond 3× resolution increments `gaps`

So duplicates and out-of-order bars **cannot reach the strategy**, and the warmup buffer is never
corrupted on a reconnect (bars only ever advance monotonically).

## Entry gate
`auto_live` blocks routing an entry unless `entry_ready()` = data **GREEN** AND dead-man **alive**
(`heimdall_monitor.entry_ready`). Wired into `LiveAuto.on_decision` alongside the existing
kill/D1c gates — infrastructure gate, not strategy.

## Fields exposed (`data_status`)
`data_state`, `state_reason`, `last_bar_age_s`, `reset_count`, `last_reset`, `bars_since_reset`,
`reconnecting`, `out_of_order`, `gaps`, `basis_confident`/`basis_from_cache`, `DATA_READY`.

## Tests
Single reset → YELLOW → GREEN after 3 bars; reconnecting → YELLOW; stale → RED; >MAX_RESETS → RED;
dup/ooo/unclosed classification; DATA_READY only when GREEN+realtime. (in `test_tv_feed.py`.)
