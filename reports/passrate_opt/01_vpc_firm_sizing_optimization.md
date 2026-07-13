# VPC eval PASS-RATE optimization — FIRM x SIZING (honest sim)

**Research / sim measurement ONLY. READ-ONLY bot strategy code (imports only). Writes confined to `research/passrate_opt/` + `reports/passrate_opt/`. Nothing armed. LIVE HOLD remains in force.**

- Harness: `research/passrate_opt/vpc_firm_sizing.py` · JSON `reports/passrate_opt/01_vpc_firm_sizing.json`
- Determinism md5 `9d91102cd9a26e5ecab8d050b8e631b9` (identical over two runs).
- Data: Databento NQ 1m->5m RTH, window **2022-01-01->2026-06-22** (data end 2026-06-22).
- Engine: fork_b VPC builders (import) + tools_account_size_research.day_rows (import) + parametrized per-firm eval rule (this file)
- ARES self-imposed daily stop **$550** held IDENTICAL across firms; profit target **$3000** (50K, UNVERIFIED per firm).

## (a) Fidelity canary

VPC standalone Apex-50K $600/cap-3 through this engine → **PASS 12.6% / BUST 3.6% / EXPIRE 83.8% / median 19d / 1.77 tr/wk** — EXACTLY reproduces the established honest baseline (12.6 / 3.6 / 83.8 / 19d). Engine faithful; only the per-firm eval RULE is re-implemented on top of the same VPC events + certified day-collapse.

## FIRM RULES MODELED (all $ UNVERIFIED — no `reports/cross_firm/00_firm_rules_2026.md` in repo)

| firm | DD archetype | DD $ | DLL | time | consistency | min days |
|---|---|---:|---:|---|---:|---:|
| Apex50K | EOD-trail | $2500 | $1000 | 30-day | — | 1 |
| Topstep50K | EOD-trail | $2000 | none | unlimited | 50% | 5 |
| MFFU_Builder | EOD-trail | $2000 | none | unlimited | — | 2 |
| Bulenox_EOD | EOD-trail | $2500 | $1100 | unlimited | — | 1 |
| ETF_Static | STATIC | $2000 | none | unlimited | — | 5 |
| Tradeify_Sel | EOD-trail | $2000 | none | unlimited | 40% | 3 |

*Unlimited firms:* every trading day is an eval start; a start unresolved by data-end is **CENSORED** (NOT a fail). `pass_resolved% = passes/(passes+busts)` estimates eventual-pass for a start with full runway.

## (b) Full firm x sizing grid

### Apex50K — 30-DAY EXPIRE (trail $2500)

