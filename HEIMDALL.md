# HEIMDALL — Bot Survival System (Operational Specification)

Status: SPEC (2026-06-10). The living ops manual for the frozen stack
(A v2 + B v1, P3, ZEUS v2, HADES controls, RAGNAROK amendments).
Goal: every failure mode is detected before it can materially damage the business.
Anchored in this repo: `bot.py`, `mffu_state.py`, `store.py`, `paper_live.py`,
`dashboard_server.py`, `config.py` (SAFETY), `tradovate_client.py`.
Calibration sources: validation baselines (A live-fill PF 1.39, +0.263R/trade;
B PF 1.30; unit day mean $40.9 / sd $210; worst day 4/2 = −$1,921, outage-stressed
−$2,881 vs $4,500 cushion) and three real incidents already experienced:
stale Dukascopy feed (8h), silent zero-signal window, empty pytest collection.

---

## 1. FAILURE MODE AUDIT (probability / severity / detectability, 1-5, 5=worst/hardest)

| # | Failure | P | S | D | Notes / observed? |
|---|---|---|---|---|---|
| T1 | Silent signal-generation failure (engine runs, no signals) | 4 | 3 | 5 | OBSERVED (Jun 2026). Deadly because it looks like a quiet market |
| T2 | Edge decay | 3 | 4 | 4 | RAGNAROK: graceful but timeline-killing; 90-trade window ≈ 3.2 months latency |
| T3 | Strategy drift (code change alters frozen logic) | 2 | 4 | 3 | Signal-parity test exists (`test_signal_parity.py`) — must run in CI |
| T4 | Position sizing error (2× contracts) | 2 | 5 | 2 | Deadliest known error (53-62% blow). Hard cap required |
| T5 | P3/risk engine silently disabled | 2 | 4 | 4 | Survival 98→90%/yr per account; slow-acting |
| E1 | Missed entries (limit never filled/placed) | 3 | 2 | 3 | Income loss only; baseline 10% assumed |
| E2 | Missed/failed EXIT (bracket absent) | 2 | 5 | 2 | The only execution path to breach. Server-side brackets mandatory |
| E3 | Slippage spike | 3 | 2 | 1 | Validated to +2pt; measurable per fill |
| E4 | Order rejection loop | 2 | 3 | 1 | API error codes visible |
| B1 | Broker API outage mid-position | 3 | 4 | 1 | Worst-day-stressed −$2,881 < cushion if brackets server-side |
| B2 | Auth failure at session open | 3 | 2 | 1 | No entry = no risk; income loss |
| B3 | Position mismatch (bot state ≠ broker) | 2 | 5 | 2 | BLACK-tier; reconcile every poll |
| C1 | Trade not copied to sibling account | 3 | 2 | 2 | Divergence, income variance |
| C2 | Copier direction flip / wrong qty | 1 | 5 | 2 | BLACK-tier; same-direction validator |
| C3 | Copier disabled during Topstep payout processing | 4 | 2 | 1 | Known platform behavior; schedule around |
| I1 | Feed stale/outage | 4 | 3 | 1 | OBSERVED. Bar-age monitor; dual feed exists in code |
| I2 | VPS/process crash | 3 | 3 | 1 | Heartbeat + auto-restart + fail-closed |
| I3 | Clock drift | 2 | 3 | 1 | NTP check; session windows are time-critical |
| I4 | DB corruption (`data/bot.db`) | 2 | 3 | 2 | Daily snapshot + integrity check |
| H1 | Missed supervision night | 4 | 1 | 1 | Bot is autonomous + fail-closed; tolerable |
| H2 | Config error on deploy | 3 | 4 | 2 | Config checksum vs signed reference at startup |
| H3 | Wrong account targeted | 2 | 4 | 2 | Account-ID allowlist in SAFETY |
| H4 | Tests silently not running | 3 | 3 | 4 | OBSERVED (pytest collected 0). CI must fail on `collected 0` |
| F1 | Prop rule change | 4 | 3 | 2 | Weekly rule-page diff check (manual) |
| F2 | Firm shutdown / payout freeze | 2 | 4 | 2 | HADES: survivable; standby + reserve |
| F3 | Regulatory change | 2 | 3 | 3 | Quarterly review item |

Top combined risks: **T1 (silent no-signal), T4/E2/B3/C2 (the four BLACK-tier account-killers),
T2 (decay), I1 (feed)** — the dashboard and tripwires below are built around exactly these.

## 2. BOT SURVIVAL DASHBOARD (extends `dashboard_server.py`)

**A. Trading Health** (per strategy A/B and blended; from `store.trades`)
- Rolling-90-trade expectancy (R and $) vs validation baseline (A: +0.263R; B: +4.0pt).
  Bands: ≥90% green · 70-90% yellow · 50-70% orange · <50% red.
