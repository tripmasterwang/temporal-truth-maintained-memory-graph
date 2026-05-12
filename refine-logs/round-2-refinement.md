# Round-2 Refinement: CalLB — Calibrated Load-Bearing Selection (math + validation hardened)

## What changed vs round-1 (and why)

| # | Change | Driver |
|---|---|---|
| 1 | **Risk function** | Rev-1 (FATAL) — old `#D/#tier` is not monotone in λ → CRC argument invalid. **New: `R(λ; q) = 1[∃ distractor in L_λ(q)]`** (clean-set indicator), monotone non-increasing in λ for each q ✓; bounded in {0,1} ⊂ [0,1] ✓; Hoeffding-CRC over 100-pt λ-grid with δ/m union bound is valid. New guarantee: `Pr_test[L_λ̂_α(q) contains any distractor] ≤ α`. |
| 2 | **Label validation gate** | Rev-2 — Cohen's κ ≥ **0.7** (not 0.65); report 3×3 confusion matrix; D-vs-non-D agreement reported separately; stratified audit oversamples borderline cases by 30 %. |
| 3 | **`no_CRC` baseline redefinition** | Rev-3 — *same* learned MLP scores + **fixed dev-tuned threshold** (median dev score, or threshold optimized for dev-set Class-C-prone slice acc). Drops `random-MLP+CRC` (uninformative). |
| 4 | **De-risk agreement narrative** | Rev-4 — added `max_substrate_score`, per-substrate `rank` features, `singleton_raw_turn_hit`, `entity_overlap`. Reframed: agreement is *one of several substrate-fusion features*, not the "primary Class-B fix". Pre-register Class-B-rescue analysis on 77 gating examples. |
| 5 | **Shrink Week-2 eval matrix** | Rev-5 — 3 seeds for **core methods on primary benchmark only**; 1 seed for ablations + secondary benchmarks (Memora-FAMA, LoCoMo). ~30 runs ≈ 15 hr eval, fits Week 2 with debug slack. |

## Problem Anchor (UNCHANGED — verbatim from round-0)