| bud/cap | PASS% | BUST% | EXP/CEN% | passRes% | med | p25-p75 | tr/wk |
|---|---:|---:|---:|---:|---:|---:|---:|
| $600/cap3 | 12.6 | 3.6 | 83.8 | 77.8 | 19 | 11-25 | 1.77 |
| $600/cap4 | 14.9 | 7.7 | 77.4 | 65.9 | 17 | 9-23 | 1.77 |
| $600/cap6 | 16.2 | 9.0 | 74.9 | 64.3 | 16 | 8-22 | 1.77 |
| $600/cap8 | 16.4 | 10.3 | 73.3 | 61.5 | 16 | 8-22 | 1.77 |
| $600/cap10 | 16.4 | 10.3 | 73.3 | 61.5 | 16 | 8-22 | 1.77 |
| $900/cap3 | 16.7 | 10.8 | 72.6 | 60.7 | 18 | 14-24 | 1.77 |
| $900/cap4 | 21.5 | 19.7 | 58.7 | 52.2 | 15 | 8-20 | 1.77 |
| $900/cap6 | 26.4 | 30.8 | 42.8 | 46.2 | 15 | 8-21 | 1.77 |
| $900/cap8 | 27.4 | 32.6 | 40.0 | 45.7 | 14 | 7-20 | 1.77 |
| $900/cap10 | 28.2 | 32.8 | 39.0 | 46.2 | 14 | 7-20 | 1.77 |
| $1200/cap3 | 16.7 | 10.5 | 72.8 | 61.3 | 18 | 13-24 | 1.77 |
| $1200/cap4 | 23.3 | 23.8 | 52.8 | 49.5 | 15 | 8-20 | 1.77 |
| $1200/cap6 | 32.1 | 35.1 | 32.8 | 47.7 | 13 | 6-21 | 1.77 |
| $1200/cap8 | 35.1 | 38.7 | 26.2 | 47.6 | 13 | 5-20 | 1.77 |
| $1200/cap10 | 35.9 | 39.7 | 24.4 | 47.5 | 12 | 5-20 | 1.77 |
| $1500/cap3 | 17.4 | 9.7 | 72.8 | 64.2 | 17 | 9-23 | 1.77 |
| $1500/cap4 | 24.6 | 23.8 | 51.5 | 50.8 | 15 | 8-20 | 1.77 |
| $1500/cap6 | 35.9 | 38.2 | 25.9 | 48.4 | 12 | 6-21 | 1.77 |
| $1500/cap8 | 36.9 | 43.3 | 19.7 | 46.0 | 11 | 2-18 | 1.77 |
| $1500/cap10 | 36.9 | 45.6 | 17.4 | 44.7 | 9 | 2-18 | 1.77 |
| $2000/cap3 | 17.4 | 9.7 | 72.8 | 64.2 | 17 | 9-23 | 1.77 |
| $2000/cap4 | 24.4 | 23.6 | 52.1 | 50.8 | 15 | 8-20 | 1.77 |
| $2000/cap6 | 35.9 | 39.0 | 25.1 | 47.9 | 12 | 6-20 | 1.77 |
| $2000/cap8 | 36.9 | 46.2 | 16.9 | 44.4 | 9 | 2-17 | 1.77 |
| $2000/cap10 | 37.9 | 47.2 | 14.9 | 44.6 | 8 | 1-16 | 1.77 |

### Topstep50K — UNLIMITED (trail $2000, 50% consist.)

| bud/cap | PASS% | BUST% | EXP/CEN% | passRes% | med | p25-p75 | tr/wk |
|---|---:|---:|---:|---:|---:|---:|---:|
| $600/cap3 | 43.6 | 52.9 | 3.5 | 45.2 | 73 | 45-102 | 1.77 |
| $600/cap4 | 42.6 | 53.9 | 3.5 | 44.2 | 62 | 41-91 | 1.77 |
| $600/cap6 | 45.1 | 50.9 | 4.0 | 47.0 | 64 | 37-96 | 1.77 |
| $600/cap8 | 45.9 | 50.1 | 4.0 | 47.8 | 64 | 39-94 | 1.77 |
| $600/cap10 | 45.6 | 50.4 | 4.0 | 47.5 | 64 | 40-95 | 1.77 |
| $900/cap3 | 34.4 | 62.1 | 3.5 | 35.7 | 64 | 40-98 | 1.77 |
| $900/cap4 | 34.7 | 63.1 | 2.2 | 35.5 | 50 | 34-82 | 1.77 |
| $900/cap6 | 32.7 | 64.8 | 2.5 | 33.5 | 41 | 27-76 | 1.77 |
| $900/cap8 | 33.9 | 63.6 | 2.5 | 34.8 | 40 | 28-75 | 1.77 |
| $900/cap10 | 33.4 | 64.1 | 2.5 | 34.3 | 40 | 28-77 | 1.77 |
| $1200/cap3 | 31.9 | 66.3 | 1.7 | 32.5 | 69 | 42-99 | 1.77 |
| $1200/cap4 | 29.4 | 69.1 | 1.5 | 29.9 | 50 | 31-77 | 1.77 |
| $1200/cap6 | 23.7 | 74.8 | 1.5 | 24.1 | 37 | 24-69 | 1.77 |
| $1200/cap8 | 25.4 | 73.1 | 1.5 | 25.8 | 34 | 21-65 | 1.77 |
| $1200/cap10 | 23.9 | 74.1 | 2.0 | 24.4 | 35 | 22-66 | 1.77 |
| $1500/cap3 | 32.2 | 64.8 | 3.0 | 33.2 | 70 | 43-100 | 1.77 |
| $1500/cap4 | 28.9 | 69.1 | 2.0 | 29.5 | 53 | 38-82 | 1.77 |
| $1500/cap6 | 23.4 | 75.1 | 1.5 | 23.8 | 36 | 23-78 | 1.77 |
| $1500/cap8 | 22.2 | 76.3 | 1.5 | 22.5 | 33 | 21-63 | 1.77 |
| $1500/cap10 | 20.2 | 78.1 | 1.7 | 20.6 | 33 | 20-66 | 1.77 |
| $2000/cap3 | 32.2 | 65.3 | 2.5 | 33.0 | 70 | 43-100 | 1.77 |
| $2000/cap4 | 29.2 | 68.8 | 2.0 | 29.8 | 53 | 39-83 | 1.77 |
| $2000/cap6 | 21.2 | 77.8 | 1.0 | 21.4 | 40 | 26-82 | 1.77 |
| $2000/cap8 | 17.7 | 81.3 | 1.0 | 17.9 | 33 | 21-49 | 1.77 |
| $2000/cap10 | 16.5 | 82.5 | 1.0 | 16.6 | 33 | 21-55 | 1.77 |

