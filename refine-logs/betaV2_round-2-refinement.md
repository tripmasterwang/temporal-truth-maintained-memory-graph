# Round 2 Refinement — Pivot β v2

## Problem Anchor (verbatim from round 0)

(unchanged — see round-0-initial-proposal.md)

## Anchor Check

- **Original bottleneck.** Truth maintenance under forgetting + abstention quality on contradictions, with a *guarantee*.
- **Why the revised method still addresses it.** Round-2 changes (i) tighten the theorem to match the procedure exactly (no more overclaim), (ii) re-define the `update_pattern` axis from inference-time graph features (no Memora-metadata dependence), and (iii) lock the 3-way split hygiene. The bottleneck is unchanged; the operator now offers a guarantee that matches what is actually proved.
- **Reviewer suggestions rejected as drift.** None. Drift = NONE confirmed in rounds 1 and 2.

## Simplicity Check

- **Dominant contribution after revision.** Selective-risk-controlled abstention rule for memory-augmented answering. Theorem: *exact* finite-sample selective-risk control via Clopper-Pearson UCB on a single fixed threshold per (g, α), where candidate thresholds are pre-frozen on a dev split. Mondrian groups defined from inference-time graph features. Headline empirics on Memora's temporal-forgetting subset with a full risk-coverage curve as the primary baseline comparison.
- **Components removed or merged.**
  - **Adaptive 50-point grid search dropped from the calibration phase.** Candidate thresholds are pre-frozen on dev (typically 5 candidates per group: 5 fixed quantiles of dev S-distribution). Calibration evaluates exactly one chosen threshold per (g, α) using exact Clopper-Pearson inversion.
  - **Wilson UCB → Clopper-Pearson exact** (cite Clopper & Pearson 1934). No more "approximate UCB" hand-wave.
  - **`update_pattern` axis re-grounded.** Now defined from inference-time graph features `(n_supersede_edges, n_active_values, n_temporal_updates)`; bin boundaries fixed on dev. Memora metadata used only to *validate the proxy* on dev (Spearman ρ ≥ 0.6), not to define the method.
  - **Strict 3-way split**: dev (score design + binning + threshold candidates) / calibration (single-threshold UCB only) / test (one shot, no tuning).
  - **Risk-coverage curve becomes the primary baseline comparison** (matched-rate point becomes a marker on the curve, not the headline).
  - **Weighted-conformal fallback** removed from the main proposal; mentioned only as future work.
- **Reviewer suggestions rejected as unnecessary complexity.** None. Each round-2 critique either fixes the theorem-procedure mismatch, re-grounds the group definition, or hardens split hygiene.
- **Why the remaining mechanism is still the smallest adequate route.** CRC layer still ~120 lines (Clopper-Pearson is a 5-line function). Pre-freezing thresholds is *simpler* than adaptive grid search. Inference-time `update_pattern` reuses the existing canonical-key-fetched conflict graph. PMI estimator still ~20 lines.

## Changes Made

