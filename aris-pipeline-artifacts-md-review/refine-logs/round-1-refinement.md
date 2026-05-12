# Round-1 Refinement: CalLB — Calibrated Load-Bearing Evidence Selection for Long-Conversation Memory

**Renamed** from CalRR to **CalLB** to signal the formal-object pivot:
*Calibrated **L**oad-**B**earing selection*, not generic rank-quality calibration.

## What changed vs round-0 (and why)

| # | Change | Driver | Round-0 → Round-1 |
|---|---|---|---|
| 1 | **Formal object** | Rev-1 (FATAL) — split-CP gave `P(S≥τ\|Y=1)`, paper claimed `P(Y=1\|S≥τ)`; wrong direction | Per-item conformal coverage → **Conformal Risk Control on distractor contamination** of the load-bearing tier |
| 2 | **Supervision target** | Rev-2 — "relevance" is too loose for Class C (over-specification) | Binary `relevant` → **3-tier `load-bearing` / `supporting` / `distractor`**; risk = distractor rate in load-bearing tier |
| 3 | **Attribution baselines** | Rev-3 — must isolate calibration vs prompt-engineering vs MLP | Added `prompt-only`, `rerank-only`, `agreement-heuristic-only` to baseline table |
| 4 | **Headline metric** | Rev-4 — Memora-FAMA dominance was aspirational | Headline = **B/C slice lift on LongMemEval-S** + bounded contamination on calibration test; Memora-FAMA → secondary parity claim |
| 5 | **Generality framing** | Rev-5 — TTMG-coupled features sold as universal | "Calibrated load-bearing selection **over a temporal-graph memory substrate**"; explicit `portable_features_only` ablation shows what survives without TTMG |
| 6 | **Cost realism** | Rev-7 (L7) — 8K labels under-estimated (60K candidates) | 2K queries × 30 candidates = 60K → stratified-subsample to **10K labelled items**; manual audit 100 items (not 50) |

---

## Problem Anchor (UNCHANGED)

(Reviewer explicitly said: do not rethink the anchor; rethink the formal object. Verbatim copy of round-0:)