### MFFU_Builder — UNLIMITED (trail $2000)

| bud/cap | PASS% | BUST% | EXP/CEN% | passRes% | med | p25-p75 | tr/wk |
|---|---:|---:|---:|---:|---:|---:|---:|
| $600/cap3 | 47.4 | 49.1 | 3.5 | 49.1 | 57 | 30-86 | 1.77 |
| $600/cap4 | 47.4 | 49.1 | 3.5 | 49.1 | 49 | 25-77 | 1.77 |
| $600/cap6 | 47.9 | 48.4 | 3.7 | 49.7 | 49 | 22-78 | 1.77 |
| $600/cap8 | 48.6 | 47.6 | 3.7 | 50.5 | 49 | 22-77 | 1.77 |
| $600/cap10 | 48.4 | 47.9 | 3.7 | 50.3 | 49 | 22-77 | 1.77 |
| $900/cap3 | 40.4 | 58.1 | 1.5 | 41.0 | 34 | 20-66 | 1.77 |
| $900/cap4 | 41.1 | 57.6 | 1.2 | 41.7 | 29 | 15-49 | 1.77 |
| $900/cap6 | 38.7 | 60.1 | 1.2 | 39.1 | 21 | 11-35 | 1.77 |
| $900/cap8 | 39.9 | 58.9 | 1.2 | 40.4 | 20 | 9-35 | 1.77 |
| $900/cap10 | 40.4 | 58.4 | 1.2 | 40.9 | 20 | 9-35 | 1.77 |
| $1200/cap3 | 37.7 | 61.6 | 0.7 | 37.9 | 34 | 18-68 | 1.77 |
| $1200/cap4 | 36.7 | 62.6 | 0.7 | 36.9 | 22 | 13-44 | 1.77 |
| $1200/cap6 | 32.2 | 67.1 | 0.7 | 32.4 | 15 | 7-23 | 1.77 |
| $1200/cap8 | 33.9 | 65.3 | 0.7 | 34.2 | 13 | 6-21 | 1.77 |
| $1200/cap10 | 33.7 | 65.6 | 0.7 | 33.9 | 11 | 6-21 | 1.77 |
| $1500/cap3 | 38.7 | 60.6 | 0.7 | 38.9 | 32 | 16-67 | 1.77 |
| $1500/cap4 | 37.2 | 62.1 | 0.7 | 37.4 | 20 | 11-42 | 1.77 |
| $1500/cap6 | 32.9 | 66.3 | 0.7 | 33.2 | 13 | 7-21 | 1.77 |
| $1500/cap8 | 32.4 | 66.8 | 0.7 | 32.7 | 9 | 5-16 | 1.77 |
| $1500/cap10 | 30.9 | 68.3 | 0.7 | 31.2 | 8 | 5-15 | 1.77 |
| $2000/cap3 | 38.7 | 60.6 | 0.7 | 38.9 | 32 | 16-67 | 1.77 |
| $2000/cap4 | 37.2 | 62.1 | 0.7 | 37.4 | 20 | 11-42 | 1.77 |
| $2000/cap6 | 32.7 | 67.1 | 0.2 | 32.8 | 12 | 6-22 | 1.77 |
| $2000/cap8 | 30.2 | 69.6 | 0.2 | 30.2 | 7 | 3-14 | 1.77 |
| $2000/cap10 | 29.2 | 70.6 | 0.2 | 29.2 | 6 | 3-11 | 1.77 |

