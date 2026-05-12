# Experiment Tracker — CARTA

**Source plan:** refine-logs/carta_EXPERIMENT_PLAN.md
**Date:** 2026-04-30
**Total runs:** 11 (9 MUST + 2 OPTIONAL)
**Kill gate:** E2 — if <5 absolute FAMA gain on Memora monthly+quarterly rec/reason by May 7, stop

---

## Status Legend
- `TODO`: Not started
- `IN_PROGRESS`: Running
- `DONE`: Complete with results
- `SKIP`: Skipped (dependency not met or killed)
- `KILLED`: Kill gate triggered

---

## Run Status

| run_id | status | result_file | key_metric | notes |
|--------|--------|-------------|------------|-------|
| P0 | TODO | — | — | Instrument retrieval pipeline |
| E1 | TODO | — | — | ACD vs fixed-k on LME-S N=500 |
| E2 | TODO | — | FAMA delta (KILL GATE) | 100q Memora monthly+quarterly rec+reason |
| E3 | TODO | — | FAMA by task/duration | Full Memora SSR |
| E4 | TODO | — | LME-S accuracy | CARTA on Flat |
| E5 | TODO | — | LoCoMo F1 | No-regression check |
| E6 | TODO | — | FAMA overall | Full Memora CARTA |
| E7 | TODO | — | LME-S KU/TR | CARTA on MemMachine |
| E8 | TODO | — | FAMA + latency | SSR efficiency ablation |
| E9 | TODO | — | accuracy-budget curve | Calibration sensitivity (OPTIONAL) |
| E10 | TODO | — | stale-error rate | Human audit (OPTIONAL) |

---

## Week 1 Focus (Apr 30 – May 7)

Kill gate: **E2 must show ≥5 absolute FAMA gain by May 7**

Priority order:
1. P0 (today, ~2h)
2. E2 pilot (today/tomorrow, ~4h)
3. E1 (parallel or tomorrow, ~2h)
4. E8 (after E2 positive, ~4h)

---

## Week 2 Focus (May 8 – May 14)

- E3, E4, E5
- Begin paper intro + method section

---

## Week 3 Focus (May 15 – May 21)

- E6, E7
- Figures, tables, results section

---

## Week 4 Focus (May 22 – May 28)

- E9, E10 (optional)
- Paper polishing
- ARR submission deadline: May 25, 2026