- **Bottom-line problem.** When an LLM agent answers from accumulated long-conversation memory, the *reader* commits two systematic errors that no current 2026 system addresses with a calibrated mechanism: (i) **over-specification** — after correctly grounding on the right evidence, it pads the answer with adjacent, unsupported details (47 % of Path D's wrong answers on LongMemEval-S); (ii) **wrong-content retrieval** — surfacing the wrong session/turn even though the right evidence exists in the haystack (41 % of wrong answers). Together these two reader-side failures account for **88.2 % of Path D's wrong answers**, empirically rejecting the "writer is the bottleneck" hypothesis. Source: gating decomposition over 186 wrong answers in `results/gating_decomposition.json` (2026-04-27).
- **Must-solve bottleneck.** A mechanism that simultaneously (a) reduces *Class B* (wrong-content retrieval) by exploiting cross-substrate agreement signal, and (b) reduces *Class C* (over-specification) by giving the reader a **bounded-contamination** load-bearing tier that does not invite padding with adjacent unsupported items. Universal across question types — operates at the per-retrieved-item selection level, not per-query stopping.
- **Non-goals.** Not a new memory architecture. Not a write-time pipeline. Not LoCoMo accuracy SOTA. Not a per-query abstention rule. Not a writer-fine-tune project.
- **Constraints.** 1–2 RTX-4090; MAAS API; 3 weeks; reuse `ttmg/` substrate; NeurIPS / ICML main-track target.
- **Success condition.** *(Updated to match the new formal object — see §Success below.)*

## Updated Success Conditions

1. **Bounded distractor contamination on test (formal object).** On Memora test and LongMemEval-S test, the load-bearing tier `L_λ̂_α(q) = {items with calibrated score ≥ λ̂_α}` has **empirical contamination** `R̂(λ̂_α) = E_q[#distractors_in_L / max(1, |L|)] ≤ α + 0.02` for α ∈ {0.10, 0.20, 0.30, 0.40} on a held-out test split. This is the **Conformal Risk Control** guarantee (Angelopoulos 2022, Bates et al. 2021), not the broken precision-style guarantee from round-0.
2. **B+C-prone slice lift on LongMemEval-S (headline metric).** CalLB-augmented Path D reader vs Path D `ttmg` baseline on LongMemEval-S full N=500: ≥ **3 pp lift** on the union of Class-B-prone slices (knowledge-update, single-session-preference) and Class-C-prone slices (single-session-user, multi-session, knowledge-update); no regression > 1 pp on any slice.
3. **Attribution causality (mandatory, per Rev-3).**
   - `prompt-only` baseline (Path D top-k + load-bearing prompt instructions, no reranker, no calibration): captures < 50 % of CalLB's slice lift, otherwise calibration is not the contribution.
   - `rerank-only` baseline (CalLB ranking, flat reader prompt, no tiering): captures < 70 % of CalLB's slice lift, otherwise tiering is not load-bearing.
   - `agreement-heuristic-only` baseline (no MLP, no calibration; rank by `cross_substrate_agreement` count, semantic-sim tiebreak; load-bearing prompt): captures < 70 % of CalLB's slice lift, otherwise the learned MLP is unnecessary.
4. **Mechanism causality.** `no_cross_substrate_agreement` ablation drops Class-B-fix lift by ≥ 50 %; `no_drift_features` (no TTMG-specific features) drops KU lift by ≥ 30 %; `no_CRC` (raw MLP scores, top-k by score with no calibrated tier) breaks contamination guarantee on test.
5. **Portable subset (honest generality).** `portable_features_only` ablation (only semantic + lexical + cross_substrate_agreement + recency, no TTMG-specific features) achieves ≥ 50 % of CalLB's slice lift — bounds the substrate-agnostic part of the contribution.
6. **FAMA — secondary parity claim.** On Memora full test, CalLB's aggregate FAMA is **within 3 pp of best baseline** (A-Mem / Mem0 / LightMem / EverMemOS-on-Memora) on the temporal-forgetting subset; if it dominates, that is bonus, not headline.
7. **LoCoMo parity.** CalLB-augmented reader within 2 pp of best of (Path D, A-Mem, SmartSearch).
8. **Failure clauses (kill conditions).**
   - (F1) Empirical contamination `R̂(λ̂_α) > α + 0.04` for ≥ 2 of 4 α on either test set → CRC application invalid; either re-derive (LTT-FST), or drop the formal claim and reframe as empirical-only.
   - (F2) `prompt-only` captures ≥ 70 % of slice lift → reframe as "prompt-engineering on TTMG substrate" with calibration as supporting; no headline calibration claim.
   - (F3) B+C slice lift < 1 pp on ≥ 2 slices → method does not address the gating-anchored bottleneck; pivot direction.

## Technical Gap (UPDATED)

Three deltas vs the 2026 frontier (EverMemOS / SmartSearch / HyperMem / Synthius / HiGMem / APEX-MEM / BMAM / MAGMA / MiCP / Stop-RAG / Conformal-RAG):

1. **No method outputs a calibrated bound on the contamination of the *retrieved-evidence set the reader sees*.** Conformal-RAG (2506.20978) calibrates *output sub-claim factuality* on RAG output. We calibrate *input evidence-set distractor rate*. Complementary: their guarantee is on what comes out, ours is on what goes in. Neither subsumes the other.
2. **No method labels evidence by *load-bearing* status** — all surveyed work uses binary relevance or rank order. Class C errors require the load-bearing distinction (an item can be "topically relevant" yet *not* load-bearing for the gold answer).
3. **No method uses cross-substrate agreement as a learned feature for memory ranking.** BMAM (2601.20465) does 4-way RRF fusion — uniform-weight, no learning. We learn per-substrate weights *and* exploit agreement as a feature.

**Why naive fixes are insufficient.**
- Heuristic learned reranker (cross-encoder over (q, item)): uncalibrated → reader cannot tell which items are load-bearing.
- Static threshold over similarity scores: no contamination control; wrong substrate fusion (similarity is single-substrate).
- Per-query coverage (MiCP): wrong granularity — controls "did we abstain enough?", not "is the evidence set clean?".

**Smallest adequate intervention.**
A learned per-item reliability score (small MLP over ~10 substrate features) with a single calibrated threshold `λ̂_α` chosen by **Conformal Risk Control** so that the load-bearing tier has bounded *expected distractor contamination*. The reader prompt is updated minimally: "items in tier L are load-bearing, use them for the answer's load-bearing facts; items in tier S are supporting context, do not use them as load-bearing evidence". One MLP + one CRC threshold + one prompt update.

## Method Thesis (REWRITTEN)

> *For each retrieved memory item, fuse semantic + lexical + claim-graph + raw-turn substrate signals into a learned reliability score; calibrate a single threshold `λ̂_α` via **Conformal Risk Control** so that the load-bearing tier `L_λ̂_α(q)` has **bounded expected distractor contamination** `E_q[R(L_λ̂_α(q))] ≤ α`; expose `L` and `S = top-k \\ L` to the reader as separate tiers, instructed to use only `L` for load-bearing facts. The contribution is a calibrated input-evidence-set guarantee — empirically motivated by 88.2 % B+C gating evidence on a 2026-frontier system — addressing both wrong-content retrieval (Class B, via the cross-substrate-agreement feature the MLP can learn) and reader over-specification (Class C, via bounded contamination of the load-bearing tier).*

- **Why this is the smallest adequate intervention.** Single CRC threshold + single MLP + single prompt update. Path D substrate frozen. Reader frozen.
- **Why timely.** (a) 88.2 % B+C empirical evidence (2026-04-27) gives the strongest case in the literature for read-side investment; (b) Memora-FAMA (2604.20006) provides a forgetting-aware metric the frontier hasn't reported on; (c) Conformal Risk Control on input evidence sets is novel for memory systems and is well-defined off-the-shelf math (no joint-null issues; Idea 1's e-process trap avoided).