### Bulenox_EOD — UNLIMITED (trail $2500)

| bud/cap | PASS% | BUST% | EXP/CEN% | passRes% | med | p25-p75 | tr/wk |
|---|---:|---:|---:|---:|---:|---:|---:|
| $600/cap3 | 55.6 | 38.4 | 6.0 | 59.2 | 69 | 34-97 | 1.77 |
| $600/cap4 | 58.1 | 36.7 | 5.2 | 61.3 | 57 | 31-88 | 1.77 |
| $600/cap6 | 59.6 | 34.9 | 5.5 | 63.1 | 57 | 29-86 | 1.77 |
| $600/cap8 | 61.1 | 33.4 | 5.5 | 64.6 | 57 | 30-87 | 1.77 |
| $600/cap10 | 61.1 | 33.4 | 5.5 | 64.6 | 57 | 30-87 | 1.77 |
| $900/cap3 | 52.9 | 45.6 | 1.5 | 53.7 | 49 | 24-84 | 1.77 |
| $900/cap4 | 49.9 | 48.4 | 1.7 | 50.8 | 34 | 16-56 | 1.77 |
| $900/cap6 | 45.9 | 52.9 | 1.2 | 46.5 | 26 | 13-43 | 1.77 |
| $900/cap8 | 45.9 | 52.9 | 1.2 | 46.5 | 22 | 11-42 | 1.77 |
| $900/cap10 | 46.4 | 52.4 | 1.2 | 47.0 | 21 | 10-41 | 1.77 |
| $1200/cap3 | 53.1 | 45.9 | 1.0 | 53.7 | 49 | 23-85 | 1.77 |
| $1200/cap4 | 51.4 | 47.6 | 1.0 | 51.9 | 32 | 15-53 | 1.77 |
| $1200/cap6 | 45.6 | 53.4 | 1.0 | 46.1 | 20 | 8-33 | 1.77 |
| $1200/cap8 | 47.1 | 51.9 | 1.0 | 47.6 | 17 | 7-33 | 1.77 |
| $1200/cap10 | 47.6 | 51.4 | 1.0 | 48.1 | 17 | 6-31 | 1.77 |
| $1500/cap3 | 53.1 | 45.9 | 1.0 | 53.7 | 48 | 22-84 | 1.77 |
| $1500/cap4 | 51.9 | 47.1 | 1.0 | 52.4 | 31 | 15-54 | 1.77 |
| $1500/cap6 | 44.9 | 54.1 | 1.0 | 45.3 | 17 | 8-30 | 1.77 |
| $1500/cap8 | 46.9 | 52.1 | 1.0 | 47.4 | 14 | 5-27 | 1.77 |
| $1500/cap10 | 46.6 | 52.4 | 1.0 | 47.1 | 12 | 4-24 | 1.77 |
| $2000/cap3 | 52.9 | 46.1 | 1.0 | 53.4 | 48 | 22-84 | 1.77 |
| $2000/cap4 | 49.6 | 49.4 | 1.0 | 50.1 | 31 | 15-54 | 1.77 |
| $2000/cap6 | 42.4 | 56.6 | 1.0 | 42.8 | 16 | 7-28 | 1.77 |
| $2000/cap8 | 42.9 | 56.1 | 1.0 | 43.3 | 10 | 2-21 | 1.77 |
| $2000/cap10 | 40.9 | 58.1 | 1.0 | 41.3 | 7 | 1-16 | 1.77 |

### ETF_Static — UNLIMITED (STATIC $2000)

