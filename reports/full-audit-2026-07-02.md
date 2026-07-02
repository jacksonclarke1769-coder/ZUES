# ZEUS FULL-SYSTEM AUDIT — 2026-07-02

Scope: backtest engines → Apex rule simulators → live runner → execution/read-back → feed/ops → live-vs-backtest parity.
Method: six independent hostile audit passes over the full repo + live logs + live SQLite journal, followed by
direct verification of the highest-stakes claims (code reads + an independent re-run of the fill simulator on the
real Databento data). Read-only — nothing in the bot was modified.

Verification note: the central backtest finding (F1) was independently reproduced by the auditor-of-record:
`b_events` re-run on `NQ_databento_1m_5y` gave n=1024, PF 1.270/+149.3R as-coded with 15.2% of wins booking on the
fill bar (1.5R target), and PF 1.637/+246.8R with 41.6% fill-bar wins at 1R target; deferring fill-bar target fills
→ PF 1.028 (+16.8R) and 0.915 (−45.2R) respectively. Matches the audit agent's numbers exactly.

---

## VERDICT (one paragraph)

The engineering discipline is real — signal causality is clean (0 parity mismatches re-verified across all three
engines), stops are adverse-first as believed, dedup/flatten/CONFIGLOCK/daily-guard persistence all verified
working, and the fail-closed philosophy held up in production last night. But three foundations are cracked:
(1) the fill simulator books limit-entry TARGET wins off the same bar's extremes — entry-vs-target look-ahead that
manufactures roughly half to two-thirds of the claimed R on both live profiles and mis-ranked the exit models;
(2) the deployed machine is not the certified machine (momentum lane permanently dead, A-stream generated with
different params than certified, D1c not in the certified numbers, modeled ledger tracks the wrong exit); and
(3) the risk layer watches a modeled world (daily stop retrospective, gates on a fresh-$50k modeled account,
read-back currently non-functional). Headline stats (A PF 1.46, B PF 1.20, 63.1% eval pass, $22.1k E[payout])
are unreliable until re-measured.

---

## TIER 0 — LIVE INCIDENTS (active right now)

### T0-1. The live session is read-back-HALTED; A/B will take zero trades until fixed
`logs/live-readback.log`: `TradingViewReadbackUnconfigured` on every 20s poll (x84+ and counting) — the Tradovate
account-manager panel is not readable in the :9222 Chrome (panel closed/collapsed, likely after a feed_watch tab
reload). Sentinel confirmed BLACK at poll 3 → FLATTEN + HALT. `halted` is sticky with **no reset path** (`/resume`
clears other flags but never `readback.halted`; `live_readback.py:146-151`, `auto_live.py:1073-1075`).
**Fix:** restore the panel (open account manager in the :9222 TV window, keep it pinned), restart the runner;
add `readback.reset()` to `/resume`; Telegram-alert on first BROKER_READ_FAIL and on any BLACK (today a halt is a
console print only).

### T0-2. The emergency-flatten signalId for APEX-50K-EVAL-1 is burned — next critical flatten is a silent no-op
`auto_live.py:691` calls `sender.flatten(a.account)` with no `reason` → deterministic sid; last night's spurious
flatten consumed it (ledger: `ZB-7a1a49050a68f4774b79`/`ZB-f7448ce761319dc2a6cd`, confirmed 22:03Z). Next BLACK
with a live position → "duplicate signalId — already confirmed" → no cancel, no exit, error swallowed.
**Fix (one line):** `sender.flatten(a.account, reason=f"readback_{int(time.time())}")` — the guardian already does
exactly this (`flatten_guardian.py:85`).

### T0-3. READ_FAIL and MISMATCH are conflated — a cosmetic panel failure market-flattens real positions
A panel that merely became unreadable triggers the same flatten as a genuine broker mismatch. At 21 MNQ that is a
forced market exit mid-trade on a DOM hiccup.
**Fix:** taxonomy split — READ_FAIL → halt entries + alert (no flatten); MISMATCH (panel read, disagrees) → flatten.

