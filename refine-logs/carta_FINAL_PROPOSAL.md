# CARTA — Final Proposal

**Date:** 2026-04-30
**Codex thread:** 019ddcaa-d0a7-7692-8ca1-505eb8bea93e
**Pipeline:** idea-discovery → novelty-check → research-review → research-refine-pipeline
**Status:** PROCEED WITH KILL GATE (not yet validated; ACD=4/10 novelty, SSR=6/10)
**Target venue:** EMNLP 2026 (ARR May 25, 2026) — NeurIPS 2026 impossible (deadline May 4)
**Kill gate:** Week 1 end — SSR must show ≥5 absolute FAMA on Memora monthly+quarterly rec/reason

---

## Problem Anchor (frozen)

Evolving agent memory retrieval fails in two specific read-side ways: it can stop too early and miss the session(s) containing answer-supporting evidence, or it can retrieve semantically relevant but no-longer-valid memories that bias the reader toward obsolete state. CARTA controls these two risks over an existing memory store: **omission risk** (the chance that the retrieved session budget excludes support needed for the current answer) and **stale-inclusion risk** (the chance that retrieved context contains superseded memories that should no longer influence the answer). Everything in the paper serves this scope: session-budget selection, stale-memory suppression, matched-budget evaluation, and no write-time restructuring claims.

---

## Formal Notation

For query `q`:
- `S+(q)`: support sessions/memories required for the current answer
- `S-(q)`: stale memories that should be excluded  
- `R_B(q)`: retrieved context under budget `B`

ACD targets: `P[S+(q) ⊄ R_B(q)]` — omission risk  
SSR targets: `P[S-(q) ∩ R_B(q) ≠ ∅]` — stale-inclusion risk

---

## Method: CARTA (Calibrated Adaptive Retrieval with Temporal Awareness)

### ACD (Adaptive Conformal Depth)

**Framing:** Coverage-calibrated session-budget selection — NOT "first conformal adaptive-k"

Given a base session retriever, ACD learns from held-out queries how deep retrieval must go before answer-supporting evidence is likely to appear. For a new query, it selects the smallest session budget `k(q)` whose calibrated omission risk is below user-set target `α`. The key comparison is against fixed-depth retrieval at the **same mean session/token budget**.

- Calibration: split conformal prediction on held-out (query, retrieval, correctness) tuples
- Nonconformity score: `1 − P(gold_session ∈ top-k)` via retrieval ranker  
- Coverage guarantee: `P(S+(q) ⊆ top-k(q)) ≥ 1−α` for new queries from same distribution
- Default `α = 0.10`; pilot mean k ≈ 4.8, range 3–7 per query
- Strictly read-side: no write-time changes required

**Pilot evidence (LME-S N=500):** Coverage k=3 → 84%, k=5 → 92%; +11.5pp accuracy gap (gold in top-k vs not)

### SSR (Semantic Supersession Reranking)

**Framing:** Retrieval-time NLI-based supersedence detection without write-time tagging

Starting from top-30 retrieved memories:
1. For each candidate `m_i`, compare only against `m_j` where `timestamp(m_j) > timestamp(m_i)` (later-timestamp-only gating)
2. Optionally filter to top-`h` semantically closest later candidates
3. Small NLI model (DeBERTa-v3-small MNLI cross-encoder) predicts contradiction/supersedence
4. Down-weight superseded `m_i` by 0.1× before reader

**Efficiency:** Later-timestamp-only reduces from O(30²)=900 to O(30·k_later) ≈ O(300) in practice.  
**Must report:** latency/query, NLI calls/query, pruning ablations.

**Primary target:** Memora FAMA — recommending + reasoning tasks (stale-memory failure modes).

### Combined: CARTA = ACD → SSR

1. ACD selects adaptive session budget k(q) for query q  
2. Retrieve top-k(q) (recall-optimized)  
3. SSR reranks: down-weight superseded memories  
4. Reader receives denoised, coverage-guaranteed context

Backend-agnostic: applies on top of any retrieval backend (Flat RAG, MemMachine, etc.)

---

## Novelty Assessment

| Component | Score | Closest Prior | Differentiation |
|-----------|-------|--------------|-----------------|
| ACD | 4/10 | CONFLARE (2404.04287), 2511.17908 (ECIR 2026) | Session-level granularity; multi-session non-stationary; matched-budget evaluation |
| SSR | 6/10 | TSM (2601.07468), SuperLocalMemory V3 (2603.14588) | Purely read-side; no write-time tagging; NLI-based without TKG |
| CARTA combined | 6-7/10 | — | Two-risk control framework; joint formalism; FAMA-targeted |

Do NOT frame ACD as "first conformal adaptive-k retrieval." Frame as "coverage-calibrated session-budget selection."

---

## Defensible Claims

**Claim 1 (ACD):** At matched average retrieval budget, coverage-calibrated session-budget selection improves LME-S accuracy by 1–3 absolute points over the best fixed-k baseline while preserving or improving support-session coverage.  
*Risk: MEDIUM. Validated by: E1.*

**Claim 2 (SSR):** On Memora recommending/reasoning, retrieval-time supersession reranking improves FAMA by 8–15 absolute points over Flat RAG and reduces stale-memory errors with sub-quadratic comparison cost.  
*Risk: MEDIUM-HIGH. Validated by: E2, E3, E8, optionally E10.*

**Claim 3 (transfer):** When layered on MemMachine, CARTA preserves standard memory QA performance on LME-S/LoCoMo while improving forgetting-aware performance on evolving-memory tasks.  
*Risk: HIGH. Validated by: E5, E7.*

---

## Venue Strategy

**Primary:** EMNLP 2026 (ARR May 25, 2026)  
- NeurIPS 2026 abstract deadline May 4 → impossible from today (April 30)  
- ACL 2026 and ICML 2026 already passed  
- EMNLP is the correct fit for NLP systems + evaluation contribution

**Milestone:** Must have E1+E2+E3+E4 complete by May 18 to make EMNLP deadline  
**Backup:** ICLR 2027 main track (~late September 2026 submission)  
**Fallback:** Workshop submission (MemAgents or similar)

---

## 9/10 Upgrade Paths (if time allows)

1. Unified formalism: two-risk framework as formal contribution  
2. Theorem: set coverage over all answer-supporting sessions under context budget  
3. SSR → principled sub-quadratic supersession module  
4. 2 backends (Flat + MemMachine), 3 benchmarks, cost-quality tradeoffs, human error analysis  
5. Released artifact: supersession annotations or FAMA-oriented retrieval evaluation harness