### 1. Pre-frozen threshold protocol + Clopper-Pearson exact UCB (CRITICAL — theorem ↔ procedure alignment)
- **Reviewer said:** "Wilson UCB is approximate; doesn't justify a strict finite-sample `1−δ` theorem. Adaptive search over a 50-point grid needs correction over `|G|·|A|·|T|`. Fix: freeze candidate thresholds on dev, evaluate only one fixed threshold per (g, α) on calibration. Or replace Wilson with Clopper-Pearson exact + correction over |G|·|A|·|T|."
- **Action.** Take the clean path:
  ```
  PHASE 1 (dev — score design + binning + threshold candidates):
    - Tune (w_h, w_u, w_p) by minimising calibration sample size needed to reach α=0.10 on dev.
    - Fix PMI_scale, pmi_bin boundaries, update_pattern bin boundaries.
    - For each group g, define a small candidate-threshold set:
        T_cand(g) = { 5 quantiles of {S_i : g_i = g, i ∈ Dev} }   (e.g. 50%, 60%, 70%, 80%, 90%)
    These are FIXED before any calibration is touched.

  PHASE 2 (calibration — single-threshold UCB only):
    For each (g, α) ∈ G × A:
        For each τ ∈ T_cand(g) (in ascending order):
            n_g(τ) = #{ i ∈ Cal : g_i = g, S_i ≥ τ }
            w_g(τ) = #{ i ∈ Cal : g_i = g, S_i ≥ τ, ŷ_i ≠ y_i* }
            UCB_CP(w_g, n_g, 1 − δ_corr) =
                inverse one-sided Clopper-Pearson upper bound at level 1 − δ_corr,
                where δ_corr = δ / (|G| · |A| · |T_cand(g)|)
            if UCB_CP ≤ α and n_g ≥ N_min = 30:
                τ̂_g(α; δ) = τ
                break
        else:
            τ̂_g(α; δ) = ∞   # always-abstain fallback
    Lock threshold_table; commit hash to git.
  ```
  Now the theorem is exact:
  > **Theorem (selective risk control, exact).** Under exchangeability of `Cal` with the test distribution, with probability at least `1 − δ` over the draw of `Cal`, for every group `g` and every `α ∈ A`,
  > `P_test[ ŷ ≠ y* | S ≥ τ̂_g(α; δ), g(q) = g ] ≤ α`.
  > *Proof.* For any fixed (g, α, τ), Clopper-Pearson inversion gives `Pr[ true selective risk > UCB_CP ] ≤ δ_corr` (exact, finite-sample). Bonferroni over the joint event of (g, α, τ) selections gives `δ_corr = δ / (|G| · |A| · |T_cand(g)|)`. Since the τ chosen per (g, α) is the smallest candidate satisfying `UCB_CP ≤ α`, the conditional risk at that τ is ≤ α with probability ≥ 1 − δ_corr per (g, α, τ); union bound over all (g, α, τ) gives ≥ 1 − δ.
- **Citations.** Clopper & Pearson 1934 (exact binomial CI); Angelopoulos et al. 2022 (Conformal Risk Control); Geifman & El-Yaniv 2017 (Selective Classification); Bates et al. 2021 (Distribution-free Risk-Controlling Prediction Sets).
- **Reasoning.** Reviewer is right that the exact theorem requires either (a) exact bound + correction over the full search grid, or (b) a fixed (small) candidate set. (b) is cleaner, requires less calibration sample, and the candidate-set quantiles are dev-independent of the calibration set so no leakage.
- **Impact on core method.** Theorem is now provably correct. Calibration is simpler and uses fewer samples. The `δ_corr = δ / (|G| · |A| · |T_cand|)` correction is small (≤ 9 × 5 × 5 = 225) so the Clopper-Pearson at `δ_corr ≈ 4 × 10⁻⁴` is still meaningful with `n_g(τ) ≈ 30-100`.

### 2. `update_pattern` re-grounded as inference-time graph feature (IMPORTANT)
- **Reviewer said:** "`update_pattern` must be computable at inference from the memory graph, not from Memora-only metadata. Define it from observable graph features, e.g. number of temporal updates for the claim key, supersede-edge count, conflict degree, active-value multiplicity. Memora metadata can validate the proxy, but should not define the method."
- **Action.** Re-define:
  ```
  At inference, given query q with canonical-key K = claim_key_q and time τ_q:
      slot_history(K, τ_q) = { all claims c with c.claim_key == K, c.created_at ≤ τ_q }
      n_supersede_edges(K, τ_q)   = # supersede edges in slot_history with hardness ≥ 2/3
      n_active_values(K, τ_q)     = |{ c.object_norm : c ∈ slot_history, valid_at(c, τ_q) }|
      n_temporal_updates(K, τ_q)  = |{ distinct values c.object_norm assigned at distinct timestamps in slot_history }|
      conflict_degree(K, τ_q)     = # contradict edges in slot_history with hardness ≥ 2/3

  update_pattern(q) :=
      "single-trace"     if n_temporal_updates ≤ 1 AND n_supersede_edges == 0
      "multi-update"     if n_temporal_updates ≥ 2 AND n_supersede_edges ≤ 1
      "supersede-heavy"  if n_supersede_edges ≥ 2 OR (n_active_values ≥ 2 AND conflict_degree ≥ 1)
  ```
  Memora's memory-trace metadata is used *only* to validate the proxy on dev: target Spearman ρ ≥ 0.6 between the inference-time `update_pattern` label and the Memora-derived ground-truth update count. If the proxy fails the validation, refine bin boundaries on dev (not on calibration).
