# Round 1 Review (GPT-5.4 xhigh) — Pivot β v2

**Thread ID:** `019dc991-2df1-79d0-8e01-d350d7638426`
**Date:** 2026-04-26
**Verdict:** REVISE
**Overall score:** 7.6 / 10

## Scores

| Dimension | Score | Notes |
|-----------|------:|-------|
| Problem Fidelity | 9 | Anchor preserved (truth maintenance under forgetting). |
| Method Specificity | 6 | **CRITICAL.** "Standard split-conformal" *does not* imply `Pr[wrong | answered, g] ≤ α`. That's the hard *conditional-on-answer* event. Mondrian too fine; `abstention` is an outcome, cannot be a group axis. |
| Contribution Quality | 8 | One dominant contribution; PMI phase diagram OK if it stays secondary. |
| Frontier Leverage | 9 | Right use of 2026 white-space. |
| Feasibility | 8 | Code delta small; risk is calibration cleanliness, not implementation. |
| Validation Focus | 6 | **IMPORTANT.** Surface area too large for 3-4 weeks; needs answer-rate / matched-abstention guard against "abstain more to look safe". |
| Venue Readiness | 6 | **CRITICAL.** Reviewers can dismiss as "generic conformal pasted on existing memory" unless theorem is right and temporal-forgetting story is visibly central. |

## CRITICAL action items

1. **Recast as selective risk control (CRC), not vanilla split CP.**
   - Current claim: standard split-conformal coverage. Reality: that gives marginal miscoverage on a *prediction-set inclusion event*, not on the *conditional-on-answer error event* which is what `Pr[wrong | answered, g] ≤ α` requires.
   - **Fix.** Define a scalar confidence score `S(q)`. On a held-out Memora calibration split, for each group `g` and threshold `τ`, estimate selective risk `r_g(τ) = #{wrong AND S≥τ} / #{S≥τ}`. Choose smallest `τ` whose one-sided upper-confidence bound is ≤ α (Wilson / Clopper-Pearson UCB), with a *minimum answered-count floor*, and a multiple-testing correction across the (g, α) grid. Cite CRC (Angelopoulos et al.) and selective-classification machinery (Geifman & El-Yaniv). Path D's controlled slice becomes a diagnostic stress set, not a threshold calibration source.

2. **Lead with the temporal-forgetting story.**
   - Make obsolete-memory cases the paper's *primary unit of analysis*. Lead the results section with supersede-heavy / multi-update / time-sensitive subsets and show the gain concentrates there. If the strong conditional guarantee is not provable in time, weaken the theorem claim *rather than overclaiming*.

## IMPORTANT action items

3. **Tighten validation surface.**
   - Memora + FAMA + answer-rate + risk-coverage curves = main paper.
   - One parity benchmark in main text, not both.
   - `no_conformal` and `no_groups` are must-haves; `no_pmi` → secondary unless PMI is in the headline.
   - Add explicit *minimum answer-rate* or *matched-abstention-rate* comparison to guard against "abstain more to look safer".

## MINOR / simplification