### T0-4. Friday 2026-07-03 is the observed Independence Day closure; feed_watch doesn't know holidays
`feed_watch.market_likely_open` (`feed_watch.py:37-51`) knows weekends/maintenance only → guaranteed heal-thrash:
2 tab reloads + `pkill` of the logged-in Chrome + relaunch, then HEAL EXHAUSTED (7 prior instances in the log).
Trading gates independently block the holiday (clean), but each Chrome kill risks the TV login and broker panel.
**Fix:** import `market_calendar.is_trading_day` into `market_likely_open`; add half-day awareness.

---

## TIER 1 — BACKTEST VALIDITY (the numbers the business is built on)

### F1. [CRITICAL — INDEPENDENTLY VERIFIED] Entry-bar target fills are look-ahead; headline stats are inflated
Every fill simulator starts the exit walk ON the fill bar and books the target off that bar's full high/low:
`exit_model_validate.py:89-105`, `apex_eval_deployed.py:124-132`, `bpartial_fidelity.py:96-121`,
`models/model01_sweep_mss_fvg.py:461-497`. These are RETEST-LIMIT entries — the favorable extreme of the fill bar
frequently prints BEFORE the limit fills. "Adverse-first" only covers stop-vs-target, not entry-vs-target.
Targets ≈ one 5m bar range, so the effect is huge:
- B single@1R: 41.6% of 1024 trades book the win on the fill bar. 5m as-coded PF 1.637/+246.8R → 1m-truth re-walk
  PF ~1.24/+109R (defer-bound 0.915).
- B single@1.5R: 1.270/+149.3R → ~1.11/+64.6R at 1m.
- A single@1R (the live exit): 24.7% of 748 trades book the win on the fill bar (+183.4R booked there). 5m 1.526 →
  ~1.13/+46.6R at 1m.
- A Exit#3 (the "PF 1.46"): 5m ~1.50 → ~1.21/+67.1R at 1m.
Fill-bar STOP hits are booked as losses (kept, pessimistic) — nowhere near offsetting the win-side inflation.
**Fix:** re-fill every trade at 1m inside the 5m windows (the 1m parquet is already loaded by `run_d1c_real`);
republish A/B PF, the exit ranking, and eval pass-rates. Treat 1m numbers as a ceiling (same ambiguity at 1m scale).

### F2. [CRITICAL consequence] The SINGLE_1R-over-EXIT3 certification is an artifact of F1 for Profile A
A 1R target is the most likely to sit inside the fill bar's range → single@1R gains the most phantom R. At 1m
truth the A ordering FLIPS: Exit#3 (~1.21/+67R) beats single@1R (~1.13/+47R). For B, 1RR stays ahead at 1m
(~1.24 vs ~1.19). The live default exit was certified on the biased convention.
**Fix:** rerun `tools_exit_final_compare.py` on 1m-truth walks with a pre-frozen held-out period before keeping
1RR as default. Do not flip anything on this audit alone — re-measure first.

### F3. [HIGH] Short-side MAE/MFE sign inversion in every B stream generator
`apex_eval_deployed.py:125-126` (same in `exit_model_validate.py:91`, `bpartial_fidelity.py:97-102`): for shorts,
`(entry - H[x]) * d` = `H - entry` → positive when under water → `min(mae, …)` never records real adverse
excursion, and winning shorts book phantom MAE. B is ~50% shorts (508/1024). The intraday-liquidation check
`bal + min(0, mae) <= thr` is fed garbage for every B short — pass-rates computed through this. (A-leg `mae_r` in
model01 is correct.)
**Fix (one line × 3 files):** short mae = `(H[x]-entry)*d`, short mfe = `(L[x]-entry)*d`. Rerun the EOD grid.