- **Bottom-line problem.** When an LLM agent answers from accumulated long-conversation memory, the *reader* commits two systematic errors that no current 2026 system addresses with a calibrated mechanism: (i) **over-specification** — after correctly grounding on the right evidence, it pads the answer with adjacent, unsupported details (47 % of Path D's wrong answers on LongMemEval-S); (ii) **wrong-content retrieval** — surfacing the wrong session/turn even though the right evidence exists in the haystack (41 % of wrong answers). Together these two reader-side failures account for **88.2 % of Path D's wrong answers**, empirically rejecting the "writer is the bottleneck" hypothesis. Source: gating decomposition over 186 wrong answers in `results/gating_decomposition.json` (2026-04-27).
- **Must-solve bottleneck.** A mechanism that simultaneously (a) reduces *Class B* (wrong-content retrieval) by exploiting cross-substrate signal fusion (not just agreement count, also singleton-raw-turn and entity-overlap signals so low-consensus correct facts are not lost), and (b) reduces *Class C* (over-specification) by giving the reader a **clean** load-bearing tier with high probability — not just a tier with bounded average contamination, but a tier with a calibrated bound on *the probability of any distractor being present*.
- **Non-goals.** Not a new memory architecture. Not a write-time pipeline. Not LoCoMo accuracy SOTA. Not a per-query abstention rule. Not a writer-fine-tune project.
- **Constraints.** 1–2 RTX-4090; MAAS API; 3 weeks; reuse `ttmg/` substrate; NeurIPS / ICML main-track target.

## Method Thesis (REWRITTEN to match new risk)

> *For each retrieved memory item, fuse semantic + lexical + claim-graph + raw-turn substrate signals into a learned reliability score; calibrate a single threshold `λ̂_α` via **Conformal Risk Control on the clean-set indicator risk** so that with probability ≥ 1 − α, the load-bearing tier `L_λ̂_α(q) = {item : score ≥ λ̂_α}` contains **no distractor**; expose `L` and `S = top-3 \\ L` to the reader as separate tiers, instructed to use only `L` for load-bearing facts. The contribution is a calibrated **probabilistic clean-set guarantee on the reader-visible load-bearing context** — empirically motivated by 88.2 % B+C gating evidence on a 2026-frontier system — addressing both wrong-content retrieval (Class B, via multi-substrate signal fusion) and reader over-specification (Class C, via probabilistic distractor exclusion).*

- **Why this is the smallest adequate intervention.** Single CRC threshold + single MLP + single prompt update. Path D substrate frozen. Reader frozen.
- **Why timely + math-clean.** (a) Clean-set risk indicator is **monotone non-increasing in λ** for each q, so vanilla Hoeffding-CRC over a finite grid with union bound gives a valid finite-sample guarantee. (b) Matches the harm model: in over-specification failures, **one** distractor poisons the answer, not "average fraction of distractors". (c) 88.2 % B+C empirical evidence (2026-04-27) gives the strongest case in the literature for read-side investment. (d) Conformal Risk Control on input evidence sets (instead of output sub-claims like Conformal-RAG) is novel for memory.

## Contribution Focus (UNCHANGED scope, sharper claim)

- **Dominant contribution.** *Calibrated **probabilistic clean-set** guarantee on the reader-visible load-bearing evidence tier* via Conformal Risk Control with a clean-set indicator risk — the first memory operator with such a guarantee. Demonstrated on a temporal-graph (TTMG) substrate; portable subset of the feature vector quantified by ablation.
- **Optional supporting contribution.** Gating-evidence-grounded error decomposition methodology (A/B/C/D, 186 reference labels released).
- **Explicit non-contributions.** Not a new memory store, not a per-query stopping rule, not a writer fine-tune, not LoCoMo SOTA, **not substrate-agnostic** (TTMG-coupled; portable subset bounded by ablation).

## Feature Set (EXTENDED per Rev-4 — 13 features, 5 portable + 5 TTMG-specific + 3 new robustness features)

| Group | Feature | Source | Why |
|---|---|---|---|
| **Portable** | `semantic_sim(q, item.content)` | embedder cosine | Substrate-agnostic. |
| **Portable** | `lexical_sim_bm25(q, item.content)` | BM25 over raw turns | Substrate-agnostic. |
| **Portable** | `cross_substrate_agreement(item)` = #substrates ∈ {sem, lex, raw, claim} containing item in their top-k | binary count over 4 (3 in portable subset) | One signal among many. |
| **Portable** | `recency_baseline` = `Δt_since_creation` | raw recency | Ablation control. |
| **Portable** | `source_type` | one-hot of {raw-turn, structured-claim} | Substrate prior. |
| **Robustness (NEW)** | `max_substrate_score(item)` | max over 4 normalized substrate scores | **Rescues low-agreement-but-strong-single-substrate items.** |
| **Robustness (NEW)** | `singleton_raw_turn_hit(item)` | 1 if item ∈ raw-turn top-k AND ∉ any other substrate top-k | **Directly protects the gating example "I've got three of them" — high in raw-turn, low elsewhere.** |
| **Robustness (NEW)** | `entity_overlap(q, item.content)` | spaCy NER overlap count, normalized | Catches lexical-entity matches that BM25 misses (negation, paraphrase). |
| **TTMG-specific** | `claim_graph_relevance(q, item.claim_id)` | cosine over claim representation; 0 if raw-turn | Sub-substrate signal. |
| **TTMG-specific** | `supersede_edge_count(item)` | hard-supersede edges *into* this item | Drift signal for KU slice. |
| **TTMG-specific** | `validity_interval_freshness(item, τ_q)` | `1` if `valid_at(item, τ_q)`, exp decay otherwise | Time-validity. |
| **TTMG-specific** | `contradiction_count(item)` | hard-contradict edges incident to item | Noise signal. |
| **TTMG-specific** | `time_volatility(item)` = `Δt_since_creation × topic_volatility(item.subject)` | drift score | Class-B fix on KU. |

The `portable_features_only` ablation uses the 5 portable + 3 robustness = 8 features (no TTMG). This bounds the substrate-agnostic part of the contribution.

The MLP input dim is now 13 (was 10). Hidden dim still 32. ~14K params, < 5 min CPU train.

## 3-tier Label (UNCHANGED semantics; tighter validation per Rev-2)

Per (query, candidate item) pair: `label ∈ {LB, S, D}`.

- **LB**: removing the item from reader's context would likely change answer's correctness.
- **S**: topically related but unnecessary; safe to include.
- **D**: would actively mislead reader (wrong entity, off-topic but tempting, near-paraphrase that mentions wrong entity, confounding adjacent context that invites over-specification).

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
  "rationale": "one sentence",
  "confidence": "high" | "low" }