- Calibrate only on held-out Memora split; controlled slice = stress diagnostic only.
- Reduce Mondrian to `PMI bin × update pattern` or `conflict degree × update pattern`. Keep KU/TR/slot type as reporting strata, not calibration strata. **Drop `abstention` as a group axis** (it's an outcome, not a pre-decision covariate).
- Choose one of LoCoMo or LongMemEval-S for main; the other → appendix.

## Modernizations

1. **Replace split-conformal framing with conformal risk control / selective classification** — the correct modern object for answer/abstain guarantees.
2. Add **risk-coverage** and **group-conditional reliability** plots, not only coverage-at-5-α tables.
3. If calibration/test mismatch persists, use **weighted or hierarchical conformal** rather than fixed sparse Mondrian cells.

## Drift Warning

**NONE major.** Moving novelty from validity intervals to coverage guarantees is the correct response to EverMemOS, not drift. Real drift risk: if PMI / generic confidence becomes the story and the temporal conflict graph becomes incidental, the work reads as generic selective QA rather than truth maintenance under forgetting.

---

<details>
<summary>Raw GPT-5.4 response (verbatim)</summary>

**Summary**

This is a real re-pivot, not a cosmetic rewrite. The paper now has a sharper and more defensible thesis than "validity intervals as novelty." The blocking issue is that the current calibration recipe does **not yet justify** the headline claim `Pr[wrong | answered, g] ≤ α` as written; fix that, and this becomes a credible guarantee paper.

**Scores**

1. **Problem Fidelity: 9/10** — It still attacks the original bottleneck: wrong answers from stale or conflicting memory under temporal updates. The abstention objective is tied to forgetting/truth-maintenance, not to generic QA confidence alone.

2. **Method Specificity: 6/10** — The engineering plan is concrete, but the **statistical target is not yet correctly instantiated**. The written split-conformal construction is not enough to imply `Pr[wrong | answered, g] ≤ α`; it looks closer to marginal miscoverage control than selective-risk control. The Mondrian design is also likely too fine-grained for the proposed calibration size.

3. **Contribution Quality: 8/10** — There is one dominant contribution, and it is materially more novel than another structural-memory variant in 2026. The PMI phase diagram is acceptable as a supporting diagnostic if it stays secondary; otherwise it risks mild sprawl.

4. **Frontier Leverage: 9/10** — This is the right use of the 2026 white-space: import mature statistical machinery into a memory setting that has not used it. Reusing temporal conflict structure as calibration features is a good interface between FM-era systems and classical guarantees.

5. **Feasibility: 8/10** — The code delta is small and the substrate exists. The risk is not implementation; it is getting a clean calibration protocol, enough samples per group, and a theorem reviewers cannot immediately punch through.

6. **Validation Focus: 6/10** — Slightly bloated. Memora/FAMA is the core; one parity benchmark is enough for the non-regression story. EverMemOS reproduction, full multi-axis Mondrian reporting, and too many main-paper baselines will consume time without proportionate evidential gain.

7. **Venue Readiness: 6/10** — As written, not yet main-track ready because the headline guarantee is overclaimed relative to the method. If the risk-control theorem is repaired and the evaluation is tightened around risk-coverage/FAMA, the framing is strong enough for a guarantee paper.

**OVERALL SCORE: 7.6/10**

**Dimensions < 7**

- **Method Specificity — CRITICAL**
Weakness: the current "standard split-conformal" claim does not establish `Pr[wrong | answered, g] ≤ α`. That conditional-on-answer event is the hard part. Also, `PMI bin × {KU, TR, abstention} × trace pattern` is too many cells unless calibration is very large, and `abstention` cannot be a group axis if it is an outcome rather than a pre-decision covariate.
Concrete fix: recast this as **selective risk control**, not vanilla split conformal. Define a scalar confidence score `S(q)` once. On a pure held-out Memora calibration split, for each group `g` and threshold `τ`, estimate selective risk
`r_g(τ) = # {wrong and S≥τ} / # {S≥τ}`.
Choose the smallest `τ` whose one-sided upper confidence bound is ≤ `α`, with a minimum answered-count floor. Use CRC/selective-classification machinery, or a fixed threshold grid with Wilson/Clopper-Pearson UCB + multiple-testing correction. Collapse groups aggressively or use hierarchical merging with minimum `n_g`. Keep the controlled supersede slice for stress-testing, not for threshold calibration.

- **Validation Focus — IMPORTANT**
Weakness: too much surface area for 3–4 weeks, and the current plan does not adequately guard against the trivial "abstain more to look safe" objection.
Concrete fix: make the main paper center on `Memora + FAMA + answer rate + risk-coverage curves`. Keep exactly one parity benchmark in the main text. Make `no_conformal` and `no_groups` the must-have ablations; move `no_pmi` to secondary unless PMI is part of the headline. Define an explicit minimum answer-rate or matched-abstention comparison.

- **Venue Readiness — CRITICAL**
Weakness: reviewers can dismiss this as "generic conformal abstention pasted on top of an existing memory system" unless the theorem is right and the temporal-forgetting slice is visibly central.
Concrete fix: make obsolete-memory cases the paper's primary unit of analysis. Lead with supersede-heavy / multi-update / time-sensitive subsets, and show that the gain concentrates there. If the strong conditional guarantee is not provable in time, weaken the theorem claim rather than overclaiming.

**Simplification Opportunities**

1. Calibrate only on a held-out Memora split; use the Path-D controlled slice only as a diagnostic stress set.
2. Reduce Mondrian groups to `PMI bin × update pattern` or `conflict degree × update pattern`; keep KU/TR/slot type as reporting strata, not calibration strata.
3. Put only one of `LoCoMo` or `LongMemEval-S` in the main paper.

**Modernization Opportunities**

1. Replace the split-conformal framing with **conformal risk control / selective classification** framing; that is the correct modern object for answer/abstain guarantees.
2. Add **risk-coverage** and **group-conditional reliability** plots, not only coverage-at-5-α tables.
3. If calibration/test mismatch remains, use **weighted or hierarchical conformal** rather than fixed sparse Mondrian cells.

**Drift Warning**

No major drift. Moving the novelty from validity intervals to coverage guarantees is the correct response to EverMemOS and is not drift. The real drift risk is narrower: if PMI/generic confidence becomes the story and the temporal conflict graph becomes incidental, the work will read as generic selective QA rather than truth maintenance under forgetting.

**Verdict: REVISE**

</details>