## Contribution Focus (TIGHTENED)

- **Dominant contribution.** *Calibrated load-bearing evidence selection via Conformal Risk Control on the distractor contamination of the reader-visible evidence set* — the first memory operator with a coverage-style guarantee on **what the reader sees as load-bearing context**, not on per-query abstention or per-output-claim factuality. Demonstrated on a temporal-graph (TTMG) memory substrate; portable subset of the feature vector quantified by ablation.
- **Optional supporting contribution.** A *gating-evidence-grounded* error decomposition methodology (Class A/B/C/D) for memory systems — released as a script + 186-question reference labels.
- **Explicit non-contributions.**
  - Not a new memory store.
  - Not a per-query abstention rule (MiCP / Stop-RAG / β own that).
  - Not a writer fine-tune (Memory-R1 / MemBuilder own that).
  - Not LoCoMo SOTA (parity claimed; structural-memory race over).
  - **Not a substrate-agnostic universal operator** — TTMG-coupled; portable subset bounded by ablation.

## Proposed Method (REVISED)

### Complexity Budget (UNCHANGED scope)

- **Frozen / reused.** Path D's `ttmg/` substrate (claim graph + supersede edges + validity intervals + `active` flag + `raw_turn_fallback` index + BM25 + `all-MiniLM-L6-v2` embedder). Reader = `deepseek-v3.2`. MAAS endpoints unchanged.
- **New (3 deltas).**
  1. *Feature extractor* (`ttmg/lb_features.py`, ~150 lines): per-(query, item) feature vector.
  2. *Learned reranker* (`ttmg/lb_model.py`, ~80 lines): small MLP (input dim ~10, hidden 32, output 1 logit), trained to predict `P(load-bearing)` via cross-entropy on 3-tier labels collapsed to binary `1[load-bearing]`.
  3. *CRC calibration layer* (`ttmg/lb_crc.py`, ~120 lines): Conformal Risk Control (Angelopoulos 2022 LTT / Bates et al. 2021) — find `λ̂_α` such that empirical risk `R̂(λ) ≤ α` on cal split with high-probability bound (Hoeffding / Bernstein per CRC).

### Feature Set (REORGANIZED — portable vs TTMG-specific)