```

**Validation protocol (TIGHTENED)**:
- 100-q audit, **stratified**: ~30 % oversampled from "judge said `confidence=low`" (borderline cases).
- Author manual labels (single annotator; second-pass spot-check by a second author for the audit set).
- Report:
  - Cohen's **κ ≥ 0.7** on full 3-class agreement (gate; below 0.65 → fall back to binary `LB` vs `not-LB`; between 0.65 and 0.7 → 3-call self-consistency on judge then re-audit).
  - Full **3×3 confusion matrix**.
  - **D-vs-non-D binary agreement** reported separately (this is what underwrites the CRC theory): target Cohen's κ ≥ **0.75** on the binary collapse.
  - Class-conditional precision / recall for D.

## CRC Math (FIXED per Rev-1)

### Risk function (clean-set indicator, monotone)

For threshold λ ∈ ℝ:
```
Tier:   L_λ(q) = { item ∈ candidates(q) : MLP_score(item) ≥ λ }
Risk:   R(λ; q) = 𝟙[ ∃ item ∈ L_λ(q) with label = D ]
              ∈ {0, 1}
```

**Monotonicity.** For λ_1 ≤ λ_2: `L_{λ_2}(q) ⊆ L_{λ_1}(q)`, so {∃ D in L_{λ_2}} ⇒ {∃ D in L_{λ_1}}. Hence `R(λ_2; q) ≤ R(λ_1; q)` for each q ✓ — risk is non-increasing in λ.

**Average risk.** `R(λ) = E_q[R(λ; q)] = Pr_q[L_λ(q) contains any distractor]` ∈ [0, 1].

**Composition into reader behavior.** With probability ≥ 1 − α (over the random test query), the load-bearing tier `L_λ̂_α(q)` contains **no distractor** — the reader can safely treat `L` as load-bearing without absorbing wrong/misleading content. This is exactly the property that addresses Class C (over-specification driver removed from load-bearing tier).

### Conformal Risk Control via Hoeffding + grid union bound

- Cal split: `n_cal = 600` queries (held out from cal pool of ~2K).
- λ grid: 100 evenly-spaced values `Λ = {λ_1, ..., λ_100}` covering observed score range.
- Per-grid-point empirical risk: `R̂_cal(λ_j) = (1/n_cal) Σ_q R(λ_j; q)`.
- Per-grid-point Hoeffding UCB at error budget `δ' = δ/100`, δ = 0.05:
  ```
  ucb_j = R̂_cal(λ_j) + √( log(2/δ') / (2 · n_cal) )
        = R̂_cal(λ_j) + √( log(4000) / 1200 )
        ≈ R̂_cal(λ_j) + 0.083
  ```
- Calibrated threshold:
  ```
  λ̂_α = inf { λ_j ∈ Λ : ucb_j ≤ α }
  ```
- **Guarantee** (under exchangeability of cal and test queries):
  ```
  Pr[ R(λ̂_α) ≤ α ] ≥ 1 − δ = 0.95     over the random cal split
  ```
  Since R is monotone non-increasing in λ, the inf is well-defined, and the union bound over the grid ensures the simultaneously-valid Hoeffding bound at the chosen λ̂_α.
- α grid: {0.10, 0.20, 0.30, 0.40} for headline reporting; with the 0.083 slack, the Hoeffding-CRC bound is non-vacuous starting around α = 0.10. (For tighter slack, switch Hoeffding → Bernstein when `R̂(λ) < 0.05`.)
- Headline α* = 0.20 (i.e., headline guarantee: at least 80 % of test queries see a clean load-bearing tier).

### Cost & secondary diagnostic

- CRC compute: 100 grid points × 600 cal-of-cal queries × <30 candidates each ≈ negligible CPU.
- **Secondary descriptive diagnostic** (no formal claim): also report mean distractor fraction in `L_λ̂_α(q)` on test, as a tightness measure.

## Inference (UNCHANGED)

