# Research Idea Report

**Direction:** Long-conversation agent memory — read-side improvement via statistical/info-theoretic machinery
**Generated:** 2026-04-30
**Pipeline:** research-lit → idea-creator (Codex) → pilot (ACD oracle analysis N=150) → deep validation
**Ideas evaluated:** 12 generated → 9 survived filtering → 1 fully piloted (ACD) → 1 flagged manual pilot (SSR) → top recommendation: CARTA (combined ACD+SSR)

---

## Executive Summary

Pilot analysis confirms: **gold evidence is missing from top-3 retrieved sessions in 16% of LongMemEval-S questions**, and this causes an **11.5pp accuracy gap**. SSU questions are critically undersearched (52% coverage at k=3). Adaptive retrieval depth from k=3 to k=5 recovers 8pp coverage. This is a tractable, read-side-only, backend-agnostic improvement. Combined with supersession-aware reranking, the proposed approach (CARTA) addresses both coverage (ACD) and ordering (SSR) problems, with the first formal coverage guarantee and FAMA-targeted stale-memory reranking in the agent memory literature.

---

## Landscape Summary

April 2026 SOTA: MemMachine 93.0% LongMemEval-S, EverMemOS 92.3% LoCoMo. Field convergence: retrieval recall dominates accuracy (+20pp spread vs +3-8pp for write strategy). Memanto's ablation: "modern LLMs perform reasoning that graph systems attempt to pre-compute at write time." MemMachine's gains: retrieval depth (+4.2%), context formatting (+2.0%), search prompt (+1.8%), query bias correction (+1.4%) — all read-side. **CONFIRMED structural white-space**: zero agent memory papers use conformal prediction, PMI scoring, retrieval-time supersedence detection, or retrieval scorer training. FAMA/Memora benchmark has no reported scores from any SOTA system — first-mover opportunity.

---

## Pilot Results

| Idea | Setup | Key Metric | Signal |
|------|-------|-----------|--------|
| ACD oracle analysis | N=150 LME-S, hybrid BM25+emb, k sweep | Coverage@3=84%, Coverage@5=92%; accuracy gap=11.5pp | **POSITIVE** |
| SSR | N/A | Needs top-30 candidate retrieval (pipeline modification) | **MANUAL PILOT NEEDED** (>2h setup) |

**ACD oracle details (N=150, hybrid BM25+MiniLM-L6):**
- Coverage@k: k=1: 72%, k=2: 81%, k=3: 84%, k=5: 92%, k=10: 95%, k=30: 100%
- Accuracy gap: gold in top-3 (n=126): 69.8% | gold NOT in top-3 (n=24): 58.3% → 11.5pp gap
- SSU: k=3 coverage=52%, acc-when-covered=100%, acc-when-missed=80% → strong motivation
- 12 of 24 missed questions recovered at k=5 (50% of missed)
- Gold rank distribution: p50=1, p90=5, p99=18 (long tail justifies adaptive depth)

---

## 🏆 Recommended Idea: CARTA — Calibrated Adaptive Retrieval with Temporal Awareness

**Status:** TOP RECOMMENDATION (combined ACD+SSR)

### Hypothesis
Separating the retrieval coverage problem (adaptive conformal depth) from the retrieval ordering problem (supersession-aware reranking) yields a backend-agnostic read-side improvement applicable to ≥90% of question types, with the first formal coverage guarantee and FAMA improvement in the agent memory literature.

### Method (2-component, read-side only)

**Component 1: Adaptive Conformal Depth (ACD)**
- Learn a nonconformity score from features available at retrieval time: retrieval score entropy, score gap between top-1 and top-k, candidate semantic dispersion, backend disagreement (if multiple backends available)
- Calibrate on held-out validation set to find threshold τ such that gold evidence inclusion ≥ 90% with distribution-free guarantee (split conformal prediction)
- At inference: retrieve initial pool, compute features, apply smallest k meeting calibrated coverage
- Expand k (never abstain) when uncertain — graceful degradation
- Token cost: amortized saving on easy questions (70-75% queries need k≤3) offset by expansion on hard queries

