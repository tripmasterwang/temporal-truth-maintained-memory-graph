# Conformal-Selective-Risk-Controlled Memory — A Calibrated Abstention Operator for Long-Conversation Agents under Forgetting

## Problem Anchor

- **Bottom-line problem.** When an LLM agent answers from accumulated long-conversation memory, two failures recur and no current method handles either with a guarantee:
  1. **Silent reliance on obsolete memory** — facts get updated, contradicted, or invalidated over weeks/months. The Memora benchmark with the new **FAMA** (Forgetting-Aware Memory Accuracy) metric (arXiv 2604.20006, 2026) measures this directly: long-term memory agents lose 18–30 pp from naive accuracy to FAMA, and the gap *grows* with timeline length.
  2. **Over-confident answering on contradictions** — when retrieved evidence disagrees on a single-slot value, every existing memory system (A-Mem 2025, Mem0, MemoryOS, LightMem 2025, SimpleMem 2026, EverMemOS 2026, SmartSearch 2026) returns *some* answer, none provides a coverage guarantee on the abstention decision.
- **Must-solve bottleneck.** A *calibrated* read-time decision rule that gives an explicit, verifiable risk guarantee `Pr[wrong | answered] ≤ α` on the answer/abstain choice, validated end-to-end by FAMA.
- **Non-goals.** Not chasing LoCoMo SOTA (race over: EverMemOS 92.3 %, SmartSearch 91.9 %). Not a token-efficiency paper. Not a new-benchmark paper (Memora exists). Not a write-time consolidation method (Diagnosing-Memory 2603.02473 shows write strategy contributes only 3-8 pp vs retrieval's 14-23 pp). Not a slot-in conflict layer (Path A, deferred).
- **Constraints.** 1–2 RTX-4090-class GPUs; MAAS API for writer/parser/reader/linker (no Agent tool); reuse `ttmg/{schema, writer_temporal, conflict_linker, truth_retriever, system}.py` as substrate (the type-level + supersede + linker machinery built across rounds 0-4 of Path D). 3-4 weeks compute budget. NeurIPS / ICML main-track target.

## Success Conditions

1. **Selective-risk guarantee (headline, exact).** On Memora test, for each α ∈ {0.05, 0.10, 0.15, 0.20, 0.25} and each *effective merged calibration group* `g ∈ G_eff`, empirical selective risk `r̂_g(τ̂_g(α; δ))` ≤ α + 0.02. Theorem: with probability ≥ 1 − δ over the draw of the calibration sample, the true conditional risk per group is ≤ α (exact via Clopper-Pearson + Bonferroni over `|G_eff| · |A| · |T_cand|`).
2. **Risk-coverage Pareto-dominance on Memora's temporal-forgetting subset.** TTMG-β's risk-coverage curve dominates A-Mem, Mem0, LightMem, EverMemOS-on-Memora at every answer rate ∈ [0.4, 0.9] on the temporal-forgetting subset (`update_pattern ∈ {multi-update, supersede-heavy}` ∧ time-sensitive slot type). Fallback summary metric: AURC (Area Under Risk-Coverage curve) — TTMG-β strictly lower (paired-bootstrap over (persona × duration) clusters, p<0.05) in case curves cross locally. Matched-rate marker at α = 0.10 reported on the curve.
3. **Aggregate-Memora FAMA non-regression.** TTMG-β within 5 FAMA-points of best baseline at matched answer rate on full Memora aggregate.
4. **Parity preservation on LongMemEval-S.** TTMG-β within 2 pp of best of (Flat, A-Mem) on overall accuracy.
5. **Mechanism causality.** `no_conformal` (revert to Path D's MWIS abstention) breaks the selective-risk guarantee; `no_groups` (marginal CP only) preserves marginal but breaks per-group conditional risk on at least 2 of `|G_eff|` cells.
6. **`update_pattern` proxy validation.** Spearman ρ ≥ 0.6 between the inference-time `update_pattern` label and Memora-derived ground-truth update count, on dev.
7. **KS-test drift diagnostic** (descriptive, not gate). Report KS statistic and p-value on the joint `(pmi_bin, update_pattern)` distribution between calibration and test splits as a transparency diagnostic; do not condition the analysis on its outcome.
8. **Failure clause.** Design fails if (a) selective risk exceeds `α + 0.04` on test for ≥ 2 of 5 α values, OR (b) AURC fails to show strict TTMG-β advantage on the temporal-forgetting subset (paired-bootstrap p<0.05) AND risk-coverage Pareto-dominance fails, OR (c) parity on LongMemEval-S breached by > 5 pp, OR (d) `update_pattern` proxy validation fails (ρ < 0.4).

## Technical Gap

A keyword scan of all 141 .tex files in the survey corpus (`MemMachine/competitor/`) returned **zero matches** in body text for: *conformal*, *calibrat-* (in method context), *off-policy / importance sampling*, *mutual information*, *PAC*, *sequential test*, *Lagrang-*, *bandit*. This is a **structural** white-space — the entire 2023-2026 memory subfield uses no statistical / information-theoretic machinery. The RAG community has the tools we need:

1. **Conformal-RAG (arXiv 2506.20978, SIGIR 2025).** Marginal CP on retrieval-grounded sub-claims with score `R(c) = max_j cos(q, d_j) · cos(c, d_j)` and threshold `q̂ = ⌈(n+1)(1−α)⌉/n`-quantile, gives `Pr[y* ⇒ y_test(x; q̂)] ≥ 1−α` with Mondrian for group-conditional. Reduces 86.8 % → 8.9 % claim removal at 85 % factuality on MedLFQA.
2. **PMI-RAG (arXiv 2411.07773).** Pointwise mutual information `PMI(q, C) = log[P(q | C) / P(q)]` correlates affinely with answer log-odds, `r > 0.8` across 5 LMs on NQ-Open / ELI5. Frozen-LM, no labels, no training.
3. **Selective Classification (Geifman & El-Yaniv 2017) + Conformal Risk Control (Angelopoulos et al. 2022) + Distribution-free Risk-Controlling Prediction Sets (Bates et al. 2021).** The correct statistical machinery for an answer/abstain guarantee — not vanilla split-conformal coverage on prediction-set inclusion.
4. **Diagnosing-Memory (arXiv 2603.02473).** *Retrieval method drives 20 pp accuracy spread; write strategy drives only 3-8 pp* on LoCoMo. Empirically validates that the entire write-time-elaboration arms race has poor ROI vs read-time investment.
5. **Memora + FAMA (arXiv 2604.20006).** Long-term memory benchmark with explicit memory-trace ground truth (add/update/delete operations across weeks-to-months). **No memory system has published FAMA scores yet**, including EverMemOS.

EverMemOS (arXiv 2601.02163, Jan 2026) hard-filters by validity intervals (`MemCell.foresight = [t_start, t_end]`) — so `valid_from / valid_to` per claim is *not* novel. SmartSearch (arXiv 2603.15599, Feb 2026) reaches 91.9 % LoCoMo with deterministic CPU-only retrieval — so the *system-level* novelty bar on LoCoMo is impossibly high. Both threats *force* the contribution to be on a different axis: a *guarantee* (exact finite-sample selective-risk control) and a *new metric* (FAMA), neither of which any 2026 memory system reports.

## Method Thesis

*For each retrieved memory subset relevant to a query, compute a hardness-weighted scalar confidence score `S(q)`; on a held-out dev split fix candidate-threshold sets per inference-time-defined group; on a calibration split, evaluate one pre-frozen threshold per (g, α) using **Clopper-Pearson exact one-sided UCB** with Bonferroni correction over the joint (g, α, τ) selection event; at inference, answer iff `S(q) ≥ τ̂_g(α; δ)` and unique-value, else abstain — yielding **exact finite-sample** `Pr[ wrong | answered, g ] ≤ α` with probability ≥ 1 − δ over the calibration sample.*

- **Smallest adequate intervention.** One CRC layer (~120 lines) + one PMI estimator (~20 lines, one frozen-LM call per applicable query). No new training, no new architecture, no auxiliary head. The substrate (Path D schema + canonicalizer + 3-call linker + applicability gate + canonical-key fetch) is reused as engineering scaffolding, *not* contribution.
- **Why timely.** (i) Memora + FAMA just dropped; field will flock to it. (ii) Diagnosing-Memory empirically validates the architectural finding ("retrieval dominates"). (iii) Conformal / CRC machinery is mainstream in classical ML; its absence in memory is a *structural* gap. (iv) EverMemOS hits 92.3 % LoCoMo without a guarantee — the next move *has to be* guarantees.

## Contribution Focus

- **Dominant contribution.** A *selective-risk-controlled abstention rule* for memory-augmented answering with **exact finite-sample** `Pr[ wrong | answered, g ] ≤ α` selective-risk control at multiple α levels and finite-sample δ-coverage on Memora — the first memory operator with a correctly-stated selective-risk guarantee. Headline numbers on Memora's *temporal-forgetting subset* with risk-coverage curve as the primary baseline comparison.
- **Optional supporting contribution.** PMI-bin Mondrian axis + phase-diagram diagnostic (frozen-LM, training-free) characterising when calibrated abstention strictly dominates hard thresholding.
- **Explicit non-contributions.**
  - Not a LoCoMo / LongMemEval-S accuracy win (parity claimed, not headline).
  - Not a new memory architecture (substrate reused).
  - Not a new benchmark (Memora exists).
  - Not a contribution about typed claim graphs, validity intervals, supersede edges, or applicability gates *in isolation* — EverMemOS already does the validity-interval part.
  - Not a contribution about MWIS or canonical-key fetch.
  - **The selective-risk guarantee is what we own.**

## Proposed Method

### Complexity Budget

- **Frozen substrate (Path D rounds 0-4).** TTMG schema with `(claim_key=(entity_id, slot_name), slot_type, object_norm, valid_from, valid_to, polarity, confidence, active, superseded_by)`, deterministic canonicalizer (lowercase + lemma + alias map), 3-call-agreement linker producing `hardness ∈ {0/3, 1/3, 2/3, 3/3}` and label ∈ `{contradict, supersede, unrelated}`, `valid_to ← valid_from − ε` materialisation on hard supersede, applicability gate routing non-applicable queries to Flat fallback, canonical-key fetch on the applicable path. **Engineering scaffolding for β, not contribution.**
- **New (2 deltas).**
  1. CRC layer (`ttmg/crc.py`, ~120 lines): pre-frozen candidate thresholds + Clopper-Pearson exact one-sided UCB + Bonferroni correction over `|G_eff| · |A| · |T_cand|` + answer-rate floor `N_min = 30` + hierarchical group-merging fallback yielding `G_eff`.
  2. PMI estimator (`ttmg/pmi.py`, ~20 lines): one frozen-LM `/v1/completions` call per applicable query.
- **Tempting additions intentionally not used.** No adaptive grid search (replaced by pre-frozen candidate thresholds); no Wilson UCB (replaced by Clopper-Pearson); no weighted conformal (future work); no linker fine-tune; no Swin-VIB; no agentic multi-round retrieval; no new MWIS solver; no reranker.

### Score Function `S(q)`

```
Opts = max-weight independent sets on hard-edge subgraph over canonical-key-fetch(q) ∩ valid_at(τ_q)
Vals = ⋃_{I ∈ Opts} { c.object_norm : c ∈ I }
S(q) = w_h · mean( hardness(c) for c ∈ ⋃ Opts )
     + w_u · 1[ |Vals| == 1 ]
     + w_p · clip( PMI(q, M_q) / PMI_scale, 0, 1 )
```
`(w_h, w_u, w_p, PMI_scale)` tuned on dev (initial `(0.5, 0.3, 0.2)`); locked before calibration.

### Mondrian Group (inference-time-computable)

```
At inference, given q with canonical-key K and time τ_q:
    slot_history(K, τ_q)        = { c : c.claim_key == K, c.created_at ≤ τ_q }
    n_supersede_edges(K, τ_q)   = # supersede edges in slot_history with hardness ≥ 2/3
    n_active_values(K, τ_q)     = | { c.object_norm : c ∈ slot_history, valid_at(c, τ_q) } |
    n_temporal_updates(K, τ_q)  = # distinct values across distinct timestamps in slot_history
    conflict_degree(K, τ_q)     = # contradict edges in slot_history with hardness ≥ 2/3

update_pattern(q) :=
    "single-trace"     if n_temporal_updates ≤ 1 AND n_supersede_edges == 0
    "multi-update"     if n_temporal_updates ≥ 2 AND n_supersede_edges ≤ 1
    "supersede-heavy"  if n_supersede_edges ≥ 2 OR (n_active_values ≥ 2 AND conflict_degree ≥ 1)

g(q) := ( pmi_bin(q), update_pattern(q) )      ∈ G  (nominal 9-cell grid)
```
Hierarchical-merge fallback: if `n_g < N_min = 30`, merge along `update_pattern` axis first (preserves the temporal-forgetting interpretation), then along PMI bin. The result is the **effective merged partition `G_eff`**. The theorem (below) holds over `G_eff`. Memora metadata used only to validate the proxy on dev (Spearman ρ ≥ 0.6).

### Strict 3-Way Split Protocol

```
Memora train (60 %) → DEV
    Tune (w_h, w_u, w_p, PMI_scale).
    Fix pmi_bin boundaries (3-quantile of S(q) on dev).
    Fix update_pattern bin boundaries.
    Validate update_pattern proxy: Spearman ρ ≥ 0.6 vs Memora ground truth.
    Define candidate threshold sets T_cand(g) (5 quantiles per cell).
    Tune baseline confidence thresholds for matched-abstention reporting.

Memora train (40 %) → CALIBRATION
    Run inference for all calibration samples.
    Apply hierarchical merging to obtain G_eff with min n_g ≥ N_min.
    Evaluate ONE pre-frozen threshold per (g, α) using Clopper-Pearson UCB.
    Lock threshold_table; commit hash to git; print hash in paper.

Memora test → TEST
    One shot. No tuning. Report per-group + aggregate selective risk + risk-coverage curves + AURC.
```

### CRC Calibration

```python
threshold_table = {}
G_eff = hierarchical_merge(Cal, axis_priority=["update_pattern", "pmi_bin"], N_min=30)
for g in G_eff:
    Cal_g = [i in Cal : g_i == g]
    for α in A:
        δ_corr = δ / (|G_eff| · |A| · |T_cand(g)|)        # Bonferroni
        for τ in sorted(T_cand(g), ascending):
            answered = [i in Cal_g : S_i ≥ τ]
            if len(answered) < N_min: continue
            wrong = [i in answered : ŷ_i ≠ y_i*]
            UCB = clopper_pearson_upper(len(wrong), len(answered), 1 − δ_corr)   # EXACT
            if UCB ≤ α:
                threshold_table[g, α] = τ
                break
        else:
            threshold_table[g, α] = ∞                       # always-abstain fallback
# Lock + commit hash; print hash in paper.
```

### Theorem (exact, finite-sample, distribution-free)

> **Theorem (selective risk control).** Let `Cal` be a calibration sample and let `G_eff` denote the effective merged partition resulting from the hierarchical-merging step. Under exchangeability of `Cal` with the test distribution, with probability at least `1 − δ` over the draw of `Cal`, for every `g ∈ G_eff` and every `α ∈ A`,
>
> `P_test[ ŷ ≠ y* | S ≥ τ̂_g(α; δ), g(q) = g ] ≤ α.`
>
> *Proof.* For any fixed `(g, α, τ)`, Clopper-Pearson inversion of the binomial gives `Pr[ true selective risk > UCB_CP ] ≤ δ_corr` (exact, finite-sample, distribution-free). Bonferroni over the joint event `{(g, α, τ) : g ∈ G_eff, α ∈ A, τ ∈ T_cand(g)}` gives `δ_corr = δ / (|G_eff| · |A| · |T_cand(g)|)`. The chosen `τ̂_g(α; δ)` is the smallest candidate satisfying `UCB_CP ≤ α`; the conditional risk at that τ is therefore ≤ α with probability ≥ 1 − δ_corr per (g, α). Union bound over all (g, α) gives ≥ 1 − δ. ∎

**Citations.** Clopper & Pearson 1934 (exact binomial CI); Geifman & El-Yaniv 2017 (selective classification); Angelopoulos et al. 2022 (CRC); Bates et al. 2021 (distribution-free risk-controlling prediction sets).

### Inference

```python
parser_out = parse(q, t_q)              # (claim_key_q, slot_type_q, τ_q, applicable)
if not parser_out.applicable:
    return Flat(q)
cand = SP_index.fetch_all(claim_key_q)
cand = [c for c in cand if valid_at(c, τ_q, parser_out.asks_history)]
if len(cand) == 0:
    cand = topK_emb(q) ∪ topK_bm25(q)   # FALLBACK (logged, audited)
Opts = exact_MWIS(cand, hard_edges)
Vals = { c.object_norm : c ∈ ⋃ Opts }
pmi_q = PMI(q, concat(cand))            # one frozen-LM call
S_q   = w_h * mean(hardness in ⋃Opts) + w_u * (|Vals|==1) + w_p * clip(pmi_q / PMI_scale, 0, 1)
g_q   = (pmi_bin(pmi_q), update_pattern(q))   # mapped to G_eff if merged
α     = 0.10                                  # paper default
if S_q >= threshold_table[g_q, α] and |Vals| == 1:
    return reader(q, any I in Opts, value=Vals.pop())
else:
    return ABSTAIN(reason="below_CRC_threshold", S_q=S_q, τ̂=threshold_table[g_q, α], g_q=g_q, pmi_q=pmi_q)
```

### Modern Primitives

Two LLM uses on top of the Path D substrate, both already in the existing MAAS budget:
- **PMI estimator** (frozen-LM prefix probability — *no additional model*).
- **Linker** (already 3-call agreement; we reuse the hardness as the conformal score input — *no change*).
Calibration is one-shot, offline, before any test-time runs.

### Integration

- **Files touched.** `ttmg/truth_retriever.py` (replace MWIS-abstention with CRC threshold rule); NEW `ttmg/crc.py` (~120 lines); NEW `ttmg/pmi.py` (~20 lines); NEW `scripts/calibrate_crc.py` (~150 lines, runs over Memora train, locks `threshold_table` and commits hash); minor `ttmg/system.py` additions for PMI toggle + CRC flag.
- **Files frozen.** Path D's `schema.py`, `writer_temporal.py`, `conflict_linker.py`, `canonicalize.py`.

### Pre-test Gates (before any test-time runs)

- **Per-group dev coverage** (held-back 10 % of dev): per-group empirical selective risk under the locked threshold ≤ α + 0.02 for all 5 α, all groups in `G_eff`.
- **PMI estimator stability**: Spearman ρ ≥ 0.5 between PMI estimate and answer-correctness on dev.
- **`update_pattern` proxy validation**: Spearman ρ ≥ 0.6 vs Memora ground-truth update count on dev.
- **KS-test calibration vs test on `(pmi_bin, update_pattern)`**: report KS statistic and p-value as a *descriptive drift diagnostic* — *not* a decision gate. Document any drift transparently.

### Failure Modes and Diagnostics

- **C1 Calibration miscoverage on Memora test.** Detect: per-group empirical risk exceeds α + 0.04 on test for any (g, α). Mitigate: hierarchical group-merging (already automatic); fall back to *aggregate-only* selective-risk guarantee if conditional fails. Report honestly.
- **C2 PMI signal collapses on memory slots vs RAG documents.** Detect: dev Spearman ρ < 0.3. Mitigate: drop PMI from S, use `(w_h, w_u) = (0.7, 0.3)`; PMI-bin axis collapses to single bin; PMI phase diagram becomes a negative result.
- **C3 Risk-coverage Pareto-dominance fails locally on temporal-forgetting subset.** Detect: curves cross at some answer-rate. Mitigate: use AURC as fallback summary metric; report the cross-point honestly; success condition (8) treats AURC dominance as a *separate* success requirement so a local cross still allows a paper claim if AURC dominates.
- **C4 EverMemOS code does not run / not reproducible.** Detect: code in `MemMachine/competitor/2601.02163_EverMemOS/code/` fails install or doesn't reproduce LoCoMo within 5 pp. Mitigate: cite published numbers; pair-compare on Memora only.
- **C5 Calibration / test distribution shift (KS detected).** Detect via the descriptive KS diagnostic. Mitigate: report drift transparently; if shift is substantial, state weighted conformal as future work.
- **C6 Group cell underpopulated.** Detect: `n_g < N_min` after hierarchical merging. Mitigate: collapse `pmi_bin` from 3 → 2 quantiles; if still failing, marginal-only guarantee (theorem still holds on `G_eff = {⋆}`).
- **C7 Trivial "abstain more to look safer" objection.** Mitigated *by design* via risk-coverage curve as primary figure and matched-abstention as a marker on the curve.
- **C8 `update_pattern` proxy fails validation (ρ < 0.4).** Mitigate: re-tune bin boundaries on dev; if still failing, drop the axis (marginal-only or single-axis Mondrian).

### Novelty and Elegance Argument

- **Closest work.** Conformal-RAG (SIGIR 2025) — split CP on RAG sub-claim factuality; PMI-RAG — PMI as frozen-LM correctness gauge; EverMemOS (Jan 2026) — structured memory with foresight intervals + 92.3 % LoCoMo; SmartSearch (Feb 2026) — deterministic retrieval + 91.9 % LoCoMo. Selective-classification literature: Geifman & El-Yaniv 2017; CRC: Angelopoulos et al. 2022; Bates et al. 2021.
- **Exact difference.**
  - Vs Conformal-RAG: it controls *prediction-set inclusion* on RAG sub-claim factuality with cosine-similarity scores; we control *conditional-on-answer selective risk* with a *typed-conflict-graph hardness* score over a memory subgraph at time `τ_q`, with Mondrian groups defined from inference-time graph features. Different statistical object, different score function, different application domain.
  - Vs EverMemOS: hard-filters by foresight intervals (no guarantee). We give a *finite-sample selective-risk guarantee* with explicit answer-rate trade-off. Calibrated dynamically per-group.
  - Vs SmartSearch: deterministic ranker (no guarantee, no group-conditional behaviour). Our coverage holds at the test distribution under exchangeability with finite-sample δ-confidence.
  - Vs PMI-RAG: PMI selects *context permutations*; we use PMI as one of three score axes + as a Mondrian calibration covariate + as a phase-diagram diagnostic.
  - Vs generic CRC / selective-classification: those operate on i.i.d. classification with a single confidence score; we operate on *agent memory at time τ* with a typed conflict graph as the score's substrate, and *Memora memory traces* as the calibration ground truth. The temporal-forgetting subset is the empirical centre.
- **Why mechanism-level (statistical), not architectural pile-up.** One CRC layer + one PMI estimator + a calibration script. The contribution is the *guarantee*, not the architecture. The paper's result is summarisable in one inequality — the theorem above. The temporal-forgetting subset is the locus where the gap to baselines concentrates.

## Claim-Driven Validation Sketch

### Claim 1 (Dominant) — Selective-risk guarantee + risk-coverage Pareto-dominance on temporal-forgetting subset

- **Statement.** On Memora test, per-group + aggregate selective risk `r̂_g(τ̂_g(α; δ))` ≤ α + 0.02 for all 5 α and all g ∈ G_eff (theorem-backed). On the temporal-forgetting subset, TTMG-β's risk-coverage curve Pareto-dominates A-Mem, Mem0, LightMem, EverMemOS-on-Memora at every answer rate ∈ [0.4, 0.9]; AURC strictly lower (paired-bootstrap p<0.05). Matched-rate marker at α = 0.10 on the curve.
- **Minimal experiment.** 5 methods × 3 seeds × deepseek-v3.2 × Memora full test. Cal on Memora train (60 % dev / 40 % calibration).
- **Baselines / ablations.** Flat hybrid-RAG; A-Mem reimpl; Mem0 reimpl; LightMem; EverMemOS (best-effort reproduction from `MemMachine/competitor/.../code` — appendix); TTMG-β full; ablations: `no_conformal` (revert to Path D MWIS abstention), `no_groups` (marginal CP only) — main text.
- **Metric.** Per-group + aggregate selective risk + Clopper-Pearson UCB band; risk-coverage curve; AURC; matched-rate marker; cluster-bootstrap CIs over (persona × duration); per-cell `(n_g, abstain_mass_g)` table.
- **Expected evidence.** Guarantee holds for all (g, α). Risk-coverage curve: TTMG-β Pareto-dominates baselines on temporal-forgetting subset; AURC strictly lower. `no_conformal` breaks guarantee. `no_groups` aggregate-OK but per-group violations on ≥ 2 of |G_eff| cells. Per-cell n_g ≥ 30 after merging.

### Claim 2 (Supporting) — Parity on LongMemEval-S + PMI phase diagram + `update_pattern` proxy validation

- **Statement.** TTMG-β within 2 pp of best of (Flat, A-Mem) on LongMemEval-S overall (3 seeds, deepseek-v3.2). PMI phase diagram on Memora dev: gap (TTMG-β AURC − best-baseline AURC) increases monotonically with PMI bin index, largest gap in high-PMI bin. `update_pattern` proxy Spearman ρ ≥ 0.6 vs Memora ground truth on dev.
- **Minimal experiment.** 3 methods × 3 seeds × 1 backbone × LongMemEval-S N=500. Plus PMI-bin breakdown of Claim-1 results. Plus `update_pattern` proxy validation on dev.
- **Expected evidence.** Parity (within 2 pp). Monotone increasing AURC gap with PMI bin. Proxy ρ ≥ 0.6.

(MAX_PRIMARY_CLAIMS = 2 honored.)

## Experiment Handoff Inputs

- **Must-prove claims.** (1) per-group selective-risk guarantee at 5 α values + AURC dominance on Memora's temporal-forgetting subset; (2) parity on LongMemEval-S + PMI phase diagram + `update_pattern` proxy validation.
- **Must-run ablations.** `no_conformal`, `no_groups` (main text); `no_pmi`, `no_canonical_key`, `no_3call_agreement` (appendix).
- **Critical datasets / metrics.** Memora train (60 % dev / 40 % calibration) + Memora test (one-shot); LongMemEval-S full N=500 (parity); LoCoMo (appendix); per-group empirical selective risk + Clopper-Pearson UCB; risk-coverage curves; AURC; matched-rate FAMA; key-fetch-fallback rate; per-cell `(n_g, abstain_mass_g)`. EverMemOS on Memora only (appendix).
- **Highest-risk assumptions.** (i) Memora's `update_pattern` metadata is reliable enough to validate the inference-time graph proxy at ρ ≥ 0.6. (ii) `Edge.hardness` from the 3-call linker is calibrated enough to be a useful CRC score input. (iii) PMI on memory-slot context behaves comparably to RAG-document context. (iv) Memora calibration / test split exchangeable enough that CRC coverage holds. (v) EverMemOS reproduces within 5 pp on its own benchmarks from `competitor/.../code`.

## Compute & Timeline Estimate

- **Compute.** All inference via MAAS API; no local training. ≈ **35 GPU-hour-equivalents** on 1–2× RTX-4090 budget.
- **Data / annotation cost.** Use Memora-supplied memory-trace ground truth (no fresh annotation).
- **Timeline.**
  - **Week 1.** Pull Memora train/test data; integrate CRC layer + PMI estimator; tune `(w_h, w_u, w_p, PMI_scale)` on dev; fix pmi_bin and update_pattern bin boundaries; validate update_pattern proxy (ρ ≥ 0.6); define `T_cand(g)` (5 quantiles per cell); tune baseline confidence thresholds for matched-abstention reporting; all intrinsic gates clear; lock `threshold_table` + commit hash.
  - **Week 2.** Full Memora test runs for 5 methods × 3 seeds; LongMemEval-S parity runs (3 methods × 3 seeds); reproduce EverMemOS from `competitor/2601.02163_EverMemOS/code/` (appendix).
  - **Week 3.** Ablations (`no_conformal`, `no_groups` main; `no_pmi`, `no_canonical_key`, `no_3call_agreement` appendix); risk-coverage curves; AURC summary; matched-rate marker; PMI phase diagram; cluster-bootstrap CIs over (persona × duration); per-cell `(n_g, abstain_mass_g)` table; KS drift diagnostic.
  - **Week 4.** Paper rewrite framing the contribution as *the first selective-risk-controlled abstention rule for memory* with the temporal-forgetting subset as the empirical centre; figures (per-group reliability plot at 5 α with Clopper-Pearson UCB band, risk-coverage curve with matched-abstention markers, FAMA bars on temporal-forgetting subset with cluster-bootstrap CIs, ablation drop bars, PMI phase diagram, `update_pattern` proxy scatter); reconcile prior `STATUS.md`; cite EverMemOS, SmartSearch, Diagnosing-Memory, Memora, Conformal-RAG, PMI-RAG, CRC, Selective Classification, Clopper-Pearson.

## Polish Items (from round-3 reviewer)

- The theorem is stated over the **effective merged partition `G_eff`**, not the nominal 9-cell grid (incorporated above).
- The **KS-test calibration vs test** check is a *descriptive drift diagnostic*, not a decision gate (incorporated in §pre-test gates and §failure modes).
- **Risk-coverage Pareto-dominance** is paired with an **AURC fallback summary** so the success condition still holds if curves cross locally (incorporated in success conditions and Claim 1).