```
query q at time τ_q
  → Path D retrieval gathers candidate set (≤ 30 items)

For each candidate item:
  features = extract_features(q, item)        # 13 features
  s = MLP(features)

Tier at headline α* = 0.20:
  L = { item : s ≥ λ̂_0.20 }                   # load-bearing tier
  S = top-3 items NOT in L, ranked by s        # supporting tier (always 3 fallback)

Reader prompt (minimal augmentation):
  """
  You are answering from memory. Below are evidence items in two tiers:

  [LOAD-BEARING] (use these for the answer's load-bearing facts):
  {L items}

  [SUPPORTING] (background only; do not use as load-bearing):
  {S items}

  Answer using ONLY load-bearing items for the answer's facts. Do not
  include details only present in supporting items unless directly asked.
  """

→ reader call (UNCHANGED model: deepseek-v3.2; no abstention rule)
```

## Baselines table (REVISED per Rev-3)

### External (mandatory)

| Baseline | What | Where |
|---|---|---|
| Path D `ttmg` | Existing reader on same substrate, no CalLB | Both benchmarks |
| MiCP-on-Path-D | MiCP per-query stopping ported to candidate set | LongMemEval-S |
| Stop-RAG-on-Path-D | Stop-RAG iterative retrieval + RL stop ported | LongMemEval-S |
| Flat hybrid-RAG | Sem + lex RRF, no claim-graph | LongMemEval-S |
| A-Mem | Reimpl from `competitors/A-mem-main` | Memora |
| Mem0 | Best-effort reproduce | Memora |
| LightMem | Best-effort reproduce | Memora |
| EverMemOS | Best-effort reproduce, appendix only | Memora (if Memora-port available) |
| SmartSearch | LoCoMo-only baseline | LoCoMo |

### Attribution baselines (mandatory per round-1 Rev-3, REDEFINED per round-2 Rev-3)

| Ablation | Definition | Tests |
|---|---|---|
| `prompt-only` | Path D's existing top-k, **same load-bearing/supplementary prompt structure**, no MLP, no CRC | Whether prompt restructuring is the real driver |
| `rerank-only` | CalLB MLP ranking, **flat reader prompt** (no tiering) | Whether tiering is what addresses Class C |
| `agreement-heuristic-only` | No MLP; rank by `cross_substrate_agreement` count, semantic-sim tiebreak; load-bearing prompt | Whether the learned MLP is necessary |
| `no_CRC` (REDEFINED) | Same learned MLP scores, **fixed dev-tuned threshold** (median of dev scores OR threshold maximizing dev Class-C-prone slice acc) | Whether CRC adds value beyond reranking |

`random-MLP + CRC` is **dropped** (per round-2 Rev-3 — uninformative, only shows random scores are bad).

### Mechanism ablations

| Ablation | Definition | Tests |
|---|---|---|
| `no_cross_substrate_agreement` | MLP without `cross_substrate_agreement` feature | Class-B fix attribution |
| `no_drift_features` | MLP without {`time_volatility`, `supersede_edge_count`, `validity_interval_freshness`, `contradiction_count`} | KU slice attribution |
| `no_robustness_features` (NEW) | MLP without {`max_substrate_score`, `singleton_raw_turn_hit`, `entity_overlap`} | Whether the new robustness features rescue low-agreement Class-B examples |

### Generality ablation

| Ablation | Definition | Tests |
|---|---|---|
| `portable_features_only` | MLP with only the 5 portable + 3 robustness = 8 substrate-agnostic features | Substrate-agnostic part of contribution |

**Total ablations: 8** (4 attribution + 3 mechanism + 1 generality). 

## Pre-registered Class-B-rescue analysis (NEW per Rev-4)

Before any test runs, commit to this analysis on the **77 Class-B examples** in `results/gating_decomposition.json`:

1. Run CalLB-augmented Path D reader on the 77 questions; measure how many become correct.
2. For each rescued question, classify the rescuing item by its `cross_substrate_agreement` count and `singleton_raw_turn_hit` flag.
3. Report fractions:
   - High-agreement rescues (count ≥ 3): if >50 %, agreement is the load-bearing mechanism.
   - Low-agreement rescues (count ≤ 1) AND `singleton_raw_turn_hit = 1`: if >30 %, robustness features are critical.
   - Low-agreement rescues without singleton-hit: if >30 %, MLP is learning subtle weights — agreement alone is wrong narrative.
4. **Reframing trigger.** If high-agreement rescues are < 30 % of total rescues, the paper positioning shifts from "cross-substrate agreement is the Class-B fix" to "learned multi-substrate signal fusion (with agreement, max-score, singleton-hit, entity-overlap as components) is the Class-B fix".

This is committed in advance to prevent post-hoc narrative shaping.

