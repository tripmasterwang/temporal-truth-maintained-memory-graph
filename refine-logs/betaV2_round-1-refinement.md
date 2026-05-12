# Round 1 Refinement — Pivot β v2

## Problem Anchor (verbatim from round 0)

- **Bottom-line problem.** When an LLM agent answers from accumulated long-conversation memory, two failures recur and no current method handles either with a guarantee: (1) silent reliance on obsolete memory; (2) over-confident answering on contradictions.
- **Must-solve bottleneck.** A *calibrated* read-time decision rule that gives an explicit, verifiable risk guarantee on the answer/abstain choice, validated end-to-end by a benchmark whose evaluation metric *itself* tracks the failure mode (FAMA).
- **Non-goals.** Not chasing LoCoMo SOTA. Not token-eff. Not new benchmark. Not write-time consolidation. Not Path-A slot-in.
- **Constraints.** 1–2 RTX-4090; MAAS API; reuse `ttmg/{schema, writer_temporal, conflict_linker, truth_retriever, system}.py` as substrate. 3–4 weeks. NeurIPS / ICML main.
- **Success condition.** (See round-1 restated success conditions below — the conditional-on-answer guarantee form is replaced with a *selective-risk* form, which is what the method actually delivers.)

## Anchor Check

- **Original bottleneck.** Truth maintenance under forgetting + abstention quality on contradictions, with a *guarantee*.
- **Why the revised method still addresses it.** Round-1 changes upgrade the statistical target (from the overclaimed `Pr[wrong | answered, g] ≤ α` to a *selective-risk* target `Pr[r̂(τ̂_g) > α] ≤ δ` with finite-sample UCB) and re-centre the empirics on temporal-forgetting subsets. The bottleneck is unchanged; the operator gives a *correctly-stated* guarantee.
- **Reviewer suggestions rejected as drift.** None. Reviewer flagged drift = NONE major; flagged the framing risk that PMI / generic confidence could take over the story — round-1 protects against this by (a) keeping the conformal score function rooted in the *typed conflict graph* (linker hardness + |Vals|), with PMI as one of several signal axes, and (b) leading the empirics with supersede-heavy / multi-update temporal-forgetting subsets so the temporal conflict story stays primary.

## Simplicity Check

