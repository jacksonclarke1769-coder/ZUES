# Risk Arithmetic Reconciliation — 2026-07-05

**Verdict: (c) — live config and the certifying simulation DISAGREE on per-trade sizing.**
The certified rev b numbers (pass 58.2 / bust 29.1 / expire 12.7) do NOT describe the machine
`go-live-recert.sh` launches. Honest numbers for the live-configured machine: **pass 47.8 /
bust 15.9 / expire 36.2 / median 16d / E[$/attempt] $5,773**. Escalated to operator; ops cycle
halted at Task 1 per protocol.

## Question 1 (as asked): does the $550 daily stop contradict $1,200/trade risk?

**No — live and sim AGREE here.** The $550 daily stop is a **cumulative post-loss entry
blocker**, not a per-trade loss clamp. A single full −1R loss (−$1,200) is allowed to land in
full; the day then shuts for further entries. This is deliberate and documented in code.

### Live path
- Stop defined: `config_defaults.py:90-96` (`daily_stop_dollars()` = 275pt × 1ct × $2 = $550);
  `auto_safety.py:14-16` (`APEX_DAILY_STOP`).
- Measurement: `auto_live.py:1198-1201` re-computes **modeled entered-P&L** from the ledger every
  bar via `trade_results.day_entered_pnl()` (`trade_results.py:41-59`, realized-at-exit, rejected
  rows excluded) and trips `DailyGuard.stop_now()` at ≤ −$550.
- Enforcement: entry-block only, pre-order (`auto_live.py:219-230` `killed()`,
  `auto_live.py:263-268`); flatten is the separate FlattenGuardian (`flatten_guardian.py:73-84`).
- The design intent is explicit in `auto_live.py:162-173` (`_risk_gate` docstring): *"deliberately
  NOT bound to the $550 headroom — a single certified A trade risks >$550 by design (the sims let
  the tripping trade's full loss land)"*.
- Known micro-race: guard recalcs once per bar, so a trade-2 signal in the same bar as trade-1's
  exit can slip through before the trip; guardian flattens next bar. Immaterial at A's ~2 trades/day.

### Sim path (`tools_account_size_research.py`, producer of the certified row)
- `day_rows()` lines 56-78: full trade loss lands (`r["real"] <= -stop` sets `stopped`); once
  stopped, **subsequent** trades that day are skipped. No clipping. Same semantics as live.
- Apex $1,000 DLL modeled as marked-trough flatten (lines 73-76); bust = intraday marked breach
  or EOD close below trailing threshold (`eval_run()` lines 81-101).

## Question 2 (found during the trace): the sizing cap divergence — VERDICT (c)

| | Certified sim | Live engine |
|---|---|---|
| Per-trade qty | `min(60, MAX_A_QTY=40, 1200//risk1)` — `tools_account_size_research.py:40,47` | `min(tier am=10, 1200//risk1)` — `auto_live.py:316-330` + `_risk_gate` `auto_live.py:203`; tier `Apex-50K-eval` `am=10` (`auto_safety.py:41`) |
| Effective A cap | **40 MNQ** | **10 MNQ** |

Every describing document — `reports/apex_validation.json §dll_recert_selected_machine`
("size-to-risk $1,200/contract-budget (max 10 MNQ)"), the machine name "A10", the vault, the
`go-live-recert.sh` banner — asserts the cap is 10. The harness that produced the number capped
at 40 (`MAX_A_QTY=40` present since the certification commit `303fa9e`).

**Materiality (measured on the certified A stream, n=435 trades):**
- Stops p10/50/90 = 18.3 / 41.7 / 99.6 pt → `1200//risk1` exceeds 10 on **64.6% of trades**.
- On those trades the sim sizes mean **21.9 contracts vs live 10**; total sim dollar risk is
  **1.42×** what the live machine would take.

**Honest re-run (baseline reproduced exactly first, then cap flipped — only change):**

| Machine | Pass | Bust | Expire | Median | Worst day | E[fund$] | E[$/attempt] |
|---|---|---|---|---|---|---|---|
| Certified (cap 40) — reproduction | 58.2 | 29.1 | 12.7 | 11d | −$1,000 | $12,207 | $7,040 |
| **Live config (cap 10)** | **47.8** | **15.9** | **36.2** | **16d** | −$1,000 | $12,206 | **$5,773** |

(n=395 starts, same harness functions, `MAX_A_QTY` monkeypatched 40→10; funded leg $480 budget
barely touches the cap, hence E[fund$] unchanged.)

Reading: the live machine is materially **safer** (bust 29.1→15.9) but **slower** — pass drops
10.4pp and expiry triples (12.7→36.2) against the 30-day clock. E[$/attempt] −$1,267 (−18%).
Additional live-only constraints the sim doesn't model (P3 cushion brake halving size near the
floor, `OPEN_RISK_CUSHION_FRAC` budget shrinkage) all push the same direction, so 47.8% is an
**upper bound** for the live-config pass rate under this model.

## Downstream contamination
- `AGENTS.md` §Production Machine, vault machine page, `go-live-recert.sh` banner, dashboard,
  memory files — all quote 58.2/29.1 as the live machine's odds.
- The conditional pass forecaster for the in-flight eval (`a9865bf`) — verify which stream it
  consumes; if certified-stream sizing, its ~33% read inherits the same bias.

## Operator decision required (certification event either way — NOT taken by this session)
1. **Re-lock at cap 10** (accept 47.8/15.9/36.2): honest description of current live config;
   bust nearly halves, but expiry-heavy against the 30-day clock, E[$/attempt] −18%.
2. **Raise live cap toward the modeled 40** (`EVAL_TIERS am`): restores certified odds but is a
   4× size increase on tight-stop trades — needs fill-quality/liquidity judgment at 20-40 MNQ
   (the `MAX_A_QTY=40` comment itself flags "fill-quality realism") and full re-cert + approval.
3. Or an intermediate cap, re-certified.

Until one of these is taken: **do not quote 58.2/29.1 as the live machine's odds.**

## Reproduction
```bash
cd ~/trading-team/bot/nq-liq-bot
# baseline (must print 58.2/29.1/12.7/11d) then cap-10 rerun: see this report's git history
# or re-run tools_account_size_research.py with MAX_A_QTY=10
```

— zeus-architect (Fable), ops cycle 1, 2026-07-05