## Updated Success Conditions

1. **Probabilistic clean-set guarantee on test (formal object).** On Memora test and LongMemEval-S test, empirical `R̂_test(λ̂_α) ≤ α + 0.04` for α ∈ {0.10, 0.20, 0.30, 0.40} (Hoeffding-CRC bound holds; +0.04 is the inflated test-time slack accounting for distribution shift).
2. **B+C-prone slice lift on LongMemEval-S (headline metric).** ≥ **3 pp lift** on the union of B-prone (KU, single-session-preference) + C-prone (single-session-user, multi-session, KU) slices vs Path D `ttmg`; no slice regression > 1 pp.
3. **Attribution causality.**
   - `prompt-only` captures < **50 %** of CalLB's slice lift, otherwise calibration is not the contribution.
   - `rerank-only` < **70 %** of slice lift, otherwise tiering is not load-bearing.
   - `agreement-heuristic-only` < **70 %** of slice lift, otherwise learned MLP is unnecessary.
   - `no_CRC` (same MLP + dev-tuned threshold) breaks per-α coverage AND drops slice lift by ≥ 1 pp, otherwise CRC adds no value.
4. **Mechanism causality.** `no_cross_substrate_agreement` drops Class-B-fix lift by ≥ 50 % OR `no_robustness_features` drops Class-B-fix lift by ≥ 50 % (at least one of the two — narrative will adjust based on which); `no_drift_features` drops KU lift by ≥ 30 %.
5. **Portable subset (honest generality).** `portable_features_only` (8 features) achieves ≥ **50 %** of CalLB's slice lift.
6. **Class-B rescue analysis.** Pre-registered analysis runs and is reported regardless of outcome. Narrative adjusted per Rev-4 trigger.
7. **FAMA — secondary parity.** On Memora full test, CalLB's aggregate FAMA within **3 pp** of best baseline on temporal-forgetting subset.
8. **LoCoMo parity.** Within **2 pp** of best of (Path D, A-Mem, SmartSearch).
9. **Failure clauses (kill conditions).**
   - F1: empirical `R̂(λ̂_α) > α + 0.06` for ≥ 2 of 4 α → CRC bound invalid; report Bernstein retry; if still failing, drop formal claim and reframe as empirical.
   - F2: `prompt-only` ≥ 70 % of slice lift → reframe as "prompt-engineering on TTMG substrate" with CRC supporting evidence.
   - F3: B+C slice lift < 1 pp on ≥ 2 slices → method does not address gating-anchored bottleneck; pivot direction.
   - F4: D-vs-non-D Cohen's κ < 0.65 → labels are too noisy for the theory; fall back to binary `LB` vs `not-LB` and re-derive.

## Compute & Timeline (TIGHTENED per Rev-5)

- **Compute.** ≈ **30 GPU-hour-equivalents** (down from 40 in round-1) on 1–2× RTX-4090. MAAS-only inference; no local training beyond MLP (< 5 min CPU).
- **Data / annotation cost.** Auto-label LLM-judge cost ≈ 10K items × ~3 sec MAAS ≈ **8.3 hr** sequential + **1 hr** author manual audit on 100 stratified-borderline items.
- **Eval matrix (Week 2)** — REDUCED:

| Block | Methods × seeds × bench | Runs | Time @ 30 min/run |
|---|---|---:|---:|
| Primary headline | {CalLB, Path D ttmg} × 3 seeds × LongMemEval-S full | 6 | 3 hr |
| Mandatory baselines | {MiCP, Stop-RAG, Flat-RAG} × 3 seeds × LongMemEval-S full | 9 | 4.5 hr |
| Attribution + mechanism + generality ablations | 8 × 1 seed × LongMemEval-S full | 8 | 4 hr |
| Memora-FAMA secondary | {CalLB, A-Mem, Mem0, LightMem, EverMemOS-appendix} × 1 seed × Memora full | 5 | 2.5 hr |
| LoCoMo parity | {CalLB, Path D, SmartSearch} × 1 seed × LoCoMo full | 3 | 1.5 hr |
| **Total** | | **31** | **~16 hr** |

This fits Week 2 with 4-day debug slack.

