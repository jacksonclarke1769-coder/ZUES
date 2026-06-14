# MONDAY — First Session Runbook

Everything is integrated: frozen Profile A engine + ARES sizing + **D1c active filter
(real CERBERUS DriftGate)** + daily guard + kill switch + TradersPost bridge, on the
credential-free Dukascopy live feed. 209 tests green. This is how you turn it on.

## The honest status (read once)
- **Profile A is fully automated and D1c-filtered.** Profile B is not in the live engine
  yet (next build) — Monday is Profile A only (~22 of ~30 weekly points).
- **Monday = PAPER unless you complete Stage 2 first.** Live order-firing is hard-gated
  behind `bracket-verified.flag` — which you only create after one manual order proves the
  stop+target actually attach at Tradovate. Skipping that risks a naked auto-position. Do
  not skip it.
- **MFFU is semi-auto: you SUPERVISE the session.** The bot trades; you watch the account.

## ~20 min before 09:30 ET — preflight (one command)
```
cd ~/trading-team/bot/nq-liq-bot
python3 monday_preflight.py --account MFFU-50K-1 --tier 50K-conservative
```
Every line must be ✓ except the execution-mode block (PAPER ONLY is expected until Stage 2).
It prints the exact run command at the end.

## Option A — PAPER session (recommended for the first run)
Watch Profile A fire on live data, D1c gate it by drift, route to the bridge in dry-run —
zero account risk:
```
python3 auto_live.py --account MFFU-50K-1 --tier 50K-conservative --d1c-mode active-eval-filter
```
You'll see each signal, D1c KEEP/BLOCK, and the would-be webhook logged to
`out/ares/bridge_webhook_log.csv` + `out/ares/d1c_eval_log.csv`.

## Option B — LIVE session (only if Stage 2 is done)
First, ONE manual order during RTH, watching the chart, to prove the bracket attaches:
```
export TRADERSPOST_LIVE_URL="<your rotated webhook>"
python3 bridge_test.py --account MFFU-50K-1 --mode live --entry \
  --side long --qty 1 --price <live> --stop <live-65> --target <live+130> \
  --symbol MNQU2026 --confirm
```
Confirm in Tradovate that BOTH the stop and the target attached. Then, and only then:
```
touch evidence/approvals/traderspost-approved.flag
touch evidence/approvals/bracket-verified.flag
python3 auto_live.py --account MFFU-50K-1 --tier 50K-conservative \
  --d1c-mode active-eval-filter --live
```

## During the session (you, supervising)
- Watch the MFFU account. The ARES daily stop is −$700; if the real account approaches it,
  hit the kill switch (the bot's sim-PnL is a proxy, not the real fill — you are the backstop):
  ```
  python3 -c "from store import Store; Store().set_state(auto_live_kill='1')"
  ```
  That halts all new entries instantly. Clear it with `set_state(auto_live_kill='')`.
- D1c keep-rate should sit ~45–80% (it prints HEIMDALL status on stop). Far outside = flag it.
- The bot is flat by 14:30 ET and only trades 09:30–11:30 ET, max 2/day, one position at a time.

## After the session
- Review `out/ares/d1c_eval_log.csv` (allowed/blocked A trades) and the bridge log.
- If you passed the eval: `python3 ares_mode.py switch-funded MFFU-50K-1` (ends ARES → ZEUS
  funded survival, A2/B1 + P3). The attack ends; the business begins.

## Known limitations (honest, for after Monday)
1. Profile B live port (B2). 2. D1c runs on the 5m feed (validated on 1m — the keep-rate
monitor watches for drift). 3. Auto daily-stop from real fills needs TradersPost fill
read-back (today: operator-watched). 4. Basis between Dukascopy proxy and Tradovate futures
— Stage 2 calibrates it.
