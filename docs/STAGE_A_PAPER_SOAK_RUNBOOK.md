# Stage A — Unattended Paper-Soak Runbook

**Goal:** prove the bot runs **unattended** — the autonomous loop, safety rails, and the read-back
sentinel survive a full session (and multiple sessions, including disconnects and restarts) with **zero
human touches and zero real money**. Pass Stage A → graduate to Stage C (live-micro unattended).

Stage A is two parts. Both must pass.

| part | proves | money at risk | orders actually reach a broker? |
|---|---|---|---|
| **A1 — Autonomy soak** | the loop/guardian/dead-man/recovery run solo | none (dry-run) | no (paper sim fills) |
| **A2 — Read-back fidelity** | the sentinel reconciles real broker truth & halts on mismatch | none (Tradovate **demo**) | yes (TradersPost → demo) |

> Why two parts: in pure paper, dry-run orders never hit a broker, so a sentinel pointed at a real
> account would see "flat" and spam false MISSING alerts. A1 runs the loop with read-back OFF; A2 routes
> real order *mechanics* to a **demo** account so the sentinel has real positions to reconcile — fake money.

---

## Pre-flight (do once, before either part)

- [ ] Logged-in TradingView **Chrome on :9222**, NQ @ 1m, real-time CME entitlement (logged-out = delayed = DATA RED, correct fail-closed).
- [ ] `python3 -m pytest -q` → **432 passed**.
- [ ] Bridge smoke: `python3 bridge_test.py --ping --mode test` → TradersPost HTTP 200.
- [ ] Feed probe: `python3 tools/probe_tradingview_bars.py` → fresh bars, 0 dupes, 0 out-of-order.
- [ ] Machine set to **not sleep** for the soak window (caffeinate / power settings).

---

## PART A1 — Autonomy soak (pure paper, read-back OFF)

Run the full live loop in **paper** (no `--live` → dry-run webhooks, sim fills, auto-armed). Real feed,
real signals, real safety machinery — only the orders are simulated.

```bash
cd ~/trading-team/bot/nq-liq-bot
python3 auto_live.py \
  --account MFFU-50K-1 --tier 50K-conservative \
  --feed tradingview-1m --d1c-mode active-eval-filter \
  --execution traderspost --mode eval \
  | tee -a logs/stageA1_$(date +%F).log
```
Then **walk away.** Do not touch it for the whole session (NY-AM killzone 09:30–11:30 ET → EOD flat 14:30 ET).

### A1 unattended-survival checks (run across ≥3 consecutive sessions)
- [ ] **Boots & arms itself** — "entry gate armed", "flatten guardian armed", D1c mode printed, feed reaches GREEN with no prompt.
- [ ] **Trades the window autonomously** — A/B signals logged, dry-run webhooks sent, ARGUS rows written (no `ARGUS LOG FAILED`).
- [ ] **EOD flat fires by itself** — guardian flattens at 14:30 wall-clock; bot ends flat.
- [ ] **Disconnect drill** (mid-session, once): close the TradingView Chrome / kill the feed →
      data goes **RED**, **entry gate blocks new entries within one poll**, guardian still flattens at EOD. Reconnect → recovers to GREEN.
- [ ] **Restart drill** (mid-session, once): `Ctrl-C` the process, relaunch the same command →
      recovery rebuilds state from the ledger, **no double-run** (instance lock), no orphaned/duplicated trades.
- [ ] **Ledger coherent at EOD** — `python3 recon.py`-equivalent / journal shows no orphan positions, no naked entries, expected = flat.
- [ ] **Zero crashes / zero unhandled exceptions** in the log across all sessions.

**A1 PASS = all boxes checked across ≥3 sessions with no human intervention.**

---

## PART A2 — Read-back fidelity (Tradovate DEMO, real order mechanics)

Now prove the read-back sentinel actually reconciles a **real broker**. Route order mechanics to a
**Tradovate demo** account (fake money) and point the sentinel at that same demo account.

### A2 setup
- [ ] `config.TRADOVATE` → **real read-only creds** (name/password/cid/sec/app_id/device_id) and
      `account_spec` = the **demo account** name/id, `env` = the demo host. (Today it's the placeholder
      `YOUR_TOPSTEP_ACCOUNT` → auth fails by design; replace it.)
- [ ] Verify read-only: the sentinel client is built with **no `safety`** → it can never place an order
      (every order method raises `_guard_live`). Confirm with: `python3 -c "import auto_live, config; from journal import Journal;
      class A: account='MFFU-50K-1'; readback=True; readback_poll=20
      s,b=auto_live.build_readback(A(),'live',Journal('/tmp/rb.db')); print('broker connected:', b is not None)"`
      → expect **broker connected: True** once demo creds are in.
- [ ] TradersPost strategy → connected to the **demo** Tradovate (NOT the funded account). Double-check in the TradersPost UI.

### A2 run (live mechanics, demo money)
```bash
python3 auto_live.py \
  --account MFFU-50K-1 --tier 50K-conservative \
  --feed tradingview-1m --d1c-mode active-eval-filter \
  --execution traderspost --mode eval \
  --readback --readback-poll 20 \
  --controlled-tv-full-live-test --live --confirm \
  | tee -a logs/stageA2_$(date +%F).log
```
Expect on boot: `read-back sentinel armed (… floor=$48,000) — fail-closed`.

### A2 fidelity checks
- [ ] **Silent when coherent** — through a normal session where bot and demo agree, the sentinel logs **no confirmed discrepancies** and **never false-halts**.
- [ ] **Position tracks** — after a demo fill, `expected` and the demo `/position/list` agree in sign (partials/Exit#3 don't false-trigger).
- [ ] **ORPHAN detection drill** — while the bot believes FLAT, **manually open 1 MNQ on the demo account in the Tradovate UI** →
      sentinel raises `ORPHAN_POSITION` (BLACK) within ~`grace × poll` (≈40s), **halts entries, writes RECON_ALERT, fires flatten**.
- [ ] **DIRECTION drill** — while bot is long on demo, **manually flip to short** → `DIRECTION_MISMATCH` (BLACK) → halt.
- [ ] **Read-fail drill** — kill network/Tradovate auth mid-session → after 3 failed polls `BROKER_READ_FAIL` escalates to BLACK → **halt (fail-closed)**.
- [ ] **Heal check** — clear an injected discrepancy before grace confirms → **no halt** (grace suppresses the blip).
- [ ] **EOD reset** — sentinel resets `expected` to flat at each new ET day; no stale carryover.

**A2 PASS = silent on coherence + every injected discrepancy detected & halted, across ≥3 sessions, zero false halts.**

---

## Abort / fail criteria (either part)
- Any **false halt** on a coherent world, or any **missed** injected discrepancy → **FAIL**, do not proceed; fix and re-soak.
- Guardian fails to flatten at EOD, or a disconnect does **not** block entries → **FAIL** (safety regression).
- Any orphaned position or naked entry left at EOD → **FAIL**.
- Any crash / unhandled exception → **FAIL**.

## On full Stage-A PASS
You have proven: the loop runs unattended (A1) **and** the bot can see + reconcile broker truth and
fail-closed (A2) — the "confirm fills by eye" gap is closed. **Next: Stage C** — same A2 config but TradersPost
→ the **funded MFFU account**, 1 MNQ, operator nearby but hands-off, a few sessions → then truly unattended.

> Do NOT skip to funded money until BOTH A1 and A2 have passed ≥3 clean sessions each. The whole point of
> Stage A is to make the first real-money unattended session boring.
