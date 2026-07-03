# MONDAY 2026-07-06 — LIVE CUTOVER RUNBOOK

**Machine:** ZEUS v2026.07.02b (DLL re-lock) — A-only · Exit#3 · D1c ACTIVE_EVAL_FILTER ·
size-to-risk **$1,200/trade** · B OFF · momentum OFF · $550 daily stop.
**Account:** Apex **APEX-50K-EVAL-1** — real. Balance **$49,404.80**, cushion to floor **~$1,905**,
need **+$3,595** to pass, ~23 days left. **Never traded by Rev B — this is its first live session.**
**Certified:** pass 58.2% / bust 29.1% / expire 12.7% (1m-truth, DLL-honest).

> Pre-staged 2026-07-03 (holiday, markets closed). Everything below runs **Monday**. Read top-to-
> bottom once before you start. Do not improvise the order — the sequence exists for a reason.

---

## ⛔ HARD RULES (read every time)
- **Going live is `./go-live-recert.sh` ONLY.** Never hand-arm `--live`. Never trust a process
  started before 2026-07-02 (that is the STALE de-certified machine — kill it).
- **Read-back panel MUST be open + readable** before arming, or the equity seed is wrong and the
  risk gate sizes off a phantom cushion.
- **Supervise the first hour.** Eyes on the Tradovate panel. This machine has never placed a real
  Rev-B order.

---

## PHASE 0 — Pre-open (before 09:30 ET) · ~10 min

- [ ] **0.1 Rotate the Tradovate password** (still outstanding per recert). Update `.env`
      (`TRADOVATE_*`), confirm `env_loader` picks it up:
      `python3 -c "import env_loader,os; print(bool(os.environ.get('TRADOVATE_PASSWORD')))"` → `True`.
- [ ] **0.2 Verify the Apex trailing threshold** on the Apex dashboard: is it **$2,500 or $2,000**?
      Recert config assumes **$2,500**. If it reads **$2,000**, update
      `config.py` EVAL trail before arming (this changes the floor and the risk-gate math).
- [ ] **0.3 Feed Chrome up + logged in** (:9222). Verify live NQ price in the tab title:
      `curl -s http://127.0.0.1:9222/json | python3 -c "import sys,json;[print(t['title']) for t in json.load(sys.stdin) if t.get('type')=='page']"`
      → live `NQ1! <price>`. If "Sign in" → **operator signs in manually** (never enter creds via bot).
- [ ] **0.4 Open + PIN the Tradovate broker panel** inside that :9222 TradingView window
      (account-manager panel). This is what read-back reads. Confirm the account row shows
      **APEX...002 @ ~$49,404.80**.
- [ ] **0.5 Confirm holiday/calendar gate is clear** — Mon Jul 6 is a normal trading day
      (Jul 3 was the holiday). Preflight will block otherwise.

## PHASE 1 — Health check · ~2 min

- [ ] **1.1** `cd ~/trading-team/bot/nq-liq-bot && git log --oneline -1` → expect `2c5145d` (or later).
- [ ] **1.2** `pgrep -fl "auto_live.py"` → expect **NONE** (stood down). If anything from before
      2026-07-02 is alive, **kill it** — it is the stale machine.
- [ ] **1.3** `python3 -m pytest -q 2>&1 | tail -1` → **722 passed** (30s). Do not arm on a red suite.

## PHASE 2 — ARM LIVE · the one command · ~1 min

