> ## 🔒 2026-07-02 — SELECTED MACHINE LOCKED + STALE-PROCESS WARNING
> The certified live machine is **A10 · Exit#3 · D1c active · size-to-risk $1,600 · B OFF · momentum
> OFF** (`reports/apex_validation.json`). Any auto_live process started before 2026-07-02 runs the OLD
> de-certified config and must not be trusted — kill it, don't reason about it.
> **Before ANY live restart:** 1) rotate the Tradovate password (old one exposed — audit T), 2) verify
> the Apex trailing DD on the live dashboard ($2,500 assumed; if $2,000 → update config.py
> EVAL.trail_dd first), 3) confirm the Tradovate account-manager panel is READABLE in the :9222 Chrome
> (read-back dies without it), 4) launch ONLY with `./go-live-recert.sh`.
> **Session processes (all four):** `auto_live.py` (via go-live-recert.sh) · `feed_watch.py --heal` ·
> `zeus_server.py` · `python3 deadman_watch.py --account APEX-50K-EVAL-1 --live`  ← NEW external
> dead-man watchdog (alerts at 3min heartbeat silence, flattens at 7min during market hours).

# OPERATOR RUNBOOK — nq-liq-bot (T-MINUS 24 edition)

Written for a tired, distracted operator at 23:00 Perth. Every alert has an action.
If in doubt at ANY point: `python3 -c "from flatten import ...;"` is NOT the way —
use the one command below, then sleep. The system fails closed without you.

---

## THE ONE EMERGENCY COMMAND

```
python3 ops_flatten.py            # (B1 wires this) — until then: broker mobile app:
                                  # close all positions, cancel all orders, DONE.
```
Mobile-app flatten is ALWAYS legitimate. It will trip a BLACK recon alert tomorrow —
that is the system working, not you breaking it. Note what you did in the incident log.

## DAILY PRE-FLIGHT (before 21:25 Perth / 09:25 ET) — 5 minutes

```
1  VPS up? dead-man green?                      (phone widget)
2  cd bot && git status --short                 -> MUST be empty (no uncommitted edits)
3  python3 -m pytest -q --collect-only | tail -1 -> expected test count, not 0
4  python3 migrate_b1.py data/journal.db        -> "already current"
5  python3 locker.py verify                     -> "LOCKER OK"
6  dashboard: all panels green/yellow only; lockout=None; cushion sane per account
7  feed age < 60s; broker auth OK; contract == same on all accounts (roll week!)
8  IF ANY LINE FAILS -> do not trade today (bot stays paper/disabled), file incident.
```

## DAILY POST-SESSION (после 14:35 ET / before bed) — 5 minutes

```
1  all accounts FLAT (dashboard + broker UI both)
2  EOD record written (dashboard shows today's EOD tick)
3  fills reconciled: bot trades == broker fills (count + PnL)
4  cushion + P3 state per account noted; payouts due? request per retention policy
5  yellows acknowledged; oranges -> root-cause note TONIGHT
```

## ALERT -> ACTION TABLE (no alert without an action)

| alert (HEIMDALL) | tier | YOUR ACTION | escalation if unresolved |
|---|---|---|---|
| heartbeat_stale | ORANGE | check VPS/process; restart service if frozen | 30 min -> mobile-flatten + stop |
| heartbeat_dead | RED | bot may be down: VERIFY FLAT via broker app NOW | flatten via app; investigate tomorrow |
| feed_lagging | YELLOW | note it; no action in-trade | recurs 3 days -> failover test |
| feed_stale_failover | ORANGE | confirm failover engaged (dashboard) | if position open and >15min -> RED row |
| feed_dead_with_position | RED | broker app: verify bracket WORKING; if unsure, flatten | always file incident |
| A_quiet / B_quiet | YELLOW | weekend check: run engine self-test on last 30 days | >12d (A) -> ORANGE: parity run |
| recon_unknowns | BLACK | bot already flattening+locking. VERIFY FLAT in app. Do NOT clear lockout tonight | next day: full reconciliation vs statements, then operator_clear with note |
| naked_position_alerts | RED | bot flattens at 60s. Verify in app | incident + do not trade next session until root-caused |
| lockout_active | BLACK | system is DOWN ON PURPOSE. Read the reason. Sleep if flat | clear ONLY after written root-cause (>=10 chars enforced) |
| p3_braked_* | YELLOW | informational — sizing already reduced | none |
| trade_cap_breach_* | RED | should be impossible (hard cap) — flatten, stop, incident | escalate to code review |

Notification chain: push -> 30 min unacked -> SMS. During 02:00-07:00 Perth the system
is DESIGNED to need no human: brackets are server-side, flatten is wall-clock, BLACK
locks itself out. Morning pre-flight catches the rest.

## STARTUP (after any stop/crash/deploy)

```
1  ONE instance only:    ps aux | grep bot     (instance lock enforces, you verify)
2  python3 -m pytest -q  -> all green (deploys only)
3  start service         -> watch logs for: lock acquired -> recovery report ->
                            "0 unresolved" -> STATE_ASSERT clean -> engine start
4  recovery resolved >0 items? READ THEM before allowing entries (dashboard prompt)
5  dashboard green -> done
```

## SHUTDOWN (planned)

```
1  no open positions?  (if open: either wait for flat or mobile-flatten first)
2  stop service        (lock releases itself)
3  locker.py snapshot  (journal filed)
```

## ACCOUNT VERIFICATION (new credentials arriving — THE T-MINUS-24 PROCEDURE)

```
1  credentials -> macOS keychain / VPS env vars. NEVER into config.py, NEVER into git.
2  config: env='demo' stays until GATEWAY Gate 6. SAFETY.enabled stays False.
3  bot reads account spec from broker and ASSERTS it matches config (plan, size,
   contract caps) before any session — mismatch = refuse to start.
4  file the firm's account confirmation email -> evidence/approvals/.
5  DO NOT TRADE the funded account until Gates 1-5 are green. A funded account
   sitting idle loses nothing (check firm inactivity rule: note the date!).
```

## ROLL WEEK (quarterly contract expiry — Mar/Jun/Sep/Dec)

Around the 3rd Friday of each quarter (next: ~2026-09-09 → 2026-09-18), TradingView's NQ1!
continuous feed and TradersPost/Tradovate can resolve DIFFERENT front-month contracts, causing
bracket prices to be off by the calendar spread (75-150 pts). The preflight will BLOCK if
`TP_SYMBOL_MNQ` is not set during this window.

```
1  Identify the active front-month ticker (e.g. MNQU2026 for Sep expiry).
2  Verify TradingView chart contract matches the active month (check bottom-left symbol label).
3  In .env, set:  TP_SYMBOL_MNQ=MNQU2026   (replace with the actual contract code)
4  Restart the bot.  preflight will pass; all MNQ orders will use the pinned symbol.
5  After expiry Friday rolls to the next month, update TP_SYMBOL_MNQ (or remove to restore
   bare MNQ default) and restart.
```

## SECRETS RULES

- config.py holds PLACEHOLDERS only; real values via environment/keychain.
- One credential exposure incident already happened in this project's history. Zero
  tolerance: anything typed into a chat/file by accident -> rotate the same day.

## INFRASTRUCTURE (current design state)

- Primary: datacenter VPS (Chicago/NY) — TO PROVISION (O3). Home Mac = monitor only.
- Dead-man: external ping service, 5-min interval, 2 misses -> page — TO PROVISION.
- Backups: journal.db hourly off-box (locker snapshot + sync); Store nightly;
  restore drill monthly (HEIMDALL).
- Backup VPS: manual promotion documented in HEIMDALL §5; not automated (by decision).