- **Dominant contribution after revision.** A *selective-risk-controlled abstention rule* for memory-augmented answering — calibrated against held-out Memora memory traces — that gives finite-sample UCB-controlled selective risk `Pr[ wrong | answered, g ] ≤ α` with explicit answer-rate floor, validated on temporal-forgetting subsets where the FAMA metric is most punishing. The first memory operator with a *correctly stated* selective-risk guarantee.
- **Components removed or merged.**
  - **Path D's controlled supersede slice** removed from calibration; kept only as a *stress diagnostic*. (Reviewer-mandated to avoid covariate-shift confounding in calibration.)
  - **Mondrian groups simplified** to one calibration axis × one secondary axis. Drop `abstention` (it's an outcome). Drop `KU / TR / slot type` from calibration (reporting strata only).
  - **`no_pmi` ablation moved to secondary.** PMI is a Mondrian-axis input + a phase-diagram diagnostic — not the headline signal.
  - **One parity benchmark only in main text** (LongMemEval-S — closer to FAMA's question style than LoCoMo and reuses the project's existing N=500 runs); LoCoMo → appendix.
  - **EverMemOS reproduction** moved out of the main empirical pipeline. We cite EverMemOS's *published* numbers and only run it on Memora (the one benchmark where neither side has published numbers, eliminating reproduction-bias).
- **Reviewer suggestions rejected as unnecessary complexity.** None. Each round-1 critique either fixes a statistical-overclaim bug, narrows the empirical surface, or makes the temporal-forgetting story primary.
- **Why the remaining mechanism is still the smallest adequate route.** One CRC layer (~120 lines, slightly bigger than round-0's vanilla split-CP layer because of the UCB + multiple-testing correction + answer-rate floor + group-merging logic), one PMI estimator (~20 lines, one frozen-LM call). Substrate (Path D schema + canonicalizer + 3-call linker + applicability gate + canonical-key fetch) reused as scaffolding.

## Changes Made

### 1. Selective risk control (CRC) replaces vanilla split conformal (CRITICAL)
- **Reviewer said:** "The current 'standard split-conformal' claim does not establish `Pr[wrong | answered, g] ≤ α`. That conditional-on-answer event is the hard part. Recast as selective risk control. Define scalar confidence `S(q)`. On held-out Memora calibration split, for each group `g` and threshold `τ`, estimate `r_g(τ) = #{wrong AND S≥τ} / #{S≥τ}`. Choose smallest τ whose one-sided UCB ≤ α, with min answered-count floor. CRC / selective-classification machinery; Wilson / Clopper-Pearson UCB + multiple-testing correction."
- **Action.** Rewrite the statistical target as **selective-risk control with finite-sample upper-confidence bound**:
  ```
  Selective risk:        r_g(τ) := P[ ŷ ≠ y* | S(q) ≥ τ, g(q) = g ]
  Empirical estimate:    r̂_g(τ) := #{ i : g(q_i)=g, S(q_i) ≥ τ, ŷ_i ≠ y_i* } / #{ i : g(q_i)=g, S(q_i) ≥ τ }
  Wilson UCB at level 1−δ:   r̂_g(τ) ≤ U_{1−δ}( #wrong, #answered )
  Calibrated threshold:  τ̂_g(α; δ) := min{ τ ∈ Grid_τ : U_{1−δ}( ŵ_g(τ), n̂_g(τ) ) ≤ α  AND  n̂_g(τ) ≥ N_min }
  Multiple-testing correction:  use Bonferroni across the (g, α) grid: δ → δ / (|G| · |A|)
  ```
  with `Grid_τ` = 50-point equispaced over the empirical S-range on calibration; `N_min = 30` (answer-count floor); `δ = 0.10` (so headline guarantee is "with prob ≥ 0.90 over the calibration sample, selective risk ≤ α on the test distribution"). When `τ̂_g(α; δ)` does not exist (i.e. no τ achieves UCB ≤ α with N_min answers), the system **always abstains** in group g — and we report the abstain-everywhere rate as part of the headline.
- **Theorem / guarantee statement (paper version).**
  > **Proposition (selective risk control).** Under exchangeability of the calibration set with the test set, for the threshold `τ̂_g(α; δ)` defined above, with probability at least `1 − δ_total` (where `δ_total = δ` after Bonferroni), for each group `g`,
  > `P_test[ ŷ ≠ y* | S ≥ τ̂_g(α; δ), g(q) = g ] ≤ α`.
  > Proof sketch: Wilson UCB on a binomial proportion with `n_g(τ)` answered samples gives a distribution-free upper bound on the true conditional miss rate; the smallest threshold meeting `UCB ≤ α` therefore guarantees the true selective risk is ≤ α with the stated coverage. Bonferroni handles the (g, α) grid.
- **References to cite.** Angelopoulos et al. 2022 ("Conformal Risk Control"); Geifman & El-Yaniv 2017 ("Selective Classification"); Bates et al. 2021 ("Distribution-free, Risk-Controlling Prediction Sets"); Wilson 1927 (binomial UCB).
- **Reasoning.** This is the correct statistical object for an answer/abstain guarantee. The previous round-0 split-conformal framing was overclaimed: split CP gives marginal coverage on prediction-set inclusion events, not on the conditional-on-answer error event. CRC / selective-classification machinery is the right modern tool, and the reviewer correctly named it.
- **Impact on core method.** The mechanism is unchanged (score, threshold lookup, group routing), but the *guarantee* is now correctly stated and tight to what the calibration actually proves. No more overclaim risk.

### 2. Lead with temporal-forgetting subsets (CRITICAL)
- **Reviewer said:** "Make obsolete-memory cases the paper's primary unit of analysis. Lead with supersede-heavy / multi-update / time-sensitive subsets, and show that the gain concentrates there."
- **Action.** Restructure the results section: lead Table 1 with **the temporal-forgetting subset of Memora** (`update pattern ∈ {multi-update, supersede-heavy}` + `time-sensitive` slot types). Show that on this subset the conformal layer's selective-risk guarantee + answer-rate is strictly better than every baseline at matched abstention rate. Aggregate Memora results follow as a secondary table; LongMemEval-S parity follows in §5.2; LoCoMo is appendix-only.
- **Reasoning.** Reviewer is right that without this, the paper reads as "generic selective QA". Leading with the temporal-forgetting subset makes the truth-maintenance / under-forgetting framing the paper's empirical centre — not just its abstract motivation.
- **Impact on core method.** No method change. The empirics are now organised so that the bottleneck the method was designed for is the bottleneck the headline numbers measure.

### 3. Mondrian simplified; `abstention` axis dropped (CRITICAL)
- **Reviewer said:** "`abstention` cannot be a group axis if it is an outcome rather than a pre-decision covariate. Reduce Mondrian to `PMI bin × update pattern` or `conflict degree × update pattern`. Keep KU/TR/slot type as reporting strata, not calibration strata. Collapse groups aggressively or use hierarchical merging with minimum n_g."
- **Action.** Mondrian-group axis is now a *single 2-D grid*:
  ```
  g(q) := ( pmi_bin(q), update_pattern(q) )
  pmi_bin(q)        ∈ {low, mid, high}     (3-quantile binning on calibration)
  update_pattern(q) ∈ {single-trace, multi-update, supersede-heavy}   (from Memora memory-trace metadata)
  ```
  → 9 cells. With Memora train ~ 800-1000 calibration questions (per the benchmark's published splits), each cell has ≥ N_min = 30 with room.
  Hierarchical-merging fallback: if any cell has `n_g < N_min`, merge it into the nearest neighbour along the `update_pattern` axis first (preserves the temporal-forgetting interpretation), then along PMI bin.
  KU / TR / single-session / abstention question-type axes are *reporting strata only* — we report selective risk per type but do not calibrate per type.
- **Reasoning.** Reviewer's diagnosis is correct: `abstention` as an outcome cannot be a calibration covariate (would create selection bias). Down-sized 2-D Mondrian gives statistical power per cell with the available calibration sample.
- **Impact on core method.** Mondrian simpler; statistical power per cell increased; reporting strata still allow per-question-type analysis. The temporal-forgetting axis (`update_pattern`) is preserved as a primary calibration axis, anchoring the method to the bottleneck.

### 4. Calibration uses Memora train only; controlled slice → stress diagnostic (IMPORTANT)
- **Reviewer said:** "Calibrate only on a held-out Memora split; use the Path-D controlled slice only as a diagnostic stress set."
- **Action.** Calibration set is now strictly Memora train (no mixing with the project-internal controlled slice). The controlled slice (250q across 2 strata, built in Path D) becomes a stress diagnostic: we report selective risk on the controlled slice as an out-of-distribution test, demonstrating either (a) the guarantee transfers, or (b) the calibration distribution is materially different from the controlled slice and the gap quantifies covariate shift.
- **Reasoning.** Avoids covariate-shift confounding in the calibration; makes the headline guarantee cleanly tied to one distribution (Memora).
- **Impact on core method.** Calibration is statistically clean. Controlled slice still informs the paper but as a transfer-risk diagnostic, not a guarantee source.

### 5. Add answer-rate floor + matched-abstention comparison (IMPORTANT)
- **Reviewer said:** "Define an explicit minimum answer-rate or matched-abstention comparison... guard against the trivial 'abstain more to look safe' objection."
- **Action.** Two complementary reporting modes:
  - *Headline (selective risk + answer rate).* For each α ∈ {0.05, 0.10, 0.15, 0.20, 0.25}, report calibrated TTMG-β's selective risk and answer rate per group + aggregated. The answer rate is part of the headline — not an afterthought.
  - *Matched-abstention comparison.* For each baseline, post-hoc tune a confidence threshold on its own scores (e.g. Mem0's own confidence or A-Mem's link-strength) so that its answer rate matches TTMG-β's at α = 0.10. Compare FAMA at matched answer rate. This eliminates the "TTMG-β just abstains more" objection.
- **Reasoning.** Standard practice for selective-classification papers. Without this, a reviewer can produce the trivial rebuttal: "answer-everything baseline + always-abstain baseline define the trivial endpoints — what's the curve?" The matched-abstention comparison shows TTMG-β strictly dominates on the answer-rate-vs-FAMA Pareto frontier, not just at one operating point.
- **Impact on core method.** No change. Adds two reporting modes and one post-hoc tuning step per baseline (cheap).

### 6. Validation surface tightened (IMPORTANT + Simplification)
- **Reviewer said:** "Memora/FAMA is the core; one parity benchmark is enough... Make `no_conformal` and `no_groups` the must-have ablations; move `no_pmi` to secondary."
- **Action.**
  - *Main text.* Memora full test (3 seeds × deepseek-v3.2 × 6 methods); risk-coverage curves; matched-abstention comparison; LongMemEval-S parity (3 seeds × 1 backbone) — one parity benchmark only.
  - *Ablations (main).* `no_conformal` (revert to MWIS abstention); `no_groups` (marginal CP only).
  - *Ablations (appendix).* `no_pmi`; `no_canonical_key`; `no_3call_agreement` (only as extreme stress checks, not headline).
  - *Appendix.* LoCoMo full; secondary backbone (Qwen3-30B-A3B) on {Flat, TTMG-β}.
  - *EverMemOS.* Cite published LoCoMo number; run on Memora only as a paired comparator (one seed; appendix).
- **Reasoning.** Tightens the empirical surface to the core thesis. Risk-coverage curves + matched-abstention comparison are the two most defensible reporting modes for a guarantee paper; everything else is supporting.
- **Impact on core method.** No change. Drops ~10 GPU-h-equivalents from the round-0 budget (~45 → ~35).

### 7. Add risk-coverage + group-conditional reliability plots (Modernization)
- **Reviewer said:** "Add risk-coverage and group-conditional reliability plots, not only coverage-at-5-α tables."
- **Action.** Two new figures:
  - *Risk-coverage curve.* x-axis = answer rate (1 − abstain rate); y-axis = selective risk. Plot TTMG-β + each baseline's matched-abstention curve. Show TTMG-β's curve dominates baselines on the answer-rate-vs-risk Pareto.
  - *Group-conditional reliability plot.* x-axis = nominal α; y-axis = empirical selective risk per group + aggregate; identity line + Wilson UCB band. Shows each group's empirical risk stays under the nominal line.
- **Reasoning.** Standard selective-classification reporting; makes the guarantee visually checkable.
- **Impact on core method.** Reporting only; no method change.

## Revised Proposal

# Conformal-Selective-Risk-Controlled Memory — A Calibrated Abstention Operator for Long-Conversation Agents under Forgetting (Pivot β v2, round 1 refinement)

## Problem Anchor

(verbatim from round 0 — see top of this document)

## Updated Success Condition (round 1, statistically correct)

1. **Selective-risk guarantee (headline).** On Memora test, for each α ∈ {0.05, 0.10, 0.15, 0.20, 0.25} and each calibration group `g`, the *empirical* selective risk `r̂_g(τ̂_g(α; δ))` is ≤ α + Wilson-UCB-slack on the test split (we expect ≤ α + 0.02), with answer rate per group reported alongside; aggregate-grid risk also ≤ α + 0.02. Theorem: with probability ≥ 1 − δ over the calibration sample, the true conditional risk per group is ≤ α.
2. **Matched-abstention FAMA win on Memora's temporal-forgetting subset.** On the temporal-forgetting subset (`update_pattern ∈ {multi-update, supersede-heavy}` ∧ time-sensitive slot type), at matched answer rate (α = 0.10), TTMG-β strictly dominates A-Mem, Mem0, LightMem, EverMemOS-on-Memora in FAMA (paired-bootstrap p<0.05 at quartile-week level).
3. **Aggregate-Memora FAMA non-regression.** On full Memora aggregate, TTMG-β's FAMA is within 5 FAMA-points of the best baseline at matched answer rate (we *do not* require strict dominance on aggregate — the temporal-forgetting subset is the headline).
4. **Parity preservation on LongMemEval-S.** TTMG-β within 2 pp of best of (Flat, A-Mem) on overall accuracy.
5. **Mechanism causality.** `no_conformal` (revert to MWIS abstention) breaks the selective-risk guarantee on Memora; `no_groups` (marginal CP only) preserves marginal but breaks per-group conditional risk on at least 2 of 9 cells.
6. **Failure clause.** Design fails if: (a) selective risk exceeds `α + 0.04` on test for ≥ 2 of 5 α values, OR (b) matched-abstention FAMA wins fail vs ≥ 3 of 4 baselines on the temporal-forgetting subset, OR (c) parity on LongMemEval-S breached by > 5 pp.

## Technical Gap

(unchanged from round 0; same survey-grounded white-space — memory subfield uses zero conformal / CRC / selective-classification / PMI / VIB. EverMemOS hard-filters by validity intervals, no guarantee. SmartSearch deterministic, no guarantee. Conformal-RAG and PMI-RAG exist in adjacent RAG subfield and are directly retargetable; we use the *correctly-stated* CRC version, not vanilla split CP.)

## Method Thesis

*For each retrieved memory subset relevant to a query, compute a hardness-weighted scalar confidence score `S(q)`; on a held-out Memora calibration split, compute per-group thresholds `τ̂_g(α; δ)` whose Wilson UCB on empirical selective risk is ≤ α with multiple-testing correction; at inference, answer iff `S(q) ≥ τ̂_g(α; δ)` and unique-value, else abstain — yielding `Pr[ wrong | answered, g ] ≤ α` with finite-sample probability ≥ 1 − δ over the calibration sample. The first memory operator with a correctly-stated selective-risk guarantee.*

- **Smallest adequate intervention.** One CRC layer (~120 lines: UCB + grid search + multiple-testing correction + answer-rate floor + hierarchical merging fallback). One PMI estimator (~20 lines, one frozen-LM call). No new training.
- **Why timely.** Field is converging on Memora + FAMA as the new natural validation. Conformal / CRC machinery is mainstream in classical ML; its absence in memory is a *structural* gap. EverMemOS at 92.3 % LoCoMo without a guarantee — the next move *has to be* guarantees.

## Contribution Focus

- **Dominant contribution.** A *selective-risk-controlled abstention rule* for memory-augmented answering with empirically validated `Pr[ wrong | answered, g ] ≤ α` selective risk at multiple α levels and finite-sample δ-coverage on Memora — the first memory operator with a correctly-stated selective-risk guarantee. Headline numbers on Memora's *temporal-forgetting subset* with matched-abstention comparison.
- **Optional supporting contribution.** PMI-bin Mondrian axis + phase-diagram diagnostic showing where the calibration earns its keep. Stays secondary in main paper; full PMI ablation moves to appendix.
- **Explicit non-contributions.** Not a LoCoMo / LongMemEval-S accuracy win (parity claimed). Not a new memory architecture (substrate reused). Not a new benchmark (Memora exists). Not a contribution about typed claim graphs, validity intervals, supersede edges, or applicability gates *in isolation* — EverMemOS already does the validity-interval part. **The selective-risk guarantee is what we own.**

## Proposed Method

### Complexity Budget
- **Frozen substrate (Path D round 0–4).** TTMG schema + canonicalizer + 3-call-agreement linker (hardness ∈ {0/3, 1/3, 2/3, 3/3}) + applicability gate + canonical-key fetch + valid_to materialisation. Engineering scaffolding, not contribution.
- **New (2 deltas).** (1) CRC layer (`ttmg/crc.py`, ~120 lines): Wilson UCB; threshold-grid search; Bonferroni multiple-testing correction; hierarchical group-merging fallback; answer-rate floor `N_min = 30`. (2) PMI estimator (`ttmg/pmi.py`, ~20 lines): one frozen-LM `/v1/completions` call per applicable query.
- **Tempting additions intentionally not used.** No linker fine-tune. No Swin-VIB. No agentic multi-round retrieval. No new MWIS solver. No reranker. No CP-other-flavour (jackknife, full CP) — split CRC suffices given Memora's calibration set size.

### Score Function `S(q)`
Pre-decision scalar score over `cand = canonical-key-fetch(q) ∩ valid_at(τ_q)`:
```
Opts   = max-weight independent sets on hard-edge subgraph over cand
Vals   = ⋃_{I ∈ Opts} { c.object_norm : c ∈ I }
S(q)   = w_h · mean( hardness(c) for c ∈ ⋃ Opts )       # typed conflict graph signal
       + w_u · 1[ |Vals| == 1 ]                          # unanimity across optima
       + w_p · clip(PMI(q, M_q) / PMI_scale, 0, 1)       # frozen-LM relevance
```
with initial `(w_h, w_u, w_p) = (0.5, 0.3, 0.2)`, all dev-tuned on a 60-q held-out split *before* CRC calibration. Calibrated thresholds `τ̂_g(α; δ)` absorb miscalibration in weights — exact weight choice is not load-bearing.

### Mondrian Group Definition (simplified)
```
g(q) := ( pmi_bin(q), update_pattern(q) )
pmi_bin(q)        ∈ {low, mid, high}     (3-quantile binning on calibration)
update_pattern(q) ∈ {single-trace, multi-update, supersede-heavy}   (from Memora memory-trace metadata)
```
9 cells. Hierarchical-merging fallback: if `n_g < N_min = 30`, merge along `update_pattern` axis first, then PMI bin.

KU / TR / single-session / abstention / slot type: *reporting strata only*, not calibration strata.

### CRC Calibration (offline, before lock)
```python
# Inputs: Calibration set Cal = {(q_i, t_i, M_i, y_i*)}_{i=1..n_cal} from Memora train.
# For each q_i, run inference to obtain (ŷ_i, S_i, g_i).

threshold_table = {}
for g in G:                                       # 9 cells
    Cal_g = [ i for i in Cal if g_i == g ]
    if len(Cal_g) < N_min:
        Cal_g = merge_hierarchical(Cal_g, axis="update_pattern")  # then "pmi_bin"
    for α in {0.05, 0.10, 0.15, 0.20, 0.25}:
        δ_corr = δ / (|G| · |A|)                 # Bonferroni
        for τ in Grid_τ:                          # 50 equispaced points
            answered = [ i for i in Cal_g if S_i >= τ ]
            if len(answered) < N_min:
                continue
            wrong = [ i for i in answered if ŷ_i != y_i* ]
            UCB = wilson_upper(len(wrong), len(answered), 1 - δ_corr)
            if UCB <= α:
                threshold_table[g, α] = τ
                break
        else:
            threshold_table[g, α] = ∞               # always-abstain fallback for this group
# Lock threshold_table; commit hash to git; print hash in paper.
```

**Theorem (paper version).**
> Under exchangeability of `Cal` with the test distribution, with probability at least `1 − δ` over the draw of `Cal`, for every group `g` and every `α ∈ A`,
> `P_test[ ŷ ≠ y* | S ≥ τ̂_g(α; δ), g(q) = g ] ≤ α`.

Proof sketch: the Wilson UCB on a binomial proportion is finite-sample valid at level `1 − δ_corr`; the smallest threshold with UCB ≤ α therefore guarantees the true conditional risk is ≤ α with probability ≥ 1 − δ_corr per (g, α) pair; Bonferroni handles the joint event over the (g, α) grid.

### Inference
```python
parser_out = parse(q, t_q)              # (claim_key_q, slot_type_q, τ_q, applicable)
if not parser_out.applicable:
    return Flat(q)
cand = SP_index.fetch_all(claim_key_q)
cand = [ c for c in cand if valid_at(c, τ_q, parser_out.asks_history) ]
if len(cand) == 0:
    cand = topK_emb(q) ∪ topK_bm25(q); ...   # FALLBACK (logged, audited)
Opts = exact_MWIS(cand, hard_edges)
Vals = { c.object_norm : c ∈ ⋃ Opts }
pmi_q = PMI(q, concat(cand))            # one frozen-LM call
S_q   = w_h * mean(hardness in ⋃Opts) + w_u * (|Vals|==1) + w_p * clip(pmi_q / PMI_scale)
g_q   = (pmi_bin(pmi_q), update_pattern(q))
α     = paper-default 0.10
if S_q >= threshold_table[g_q, α] and |Vals| == 1:
    return reader(q, any I in Opts, value=Vals.pop())
else:
    return ABSTAIN(reason="below_CRC_threshold", S_q, τ̂=threshold_table[g_q, α], g_q, pmi_q)
```

### Modern Primitive Usage
Two LLM uses on top of the Path D substrate, both already in the existing MAAS budget:
- **PMI estimator** (frozen-LM prefix probability — *no additional model*).
- **Linker** (already 3-call agreement; we reuse the hardness as the conformal score input — *no change*).
Calibration is one-shot, offline, before any test-time runs.

### Integration
Files touched: `ttmg/truth_retriever.py` (replace MWIS-abstention with CRC threshold rule); NEW `ttmg/crc.py` (~120 lines); NEW `ttmg/pmi.py` (~20 lines); NEW `scripts/calibrate_crc.py` (~150 lines, runs over Memora train, locks `threshold_table` and commits hash); minor `ttmg/system.py` additions for PMI toggle + CRC flag.
Files frozen: Path D's `schema.py`, `writer_temporal.py`, `conflict_linker.py`, `canonicalize.py`.

### Training Plan
None. Calibration is offline, one-shot. Pre-test gates *before* test-time runs:
- **Calibration coverage on dev split** (40% of Memora train held back as dev): per-group empirical selective risk under the locked threshold ≤ α + 0.02 for all 5 α, all groups.
- **PMI estimator stability**: Spearman ρ ≥ 0.5 between PMI estimate and answer-correctness on dev (relaxed from round 0's `r ≥ 0.7` since correlation is now an *input axis* not a *guarantee*).
- **Calibration-to-test exchangeability**: Kolmogorov-Smirnov p > 0.05 on the joint `(pmi_bin, update_pattern)` distribution between calibration and Memora-test split. If KS fails → use weighted conformal (importance-weighted Wilson UCB).

### Failure Modes and Diagnostics
- **C1 Calibration miscoverage on Memora test.** Detect: per-group empirical risk exceeds α + 0.04 on test for any (g, α). Mitigate: hierarchical group-merging; fall back to *aggregate-only* selective-risk guarantee if conditional fails. Report honestly.
- **C2 PMI signal collapses on memory slots.** Detect: dev Spearman ρ < 0.3. Mitigate: drop PMI from S, use `(w_h, w_u) = (0.7, 0.3)`; PMI-bin axis collapses to single bin (Mondrian becomes `{single-trace, multi-update, supersede-heavy}` — 3 cells); PMI phase diagram becomes a negative result.
- **C3 Matched-abstention FAMA win does not materialise.** Detect: bootstrap fails to show TTMG-β > 3 of 4 baselines on temporal-forgetting subset at matched answer rate. Mitigate: tighten α (sacrifice answer rate for selective risk); if still failing, reframe as "first calibration-on-memory paper, selective-risk verified, FAMA no-worse-than baselines" (smaller paper, ICLR / workshop track).
- **C4 EverMemOS not reproducible.** Detect: code in `MemMachine/competitor/2601.02163_EverMemOS/code/` fails install or doesn't reproduce LoCoMo within 5 pp. Mitigate: cite published numbers; pair-compare on Memora only.
- **C5 Calibration / test distribution shift.** Detect: KS p ≤ 0.05 on `(pmi_bin, update_pattern)`. Mitigate: weighted conformal (likelihood ratios estimated from calibration vs test PMI distribution).
- **C6 Group cell underpopulated.** Detect: `n_g < N_min` after hierarchical merging. Mitigate: collapse `pmi_bin` from 3 → 2 quantiles; if still failing, marginal-only guarantee.
- **C7 Trivial "abstain more to look safer" objection.** Mitigated *by design* with the matched-abstention reporting mode; we report risk-coverage curves so any reviewer can verify TTMG-β dominates baselines on the answer-rate-vs-FAMA Pareto, not just at one α.

### Novelty and Elegance Argument
- **Closest work.** Conformal-RAG (SIGIR 2025) — split CP on RAG sub-claim factuality with cosine-similarity scores; PMI-RAG — PMI as frozen-LM correctness gauge; EverMemOS (Jan 2026) — structured memory with foresight intervals + 92.3% LoCoMo; SmartSearch (Feb 2026) — deterministic retrieval + 91.9% LoCoMo. Selective-classification literature: Geifman & El-Yaniv 2017; CRC: Angelopoulos et al. 2022; Bates et al. 2021.
- **Exact difference.**
  - Vs Conformal-RAG: it controls *prediction-set inclusion* on RAG sub-claim factuality with cosine-similarity scores; we control *conditional-on-answer selective risk* with a *typed-conflict-graph hardness* score over a memory subgraph at time τ_q. Different statistical object, different score function, different application domain.
  - Vs EverMemOS: hard-filters by foresight intervals (no guarantee). We give a *finite-sample selective-risk guarantee* with explicit answer-rate trade-off. Calibrated dynamically per-group.
  - Vs SmartSearch: deterministic ranker (no guarantee, no group-conditional behaviour). Our coverage holds at the test distribution under exchangeability with finite-sample δ-confidence.
  - Vs PMI-RAG: PMI selects *context permutations*; we use PMI as one of three score axes + as a Mondrian calibration covariate + as a phase-diagram diagnostic.
  - Vs generic CRC / selective-classification: those operate on i.i.d. classification with a single confidence score; we operate on *agent memory at time τ* with a typed conflict graph as the score's substrate, and *Memora memory traces* as the calibration ground truth (which exist nowhere else in the memory subfield). The temporal-forgetting subset is the empirical centre.
- **Why mechanism-level (statistical), not architectural pile-up.** One CRC layer + one PMI estimator + a calibration script. The contribution is the *guarantee*, not the architecture. The paper's result is summarisable in one inequality — the theorem above. The temporal-forgetting subset is the locus where the gap to baselines concentrates, anchoring the work to truth-maintenance-under-forgetting rather than generic selective QA.

## Claim-Driven Validation Sketch

### Claim 1 (Dominant) — Selective-risk guarantee + matched-abstention FAMA win on Memora's temporal-forgetting subset
- **Statement.** On Memora test, for each α ∈ {0.05, 0.10, 0.15, 0.20, 0.25} and each calibration group g ∈ G, empirical selective risk `r̂_g(τ̂_g(α; δ))` ≤ α + 0.02. On the temporal-forgetting subset (`update_pattern ∈ {multi-update, supersede-heavy}` ∧ time-sensitive slot type), at matched answer rate (α = 0.10), TTMG-β strictly dominates A-Mem, Mem0, LightMem, EverMemOS-on-Memora in FAMA (paired-bootstrap p<0.05 at quartile-week level).
- **Minimal experiment.** 5 methods × 3 seeds × deepseek-v3.2 × Memora full test. Calibration on Memora train (60%); dev = 40% of train.
- **Baselines / ablations.** Flat hybrid-RAG; A-Mem reimpl; Mem0 reimpl; LightMem (or its published numbers); EverMemOS (best-effort reproduction from `MemMachine/competitor/.../code` — appendix); TTMG-β full; ablations: `no_conformal` (revert to Path D's MWIS abstention), `no_groups` (marginal CP only — calibration without Mondrian).
- **Metric.** Per-group + aggregate selective risk @ each α; risk-coverage curves; matched-abstention FAMA on temporal-forgetting subset; cluster-bootstrap CIs over (persona × duration).
- **Expected evidence.** Selective-risk guarantee holds for all (g, α) on Memora test. FAMA on temporal-forgetting subset: TTMG-β > each baseline by ≥ 5 FAMA-points at matched answer rate. `no_conformal` breaks the selective-risk guarantee. `no_groups` produces aggregate-OK but per-group violations on ≥ 2 of 9 cells. Risk-coverage curve: TTMG-β Pareto-dominates baselines.

### Claim 2 (Supporting) — Parity preserved on LongMemEval-S; PMI phase diagram delineates calibration's regime
- **Statement.** On LongMemEval-S (N=500, 3 seeds, deepseek-v3.2), TTMG-β within 2 pp of best of (Flat, A-Mem) on overall accuracy. PMI phase diagram on Memora dev: the gap (TTMG-β FAMA − best-baseline-at-matched-abstention FAMA) increases monotonically with PMI bin index, largest gap in high-PMI bin.
- **Minimal experiment.** 3 methods × 3 seeds × 1 backbone × LongMemEval-S N=500. Plus PMI-bin breakdown of Claim-1 Memora results.
- **Baselines.** Flat; A-Mem; TTMG-β.
- **Metric.** Per-category accuracy; paired McNemar (we expect *not significant*, i.e. parity); PMI-bin FAMA gap with bootstrap CIs.
- **Expected evidence.** Parity (within 2 pp). Monotone increasing FAMA gap with PMI bin; largest gap in high-PMI bin. *We do not claim a LongMemEval-S win.*

(MAX_PRIMARY_CLAIMS = 2 honored.)

## Experiment Handoff Inputs

- **Must-prove claims.** (1) per-group selective-risk guarantee at 5 α values + matched-abstention FAMA win on Memora's temporal-forgetting subset; (2) parity on LongMemEval-S + PMI phase diagram.
- **Must-run ablations.** `no_conformal`, `no_groups` (main text); `no_pmi`, `no_canonical_key`, `no_3call_agreement` (appendix).
- **Critical datasets / metrics.** Memora train (calibration; 60% / dev 40%) + Memora test (evaluation); LongMemEval-S full N=500 (parity); LoCoMo (appendix); per-group empirical selective risk + Wilson UCB; risk-coverage curves; matched-abstention FAMA; key-fetch-fallback rate. EverMemOS on Memora only (appendix).
- **Highest-risk assumptions.** (i) Memora's `update_pattern` metadata is reliable and granular enough to define `single-trace / multi-update / supersede-heavy`. (ii) `Edge.hardness` from the 3-call linker is calibrated enough to be a useful CRC score input. (iii) PMI on memory-slot context behaves comparably to RAG-document context. (iv) Memora calibration / test split exchangeable enough that CRC coverage holds (KS-tested before lock). (v) EverMemOS reproduces within 5 pp on its own benchmarks from `competitor/.../code`.

## Compute & Timeline Estimate

- **Compute.** ≈ **35 GPU-h-equivalents** on 1–2× RTX-4090 (down from round 0's 45; main-text empirics are tighter).
- **Data / annotation cost.** Use Memora-supplied memory-trace ground truth.
- **Timeline.**
  - **Wk 1.** Pull Memora train/test data; integrate CRC layer (`crc.py` ~120 lines) and PMI estimator (`pmi.py` ~20 lines); tune `(w_h, w_u, w_p)` on 60-q held-out dev; run all calibration-stage intrinsic gates (per-group dev coverage, PMI Spearman ρ ≥ 0.5, KS-test exchangeability); lock `threshold_table` + commit hash.
  - **Wk 2.** Full Memora test runs for 5 methods × 3 seeds; LongMemEval-S parity runs (3 methods × 3 seeds); reproduce EverMemOS from `competitor/.../code` (appendix).
  - **Wk 3.** Ablations on Memora (`no_conformal`, `no_groups` main; `no_pmi`, `no_canonical_key`, `no_3call_agreement` appendix); risk-coverage curves; matched-abstention comparison; PMI phase diagram; cluster-bootstrap CIs over (persona × duration).
  - **Wk 4.** Paper rewrite (round-1 framing: *the first selective-risk-controlled abstention rule for memory*, with the temporal-forgetting subset as the empirical centre); figures (per-group reliability plot at 5 α with Wilson UCB band, risk-coverage curve with matched-abstention baselines, FAMA bars on temporal-forgetting subset with cluster-bootstrap CIs, ablation drop bars, PMI phase diagram); reconcile prior `STATUS.md`; cite EverMemOS, SmartSearch, Diagnosing-Memory, Memora, Conformal-RAG, PMI-RAG, CRC, Selective-Classification.

(End of round-1 refinement.)
