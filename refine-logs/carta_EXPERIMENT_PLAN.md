# Experiment Plan — CARTA

**Date:** 2026-04-30
**Method:** CARTA = ACD (Adaptive Conformal Depth) + SSR (Semantic Supersession Reranking)
**Kill gate:** SSR E2 pilot — if <5 absolute FAMA gain on Memora monthly+quarterly rec/reason by end of week 1, kill project
**GPU budget:** 48h total (RTX-4090, GPU 0 or 1 — NOT GPU 3)
**API budget:** MAAS (deepseek-v3.2, Kimi-K2, glm-5.1) for answer generation and judging

---

## Background

88.2% of TTMG failures are read-side (gating decomposition, results/gating_decomposition.json).
CARTA targets two specific read-side failure modes:
- Omission risk: retrieved set excludes answer-supporting sessions
- Stale-inclusion risk: retrieved set includes superseded memories that bias the reader

Pilot evidence (ACD on LME-S N=500): gold coverage k=3=84%, k=5=92%; +11.5pp accuracy gap.

---

## Experiment Table

| run_id | method | dataset | metric | est. GPU-hours | priority | dependency |
|--------|--------|---------|--------|----------------|----------|------------|
| P0 | Add top-30 candidate storage, timestamp normalization, cache retrieval | LME-S, Memora, LoCoMo | pipeline ready | 0.5 | MUST | none |
| E1 | Fixed k={3,5,7} vs ACD α=0.10, matched mean budget | LME-S N=500 | accuracy, support coverage, mean sessions/tokens | 2.0 | MUST | P0 |
| E2 | SSR alone, later-timestamp-only gating, small NLI model | Memora monthly+quarterly, rec+reason (100q pilot) | FAMA (kill gate) | 1.0 | MUST | P0 |
| E3 | SSR alone, full Memora | Memora weekly/monthly/quarterly, all tasks | FAMA by task/duration | 6.0 | MUST | E2 positive |
| E4 | CARTA = ACD+SSR on Flat | LME-S N=500 | accuracy, coverage, mean budget | 2.5 | MUST | E1, E2 |
| E5 | CARTA on Flat | LoCoMo N=60 | accuracy/F1, no-regression check | 1.5 | MUST | E4 |
| E6 | CARTA on Flat | Memora full | FAMA overall + by task/duration | 6.0 | MUST | E3, E4 |
| E7 | CARTA on MemMachine backend | LME-S full or KU/TR subset first | accuracy, support coverage, mean budget | 5.0 | MUST | E1, P0 |
| E8 | SSR efficiency ablation: full pairwise vs later-only vs later-only+top-h | Memora monthly+quarterly | FAMA, latency/query, NLI calls/query | 4.0 | MUST | E2 |
| E9 | Calibration sensitivity: α ∈ {0.05, 0.10, 0.15, 0.20} | LME-S N=500 | accuracy-budget curve, coverage curve | 2.0 | OPTIONAL | E1 |
| E10 | Human stale-memory error audit | Memora sampled rec/reason | stale-error rate before/after SSR | 0.0 | OPTIONAL | E3/E6 |

**Must-run total:** ~28.5 GPU-hours  
**Optional total:** ~2.0 GPU-hours  
**Fits in 48h budget** with room for reruns.

---

## Run Order

**Day 1 (today):**
1. `P0`: Instrument Flat RAG to save top-30 retrieved candidates (score, session_id, timestamp, text). Normalize timestamps across Memora. Build SSR with later-timestamp-only gating and DeBERTa-v3-small MNLI cross-encoder.
2. `E2` (100q pilot): Run on Memora monthly+quarterly, recommending+reasoning only. Compute: FAMA delta vs Flat, stale-memory hit rate before/after, mean NLI calls/query, latency/query.
3. `E1` (parallel with E2 or day 2): Fixed k={3,5,7} vs ACD α=0.10 on LME-S N=500.

**Week 1:**
- After E2 positive: run E8 (efficiency ablation)
- After E2 negative: STOP — kill gate triggered

**Week 2:**
- E3, E4, E5 — begin paper intro/method writing

**Week 3:**
- E6, E7 — figures, tables, backend comparison

**Week 4:**
- E9, E10 (optional) — paper polishing, reproducibility appendix

---

## Kill Gate

If `E2` (100q Memora monthly+quarterly pilot) shows **<5 absolute FAMA gain** over Flat RAG on recommending+reasoning tasks by end of **Week 1 (May 7, 2026)**:

→ **Kill CARTA as main-track paper**

Options after kill:
- Pivot to SSR as systems workshop paper (MemAgents)  
- Drop SSR and reassess CARTA as ACD-only contribution
- Reassess CalLB (if not already killed)

---

## FAMA Evaluation Notes

- Do NOT anchor on A-Mem=154.50/300 (LangMem is strongest per Memora paper)
- Must win on recommending/reasoning (where stale-memory matters), NOT just remembering
- Minimum convincing for main-track: +10 absolute overall FAMA over best reproduced baseline
- A gain only on "remembering" task will not be compelling to reviewers

---

## Backend Selection

**Primary pair: Flat RAG + MemMachine** (strongest credibility)
- Flat RAG: shows backend-agnostic property
- MemMachine: strong retrieval-focused system (93.0% LME-S), not already claiming conflict resolution
- Do NOT use Flat + Memanto as main pair (Memanto claims conflict resolution → muddies SSR story)
- TTMG optional as third backend (shows orthogonality to write-side)

---

## 4-Week Calendar

| Week | Dates | Experiments | Writing |
|------|-------|-------------|---------|
| Week 1 | Apr 30 – May 7 | P0, E2 (kill gate), E1, E8 | — |
| Week 2 | May 8 – May 14 | E3, E4, E5 | Intro + Method |
| Week 3 | May 15 – May 21 | E6, E7 | Results + Analysis |
| Week 4 | May 22 – May 28 | E9, E10 (opt) | Polish + Submission (ARR May 25) |

---

## Day 1 Checklist

- [ ] Instrument Flat RAG to store top-30 candidates with (score, session_id, timestamp, text)
- [ ] Normalize timestamps to sortable integers for Memora + LME-S + LoCoMo
- [ ] Build SSR module: later-timestamp-only gating + DeBERTa-v3-small MNLI cross-encoder + 0.1× down-weight
- [ ] Run E2 pilot (100q Memora monthly+quarterly rec+reason)
- [ ] Compute: FAMA delta, stale hit rate, NLI calls/query, latency/query
- [ ] Kill gate decision: ≥5 FAMA gain → proceed; <5 → stop
