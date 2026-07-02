# TASK: Z — Profile A V2: HTF-alignment skip filter [PENDING operator approval + paper-forward gate]

ROLE: Sonnet implement (AFTER operator approval; deploy only after paper-forward confirmation)
DE-CERTIFIES: yes (entry filter change — full re-certification included below)

## Finding (tools_a_v2_score.py + follow-up cells, 2026-07-02)
V2 score research: the ONLY holdout-surviving component cluster is HTF trend alignment
(EMA(20)-slope sign on 15m/1h/4h vs trade direction; rho +0.15..+0.36 in BOTH eras). Counter-HTF
trades (alignment sum <= -2; 77/435 = 18%) have NEGATIVE expectancy in BOTH eras (WR ~32%, expR
-0.12/-0.17). Mechanism: Profile A is a sweep-reversal structure — fading a sweep against the
higher-timeframe trend fights the tape. This also explains the confluence paradox (the old score's
premium/discount and displacement bonuses systematically award counter-trend entries).

SKIP rule (drop trades with htf15+htf1h+htf4h <= -2), rev-b machine, DLL-honest:
  * stream: WR 58.6 -> 64.2% (IS 62.2 / HO 68.4), PF 2.31 -> 2.7/3.7, netR +184 -> +194,
    every year positive (worst 2024 PF 1.79)
  * eval: pass 58.2 -> 60.7, bust 29.1 -> 22.1, expire 12.7 -> 17.2, median 11d; IS and HO both up.

## Gates before implementation
1. OPERATOR approves the change in principle.
2. Caveat acknowledged: the holdout was OBSERVED during component analysis (semi-blind result).
   Deployment therefore requires a PAPER-FORWARD confirmation window (>= 20 A signals with the
   filter shadow-logged agreeing with backtest classification) before live arming.

## Scope (when activated)
- Live: compute EMA(20) slope signs on 15m/1h/4h aggregates of the live 5m feed at signal time;
  skip A entries with alignment sum <= -2. Shadow-log the score for every signal (ARGUS field).
- Parity test: live HTF classification == backtest classification over full history (0 mismatches).
- Full re-certification via the committed harnesses; apex_validation.json entry
  (candidate numbers above); AGENTS.md rev-c lock on operator sign-off.

## Files forbidden until activated: ALL (parked decision).