| Group | Feature | Source | Why |
|---|---|---|---|
| **Portable** | `semantic_sim(q, item.content)` | embedder cosine | Substrate-agnostic. |
| **Portable** | `lexical_sim_bm25(q, item.content)` | BM25 over raw turns | Substrate-agnostic. |
| **Portable** | `cross_substrate_agreement(item)` = #substrates ∈ {sem, lex, raw, claim} containing item in their top-k | binary across 4 substrates (claim is TTMG-only; in portable subset use 3) | **Primary Class-B fix.** |
| **Portable** | `recency_baseline` = `Δt_since_creation` | raw recency | Ablation control: "drift-aware" vs "just recency". |
| **Portable** | `source_type` | one-hot of {raw-turn, structured-claim} | Lets MLP learn substrate prior. |
| **TTMG-specific** | `claim_graph_relevance(q, item.claim_id)` | cosine over claim representation; 0 if raw-turn | Sub-substrate signal. |
| **TTMG-specific** | `supersede_edge_count(item)` | hard-supersede edges *into* this item | Drift signal for KU slice. |
| **TTMG-specific** | `validity_interval_freshness(item, τ_q)` | `1` if `valid_at(item, τ_q)`, exp decay otherwise | Time-validity. |
| **TTMG-specific** | `contradiction_count(item)` | hard-contradict edges incident to item | Noise signal. |
| **TTMG-specific** | `time_volatility(item)` = `Δt_since_creation × topic_volatility(item.subject)` | drift score | Class-B fix on KU. |

The `portable_features_only` ablation uses only the 5 portable features. This bounds the substrate-agnostic part of the contribution.

### 3-tier Label (NEW per Rev-2)

Per (query, candidate item) pair, label ∈ {**load-bearing (LB)**, **supporting (S)**, **distractor (D)**}:

- **LB**: removing the item from the reader's context would likely change the answer's correctness. Item is necessary or near-necessary evidence for the gold answer.
- **S**: topically related; the reader could still produce the gold answer without it; including it is safe but unnecessary.
- **D**: would actively mislead the reader — wrong-entity item, off-topic but tempting, near-paraphrase that mentions the wrong entity, confounding adjacent context that invites over-specification.

**LLM-judge prompt** (deepseek-v3.2):

```
GIVEN:
  - Question: {q}
  - Gold answer: {gold}
  - Candidate retrieved item: {item.content}

Classify the item:
(A) LOAD-BEARING — if removed from the reader's context, the reader would
    likely fail to produce the gold answer. Item is necessary evidence.
(B) SUPPORTING — topically related to the question/answer, but the reader
    could still produce the gold answer without it. Safe to include.
(C) DISTRACTOR — would actively mislead the reader: wrong entity, wrong
    fact, off-topic, or invites the reader to add unsupported adjacent
    detail to the answer.

Return strict JSON:
{ "label": "LB" | "S" | "D",
  "rationale": "one sentence" }
```

**Risk** for Conformal Risk Control:
```
R(λ ; q) = ( # candidates with score ≥ λ AND label = D ) / max(1, # candidates with score ≥ λ)
```
i.e., distractor fraction in the load-bearing tier. Treats `S` as benign (safe to include even though not necessary). `R(λ; q) ∈ [0, 1]`, monotone non-increasing in λ (larger λ → smaller, cleaner tier), CRC-compatible.

**Average risk** is what CRC bounds:
```
R(λ) = E_q[R(λ; q)]      with R(λ; q) := 0 if |L| = 0   (vacuously safe)
```

### Conformal Risk Control: the calibrated threshold

Following Angelopoulos 2022 (`arXiv:2208.02814`), Bates et al. 2021 (Learn-Then-Test):

- Hold out `n_cal` queries (with their candidate sets and 3-tier labels) as a calibration set.
- Define empirical risk `R̂_cal(λ) = (1/n_cal) Σ_q R(λ; q)`.
- Find `λ̂_α = inf { λ : ucb(R̂_cal(λ)) ≤ α }`, where `ucb` is a concentration-based UCB (Hoeffding for [0,1]-bounded risk; ucb(R̂) = R̂ + √(log(1/δ)/(2 n_cal)), δ=0.05 per α).
- Guarantee (under exchangeability of cal and test queries): `Pr[R(λ̂_α) ≤ α] ≥ 1 − δ` over the random cal split.

