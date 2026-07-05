# L1 — A-London Upsizing (KRONOS K6) — Profile A with London-sweep-only filter, upsized

**Status: WATCHED — NOT re-tested this sprint per no-dead-research rule.**

- **Prior test location**: `memory/tested-strategies.md` (KRONOS K6 entry); build at `backtests/ict-nq-framework/challenger/kronos_wave2_build.py`.
- **Years**: reproduces on 2019+ (N=266); 2026 YTD checked separately.
- **Headline numbers**: PF 1.691 reproduces on 2019+ (N=266), beats "A-rest" (Profile A ex-London) in 7/8 years. Fails at the pre-registered gate: expR +0.252R at hostile (2pt slip) costs vs. the required ≥+0.30R gate (recorded +0.358R baseline doesn't reproduce under hostile costs). 2026 YTD London PF 0.28 vs. A-rest PF 2.72 (sharp regime divergence).
- **Verdict: WATCHED (pre-registered hostile-cost gate failed, not an outright kill).** Winner-of-16-filters selection risk noted in the original register. Clean re-test possible on 2027+ data (fresh out-of-sample year) via the existing `kronos_wave2_build.py` harness — do not re-run before then.