- **Reasoning.** Reviewer correctly noted this looked benchmark-dependent. The fix makes the method deployable on any memory system that maintains a typed claim graph (which is exactly what the Path D substrate provides). Memora becomes the *measurement instrument*, not a method dependency.
- **Impact on core method.** Mechanism is now benchmark-independent. The Mondrian axis is grounded in graph observables.

### 3. Strict 3-way split hygiene (IMPORTANT)
- **Reviewer said:** "Weight tuning, `PMI_scale`, bin boundaries, and merge rules must be fixed before threshold calibration. State a strict 3-way protocol."
- **Action.** Document the locked protocol in the proposal + paper:
  ```
  Memora train (60 % of train) → DEV
      tune (w_h, w_u, w_p)
      fix PMI_scale
      fix pmi_bin boundaries (3-quantile of S(q) on dev)
      fix update_pattern bin boundaries
      validate update_pattern proxy: Spearman ρ ≥ 0.6 vs Memora ground truth
      define candidate threshold sets T_cand(g) (5 quantiles per cell)
      tune baseline thresholds (for matched-abstention comparison)

  Memora train (40 % of train) → CALIBRATION
      run inference for all calibration samples
      evaluate ONE pre-frozen threshold per (g, α, τ) using Clopper-Pearson UCB
      lock threshold_table; commit hash to git; print hash in paper
      no further tuning past this point

  Memora test (held out) → TEST
      one shot; no tuning; report per-group + aggregate selective risk + risk-coverage curves
  ```
- **Reasoning.** Standard practice for selective-classification papers; absence in round 1 was a hole. Locking before calibration eliminates the post-hoc-tuning objection.
- **Impact on core method.** No method change. Add a "Split protocol" subsection to the paper.

