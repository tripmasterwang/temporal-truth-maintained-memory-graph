# Round-3 Review — CalLB (round-2 refinement)

**Reviewer:** GPT-5.4 xhigh via Codex MCP (same thread)
**Thread ID:** `019dcdd2-8a56-7c51-8017-9ac14ad3038e`
**Date:** 2026-04-27
**Overall:** **8.5 / 10 — REVISE** (up from 7.6 → 8.5)

> "This is close. It is no longer a rethink. The math is mostly repaired, the positioning is honest,
> and the paper has one clear mechanism. I would still not call it READY because there are two
> remaining review-facing vulnerabilities: **cleanliness vs utility**, and **whether CRC matters
> beyond a fixed threshold**."

## Scores

| Dimension | R1 | R2 | R3 | Δ R2→R3 | Note |
|---|---:|---:|---:|---:|---|
| Problem Fidelity | 8 | 8.5 | **9** | +0.5 | Tightly aligned with anchored bottleneck. |
| Method Specificity | 7.5 | 8.5 | **9** | +0.5 | Engineer could implement tomorrow. |
| Contribution Quality | 5.5 | 6.5 | **8** | +1.5 | Focused; remaining weakness is cleanliness ≠ utility. |
| Frontier Leverage | 7 | 8 | **8.5** | +0.5 | Good FM-era primitive use; small learned component. |
| Feasibility | 6 | 7 | **8.5** | +1.5 | Now feasible in stated budget. |
| Validation Focus | 5.5 | 7.5 | **8** | +0.5 | Run matrix disciplined; missing utility check. |
| Venue Readiness | 5.5 | 7 | **8** | +1.0 | Plausible main-track if empirical lands. |

## Lens-by-lens readout

- **L1''(a) monotonicity.** ✓ `R(λ; q) = 1[∃ D in L_λ(q)]` monotone non-increasing because `L_{λ_2} ⊆ L_{λ_1}` for `λ_1 ≤ λ_2`.
- **L1''(b) Hoeffding-on-grid validity.** ✓ With one condition: the 100-pt λ grid must be **fixed independently of cal sample**. Under that, Hoeffding + union bound gives valid simultaneous UCB; selecting `λ̂_α` by `ucb_j ≤ α` is valid.
- **L1''(c) slack tightness.** Hoeffding 0.083 slack is **coarse but not fatal**. For α* = 0.20, still informative (need `R̂ ≤ 0.117` to certify). For **α = 0.10, close to non-actionable** — should not headline α=0.10 unless tightened. Since risk is Bernoulli, **one-sided exact binomial (Clopper-Pearson) or empirical-Bernstein UCB is preferable to plain Hoeffding**.
- **L1''(d) composition to reader.** Composes much better than R2. "No distractor in load-bearing tier" aligns with avoiding over-specification. **But still not a guarantee of answer correctness, because it says nothing about whether L contains necessary LB evidence.** ← This is the cleanliness-vs-utility gap; needs a non-vacuity check.
- **L2'' supervision protocol.** ✓ Defensible. κ ≥ 0.7 + κ ≥ 0.75 D-vs-non-D + borderline oversampling + confusion matrix is strong enough. Caveat: paper should show LB↔S confusion, emphasize formal guarantee depends only on D.
- **L3'' attribution baselines.** ✓ Sufficient. The 4 isolate prompt / score / fusion / calibration. `random-MLP+CRC` not needed.
- **L4'' robustness features + pre-registered rescue analysis.** ✓ Enough. If low-agreement singleton-raw-turn rescues dominate → demote "agreement" from thesis-level language immediately.
- **L5'' eval matrix.** ✓ 31 runs / ~16 hr realistic for 1 person + 1 day buffer for API/reruns.
- **L6'' novelty.** Defensible **narrowly**. Not new CRC; introducing a *new reader-facing clean-set risk for memory evidence selection* + showing this is the right object for the anchored failure mode. Enough for main track if empirical story is crisp.
- **L7'' fallback paper.** **NO**. "Formal guarantee only" is not strong main-track fallback. If `no_CRC ≈ CalLB` on downstream accuracy, need ONE of: (i) stronger robustness evidence that CRC generalizes better than fixed thresholding across datasets/slices, OR (ii) stronger practical value from the certified guarantee itself. **Without that, reviewers will say the calibration layer is mathematically neat but practically unnecessary.**

