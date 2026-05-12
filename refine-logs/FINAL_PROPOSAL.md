# FINAL PROPOSAL: CalLB — Calibrated Load-Bearing Evidence Selection for Long-Conversation Memory

**Status:** READY (round-4 score 9.0/10) — proceed to `/experiment-plan` handoff.
**Reviewer:** GPT-5.4 xhigh via Codex MCP. Refinement trajectory: 6.7 (RETHINK) → 7.6 (REVISE) → 8.5 (REVISE) → **9.0 (READY)**.
**Reviewer thread ID:** `019dcdd2-8a56-7c51-8017-9ac14ad3038e`.
**Date:** 2026-04-27.

## Problem Anchor (immutable across all 4 rounds)

- **Bottom-line problem.** When an LLM agent answers from accumulated long-conversation memory, the *reader* commits two systematic errors that no current 2026 system addresses with a calibrated mechanism: (i) **over-specification** — after correctly grounding on the right evidence, it pads the answer with adjacent, unsupported details (47 % of Path D's wrong answers on LongMemEval-S); (ii) **wrong-content retrieval** — surfacing the wrong session/turn even though the right evidence exists in the haystack (41 % of wrong answers). Together these two reader-side failures account for **88.2 % of Path D's wrong answers**, empirically rejecting the "writer is the bottleneck" hypothesis. Source: gating decomposition over 186 wrong answers in `results/gating_decomposition.json` (2026-04-27).
- **Must-solve bottleneck.** A mechanism that simultaneously (a) reduces *Class B* (wrong-content retrieval) by exploiting cross-substrate signal fusion (not just agreement count, also singleton-raw-turn and entity-overlap signals so low-consensus correct facts are not lost), and (b) reduces *Class C* (over-specification) by giving the reader a **clean** load-bearing tier with high probability — not just a tier with bounded average contamination, but a tier with a calibrated bound on *the probability of any distractor being present*.
- **Non-goals.** Not a new memory architecture. Not a write-time pipeline. Not LoCoMo accuracy SOTA. Not a per-query abstention rule. Not a writer-fine-tune project.
- **Constraints.** 1–2 RTX-4090; MAAS API for writer/reader/judge (`deepseek-v3.2`, `Kimi-K2`, `glm-5.1`); 3 weeks; reuse `ttmg/` substrate; NeurIPS / ICML main-track target; shared-host load varies → default sequential MAAS.

## Method Thesis

> *For each retrieved memory item, fuse semantic + lexical + claim-graph + raw-turn substrate signals into a learned reliability score; calibrate a single threshold `λ̂_α` via **Conformal Risk Control on the clean-set indicator risk** so that with probability ≥ 1 − α, the load-bearing tier `L_λ̂_α(q) = {item : score ≥ λ̂_α}` contains **no distractor**; expose `L` and `S = top-3 \\ L` to the reader as separate tiers, instructed to use only `L` for load-bearing facts.*

The contribution is a **calibrated probabilistic clean-set guarantee on the reader-visible load-bearing context** — empirically motivated by 88.2 % B+C gating evidence on a 2026-frontier system — addressing both wrong-content retrieval (Class B, via multi-substrate signal fusion) and reader over-specification (Class C, via probabilistic distractor exclusion).

## Contribution Focus

- **Dominant contribution.** *Calibrated probabilistic clean-set guarantee on the reader-visible load-bearing evidence tier* via Conformal Risk Control (CRC) with a clean-set indicator risk — the first memory operator with such a guarantee.
- **Optional supporting contribution.** Gating-evidence-grounded error decomposition methodology (Class A/B/C/D) for memory systems — released as a script + 186-question reference labels.
- **Explicit non-contributions.** Not a new memory store, not a per-query stopping rule (MiCP / Stop-RAG own that), not a writer fine-tune (Memory-R1 / MemBuilder own that), not LoCoMo SOTA, **not substrate-agnostic** (TTMG-coupled; portable subset bounded by ablation).

## Proposed Method

### Complexity Budget

- **Frozen / reused.** Path D's `ttmg/` substrate: claim graph (with supersede edges + validity intervals + `active` flag), `raw_turn_fallback` index, BM25 lexical index, `all-MiniLM-L6-v2` embedder. Reader = `deepseek-v3.2`. MAAS endpoints unchanged.
- **New (3 deltas, all small).**
  1. *Feature extractor* (`ttmg/lb_features.py`, ~150 lines): per-(query, item) feature vector of 13 features.
  2. *Learned reranker* (`ttmg/lb_model.py`, ~80 lines): MLP (input 13, hidden 32, output 1 logit), trained to predict `P(load-bearing)` via cross-entropy on 3-tier labels collapsed to binary `1[label = LB]`.
  3. *CRC calibration layer* (`ttmg/lb_crc.py`, ~120 lines): Clopper-Pearson UCB on 100-pt λ-grid + union bound; produces per-α threshold `λ̂_α`.
- **Tempting additions intentionally not used.** No e-process / sequential testing (Idea 1 broken math). No per-query abstention (β failure mode). No new memory writer (gating says writer is 11 % bottleneck, not 70 %). No cross-encoder fine-tune (overshoots; MLP is enough). No per-question_type model (used as reporting stratum, not model split).

### Feature Set (13 features: 5 portable + 3 robustness + 5 TTMG-specific)

| Group | Feature | Source | Why |
|---|---|---|---|
| **Portable** | `semantic_sim(q, item.content)` | embedder cosine | Substrate-agnostic. |
| **Portable** | `lexical_sim_bm25(q, item.content)` | BM25 over raw turns | Substrate-agnostic. |
| **Portable** | `cross_substrate_agreement(item)` | #substrates ∈ {sem, lex, raw, claim} containing item in their top-k | One signal among many (de-risked from R2 narrative). |
| **Portable** | `recency_baseline` = `Δt_since_creation` | raw recency | Ablation control. |
| **Portable** | `source_type` | one-hot {raw-turn, structured-claim} | Substrate prior. |
| **Robustness** | `max_substrate_score(item)` | max over 4 normalized substrate scores | Rescues low-agreement-but-strong-single-substrate items. |
| **Robustness** | `singleton_raw_turn_hit(item)` | 1 if item ∈ raw-turn top-k AND ∉ any other substrate top-k | Directly protects gating example "I've got three of them". |
| **Robustness** | `entity_overlap(q, item.content)` | spaCy NER overlap, normalized | Catches lexical-entity matches BM25 misses. |
| **TTMG-specific** | `claim_graph_relevance(q, item.claim_id)` | cosine over claim representation; 0 if raw-turn | Sub-substrate signal. |
| **TTMG-specific** | `supersede_edge_count(item)` | hard-supersede edges *into* this item | Drift signal for KU slice. |
| **TTMG-specific** | `validity_interval_freshness(item, τ_q)` | `1` if `valid_at(item, τ_q)`, exp decay | Time-validity. |
| **TTMG-specific** | `contradiction_count(item)` | hard-contradict edges incident to item | Noise signal. |
| **TTMG-specific** | `time_volatility(item)` = `Δt_since_creation × topic_volatility(item.subject)` | drift score | Class-B fix on KU. |

The `portable_features_only` ablation uses 8 features (5 portable + 3 robustness, no TTMG-specific) — bounds the substrate-agnostic part of the contribution.

### 3-tier Label

Per (query, candidate item) pair: `label ∈ {LB, S, D}`.

- **LB** (load-bearing): removing the item from reader's context would likely change the answer's correctness. Necessary evidence.
- **S** (supporting): topically related but unnecessary; safe to include.
- **D** (distractor): would actively mislead the reader (wrong entity, off-topic but tempting, near-paraphrase that mentions wrong entity, confounding adjacent context that invites over-specification).

**LLM-judge prompt** (deepseek-v3.2):
```
GIVEN:
  - Question: {q}
  - Gold answer: {gold}
  - Candidate retrieved item: {item.content}

Classify the item:
(A) LOAD-BEARING — necessary evidence; removing it likely breaks the answer.
(B) SUPPORTING — topically related but unnecessary; safe to include.
(C) DISTRACTOR — would actively mislead the reader.

Return strict JSON:
{ "label": "LB" | "S" | "D",
  "rationale": "one sentence",
  "confidence": "high" | "low" }
```

**Validation gate** (intrinsic, before any test runs):
- **100-q stratified audit** with 30 % oversampling of `confidence=low` (borderline) cases.
- Cohen's **κ ≥ 0.7** on full 3-class agreement (gate; 0.65–0.7 → 3-call self-consistency + re-audit; below 0.65 → fall back to binary `LB` vs `not-LB`).
- D-vs-non-D binary agreement: **κ ≥ 0.75** (the risk depends only on D detection).
- Full 3×3 confusion matrix + class-conditional precision/recall for D reported in paper.

### CRC Math (Clopper-Pearson exact binomial UCB)

**Risk function (clean-set indicator).**
```
L_λ(q) = { item ∈ candidates(q) : MLP_score(item) ≥ λ }
R(λ; q) = 𝟙[ ∃ item ∈ L_λ(q) with label = D ]   ∈ {0, 1}
R(λ)    = E_q[R(λ; q)] = Pr_q[L_λ(q) contains any distractor]   ∈ [0, 1]
```

Monotone non-increasing in λ for each q (and hence on average), since `L_{λ_2} ⊆ L_{λ_1}` for `λ_1 ≤ λ_2`.

**Theorem (Clopper-Pearson CRC, validated by reviewer R4).**

> Fix a λ-grid `Λ = {λ_1, ..., λ_m}` with m = 100 chosen *independently* of the calibration sample. For each `λ_j ∈ Λ`, let `R̂(λ_j) = (1/n_cal) Σ_{q ∈ cal} R(λ_j; q)` and let `U_j = U_{CP}(R̂(λ_j); n_cal, δ/m)` be the **one-sided Clopper-Pearson upper bound** on the Bernoulli mean at confidence `1 − δ/m`.
>
> Define `λ̂_α = inf { λ_j ∈ Λ : U_j ≤ α }` (= +∞ if no λ_j satisfies).
>
> Under exchangeability of cal and test queries:
> ```
> Pr_{cal split} [ R(λ̂_α) ≤ α ] ≥ 1 − δ
> ```
> where the outer probability is over the random calibration split, and `R(λ̂_α) = Pr_{q ∼ test}[L_λ̂_α(q) contains any distractor]` is the test-time clean-set failure probability.

**Two clean confidence levels.**
- `1 − δ = 0.95`: confidence over the random calibration split (split-conformal level).
- `1 − α`: clean-set probability over test queries given the chosen threshold (headline α* = 0.20).

**Tightness.** At n_cal = 600, δ/m = 0.0005:
- Hoeffding slack: ≈ 0.083 (constant, data-independent).
- **Clopper-Pearson at `R̂ = 0.05`: UCB ≈ 0.078** (slack 0.028, much tighter at small risks).
- CP at `R̂ = 0.20`: UCB ≈ 0.245 (slack 0.045).

This makes α = 0.10 **actionable** (need `R̂ ≤ ~0.04` to certify) and α = 0.20 comfortable.

### Non-vacuity / Utility Metrics on L (mandatory reporting)

The clean-set guarantee is vacuously satisfied if L is empty. Pre-committed reporting:

| Metric | Definition | Headline target (α* = 0.20) | Failure |
|---|---|---|---|
| `non_empty_fraction(L)` | Pr_q[\|L\| ≥ 1] | **≥ 0.85** | < 0.70 → vacuous, F2 |
| `mean_size(L)` | E_q[\|L\|] | **∈ [2, 5]** | < 1.0 → too aggressive |
| `LB_recall(L)` | Pr_q[L contains ≥ 1 LB-labelled item] | **≥ 0.75** | < 0.50 → mis-trained, F2 |
| `LB_precision(L)` | E_q[#LB / max(1,\|L\|)] | descriptive | — |
| mean distractor fraction in L | descriptive (was R2's risk) | descriptive | — |

### System Overview

```
WRITE-time  (UNCHANGED): writer → claims → linker → supersede edges
                         → claim graph + raw-turn index

CALIBRATION (offline, one-time):
  Stratified-subsample 10K (q, item) pairs from
    2K queries × ~30 candidates each (40 % LongMemEval-S train + 40 % Memora train)
  Auto-label each pair {LB, S, D} via LLM-judge (deepseek-v3.2)
    Manual audit on 100 stratified-borderline pairs; κ ≥ 0.7 (3-class), κ ≥ 0.75 (D-vs-non-D)
  Train MLP: input 13 features → hidden 32 → output 1 logit
    Loss: BCE on `1[label = LB]`; 5 epochs; Adam LR 1e-3; 80/20 query-split (no leakage)
  Hold out 30 % of cal queries (~600) → cal-of-cal
  For each α ∈ {0.10, 0.20, 0.30, 0.40}:
    For each λ_j on 100-pt grid: compute R̂(λ_j) and U_j = U_CP(R̂; 600, 0.05/100)
    λ̂_α = inf { λ_j : U_j ≤ α }
  Lock λ̂ table; commit hash to git; print in paper.

INFERENCE:
  query q at time τ_q
    → Path D retrieval gathers candidate set (≤ 30 items)
  For each candidate:
    features = extract_features(q, item)        # 13 features
    s = MLP(features)
  Tier at headline α* = 0.20:
    L = { item : s ≥ λ̂_0.20 }                   # load-bearing (clean tier w.p. ≥ 80%)
    S = top-3 not in L, ranked by s              # supporting fallback
  Reader prompt (minimal augmentation):
    [LOAD-BEARING] (use these for the answer's load-bearing facts):
      {L items}
    [SUPPORTING] (background only; do not use as load-bearing):
      {S items}
    "Answer using ONLY load-bearing items for the answer's facts. Do not
     include details only present in supporting items unless directly asked."
  → reader call (UNCHANGED model: deepseek-v3.2; no abstention rule)
```

### Integration

- **Files touched.** New: `ttmg/lb_features.py`, `ttmg/lb_model.py`, `ttmg/lb_crc.py`, `scripts/calibrate_lb.py`, `scripts/audit_judge_labels.py`, `experiments/eval_callb.py`. Modified: `ttmg/system.py` (add `enable_callb` flag + tiered-prompt path in `answer()`).
- **Files frozen.** All Path D substrate (`schema.py`, `writer_temporal.py`, `conflict_linker.py`, `truth_retriever.py`, `graph.py`, `maas_client.py`, `baseline_amem.py`).

## Baselines & Ablations

### External baselines (mandatory)

| Baseline | What | Where |
|---|---|---|
| Path D `ttmg` | Existing reader on same substrate, no CalLB | LME-S, Memora |
| MiCP-on-Path-D | MiCP per-query stopping ported to candidate set | LongMemEval-S |
| Stop-RAG-on-Path-D | Stop-RAG iterative retrieval + RL stop ported | LongMemEval-S |
| Flat hybrid-RAG | Sem + lex RRF, no claim-graph | LongMemEval-S |
| A-Mem | Reimpl from `competitors/A-mem-main` | Memora |
| Mem0 | Best-effort reproduce | Memora |
| LightMem | Best-effort reproduce | Memora |
| EverMemOS | Best-effort reproduce, **appendix only** | Memora (if Memora-port available) |
| SmartSearch | LoCoMo-only | LoCoMo |

### Attribution baselines (mandatory)

| Ablation | Definition | Tests |
|---|---|---|
| `prompt-only` | Path D's existing top-k + same load-bearing prompt; no MLP/CRC | Whether prompt restructuring is the real driver |
| `rerank-only` | CalLB MLP ranking; flat reader prompt (no tiering) | Whether tiering is what addresses Class C |
| `agreement-heuristic-only` | No MLP; rank by agreement count + sem-sim tiebreak; load-bearing prompt | Whether learned MLP is necessary |
| `no_CRC` (REDEFINED) | Same MLP scores + dev-tuned fixed threshold | Whether CRC adds value beyond reranking |

### Mechanism ablations (3) + Generality ablation (1)

| Ablation | Definition | Tests |
|---|---|---|
| `no_cross_substrate_agreement` | MLP without `cross_substrate_agreement` | Class-B fix attribution |
| `no_drift_features` | MLP without {time_volatility, supersede_edge_count, validity_interval_freshness, contradiction_count} | KU slice attribution |
| `no_robustness_features` | MLP without {max_substrate_score, singleton_raw_turn_hit, entity_overlap} | Whether new robustness features rescue low-agreement Class B |
| `portable_features_only` | MLP with only 5 portable + 3 robustness = 8 features | Substrate-agnostic part of contribution |

**Total ablations: 8** (4 attribution + 3 mechanism + 1 generality).

### Pre-registered Class-B-rescue analysis (committed in advance)

On the **77 Class-B examples** in `results/gating_decomposition.json`:

1. Run CalLB-augmented Path D reader; measure how many become correct.
2. For each rescued question, classify the rescuing item by `cross_substrate_agreement` count and `singleton_raw_turn_hit` flag.
3. Report fractions:
   - High-agreement rescues (count ≥ 3): if > 50 %, agreement is the load-bearing mechanism.
   - Low-agreement (count ≤ 1) AND `singleton_raw_turn_hit = 1`: if > 30 %, robustness features are critical.
   - Low-agreement, no singleton-hit: if > 30 %, MLP learns subtle weights — agreement narrative wrong.
4. **Reframing trigger.** If high-agreement rescues are < 30 % of total rescues, paper positioning shifts from "cross-substrate agreement is the Class-B fix" to "learned multi-substrate signal fusion is the Class-B fix".

## Acceptance Logic for Main-Track Submission (PRE-COMMITTED)

CalLB is accepted as a NeurIPS / ICML main-track contribution **iff at least one of**:

- **Path (A) — Downstream lift over fixed thresholding**: CalLB beats `no_CRC` (same MLP scores + dev-tuned fixed threshold) on B+C-prone slice accuracy by ≥ **1 pp** with **bootstrapped paired p < 0.05** on at least one of {LongMemEval-S, Memora-FAMA}.
- **Path (B) — Cross-dataset robustness**: When λ̂_α calibrated on one corpus and tested on another (LongMemEval-S → Memora and vice versa) **without re-calibration**, CalLB's contamination guarantee holds within `α + 0.06` on the held-out corpus while `no_CRC`'s fixed threshold violates by `> 0.10`. (CRC threshold transfers; fixed dev threshold doesn't.)

**Fallback if neither holds:**
- **Option F1**: Pivot to a workshop / findings track venue (smaller-scope claim: "calibrated load-bearing selection for memory; first formal guarantee").
- **Option F2**: Drop the formal-guarantee thesis. Reframe as a purely empirical paper on "learned multi-substrate fusion + tiered-prompt reader for long-conversation memory", with CRC as a supplementary appendix. Submit to main-track *only if* B+C slice lift ≥ 5 pp on the empirical headline.

This commits the team **in advance**; no post-hoc venue-rationalization. (Reviewer's only operational caveat at the READY verdict: "honor the pre-committed venue logic".)

## Success Conditions (consolidated)

1. **Probabilistic clean-set guarantee on test (formal object).** Empirical `R̂_test(λ̂_α) ≤ α + 0.04` for α ∈ {0.10, 0.20, 0.30, 0.40} on Memora test + LongMemEval-S test (Clopper-Pearson CRC bound holds).
2. **Non-vacuity / utility on L.** At α* = 0.20: `non_empty_fraction ≥ 0.85`, `mean |L| ∈ [2, 5]`, `LB_recall ≥ 0.75`.
3. **B+C-prone slice lift on LongMemEval-S (headline).** ≥ **3 pp lift** on union of B-prone (KU, single-session-preference) + C-prone (single-session-user, multi-session, KU) slices vs Path D `ttmg`; no slice regression > 1 pp.
4. **Acceptance logic for main-track.** Path (A) OR Path (B). If neither → Option F1 or F2.
5. **Attribution causality.** `prompt-only` < 50 %, `rerank-only` < 70 %, `agreement-heuristic-only` < 70 %, and `no_CRC` (Path A) — see acceptance logic above.
6. **Mechanism causality.** `no_cross_substrate_agreement` OR `no_robustness_features` drops Class-B-fix lift by ≥ 50 %; `no_drift_features` drops KU lift by ≥ 30 %.
7. **Portable subset.** `portable_features_only` (8 features) achieves ≥ 50 % of CalLB's slice lift.
8. **Class-B rescue analysis.** Reported regardless of outcome; narrative adjusted per pre-registration trigger.
9. **FAMA secondary parity.** Within 3 pp of best baseline on Memora-temporal-forgetting subset.
10. **LoCoMo parity.** Within 2 pp of best of (Path D, A-Mem, SmartSearch).

## Failure Clauses (Kill Conditions)

| ID | Detect | Action |
|---|---|---|
| F1 | `R̂(λ̂_α) > α + 0.06` for ≥ 2 of 4 α | Check CP computation; if persistent → drop formal claim → trigger Option F2 |
| F1' | `non_empty < 0.70` OR `LB_recall < 0.50` | L vacuous → Option F2 |
| F2 | `prompt-only ≥ 70 %` of slice lift | Reframe as prompt-engineering paper |
| F3 | B+C slice lift < 1 pp on ≥ 2 slices | Pivot direction |
| F4 | D-vs-non-D κ < 0.65 | Binary collapse `LB` vs `not-LB` and re-derive |
| F9 | No Path A AND No Path B | Option F1 (workshop) or F2 (empirical-only with ≥ 5 pp bar) |

## Compute & Timeline

- **Compute.** ≈ 30 GPU-hour-equivalents on 1–2× RTX-4090 (MAAS-only inference; MLP < 5 min CPU).
- **Annotation.** 10K LLM-judge labels @ ~3 s = **8.3 hr** sequential MAAS + **1 hr** author audit on 100 stratified items.

### Eval matrix (Week 2, 31 runs / ~16 hr)

| Block | Methods × seeds × bench | Runs | Time |
|---|---|---:|---:|
| Primary headline | {CalLB, Path D ttmg} × 3 seeds × LongMemEval-S full | 6 | 3 hr |
| Mandatory baselines | {MiCP, Stop-RAG, Flat-RAG} × 3 seeds × LongMemEval-S full | 9 | 4.5 hr |
| Attribution + mechanism + generality | 8 × 1 seed × LongMemEval-S full | 8 | 4 hr |
| Memora-FAMA secondary | 5 × 1 seed × Memora full | 5 | 2.5 hr |
| LoCoMo parity | 3 × 1 seed × LoCoMo full | 3 | 1.5 hr |
| **Total** | | **31** | **~16 hr** |

### Timeline

- **Week 1 — build & calibrate.** Feature extractor + MLP + CRC + LLM-judge labelling script. Auto-label 10K cal pairs. Manual audit 100 stratified-borderline items. Train MLP. Compute Clopper-Pearson CRC table for 4 α. Lock + commit hash. All intrinsic gates clear (κ ≥ 0.7 / 0.75; AUC ≥ 0.75; per-α dev coverage holds).
- **Week 2 — eval.** 31-run matrix above. Generate per-α coverage plot, B+C slice lift bar chart, attribution chart, mechanism ablation chart, portable-vs-full chart, Class-B-rescue analysis, FAMA bars, LoCoMo parity table.
- **Week 3 — paper.** Writing + figures. Cite Conformal Risk Control (Angelopoulos 2022, Bates et al. 2021), Conformal-RAG (2506.20978), MiCP (2604.01413), Stop-RAG (2510.14337), BMAM (2601.20465), HiGMem (2604.18349), Path D's underlying TTMG paper.

## Novelty and Elegance Argument

| Paper | Statistical object | Granularity | Subsumes us? |
|---|---|---|---|
| Conformal-RAG (2506.20978) | Output sub-claim factuality | Per-output-claim | No — different side (output, not input evidence) |
| MiCP (2604.01413) | Per-query stopping coverage | Per-query | No — wrong granularity |
| Stop-RAG (2510.14337) | Per-query stopping (RL) | Per-query | No — non-statistical + wrong granularity |
| BMAM (2601.20465) | None (RRF heuristic) | Per-substrate fusion | No — uncalibrated, no learning |
| HiGMem (2604.18349) | None | Architectural | No — no calibration |
| Conformal Risk Control (2208.02814) | Generic risk control | Generic | Provides our **tool**, not the application |

**Exact difference.** Per-(query, item) **load-bearing** label + Conformal Risk Control with **clean-set indicator risk** on the **probability the reader-visible load-bearing tier contains any distractor** + multi-substrate signal fusion (agreement + max-score + singleton-hit + entity-overlap + TTMG drift features) as learned MLP features.

**Why mechanism-level, not pile-up.** One MLP + one CRC threshold + one prompt update. Path D substrate frozen. Reader frozen. Contribution summarisable in **one inequality**: `Pr_test[L_λ̂_α(q) contains distractor] ≤ α` w.p. ≥ 1 − δ over cal split.

## Experiment Handoff Inputs (for `/experiment-plan`)

- **Must-prove claims.** (1) Clopper-Pearson CRC clean-set guarantee at 4 α + non-vacuity targets; (2) B+C slice lift ≥ 3 pp on LongMemEval-S; (3) Path (A) downstream lift over `no_CRC` ≥ 1 pp w/ p<0.05 OR Path (B) cross-dataset CRC threshold transfer.
- **Must-run baselines.** Path D `ttmg`, MiCP-on-Path-D, Stop-RAG-on-Path-D, Flat hybrid-RAG (LongMemEval-S); A-Mem, Mem0, LightMem (Memora); EverMemOS appendix; SmartSearch (LoCoMo).
- **Must-run ablations.** 4 attribution (`prompt-only`, `rerank-only`, `agreement-heuristic-only`, `no_CRC`) + 3 mechanism (`no_cross_substrate_agreement`, `no_drift_features`, `no_robustness_features`) + 1 generality (`portable_features_only`) = **8 total**.
- **Critical datasets / metrics.** Memora train/test, LongMemEval-S train/test (full N=500), LoCoMo full; per-α Clopper-Pearson empirical risk; non-vacuity utility metrics; cluster-bootstrap CIs; bootstrapped paired p-test for Path A.
- **Highest-risk assumptions.** (i) LLM-judge κ ≥ 0.7 / 0.75 on 100-q audit. (ii) Cal/test exchangeability holds. (iii) MLP dev AUC ≥ 0.75. (iv) Either Path A or Path B holds at end of Week 2 (else trigger Option F1/F2 per pre-commitment).