### 4. Risk-coverage curve = primary baseline comparison (IMPORTANT)
- **Reviewer said:** "Matched-answer-rate baseline comparison should avoid looking post-hoc. Either choose baseline thresholds on dev, or make the full risk-coverage curve the primary comparison and the matched-rate point secondary."
- **Action.** Take *both* fixes:
  - Baseline thresholds for matched-abstention reporting are tuned on **dev** (locked before test).
  - **Risk-coverage curve** (x-axis = answer rate; y-axis = selective risk; one curve per method; TTMG-β + each baseline by sweeping each method's own confidence threshold) becomes the **primary** Claim-1 figure. The matched-rate point is a *marker* on the curve, not the headline.
- **Reasoning.** Pre-tuning baseline thresholds on dev removes the post-hoc objection; making the full curve primary removes the "single-point cherry-pick" objection. Standard for selective-classification.
- **Impact on core method.** No method change. Reporting protocol upgrade.

### 5. Weighted-conformal moved to future work; per-cell counts reported (MINOR)
- **Reviewer said:** "Weighted-conformal fallback is probably too much for the main paper unless you actually implement it. Report per-cell counts and abstention mass."
- **Action.** Drop weighted-conformal from main; mention only in §discussion as future work. Add to Claim-1 results: a small auxiliary table of `(g, n_g, abstain_mass_g)` so reviewers can verify the 9 cells are populated.
- **Reasoning.** Trimming hypothetical machinery; transparency on cell populations.
- **Impact on core method.** None.

## Revised Proposal

# Conformal-Selective-Risk-Controlled Memory — A Calibrated Abstention Operator for Long-Conversation Agents under Forgetting (Pivot β v2, round 2 refinement)

## Problem Anchor

(verbatim from round 0)

## Updated Success Condition (round 2 — theorem now exact)

1. **Selective-risk guarantee (headline, exact).** On Memora test, for each α ∈ {0.05, 0.10, 0.15, 0.20, 0.25} and each calibration group g ∈ G, empirical selective risk `r̂_g(τ̂_g(α; δ))` ≤ α + 0.02. Theorem: with probability ≥ 1 − δ over the draw of Cal, true conditional risk per group ≤ α (exact via Clopper-Pearson + Bonferroni over `|G|·|A|·|T_cand|`).
2. **Risk-coverage Pareto-dominance on Memora's temporal-forgetting subset.** TTMG-β's risk-coverage curve dominates all baselines (A-Mem, Mem0, LightMem, EverMemOS-on-Memora) at every answer rate ∈ [0.4, 0.9] on the temporal-forgetting subset (`update_pattern ∈ {multi-update, supersede-heavy}`). Matched-rate point at α = 0.10 also dominates (paired-bootstrap p<0.05 at quartile-week level), but the curve is the headline.
3. **Aggregate-Memora FAMA non-regression.** TTMG-β within 5 FAMA-points of best baseline at matched answer rate on full Memora aggregate.
4. **Parity preservation on LongMemEval-S.** TTMG-β within 2 pp of best of (Flat, A-Mem) on overall accuracy.
5. **Mechanism causality.** `no_conformal` breaks the selective-risk guarantee; `no_groups` preserves marginal but breaks per-group on ≥ 2 of 9 cells.
6. **`update_pattern` proxy validation.** Spearman ρ ≥ 0.6 between inference-time `update_pattern` label and Memora ground-truth update count, on dev.
7. **Failure clause.** Design fails if (a) selective risk exceeds α + 0.04 on test for ≥ 2 of 5 α, OR (b) risk-coverage Pareto-dominance fails on temporal-forgetting subset, OR (c) parity on LongMemEval-S breached > 5 pp, OR (d) `update_pattern` proxy validation fails (ρ < 0.4).

## Method Thesis (round 2, final)

*For each retrieved memory subset relevant to a query, compute a hardness-weighted scalar confidence score `S(q)`; on a dev split fix candidate-threshold sets per inference-time-defined group; on a calibration split, evaluate one pre-frozen threshold per (g, α) using Clopper-Pearson exact UCB with Bonferroni correction; at inference, answer iff `S(q) ≥ τ̂_g(α; δ)` and unique-value, else abstain — yielding **exact finite-sample** `Pr[ wrong | answered, g ] ≤ α` with probability ≥ 1 − δ.*

## Contribution Focus

(unchanged; see round-1 refinement.)

## Proposed Method

### Complexity Budget

- **Frozen substrate.** Path D rounds 0–4 (TTMG schema + canonicalizer + 3-call linker + applicability gate + canonical-key fetch + valid_to materialisation).
- **New (2 deltas).**
  1. CRC layer (`ttmg/crc.py`, ~120 lines): pre-frozen candidate thresholds + Clopper-Pearson UCB + Bonferroni correction + answer-rate floor + hierarchical group-merging fallback.
  2. PMI estimator (`ttmg/pmi.py`, ~20 lines): one frozen-LM call per applicable query.
- **Tempting additions intentionally not used.** No adaptive grid search (replaced by pre-frozen candidate thresholds); no Wilson UCB (replaced by Clopper-Pearson); no weighted conformal (future work); no linker fine-tune; no Swin-VIB; no agentic multi-round retrieval; no new MWIS solver; no reranker.

### Score Function `S(q)`

```
Opts = max-weight independent sets on hard-edge subgraph over canonical-key-fetch(q) ∩ valid_at(τ_q)
Vals = ⋃_{I ∈ Opts} { c.object_norm : c ∈ I }
S(q) = w_h · mean( hardness(c) for c ∈ ⋃ Opts )
     + w_u · 1[ |Vals| == 1 ]
     + w_p · clip( PMI(q, M_q) / PMI_scale, 0, 1 )
```
`(w_h, w_u, w_p, PMI_scale)` tuned on dev; locked before calibration.

### Mondrian Group (inference-time-computable)

```
At inference, for query q with canonical-key K and time τ_q, compute graph features:
    slot_history(K, τ_q)        = { c : c.claim_key == K, c.created_at ≤ τ_q }
    n_supersede_edges(K, τ_q)   = # supersede edges with hardness ≥ 2/3
    n_active_values(K, τ_q)     = | { c.object_norm : c ∈ slot_history, valid_at(c, τ_q) } |
    n_temporal_updates(K, τ_q)  = # distinct values across distinct timestamps in slot_history
    conflict_degree(K, τ_q)     = # contradict edges with hardness ≥ 2/3

update_pattern(q) :=
    "single-trace"     if n_temporal_updates ≤ 1 AND n_supersede_edges == 0
    "multi-update"     if n_temporal_updates ≥ 2 AND n_supersede_edges ≤ 1
    "supersede-heavy"  if n_supersede_edges ≥ 2 OR (n_active_values ≥ 2 AND conflict_degree ≥ 1)

g(q) := ( pmi_bin(q), update_pattern(q) )
```
9 cells. Hierarchical-merge fallback if `n_g < N_min = 30`. Memora metadata used only to validate the proxy (Spearman ρ ≥ 0.6).

### Strict 3-Way Split Protocol

```
Memora train (60 %) → DEV  ── score design, binning, candidate thresholds, baseline thresholds
Memora train (40 %) → CALIBRATION ── single-threshold Clopper-Pearson UCB; lock threshold_table
Memora test          → TEST  ── one shot; no tuning
```

### CRC Calibration (offline, before lock)

```python
# Phase 1 (dev): tune (w_h, w_u, w_p, PMI_scale); fix bin boundaries; define T_cand(g) = 5 quantiles per cell
# Phase 2 (calibration):
threshold_table = {}
for g in G:
    Cal_g = [ i in Cal : g_i == g ]
    if len(Cal_g) < N_min: Cal_g = merge_hierarchical(Cal_g, axis="update_pattern")
    for α in A:
        δ_corr = δ / (|G| · |A| · |T_cand(g)|)        # Bonferroni
        for τ in sorted(T_cand(g), ascending):
            answered = [i in Cal_g : S_i ≥ τ]
            if len(answered) < N_min: continue
            wrong = [i in answered : ŷ_i ≠ y_i*]
            UCB = clopper_pearson_upper(len(wrong), len(answered), 1 − δ_corr)
            if UCB ≤ α:
                threshold_table[g, α] = τ
                break
        else:
            threshold_table[g, α] = ∞                 # always-abstain
# Lock threshold_table; commit hash; print hash in paper.
```

**Theorem (exact, finite-sample).** Under exchangeability of `Cal` with the test distribution, with probability at least `1 − δ` over the draw of `Cal`, for every `g ∈ G` and every `α ∈ A`,
`P_test[ ŷ ≠ y* | S ≥ τ̂_g(α; δ), g(q) = g ] ≤ α.`

*Proof.* For any fixed `(g, α, τ)`, Clopper-Pearson inversion of the binomial gives `Pr[ true selective risk > UCB_CP ] ≤ δ_corr` (exact, finite-sample, distribution-free). Bonferroni over the joint event `{(g, α, τ) : g ∈ G, α ∈ A, τ ∈ T_cand(g)}` gives `δ_corr = δ / (|G| · |A| · |T_cand(g)|)`. The chosen `τ̂_g(α; δ)` is the smallest candidate satisfying `UCB_CP ≤ α`; the conditional risk at that τ is ≤ α with probability ≥ 1 − δ_corr per (g, α). Union bound over all (g, α) gives ≥ 1 − δ. ∎

### Inference

(unchanged from round 1; see round-1 refinement.)

### Modern Primitives

- PMI estimator (frozen-LM, no additional model).
- Linker (3-call agreement, hardness reused as score input).
- Calibration one-shot, offline.

### Integration

Files touched: `ttmg/truth_retriever.py`; NEW `ttmg/crc.py` ~120; NEW `ttmg/pmi.py` ~20; NEW `scripts/calibrate_crc.py` ~150; minor `ttmg/system.py`. Frozen: Path D `schema.py`, `writer_temporal.py`, `conflict_linker.py`, `canonicalize.py`.

### Pre-test Gates

- Per-group dev coverage ≤ α + 0.02 for all 5 α.
- PMI Spearman ρ ≥ 0.5 on dev.
- `update_pattern` proxy ρ ≥ 0.6 vs Memora ground truth on dev.
- KS-test calibration vs test on `(pmi_bin, update_pattern)` p > 0.05.

### Failure Modes

(C1–C7 from round 1 unchanged. New: C8 `update_pattern` proxy fails validation → re-tune bin boundaries on dev; if still failing, drop the axis and use marginal-only.)

### Novelty

(unchanged from round 1.)

## Claim-Driven Validation Sketch

### Claim 1 (Dominant) — Selective-risk guarantee + risk-coverage Pareto-dominance on temporal-forgetting subset

- **Statement.** On Memora test, per-group + aggregate selective risk ≤ α + 0.02 for all 5 α (theorem-backed). On the temporal-forgetting subset, TTMG-β's risk-coverage curve Pareto-dominates A-Mem, Mem0, LightMem, EverMemOS-on-Memora at every answer rate ∈ [0.4, 0.9]. Matched-rate point at α = 0.10 dominates with paired-bootstrap p<0.05.
- **Minimal experiment.** 5 methods × 3 seeds × deepseek-v3.2 × Memora full test. Cal on Memora train (60 % dev / 40 % calibration).
- **Baselines / ablations.** Flat; A-Mem reimpl; Mem0 reimpl; LightMem; EverMemOS (appendix); TTMG-β full; ablations: `no_conformal`, `no_groups` (main text).
- **Metric.** Per-group + aggregate selective risk + Wilson UCB band; risk-coverage curve; matched-rate FAMA on temporal-forgetting subset; cluster-bootstrap CIs over (persona × duration); per-cell `(n_g, abstain_mass_g)` table.
- **Expected evidence.** Guarantee holds for all (g, α). Risk-coverage curve: TTMG-β Pareto-dominates baselines on temporal-forgetting subset. `no_conformal` breaks guarantee. `no_groups` aggregate-OK but per-group violations on ≥ 2 of 9 cells. Per-cell n_g ≥ 30 after merging.

### Claim 2 (Supporting) — Parity + PMI phase diagram + `update_pattern` proxy validation

- **Statement.** TTMG-β within 2 pp of best of (Flat, A-Mem) on LongMemEval-S overall (3 seeds). PMI phase diagram on Memora dev: gap (TTMG-β FAMA − best baseline FAMA) increases monotonically with PMI bin index. `update_pattern` proxy Spearman ρ ≥ 0.6 vs Memora ground truth on dev.
- **Minimal experiment.** 3 methods × 3 seeds × 1 backbone × LongMemEval-S N=500 (parity). Plus PMI-bin breakdown of Claim-1 results. Plus `update_pattern` proxy validation on dev.
- **Expected evidence.** Parity (within 2 pp). Monotone increasing FAMA gap with PMI bin. Proxy ρ ≥ 0.6.

(MAX_PRIMARY_CLAIMS = 2 honored.)

## Experiment Handoff Inputs

(unchanged from round 1, with the addition of: `update_pattern` proxy validation on dev as a pre-test gate.)

## Compute & Timeline Estimate

- **Compute.** ≈ **35 GPU-h-equivalents** on 1–2× RTX-4090 (unchanged from round 1).
- **Timeline.**
  - **Wk 1.** Pull Memora; integrate CRC + PMI; tune `(w_h, w_u, w_p, PMI_scale)` and bin boundaries on dev; validate `update_pattern` proxy (Spearman ρ ≥ 0.6); define `T_cand(g)`; tune baseline thresholds on dev; all intrinsic gates clear; lock `threshold_table` + commit hash.
  - **Wk 2.** Full Memora test (5 methods × 3 seeds); LongMemEval-S parity (3 methods × 3 seeds); EverMemOS reproduction (appendix).
  - **Wk 3.** Ablations (`no_conformal`, `no_groups` main; `no_pmi`, `no_canonical_key`, `no_3call_agreement` appendix); risk-coverage curves; matched-rate markers; PMI phase diagram; cluster-bootstrap CIs; per-cell counts table.
  - **Wk 4.** Paper rewrite (round-2 framing: *exact* selective-risk control with theorem-procedure alignment); figures (per-group reliability plot at 5 α with Clopper-Pearson UCB band, risk-coverage curves, FAMA bars on temporal-forgetting with bootstrap CIs, ablation drops, PMI phase diagram, `update_pattern` proxy scatter); cite EverMemOS, SmartSearch, Diagnosing-Memory, Memora, Conformal-RAG, PMI-RAG, CRC, Selective-Classification, Clopper-Pearson.

(End of round-2 refinement.)