- Rolling-90 PF vs live baseline (A 1.39, B 1.30): <1.2 yellow, <1.0 orange.
- Win rate (baseline 46-47%): outside 35-58% on 90 trades = yellow.
- Current DD vs MC envelope: > DD95 ($3.6k/unit-scaled) orange; > DD99 red.
- **Days since last signal: A >7 calendar days = yellow, >12 = orange (catches T1);
  B >3 trading days = yellow.** (A trades ~1 per 1.8 trading days.)
- Live-vs-validation drift panel: side-by-side of last-90 vs backtest distribution.

**B. Execution Health** (from fill logs / `paper_fill_log.csv` schema)
- Slippage per fill vs 2pt assumption: rolling-20 mean >1.0× = green, >1.25× = yellow, >1.5× = orange.
- Entry fill rate vs 90% baseline: <80% over 20 signals = yellow.
- **Bracket integrity: % of open positions with confirmed server-side stop+target = must be 100%; anything else = RED.**
- Copy success rate across 5 accounts: <100% on any day = yellow; qty/direction mismatch = BLACK.
- Order rejection count: >2/day = orange.

**C. Infrastructure Health**
- Feed freshness: last bar age. >2× poll interval = yellow, >5 min in-session = orange (auto-failover), >15 min with open position = red.
- Broker API: last successful auth + poll round-trip; 3 consecutive failures in-session = orange.
- Process heartbeat (every 60s to `store.set_state`); external dead-man's-switch ping every 5 min to an OFF-VPS monitor — 2 missed pings = page operator.
- Clock drift vs NTP: >2s = yellow, >10s = orange (session windows are time-gated).
- DB: nightly `PRAGMA integrity_check` + snapshot success flag.

**D. Portfolio Health** (from `mffu_state` per account)
- Per-account: phase, balance, cushion $, cushion % of dd, payouts to date, next-payout ETA.
- Funded count vs plan (3 MFFU + 2 TS + 1 standby), evals in flight, cash reserve vs $6k target.
- Cumulative payout vs MFFU $100k/user cap; live-transition trigger countdown (3 consecutive payouts).
- Capital growth vs VALHALLA conservative corridor (the honest baseline per RAGNAROK).

**E. Risk Health**
- Distance to floor per account ($ and %); P3 state (NORMAL/BRAKED) with threshold readout (40%/60% of dd) — **P3 checksum: thresholds loaded and non-zero at startup, displayed in green/red.**
- Daily loss usage vs $800 halt; trades today vs 2-cap.
- Account survival estimate: cushion percentile vs MC distribution.

## 3. TRIPWIRE SYSTEM

| Tier | Trigger (examples — full set above) | Action | Recovery |
|---|---|---|---|
| GREEN | new fill, payout, eval pass, daily summary | log + dashboard | — |
| YELLOW | expectancy 70-90% of baseline · slip >1.25× · fill rate <80% · feed age >2× poll · 1 copy miss · A silent >7d | investigate within 24h; no trading change | clears when metric re-enters band for 5 days |
| ORANGE | expectancy 50-70% (→ L2 half size) · DD > DD95 · feed >5min in-session (failover) · 3 API failures · rejection loop · clock >10s · B silent >3 sessions w/ A active | human review SAME day; size already auto-reduced where defined | written note in `store.events` + metric back in band 10 days, then restore |
| RED | expectancy <50% (→ halt new entries) · DD > DD99 · bracket integrity <100% · feed >15min with open position · daily loss ≥ $800 | **trading disabled for new entries; existing positions managed to exit; operator paged** | root-cause doc + restart criteria of §4 / incident playbook; manual re-arm only |
| BLACK | position mismatch bot≠broker · copier direction/qty flip · unexplained cushion drop crossing P3 floor · account trading outside allowlist | **flatten everything, disable all order routing (SAFETY.enabled=False), page operator** | full reconciliation against broker statements; paper-mode parity run before re-arm; 2-person rule if available (operator + checklist) |

Alert delivery: push (primary) + email (secondary); ORANGE+ unacknowledged 30 min → SMS.
The dead-man's-switch lives OFF the VPS: silence = page, regardless of what the bot thinks.
Fail-closed principle everywhere: no heartbeat → no new orders; brackets are placed WITH
the entry as one server-side OCO or the entry is cancelled.

## 4. EDGE DECAY MONITOR (RAGNAROK tripwire, statistically honest)

Window: rolling 90 trades blended (≈3.2 months at ~28 trades/mo) + rolling 30 per strategy
as early-warning (noisier). Baseline = frozen validation expectancy.
NOTE: with healthy edge, L1 will false-fire occasionally (90-trade SE ≈ 0.4-0.5× mean) —
responses are deliberately proportionate, never destructive.