- **Timeline.**
  - **Week 1 (build & calibrate)**: features + MLP + CRC + LLM-judge labelling script. Auto-label 10K cal pairs. Manual audit 100 stratified items. Train MLP. Compute Hoeffding-CRC table for 4 α. Lock + commit hash. All intrinsic gates clear (κ ≥ 0.7 or fall-back; AUC ≥ 0.75; per-α dev coverage holds).
  - **Week 2 (eval)**: ~31 runs per matrix above. Generate per-α coverage plot, slice lift bar chart, attribution chart, mechanism ablation chart, portable-vs-full chart, Class-B-rescue analysis, FAMA bars, LoCoMo parity table.
  - **Week 3 (write)**: paper writing + figures. Cite Conformal Risk Control (Angelopoulos 2022, Bates et al. 2021), Conformal-RAG, MiCP, Stop-RAG, BMAM, HiGMem, Path D's underlying TTMG paper.

## Failure Modes and Diagnostics (UPDATED)

- **F1 LLM-judge label noise on 3-class.** Detect: dev κ < 0.7 (full 3-class) OR D-vs-non-D κ < 0.65. Mitigate: 3-call self-consistency on judge → re-label disagreed items → re-audit. Fall-back: collapse to binary `LB` vs `not-LB` and re-derive (theory still holds with binary).
- **F2 MLP underfits.** Detect: dev AUC < 0.7. Mitigate: increase hidden dim to 64; add interaction features; check label imbalance.
- **F3 CRC contamination miss on test.** Detect: empirical `R̂(λ̂_α) > α + 0.06` for any α. Mitigate: switch Hoeffding → Bernstein UCB (tighter for small risks); if cal/test exchangeability fails, run a KS descriptive check and admit honestly.
- **F4 B+C slice lift fails.** Detect: < 1 pp lift on ≥ 2 of union slices. Mitigate: increase `K_supp`; lower α; check tiered prompt is being respected via prompt audit; if persistent, the gating-evidence-driven design intuition is wrong — pivot.
- **F5 `prompt-only` baseline captures most lift.** Detect: ≥ 70 % of slice lift. Mitigate: reframe as "prompt-engineering on TTMG substrate" + CRC supporting; demote calibration from headline.
- **F6 `agreement-heuristic-only` matches MLP.** Detect: ≥ 70 % of slice lift. Mitigate: drop MLP, deliver heuristic + CRC as simpler method.
- **F7 Cross-substrate agreement collinear / hurts.** Detect: in dev, agreement correlates ρ > 0.85 with sem-sim ranking, OR Class-B-rescue analysis shows < 30 % of rescues come from high-agreement items. Mitigate: reframe positioning per pre-registered Rev-4 trigger ("learned multi-substrate signal fusion" not "agreement").
- **F8 Memora-FAMA falls behind.** Detect: ≥ 2 of 4 baselines beat CalLB on temporal-forgetting subset. Mitigate: parity claim downgraded to honest report; do not over-sell.
- **F9 `no_CRC` (same MLP + fixed dev threshold) ≈ CalLB.** Detect: < 1 pp gap. Mitigate: this means the CRC is providing **only the formal guarantee, not empirical lift**. Reframe contribution as "first formal guarantee" (paper-worthy on its own; theoretical contribution).

## Novelty and Elegance Argument (UPDATED)

| Paper | Statistical object | Granularity | Subsumes us? |
|---|---|---|---|
| Conformal-RAG (2506.20978) | Output sub-claim factuality | Per-output-claim | No — different side (output, not input evidence) |
| MiCP (2604.01413) | Per-query stopping coverage | Per-query | No — wrong granularity |
| Stop-RAG (2510.14337) | Per-query stopping (RL) | Per-query | No — non-statistical + wrong granularity |
| BMAM (2601.20465) | None (RRF heuristic) | Per-substrate fusion | No — uncalibrated, no learning |
| HiGMem (2604.18349) | None | Architectural | No — no calibration |
| Conformal Risk Control (2208.02814) | Generic risk control | Generic | Provides the **tool**, not the application |

**Exact difference:** Per-(query, item) **load-bearing** label + Conformal Risk Control with **clean-set indicator risk** on the **probability** the reader-visible load-bearing tier contains any distractor + multi-substrate signal fusion (agreement + max-score + singleton-hit + entity-overlap + TTMG drift features) as learned MLP features.

**Why mechanism-level, not pile-up.** One MLP + one CRC threshold + one prompt update. Contribution summarisable in **one inequality**: `Pr[L_λ̂_α(q) contains distractor] ≤ α`.

(End of round-2 refinement.)