This is a standard finite-sample CRC bound on the **expected distractor contamination of the reader's load-bearing tier**. It composes directly into a property the reader cares about (the load-bearing context the reader treats as authoritative is bounded-contamination), addressing the L1 critique from round-1.

### System Overview (UPDATED)

```
WRITE-time:  Path D pipeline (UNCHANGED)
             writer → claims → linker → supersede edges → claim graph + raw-turn index

CALIBRATION (offline, one-time):

  ┌──────────────────────────────────────────────────────────────────────┐
  │ Stratified-subsample 10K (q, item) pairs from                        │
  │   2K queries × ~30 candidates each                                   │
  │   (40 % LongMemEval-S train + 40 % Memora train)                     │
  │                                                                      │
  │ Auto-label each pair {LB, S, D} via LLM-judge (deepseek-v3.2)        │
  │   - Manual audit on 100 dev pairs; target ≥ 0.80 author-agreement    │
  │     on 3-class (lower than binary 0.85 bar; appropriate for ordinal) │
  │                                                                      │
  │ Train MLP: input 10 features → hidden 32 → output 1 logit            │
  │   - Loss: BCE on `1[label = LB]` (binary collapse)                   │
  │   - 5 epochs, Adam, LR 1e-3, weight decay 1e-4                       │
  │   - Train/dev split: 80/20 by query (no query leakage)               │
  │                                                                      │
  │ CRC: hold out 30 % of cal queries → cal-of-cal (~600 queries)        │
  │   For each α ∈ {0.10, 0.20, 0.30, 0.40}:                             │
  │     Sweep λ on a 100-point grid → compute R̂(λ)                       │
  │     λ̂_α = inf { λ : R̂(λ) + Hoeffding(δ=0.05) ≤ α }                  │
  │   Lock λ̂ table; commit hash to git; print in paper.                  │
  └──────────────────────────────────────────────────────────────────────┘

INFERENCE:

  ┌──────────────────────────────────────────────────────────────────────┐
  │ query q at time τ_q                                                  │
  │   → Path D retrieval gathers candidate set                           │
  │     (semantic top-10 ∪ lexical top-10 ∪ claim top-10 ∪ raw-turn      │
  │     top-10, deduplicated; ≤ 30 candidates)                           │
  │                                                                      │
  │ For each candidate item:                                             │
  │   features = extract_features(q, item)                               │
  │   s = MLP(features)                                                  │
  │                                                                      │
  │ Tier the candidates at headline α* = 0.20:                           │
  │   L  (load-bearing)  = { item : s ≥ λ̂_0.20 }                         │
  │   S  (supporting)    = top-K_supp items NOT in L, ranked by s        │
  │                        (K_supp = 3; ensures reader has ≥ 3 fallback) │
  │                                                                      │
  │ Reader prompt (minimal augmentation):                                │
  │   """                                                                │
  │   You are answering from memory. Below are evidence items in two     │
  │   tiers:                                                             │
  │                                                                      │
  │   [LOAD-BEARING] (use these for the answer's load-bearing facts):    │
  │   {L items}                                                          │
  │                                                                      │
  │   [SUPPORTING] (background only; do not use as load-bearing):        │
  │   {S items}                                                          │
  │                                                                      │
  │   Answer the question using ONLY load-bearing items for the          │
  │   answer's facts. Do not include details only present in supporting  │
  │   items unless directly asked.                                       │
  │   """                                                                │
  │                                                                      │
  │ → reader call (UNCHANGED model: deepseek-v3.2; no abstention rule)   │
  └──────────────────────────────────────────────────────────────────────┘
```

### Core Mechanism (UPDATED)

