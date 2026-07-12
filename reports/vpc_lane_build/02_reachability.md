# VPC Live-Poll Reachability Analysis (D5)

Branch `vpc-execution-lane`. Grounded in code, not prose. Question (per the deferral): what lag class
does a VPC entry face between bar close and webhook send, and can any VPC signal be SUPPRESSED the
way Profile A's were (A's W1/W2 "surface-lag" lesson)? If a real suppression class exists, say so
loudly — it would change the certified expectations.

## Method

Read the actual emission path end-to-end:
- `strategy_engine_vpc.ProfileVEngine.latest_signal` (what the signal reads / when it fires),
- `tv_feed.TradingViewFeed.live` + `_classify` (what the feed yields and when),
- `auto_live._engine_bar` → `on_v_signal` (how a fired signal becomes a webhook), and the
  `entry_gate` (`heimdall_monitor.entry_ready`) it must pass,
- `strategy_engine_vpc.WARMUP_BARS` (the cold-start gate),
- `vpc_trail_manager.on_1m_bar` (the trail's own bar cadence).

## What the code actually does

1. **The signal computes on CLOSED 5m bars only.** `feed.live()` yields a bar only after
   `_classify` clears it: a bar with timestamp `ts` is `"unclosed"` while
   `now < ts.tz_convert(UTC) + close_min` (`tv_feed.py:335`), so a 5m bar is emitted only once
   wall-clock ≥ its close. `ProfileVEngine.add_bar` buffers it and `latest_signal` recomputes the
   certified causal feature frame; the trigger at bar *i* is a pure function of bars ≤ *i* (the
   truncation canary, `test_vpc_signal_parity`). **There is NO per-signal freshness/drift gate on
   the VPC signal** — unlike Profile A, which additionally runs the D1c `DriftGate`
   (`auto_live.py`: `self.gate = DriftGate(...)`, consulted only for A). `on_v_signal` NEVER calls
   `self.gate`; D1c is Profile-A-only. So **A's D1c "surface-lag" suppression class has no VPC
   analog at the signal level.**

2. **The entry is a next-bar-open MARKET order.** The engine emits `entry_bar_offset=+1`; the
   certified fill is the next 5m bar's open. `on_v_signal` (armed) builds `build_vpc_entry`
   (a MARKET entry, `orderType:"market"`) and sends immediately on the signal bar's close.

3. **The trail steps on CLOSED 1m bars**, one at a time, with the monotonic guard rejecting any
   `bar_id <= last_bar_processed` (F2). No freshness gate on the trail either — a stale/replayed 1m
   bar is *rejected*, never re-stepped.

4. **Poll cadence.** `TradingViewFeed` polls every `poll_sec` (`tv_feed.py:168`, class default 20s);
   `auto_live` passes `--poll` (default 60s). So the operational detection interval is
   `poll_sec ∈ [20s, 60s]`.

## Lag class between bar close and webhook send

For a VPC entry on a signal bar with close at time `T_close` (= bar-open + 5m):

| Stage | Mechanism (code) | Added latency |
|---|---|---|
| Bar becomes emittable | `_classify` clears `"unclosed"` at `now ≥ T_close` | 0 (definitional) |
| Feed detects the closed bar | next `feed.live()` poll after `T_close` (`_t.sleep(self.poll)`) | ≤ `poll_sec` (20–60s) |
| Engine processes + fires | `add_bar`→`latest_signal` (pure, in-process) | ~ms |
| Webhook send | `on_v_signal`→`build_vpc_entry`→`sender.send` | ~ network RTT |
| Certified fill target | NEXT 5m bar's open (`entry_bar_offset=+1`) | up to +5m (by design) |

**Lag class: a single "one-poll detection lag" of ≤ `poll_sec` (20–60s) between bar close and send,
strictly bounded well inside the 5-minute bar the market entry targets.** Because the entry is a
MARKET order aimed at the *next* bar's open, a 20–60s detection lag lands the send with minutes of
slack before that open — it does **not** move the fill off the certified next-bar-open assumption,
and there is no per-signal staleness gate that could veto it after it fires. This is materially
*safer* than Profile A's path: A's D1c drift/staleness gate can VETO an A entry when the surface
reading drifts (A's W1/W2 lesson); VPC has no such per-signal veto.

## Can a VPC signal be SUPPRESSED? — the honest table

| Suppression class | Where in code | Applies to VPC? | Shared with A/B? | Changes certified expectations? |
|---|---|---|---|---|
| **A-style D1c surface-lag veto** (drift/staleness gate suppresses the *signal*) | `DriftGate` / `self.gate`, A-only | **NO** — `on_v_signal` never consults D1c | A-only | No — VPC is *less* gated than A |
| **Feed-RED / entry-gate block** (data not GREEN, dead-man not alive) | `entry_ready` (`heimdall_monitor.py:72`), threaded into `on_v_signal` via `entry_gate` | YES | YES (A, B, V equally) | No — fail-closed *infrastructure* gate, not a VPC edge property; a logged-out TV feed's 10-min delay pins the feed RED (`STALE_RED_S=300`) and blocks ALL lanes, VPC included |
| **Cold-start warmup gate** (`len(buf) < WARMUP_BARS`) | `strategy_engine_vpc.WARMUP_BARS=120`; `latest_signal` returns `None` until warm | YES | VPC-specific (mirrors tv_feed warmup) | **Only on a fresh mid-session restart** — see below |
| **Feed gap / missed bar** (a reconnect drops the signal bar) | `tv_feed.live` `gaps`/`ooo` counters; the bar is never buffered | YES | YES (A, B, V) | No systematic bias — a missed bar = a missed trade in *any* lane; VPC's max-2/day means no re-emergence, same as A |
| **Per-signal timing lag** (send too late to catch the fill) | one-poll ≤ `poll_sec` vs a +5m next-bar-open target | Bounded ≤60s ≪ 5m | shared | No — slack is minutes |

## The one real class — stated loudly

**COLD-START WARMUP is the only VPC-specific suppression class, and it is bounded and non-systematic.**
On a *fresh process cold-start intraday*, `ProfileVEngine` emits NOTHING until its buffer holds
`WARMUP_BARS = 120` continuous bars (~1.5 RTH sessions), because a cold rolling-14 ATR on an
incomplete buffer would diverge from the continuously-computed certified batch (the cross-audit's
diagnosed "cold-buffer artifact"). Consequences:

- In **steady-state continuous operation** (the certified assumption — the batch backtest is one
  continuous stream) the buffer is always warm, so **there is ZERO systematic suppression**; live
  VPC signal availability matches the certified taken-trade set. This is confirmed by
  `replay_5m_native` reproducing the certified ledger exactly (n=408) — and by construction that
  replay uses `warmup_bars=0` precisely because it starts from a genuine (equally-cold) history
  start, i.e. an apples-to-apples comparison.
- The suppression bites ONLY on an **operational fresh restart mid-session**: that session's early
  VPC signals (until 120 bars accumulate) are not emitted. This is an *operations/runbook* concern
  (start the process before the session, or warm from history), **not** a systematic haircut to the
  certified edge. It does not bias direction or PF; it can only drop early-session trades on a
  restart day.

## Verdict

- **Lag class:** one-poll detection lag ≤ `poll_sec` (20–60s), bounded well inside the 5-minute
  next-bar-open target — no per-signal staleness veto after firing.
- **Suppression:** VPC faces **no new signal-specific suppression class** relative to A, and
  specifically **lacks A's D1c surface-lag veto** (it doesn't consult D1c). The classes it *does*
  share are fail-closed infrastructure gates (feed-RED/entry-gate, feed-gap) that suppress ALL lanes
  identically. The only VPC-specific gate — cold-start warmup — is bounded, non-systematic, and does
  **not** change the certified expectations for a continuously-running process; it is a restart
  runbook item.
- **No real suppression class that changes the certified expectations exists** for steady-state
  operation. The honest caveat to carry into Phase-4 acceptance: a mid-session cold restart drops
  that session's pre-warm signals — verify the process is started warm (or warmed from history)
  before the RTH window, exactly as the A lane already requires.
