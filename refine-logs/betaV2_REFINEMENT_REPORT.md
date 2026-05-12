# Refinement Report — Pivot β v2

**Problem.** Truth maintenance under forgetting + abstention quality on contradictions in long-conversation agent memory, *with a guarantee*. The previous Path D refinement (already in `pathD_*` archive) reframed TTMG as a "scoped specialist with audited applicability gate"; the user pushed back that this is reviewer-safe but incremental given the actual 2026 frontier (EverMemOS already does validity intervals; SmartSearch deterministic at 91.9 % LoCoMo). The structural white-space the field has not entered is statistical / information-theoretic.

**Initial Approach (Pivot β).** Selective-risk-controlled abstention operator with exact finite-sample guarantee, validated end-to-end on Memora + FAMA where no memory system has reported scores yet. Reuse Path D substrate as engineering scaffolding, *not* contribution.

**Date.** 2026-04-26
**Rounds.** 3 / 5
**Final Score.** **9.15 / 10**
**Final Verdict.** **READY**

## Problem Anchor (verbatim across all 3 rounds)

(See `REVIEW_SUMMARY.md` for the full Problem Anchor.)

## Output Files

- Final proposal: `refine-logs/FINAL_PROPOSAL.md`
- Review summary: `refine-logs/REVIEW_SUMMARY.md`
- Round-0 initial proposal: `refine-logs/round-0-initial-proposal.md`
- Round-N reviews: `refine-logs/round-{1,2,3}-review.md`
- Round-N refinements: `refine-logs/round-{1,2}-refinement.md`
- Score evolution: `refine-logs/score-history.md`
- Frontier report (motivation): `refine-logs/AGENT_MEMORY_FRONTIER_REPORT.md`
- Idea evaluation (motivation): `refine-logs/IDEA_EVALUATION.md`
- Lit survey (the document the user pointed to): `refine-logs/LIT_SURVEY.md`
- Path D archive (deprecated as primary, kept as substrate): `refine-logs/pathD_*.md`

## Score Evolution

| Round | Problem Fidelity | Method Specificity | Contribution Quality | Frontier Leverage | Feasibility | Validation Focus | Venue Readiness | Overall | Verdict |
|-------|-----------------:|-------------------:|---------------------:|------------------:|------------:|-----------------:|----------------:|--------:|---------|
| 1     | 9                | 6                  | 8                    | 9                 | 8           | 6                | 6               | 7.6     | REVISE  |
| 2     | 9                | 8                  | 9                    | 9                 | 8           | 8                | 8               | 8.6     | REVISE  |
| 3     | 10               | 9                  | 9                    | 9                 | 9           | 9                | 9               | **9.15** | **READY** |

## Round-by-Round Review Record

| Round | Main Reviewer Concerns | What Was Changed | Result |
|-------|------------------------|------------------|--------|
| 1 | Theorem overclaimed (vanilla split-CP not a `Pr[wrong | answered]` guarantee); Mondrian too fine; `abstention` as group axis invalid; bloated validation; "generic conformal pasted on existing memory" risk. | Recast as CRC / selective risk control with Wilson UCB; Mondrian simplified to `(pmi_bin, update_pattern)`; lead with temporal-forgetting subset; matched-abstention comparison; trim validation. | Resolved: 7.6 → 8.6. |
| 2 | Wilson UCB approximate; adaptive grid needs threshold-level Bonferroni; `update_pattern` benchmark-dependent; split hygiene not explicit; matched-abstention looks post-hoc. | Pre-frozen candidate thresholds on dev + Clopper-Pearson exact UCB + Bonferroni over `|G|·|A|·|T_cand|`; `update_pattern` re-grounded from inference-time graph features; strict 3-way split; risk-coverage curve = primary baseline comparison; baseline thresholds tuned on dev. | Resolved: 8.6 → 9.15. |
| 3 | Polish only: theorem should state over `G_eff`; KS-test should be diagnostic not gate; risk-coverage Pareto might cross locally — need AURC fallback. | (Polish folded into `FINAL_PROPOSAL.md`.) | **READY.** |

## Final Proposal Snapshot

Canonical clean version lives in `refine-logs/FINAL_PROPOSAL.md`. The thesis in 5 bullets:

