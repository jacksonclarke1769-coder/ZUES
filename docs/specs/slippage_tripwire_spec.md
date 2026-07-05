# SPEC — Execution Slippage Tripwire (SLIP-class halt)

> ⚠ 2026-07-05: certified numbers corrected to 47.8/15.9/36.2 (cap-10 re-lock, DEC-20260705-1102); 58.2/29.1 figures below are the pre-correction baseline.

**Status:** BUILT 2026-07-03 — alert-only mode wired into `go-live-recert.sh` (cannot halt/flatten;
observational). Default OFF everywhere else. Halt mode built + tested, opt-in via `--slip-mode halt`.
**Author:** Trading CEO / ZEUS, 2026-07-03 (pre-Monday-live)
**Machine:** ZEUS v2026.07.02b (A-only · Exit#3 · D1c · size-to-risk $1,200 · B OFF · momentum OFF)
**Depends on:** `exec_telemetry.py` (data source), `live_readback.ReadbackSentinel` (halt plumbing)

---

## 1. Why this exists (the one-paragraph case)

The entire certified pass rate — **58.2% pass / 29.1% bust** — is computed on **adverse-first
backtest fills** that assume the A limit fills **at the modeled level with ~0 entry slippage**.
That assumption has **never been checked against a real Tradovate fill.** If live entries fill
even **0.10R worse on average** ($120/trade at 1R = $1,200), that is a direct, silent tax on every
trade's expectancy — enough to move a 58.2/29.1 machine toward the bust wall without a single line
of the dashboard turning red. Slippage is the **#1 unmeasured variable** in the whole system, and
the eval has only **~$1,905 of cushion**. This tripwire makes the **first ~10 live fills teach us
the real number** and **auto-halts new entries** before an unmodeled cost silently drains the eval.

`exec_telemetry.py` already *measures* slippage. This spec adds the part that **acts on it.**

---

## 2. Design contract (non-negotiable)

1. **Observational-first, halt-only.** Like a READ-class read-back BLACK, a slippage breach
   **HALTS new entries + alerts the operator. It NEVER flattens.** Bad fills do not mean the open
   position is wrong — they mean the *entry assumption* is leaking. Existing Exit#3 brackets stay
   on the book untouched. (Mirrors `live_readback.py` lines 26–29 discipline.)
2. **Never raises into the order path.** Same contract as `exec_telemetry`: every method wrapped
   in try/except, prints loudly, returns. A tripwire bug must never block or crash a trade.
3. **Reuses existing plumbing, invents none.** The halt latches through the **same
   `entry_gate()` mechanism** `auto_live` already checks at lines 271 & 448, and clears through the
   **same operator `/resume` → `reset()`** path. No new kill-switch, no new file protocol.
4. **Default OFF, flag-gated.** Ships behind `--slip-tripwire` (or
   `config_defaults.SLIP_TRIPWIRE_ENABLED=False`). Monday launch may run it in **alert-only mode
   first** (see §6) so it cannot itself cause a halt on day one until we trust it.
5. **Warm-up guarded.** No halt is possible before `SLIP_WARMUP_MIN` resolved fills — one bad
   print can never stop the machine.

---

## 3. Signals it watches (all already in `exec_telemetry.csv`)

| Metric | Source column | What a breach means |
|---|---|---|
| **Entry slippage** | `slippage_R` (FILLED rows) | Fills are systematically worse than modeled → expectancy tax |
| **Miss rate** | `resolution` = MISSED vs FILLED | Limits aren't filling → the paper edge is **never captured** at all |
| **Single-fill outlier** | `slippage_R` | One catastrophic fill (fat gap / bad routing) |

> The miss-rate signal is as important as slippage: a modeled edge you can't get filled on is a
> phantom edge (cf. the 2026-06-30 blind-trading finding — trades that never filled looked like P&L).

---

## 4. Thresholds (grounded in 1R = $1,200, MNQ $2/pt)

All configurable in `config_defaults.py`. Proposed initial values, deliberately conservative
because cushion is thin (~$1,905):

```
SLIP_WARMUP_MIN        = 5      # no action before 5 resolved fills
SLIP_WINDOW_N          = 10     # rolling window of most-recent FILLED entries
SLIP_MEAN_R_HALT       = 0.10   # mean entry slippage over window > 0.10R  -> HALT   (~$120/trade tax)
SLIP_SINGLE_R_ALERT    = 0.25   # any single fill > 0.25R worse           -> ALERT  (~$300 on entry alone)
SLIP_SINGLE_R_HALT     = 0.50   # any single fill > 0.50R worse           -> HALT   (half the risk, on entry)
MISS_RATE_WINDOW_N     = 10     # rolling window of resolved A signals
MISS_RATE_HALT         = 0.40   # MISSED / (FILLED+MISSED) > 40%          -> HALT
```

**Rationale for 0.10R mean halt:** `tools_exec_report.py` already models expectancy sensitivity at
**−0.05R/trade**. A sustained 0.10R entry cost is *2× that sensitivity band* — past the point where
the certified 58.2% pass rate can be assumed to hold. Halting there buys a re-cert decision while
cushion still exists, rather than after it's gone.

**Positive slippage is fine.** Sign convention (from `exec_telemetry`): positive = worse. Better-
than-modeled fills (negative) never trip anything.

---

## 5. Behaviour on breach

```
on each exec_telemetry row resolution (FILLED / MISSED):
    if resolved_count < SLIP_WARMUP_MIN: return        # warm-up
    evaluate the three rules over the rolling windows
    if SINGLE_R_ALERT breached  -> Telegram alert, NO halt, annotate
    if any HALT rule breached:
        sentinel.slip_halt(reason)      # latches entry_gate CLOSED, fires alert ONCE
        # NO flatten. brackets stay. operator decides: re-cert / re-tune size / resume.
```

- Halt reason string is explicit, e.g.
  `SLIP-HALT: mean entry slippage 0.14R over last 10 fills (cap 0.10R) — entries frozen, brackets live, position untouched.`
- Clears **only** by operator `/resume` (→ `reset()`), identical to a read-back halt. No auto-clear.
- Writes a `SLIP_HALT` line to the decision log + `out/exec/slip_halt_events.csv` for the exec
  report.

---

## 6. Monday rollout mode (safety-laddered)

1. **Session 1 (Mon):** run **alert-only** (`SLIP_TRIPWIRE_MODE=alert`) — the tripwire *computes and
   Telegrams* every breach but does **not** latch a halt. We are supervising live anyway; we want to
   see the real slippage number before we let an unproven monitor stop the machine.
2. **After the first ~10 fills** produce a sane slippage distribution → flip to
   `SLIP_TRIPWIRE_MODE=halt` for unsupervised windows.
3. `tools_exec_report.py` gets a one-line summary appended: *"tripwire status: N breaches, would-
   have-halted at fill K"* so alert-only mode still tells us if it would have fired.

---

## 7. What this is NOT

- Not a P&L stop (that's the $550 daily guard — separate, already live).
- Not a flatten trigger (that's MISMATCH-class read-back — separate).
- Not an edge-finder. It protects the edge we *have* from execution leakage. It buys **decision
  time**, not trades.

---

## 8. Build checklist

- [x] `slip_tripwire.py` — pure `evaluate(slips, resolutions, cfg) -> (action, reason)`, no I/O,
      unit-tested against synthetic sequences (clean / creeping / one-fat-print / high-miss / window
      rolloff / negative-slip). Stateful `SlipTripwire` monitor (off/alert/halt) on top.
- [x] `ReadbackSentinel.slip_halt(reason)` — latches `halted` + alerts once, reuses existing
      `ready()`/`reset()`; never flattens. Tested (latch, idempotent, no-flatten, /resume clears).
- [x] Wired in `auto_live` at the `on_fill_confirmed` (FILLED) and `on_missed` (MISSED) resolution
      points; `exec_telemetry.on_fill_confirmed` now returns `slippage_R` for direct consumption.
- [x] `--slip-tripwire` flag + `--slip-mode {alert,halt}`; `config_defaults` SLIP_* block; default **off**.
- [x] `go-live-recert.sh` arms it in **alert** mode (safe: cannot halt/flatten).
- [x] Tests green — 17 new, full suite **739 passed / 1 skipped**.
- [ ] TODO (post-first-fills): extend `tools_exec_report.py` with a "would-have-fired at fill K" line;
      flip Monday session to `--slip-mode halt` once the live slippage distribution is trusted.
