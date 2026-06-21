# EXITLOCK — Single-Target (LIVE) Backtest & Exit #3 Comparison
_2026-06-21 · research only · 12 months · 3 MNQ · D1c active · −$700 daily stop · ~$6/trade cost_
_Engine: `backtests/ict-nq-framework/_exitlock_single_target.py` (both models bar-walked from the same 5m data, same fills)_

## What was tested
The **exact current live bridge model**: Profile A, full 3 MNQ → ONE 2R target, full 3 MNQ → ONE
stop, no TP1, no partial, no breakeven, no trailing. Compared head-to-head against the **validated
Exit #3** (50% @ +1R, 50% @ +2R) on the identical signal set and fills.

## Phase 3 — $1,400 reconstruction (locked in code + test)
risk 116.67pt · reward 233.34pt · **RR 2.00**

| Exit assumption | P&L (3 MNQ) |
|---|---|
| **Full 3 @ 2R (single-target / LIVE)** | **+$1,400** ✅ matches |
| Exit #3 integer (1@1R + 2@2R) | +$1,167 |
| Exit #3 fractional (1.5/1.5) | +$1,050 |
| 2@1R + 1@2R | +$933 |
`trade_results.pnl_from_r` solved ⇒ result_r = **2.0 on full 3 contracts**. The $1,400 is the
single-target model, not Exit #3. (Tests `test_exitlock.py::test_*pnl*` lock all four.)

## Phase 4/5 — head-to-head (last 12 months)
| Metric | Exit #3 (validated) | Single-target (LIVE) | Read |
|---|---:|---:|---|
| Trades | 101 | 101 | same signals |
| Win rate | 54% | 56% | ~tie |
| **Profit factor** | **2.87** | 2.39 | Exit #3 better |
| Expectancy R | +0.46 | +0.51 | single slightly higher |
| **Net $ (3 MNQ)** | +$18,356 | **+$20,448** | single +$2,092 |
| Avg win | +$513 | +$617 | single bigger wins |
| **Avg loss** | **−$214** | −$334 | single −56% bigger losses |
| Worst trade | −$1,284 | −$1,284 | same |
| Best trade | +$1,424 | +$1,623 | single bigger |
| **Max drawdown** | **$1,486** | **$2,231** | single **+50%, EXCEEDS $2k buffer** |
| Max consec losses | 7 | 7 | same |
| Daily-stop days | 2 | 2 | same |

### Yearly / trailing R
| Window | Exit #3 | Single |
|---|---:|---:|
| 2025 | +28.1R | +34.9R |
| 2026 | +18.6R | +16.3R |
| last 3mo | +10.0R | +6.4R |
| last 6mo | +20.4R | +19.1R |
| last 12mo | +45.5R | +50.7R |

### Eval survival (MFFU 50K, $2k EOD trailing)
| | Breach? | Passed | **Min cushion** | End |
|---|---|---|---|---|
| Exit #3 | No | 2025-09-16 | **$270** | $68,356 |
| Single-target | No | 2025-09-10 | **$32** | $70,448 |

## Verdict on the single-target model
**Higher return, materially higher risk — and it breaches the eval risk ceiling.**
- It makes ~+$2k more over 12mo with a slightly higher expectancy and win rate.
- **But its max drawdown is $2,231 — it EXCEEDS the $2,000 eval trailing buffer.** Exit #3 keeps max
  DD at $1,486, *under* the buffer.
- On this one historical path it survived by **$32** of cushion (luck — the big DD landed after the
  floor had locked at breakeven). A max DD above the buffer means a slightly different start date /
  sequence **breaches**. That is not eval-safe on a robustness basis.
- Bigger average losses (−$334 vs −$214) because there is no +1R banking to cushion a reversal: a
  trade that runs +1.9R then reverses is a **full −1R** live, vs ~0R under Exit #3.

**Conclusion:** single-target is a "more money, more variance" profile that **violates the $2k-buffer
DD ceiling the eval is built around.** It is NOT validated-safe for the eval despite the higher raw
return. The validated, buffer-respecting model is Exit #3.
