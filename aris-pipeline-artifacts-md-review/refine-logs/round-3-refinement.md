# Round-3 Refinement: CalLB — Final-round (utility check + tighter UCB + go/no-go)

## What changed vs round-2 (and why)

| # | Change | Driver |
|---|---|---|
| 1 | **Non-vacuity / utility metrics on L** | R3 Rev-1 — formal cleanliness object alone is vacuous if L is empty/tiny. Now report `non_empty_fraction`, `mean_|L|`, `LB-recall(L)` with headline targets. |
| 2 | **Clopper-Pearson exact binomial UCB** | R3 Rev-2 — Hoeffding 0.083 slack makes α=0.10 close to non-actionable. CP exact-binomial UCB is tighter for Bernoulli; theorem cleanly separates `1-δ` (cal) vs `1-α` (test). |
| 3 | **Explicit go/no-go on `no_CRC`** | R3 Rev-3 — fallback "formal-guarantee-only" paper is NOT strong main-track. Acceptance logic: (A) downstream lift over `no_CRC` ≥ 1 pp w/ p<0.05, OR (B) cross-dataset robustness; if neither → workshop pivot. |

(All other R2 content — anchor, thesis, features, labels, baselines, eval matrix, timeline — carries over unchanged.)

## Problem Anchor (UNCHANGED — verbatim from round-0)

[Same as round-0 / round-1 / round-2.]

## Method Thesis (UNCHANGED from round-2)

> *For each retrieved memory item, fuse semantic + lexical + claim-graph + raw-turn substrate signals into a learned reliability score; calibrate a single threshold `λ̂_α` via **Conformal Risk Control on the clean-set indicator risk** so that with probability ≥ 1 − α, the load-bearing tier `L_λ̂_α(q) = {item : score ≥ λ̂_α}` contains **no distractor**; expose `L` and `S = top-3 \\ L` to the reader as separate tiers, instructed to use only `L` for load-bearing facts.*

## CRC Math (TIGHTENED per R3 Rev-2)

### Risk function (UNCHANGED — clean-set indicator)

```
L_λ(q) = { item ∈ candidates(q) : MLP_score(item) ≥ λ }
R(λ; q) = 𝟙[ ∃ item ∈ L_λ(q) with label = D ]   ∈ {0, 1}
R(λ)    = E_q[R(λ; q)] = Pr_q[L_λ(q) contains any distractor]   ∈ [0, 1]
```

Monotone non-increasing in λ for each q (and hence for the average) because `L_{λ_2} ⊆ L_{λ_1}` for `λ_1 ≤ λ_2`.

### Theorem (CLEAN — Clopper-Pearson UCB + grid union bound)

> **Theorem.** Fix a λ-grid `Λ = {λ_1, ..., λ_m}` with m = 100 chosen *independently* of the calibration sample. For each `λ_j ∈ Λ`, let `R̂(λ_j) = (1/n_cal) Σ_{q ∈ cal} R(λ_j; q)` and let `U_j = U_{CP}(R̂(λ_j); n_cal, δ/m)` be the **one-sided Clopper-Pearson upper bound** on the Bernoulli mean at confidence `1 − δ/m` (i.e., `U_j` is the largest p such that `Pr[Binomial(n_cal, p) ≤ R̂(λ_j) · n_cal] ≥ δ/m`).
>
> Define `λ̂_α = inf { λ_j ∈ Λ : U_j ≤ α }` (= +∞ if no λ_j satisfies).
>
> Under exchangeability of cal and test queries:
> ```
> Pr_{cal split} [ R(λ̂_α) ≤ α ] ≥ 1 − δ
> ```
> where the outer probability is over the random calibration split, and `R(λ̂_α) = Pr_{q ∼ test}[L_λ̂_α(q) contains any distractor]` is the test-time clean-set failure probability.

**Clean separation of confidence levels.** The theorem has two distinct probability statements:
- `1 − δ` is the confidence over the *random calibration split* (split-conformal level; we set δ = 0.05).
- `1 − α` is the *clean-set probability over test queries*, given the chosen threshold (e.g., α* = 0.20 → at least 80 % of test queries see a clean L).