- [ ] **2.1** `./go-live-recert.sh`
- [ ] **2.2** Type exactly `GO LIVE RECERT` at the prompt (anything else aborts).
- [ ] **2.3** Watch `logs/live-recert.log` for the three confirmations:
      - `equity SEEDED $49,404.80` (seed matches the real panel — if it seeds a different number,
        **the panel wasn't readable — abort, fix 0.4, re-run**).
      - `read-back ... GREEN` (sentinel can see the broker).
      - `ARMED, live webhooks active` + `EXIT3` (right machine, right exit model).
      - `slip tripwire ON [alert]` (fill-quality watch armed — alert-only, cannot halt/flatten).
      - If **PREFLIGHT BLOCKED** → almost always feed RED / panel not open / dead-man not up. Fix
        the named item and re-run. A block is the system doing its job, not a failure.

## PHASE 3 — Bring the guardians up · ~1 min

- [ ] **3.1** Feed watchdog: `pgrep -fl feed_watch || nohup python3 feed_watch.py --heal > logs/feed-watch.log 2>&1 &`
- [ ] **3.2** Dead-man switch: `nohup python3 deadman_watch.py --live > logs/deadman.log 2>&1 &`
      (external flatten at 7 min silent, alert at 3 min).
- [ ] **3.3** Dashboard: confirm `zeus_server.py` is up → `/v3` Mission Deck shows **mode: LIVE**,
      account seeded, Profile B **OFF**.
- [ ] **3.4** `cat out/heimdall/heartbeat.json` → fresh `ts` (today), `mode: live`, `data_state`
      GREEN, recent `last_bar`.

## PHASE 4 — First-hour watch (the part that actually matters) · ongoing

- [ ] **4.1** Sit on the Tradovate panel through the **NY-AM window**. Profile A is NY-AM cash-only.
- [ ] **4.2** On the **first fill**, eyeball it against the log's expected entry. This is the
      **#1 unknown** going live — real fill quality vs the modeled level.
- [ ] **4.3** The **slippage tripwire is now armed in alert-only mode** (auto-armed by
      `go-live-recert.sh`). It watches every fill and **Telegrams** you on a breach — but in alert
      mode it **cannot halt or flatten**; you are still the decision-maker. Breaches also log to
      `out/exec/slip_halt_events.csv`. Spec: [docs/specs/slippage_tripwire_spec.md](docs/specs/slippage_tripwire_spec.md).
- [ ] **4.4** After a few fills: `python3 tools_exec_report.py` → read **mean/median/worst slippage
      (pts and R)** and **fill rate**. This is the single most valuable new number in the system.
      - **Green:** slippage mean < ~0.05R, fill rate high → the paper edge is real; let it run.
      - **Amber:** slippage 0.05–0.10R → keep supervising, note it, don't scale.
      - **Red:** slippage > 0.10R **or** miss rate > ~40% → **manually stop entries (do not flatten)**
        and re-cert size before continuing. The tripwire will have Telegrammed you at this exact
        threshold. Once you trust its numbers (~10 fills in), flip it to **halt mode** by relaunching
        with `--slip-mode halt` so it freezes entries itself in unsupervised windows.

---

## IF SOMETHING GOES WRONG

| Symptom | Do this |
|---|---|
| Read-back goes RED / panel collapses | Entries auto-halt (no flatten). Re-open+pin the panel, `/resume` to clear. Position sits on its brackets — safe. |
| Feed DATA RED | Check first: **market-closed vs real freeze** (see `feed_operations` playbook). If real, `feed_watch --heal` should self-heal via visibility-spoof keep-alive. |
| Fills clearly bad (slippage > 0.10R) | Manual halt: stop `auto_live`, let brackets manage the open position, run `tools_exec_report.py`, decide re-cert. Do **not** panic-flatten a healthy position over entry cost. |
| Daily P&L hits −$550 | $550 DailyGuard trips automatically. Done for the day. |
| Anything you don't understand | Stop arming. The cushion is $1,905. There is no trade worth guessing on. |

## END OF SESSION
- [ ] EOD flatten confirmed (auto, retries until ok).
- [ ] `python3 tools_exec_report.py` → log the day's slippage/fill numbers.
- [ ] Update the vault (Current State, daily log, handoff) per `Vault Conventions.md`, then
      `git add -A && git commit -m "session 2026-07-06: first Rev-B live cutover"`.

---
*Pre-staged 2026-07-03. Source of truth for the machine = repo `AGENTS.md`
§"ZEUS Production Machine v2026.07.02" + the handoff memory. On any conflict, the Obsidian vault
`~/Documents/Zues` Current State wins.*
