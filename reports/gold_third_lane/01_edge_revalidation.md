# Gold Third-Lane -- Lane 1: Edge Revalidation

RESEARCH ONLY. Not deployed. Modifies nothing existing.

```
PRE-REGISTERED PRIORS
  full-sample PF 1.45 is LUMPY: 2023 0.78 / 2024 1.67 / 2025 1.07 / 2026 2.29 (per-year honesty is the point)
  ~0.6 tr/wk -> ~2.6 trades/eval -> expected portfolio effect SMALL
  15yr definitive verdict: simple gold strategies are dead after costs -- if the extended window
    kills this edge, that IS the expected outcome; report plainly
  PF > 1.8 full-sample -> suspicious -> FREEZE + FLAG
KILL GATES: extended-window full PF < 1.15 @ 0.6pt RT | 2019-2022 pseudo-OOS PF < 1.0 | vol-gate cliff
```

## (1) Canary

n=140 PF=1.454 WR=0.493 -- verdict: MATCH

| year | n | pf | wr | totR |
| --- | --- | --- | --- | --- |
| 2022.0000 | 18.0000 | 2.2883 | 0.6111 | 35.5346 |
| 2023.0000 | 31.0000 | 0.7850 | 0.4194 | -15.8391 |
| 2024.0000 | 33.0000 | 1.6675 | 0.5758 | 45.6624 |
| 2025.0000 | 44.0000 | 1.0657 | 0.4091 | 12.3611 |
| 2026.0000 | 14.0000 | 2.2921 | 0.5714 | 130.7102 |

## (2) Extended Window (2019-2026, faithful rules, cost=0.30pt)

n=277 PF=1.040 WR=0.419 totR=32.1pts

| year | n | pf | wr | totR |
| --- | --- | --- | --- | --- |
| 2019.0000 | 33.0000 | 0.7656 | 0.3939 | -11.8978 |
| 2020.0000 | 52.0000 | 0.6028 | 0.3654 | -55.9945 |
| 2021.0000 | 44.0000 | 2.2495 | 0.5682 | 76.4543 |
| 2022.0000 | 25.0000 | 1.0610 | 0.4000 | 3.0519 |
| 2023.0000 | 31.0000 | 0.8296 | 0.4194 | -11.7876 |
| 2024.0000 | 34.0000 | 0.8113 | 0.4118 | -20.0142 |
| 2025.0000 | 46.0000 | 0.8250 | 0.3478 | -39.5246 |
| 2026.0000 | 12.0000 | 1.8709 | 0.5000 | 91.8039 |

2019-2022 pseudo-OOS: n=154 PF=1.038 WR=0.435

@0.6pt RT (kill-gate reference): PF=0.941 n=277

## (3) Futures Cost Ladder (MGC $10/pt)

| cost_rt | slip | n | pf | wr | totR |
| --- | --- | --- | --- | --- | --- |
| 0.3000 | 0.0000 | 277.0000 | 1.0396 | 0.4188 | 32.0913 |
| 0.3000 | 0.1000 | 277.0000 | 0.9957 | 0.4043 | -3.5773 |
| 0.3000 | 0.2000 | 277.0000 | 0.9307 | 0.3863 | -60.1576 |
| 0.6000 | 0.0000 | 277.0000 | 0.9406 | 0.4116 | -51.0087 |
| 0.6000 | 0.1000 | 277.0000 | 0.9018 | 0.4007 | -86.6773 |
| 0.6000 | 0.2000 | 277.0000 | 0.8442 | 0.3827 | -143.2576 |
| 1.0000 | 0.0000 | 277.0000 | 0.8248 | 0.4043 | -161.8087 |
| 1.0000 | 0.1000 | 277.0000 | 0.7920 | 0.3935 | -197.4773 |
| 1.0000 | 0.2000 | 277.0000 | 0.7429 | 0.3755 | -254.0576 |

## (4) 1M Truth

1m-rewalk PF=0.995 vs 5m-native PF=1.040 (shift -0.044); nodata trades=39

Timestamp convention: HistData M1 naive timestamps are ALREADY America/New_York wall-clock (follow US DST calendar directly, no offset shift needed); verified via an 8-date sweep 2019-2023 spanning DST boundaries vs the dukascopy UTC series (a first-pass fixed-UTC-5 test looked plausible on 2 dates but broke down elsewhere -- best-fit offset flips +4h/+5h exactly at DST changeovers). Stop/target rebased to the M1 series' own entry-time open (relative ATR distances preserved) to avoid cross-vendor absolute-price noise.

## (5) Vol-Gate Sensitivity

| gate | n | pf | wr | totR |
| --- | --- | --- | --- | --- |
| 0.6000 | 192.0000 | 0.8501 | 0.4010 | -92.2750 |
| 0.6500 | 228.0000 | 0.9843 | 0.4167 | -10.8347 |
| 0.7000 | 277.0000 | 1.0396 | 0.4188 | 32.0913 |
| 0.7500 | 332.0000 | 0.9522 | 0.4096 | -46.5950 |
| 0.8000 | 372.0000 | 1.0325 | 0.4113 | 36.1396 |

Cliff verdict: plateau/gradual (pass)

## Kill-Gate Verdicts

- extended-window PF<1.15 @0.6RT: KILL
- 2019-2022 pseudo-OOS PF<1.0: pass
- vol-gate cliff: pass
- full-sample PF>1.8 (freeze+flag): no
