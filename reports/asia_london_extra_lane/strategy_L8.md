# L8 — M11: London Sweep Trigger (ict-nq-models-2-12 battery)

**Status: DEAD — NEVER QUOTE. Not re-tested this sprint per no-dead-research rule.**

- **Prior test location**: `memory/tested-strategies.md` (`ict-nq-models-2-12 | m11_london_sweep` row); results at `backtests/ict-nq-framework/out/models_battery.csv`.
- **Years**: NQ 5m 24h, 2019–2026.
- **Headline numbers**: PF 1.04 long-only, N=124 long, WR 49.2%, exp 0.064R. Killed alongside M3/M4/M5/M7/M12 in the same battery (M11 was the London-specific variant of the 9-model sweep-trigger family).
- **Verdict: DEAD (KILL, "marginal").** PF 1.04 sits well below the 1.15 bar and the trade count (124 over ~7y ≈ 0.34/wk) also fails this sprint's frequency floor.