| bud/cap | PASS% | BUST% | EXP/CEN% | passRes% | med | p25-p75 | tr/wk |
|---|---:|---:|---:|---:|---:|---:|---:|
| $600/cap3 | 60.8 | 33.7 | 5.5 | 64.4 | 73 | 36-112 | 1.77 |
| $600/cap4 | 60.1 | 34.9 | 5.0 | 63.3 | 59 | 32-91 | 1.77 |
| $600/cap6 | 62.6 | 32.4 | 5.0 | 65.9 | 61 | 30-96 | 1.77 |
| $600/cap8 | 62.1 | 32.9 | 5.0 | 65.4 | 58 | 30-92 | 1.77 |
| $600/cap10 | 61.3 | 33.7 | 5.0 | 64.6 | 58 | 30-91 | 1.77 |
| $900/cap3 | 58.1 | 40.4 | 1.5 | 59.0 | 55 | 27-89 | 1.77 |
| $900/cap4 | 55.1 | 43.1 | 1.7 | 56.1 | 38 | 20-65 | 1.77 |
| $900/cap6 | 51.6 | 46.4 | 2.0 | 52.7 | 30 | 18-55 | 1.77 |
| $900/cap8 | 51.4 | 46.6 | 2.0 | 52.4 | 29 | 16-50 | 1.77 |
| $900/cap10 | 52.1 | 45.9 | 2.0 | 53.2 | 29 | 17-50 | 1.77 |
| $1200/cap3 | 56.9 | 42.1 | 1.0 | 57.4 | 53 | 25-88 | 1.77 |
| $1200/cap4 | 50.9 | 48.1 | 1.0 | 51.4 | 34 | 19-56 | 1.77 |
| $1200/cap6 | 43.9 | 55.1 | 1.0 | 44.3 | 22 | 16-36 | 1.77 |
| $1200/cap8 | 43.4 | 55.6 | 1.0 | 43.8 | 21 | 15-35 | 1.77 |
| $1200/cap10 | 43.9 | 55.1 | 1.0 | 44.3 | 21 | 15-35 | 1.77 |
| $1500/cap3 | 55.4 | 43.6 | 1.0 | 55.9 | 50 | 24-86 | 1.77 |
| $1500/cap4 | 50.1 | 48.9 | 1.0 | 50.6 | 33 | 18-57 | 1.77 |
| $1500/cap6 | 41.6 | 57.4 | 1.0 | 42.1 | 21 | 16-34 | 1.77 |
| $1500/cap8 | 39.2 | 59.9 | 1.0 | 39.5 | 20 | 14-28 | 1.77 |
| $1500/cap10 | 38.7 | 60.3 | 1.0 | 39.0 | 19 | 13-27 | 1.77 |
| $2000/cap3 | 55.6 | 43.4 | 1.0 | 56.2 | 51 | 24-86 | 1.77 |
| $2000/cap4 | 49.4 | 49.6 | 1.0 | 49.9 | 33 | 17-56 | 1.77 |
| $2000/cap6 | 37.7 | 61.6 | 0.7 | 37.9 | 21 | 16-30 | 1.77 |
| $2000/cap8 | 35.4 | 63.8 | 0.7 | 35.7 | 19 | 13-25 | 1.77 |
| $2000/cap10 | 32.2 | 67.1 | 0.7 | 32.4 | 17 | 13-23 | 1.77 |

### Tradeify_Sel — UNLIMITED (trail $2000, 40% consist.)