1. **Selective-risk-controlled abstention operator for memory-augmented answering.** For each retrieved memory subset relevant to a query, compute hardness-weighted scalar score `S(q) = w_h · mean(hardness in ⋃Opts) + w_u · 1[|Vals|==1] + w_p · clip(PMI/PMI_scale)`; on dev fix candidate-threshold sets per inference-time-defined group; on calibration evaluate one pre-frozen threshold per (g, α) using Clopper-Pearson exact UCB with Bonferroni correction; at inference, answer iff `S(q) ≥ τ̂_g(α; δ)` and unique-value, else abstain.
2. **Theorem (exact, finite-sample, distribution-free).** Under exchangeability, with prob ≥ 1 − δ over Cal, for every `g ∈ G_eff` and every `α ∈ A`, `P_test[ŷ ≠ y* | S ≥ τ̂_g(α; δ), g(q) = g] ≤ α`. Proof via Clopper-Pearson inversion + Bonferroni over (g, α, τ).
3. **Inference-time-computable Mondrian groups.** `g(q) = (pmi_bin(q), update_pattern(q))` where `update_pattern ∈ {single-trace, multi-update, supersede-heavy}` is computed from observable graph features (`n_supersede_edges`, `n_active_values`, `n_temporal_updates`, `conflict_degree`). Memora metadata only validates the proxy on dev (Spearman ρ ≥ 0.6).
4. **Memora-first headline empirics on the temporal-forgetting subset.** Risk-coverage curve as the primary figure (sweep each method's confidence threshold); AURC as fallback summary; matched-rate marker at α = 0.10 on the curve. **No memory system has published FAMA scores yet** — TTMG-β is the first.
5. **Honest non-claims and parity.** No claim of LoCoMo / LongMemEval-S accuracy win; parity within 2 pp on LongMemEval-S. The contribution is the *guarantee*, not the architecture (Path D substrate is engineering scaffolding, not novelty).

## Method Evolution Highlights

1. **Most important simplification / focusing move.** Round 2's pre-freeze of candidate thresholds on dev. Eliminated the adaptive-grid search, made the theorem exact, reduced calibration sample needs, and removed the threshold-level multiple-testing-correction headache. *Less* code, *more* rigour.
2. **Most important mechanism upgrade.** Round 1's recast from vanilla split-CP to CRC / selective risk control. The previous claim was statistically wrong; the recast aligned the theorem with what the procedure actually proves. Without this, the entire paper would have been published with an overclaim.
3. **Most important modernization.** Importing Clopper-Pearson + Bonferroni + selective-classification machinery into a memory-system paper. The keyword-scan-confirmed white-space turned a system-level paper into a guarantee-level paper, which is the only way to differentiate against the saturated structural-memory frontier (EverMemOS, SmartSearch, SimpleMem, LightMem).

## Pushback / Drift Log

| Round | Reviewer Said | Author Response | Outcome |
|-------|---------------|-----------------|---------|
| 1 | "Recast as CRC / selective risk control." | Accepted. | Round 1 refinement uses Wilson UCB; round 2 upgrades to Clopper-Pearson exact. |
| 1 | "Lead with temporal-forgetting subset." | Accepted. | Headline empirics restructured. |
| 1 | "`abstention` cannot be a group axis." | Accepted. | Mondrian simplified to `(pmi_bin, update_pattern)`. |
| 2 | "Wilson is approximate; adaptive grid needs threshold-level Bonferroni." | Accepted (clean path: pre-freeze candidates on dev + Clopper-Pearson exact). | Theorem exact. |
| 2 | "`update_pattern` benchmark-dependent." | Accepted. Re-grounded from inference-time graph features. | Method benchmark-independent. |
| 2 | "Matched-abstention looks post-hoc." | Accepted (both fixes applied: dev-tuned baseline thresholds + risk-coverage curve as primary). | Eliminates post-hoc objection. |
| All | (No reviewer suggestions caused drift.) | (No pushback needed.) | Drift = NONE in all 3 rounds. |

## Remaining Weaknesses

- **Theorem dependent on exchangeability assumption.** If the calibration set and Memora test split are not exchangeable, the guarantee no longer holds. The KS-test drift diagnostic gives transparency on this; weighted conformal (mentioned as future work) would be the principled fix.
- **`update_pattern` proxy may correlate weakly with Memora ground truth in practice.** Pre-test gate ρ ≥ 0.6 may need re-tuning of bin boundaries; if it fails after re-tuning (ρ < 0.4), we drop the axis (marginal-only Mondrian) and the per-group story weakens.
- **EverMemOS reproduction risk.** If the public code in `MemMachine/competitor/2601.02163_EverMemOS/code/` does not reproduce within 5 pp of the paper's LoCoMo number, the head-to-head comparison on Memora is unfair; mitigated by also citing EverMemOS's published numbers and pair-comparing on Memora only (where neither side has published numbers).
- **Risk-coverage curves may cross locally.** AURC fallback summary handles this case; success condition (8) treats AURC dominance as a separate sufficient outcome.
- **Memora calibration set may be too small per cell after merging.** N_min = 30 floor + hierarchical merging fallback handles this, but if the Memora train split is genuinely too small the entire 9-cell Mondrian collapses to fewer effective cells — reported transparently in `G_eff`.

## Raw Reviewer Responses

<details>
<summary>Round 1 Review</summary>

(See `refine-logs/round-1-review.md` for the raw GPT-5.4 response in full.)

</details>

<details>
<summary>Round 2 Review</summary>

(See `refine-logs/round-2-review.md` for the raw GPT-5.4 response in full.)

</details>

<details>
<summary>Round 3 Review (READY)</summary>

(See `refine-logs/round-3-review.md` for the raw GPT-5.4 response in full.)

</details>

## Next Steps

- **READY → proceed to `/experiment-plan`** for a detailed execution roadmap that turns the FINAL_PROPOSAL into concrete weekly experiments with explicit MAAS-call budgets, file-level changes to `ttmg/`, prompt drafts for writer/linker/parser, statistical-test plans (Clopper-Pearson UCB at the chosen δ, cluster-bootstrap CIs, AURC computation, KS drift diagnostic), and the Memora data-pull script.
- After `/experiment-plan` is in hand, `/run-experiment` is the natural next step — but only after Week-1 intrinsic gates clear (per-group dev coverage, PMI Spearman ρ, `update_pattern` proxy ρ, KS drift diagnostic). If any gate fails, **lock-stop** and iterate dev-side parameters before any test-time runs.
- Pre-execution housekeeping (already enumerated as paper-level non-negotiables in `IDEA_EVALUATION.md` and `AGENT_MEMORY_FRONTIER_REPORT.md`): reconcile prior `STATUS.md` with reality, swap in real MemGPT (arXiv 2310.08560), cite SimpleMem and LightMem rows in the comparison table, run EverMemOS from `MemMachine/competitor/2601.02163_EverMemOS/code/` early (Week 1) so its reproduction risk is known by Week 2.
