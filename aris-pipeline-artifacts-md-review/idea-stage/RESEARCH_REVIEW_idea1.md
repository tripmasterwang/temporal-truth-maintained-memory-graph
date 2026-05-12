# Research Review — Adaptive E-Process Reader

**Date:** 2026-04-27
**Reviewer:** Codex GPT-5.4 xhigh (thread `019dcd12-189e-7c60-9090-f251a38d0748`)
**Verdict:** **PIVOT TO IDEA #5 (Drift-Calibrated Volatility Reranker)**
**Overall score: 4.1 / 10** (weighted)

## Scores

| Dimension | Score | Note |
|---|---:|---|
| Problem Fidelity | 8 | Anchor preserved; hits the right bottlenecks. |
| **Method Correctness** | **3** | **FATAL.** E-process fusion claim is mathematically broken. |
| **Empirical Leverage** | **4** | Pointed at the wrong bottleneck (writer-side errors dominate, not reader). |
| Novelty (post-MiCP) | 4 | MiCP collision is *substantive*, not cosmetic. |
| Feasibility (3 wk) | 4 | Required theoretical fixes are not 3-week work. |
| Validation Focus | 6 | Decisive experiments are well-defined. |
| Venue Readiness | 3 | Not ready for NeurIPS / ICML main as currently framed. |
| Differentiation from MiCP | 3 | Only substantive axis (multi-substrate temporal conflict) is exactly where the math is weakest. |

## The four critical findings

### 1. Method math is broken (FATAL)

> For candidate `a`, a valid sequential story needs an e-process `E_t(a)` with `E_0=1` and `E[E_t(a) | H_0^a] ≤ 1` under the null "`a` is not the correct answer." The only safe generic construction is `E_t(a) = ∏ G_u(a)` where each batch factor satisfies `E[G_u | F_{u-1}, H_0^a] ≤ 1` under one shared global filtration.

**Two breakages:**

1. **Multi-substrate fusion**. Multiplying score-based "likelihood-ratio surrogates" from 4 substrates is *not* valid unless we model the joint null OR prove conditional factorization. Arbitrary correlated substrate noise (and we know substrates *are* correlated — they all retrieve from the same conversation) kills the Ville-inequality guarantee. The only safe alternative is a **convex combination** of per-substrate e-values — but that's "much weaker" and not novel.

2. **e-BH / FDR is the wrong error target**. FDR controls the *expected fraction of false discoveries in a set*, not `P(the one returned answer is wrong)`. For single-answer QA we need **FWER / selective coverage / prediction-set validity**. If we switch to Bonferroni/FWER over *m* candidates, the threshold becomes ~`m/α` → uselessly conservative.

### 2. "Universal scope" claim collapses on free-form QA (FATAL)

> Single-slot questions have a manageable candidate set. Lists, aggregation, recommendation, and free-form do not. Once candidates are generated *adaptively* from retrieved evidence, the hypothesis family is **random and data-dependent**. Then the clean multiple-testing story is gone unless you add another layer of sequential family management. That is not a 3-week refinement; that is a new theory paper.

So the very thing that supposedly defended against β's "narrow specialist" failure (universal applicability) ironically requires a heavier theoretical apparatus we don't have.

### 3. MiCP collision is substantive, not cosmetic

> As of April 1 2026, MiCP already claims adaptive multi-turn stopping with end-to-end coverage guarantees on adaptive RAG and ReAct. Your "MiCP is static / not multi-turn-valid" angle does not survive contact with the paper. "Not on memory benchmarks" is cosmetic. The only substantive differentiator left is **heterogeneous multi-substrate temporal conflict handling** — and that is exactly the part where your math is currently weakest.

### 4. Pointed at the wrong bottleneck

> Your own summary says writer extraction misses cap LongMemEval-S around `~70%`. If more than half the errors are writer-side, a smarter stopping rule is **lipstick**.

**Frontier moved further** since our cut-off:
- SmartSearch (2603.15599) reports **93.5 LoCoMo + 88.4 LongMemEval-S** at ~650 ms CPU.
- EverMemOS (2601.02163) reports **93.05 LoCoMo + 83.00 LongMemEval**.
- The frontier is now "ranking-and-compilation", not "stopping".

### 5. The TTMG moat dilemma

> If this works without TTMG, the moat is fake. If it only works because of supersede edges, the generality claim is fake. You do not get both.

## What the reviewer recommends instead

**PIVOT TO IDEA #5: Drift-Calibrated Volatility Reranker.**

> Closer to the observed bottleneck (stale facts), easier to validate in 3 weeks, still lets you reuse the TTMG substrate.

## Mandatory action items before refinement

1. **Drop the per-candidate FDR-safe single-answer claim**. Replace with either a prediction-set / selective-coverage claim OR a much narrower fixed-candidate single-slot setting.
2. **Prove one valid batch e-factor on paper before coding.** Either calibrate one *joint verifier* over the full multi-substrate feature vector, OR use a *convex combination* of per-substrate e-values. No product fusion without a joint null model.
3. **Run an oracle error decomposition first.** `writer-correct vs writer-wrong`, and separately `retrieval-insufficient vs answer-synthesis-wrong`. **If writer-wrong dominates, kill the idea immediately.**
4. **Run a minimal Pareto study** against `raw_turn_fallback`, a MiCP-style conformal stopping baseline, and a strong ranking baseline. If the proposal does not dominate on either `risk-coverage` or `accuracy-latency`, the guarantee is not buying enough.
5. **Decide the moat.** If the e-process truly needs TTMG, write the paper as TTMG-coupled. If it works without, drop the moat claim.

## Two falsification experiments (smallest decisive)

### Falsification #1 — math validity
Fix a finite candidate set per query; remove the gold answer; keep only decoys of the same answer type; run the exact stopping rule with all 4 substrate signals. If the system outputs any decoy above the claimed `α` more often than allowed on a held-out split → **e-process story dead**.

### Falsification #2 — wrong bottleneck
Take 200 stratified benchmark queries; oracle-label whether writer extracted the needed fact correctly; compare proposed reader vs current `raw_turn_fallback` reader **only on the writer-correct slice**. If gain is < 3 pp OR writer-wrong cases dominate total errors → **kill the idea**.

## Honest read for the project

The brainstorm Codex put Idea #1 at the top because it satisfied the *meta-constraints* (universality, has-a-tool-from-outside, fits white-space). The review Codex now points out that satisfying meta-constraints with broken math doesn't make a paper. This is the same failure mode that produced two 9.15/10 internal scores followed by 0/15 actual smoke results — *internal scoring rubrics keep rewarding superficially-clean ideas that the field would reject*.

The reviewer's pivot recommendation (Idea #5: Drift-Calibrated Volatility Reranker) is *narrower in ambition* but **directly aimed at the dominant empirical failure mode (stale-fact reliance, FAMA penalty 18-30 pp)**, easier to defend, and reuses the same substrate. **It accepts that "ranking is the bottleneck" per Diagnosing-Memory.**

But before pivoting blindly, we should:
- Re-novelty-check Idea #5 (it has its own HC-#7 risk: "just recency weighting with better branding").
- Get one more reviewer pass on Idea #5 specifically (different angle).
- OR consider whether to escalate — maybe none of the 10 ideas survives this kind of scrutiny and the brief itself needs revising.
