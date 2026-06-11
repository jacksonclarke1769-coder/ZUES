# NQ Liq-Session — Automated Bot + Dashboard

Fully automated trading bot for the **NQ Liq-Session** strategy on **Tradovate**, with a
live **dashboard** (eval tracker, daily-P&L calendar, equity curve, trade log, strategy state).

Strategy logic mirrors `strategies/active/nq-liq-session/NQ_LiqSession_Phased.pine`:
Asian-range break + FVG displacement + vol-expansion gate, **long-only**, one trade/day,
auto phase-switch **EVAL → FUNDED** on +$3,000.

```
EVAL phase   : fixed 30pt stop · entries 09:15–09:45 ET · ride to EOD · 1 NQ   (~69% pass / 8% bust)
FUNDED phase : structure stop · rr3 target · entries 09:15–11:30 · ride runners (PF 1.62)
```

## Layout
| File | Role |
|---|---|
| `config.example.py` → `config.py` | credentials + strategy/eval/safety params (config.py gitignored) |
| `tradovate_client.py` | Tradovate REST/WS: auth, contracts, bars, OSO brackets, flatten, positions |
| `strategy_engine.py` | live phased signal engine (mirrors the backtest, no lookahead) |
| `bot.py` | main loop: data → signal → order → risk/eval → persist; SIM + LIVE modes |
| `store.py` | SQLite store (trades, equity, daily P&L, state, events) |
| `dashboard_server.py` + `dashboard/` | FastAPI + UI |
| `seed_from_backtest.py` | populate the dashboard with backtest/paper data |

## Dashboard (real backtest data only)
```bash
pip install -r requirements.txt
python build_real_backtest.py     # runs the REAL backtest of the current optimized config
python dashboard_server.py        # http://127.0.0.1:8000
```
The dashboard shows **only actual backtest results** — every trade is a real historical trade
on its real date; the calendar shows the actual trades taken each day; pass-rates are the real
historical green-light-window statistics. Nothing simulated or random.

**Current optimized config** (what the backtest runs):
long-only · min_sweep 10 · cut Friday (PF 0.89) · cut 10:00-10:30 chop (WR 50%) · trail-50 · ride-EOD.

**Panels:** KPIs (PF/WR/net/maxDD), equity curve, daily-P&L calendar (real trades per day,
hover for detail), why-winners-win/losers-lose forensics, per-year robustness, pass-rate by
prop firm (static-DD clears 70%+), trade distribution, full trades table.

Rebuild after a strategy change: `python build_real_backtest.py` (wipes & repopulates from the real backtest).

## Going live (when you have the Tradovate API key)
1. `cp config.example.py config.py`, then fill `TRADOVATE`:
   - `name`/`password` — your Tradovate login
   - `cid`/`sec` — **the API key + secret** from Tradovate's API-app registration (https://trader.tradovate.com → Application Settings → API Access)
   - `app_id`, `device_id` — any stable strings
   - `account_spec` — your Apex eval account name/id
   - `env` — `"live"` for the Apex eval/funded sim accounts (they trade on the live host), `"demo"` for paper
2. Set safety in `config.py`:
   - `SAFETY["enabled"]=True` to allow orders; **`paper=True` keeps fills simulated even when connected** (recommended first run)
   - `require_greenlight=True` → only trades when the vol-gate is ON
   - `max_daily_loss` → hard daily kill-switch ($)
3. Dry-run connected but paper: set `paper=True`, run `python bot.py --live` → confirms auth, contract resolve, data stream, and signal logic place *simulated* orders.
4. Flip `paper=False` to send real OSO brackets. Start with `eval_qty=1` (1 NQ).
5. Run the dashboard alongside: `python dashboard_server.py`.

> The bot starts a **fresh $50k eval at first trade** in live mode and records the real account forward. The seeded demo data is only for previewing the dashboard.

## How it trades (per closed 5m bar)
1. Build the Asian range (18:00–02:00 ET) and the daily vol-gate (ATR14 ≥ SMA20).
2. In the killzone, if price **breaks & closes above the Asian high with an FVG**, arm a long.
3. Fill **market at the next bar's open**; attach a bracket (EVAL: 30pt stop, no target / FUNDED: structure stop + 3R).
4. Manage stop/target intrabar (stop-first); **flat by 15:55 ET**.
5. Update eval balance, peak, and the $2,500 trailing threshold (locks at $50,100). Auto-switch to FUNDED on +$3,000.
6. Kill-switch on daily-loss limit, bust, or green-light OFF.

## Dashboard
- **Eval tracker** — balance vs $53k target, distance to the trailing threshold, peak, live green-light.
- **Daily-P&L calendar** — month heatmap, $ earned/lost each day (hover for detail).
- **Equity curve** — balance + trailing-threshold line.
- **Strategy state** — phase, open position, today's Asian range, vol-gate ratio, day P&L, last price.
- **Trades table + event log** — every fill and decision.
- Auto-refreshes every 5s from the bot's SQLite store.

## Safety notes
- `config.py` holds secrets and is gitignored — never commit it.
- First live session: `paper=True`. Watch a full day, confirm signals/fills match expectation, then go real.
- The green-light routine (`/schedule`) is the macro gate; `require_greenlight` is the bot-level enforcement of the same vol-gate.
- This is a single-strategy bot on one account — size with the Apex trailing DD in mind (1 NQ eval, 1 MNQ funded).