- **Input.** Query `q` at time `τ_q`; Path D candidate set (≤ 30 items).
- **Output.** Two tiers `(L, S)`; reader prompt instructs use of `L` as load-bearing.
- **Architecture.** Feature extractor (deterministic Python) → MLP → CRC threshold lookup → tier construction → augmented reader prompt.
- **Training signal.** Binary cross-entropy on `1[label = LB]`. The 3-class label is collapsed to binary for the MLP; the 3-class semantics matter for the *risk function* (only `D` counts as contamination).
- **Why this is the main novelty.**
  - Conformal-RAG calibrates *output sub-claim factuality* — different statistical object (output side, not input evidence side).
  - MiCP / Stop-RAG calibrate *per-query stopping* — different granularity.
  - BMAM / HetaRAG fuse multi-substrate via RRF — uncalibrated, no agreement learning.
  - HiGMem / EverMemOS / Synthius / HyperMem are architectural — no calibration layer.
  - Cross-substrate agreement as a learned MLP feature (with TTMG features adding drift signal) is empirically grounded in the gating evidence (Class B = 41 %).

### Modern Primitive Usage (UNCHANGED, justified)

1. Path D substrate (already-built): writer + linker + parser + reader. No change.
2. Item-level relevance labeller (LLM-as-judge, one-shot, deepseek-v3.2): for cal set construction, validated on 100-dev manual audit (≥ 0.80 author-agreement on 3-class).
3. Reader prompt update (no fine-tune): minimal prompt-engineering change.

The MLP is the only learned component (~10K params, < 5 min CPU training).

### Integration into Path D Pipeline

- **Files touched.** New: `ttmg/lb_features.py`, `ttmg/lb_model.py`, `ttmg/lb_crc.py`, `scripts/calibrate_lb.py`, `scripts/audit_judge_labels.py`, `experiments/eval_callb.py`. Modified: `ttmg/system.py` (add `enable_callb` flag + tiered-prompt path in `answer()`).
- **Files frozen.** All Path D substrate.
- **Inference order.** Same as Path D until candidate set is built; then CalLB tiers; then tiered-prompt reader call.

### Training Plan (REALISTIC COSTS)

- **No model training beyond the MLP.** MLP trains on a single CPU in < 5 min.
- **Calibration set construction (real cost).**
  - Source pool: ~2K queries (1K LongMemEval-S train + 1K Memora train, ~40 % each).
  - Candidate sets: ~30 items per query → ~60K (q, item) pairs total.
  - **Stratified subsample to 10K labelled pairs**, stratified by `(question_type × candidate_position_in_top-k)` to ensure coverage of both top-of-list and tail items.
  - LLM-judge call cost: 10K × ~3 sec/item (deepseek-v3.2) ≈ **8.3 hr MAAS sequential** (one in-flight call per server-load policy).
  - Author manual audit: 100 dev items × ~30 sec each ≈ **50 min** for the agreement check.
