# Review Summary — CalLB Refinement (4 rounds, READY at 9.0)

**Reviewer:** GPT-5.4 xhigh via Codex MCP
**Thread ID:** `019dcdd2-8a56-7c51-8017-9ac14ad3038e`
**Date range:** 2026-04-27 (single-day refinement)
**Final verdict:** **READY** (9.0/10) — proceed to `/experiment-plan` handoff.

## Score trajectory

| Round | OVERALL | Verdict | What broke / What landed |
|---|---:|---|---|
| **R1** | **6.7** | RETHINK | The original "per-item conformal coverage" claim `Pr[Y=1\|S≥τ] ≥ 1−α` is the **wrong direction** of the split-CP recipe (which gives `Pr[S≥τ\|Y=1] ≥ 1−α`). Anchor is correct, but the formal object is broken. |
| **R2** | **7.6** | REVISE | Anchor preserved + labels redefined (LB/S/D) + attribution baselines added + FAMA downgraded + TTMG-coupling honest. NEW math bug: distractor-fraction risk `#D / #tier` is **NOT monotone in λ** (counterexample at low vs high λ). |
| **R3** | **8.5** | REVISE | Switched to clean-set indicator risk `1[∃ D in L]` — monotone ✓. Hoeffding+grid+union-bound valid. Two remaining: (i) cleanliness ≠ utility (need non-vacuity metrics); (ii) need acceptance go/no-go on `no_CRC`. |
| **R4** | **9.0** | **READY** ✓ | All 3 R3 fixes landed: non-vacuity metrics + Clopper-Pearson UCB + Path (A)/(B) acceptance logic. Reviewer's only operational caveat: **honor the pre-committed venue logic** if neither Path lands. |

## Per-dimension trajectory

| Dimension | R1 | R2 | R3 | R4 | Total Δ |
|---|---:|---:|---:|---:|---:|
| Problem Fidelity | 8 | 8.5 | 9 | **9.5** | +1.5 |
| Method Specificity | 7.5 | 8.5 | 9 | **9.0** | +1.5 |
| Contribution Quality | 5.5 | 6.5 | 8 | **9.0** | +3.5 |
| Frontier Leverage | 7 | 8 | 8.5 | **8.8** | +1.8 |
| Feasibility | 6 | 7 | 8.5 | **8.8** | +2.8 |
| Validation Focus | 5.5 | 7.5 | 8 | **9.0** | +3.5 |
| Venue Readiness | 5.5 | 7 | 8 | **8.8** | +3.3 |

**Largest gains:** Contribution Quality (+3.5), Validation Focus (+3.5), Venue Readiness (+3.3). All gains came from formal-object corrections + supervision-validation hardening + acceptance-logic pre-commitment, NOT from method-feature additions.

## Anchored problem (immutable across all 4 rounds)

> When an LLM agent answers from accumulated long-conversation memory, the *reader* commits two systematic errors that no current 2026 system addresses with a calibrated mechanism: (i) **over-specification** after correct grounding (47 % of Path D's wrong answers); (ii) **wrong-content retrieval** (41 % of wrong answers). 88.2 % of Path D's wrong answers on LongMemEval-S are read-side actionable per gating decomposition (`results/gating_decomposition.json`).

**Reviewer note (R2):** *"Important nuance: do not rethink the problem anchor. The anchor is finally right. Rethink the formal object and the supervision target."* This held across R3 and R4.

## Final method (one-line)

> A learned MLP reranker over 13 substrate-fusion features (5 portable + 3 robustness + 5 TTMG-specific) producing a per-item reliability score, with a single threshold `λ̂_α` calibrated via **Clopper-Pearson Conformal Risk Control on the clean-set indicator** so that with probability ≥ 1−α, the reader-visible **load-bearing tier** contains no distractor — addressing both Class B (multi-substrate signal fusion) and Class C (probabilistic distractor exclusion).

## Mandatory baselines (committed)

External: Path D `ttmg`, MiCP-on-Path-D, Stop-RAG-on-Path-D, Flat hybrid-RAG, A-Mem, Mem0, LightMem, EverMemOS (appendix), SmartSearch (LoCoMo).

Attribution: `prompt-only`, `rerank-only`, `agreement-heuristic-only`, **`no_CRC`** (= same MLP scores + dev-tuned fixed threshold; this is the calibration go/no-go).

Mechanism: `no_cross_substrate_agreement`, `no_drift_features`, `no_robustness_features`.

Generality: `portable_features_only`.

## Pre-committed acceptance logic for main-track

CalLB → main-track iff:
- **(A)** ≥ 1 pp B+C-prone slice lift over `no_CRC` w/ bootstrapped p<0.05 on at least one of {LongMemEval-S, Memora-FAMA}, **OR**
- **(B)** Cross-dataset CRC threshold transfer (CalLB holds within α + 0.06 cross-corpus; `no_CRC` violates by > 0.10).

Else: **Option F1** (workshop) or **Option F2** (drop formal-guarantee thesis; main-track only if B+C lift ≥ 5 pp).

## Compute and timeline

- ≈ **30 GPU-hour-equivalents** + 8.3 hr MAAS labelling + 1 hr author audit.
- **Week 1**: build + label + train + Clopper-Pearson CRC + lock.
- **Week 2**: 31-run eval matrix (~16 hr).
- **Week 3**: paper writing.
- Total: 3 weeks.

## Reviewer's final operational requirement

> "**Honor the pre-committed venue logic.** If neither Path A nor Path B lands, do not rationalize it into a main-track theory paper after the fact."

## Next step

Invoke `/experiment-plan "CalLB"` to formalize the Week-1 build + Week-2 eval matrix into a runnable execution roadmap with explicit sequencing, compute budget allocation, and tracker.
