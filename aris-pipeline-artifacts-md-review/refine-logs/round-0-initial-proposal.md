# Research Proposal: CalRR — Calibrated Hybrid Reranker for Long-Conversation Memory with Per-Item Rank-Quality Coverage

## Problem Anchor

- **Bottom-line problem.** When an LLM agent answers from accumulated long-conversation memory, the *reader* commits two systematic errors that no current 2026 system addresses with a calibrated mechanism: (i) **over-specification** — after correctly grounding on the right evidence, it pads the answer with adjacent, unsupported details (47 % of Path D's wrong answers on LongMemEval-S); (ii) **wrong-content retrieval** — surfacing the wrong session/turn even though the right evidence exists in the haystack (41 % of wrong answers). Together these two reader-side failures account for **88.2 % of Path D's wrong answers**, empirically rejecting the "writer is the bottleneck" hypothesis. Source: gating decomposition over 186 wrong answers in `results/gating_decomposition.json` (2026-04-27).
- **Must-solve bottleneck.** The minimal mechanism a memory system needs but does not have: a **calibrated, per-retrieved-item rank-quality score** that (a) fuses heterogeneous substrate signals (semantic + lexical + claim-graph + raw-turn) so cross-substrate disagreement downweights items, (b) prefers *cleanliness over breadth* in the top-k so the reader does not pad with marginal items, and (c) carries a *coverage guarantee on rank quality* (per-item calibrated reliability ∈ [0, 1] with split-conformal coverage on a held-out dev split). Universal across question types — not per-query stopping decision (which is what MiCP / Stop-RAG / β did and which we explicitly reject).
- **Non-goals.** Not a new memory architecture. Not a write-time pipeline. Not LoCoMo accuracy SOTA (frontier saturated at 92.3 %). Not a per-query abstention rule (we own item-level scoring; the reader's existing answer/abstain stays unchanged). Not a writer-fine-tune project (writer-side failures are 11 % of errors per gating, not the bottleneck).
- **Constraints.** 1–2 RTX-4090; MAAS API for writer/reader/judge (`deepseek-v3.2`, `Kimi-K2`, `glm-5.1`); 3 weeks; reuse `ttmg/` substrate (Path D's claim graph + supersede edges + `raw_turn_fallback` index — all working code); shared-host load varies, default sequential MAAS; NeurIPS / ICML main-track target.
- **Success condition.**
  1. **Per-item conformal coverage holds.** On Memora-FAMA test, the reranker's calibrated reliability score has empirical coverage `Pr[item is gold-relevant | reliability ≥ τ̂_α] ≥ 1 − α` for α ∈ {0.05, 0.10, 0.15, 0.20, 0.25}, with Wilson UCB margin ≤ α + 0.02.
  2. **Top-k cleanliness improves answer accuracy.** Path D reader fed top-k ranked by CalRR (vs the existing `raw_turn_fallback`-based top-k) shows ≥ 3 pp lift on the *Class-C-prone* question types (single-session-user, knowledge-update, single-session-preference per the gating breakdown), without regressing on others.
  3. **FAMA wins on Memora.** Aggregated FAMA strictly dominates A-Mem / Mem0 / LightMem / EverMemOS-on-Memora (paired-bootstrap p<0.05 over (persona × duration) clusters).
  4. **Parity on LoCoMo.** CalRR-augmented reader within 2 pp of best of (Path D, A-Mem, SmartSearch).
  5. **Mechanism causality.** Removing `cross_substrate_agreement` feature drops Class-B-fix; removing `cleanliness_penalty` drops Class-C-fix; removing the conformal calibration breaks per-item coverage.
  6. **Failure clause.** Design fails if (a) per-item coverage exceeds α + 0.04 for ≥ 2 of 5 α values on Memora test, OR (b) top-k cleanliness lift is < 1 pp on at least 2 of the 3 Class-C-prone slices, OR (c) FAMA does not dominate ≥ 3 of 4 baselines on the temporal-forgetting subset.

## Technical Gap

The 2026 frontier (EverMemOS 92.3 % LoCoMo, SmartSearch 91.9 %, HyperMem 92.73 %, Synthius-Mem 94.37 %, HiGMem A-Mem-beating, APEX-MEM 88.88 %, MiCP arXiv 2604.01413, Stop-RAG arXiv 2510.14337, BMAM arXiv 2601.20465 4-way hybrid retrieval, MAGMA arXiv 2601.03236) addresses two adjacent problems but not the per-item rank-quality problem:

1. **Better retrieval architectures** (BMAM, MAGMA, HetaRAG): use multiple substrates but fuse via **Reciprocal Rank Fusion** — a ranking heuristic with no calibration and no item-level reliability score. Fusion is uniform across substrates, doesn't learn cross-substrate agreement is a *signal*.
2. **Better stopping rules** (MiCP, Stop-RAG, Conformal-RAG): operate at the *per-query decision* level (when to stop retrieving / when to answer). They do not produce per-item calibrated reliability — items get included in or excluded from the prediction set, but a "marginal" item gets the same treatment as a "clear" item.

**Why naive fixes are insufficient.**
- Heuristic learned reranker (cross-encoder over (q, item)) fixes ranking quality but produces **uncalibrated** scores → reader doesn't know how much to trust each item → over-specification persists (Class C).
- Static threshold over similarity scores fixes nothing → already what BM25 / semantic does.
- Per-query coverage (MiCP-style) → still permits "include this marginal item in the prediction set" → reader still over-specifies.

**Smallest adequate intervention.** A learned, per-item reranker over a small (~10) feature vector that fuses substrate signals, with **split-conformal calibration on item-level relevance labels** (not on per-query coverage). The reader is given top-k items each with a calibrated reliability score; the reader prompt is updated to *use only items above a calibrated threshold for the answer's load-bearing facts*. This is the smallest mechanism that addresses both Class B and Class C with one statistical object.

**Required minimum evidence.**
- Per-item coverage holds at 5 α values on Memora test (validates statistical claim).
- Top-k cleanliness lift on Class-C-prone slices (validates the over-specification fix).
- Cross-substrate agreement ablation drops Class-B-fix lift (validates that the agreement feature is the load-bearing signal for Class B).
- FAMA win on Memora (validates the new-benchmark angle).

## Method Thesis

- **One-sentence thesis.** *For each retrieved memory item, fuse semantic + lexical + claim-graph + raw-turn substrate signals into a learned reliability score and split-conformally calibrate it against held-out item-level relevance labels, so the reader receives a clean top-k with provable per-item coverage `Pr[item is gold-relevant | score ≥ τ̂_α] ≥ 1 − α` — addressing both reader over-specification (Class C) and wrong-content retrieval (Class B) without per-query abstention.*
- **Why this is the smallest adequate intervention.** It changes the *output type* of the retrieval layer (from unscored items to calibrated-score items) and the *reader prompt* (use load-bearing items above threshold), and nothing else. No new memory architecture, no new training objective beyond the reranker MLP (~10K params), no per-query stopping rule, no abstention. Frozen Path D substrate; frozen reader.
- **Why timely.** (a) Memora + FAMA dropped, providing a forgetting-aware metric none of the frontier has reported on. (b) The gating evidence (88.2 % B+C) gives a strong empirical case for read-side investment that none of the prior memory papers has done. (c) Conformal calibration at item level (not query level) is novel for memory and avoids both β's and Idea-1's failure modes. (d) Cross-substrate composition is the empirical fix for Class B that BMAM-style RRF doesn't capture.

## Contribution Focus

- **Dominant contribution.** *Per-item rank-quality calibration via split conformal* on a learned, multi-substrate, drift-aware reranker — the first memory operator with a coverage guarantee at the *retrieved-item* level (not per-query). Deployed transparently behind any reader; demonstrated on Path D substrate but applicable to A-Mem / Mem0 / LightMem / EverMemOS substrates by feature-vector adaptation.
- **Optional supporting contribution.** A *gating-evidence-grounded* error decomposition methodology (Class A/B/C/D) for memory systems — released as a script + 186-question reference labels. Useful for the field's future read-side method-design.
- **Explicit non-contributions.**
  - Not a new memory store.
  - Not a per-query abstention or stopping rule (MiCP / Stop-RAG / β own that).
  - Not a writer fine-tune (Memory-R1 / MemBuilder own that).
  - Not LoCoMo SOTA (parity claimed; structural-memory race over).
  - Not a benchmark contribution (Memora exists; the gating-decomposition methodology is in supplementary).

## Proposed Method

### Complexity Budget

- **Frozen / reused.** Path D's `ttmg/` substrate: claim graph (with supersede edges + validity intervals + `active` flag), `raw_turn_fallback` index, BM25 lexical index, `all-MiniLM-L6-v2` embedder. Reader = `deepseek-v3.2` (same as Path D pilot baseline). MAAS endpoints unchanged.
- **New (3 deltas, all small).**
  1. *Feature extractor* (`ttmg/rerank_features.py`, ~150 lines): per-(query, retrieved-item) feature vector of ~10 features (see §Feature Set below).
  2. *Learned reranker* (`ttmg/rerank_model.py`, ~80 lines): small MLP (input dim ~10, hidden 32, output 1 logit), trained to predict item-level relevance via cross-entropy.
  3. *Conformal calibration layer* (`ttmg/rerank_calibrate.py`, ~100 lines): split conformal on held-out item-level relevance labels; produces per-α threshold table `τ̂_α`.
- **Tempting additions intentionally not used.** No e-process / sequential testing (Idea 1's broken math). No per-query abstention rule (β's failure mode). No new memory writer / extractor (Diagnosing-Memory says ROI is read-side). No cross-encoder fine-tune (overshoots; MLP is enough). No per-question_type model (we use it as a reporting stratum, not a model split).

### Feature Set (~10 features per (query, item) pair)

| Feature | Source | Why |
|---|---|---|
| `semantic_sim(q, item.content)` | embedder cosine | Standard signal. |
| `lexical_sim_bm25(q, item.content)` | BM25 over raw turns | Captures named entities embedder misses. |
| `claim_graph_relevance(q, item.claim_id)` | cosine over claim representation; 0 if item is a raw-turn | Sub-substrate signal. |
| `supersede_edge_count(item)` | hard-supersede edges *into* this item | Drift signal for KU slice; downweight superseded. |
| `validity_interval_freshness(item, τ_q)` | `1` if `valid_at(item, τ_q)`, exponential decay otherwise | Time-validity signal. |
| `contradiction_count(item)` | hard-contradict edges incident to item | Noise signal; high → low rerank. |
| `time_volatility(item)` = `Δt_since_creation × topic_volatility(item.subject)` | drift score | Class-B fix on KU. |
| `cross_substrate_agreement(item)` = `1[item ∈ semantic_topk] + 1[item ∈ lexical_topk] + 1[item ∈ raw_turn_topk]` | binary across 3 substrates | **Primary Class-B fix**: items present in ≥ 2 substrates get a multiplicative boost. |
| `source_type` | one-hot of {raw-turn, claim, claim-with-supersede} | Lets the reranker learn substrate-prior. |
| `recency_baseline` = `Δt_since_creation` (raw, no volatility weighting) | raw recency | For ablation: distinguishes "drift-aware" from "just recency". |

### System Overview

```
            ┌────────────────────────────────────────────────────────────┐
WRITE-time  │  Path D pipeline (unchanged): writer → claims → linker →   │
            │  supersede edges → claim graph + raw-turn index            │
            └────────────────────────────────────────────────────────────┘

CALIBRATION (offline, one-time)
            ┌────────────────────────────────────────────────────────────┐
            │  Calibration set: item-level relevance labels              │
            │  - For each (q, item) pair across LongMemEval-S train +    │
            │    Memora train (40 % of train held back as cal split)     │
            │  - Label: `1` if item appears verbatim or near-paraphrase  │
            │    in answer-evidence sessions (`answer_session_ids`)      │
            │  - Class A questions (gating decomposition) excluded       │
            │                                                            │
            │  Train MLP reranker (~10K params, 5 epochs, BCE loss)      │
            │  → output logit s ∈ ℝ                                      │
            │                                                            │
            │  Split conformal on held-out cal-of-cal split:             │
            │  for each α ∈ {0.05, 0.10, 0.15, 0.20, 0.25}:              │
            │    τ̂_α = ⌈(n_cal+1)(1−α)⌉/n_cal -quantile of {s_i : y_i=1}│
            │  Lock τ̂ table; commit hash to git.                         │
            └────────────────────────────────────────────────────────────┘

INFERENCE
            ┌────────────────────────────────────────────────────────────┐
            │  query q → Path D retrieval gathers candidate set          │
            │  (semantic top-k ∪ lexical top-k ∪ claim top-k             │
            │   ∪ raw-turn top-k; ≤ 30 candidates)                       │
            │                                                            │
            │  For each candidate item:                                  │
            │    features = extract_features(q, item)                    │
            │    s = MLP(features)                                       │
            │    reliability ∈ {high, mid, low} per τ̂ table              │
            │      high   if s ≥ τ̂_0.10                                  │
            │      mid    if τ̂_0.20 ≤ s < τ̂_0.10                         │
            │      low    if s < τ̂_0.20                                  │
            │                                                            │
            │  Reader prompt receives:                                   │
            │    - top-3 high-reliability items as load-bearing context  │
            │    - top-3 mid-reliability items as supplementary context  │
            │    - reader instructed: "answer using only the load-bearing│
            │      items; supplementary may inform style/wording"        │
            │  → answer (no abstention rule; reader decides as before)   │
            └────────────────────────────────────────────────────────────┘
```

### Core Mechanism

- **Input.** A query `q` at time `τ_q`; the Path D retrieval candidate set (≤ 30 items: semantic top-10 ∪ lexical top-10 ∪ claim top-10 ∪ raw-turn top-10, deduplicated).
- **Output.** Per-item `(score s, reliability ∈ {high, mid, low})` ranked list, top-k by score.
- **Architecture / policy.** Feature extractor (deterministic Python) → MLP (input 10, hidden 32, output 1) → split-conformal threshold table lookup → 3-tier reliability label → reader prompt with load-bearing/supplementary split.
- **Training signal / loss.** Binary cross-entropy on item-level relevance labels (label = 1 iff item content appears verbatim / near-paraphrase in any answer-evidence session; LLM-judge auto-labels with manual audit on 50 dev samples).
- **Why this is the main novelty.** No surveyed competitor produces a *per-item calibrated reliability score*. BMAM (multi-substrate retrieval) uses RRF — uncalibrated, no agreement signal. MiCP / Stop-RAG (statistical stopping) operate at per-query decision level. Conformal-RAG calibrates per-claim factuality but not per-retrieved-item rank quality. The cross-substrate agreement feature is empirically motivated by gating evidence (Class B = 41 % of failures, exactly what cross-substrate voting fixes).

### Modern Primitive Usage

Three minimal LLM uses, all zero-shot or training-free except the MLP:

1. **Path D substrate** (already-built): writer + linker + parser + reader (LLM as structurer/judge). No change.
2. **Item-level relevance labeller** (LLM-as-judge, one-shot): for calibration set construction, an LLM-judge auto-labels each (query, item) pair as relevant / not relevant. Uses `deepseek-v3.2`. Validated on 50-dev manual audit (target ≥ 0.85 author-agreement).
3. **Reader prompt update** (no fine-tune): reader prompt is augmented with the load-bearing/supplementary distinction — minimal prompt-engineering change.

### Integration into Path D Pipeline

- **Files touched.** New: `ttmg/rerank_features.py`, `ttmg/rerank_model.py`, `ttmg/rerank_calibrate.py`, `scripts/calibrate_rerank.py`, `experiments/eval_calrr.py`. Modified: `ttmg/system.py` (add `enable_calrr` flag + integration hook in `answer()`).
- **Files frozen.** All Path D substrate (`schema.py`, `writer_temporal.py`, `conflict_linker.py`, `truth_retriever.py`, `graph.py`, `maas_client.py`, `baseline_amem.py`).
- **Inference order.** Same as Path D until the candidate set is built; then CalRR layer rescores; then the reader prompt with reliability tiers; then unchanged reader call.

### Training Plan

- **No model training beyond the MLP (~10K params).** MLP trains on a single CPU in < 5 min.
- **Calibration set construction.** 40 % of LongMemEval-S train (the dev side from Path D pilot is reusable) + 40 % of Memora train. Per-question, generate per-(query, item) pairs by retrieving the candidate set; auto-label each with LLM-judge; reserve a 10 % cal-of-cal split for the conformal threshold computation.
- **Split conformal.** Standard split CP. For each α ∈ {0.05, 0.10, 0.15, 0.20, 0.25}, `τ̂_α = ⌈(n_cal+1)(1−α)⌉/n_cal-quantile` of {`s_i` : `y_i = 1`} on cal-of-cal. Coverage guarantee: `Pr[gold-relevant | s ≥ τ̂_α] ≥ 1 − α` under exchangeability.
- **Acceptance gates** (before any test-time runs):
  - LLM-judge labelling agreement ≥ 0.85 vs author-manual on 50-q dev audit.
  - MLP dev-set AUC ≥ 0.75 on item-relevance prediction (binary).
  - Per-α dev-set coverage `r̂(τ̂_α)` ≤ α + 0.02 for all 5 α.
  - Locked `τ̂` table committed to git; commit hash printed in paper.

### Failure Modes and Diagnostics

- **F1 LLM-judge label noise.** Detect: dev audit < 0.85 agreement. Mitigate: 3-call self-consistency on judge; relabel low-agreement items.
- **F2 MLP underfits.** Detect: dev AUC < 0.7. Mitigate: increase hidden dim; add more features; check for label imbalance.
- **F3 Conformal coverage miss on test.** Detect: empirical `r̂(τ̂_α) > α + 0.04` for any α. Mitigate: re-calibrate with larger cal split; admit conditional-coverage failure if exchangeability fails (KS-test descriptive only, per round-3 lesson from β v2).
- **F4 Top-k cleanliness lift fails on Class-C-prone slices.** Detect: < 1 pp lift on single-session-user / KU / single-session-preference. Mitigate: tighten the τ̂_high threshold; check if the reader prompt's "load-bearing only" instruction is being respected via prompt audit.
- **F5 FAMA does not dominate.** Detect: paired-bootstrap fails on ≥ 3 of 4 baselines on Memora temporal-forgetting subset. Mitigate: tune reranker training to upweight `time_volatility` feature; if still failing, reframe as parity-with-guarantee.
- **F6 Cross-substrate agreement turns out not to be load-bearing.** Detect: `no_cross_substrate_agreement` ablation drops only ≤ 0.5 pp on Class B. Mitigate: this would mean the gating-evidence-driven design intuition is wrong; report honestly; the conformal calibration angle still stands as the dominant contribution.

### Novelty and Elegance Argument

- **Closest work.**
  - Conformal-RAG (arXiv 2506.20978) — calibrates *per-sub-claim factuality* on RAG output. We calibrate *per-retrieved-item rank quality* on memory retrieval. Different statistical object, different calibration target.
  - MiCP (arXiv 2604.01413) — multi-turn conformal stopping. Per-query decision, not per-item score.
  - Stop-RAG (arXiv 2510.14337) — RL stopping for iterative RAG. Per-query, not per-item, not statistical.
  - BMAM (arXiv 2601.20465) — 4-way hybrid retrieval with RRF fusion. Uncalibrated, no agreement signal.
  - HiGMem (arXiv 2604.18349) — hierarchical event-turn memory. Architectural, no calibration.
- **Exact difference.** Per-item rank-quality calibration via split conformal, with cross-substrate agreement as the empirically-motivated key feature — none of these neighbours has either (i) per-item conformal calibration or (ii) cross-substrate agreement as a load-bearing feature.
- **Why mechanism-level, not pile-up.** One MLP + one calibration table + one prompt update. Path D substrate frozen. Reader frozen. The contribution is summarisable in one inequality (the coverage guarantee above).

## Claim-Driven Validation Sketch

### Claim 1 (Dominant) — Per-item rank-quality coverage holds + Class-C-prone lift

- **Statement.** On Memora test, per-α coverage `r̂(τ̂_α) ≤ α + 0.02` for all 5 α ∈ {0.05, 0.10, 0.15, 0.20, 0.25}. On the 3 Class-C-prone LongMemEval-S slices (single-session-user / knowledge-update / single-session-preference), Path D reader fed CalRR's top-k shows ≥ 3 pp accuracy lift over the existing `raw_turn_fallback`-based top-k.
- **Minimal experiment.** 1 method (CalRR) × 3 seeds × 1 backbone (deepseek-v3.2) × Memora full test + LongMemEval-S full N=500. Cal on Memora train (60 % dev / 40 % cal-of-cal) + LongMemEval-S train.
- **Baselines / ablations.** Path D `ttmg`; CalRR full; ablations: `no_cross_substrate_agreement`, `no_drift_features` (drop time_volatility + supersede_edge_count + validity_interval_freshness), `no_conformal` (raw MLP scores).
- **Metric.** Per-α empirical coverage (rank-quality); Class-C-prone slice accuracy lift; full-set accuracy.
- **Expected evidence.** Coverage holds for all 5 α on Memora test. Class-C-prone slices: ≥ 3 pp lift; `no_cross_substrate_agreement` drops Class B specifically; `no_drift_features` drops KU specifically; `no_conformal` breaks coverage.

### Claim 2 (Supporting) — FAMA win on Memora + parity on LoCoMo

- **Statement.** On Memora full test, CalRR's aggregate FAMA strictly dominates A-Mem / Mem0 / LightMem / EverMemOS-on-Memora (paired-bootstrap p<0.05 over (persona × duration) clusters). On LoCoMo full, CalRR within 2 pp of best of (Path D, A-Mem, SmartSearch).
- **Minimal experiment.** 5 methods × 3 seeds × deepseek-v3.2 × Memora full test + LoCoMo full.
- **Baselines.** A-Mem reimpl, Mem0 (best-effort reproduce), LightMem (best-effort reproduce), EverMemOS (best-effort reproduce, appendix), SmartSearch (LoCoMo-only baseline).
- **Metric.** Aggregate FAMA per duration; cluster-bootstrap CIs; LoCoMo accuracy.
- **Expected evidence.** Memora-FAMA: CalRR > each of 4 baselines by ≥ 5 FAMA-points on temporal-forgetting subset. LoCoMo: parity.

(MAX_PRIMARY_CLAIMS = 2 honored.)

## Experiment Handoff Inputs

- **Must-prove claims.** (1) per-item conformal coverage at 5 α + Class-C-prone slice lift; (2) FAMA win on Memora + LoCoMo parity.
- **Must-run ablations.** `no_cross_substrate_agreement`, `no_drift_features`, `no_conformal` (3 ablations).
- **Critical datasets / metrics.** Memora train/test (calibration + headline FAMA); LongMemEval-S full N=500 (Class-C-prone slice + parity); LoCoMo full (parity); per-α Wilson UCB; cluster-bootstrap CIs.
- **Highest-risk assumptions.** (i) LLM-judge item-relevance labelling reaches ≥ 0.85 agreement on 50-q audit. (ii) Cross-substrate agreement is actually load-bearing for Class B. (iii) Memora calibration / test exchangeability holds (KS descriptive). (iv) MLP dev AUC ≥ 0.75 on item-relevance.

## Compute & Timeline Estimate

- **Compute.** ≈ **30 GPU-hour-equivalents** on 1–2× RTX-4090 budget. MAAS-only inference; no local training beyond the MLP (~5 min CPU).
- **Data / annotation cost.** Auto-label LLM-judge cost ≈ 8K items × 1 judge call ≈ 4 hr MAAS sequential + 1 hr author manual audit on 50 dev items.
- **Timeline.**
  - **Week 1.** Build feature extractor + MLP + calibration script. Auto-label calibration set on Memora train + LongMemEval-S train. Manual audit 50 items. Train MLP. Compute conformal table. Lock + commit hash. All intrinsic gates clear.
  - **Week 2.** Full Memora test runs (5 methods × 3 seeds). LongMemEval-S full N=500 (Path D + CalRR + 3 ablations × 3 seeds). LoCoMo full at seed=0 for {Path D, CalRR, SmartSearch}.
  - **Week 3.** Paper writing. Figures (per-α reliability plot with Wilson UCB band, Class-C-prone slice lift bar chart, ablation drops, FAMA bars with cluster-bootstrap CIs). Cite Conformal-RAG, MiCP, Stop-RAG, BMAM, HiGMem, Path D's underlying TTMG paper.

(End of round-0 initial proposal.)
