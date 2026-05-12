# Review Summary — Pivot β v2

**Problem.** When an LLM agent answers from accumulated long-conversation memory, two failures recur and no current method handles either with a guarantee: (1) silent reliance on obsolete memory (FAMA shows 18-30 pp drop, gap *grows* with timeline), (2) over-confident answering on contradictions. EverMemOS (Jan 2026, 92.3% LoCoMo) already does validity intervals; SmartSearch (Feb 2026, 91.9%) does deterministic retrieval — the structural-memory race on LoCoMo is over. The keyword-scan-confirmed structural white-space is *statistical / information-theoretic*: zero memory papers use conformal, calibration, MI, PAC, sequential testing, Lagrangian, or bandit methods.

**Initial Approach (Pivot β).** Bring conformal coverage + PMI as a frozen-LM gauge into agent memory, validated end-to-end on the new Memora + FAMA benchmark where no memory system has reported scores yet. Reuse Path D's TTMG schema + canonicalizer + 3-call linker + applicability gate as engineering substrate.

**Date.** 2026-04-26
**Rounds.** 3 / 5
**Final Score.** **9.15 / 10**
**Final Verdict.** **READY**

## Problem Anchor (verbatim across all 3 rounds)

- **Bottom-line problem.** When an LLM agent answers from accumulated long-conversation memory, two failures recur and no current method handles either with a guarantee: silent reliance on obsolete memory; over-confident answering on contradictions.
- **Must-solve bottleneck.** A *calibrated* read-time decision rule that gives an explicit, verifiable risk guarantee on the answer/abstain choice, validated end-to-end by FAMA.
- **Non-goals.** Not chasing LoCoMo SOTA; not token-eff; not new benchmark; not write-time consolidation; not Path-A slot-in.
- **Constraints.** 1-2 RTX-4090; MAAS API; reuse `ttmg/{schema, writer_temporal, conflict_linker, truth_retriever, system}.py`; 3-4 weeks; NeurIPS / ICML main.

## Round-by-Round Resolution Log

| Round | Main Reviewer Concerns | What This Round Simplified / Modernized | Solved? | Remaining Risk |
|-------|------------------------|------------------------------------------|---------|----------------|
| 1 | Theorem overclaimed: vanilla split-CP doesn't give `Pr[wrong | answered, g] ≤ α`. Mondrian too fine; `abstention` as group axis is invalid (it's an outcome). Validation surface bloated; risks "abstain more to look safe" objection. Reviewers will dismiss as "generic conformal pasted on existing memory" unless temporal-forgetting story is central. | Recast as **selective risk control / CRC** with Wilson UCB; lead with **temporal-forgetting subset** of Memora; **simplify Mondrian** to `(pmi_bin, update_pattern)`; calibrate only on Memora train (controlled slice → diagnostic only); **matched-abstention comparison** + answer rate as headline; trim main-text validation (Memora + LongMemEval-S parity only); add **risk-coverage** + **reliability** plots. | Yes — guarantee correctly stated as selective risk; temporal-forgetting subset is the headline. | Theorem-procedure alignment: Wilson is approximate; adaptive grid needs threshold-level Bonferroni. `update_pattern` still benchmark-dependent. |
| 2 | Theorem still overreaches: Wilson is approximate; adaptive 50-point search needs correction over `|G|·|A|·|T|`, not just `|G|·|A|`. `update_pattern` benchmark-dependent. Split hygiene not explicit. Matched-abstention looks post-hoc. | **Pre-freeze candidate thresholds on dev**; evaluate single threshold per (g, α) on calibration with **Clopper-Pearson exact UCB** + Bonferroni over `|G|·|A|·|T_cand|`. **Re-ground `update_pattern` from inference-time graph features** (`n_supersede_edges`, `n_active_values`, `n_temporal_updates`, `conflict_degree`); Memora metadata only validates proxy on dev (ρ ≥ 0.6). **Strict 3-way split**: dev/calibration/test. **Risk-coverage curve = primary** baseline comparison; baseline thresholds tuned on dev (no post-hoc). Drop weighted-conformal from main; add per-cell `(n_g, abstain_mass_g)` table. | Yes — exact, finite-sample, distribution-free theorem; method now benchmark-independent; split hygiene locked. | Polish only: theorem statement should mention `G_eff`; KS-test should be diagnostic not gate; risk-coverage might cross locally → AURC fallback. |
| 3 | (READY round) | (Polish folded into FINAL_PROPOSAL.md.) Theorem now stated over `G_eff`; KS-test framed as descriptive drift diagnostic; AURC added as fallback summary alongside Pareto-dominance. | Yes — no blocking issues. | None blocking. |