| bud/cap | PASS% | BUST% | EXP/CEN% | passRes% | med | p25-p75 | tr/wk |
|---|---:|---:|---:|---:|---:|---:|---:|
| $600/cap3 | 39.2 | 56.9 | 4.0 | 40.8 | 97 | 64-148 | 1.77 |
| $600/cap4 | 39.7 | 56.4 | 4.0 | 41.3 | 86 | 56-133 | 1.77 |
| $600/cap6 | 41.1 | 53.6 | 5.2 | 43.4 | 89 | 55-140 | 1.77 |
| $600/cap8 | 41.4 | 53.4 | 5.2 | 43.7 | 88 | 56-139 | 1.77 |
| $600/cap10 | 41.4 | 53.4 | 5.2 | 43.7 | 88 | 56-139 | 1.77 |
| $900/cap3 | 29.2 | 67.1 | 3.7 | 30.3 | 86 | 54-143 | 1.77 |
| $900/cap4 | 29.4 | 67.8 | 2.7 | 30.3 | 76 | 48-109 | 1.77 |
| $900/cap6 | 29.7 | 67.6 | 2.7 | 30.5 | 73 | 35-115 | 1.77 |
| $900/cap8 | 29.4 | 66.8 | 3.7 | 30.6 | 75 | 38-115 | 1.77 |
| $900/cap10 | 29.4 | 66.8 | 3.7 | 30.6 | 75 | 38-113 | 1.77 |
| $1200/cap3 | 26.4 | 71.6 | 2.0 | 27.0 | 91 | 62-142 | 1.77 |
| $1200/cap4 | 25.2 | 73.1 | 1.7 | 25.6 | 77 | 48-112 | 1.77 |
| $1200/cap6 | 20.4 | 77.8 | 1.7 | 20.8 | 68 | 33-111 | 1.77 |
| $1200/cap8 | 22.2 | 75.6 | 2.2 | 22.7 | 73 | 31-110 | 1.77 |
| $1200/cap10 | 20.9 | 76.3 | 2.7 | 21.5 | 73 | 35-105 | 1.77 |
| $1500/cap3 | 26.7 | 70.1 | 3.2 | 27.6 | 94 | 62-153 | 1.77 |
| $1500/cap4 | 23.9 | 73.8 | 2.2 | 24.5 | 79 | 49-103 | 1.77 |
| $1500/cap6 | 18.0 | 80.0 | 2.0 | 18.3 | 72 | 39-113 | 1.77 |
| $1500/cap8 | 19.5 | 78.8 | 1.7 | 19.8 | 60 | 29-111 | 1.77 |
| $1500/cap10 | 17.7 | 80.3 | 2.0 | 18.1 | 63 | 28-108 | 1.77 |
| $2000/cap3 | 26.9 | 70.3 | 2.7 | 27.7 | 94 | 62-154 | 1.77 |
| $2000/cap4 | 24.2 | 73.6 | 2.2 | 24.7 | 81 | 49-104 | 1.77 |
| $2000/cap6 | 15.2 | 83.5 | 1.2 | 15.4 | 75 | 44-132 | 1.77 |
| $2000/cap8 | 14.7 | 83.8 | 1.5 | 14.9 | 58 | 32-92 | 1.77 |
| $2000/cap10 | 14.0 | 84.5 | 1.5 | 14.2 | 72 | 28-99 | 1.77 |

## (c) Best configurations

**Max pass% per firm (its native metric — raw pass% for 30-day, resolved for unlimited):**

| firm | best cell | PASS% | passRes% | BUST% | median d | note |
|---|---|---:|---:|---:|---:|---|
| Apex50K | $2000/cap10 | 37.9 | 44.6 | 47.2 | 8 | sizing-up beats clock |
| Topstep50K | $600/cap8 | 45.9 | 47.8 | 50.1 | 64 | smallest size = max pass |
| MFFU_Builder | $600/cap8 | 48.6 | 50.5 | 47.6 | 49 | smallest size = max pass |
| Bulenox_EOD | $600/cap8 | 61.1 | 64.6 | 33.4 | 57 | smallest size = max pass |
| ETF_Static | $600/cap6 | 62.6 | 65.9 | 32.4 | 61 | smallest size = max pass |
| Tradeify_Sel | $600/cap8 | 41.4 | 43.7 | 53.4 | 88 | smallest size = max pass |

### SINGLE BEST for MAX pass%

**ETF_Static $600/cap-6 → PASS 62.6% (65.9% of resolved starts) · BUST 32.4% · CENSORED 5.0% · median 61 days (p25-p75 30-96).** Kindest DD (static floor never ratchets). ETF's $2,000 static is the *most* UNVERIFIED number here. **Verified-archetype near-equal: Bulenox_EOD $600/cap-8 → PASS 61.1% (64.6% resolved) · BUST 33.4% · median 57d** on a standard EOD-trail $2,500 rule.

### SINGLE BEST for pass%-per-unit-time (cash flow, pass>=bust)

**ETF_Static $900/cap-10 → PASS 52.1% · BUST 45.9% · median 29 days (p25-p75 17-50)** — 1.80 pass-pts/day, roughly 2x the cash-flow rate of the max-pass cell for ~10pp less pass. Verified-archetype peer: **Bulenox_EOD $900/cap-4 → PASS 49.9% · BUST 48.4% · median 34d.**

## Per-year concentration (best cell / firm) — NO single-year > 50% of passes