## Three critical fixes for round-4 (LAST allowed round)

### Rev-1 (utility check) — Add non-vacuity metrics on L

The formal object only rewards cleanliness. Reviewers can argue the method certifies cleanliness by **shrinking L too aggressively**. Report at least:

- **Non-empty fraction**: fraction of test queries with `|L_λ̂_α(q)| ≥ 1`.
- **Average tier size**: mean `|L_λ̂_α(q)|` over test.
- **LB-recall of L**: fraction of queries where `L_λ̂_α(q)` contains at least one **LB**-labelled item; equivalently the recall of LB items by L.
- **Ideal headline target**: at α* = 0.20: `non_empty_fraction ≥ 0.85`, `mean |L| ∈ [2, 5]`, `LB_recall ≥ 0.75`.

If these aren't reported, reviewers will assume L is empty/tiny on most queries and the cleanliness guarantee is vacuous.

### Rev-2 (tighten certification) — Pre-specify ONE UCB; clean separation of 1-δ vs 1-α

- **Replace** "Hoeffding with Bernstein fallback" with **one pre-specified one-sided UCB** for Bernoulli mean: **Clopper-Pearson exact binomial UCB at level 1−δ' = 1 − δ/m** (per grid point).
- Theorem statement (proposed):
  > *Theorem. Let `R̂(λ_j) = (1/n_cal) Σ_q R(λ_j; q)` for grid `Λ = {λ_1, ..., λ_m}` fixed independently of cal. Let `U_j = U_{CP}(R̂(λ_j); n_cal, δ/m)` be the Clopper-Pearson upper bound at level `1 − δ/m`. Define `λ̂_α = inf{λ_j ∈ Λ : U_j ≤ α}`. Then under exchangeability of cal and test queries, `Pr_{cal}[ R(λ̂_α) ≤ α ] ≥ 1 − δ`, where the probability is over the random calibration split, and `R(λ̂_α) = Pr_{q ~ test}[L_λ̂_α(q) contains any distractor]` is the test-time clean-set failure probability.*
- **Clean separation**: `1 − δ` is confidence over the random cal split (split-conformal style). `1 − α` is the clean-set probability over test queries given the chosen threshold.

### Rev-3 (`no_CRC` as real go/no-go, not soft fallback)

Make the **acceptance logic explicit** in success conditions:

- CalLB is accepted as a main-track contribution **iff at least one of**:
  - **(A) Downstream lift over fixed thresholding**: CalLB beats `no_CRC` (same MLP scores + dev-tuned fixed threshold) on B+C-prone slice accuracy by ≥ **1 pp** with bootstrapped p < 0.05 on at least one of {LongMemEval-S, Memora}.
  - **(B) Cross-dataset robustness**: when calibrated on one corpus and tested on another (LongMemEval-S → Memora and vice versa), CalLB's contamination guarantee holds within α + 0.06 across both, while `no_CRC`'s fixed threshold violates the same on the held-out corpus by > 0.10.
- **If neither (A) nor (B) holds** at end of Week 2: project is **not strong enough for NeurIPS / ICML main-track** as currently framed. Two options:
  - Pivot to a workshop / findings track venue (smaller scope claim).
  - Replace the formal-guarantee thesis with a "learned multi-substrate fusion + tiered-prompt reader" empirical paper (still defensible if slice lift is real).

This commits the team in advance and prevents post-hoc venue-reframing.

## Implications for round-4 refinement (final round)

1. Add **§Non-vacuity and Utility Metrics** with the three metrics + headline targets.
2. Replace CRC math section with the cleaner Clopper-Pearson theorem statement.
3. Add explicit **§Acceptance Logic for Main-Track Submission** with the (A)-or-(B) requirement and the workshop-pivot fallback.

These are bounded, math-only / spec-only changes — no new experiments to design. After round-4, expect score ≥ 9 (READY) or worst-case 8.7-8.9 (REVISE we accept and proceed since MAX_ROUNDS=4 reached).
