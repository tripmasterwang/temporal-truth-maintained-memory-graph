# novelty-check trace — 2026-04-30 run01

## Skill: novelty-check (Phase 3 of idea-discovery)
## Date: 2026-04-30
## Codex thread: 019ddcaa-d0a7-7692-8ca1-505eb8bea93e
## Model reasoning effort: xhigh

## Idea evaluated: CARTA (Calibrated Adaptive Retrieval with Temporal Awareness)
### Component 1: ACD — Adaptive Conformal Depth (calibrated adaptive-k retrieval)
### Component 2: SSR — Semantic Supersession Reranking (retrieval-time NLI staleness detection)

## Literature Searched

### Conformal prediction + RAG
- CONFLARE (2404.04287, Apr 2024): CP uncertainty quantification for RAG; threshold-based, static corpora
- Principled Context Engineering (2511.17908, Nov 2025, ECIR 2026): conformal filtering for RAG; NeuCLIR/RAGTIME news retrieval, adaptive set size by filtering
- Conformal-RAG (2506.20978, SIGIR 2025): CP for response quality sub-claims; not retrieval depth
- C-RAG (2402.03181, ICML 2024): weakens "first conformal guarantees for RAG" claim

### Temporal reranking + agent memory
- TSM / Beyond Dialogue Time (2601.07468, Jan 2026): temporal reranking via write-time TKG; write-side not read-side
- SuperLocalMemory V3 (2603.14588, Mar 2026): sheaf model for contradiction detection; write-time supersede edges; info-geometric foundations
- Memanto (2604.22085, Apr 2026): explicitly mentions conflict resolution + temporal versioning; but primarily about indexing efficiency

### Adaptive retrieval (agent memory)
- AdaMem (2603.16496, Mar 2026): question-conditioned retrieval route; NOT conformal, not coverage-guarantee-based
- FluxMem: dynamic memory structure selection; different mechanism

## Codex Verdict

### ACD novelty: 4/10
- CONFLARE already calibrates threshold → adaptive set size (not exactly adaptive-k but similar effect)
- 2511.17908 (ECIR 2026) is close: conformal filtering preserving evidence with coverage control
- Genuine ACD delta: session-level evidence coverage in multi-session agent memory; memory-specific evaluation benchmarks
- Gap from 2511.17908: real but not enough by itself; "filtering is not adaptive-k" argument won't survive review (filtering already produces adaptive set size)

### SSR novelty: 6/10
- No exact match for retrieval-time NLI-based supersedence WITHOUT write-time tagging
- TSM: write-time TKG required
- SuperLocalMemory V3: write-time sheaf consistency checker
- Memanto: mentions conflict resolution but this is indexing-side

### CARTA combination: 6/10 now, 7/10 with strong ablations
- ACD attacks false negatives (missing evidence); SSR attacks false positives (stale evidence)
- Complement motivated by Memora/FAMA failure mode
- Risk: reviewers may see as "two read-side add-ons" unless joint story is crisp

### FAMA first-mover claim
- NOT "first system on FAMA" (Memora paper itself evaluated 6 systems)
- Defensible claim: "first method explicitly designed and evaluated to improve FAMA via retrieval-time stale-memory suppression"

### Publication risk
- Without strong FAMA gains + no LME-S/LoCoMo regression: safer for ACL/EMNLP
- NeurIPS/ICML main track requires: strong FAMA gains on recommending/reasoning, no material regression on LME-S/LoCoMo, backend-agnostic results on ≥2 systems, clean ACD+SSR ablations

## Go/No-Go Criteria (Codex)
- SSR must show clear Memora/FAMA gain on at least one strong backend (recommending/reasoning tasks)
- ACD must beat fixed-k at matched average context budget
- CARTA must not produce noticeable LME-S/LoCoMo regression

## Final Codex Recommendation
Proceed with 1-week kill gate. No fatal novelty blocker. SSR-centered CARTA is worth 4-week implementation. ACD alone is not sufficient to anchor the paper.

## Additional Papers Flagged by Codex
- C-RAG (2402.03181, ICML 2024): weakens broad "first conformal guarantees for RAG" claim
- AdaMem (2603.16496): question-conditioned adaptive retrieval route (not conformal)
- ES-Mem (2601.07582): dynamic segmentation + hierarchical episodic localization
- Memanto: conflict resolution + temporal versioning in abstract (verify scope)