**Proof sketch.** For each fixed `λ_j`, `n_cal · R̂(λ_j) ~ Binomial(n_cal, R(λ_j))`, so the Clopper-Pearson UCB satisfies `Pr[U_j < R(λ_j)] ≤ δ/m` for each j. Union bound over the m = 100 grid points: `Pr[∃ j with U_j < R(λ_j)] ≤ δ`. On the high-prob event {∀j: U_j ≥ R(λ_j)}, by monotonicity of R in λ, for any j with `U_j ≤ α`, `R(λ_j) ≤ U_j ≤ α`. Hence `R(λ̂_α) ≤ α`. ∎

**Why Clopper-Pearson over Hoeffding.** For Bernoulli mean with n_cal=600 and δ/m = 0.0005:
- Hoeffding slack: ≈ 0.083 (constant, not data-adaptive).
- Clopper-Pearson at `R̂ = 0.05`: UCB ≈ 0.078 (slack ≈ 0.028, much tighter at small risks).
- At `R̂ = 0.20`: UCB ≈ 0.245 (slack ≈ 0.045, still tighter).

This makes α = 0.10 actionable (need `R̂ ≤ ~0.04` to certify) and α = 0.20 comfortable.

### Cost

CRC compute: 100 grid points × 600 cal-of-cal queries × <30 candidates each ≈ negligible CPU. Clopper-Pearson UCB via `scipy.stats.beta.ppf` (closed-form) per grid point.

## Non-vacuity and Utility Metrics on L (NEW per R3 Rev-1)

The clean-set guarantee `Pr[no D in L] ≥ 1 − α` is **vacuously satisfied if L is empty**. The paper must show that L is non-trivially populated and contains useful evidence. Reporting (mandatory in the paper):

| Metric | Definition | Headline target (α* = 0.20) | Failure threshold |
|---|---|---|---|
| `non_empty_fraction(L)` | Fraction of test queries with `|L_λ̂_0.20(q)| ≥ 1` | **≥ 0.85** | < 0.70 → L vacuous; reframe |
| `mean_size(L)` | Mean of `|L_λ̂_0.20(q)|` over test | **∈ [2, 5]** | < 1.0 → too aggressive; lower λ̂ |
| `LB_recall(L)` | Fraction of test queries where `L_λ̂_0.20(q)` contains at least one **LB**-labelled item | **≥ 0.75** | < 0.50 → L misses load-bearing; reranker mis-trained |
| `LB_precision(L)` | Average over queries of `#(LB items in L) / max(1, |L|)` | report descriptively | — |
| (descriptive) `mean distractor fraction in L` | The R2 risk, now reported as a secondary diagnostic | report descriptively | — |

**Joint reading**: a healthy CalLB shows `non_empty ≥ 0.85`, `mean |L| ∈ [2,5]`, `LB_recall ≥ 0.75`, AND `R̂(λ̂_α) ≤ α + 0.04`. If clean-set certification is met but utility metrics fail (e.g., L is mostly empty), the **F1' failure clause** triggers: drop the formal guarantee, reframe as "learned multi-substrate fusion + tiered prompt" empirical paper.

**Pre-registration:** all four utility metrics are computed and reported regardless of outcome.

## Acceptance Logic for Main-Track Submission (NEW per R3 Rev-3)

CalLB is accepted as a **NeurIPS / ICML main-track contribution** iff at least one of the following holds at end of Week 2:

### Path (A) — Downstream lift over fixed thresholding
CalLB beats `no_CRC` (same MLP scores + dev-tuned fixed threshold) on B+C-prone slice accuracy by ≥ **1 pp** with **bootstrapped paired p < 0.05** on at least one of {LongMemEval-S, Memora-FAMA}.

### Path (B) — Cross-dataset robustness
When λ̂_α is calibrated on **one corpus** (e.g., LongMemEval-S train) and applied directly to test on **another** (e.g., Memora test) **without re-calibration**:
- CalLB's contamination guarantee holds within `α + 0.06` on the held-out corpus.
- `no_CRC`'s fixed dev-tuned threshold violates the equivalent contamination by `> 0.10` on the held-out corpus.

I.e., CRC threshold transfers; fixed dev threshold does not.

### Fallback if neither (A) nor (B) holds

The project is **not strong enough for the current main-track venue target** as currently framed. Two pre-committed options:

- **Option F1**: Pivot to a workshop / findings track venue (smaller-scope claim: "calibrated load-bearing selection for memory; first formal guarantee").
- **Option F2**: Drop the formal-guarantee thesis. Reframe as a **purely empirical paper** on "learned multi-substrate fusion + tiered-prompt reader for long-conversation memory", with CRC as a supplementary appendix. Submit to main-track *only if* B+C slice lift is ≥ 5 pp on the empirical headline (stronger empirical bar to compensate for losing the theoretical hook).

