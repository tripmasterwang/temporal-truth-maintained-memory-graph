# Score History — CalRR refinement

| Round | Date | Overall | Verdict | Reviewer | Thread ID |
|---|---|---:|---|---|---|
| 0 (initial) | 2026-04-27 | — | (proposal only) | — | — |
| 1 (review) | 2026-04-27 | **6.7** | RETHINK | gpt-5.4 xhigh | `019dcdd2-8a56-7c51-8017-9ac14ad3038e` |
| 2 (review) | 2026-04-27 | **7.6** | REVISE | gpt-5.4 xhigh | (same thread) |
| 3 (review) | 2026-04-27 | **8.5** | REVISE | gpt-5.4 xhigh | (same thread) |
| 4 (review) | 2026-04-27 | **9.0** | **READY** ✓ | gpt-5.4 xhigh | (same thread) |

## Per-dimension trace

| Dimension | R1 | R2 | R3 | R4 | Total Δ |
|---|---:|---:|---:|---:|---:|
| Problem Fidelity | 8 | 8.5 | 9 | **9.5** | +1.5 |
| Method Specificity | 7.5 | 8.5 | 9 | **9.0** | +1.5 |
| Contribution Quality | 5.5 | 6.5 | 8 | **9.0** | +3.5 |
| Frontier Leverage | 7 | 8 | 8.5 | **8.8** | +1.8 |
| Feasibility | 6 | 7 | 8.5 | **8.8** | +2.8 |
| Validation Focus | 5.5 | 7.5 | 8 | **9.0** | +3.5 |
| Venue Readiness | 5.5 | 7 | 8 | **8.8** | +3.3 |

## Verdicts

- **R1 (RETHINK, 6.7).** Anchor is correct (88.2% B+C gating evidence). FATAL: stated split-CP guarantee `P(Y=1|S≥τ) ≥ 1−α` is wrong direction; the recipe gives `P(S≥τ|Y=1) ≥ 1−α`. Pivot the *formal object* (CRC on load-bearing contamination), the *label* (load-bearing/supporting/distractor), the *baselines* (prompt-only, rerank-only, heuristic-only), the *FAMA claim* (downgrade), the *generality claim* (TTMG-coupled honest framing).
- **R2 (REVISE, 7.6).** Anchor + labels + attribution + FAMA framing are now right. NEW math bug: the distractor-fraction risk `R(λ; q) = #D/#tier` is **not monotone in λ** (counterexample: at low λ 1D + 9 good = 0.1; at high λ only D remains = 1.0). Switch to `R(λ; q) = 1[∃ D in L_λ(q)]` which IS monotone and matches the "1 distractor poisons the answer" harm model. Other fixes: κ ≥ 0.7 + D-vs-non-D separately; redefine `no_CRC` = same scores + dev-tuned threshold; add singleton-raw-turn feature + pre-register Class-B-rescue analysis; shrink eval matrix to 3-seeds-on-core / 1-seed-on-ablation.
- **R3 (REVISE, 8.5).** Math now valid (clean-set indicator monotone ✓; Hoeffding+grid+union-bound valid given fixed grid). Two remaining review-facing vulnerabilities: (i) **cleanliness ≠ utility** — guarantee says nothing about whether L contains necessary LB evidence; need non-vacuity metrics (non-empty fraction, mean |L|, LB-recall of L); (ii) **CRC vs fixed threshold go/no-go** — fallback "formal-guarantee-only" paper is not strong main-track; need explicit acceptance logic (A) downstream lift OR (B) cross-dataset robustness over `no_CRC`. Also: replace Hoeffding with Clopper-Pearson exact binomial UCB; clean separation of `1-δ` (cal split) vs `1-α` (test queries).
- **R4 (READY, 9.0) ✓**. All 3 R3 fixes landed cleanly. Non-vacuity metrics committed (`non_empty ≥ 0.85`, `mean |L| ∈ [2,5]`, `LB_recall ≥ 0.75`). Clopper-Pearson UCB tightens slack at α=0.10 from 0.083 to 0.078 (actionable). Path (A)/(B) acceptance logic pre-committed with workshop-pivot fallback. Reviewer's only operational caveat: **honor the pre-committed venue logic** — if neither Path A nor Path B lands, do not rationalize it into a main-track theory paper after the fact. Proceed to `/experiment-plan`.