### F4. [HIGH] The joint intraday breach at 21 MNQ was never measured
`apex_eval_eod.py:47` marks each event's MAE alone; three lanes simultaneously open are never jointly marked.
The corrective harness EXISTS (`apex_joint_bar_sim.py`) but no JOINT results appear anywhere in reports/evidence.
63.1%/57.5% is the optimistic edge of an unmeasured bracket — acknowledged in docstrings, never quantified.
**Fix:** run `apex_joint_bar_sim.py`, record the bracket in `apex_validation.json`. The sweep already contains
smaller configs (8/4/5, 6/3/4) if the joint number sags.

### F5. [HIGH] Funded payout economics use pre-4.0 rules — E[payout] materially inflated
Sims pay $2k×5 then $4k/month FOREVER (`apex_funded_*.py`, `tools_exit_final_compare.py`). Apex 4.0 (2026,
help-center-derived): 50K EOD PA ladder $1.5k/$1.5k/$2k/$2.5k/$2.5k/$3k, **max 6 payouts ≈ $13k lifetime, then the
PA closes**. Claimed $22.1k/account exceeds the ceiling. Also: the 50% consistency-since-last-payout gate is coded
as a stale 30% constant and NEVER called by any payout sim; the 5×$250 qualifying-day rule is unmodeled; Apex's
native $1k daily loss limit is unmodeled (the certification's own census shows ~97 days with troughs ≤ −$1k at
deployed size). **Verify exact rules against the live contract** (account vintage ~June 2026 ⇒ 4.0), then rebuild
funded economics + the weekly-buy cadence math. Same-day empirical check: the live account displays its trailing
threshold — one glance settles $2,000-vs-$2,500 PA trail (S1).