## Overall Evolution

- **Method became more concrete.** From "standard split-conformal coverage" (round 0, overclaimed) → "Wilson UCB selective-risk control" (round 1, still approximate) → "Clopper-Pearson exact UCB on pre-frozen candidate thresholds with Bonferroni over (g, α, τ)" (round 2, exact + finite-sample) → "+ AURC fallback + drift diagnostic + `G_eff`-aware theorem" (round 3, polished).
- **Dominant contribution became more focused.** Started as "Conformal-Calibrated Memory + PMI Phase Diagram on FAMA" (3 coupled tools); became "Selective-Risk-Controlled Abstention Operator with Exact Finite-Sample Guarantee, Headline on Memora's Temporal-Forgetting Subset" (1 dominant + 1 supporting).
- **Unnecessary complexity removed.** Adaptive 50-point grid search → 5 pre-frozen candidates per cell. Wilson UCB → Clopper-Pearson exact. Vanilla split CP claim → CRC / selective-classification framing. Memora-metadata-dependent groups → inference-time graph-feature groups. Path D's controlled slice → stress diagnostic only (not calibration). LoCoMo → appendix. Secondary backbone → appendix. `no_pmi` ablation → secondary. Weighted conformal → future work.
- **Frontier leverage validated as appropriate.** No new training, no new architecture, no agentic multi-round retrieval, no Swin-VIB. LLM-as-structurer (writer), LLM-as-judge (linker, 3-call self-consistency), LLM-as-relevance-gauge (PMI, frozen prefix probability) — exactly the SimpleMem-2026 / LightMem-2026 division of labour, applied to the abstention-quality sub-problem the field has not addressed.
- **Drift avoided.** Reviewer flagged drift = NONE in all 3 rounds. The pivot from "validity intervals as novelty" (Path D) to "selective-risk guarantee as novelty" (β v2) was the correct response to the EverMemOS scoop, not drift. Round-1 reviewer warning ("PMI / generic confidence taking over the story") was preempted by keeping the score function rooted in the typed conflict graph and leading the empirics with the temporal-forgetting subset.

## Final Status

- **Anchor status.** Preserved + better anchored across all 3 rounds. Truth maintenance under forgetting + abstention quality on contradictions, with a *guarantee* — and the guarantee is now exact and finite-sample.
- **Focus status.** Tight. One semantic + statistical contribution; one supporting diagnostic; risk-coverage as primary figure; temporal-forgetting subset as empirical centre.
- **Modernity status.** Appropriately frontier-aware. FM-era primitives (writer, linker, PMI) in their natural roles; classical-statistics primitives (Clopper-Pearson, Bonferroni, selective classification, CRC) imported from RAG and i.i.d. ML, retargeted to memory.
- **Strongest parts of final method.**
  - Theorem is *exact, finite-sample, distribution-free*: `Pr[wrong | answered, g] ≤ α` with probability ≥ 1 − δ over the calibration sample, via Clopper-Pearson + Bonferroni over (g, α, τ).
  - `update_pattern` axis is *inference-time computable* from observable graph features — no benchmark dependence.
  - Risk-coverage curve as the primary figure preempts the trivial "abstain more to look safer" objection by design.
  - Pre-registered intrinsic gates (per-group dev coverage, PMI ρ, `update_pattern` proxy ρ) all run *before* test-time and gate the entire pipeline.
- **Remaining weaknesses (polish only, all from round-3 review).**
  - Theorem must state explicitly over `G_eff` not the nominal 9-cell grid (folded into FINAL_PROPOSAL).
  - KS-test should be framed as a descriptive drift diagnostic (folded into FINAL_PROPOSAL).
  - Risk-coverage Pareto-dominance is aggressive; AURC added as fallback summary metric (folded into FINAL_PROPOSAL).