**Component 2: Semantic Supersession Reranking (SSR)**
- Within the retrieved top-k pool, build a query-conditioned supersession graph: for each pair (m_old, m_new) with temporal ordering and semantic overlap, apply a lightweight NLI/cross-encoder to classify as supports / supersedes / unrelated
- Rerank pool by: base_relevance + temporal_currentness - supersededness_penalty
- Novel principle: "currentness as residual information" — a snippet's utility = its information about the query after conditioning on newer near-duplicate evidence
- Works on free-text snippets, no canonical matching, no write-time preprocessing
- Addresses FAMA directly: penalizes relying on superseded evidence

**Combined CARTA pipeline:**
1. Retrieve initial pool (k_init = 3, default)
2. Compute ACD features → decide if pool needs expansion
3. If yes, expand to k_expanded (bounded by budget cap)
4. Apply SSR to rerank final pool
5. Pass top-k' sorted pool to reader (k' ≤ k_expanded)

### Target Benchmarks
- LongMemEval-S N=500 (primary, 6 question types ≥50% coverage)
- LoCoMo full set (cross-domain, MUST not regress vs Flat RAG)
- Memora/FAMA (first-mover: no SOTA system has reported FAMA scores)

### Expected Outcome (conservative estimates)
- ACD component alone: +2-4pp LME-S accuracy (oracle ceiling: 8pp coverage gain → ~2-3pp accuracy assuming ~40% coverage-to-accuracy translation)
- SSR component alone: +5pp FAMA on Memora, +1-2pp LME-S KU/TR slices
- Combined CARTA on Flat RAG: +3-6pp LME-S, +5-8pp FAMA, no LoCoMo regression
- **Key bar:** Apply on top of MemMachine/Memanto baseline (>85% LME-S) → show that even SOTA systems improve with CARTA