### F6. [MEDIUM] Methodology gaps in the exit gate
No held-out sample in `tools_exit_final_compare.py`; `exit_model_validate.py:308-316` ranks variants BY the OOS
column (OOS was consulted → no longer OOS). The adversarial suite reuses the same biased generators (F1 is
common-mode, undetectable by it). `apex_montecarlo.py:76-77` clamps every losing day to exactly −$550 (live lets
the tripping trade's full loss land: real worst days −$3.9k to −$4.8k) → tail clustering understated; also stale
`EVAL_PASS=0.575` hardcode. Momentum costs: flips counted as 1 contract, zero slippage, close-fills.

---

## TIER 2 — THE DEPLOYED MACHINE ≠ THE CERTIFIED MACHINE

### D1. [HIGHEST parity impact] Momentum lane (mm6) is certified-in but live-DEAD
Warmup feeds only the A engine (`auto_live.py:773-776`); `m_engine` needs 52 distinct dates of buffer
(`profile_momentum_engine.py:88-90`), gets bars only live, `snapshot()/restore()` never called, sessions relaunch
daily → permanent `momentum_warmup` (78 skips/day, every live day, in the ARGUS logs). So the live book is
effectively A10/B5/**mm0** — a config with NO printed pass-rate (no 10/5/0 row in `apex_eval_eod_databento.py`).
Knock-on: the EOD flatten was deferred 14:30→15:30 FOR momentum — live A/B carry +60min of uncertified exposure
for a lane that never fires. Also (latent): the momentum executor was wired with `entry_gate=None` captured by
value (`auto_live.py:614-644`, rebind at :823 comes too late) → if it ever DID warm up, it bypasses
armed/GREEN/holiday/dead-man/readback-halt gates; and it never registers with the read-back sentinel → its first
fill would look like an ORPHAN → spurious BLACK flatten.
**Fix:** either warm B+M engines from `feed.history()` (+persist M snapshot; ~5 lines) AND fix the gate binding
AND register M with the sentinel — or drop `--profile-momentum` and re-certify at mm0 with the 14:30 flatten
restored. Decide honestly; don't run a phantom lane.

### D2. [HIGH] Live A signals come from different params than the certified 1RR stream
Certified single1 regenerated the trade list with `rr=1.0, partial=None, slip_ticks=8` (`exit_model_validate.py:48`);
exits change the no-overlap scanner windows (`model01:324`). Live uses the PROFILE_A rr=2.0/partial stream
(`strategy_engine_profileA.py:20-22`) and swaps only the order target to +1R (`auto_live.py:264-266`); live slip
default is 2 ticks vs certified 8 → different entry price, R, and target for every trade. Measured divergence:
1781 vs 1701 trades, 109 certified-only + 29 live-only (~7.8%).
**Fix:** when EXIT_MODEL=SINGLE_1R, run the engine with the certified single1 params — or re-certify the deployed
hybrid. (B's coupling is clean: live `_single1r` B geometry ≡ certified walk. Verified.)

### D3. [HIGH] The modeled P&L ledger — input to the daily stop — models the WRONG exits
A: `PaperTracker` books Exit#3 blends (tp1@1R half, tp2@2R; `paper_live.py:200-276`) while live exits full @+1R.
B: `b_tracker.on_signal(..., partial=False)` under `_single1r` → models single 1.5R target while live TP is +1R
(`auto_live.py:389`, `profile_b_tracker.py:110`). The $550 daily stop, dashboard, journal and Telegram all run on
P&L that is neither real nor the right model. `decision_log.py:21` also hardcodes
`EXIT_MODEL="EXIT3_FIXED_PARTIAL"` into every audit row of a SINGLE_1R session.
**Fix:** make both trackers exit-model-aware; set decision_log from the resolved model.

### D4. [MEDIUM] Daily-stop semantics differ from certification
Backtest: whole trade P&L lands at fill-time; later same-day entries dropped once cum ≤ −$550
(`apex_eval_deployed.py:173-186`). Live: accrues only on RESOLVED modeled trades, then blocks entries and
guardian-flattens open positions (unmodeled). Live can enter trade #2 while a fatal loser is still open; live cuts
runners the model let finish. Backtest momentum P&L lands as one ~16:00 event (can't be halted intraday).

### D5. [MEDIUM] D1c ACTIVE_EVAL_FILTER runs live but is absent from every certified pass/payout stream
Live blocks ~38% of A entries via DriftGate (`auto_live.py:213-229`); the 57.5/63.1% and E[payout] numbers were
computed on the UNFILTERED A stream (grep: no d1c/drift in any certification harness). `run_d1c_real.attach_drift`
exists — merge and rerun.

### D6. [MEDIUM] Live-only MFFU gate on the wrong firm's rules blocks certified trades
`bot.py:126` gates every A entry via `config.EVAL` = MyFundedFutures Core 50K trailing + `max_trades_per_day=2` on
MODELED equity. The account is Apex; the certification has no such gate. Real instance 06-29
(`too_close_to_floor` rejection). Either encode the real Apex EOD rule or remove — but note it's currently the
ONLY pre-trade floor protection (see R2 before deleting).

### D7. [MEDIUM] Order lifecycle unvalidated: late placement, no TTL, no max-hold
Certified: A fills on touch intrabar; B retest must fill within 6 bars or no trade; A max hold 48 bars, B 24.
Live: limit posted after 5m close (+1m agg +poll ≤60s), NO expiry, NO cancel until EOD flatten; B can fill outside
its certified window; unfilled limits rest all session (model/broker divergence + orphan-fill risk); no max-hold
exit (positions ride to 15:30). Fix: order TTL via existing `build_cancel` when the tracker expires a watch; B
market-exit at fill+24 bars.

---

## TIER 3 — RISK ARCHITECTURE (what can bust the eval independent of edge)

### R1. [SEV-0 class] The $550 daily stop is retrospective and blind to concurrent open risk
Nothing books until an exit resolves; A(10)+B(5) can be open together (M too if ever warmed); the overlap gate
never resizes A/B; `validate_size()` is never called by auto_live; A's stop is UNCAPPED (real 06-29 signal:
137pt → −$2,746 for one trade; the 80pt cap exists only as an observe-only ShadowOverlay). Quantified concurrent
bracket risk ≈ −$3,300 (A+B) before slippage vs ~$1.4-1.9k real remaining cushion. One coordinated adverse morning
inside the code's rules busts the eval; the stop only blocks the NEXT entry after damage books.
**Fix (the single most protective change):** pre-order concurrent-exposure check —
`sum(open risk_usd) + new risk_usd ≤ min(daily_stop_remaining, real_cushion_buffer)`; all inputs already exist in
the payload metas (`bridge_traderspost.py:98-101`). Plus: promote the 80pt A stop-cap from shadow to enforced
(research already validated ≤80pt as the safe overlay), or size A down when stop_pts × qty × $2 > buffer.

### R2. [SEV-0 class] Every equity-referencing gate watches a modeled account that resets to $50k on restart
`auto_live.py:711` builds a fresh `PaperLiveRunner` (never `.restore()`); `too_close_to_floor` and the P3 brake
(which IS wired — `auto_live.py:122,173-182,233,716` — contrary to memory) always see a full $2,000 cushion. Real
cushion is ~$1.5k. The only real-balance check is the sentinel's BALANCE_FLOOR — reactive AND currently dead (T0-1),
and it silently skips when `balance()` returns None (equity regex requires decimals; comma-only renders → None →
check inert, fail-open: `readback_tradingview.py:47-49`, `live_readback.py:122`).
**Fix:** seed modeled state from the panel equity (or operator prompt) at launch; make BALANCE_FLOOR fail-closed
after N consecutive None reads; loosen the equity regex.

### R3. [SEV-0 class] No kill-switch exists outside the bot process
FlattenGuardian is a daemon THREAD inside auto_live. Bot dies with 21 MNQ open → heartbeat stops → dead-man RED →
consumed by NOTHING that acts (feed_watch only logs; zeus only displays; neither imports telegram). Operator's
alert is the ABSENCE of an hourly ping (up to ~60min of silence). No EOD flatten, no daily stop; broker-side
brackets are the only protection (momentum entries would carry stop-only, NO target: `build_momentum_entry`).
**Fix:** standalone `deadman_watch.py` (or extend feed_watch, which already computes dm): on RED during market
hours → Telegram immediately → after N min fire `ops_flatten` via its own BridgeSender. Plus launchd units
(KeepAlive) for all four processes + `caffeinate -dims`; everything is currently hand-launched and dies on reboot
or Chrome auto-update (updater agents ARE installed).

### R4. [HIGH] Sentinel accounting: `expected` never decrements on exits
`on_partial_or_exit` has ZERO production callers; `on_flat` only at day roll. Bracket exits leave `expected` stale
all day → concrete false BLACK: A long 10 stops out (expected stays +10), B shorts 5 → expected +5 vs broker −5 →
DIRECTION_MISMATCH → auto-flatten of a healthy B trade. Stale positive expected also masks same-sign orphans.
**Fix:** hook `_record_resolved`/`b_tracker` resolutions/guardian flatten to `on_partial_or_exit`; register
momentum entries.

### R5. [HIGH] No positive fill confirmation — the phantom-trade class is NOT closed
`on_entry` fires at webhook-SEND time; an unfilled entry is only ever ORANGE (never halts, never alerts); modeled
P&L and the daily stop still run on assumed fills; the designed `order_filled(signal_id)` is dead code and CANNOT
work (TradersPost doesn't propagate extras.signalId into Tradovate order ids). The 06-30 B 5-MNQ send (http 200)
has NO fill record anywhere — whether it filled is unknowable from the bot's own records (S4: check Tradovate fill
history for 06-30).
**Fix:** positive confirmation loop — after send, require the broker net delta within the retest window; confirmed
→ mark filled (tracker + daily stop count REAL fills); not confirmed by window end → `build_cancel` + mark rejected.

### R6. [MEDIUM] Webhook retry can double-send after a timeout
`bridge_sender.send:117-126` retries on RequestException including read-timeout-after-accept; TradersPost has no
native dedup (`bridge_traderspost.py:78` comment). Flaky connection → possible 2× bracket position.
**Fix:** on timeout, don't blind-retry an entry — read-back position check first.

### R7. [MEDIUM] EOD flatten is fire-once even on FAILURE; cancel-then-exit can strip brackets then fail
`scheduler.py:97-112` marks fired when due, not when ok. TradersPost down at 15:30 → no retry that day → position
rides into the close (Apex requires flat by 4:59pm ET). Cancel succeeded + exit failed = position with NO stop and
NO target. `flatten.py`'s EmergencyFlatten verify-and-reissue engine exists but isn't wired to the live path.
**Fix:** mark fired only on ok=True; retry each guardian tick; escalate to Telegram; verify flat via read-back.

### R8. Assorted confirmed
- Plaintext Tradovate password in `config.py:7-17` (gitignored but live) — ROTATE; move to env.
- The permanent `controlled-tv-full-live-test-approved.flag` bypasses the strongest preflight gate on every launch
  (the gate that hard-blocks TV feeds as "not unattended-grade") — make it single-use or TTL.
- `FEED_DEGRADED.flag` is write-only theater (no reader in the repo).
- zeus dashboard's Heimdall alert engine (`feed dead with position open`) is vacuous — its store keys are written
  only by the demo seeder; `has_open_position` never passed.
- `TV_REALTIME_CONFIRMED=1` is a permanent env attestation, not a check (mitigated: logged-out 10-min delay pins
  the feed RED → fail-closed to missed sessions).
- Sep roll window (~Sep 10-18) unmanaged: feed NQ1! vs order bare-root MNQ; TV and TradersPost roll on different
  days → bracket prices off by the calendar spread (~75-150pt) in one direction. Calendar-pin the roll week or set
  explicit TP_SYMBOL=MNQU2026 + assert chart contract.
- Half-days hardcoded for 2026 only (`scheduler.py:32-35`); January manual dependency on the money path.
- `day_entered_pnl` doesn't filter mode → a same-day paper run under the live account id would pollute the live
  daily stop (S1; one-line fix).
- TradersPost `cancel` action marked "CONFIRM" in code — verify once in Tradovate order history that cancels
  actually cancel (S2; flatten correctness depends on it).
- Daytime Jul 1 session ran `--eyes-confirmed-blind` (override working as coded; noted for the record).

---

## VERIFIED CLEAN (credit where due)

- Signal causality: sweep/MSS/OTE decided on closed bars, fills strictly after signal bar (A, B, momentum);
  momentum sigma/trend `shift(1)`; HTF levels merge_asof(backward) with confirmation-deferred swings.
- Stop-vs-target adverse-first: genuinely implemented everywhere, both directions, including fill bar.
- Parity re-verified TODAY: A 71/71, B 3173/3173, momentum 94,344 bars — 0 mismatches each (for the params each
  stream uses — see D2).
- Data: Databento 1m complete (0 missing weekdays; holiday/half-day anomalies legitimate), UTC→ET DST-safe,
  5m boundaries identical live (Bar5Aggregator floors to :00/:05, acts only on closed buckets) vs backtest
  resample(label=left, closed=left).
- EOD eval rule shape (threshold at close, ratchets on EOD highs, lock at start+$100, intraday downside
  liquidates) matches the operator-confirmed Apex EOD description.
- MC correlation: whole-day block bootstrap of the merged A/B/M stream — same-day cross-lane correlation preserved.
- CONFIGLOCK fail-closed (SAFE_FALLBACK decoupled — the earlier fail-open is truly fixed); EXITLOCK entries-only;
  routing-integrity guard; instance flock; deterministic signalId dedup within the bot; restart cannot re-fire old
  signals; DailyGuard state persisted per (account, ET-day) — no restart bypass of the stop itself.
- EOD guardian: wall-clock, feed-independent, restart-persisted, fresh timestamped reasons, fired clean 3/3 live
  days; brackets server-side in ONE payload (stop+target verified keys, bracket-verified.flag).
- Journal/ledger hygiene: rejected trades excluded from day P&L and dashboards; B tracker restart-idempotent;
  86% dashboard figure retired with provenance (now 60 w/ root-cause note); atomic heartbeat writes.
- The sentinel's fail-closed philosophy WORKED in production last night (halted all entries on unreadable broker
  — costly, not dangerous; the defects are in taxonomy/reset/coverage, not the principle).

---

## WHAT THIS MEANS FOR THE BUSINESS NUMBERS

- A PF 1.46 / B PF 1.20 / 1RR eval 63.1% / E[payout] $22.1k: all unreliable pending the 1m re-fill (F1), sign fix
  (F3), joint sim (F4), and 4.0 payout rebuild (F5). Best current estimates from the 1m-truth re-walk: A ~1.13-1.21
  PF (Exit#3 > 1RR for A), B ~1.11-1.24 (1RR still best for B), eval pass materially below 63.1%, funded payouts
  capped ≈ $13k/PA lifetime.
- The deployed live book is A10/B5/mm0 + D1c — a configuration whose pass-rate was NEVER printed. The honest next
  number: rerun `apex_eval_eod_databento.py` with 1m-truth fills, MAE sign fix, D1c attached, mm0 (or fixed mm6),
  exit-time daily-stop accrual, joint intraday marking, and the $1k DLL clamp.
- The edge may still be real (signal causality is clean; the defer-bound B@1.5R is +16.8R ≈ breakeven, and the 1m
  walks are positive) — but it is THIN, and at 21 MNQ the concentration risk (R1) is not paid for by the measured
  edge until re-certification says otherwise.

## PRIORITIZED FIX PLAN

**Before the next live entry (operator decision whether to trade at all before re-measure):**
1. T0-2 one-line flatten-reason fix. 2. T0-1 panel restore + `/resume` reset + Telegram on BLACK/READ_FAIL.
3. T0-3 taxonomy split. 4. R1 pre-order exposure check + enforce the 80pt A stop-cap. 5. R2 seed real equity.
6. D1 decision: mm0 (drop flag, restore 14:30 flatten) until warmup is engineered. 7. R8 rotate the password.

**This week (re-measurement — the actual truth of the business):**
8. F1 1m re-fill of every trade → republish PF/pass-rates. 9. F3 sign fix (3 files). 10. F2 rerun exit gate on 1m
truth w/ pre-frozen holdout (decide 1RR-vs-EXIT3 per profile — likely split: EXIT3 for A, 1RR for B).
11. F4 joint sim + $1k DLL clamp → record bracket. 12. F5 funded economics on 4.0 rules (+ read the live trailing
threshold off the dashboard to settle $2.0k-vs-$2.5k). 13. D5 attach D1c to the certified stream. 14. D2/D3 make
live params + trackers match whatever the re-certification picks.

**Structural (before scaling / before funded):**
15. R3 external dead-man flattener + launchd + caffeinate. 16. R5 positive fill confirmation + order TTL (D7).
17. R4 sentinel exit-awareness + momentum registration. 18. R6/R7 webhook timeout + flatten retry semantics.
19. Sep roll runbook (TP_SYMBOL pin). 20. Retire the permanent controlled-test flag; wire FEED_DEGRADED + zeus
Heimdall store keys.

## IMPROVEMENTS (the honest list)

No new alpha was found, and none is claimed. The genuine improvements available are:
(1) the risk fixes above — R1/R2 convert the daily stop from retrospective to prospective and are worth more to
eval survival than any strategy tweak; (2) exit-model re-selection per profile on clean 1m fills (likely EXIT3 for
A / 1RR for B — a real, measurable improvement over the current uniform 1RR IF it survives re-measurement);
(3) D1 (warm the momentum lane properly OR stop paying +60min of A/B exposure for a dead lane — either is an
improvement over the current state); (4) possible size-down at eval per the joint sim's bracket (the 8/4/5 and
6/3/4 rows already exist to compare against 10/5/6 under honest marking).