- **CRC compute.** 100-point λ grid × 4 α values × 600 cal-of-cal queries × <30 candidates each ≈ negligible CPU.
- **Acceptance gates** (intrinsic, before any test runs):
  - LLM-judge labelling agreement ≥ 0.80 on 100-q audit (3-class, Cohen's κ ≥ 0.65).
  - MLP dev-set AUC ≥ 0.75 on `1[label=LB]` (binary).
  - Per-α dev-set risk `R̂_dev(λ̂_α)` ≤ α + 0.02 for all 4 α.
  - Locked `λ̂` table committed to git; commit hash printed in paper.
  - All gates clear → proceed to test.

### Failure Modes and Diagnostics (UPDATED)

- **F1 LLM-judge label noise on 3-class.** Detect: dev κ < 0.65. Mitigate: 3-call self-consistency; relabel low-agreement; if persistent, fall back to 2-class collapse `LB` vs `not-LB`.
- **F2 MLP underfits.** Detect: dev AUC < 0.7. Mitigate: increase hidden dim to 64; add interaction features; check label imbalance.
- **F3 CRC contamination miss on test.** Detect: empirical `R̂(λ̂_α) > α + 0.04` for any α. Mitigate: re-derive with tighter Bernstein UCB; if cal/test exchangeability fails, run a KS descriptive check and admit honestly (per round-3 lesson from β v2).
- **F4 B+C slice lift fails.** Detect: < 1 pp lift on ≥ 2 of the union slices. Mitigate: increase `K_supp`; tighten α; check tiered-prompt is being respected via prompt audit; if persistent, the gating-evidence-driven design intuition is wrong.
- **F5 `prompt-only` baseline captures most lift.** Detect: `prompt-only` achieves ≥ 70 % of CalLB's slice lift. Mitigate: reframe as "prompt-engineering on TTMG substrate"; keep CRC as supporting evidence; demote calibration from headline.
- **F6 `agreement-heuristic-only` matches MLP.** Detect: heuristic achieves ≥ 70 % of CalLB's slice lift. Mitigate: drop the MLP, deliver the heuristic + CRC as a simpler method; update story.
- **F7 Cross-substrate agreement collinear (per L3).** Detect: in dev split, `cross_substrate_agreement` correlates ρ > 0.85 with single-substrate semantic ranking. Mitigate: redefine agreement to penalize duplication (e.g., diversity-weighted), or fall back to 2-substrate count.
- **F8 Memora-FAMA falls behind baselines.** Detect: paired-bootstrap shows CalLB worse than 2 of 4 baselines on temporal-forgetting subset. Mitigate: this is now an honest parity claim; report as such, do not over-sell.

### Novelty and Elegance Argument (UPDATED)

- **Closest work table.**

| Paper | Statistical object | Granularity | Subsumes us? |
|---|---|---|---|
| Conformal-RAG (2506.20978) | Output sub-claim factuality | Per-output-claim | No — different side (output, not input) |
| MiCP (2604.01413) | Per-query stopping coverage | Per-query | No — wrong granularity (stopping ≠ evidence cleanliness) |
| Stop-RAG (2510.14337) | Per-query stopping (RL) | Per-query | No — same as above + non-statistical |
| BMAM (2601.20465) | None (RRF heuristic) | Per-substrate fusion | No — uncalibrated, uniform weight |
| HiGMem (2604.18349) | None | Architectural | No — no calibration |
| Conformal Risk Control (2208.02814) | Generic risk control | Generic | Provides our **tool**, not our application |

**Exact difference from each:** Per-(query, item) **load-bearing** label + Conformal-Risk-Control on **distractor contamination of the reader-visible load-bearing tier** + cross-substrate agreement as learned feature with TTMG drift signals.

- **Why mechanism-level, not pile-up.** One MLP + one CRC threshold + one prompt update. The contribution is summarisable in one inequality and one design choice (the load-bearing tier semantics).

## Claim-Driven Validation Sketch (REVISED)

### Claim 1 (Dominant) — Bounded distractor contamination + B+C slice lift

- **Statement.** (a) On Memora test and LongMemEval-S test: empirical `R̂(λ̂_α) ≤ α + 0.02` for α ∈ {0.10, 0.20, 0.30, 0.40} (Hoeffding-CRC bound holds). (b) On LongMemEval-S full N=500: ≥ 3 pp lift on the union of B-prone (KU, single-session-preference) and C-prone (single-session-user, multi-session, KU) slices vs Path D `ttmg`, no regression > 1 pp on any slice.
- **Minimal experiment.** 1 method (CalLB) × 3 seeds × deepseek-v3.2 × Memora full test + LongMemEval-S full N=500.
- **Baselines.** Path D `ttmg` (existing); MiCP-on-Path-D (mandatory, port stopping rule to candidate set); Stop-RAG-on-Path-D (mandatory, port to candidate set); Flat hybrid-RAG.
- **Attribution baselines (per Rev-3).** `prompt-only` (Path D top-k + same load-bearing prompt; no MLP / CRC), `rerank-only` (CalLB ranking, flat reader prompt; no tiering), `agreement-heuristic-only` (no MLP, rank by agreement count + sem-sim tiebreak; load-bearing prompt).
- **Mechanism ablations.** `no_cross_substrate_agreement`, `no_drift_features`, `no_CRC` (raw MLP top-k by score, no calibrated tier).
- **Generality ablation.** `portable_features_only` (5 portable features only).
- **Metrics.** Per-α empirical risk; B+C-slice accuracy lift; full-set accuracy; per-slice no-regression check.
- **Expected evidence.** Risk holds for all 4 α; ≥ 3 pp slice lift; attribution baselines each capture < expected fraction; mechanism ablations drop appropriately; portable subset bounds substrate-agnostic part.

### Claim 2 (Supporting) — Memora-FAMA parity + LoCoMo parity

- **Statement.** On Memora full test, CalLB's aggregate FAMA within 3 pp of best baseline on temporal-forgetting subset (parity claim). On LoCoMo full, CalLB-augmented reader within 2 pp of best of (Path D, A-Mem, SmartSearch).
- **Minimal experiment.** 5 methods × 1 seed (LoCoMo) / 3 seeds (Memora) × deepseek-v3.2 × Memora full test + LoCoMo full.
- **Baselines.** A-Mem reimpl, Mem0 (best-effort reproduce), LightMem (best-effort reproduce), EverMemOS (best-effort reproduce — appendix only if Memora-port available), SmartSearch (LoCoMo only).
- **Metric.** Aggregate FAMA per duration; cluster-bootstrap CIs; LoCoMo accuracy.
- **Expected evidence.** Memora-FAMA: parity (within 3 pp); LoCoMo: parity (within 2 pp). If we win, bonus; not headline.

(MAX_PRIMARY_CLAIMS = 2 honored.)

## Experiment Handoff Inputs (UPDATED)

- **Must-prove claims.** (1) bounded contamination at 4 α + B+C slice lift on LongMemEval-S; (2) Memora-FAMA + LoCoMo parity.
- **Must-run baselines.** Path D `ttmg`; MiCP-on-Path-D; Stop-RAG-on-Path-D; Flat hybrid-RAG; A-Mem; Mem0; LightMem; (EverMemOS appendix); SmartSearch (LoCoMo).
- **Must-run ablations.** `prompt-only`, `rerank-only`, `agreement-heuristic-only` (3 attribution); `no_cross_substrate_agreement`, `no_drift_features`, `no_CRC` (3 mechanism); `portable_features_only` (1 generality). **7 ablations total.**
- **Critical datasets / metrics.** Memora train/test, LongMemEval-S train/test (full N=500), LoCoMo full (parity); per-α Hoeffding-CRC empirical risk; cluster-bootstrap CIs.
- **Highest-risk assumptions.** (i) LLM-judge 3-class agreement ≥ 0.80 on 100-q audit; (ii) cross-substrate agreement is not collinear with single-substrate ranking; (iii) cal/test exchangeability holds; (iv) MLP dev AUC ≥ 0.75; (v) `prompt-only` does not capture most of the slice lift.

## Compute & Timeline Estimate (REALISTIC)

- **Compute.** ≈ **40 GPU-hour-equivalents** on 1–2× RTX-4090 budget. MAAS-only inference; no local training beyond the MLP (< 5 min CPU).
- **Data / annotation cost.** Auto-label LLM-judge cost ≈ 10K items × ~3 sec MAAS ≈ **8.3 hr** sequential + **50 min** author manual audit on 100 dev items.
- **Timeline.**
  - **Week 1.** Build feature extractor + MLP + CRC script + LLM-judge labelling script. Auto-label 10K cal pairs on Memora train + LongMemEval-S train. Manual audit 100 items. Train MLP. Compute CRC table for 4 α. Lock + commit hash. All intrinsic gates clear.
  - **Week 2.** Full Memora test runs (5 methods + ablations × 3 seeds). LongMemEval-S full N=500 (Path D + CalLB + 3 attribution + 4 mechanism + 1 generality + 3 mandatory baselines × 3 seeds for headline; 1 seed for ablations). LoCoMo full at seed=0 for {Path D, CalLB, SmartSearch}.
  - **Week 3.** Paper writing. Figures: per-α contamination plot with Hoeffding band, B+C slice lift bar chart, attribution bar chart (CalLB vs `prompt-only` vs `rerank-only` vs `agreement-heuristic-only`), mechanism ablation drops, portable-vs-full ablation, FAMA bars with cluster-bootstrap CIs, LoCoMo parity. Cite Conformal Risk Control (Angelopoulos 2022, Bates et al. 2021), Conformal-RAG, MiCP, Stop-RAG, BMAM, HiGMem, Path D's underlying TTMG paper.

(End of round-1 refinement.)