### Novelty
- **vs MemMachine**: MemMachine tunes k manually (fixed k per config); ACD provides calibrated adaptive k with formal guarantee. SSR is absent.
- **vs Memanto**: Information-theoretic retrieval (Moorcheh) addresses indexing efficiency not coverage guarantee. Supersession detection absent.
- **vs SmartSearch**: Deterministic pipeline, no formal guarantee, no staleness modeling.
- **vs Conformal-RAG (2506.20978, SIGIR'25)**: Applied to document QA, not agent memory; no temporal/supersession dimension.
- **vs PMI-RAG (NAACL'25)**: PMI as performance gauge, not as retrieval reranking feature; no temporal conditioning.
- **vs 2602.12192 (Memory-aware Reranker)**: Listwise reranking for long context, doesn't address temporal supersedence.

### Implementation Plan
- Week 1: ACD implementation + calibration on LME-S; SSR NLI judge (deepseek-v3.2 pairwise check)
- Week 2: Full evaluation on LME-S N=500, LoCoMo; ablation (ACD-only vs SSR-only vs combined)
- Week 3: Memora/FAMA evaluation; theoretical coverage proof write-up
- Week 4: Apply to MemMachine backend (validation on strong baseline); paper draft

### Feasibility
- Compute: ACD calibration: ~0.2 GPUh. SSR NLI check: ~1.5 GPUh for N=500. Total: ~2 GPUh.
- Code: TTMG retrieval pipeline extensible; Flat RAG already available as backend
- Risk: MEDIUM — NLI pairwise judge can be noisy; coverage guarantee holds for calibration distribution but may drift under domain shift

### Reviewer's Likely Objections
1. "ACD is just adaptive top-k with conformal branding" → Counter: provide theorem, show calibration holds across backends/domains; show coverage efficiency curve (smaller mean k for same coverage)
2. "SSR is engineering, not research" → Counter: derive "currentness as residual information" formally; show ablation vs simple recency reranking (+ε) and vs raw embedding similarity (-2pp)
3. "Overall gains may be small if reader compensates for coverage gaps" → Counter: 11.5pp accuracy gap is the direct empirical answer; SSU at 100%/80% with/without gold is the clearest evidence

---

## Backup Idea: ACD-Only (Adaptive Conformal Depth)

If SSR is too noisy or computation-expensive, ACD alone is a publishable standalone contribution:
- First formal coverage guarantee in agent memory
- 95% question-type coverage (applies to all types, not specialist)
- Pilot: POSITIVE (8pp coverage gain, 11.5pp accuracy gap)
- Theorem: distribution-free guarantee on gold-evidence inclusion
- Reviewer bar (from Codex): realized 90% coverage within 88-92%, matching best fixed-k accuracy within 0.5pp, reducing mean tokens ≥30%, plus theorem

---

## Ranked Ideas (full list)

| Rank | Idea | FAMA | Coverage | Compute | Risk | Pilot |
|------|------|------|----------|---------|------|-------|
| 1 | **CARTA (ACD+SSR combined)** | yes | 90% | ~2h | MEDIUM | POSITIVE (ACD), SSR manual |
| 2 | **ACD standalone** | partial | 95% | 0.2h | LOW | **POSITIVE** |
| 3 | SSR standalone | yes | 75% | 1.5h | MEDIUM | manual pilot needed |
| 4 | Temporal Conditional MI (TCMI) | yes | 70% | 1.5h | MEDIUM | not run |
| 5 | Sequential Recall Testing | partial | 95% | 0.3h | LOW/MED | not run |
| 6 | Conformal Backend Routing | yes | 80% | 0.5h | MEDIUM | not run |
| 7 | Jackknife Score Uncertainty | partial | 90% | 0.5h | LOW | not run |
| 8 | Conditional MI Diversification | partial | 85% | 0.4h | LOW | not run |
| 9 | Contrastive Currentness Retrieval | yes | 70% | 1.2h | MED/HIGH | not run |

## Eliminated Ideas (reference)
| Idea | Reason |
|------|--------|
| Marginal Answer Utility Scorer | >2h compute for full DPO training; needs write-time (writer-scored labels) |
| Reader Surprisal Guided Reranking | >2h compute; inference cost explosion risk |
| On-the-Fly Belief Propagation | HIGH risk: relation errors cascade; complex engineering |

---

## Key Constraints Satisfied (CARTA)
✅ Not a specialist (<50% slice) — 90%+ question type coverage
✅ No canonical entity-slot matching — NLI works on free text
✅ No over-abstain — expands k rather than abstaining
✅ Not single-valued scope — applies to all answer types
✅ No write-time pipeline — fully read-side
✅ Not re-litigation of structured memory — orthogonal to write strategy
✅ No LoCoMo regression expected — purely additive to any retrieval backend
✅ Statistical/info-theoretic contribution — conformal coverage theorem + residual-information reranking

---

## Phase 3: Novelty Check Results (2026-04-30)

**Codex thread:** 019ddcaa-d0a7-7692-8ca1-505eb8bea93e | **Trace:** .aris/traces/novelty-check/2026-04-30_run01/trace.md

| Component | Score | Closest Prior | Verdict |
|-----------|-------|--------------|---------|
| ACD | **4/10** | CONFLARE (2404.04287), 2511.17908 (ECIR 2026) | Not "first conformal adaptive-k"; reframe as "session-budget coverage calibration" |
| SSR | **6/10** | TSM (2601.07468), SuperLocalMemory V3 (2603.14588) | No exact match for read-time NLI without write-time tagging |
| CARTA combined | **6-7/10** | — | Proceed with 1-week kill gate; SSR-centered story |

**Key novelty clarifications:**
- ACD: CONFLARE (2024) already calibrates threshold → adaptive set size. 2511.17908 (ECIR'26) does conformal context filtering. ACD's delta: session-level granularity, multi-session non-stationary memory, matched-budget evaluation.
- SSR: TSM and SuperLocalMemory V3 both do supersedence at WRITE TIME. SSR is purely read-time NLI, no write-time tags.
- FAMA: NOT "first system on FAMA" — Memora paper evaluated 6 systems. Defensible: "first method explicitly designed to improve FAMA via retrieval-time stale-memory suppression."
- New threat flagged: AdaMem (2603.16496) — question-conditioned adaptive retrieval route (not conformal).

**Codex recommendation:** "SSR-centered CARTA is worth 4-week implementation. ACD alone is not sufficient to anchor the paper."

---

## Phase 4: Critical Review (2026-04-30)

**Trace:** .aris/traces/research-review/2026-04-30_run01/trace.md

**Score prediction:** 3/10 (weak reject / reject) with pilot evidence only. Scores expected: 3/4/4/5.

**Strongest objections:**
1. "Incremental engineering" — ACD adapts CONFLARE/C-RAG to memory; SSR is another temporal reranker.
2. "Coverage guarantee misaligned with task" — P(gold_session ∈ top-k) ≠ P(all answer-supporting sessions in top-k), especially for MS questions.
3. "Empirical story incomplete" — SSR has no results; 900 NLI calls/query needs efficiency analysis.

**ACD framing fix:** Reframe as "coverage-calibrated session-budget selection" (not "first conformal k"). Key: matched-budget comparisons; per-question-type analysis; multi-session set coverage, not single-gold-session.

**SSR efficiency:** Must use small NLI model (DeBERTa-v3-small), report latency, show pruning ablations (later-timestamp-only gating reduces O(900) → O(300) in practice).

**FAMA strategy:** Win on recommending/reasoning (stale-memory tasks), NOT just remembering. +10 absolute FAMA minimum for main-track credibility.

**Backend:** Flat + MemMachine. NOT Flat + Memanto (Memanto claims conflict resolution → muddies SSR story).

---

## Phase 4.5: Refinement + Experiment Plan (2026-04-30)

**Trace:** .aris/traces/research-refine/2026-04-30_run01/trace.md

**Problem Anchor (frozen):** Two read-side failure modes: omission risk P[S+(q) ⊄ R_B(q)] and stale-inclusion risk P[S-(q) ∩ R_B(q) ≠ ∅]. CARTA controls both. No write-time changes.

**Venue:** EMNLP 2026 (ARR May 25) — NeurIPS 2026 abstract deadline May 4 (impossible from today). Backup: ICLR 2027.

**Kill gate:** E2 SSR pilot on Memora monthly+quarterly rec/reason (100q) by May 7. If <5 absolute FAMA gain → kill CARTA.

**Full experiment plan:** refine-logs/carta_EXPERIMENT_PLAN.md (9 MUST runs, ~28.5 GPU-hours)

**Day 1 priority:**
1. P0: Instrument Flat RAG to store top-30 candidates + normalize timestamps
2. E2: 100q SSR pilot (Memora monthly+quarterly rec+reason) — KILL GATE
3. E1: ACD vs fixed-k on LME-S N=500 (parallel)

---

## Next Steps
- [x] ACD pilot: POSITIVE (oracle analysis, +11.5pp accuracy gap)
- [x] /novelty-check CARTA: 4/10 ACD, 6/10 SSR, 6-7/10 combined
- [x] /research-review CARTA: 3/10 predicted, clear upgrade path identified
- [x] /research-refine-pipeline CARTA: problem anchor frozen, experiment plan written
- [ ] **P0**: Instrument retrieval pipeline to store top-30 candidates + timestamps (Day 1)
- [ ] **E2 (KILL GATE)**: SSR pilot on 100q Memora monthly+quarterly rec/reason (Day 1-2)
- [ ] **E1**: ACD vs fixed-k at matched budget on LME-S N=500 (Day 2)
- [ ] **E8**: SSR efficiency ablation (after E2 positive)
- [ ] **E3-E6**: Full Memora + LME-S + LoCoMo evaluation (Week 2-3)
- [ ] **E7**: Apply CARTA on MemMachine backend (Week 3)
- [ ] Paper draft targeting EMNLP 2026 ARR May 25 submission
