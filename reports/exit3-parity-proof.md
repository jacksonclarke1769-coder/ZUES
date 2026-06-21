# EXIT3 Parity Proof
_2026-06-21 · `tools/check_exit3_parity.py` · the $1,400 trade (short 3 MNQ, entry 30654.83, stop 30771.50, target 30421.49)_

| Model | P&L (3 MNQ) |
|---|---|
| Single-target full-qty @ 2R (LEGACY, retired) | $+1,400 |
| **Exit #3 integer 1@1R + 2@2R (OFFICIAL)** | **$+1,167** |
| Exit #3 fractional 1.5/1.5 (backtest) | $+1,050 |
| **LIVE split payload full-win (sum of legs)** | **$+1,167** |

Legs: `entry_tp2 = 2 @ 2.0R ($+933)` + `entry_tp1 = 1 @ 1.0R ($+233)` = **$1,167**

- ✅ live payload **==** Exit #3 integer — **PASS**
- ✅ live payload **!=** single-target ($1,400) — **PASS**

The live bridge now resolves to the same value the paper SimBot computes ($1,167). The integer 1/2
split is ~+11% vs the backtest's fractional 1.5/1.5 ($1,050) — the closest live-implementable form,
documented as the official live model. **The $1,400 single-target figure is no longer produced.**

**PASS.**