| Level | Trigger (rolling-90) | Sizing response | Investigation | Restart criteria |
|---|---|---|---|---|
| L1 | <90% of baseline | none (informational) | check execution-health first (slippage/fills often masquerade as decay) | auto-clears ≥90% for 30 trades |
| L2 | <70% | **halve size portfolio-wide (A//2, B→min)** | per-strategy split: is it A, B, or both? regime vs execution decomposition; review costs | ≥80% for 60 trades → full size |
| L3 | <50% | **halt new entries** (manage exits only) | full review vs validation distributions; check for structural market change; paper-trade continues for data | ≥70% on 60 PAPER trades + written review → resume at half size |
| L4 | <0 (negative expectancy over 90) | halted (already at L3 en route) | treat as edge death; convene re-validation; business falls back to reserve + VALHALLA conservative plan | only via full re-validation battery equivalent to original (no shortcut) |

Per RAGNAROK: decay cannot blow accounts (P3/floors) — these levels protect the TIMELINE
and the verified track record's integrity.

## 5. OPERATIONAL RESILIENCE

- **Primary runtime: datacenter VPS** (Chicago/NY metro), NOT the home Mac. Home Mac =
  monitor + dev only. (Removes home power/internet as trading SPOFs.)
- **Warm backup VPS** (different provider/region): receives hourly `bot.db` snapshot +
  config; runs in monitor-only mode; promotion = manual one-command (<15 min RTO), RPO ≤1h.
- **Feeds**: Tradovate primary, Dukascopy secondary (both already in `paper_live.py`),
  cross-checked each session open; divergence >0.25% = yellow. TradingView MCP as tertiary
  manual sanity check.
- **Broker paths**: Tradovate API primary (MFFU), TopstepX (Topstep) — two independent
  stacks by construction. Last-resort manual path: broker mobile app flatten procedure
  printed in the runbook (target: flat in <5 min from page).
- **Copier**: Tradesyncer primary; fallback = bot places orders per-account directly
  (same engine, N adapters) — removes copier as hard dependency.
- **Disaster matrix**: broker fails → positions protected by server-side brackets, no new
  entries (fail-closed), page; VPS dies → dead-man page in ≤10 min, warm VPS promoted,
  worst case = miss a session (income, not loss); DB corrupt → restore last snapshot,
  reconcile vs broker fills (broker is source of truth); internet/power at home →
  irrelevant (VPS architecture); everything at once → mobile-app flatten + firms' own
  EOD floors cap the damage at known cushion levels.

## 6. HOSTILE AUDIT OF THIS DESIGN (and the fixes now embedded)

1. **The operator is the residual SPOF** (acknowledged since HADES). Mitigations: fail-closed
   defaults make inaction safe; everything pages TWO channels; weekly procedures are
   checklists, not memory. Residual: multi-month operator absence stalls the business
   (RAGNAROK already priced this); not fixable by software.
2. **The watchman needs watching**: dashboard/VPS self-reporting is circular → external
   dead-man's-switch (independent service) is the non-negotiable fix, included above.
3. **Tradovate is both MFFU broker AND copier substrate** — vendor concentration.
   Fix: direct per-account order placement fallback (no copier), plus Topstep on a
   disjoint stack.
4. **Threshold gaming/alert fatigue**: L1/yellow will fire in normal variance.
   Fix: tiered responses where only ORANGE+ demands action; monthly audit reviews
   false-positive rates and may recalibrate BANDS but never the FROZEN baselines.
5. **Config drift**: deploys can silently change frozen parameters.
   Fix: startup checksum of strategy + risk params against a signed reference; mismatch
   = refuse to trade (RED).
6. **CI theater** (observed: pytest collected 0): CI must fail when collection count
   drops below the known test count; signal-parity test is the merge gate.
7. **Single human review of BLACK recovery**: best-effort 2-person rule (operator +
   written checklist + 24h cooling period before re-arm when no second person exists).

## 7. PROCEDURES

**Deployment checklist (per release)**: all tests green AND collected-count == expected ·
signal-parity vs frozen reference passes · config checksum matches · paper-mode session
replay clean · SAFETY posture verified (`enabled=False` until go) · brackets verified
server-side on demo · rollback tag noted.

**Daily (≈10 min, after NY close)**: dashboard sweep (all panels green/yellow only) ·
confirm EOD flat on all accounts · reconcile bot fills vs broker statements (count + PnL) ·
cushion + P3 state per account · feed freshness + heartbeat log · acknowledge yellows.

**Weekly (≈30 min)**: rolling-90 expectancy/PF review vs bands · slippage and fill-rate
trend · copy-success summary · firm rule-page diff (MFFU + Topstep changelogs) · reserve
balance vs $6k · snapshot restore-test (1-command dry run) · payout requests per retention
policy.

**Monthly audit (≈2h)**: decay-monitor formal reading (sign the level) · live-vs-validation
distribution comparison appended to the verified-record file · DR drill in rotation
(feed failover / VPS promotion / mobile flatten — one per month) · false-positive review
of tripwires · account caps vs plan (MFFU $100k cumulative, transition countdowns) ·
VALHALLA gate checkpoints (anchor-investor pipeline, platform time-stamps current) ·
backup integrity verify · written 1-page state-of-the-business note.

---

*The goal is no longer finding edge. The edge is frozen. HEIMDALL exists so that the
only way this business dies is the one no system can prevent — and even then, on
purpose, with the operator watching it happen in green and yellow first.*
