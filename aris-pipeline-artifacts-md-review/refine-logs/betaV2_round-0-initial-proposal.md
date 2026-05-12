# Pivot β — Research Proposal: Conformal-Calibrated Memory — Provable Abstention Coverage for Long-Conversation Agents under Forgetting

## Problem Anchor

- **Bottom-line problem.** When an LLM agent answers from accumulated long-conversation memory, two failures recur and no current method handles either with a guarantee:
  1. **Silent reliance on obsolete memory** — facts get updated, contradicted, or invalidated over weeks/months, but retrievers and readers still surface and trust them. The Memora benchmark with the new **FAMA** (Forgetting-Aware Memory Accuracy) metric (arXiv 2604.20006, 2026) measures this directly: long-term memory agents lose 18–30 pp from naive accuracy to FAMA, and the gap *grows* with timeline length.
  2. **Over-confident answering on contradictions** — when retrieved evidence disagrees on a single-slot value, every existing memory system (A-Mem 2025, Mem0, MemoryOS, LightMem 2025, SimpleMem 2026, EverMemOS 2026, SmartSearch 2026) returns *some* answer, none provides a coverage guarantee on the abstention decision.
- **Must-solve bottleneck.** The minimal mechanism a memory system needs but does not have: a *calibrated* read-time decision rule that gives an explicit, verifiable risk guarantee — `Pr[wrong | answered] ≤ α` — on the answer/abstain choice, validated end-to-end by a benchmark whose evaluation metric *itself* tracks the failure mode (FAMA).
- **Non-goals.** Not chasing LoCoMo SOTA (EverMemOS 92.3 %, SmartSearch 91.9 %) — the structural-memory race is over; we target parity, not headline. Not a token-efficiency paper. Not a new-benchmark paper (Memora exists). Not a write-time consolidation method (Diagnosing-Memory 2603.02473 shows write strategy contributes only 3–8 pp vs retrieval's 14–23 pp). Not a slot-in conflict layer for arbitrary memories (Path A, deferred).
- **Constraints.** 1–2 RTX-4090-class GPUs; MAAS API for writer/parser/reader/linker (no Agent tool); reuse `ttmg/{schema, writer_temporal, conflict_linker, truth_retriever, system}.py` as the substrate (the type-level + supersede + linker machinery built across rounds 0-4 of Path D). 3–4 weeks compute budget. NeurIPS / ICML main-track target.
- **Success condition (single dominant + one supporting + one diagnostic).**
  1. **Coverage guarantee** holds empirically on Memora dev split: across 5 conformal target levels α ∈ {0.05, 0.10, 0.15, 0.20, 0.25}, achieved error rate `Pr[wrong | answered]` ≤ α on the test split (paired-bootstrap CI excludes α + 0.02 in TTMG-β's favour).
  2. **FAMA win on Memora**: TTMG-β strictly dominates A-Mem, Mem0, LightMem, SimpleMem, EverMemOS (if its code runs) in *aggregate* FAMA (paired McNemar / cluster-bootstrap p<0.05 at the worst-case quartile-week level), driven by the conformal abstention layer minimising forgetting penalty.
  3. **Parity preservation** on LoCoMo and LongMemEval-S: TTMG-β within 2 pp of the best of (Flat, A-Mem, SmartSearch) on overall accuracy. We *do not* claim to beat EverMemOS or SmartSearch on these benchmarks.
  4. **Mechanism causality**: removing the conformal layer (`no_conformal`) eliminates the FAMA win and breaks the coverage guarantee; removing the PMI phase-diagram conditioner (`no_pmi`) shifts the regime where calibration earns its keep.
  5. **Failure clause.** The design fails if (a) the empirical coverage `Pr[wrong | answered]` exceeds α + 0.02 on the test split for 2 out of 5 α values, OR (b) FAMA aggregate does not show paired wins vs ≥3 of 5 baselines, OR (c) parity on LoCoMo / LongMemEval-S is breached by > 5 pp.

## Technical Gap (survey-grounded)

**A keyword scan of all 141 .tex files in `MemMachine/competitor/` returned zero matches in body text** for: *conformal*, *calibrat-* (in method context), *off-policy / importance sampling*, *mutual information*, *PAC*, *sequential test*, *Lagrang-*, *bandit*. This is a *structural* white-space — the entire 2023–2026 memory subfield uses no statistical / information-theoretic machinery. Meanwhile, the RAG community has the tools we need:

1. **Conformal-RAG (arXiv 2506.20978, SIGIR 2025).** Marginal CP on retrieval-grounded sub-claims:
   ```
   Score:        R(c) = max_j  CosineSim(q, d_j) · CosineSim(c, d_j)
   Calibrate:    S_i = inf{ q : ∀c ∈ F_q(ŷ_i), A(c, x_i, y_i*, D_i) = 1 }
   Threshold:    q̂ = ⌈(n+1)(1−α)⌉/n -quantile of {S_i}
   Guarantee:    Pr[ y* ⇒ y_test(x_test; q̂) ] ≥ 1 − α
   ```
   With Mondrian partitioning by group `g(x) ∈ G`, group-conditional. Reduced from 86.8 % → 8.9 % claim removal at 85 % factuality target on MedLFQA. **Directly retargetable** to memory: substitute "sub-claim factuality" with "memory slot temporal validity"; use TTMG's `Edge.hardness` (3-call linker agreement, already in code) as the score function.

2. **PMI-RAG (arXiv 2411.07773).** Pointwise mutual information as an unsupervised, frozen-LM relevance gauge:
   ```
   PMI(q, C) = log[ P(q | C) / P(q) ]
   ```
   Empirically affine to log-odds of answer correctness with `r > 0.8` across 5 LMs on NQ-Open / ELI5. **Directly retargetable**: PMI between query and memory-slot context predicts whether retrieved memory is "informative for the query"; gives a *training-free* condition that defines the regime where calibrated abstention strictly dominates hard thresholding.

3. **Swin-VIB (arXiv 2504.12982).** Variational information bottleneck on RAG knowledge conflicts:
   ```
   Loss_n = E[−log p_φ(Y | Z_n)] + β · KL(q_θ(Z_n | G_n) || N(0, I))
   p̂(q, ω^k) = (1/N) Σ_n p_φ_n(Y = 1 | G_n^k)
   ```
   Per-layer attention bottleneck classifier predicting whether two pieces of evidence disagree. **Directly retargetable** to "two memory claims for the same `claim_key` disagree on `object_norm`", giving a learned conflict-detection signal complementary to the conformal calibration.

4. **Diagnosing-Memory (arXiv 2603.02473, ICLR 2026 submission).** 3×3 factorial on LoCoMo: retrieval method spread = 20 pp; write strategy spread = 3–8 pp; retrieval precision correlates with accuracy at r = 0.98. **Architectural implication**: invest in inference-time calibration, not write-time elaboration — this is exactly the design choice Pivot β makes. We *cite this finding as motivation*, not as our own.

5. **Memora + FAMA (arXiv 2604.20006).** Long-term memory benchmark with explicit memory-trace ground truth (add/update/delete operations across weeks-to-months) and a metric:
   ```
   FAMA_q = presence_score(response, valid_slots@t_q) − α · forgetting_penalty(response, invalid_slots@t_q)
   ```
   Long-term memory agents (MemoBase, MemoryOS, Mem-0) drop 43.6 → 15.18 / 51.84 → 25.05 from week to quarter on the *remembering* axis. **No memory system has published FAMA scores yet**, including EverMemOS. Pivot β's contribution is to be the *first* memory paper with calibrated FAMA results.

**EverMemOS / SmartSearch scoop check.** EverMemOS already maintains validity intervals (`[t_start, t_end]` foresight) — so `valid_from / valid_to` per claim is *not* novel as of Jan 2026. SmartSearch shows deterministic retrieval reaches 91.9 % on LoCoMo — meaning the *system-level* novelty bar on LoCoMo is impossibly high. Both threats *force* the contribution to be on a different axis: a *guarantee* (conformal coverage) and a *new metric* (FAMA), neither of which EverMemOS or SmartSearch reports.

## Method Thesis

- **One-sentence thesis.** *For each retrieved memory subset relevant to a query, compute a hardness-weighted conformal-calibrated decision score; answer iff that score exceeds a per-group conformal threshold calibrated on a labelled supersede set; otherwise abstain — yielding a `Pr[wrong | answered] ≤ α` coverage guarantee that the entire memory subfield currently lacks.*
- **Why the smallest adequate intervention.** One new module on top of TTMG's existing pipeline: a *conformal calibration layer* over the linker's existing 3-call-agreement hardness scores, plus a PMI-based regime conditioner. No new training, no architecture, no auxiliary head. The substrate (claim schema with `valid_from / valid_to / object_norm`, canonical `claim_key`, agreement-hard typed edges, applicability gate) is already built across rounds 0-4 of Path D — Pivot β reuses it as engineering scaffolding, not as the contribution.
- **Why timely.** (i) Memora + FAMA just dropped; field will flock to it. (ii) The Diagnosing-Memory factorial published the architectural finding ("retrieval dominates") that motivates the design. (iii) Conformal prediction is mainstream in classical ML / RAG; its absence in memory is now a *structural* rather than *methodological* gap. (iv) EverMemOS hits 92.3 % LoCoMo without a guarantee — the next move *has* to be guarantees, not more accuracy.

## Contribution Focus

- **Dominant contribution.** A *conformal-calibrated read-time decision rule* for memory-augmented answering with empirically validated `Pr[wrong | answered] ≤ α` coverage on the abstention decision, at multiple α levels, on the new Memora benchmark with FAMA — the first memory operator with a coverage guarantee.
- **Optional supporting contribution.** A *PMI-based regime conditioner* (frozen-LM, training-free) that characterises when calibrated abstention strictly dominates hard-thresholded retrieval, presented as a phase diagram on the Memora dev split. Two coupled tools, one guarantee, one diagnostic — not a kitchen sink.
- **Explicit non-contributions.**
  - Not a LoCoMo / LongMemEval-S accuracy win (parity claimed, not headline).
  - Not a new memory architecture (we reuse TTMG's substrate).
  - Not a new benchmark (Memora exists).
  - Not a contribution about typed claim graphs, validity intervals, supersede edges, or applicability gates *in isolation* — EverMemOS already does the validity-interval part. Those are now *implementation substrate*; the *guarantee* is what we own.
  - Not a contribution about MWIS or canonical-key fetch.

## Proposed Method

### Complexity Budget

- **Frozen / reused substrate (built in Path D rounds 0-4).** TTMG schema with `(claim_key=(entity_id, slot_name), slot_type, object_norm, valid_from, valid_to, polarity, confidence, active, superseded_by)`, deterministic canonicalizer, 3-call-agreement linker producing `hardness ∈ {0/3, 1/3, 2/3, 3/3}` and label ∈ `{contradict, supersede, unrelated}`, `valid_to ← valid_from − ε` materialisation on hard supersede, applicability gate routing non-applicable queries to Flat fallback, canonical-key fetch on the applicable path. **All of this is engineering scaffolding for Pivot β, not contribution.**
- **New / extended (2 deltas only, both small).**
  1. *Conformal scoring layer.* Replace TTMG's all-optima MWIS abstention rule with a conformal coverage rule over the hardness-weighted candidate score. Implementation: 1 new ~80-line module `ttmg/conformal.py` doing calibration + threshold lookup + group-conditional Mondrian.
  2. *PMI regime conditioner.* For each applicable query at inference, compute `PMI(query, retrieved_context)` via a frozen-LM prefix probability call (one extra `/v1/completions` call per applicable query — `~150 ms` on `deepseek-v3.2`). Used both as an additional Mondrian group axis and as the x-axis of the phase-diagram diagnostic.
- **Tempting additions intentionally not used.** No fine-tuning of the linker (3-call agreement is the score; Brier already calibrated at this stage). No VIB (Swin-VIB-style learned conflict detector) — keeping the scope to *one* statistical machinery (conformal) + *one* information-theoretic gauge (PMI). No agentic multi-round retrieval (EverMemOS does this). No new MWIS / MaxSAT solver. No reranker. No backbone change beyond Path D's deepseek-v3.2 + Qwen3-30B-A3B robustness check.

### System Overview

```
            ┌────────────────────────────────────────────────────────────┐
            │  WRITE-time and RETRIEVE-time machinery: unchanged from    │
            │  Path D round-3 final (canonicalizer, 3-call linker,       │
            │  valid_to materialisation, applicability gate, canonical-  │
            │  key fetch, all-optima MWIS).                              │
            └────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
            ┌────────────────────────────────────────────────────────────┐
CALIBRATE   │  Inputs:                                                   │
(once,      │   - Calibration set Cal = {(q_i, t_i, M_i, y_i*)}_{i=1..n}│
offline,    │     drawn from Memora train + the controlled-supersede     │
before lock)│     slice built in Path D round 1                          │
            │   - Linker-hardness candidate score per query:             │
            │     S(q, M, ŷ) = max-weight independent-set weight on the  │
            │     hard-edge subgraph restricted to claim_key_q and       │
            │     valid_at(τ_q), weights = hardness × writer_conf        │
            │   - Mondrian groups g(q) ∈ {high-PMI, mid-PMI, low-PMI}    │
            │     × {KU, TR, abstention} × {single-trace, multi-update}  │
            │  For each group g:                                         │
            │     U_i^g = inf{ u : answer_g_at_u(q_i, M_i) = y_i* }      │
            │     τ̂_g(α) = ⌈(n_g + 1)(1−α)⌉ / n_g -quantile of {U_i^g}   │
            │  Lock {τ̂_g(α)} for α ∈ {0.05, 0.10, 0.15, 0.20, 0.25}     │
            │  Commit τ̂ table to git, hash printed in paper.             │
            └────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
            ┌────────────────────────────────────────────────────────────┐
INFERENCE   │  query q at t_q  →  parser → (claim_key_q, τ_q, applicable)│
            │  if not applicable → Flat fallback (unchanged)             │
            │  cand   = canonical-key-fetch(q) ∩ valid_at(τ_q)           │
            │  Opts   = max-weight independent sets on hard-edge subgraph│
            │  Vals   = ⋃ {c.object_norm : c ∈ I, I ∈ Opts}              │
            │  pmi_q  = PMI(q, concat(cand))    # one frozen-LM call    │
            │  g_q    = group(q, pmi_q, slot type, trace pattern)        │
            │  U_q    = group-conditional score (hardness, |Vals|, pmi_q)│
            │  if |Vals| == 1  AND  U_q ≥ τ̂_{g_q}(α):                   │
            │      return reader(q, any I in Opts, value=Vals.pop())     │
            │  else:                                                     │
            │      return ABSTAIN(reason="below_conformal_threshold",    │
            │                     U_q=U_q, τ̂=τ̂_{g_q}(α), pmi_q=pmi_q)   │
            └────────────────────────────────────────────────────────────┘
```

### Core Mechanism — the conformal score and the coverage guarantee

- **Score function** `U(q, M, t_q)`:
  ```
  U = w_hardness · mean( hardness(c) for c ∈ ⋃ Opts )
    + w_unique  · 1[|Vals| == 1]
    + w_pmi     · PMI(q, M_q)            # M_q = concat of canonical-fetch
  ```
  Initial weights: `(w_hardness, w_unique, w_pmi) = (0.5, 0.3, 0.2)`, dev-tuned on a 60-q held-out split. Calibrated thresholds `τ̂_g(α)` absorb miscalibration in the weights — exact weight choice is not load-bearing.
- **Calibration set construction.**
  - Source: Memora *training* split (where `(t, valid_slots, invalid_slots)` ground truth is available) + the 250-q two-stratum controlled supersede slice built in Path D round 1.
  - For each `(q_i, t_i, M_i, y_i*)`, run the inference pipeline to obtain a candidate answer; compute `U_i`; record whether the answer matches `y_i*` (or whether abstention was correct given `valid_slots`).
  - Define `U_i^g = inf{ u : answer-at-threshold-u (q_i, M_i) is correct }` for each Mondrian group `g`.
- **Threshold lookup.**
  - For each `(g, α) ∈ G × {0.05, 0.10, 0.15, 0.20, 0.25}`, compute `τ̂_g(α) = ⌈(n_g + 1)(1−α)⌉/n_g`-quantile of `{U_i^g}`. Lock the table; commit to git; hash printed in paper. No test-time tuning.
- **Coverage guarantee.** Standard split-conformal result: under exchangeability of the calibration set with the test set,
  ```
  Pr[ wrong | answered, group = g ] ≤ α
  ```
  for each group `g`, marginalised over the test distribution. Reported per group and aggregated.
- **PMI estimator.** Frozen `deepseek-v3.2` prefix probability:
  ```
  PMI(q, M_q) = log [ P_lm(q | M_q) / P_lm(q) ]
  ```
  computed via two completion-API calls returning logprobs (one with `M_q` prepended, one without). Cost: ~300 ms × 2 ≈ 0.6 s extra per applicable query. Used to define Mondrian groups (3-quantile binning on calibration set) and as a continuous diagnostic axis for the phase diagram.
- **Why this is the main novelty.** No memory paper offers a coverage guarantee on the abstention decision. EverMemOS hard-filters by foresight intervals (no guarantee, no calibration). SmartSearch deterministic-thresholds (no guarantee). Mem0 / A-Mem / LightMem / SimpleMem use heuristic confidences. Conformal-RAG offers the guarantee in *RAG response quality* but not in *memory abstention*; we retarget. PMI as a regime conditioner is similarly retargeted from PMI-RAG (where it predicts answer correctness) to memory (where it characterises the regime in which calibration earns its keep).

### Modern Primitive Usage

Two LLM uses on top of the Path D substrate, both already in the existing MAAS budget:
1. **PMI estimator** (frozen-LM prefix probability — *no additional model*).
2. **Linker** (already 3-call agreement; we reuse the hardness as the calibration score input — *no change to the linker*).

Plus the calibration step is *one-shot, offline*, before any test-time runs. The whole conformal layer is `~80 lines` of Python plus the calibration script.

### Integration into the Existing Pipeline

- **Files touched.** `ttmg/truth_retriever.py` (replace all-optima-MWIS-abstention with the conformal threshold rule); NEW `ttmg/conformal.py` (~80 lines; calibration + threshold lookup + Mondrian group routing); NEW `scripts/calibrate_conformal.py` (~120 lines; runs over Memora train + controlled slice; produces locked `τ̂_g(α)` table); minor `ttmg/system.py` additions for PMI computation toggle and conformal-on/off flag.
- **Files frozen.** Path D's `schema.py`, `writer_temporal.py`, `conflict_linker.py`, `canonicalize.py` (all built in rounds 0-4) — these are now substrate, not contribution.

### Training Plan

There is no training. Calibration is offline, one-shot. Acceptance gates *before* test-time runs (in addition to all Path D gates):
- **Calibration coverage on dev split**: per-group empirical coverage `Pr[wrong | answered, g]` ≤ α + 0.02 for all 5 α values on a held-out portion of the calibration set (40 % of Memora train).
- **PMI estimator stability**: `r ≥ 0.7` correlation between PMI estimate and answer log-odds on the calibration set, mirroring PMI-RAG's headline number.
- **Calibration-to-test exchangeability check**: KS-test between calibration-set group distribution and Memora-test-set group distribution, p > 0.05.

### Failure Modes and Diagnostics

- **C1 Calibration miscoverage on Memora test.** Detect: per-group empirical coverage exceeds α + 0.02 on test split. Mitigate: (a) widen Mondrian groups (coarser binning); (b) re-calibrate with a larger calibration sample; (c) admit conditional-coverage failure and fall back to marginal-coverage claim only.
- **C2 PMI signal collapses on memory slots (vs RAG documents).** Detect: dev correlation `r < 0.5` between PMI and answer log-odds. Mitigate: drop PMI from the score function (use `(w_hardness, w_unique) = (0.7, 0.3)` only); the PMI phase-diagram diagnostic becomes a negative result.
- **C3 FAMA win does not materialise.** Detect: paired-bootstrap on Memora dev shows TTMG-β not strictly dominating ≥3 of the 5 baselines. Mitigate: tighten the conformal α (sacrifice answer rate for forgetting penalty); if still failing, reframe as "first calibration-on-memory paper, FAMA no-worse-than baselines, but coverage guarantee verified" (smaller paper, workshop track).
- **C4 EverMemOS code does not run / not reproducible.** Detect: README and code in `competitor/2601.02163_EverMemOS/code` fail to install or to reproduce within 5 pp of the paper's LoCoMo number. Mitigate: cite EverMemOS's published numbers, run paired comparisons on Memora only (where neither side has published numbers yet, eliminating reproduction-bias risk).
- **C5 Calibration-set drift.** Detect: KS-test fails between calibration and test groups. Mitigate: re-calibrate with stratified resampling; report as a Memora-distribution-shift section.
- **C6 Diagnosing-Memory's 'retrieval dominates' finding does not hold on Memora.** Detect: per-cell ablation on Memora reveals write-strategy is more important than on LoCoMo. Mitigate: report honestly; this is a benchmark-property finding, not a TTMG-β failure.

### Novelty and Elegance Argument

- **Closest work.** Conformal-RAG (SIGIR 2025) — conformal coverage on RAG sub-claims; PMI-RAG — PMI as a frozen-LM correctness gauge; EverMemOS (Jan 2026) — structured memory with foresight intervals and 92.3 % LoCoMo SOTA; SmartSearch (Feb 2026) — deterministic retrieval with 91.9 % LoCoMo.
- **Exact difference.** Conformal-RAG operates on RAG *sub-claim factuality* using cosine-similarity scores; we operate on *memory slot temporal validity* using a 3-call-agreement-hardness score over a typed conflict graph at time `τ_q`, with Mondrian groups defined by PMI bin × slot type × trace pattern. The calibration set is *labelled supersede* + *Memora memory traces*, which exist nowhere else in the memory subfield. EverMemOS hard-filters by foresight intervals (no guarantee, fixed threshold); we calibrate dynamically per-group and produce `Pr[wrong | answered] ≤ α`. SmartSearch uses a deterministic ranker (no guarantee, no group-conditional behaviour); our coverage guarantee holds at the test distribution under exchangeability. PMI-RAG uses PMI to *select context permutations*; we use PMI to *characterise the regime* in which calibrated abstention strictly dominates hard thresholding, presented as a phase diagram.
- **Why mechanism-level (statistical), not architectural pile-up.** One conformal layer + one PMI estimator + a calibration script. The contribution is the *guarantee*, not the architecture. The paper's result is summarisable in one inequality:
  ```
  Pr[ TTMG-β answers wrong | TTMG-β answered, group = g ] ≤ α   for all α ∈ {0.05, ..., 0.25}, all g ∈ G
  ```
  validated empirically on Memora test, in a memory subfield where no other system offers any such guarantee.

## Claim-Driven Validation Sketch

### Claim 1 (Dominant) — Coverage guarantee + FAMA win on Memora

- **Statement.** On Memora test (held-out from calibration), TTMG-β's *empirical* per-group coverage `Pr[wrong | answered, g]` ≤ α + 0.02 for all 5 α ∈ {0.05, 0.10, 0.15, 0.20, 0.25} and all groups g ∈ G; aggregated FAMA strictly dominates A-Mem, Mem0, LightMem, SimpleMem, EverMemOS-if-runnable on the worst-case quartile-week level (cluster-bootstrap p<0.05).
- **Minimal experiment.** 6 methods × 3 seeds × 1 backbone (deepseek-v3.2) × Memora full test (≈ persona-task-duration grid). Calibration on Memora train + Path D's controlled slice.
- **Baselines / ablations.** Flat hybrid-RAG; A-Mem reimpl; Mem0; LightMem; SimpleMem; EverMemOS (best-effort reproduction from `competitor/2601.02163_EverMemOS/code`); TTMG-β full; ablations: `no_conformal` (revert to Path D's all-optima MWIS abstention), `no_pmi` (drop PMI from score and Mondrian groups), `no_groups` (marginal CP only, no Mondrian).
- **Metric.** Per-group empirical coverage @ each α; aggregate FAMA; per-task / per-duration FAMA breakdown; abstention rate; cluster-bootstrap CIs over (persona × duration) clusters.
- **Expected evidence.** Coverage holds for all (g, α). FAMA: TTMG-β > each of {A-Mem, Mem0, LightMem, SimpleMem, EverMemOS} by ≥ 5 FAMA-points aggregate. `no_conformal` breaks coverage and loses FAMA. `no_pmi` produces miscoverage on the high-PMI group only (the regime where calibration most matters). `no_groups` violates per-group coverage but preserves marginal coverage — proving Mondrian's necessity.

### Claim 2 (Supporting) — Parity preserved on LoCoMo + LongMemEval-S; PMI phase diagram delineates calibration's regime

- **Statement.** On LoCoMo and LongMemEval-S (both N=500, 3 seeds, deepseek-v3.2), TTMG-β within 2 pp of the best of (Flat, A-Mem, SmartSearch) on overall accuracy. PMI phase diagram on Memora dev: the gap (TTMG-β FAMA − best baseline FAMA) increases monotonically with PMI-bin index, with the largest gap in the high-PMI bin — empirically delineating the regime where calibrated abstention strictly dominates hard thresholding.
- **Minimal experiment.** 6 methods × 3 seeds × 1 backbone × {LoCoMo full, LongMemEval-S N=500}. Plus PMI-grouped breakdown of Claim-1 results on Memora dev.
- **Baselines / ablations.** Same as Claim 1 plus SmartSearch (deterministic baseline, expected to score 91-92 % on LoCoMo).
- **Metric.** Per-benchmark overall accuracy; paired McNemar TTMG-β vs each baseline (we expect *not significant*, i.e. parity); PMI-bin FAMA gap with bootstrap CIs.
- **Expected evidence.** Parity: TTMG-β within 2 pp of best baseline. Phase diagram: monotone increasing FAMA gap with PMI bin; largest gap in high-PMI bin. *We do not claim a LoCoMo / LongMemEval-S win.*

(MAX_PRIMARY_CLAIMS = 2 honored.)

## Experiment Handoff Inputs

- **Must-prove claims.** (1) per-group conformal coverage at 5 α values + FAMA paired wins on Memora; (2) parity on LoCoMo / LongMemEval-S + PMI phase diagram.
- **Must-run ablations.** `no_conformal`, `no_pmi`, `no_groups` (3, all on Memora test).
- **Critical datasets / metrics.** Memora train (calibration) + Memora test (evaluation); Path D's controlled supersede slice (joins calibration set); LoCoMo + LongMemEval-S full N=500 (parity); per-group empirical coverage; aggregate + per-task / per-duration FAMA; PMI-bin FAMA gap with bootstrap CIs; abstention rate per group.
- **Highest-risk assumptions.** (i) `Edge.hardness` from the 3-call-agreement linker (Path D round 1) is calibrated enough to be a useful conformal score input. (ii) PMI on memory-slot context behaves comparably to PMI on RAG documents (PMI-RAG `r > 0.8` reproduces approximately on Memora). (iii) Memora train / test split is exchangeable enough that conformal coverage holds. (iv) EverMemOS reproduces within 5 pp of its published numbers from `competitor/.../code`. (v) Diagnosing-Memory's "retrieval dominates" finding generalises from LoCoMo to Memora.

## Compute & Timeline Estimate

- **Compute.** All inference via MAAS API; no local training. Total ≈ **45 GPU-hour-equivalents** on a 1–2× RTX-4090 budget (Path D was 30; Pivot β adds Memora full test + EverMemOS reproduction + PMI calls, partially offset by dropping the secondary backbone for everything except parity).
- **Data / annotation cost.** Use Memora-supplied memory-trace ground truth (no fresh annotation); Path D's controlled slice + 60-q dev split already exist.
- **Timeline.** Wk 1: pull Memora train/test data; integrate conformal layer; wire PMI estimator; run all calibration-stage intrinsic gates (coverage on dev, PMI `r ≥ 0.7`, exchangeability KS); lock `τ̂_g(α)` table + commit hash. Wk 2: full Memora test runs for 6 methods × 3 seeds (TTMG-β + 5 baselines); LoCoMo + LongMemEval-S parity runs; reproduce EverMemOS from its `code/`. Wk 3: 3 ablations on Memora; PMI phase diagram; statistical hardening (cluster-bootstrap CIs over persona × duration). Wk 4: paper rewrite framing the contribution as *the first calibrated memory operator with coverage guarantee*; figures (per-group coverage plot at 5 α, FAMA comparison bars with CIs, PMI phase diagram, ablation drop bars); reconcile prior `STATUS.md`; cite EverMemOS, SmartSearch, Diagnosing-Memory, Memora, Conformal-RAG, PMI-RAG.

(End of round-0 initial proposal for Pivot β.)