| firm | cell | 2022 | 2023 | 2024 | 2025 | 2026 | max-year share |
|---|---|--:|--:|--:|--:|--:|--:|
| Apex50K | $2000/cap10 | 38 | 24 | 42 | 28 | 16 | 28% |
| Topstep50K | $600/cap8 | 50 | 23 | 40 | 49 | 22 | 27% |
| MFFU_Builder | $600/cap8 | 50 | 27 | 46 | 49 | 23 | 26% |
| Bulenox_EOD | $600/cap8 | 64 | 38 | 53 | 67 | 23 | 27% |
| ETF_Static | $600/cap6 | 73 | 33 | 58 | 64 | 23 | 29% |
| Tradeify_Sel | $600/cap8 | 50 | 17 | 40 | 41 | 18 | 30% |

Max single-year share ~30% (2022) across every firm's best cell — **passes are spread across all five years, no single-year concentration.** 2026 is lightest (~9-12%) because it is a partial year (ends 06-22) with fewer starts.

## KEY FINDINGS

1. **The 30-day Apex expiry WAS the binding constraint — removing it ~5x's VPC pass rate.** Bulenox is literally 'Apex ($2,500 trail) with unlimited time': it takes VPC from **12.6% → 61%** pass. Confirmed.

2. **But expiry does NOT convert cleanly to PASS — it splits into PASS + BUST.** Apex's 83.8% expiry (harmless fee loss) becomes ~61% pass **+ ~33% bust** + ~5% censored on unlimited time. The trailing floor, given infinite runway, eventually catches a $2,500 give-back it never had time to catch in 30 days. Bust rises 3.6% → ~33%. Real, honest cost of going unlimited.

3. **SIZING UP does NOT raise pass on unlimited firms — it LOWERS it.** On every unlimited firm, $600 is the pass-maximising budget; larger size only amplifies the drawdown that trips the floor before target. Sizing buys **SPEED, not pass**: median days-to-pass drops ~60d → ~10d as you scale $600→$2000, but pass% falls and bust crosses above pass. (Sizing up *does* raise pass on **Apex** — there the clock, not bust, binds, so speed helps: 12.6% → 37.9% @ $2000/cap-10, but bust also 3.6% → 47.2%.)

4. **DD ARCHETYPE dominates the $ amount.** Static $2,000 (ETF) and wide-trail $2,500 (Bulenox) both beat tight-trail $2,000 (MFFU 50.5% resolved) — a wider/non-ratcheting floor is worth more than $500 of nominal DD. The **consistency rule** costs ~3-6pp: MFFU (no consist.) 50.5% > Topstep (50%) 47.8% > Tradeify (40%) 43.7%, all on the same $2,000 trail.

## (d) HONEST CAVEATS

1. **ALL firm $ thresholds are UNVERIFIED.** `reports/cross_firm/00_firm_rules_2026.md` does not exist in the repo; rules were taken from the task brief. **ETF_Static $2,000** is explicitly flagged as the least trustworthy — the entire ETF result rides on it. $3,000 targets and the trail amounts need contract confirmation before any of these pass-rates are acted on.

2. **Data-censoring on unlimited firms.** Starts within the last few months of data (→2026-06-22) cannot resolve and are counted CENSORED (~4-6%), NOT failed. `pass_resolved%` excludes them; raw `pass%` is therefore slightly understated for unlimited firms. Censoring is small here but real.

3. **Consistency-rule modeling is an assumption.** Modeled as: a PASS is claimed only once bal>=target AND max single-day realized profit <= X% of total profit (else keep trading to dilute). Real firms may compute consistency on different bases (highest-day vs total, or block payout not the pass). Directional.

4. **Same-firm DLL / min-days simplifications.** DLL flatten uses the certified marked-trough semantics; min-days uses active VPC trading days (VPC trades ~1.8 days/wk so min-days rarely binds). No firm-specific 'max contracts' or scaling-plan caps modeled.

5. **Still sim, not live.** Faithful engine replay on honest next-5m-open VPC fills; per-trade sequential marking is slightly optimistic vs the true joint intraday tick path. N>=30 live-fill parity still gates everything. This measures eval-CARRY only — NOT stress-certification for arming.

6. **pass < bust on the fast cells.** Every cash-flow-optimised (fast) cell runs bust ~46-58%. Economically still positive if funded value >> eval fee, but flagged: these are bust-heavy and fragile on a pass>bust safety basis. The max-pass cells (ETF/Bulenox $600) keep pass>bust (~61-62% vs ~33%).