This commits the team **in advance** and prevents post-hoc venue-rationalization.

## Updated Success Conditions (CONSOLIDATED)

1. **Probabilistic clean-set guarantee on test (formal object).** Empirical `R̂_test(λ̂_α) ≤ α + 0.04` for α ∈ {0.10, 0.20, 0.30, 0.40} on Memora test + LongMemEval-S test (Clopper-Pearson CRC bound holds).
2. **Non-vacuity / utility metrics on L (NEW).** At α* = 0.20: `non_empty_fraction ≥ 0.85`, `mean |L| ∈ [2, 5]`, `LB_recall ≥ 0.75`.
3. **B+C-prone slice lift on LongMemEval-S (headline metric).** ≥ **3 pp lift** on union of B-prone (KU, single-session-preference) + C-prone (single-session-user, multi-session, KU) slices vs Path D `ttmg`; no slice regression > 1 pp.
4. **Acceptance logic for main-track (NEW).** Path (A) OR Path (B) holds. If neither → Option F1 (workshop) or F2 (empirical-only main-track with ≥ 5 pp bar).
5. **Attribution causality.** `prompt-only` < 50 %, `rerank-only` < 70 %, `agreement-heuristic-only` < 70 %, `no_CRC` < 100 % of CalLB's slice lift (with the 1-pp gap committed in Path (A) above).
6. **Mechanism causality.** `no_cross_substrate_agreement` OR `no_robustness_features` drops Class-B-fix lift by ≥ 50 % (at least one — narrative adjusts per pre-registration); `no_drift_features` drops KU lift by ≥ 30 %.
7. **Portable subset (honest generality).** `portable_features_only` (8 features) achieves ≥ **50 %** of CalLB's slice lift.
8. **Class-B rescue analysis (pre-registered).** Reported regardless of outcome; narrative adjusted per Rev-4 trigger from R2.
9. **FAMA — secondary parity.** Within **3 pp** of best baseline on Memora-temporal-forgetting subset.
10. **LoCoMo parity.** Within **2 pp** of best of (Path D, A-Mem, SmartSearch).
11. **Failure clauses (kill conditions).**
    - F1 (CRC bound invalid): `R̂(λ̂_α) > α + 0.06` for ≥ 2 of 4 α → check Clopper-Pearson computation; if persistent, drop formal claim → trigger Option F2.
    - F1' (L vacuous): `non_empty_fraction < 0.70` OR `LB_recall < 0.50` → Option F2.
    - F2 (prompt-only dominates): `prompt-only ≥ 70 %` of slice lift → reframe as prompt-engineering paper.
    - F3 (no slice lift): B+C slice lift < 1 pp on ≥ 2 slices → pivot direction entirely.
    - F4 (label noise): D-vs-non-D κ < 0.65 → binary collapse and re-derive.
    - F9 (CRC vs fixed): `no_CRC ≈ CalLB` (no Path A win AND no Path B robustness) → trigger Option F1 or F2.

## Everything Else (UNCHANGED from round-2)

The following sections of the round-2 refinement carry over verbatim and are not duplicated here:

- **Contribution Focus** (one dominant + one supporting + explicit non-contributions; not substrate-agnostic).
- **Feature Set** (13 features: 5 portable + 3 robustness + 5 TTMG-specific).
- **3-tier Label** semantics + LLM-judge prompt (κ ≥ 0.7 / κ ≥ 0.75 D-vs-non-D / 30 % borderline oversample).
- **Inference** (load-bearing/supporting tiered prompt at α* = 0.20).
- **Baselines** table (4 attribution + 3 mechanism + 1 generality = 8 ablations; external = 4-9 baselines).
- **Pre-registered Class-B-rescue analysis** on the 77 gating examples.
- **Eval matrix** (31 runs / ~16 hr in Week 2).
- **Compute & Timeline** (30 GPU-h equivalent; Week 1 build & calibrate; Week 2 eval; Week 3 paper).
- **Failure Modes and Diagnostics** (F1-F9 above + fall-backs).
- **Novelty and Elegance Argument** (closest work table; exact difference; one-inequality summary).

(End of round-3 refinement.)
