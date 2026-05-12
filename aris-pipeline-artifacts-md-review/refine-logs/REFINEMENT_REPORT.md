# Refinement Report — CalLB (4 rounds, 6.7 → 9.0)

This is the meta-report on what changed each round and why. Use this to understand the evolution if returning to the project months later.

## Round 0 → Round 1

**Original proposal (round-0)**: "CalRR — Calibrated Hybrid Reranker for Long-Conversation Memory with Per-Item Rank-Quality Coverage". Per-item split-conformal calibration on a learned MLP reranker, claiming coverage `Pr[item is gold-relevant | reliability ≥ τ̂_α] ≥ 1 − α`.

**Round-1 review (6.7, RETHINK)**: Reviewer flagged the formal object as **mathematically broken**. The split-CP recipe (`τ̂_α = ⌈(n_cal+1)(1−α)⌉/n_cal -quantile of {s_i : y_i=1}`) gives `Pr[S ≥ τ | Y=1] ≥ 1−α` (recall on positives), NOT `Pr[Y=1 | S ≥ τ] ≥ 1−α` (precision on retained). These are different objects. Reviewer's salvage: *"Load-bearing evidence selection for long-conversation memory, with calibrated contamination control of the reader-visible evidence set."*

**Round-1 refinement (CalRR → CalLB)**: 6 changes:
1. Formal object: per-item conformal coverage → **Conformal Risk Control on contamination of the load-bearing tier** (`E_q[#D / #tier] ≤ α`).
2. Label: binary `relevant` → 3-tier `LB / S / D`.
3. Attribution baselines: `prompt-only`, `rerank-only`, `agreement-heuristic-only` made mandatory.
4. FAMA: dominance claim downgraded to parity (no Memora pilot).
5. Generality: dropped substrate-agnostic claim; added `portable_features_only` ablation.
6. Cost realism: 8K labels → 10K stratified subsample (60K candidates total).

## Round 1 → Round 2

**Round-2 review (7.6, REVISE)**: Anchor + labels + attribution + FAMA framing all correct. **NEW math bug**: the contamination-fraction risk `R(λ; q) = #D / #tier` is **not monotone in λ**. Counterexample: at low λ, retained set has 1 D + 9 good = risk 0.1; at high λ, only the D remains = risk 1.0. Vanilla CRC threshold-search needs monotonicity.

**Round-2 refinement**: 5 changes:
1. **Risk function fix**: `#D/#tier` → `1[∃ D in L_λ(q)]` (clean-set indicator). Monotone ✓; matches "1 distractor poisons answer" harm model; Hoeffding + 100-pt grid + δ/m union bound is valid.
2. Label validation hardened: κ ≥ 0.7 (3-class) + κ ≥ 0.75 (D-vs-non-D binary collapse) + 30 % borderline oversampling + 3×3 confusion matrix + class-conditional precision/recall for D.
3. `no_CRC` redefined: same MLP scores + dev-tuned fixed threshold (NOT random scores).
4. **Robustness features added** (3 new): `max_substrate_score`, `singleton_raw_turn_hit`, `entity_overlap` — directly to rescue low-agreement Class-B examples (per L9 fragility on agreement).
5. Eval matrix shrunk: 3 seeds for core; 1 seed for ablations + secondary. 31 runs total.

Plus: pre-registered Class-B-rescue analysis on the 77 gating examples committed in advance (prevents post-hoc narrative shaping).

## Round 2 → Round 3

**Round-3 review (8.5, REVISE)**: Math now valid (clean-set indicator monotone ✓). Two remaining vulnerabilities: (i) **cleanliness ≠ utility** — guarantee says nothing about whether L is non-empty or contains LB; (ii) **CRC vs fixed threshold go/no-go** — fallback "formal-guarantee-only" paper not strong main-track.

**Round-3 refinement**: 3 bounded fixes:
1. **Non-vacuity / utility metrics on L** (mandatory reporting): `non_empty_fraction(L) ≥ 0.85`, `mean_size(L) ∈ [2, 5]`, `LB_recall(L) ≥ 0.75`, plus descriptive `LB_precision` and mean distractor fraction. F1' failure clause triggers Option F2 if vacuous.
2. **Clopper-Pearson exact binomial UCB** replacing Hoeffding + Bernstein-fallback. Tightens slack at α=0.05 from 0.083 to 0.028; makes α=0.10 actionable. Theorem cleanly separates `1-δ` (cal split) from `1-α` (test queries).
3. **Explicit Path (A)/(B) acceptance logic** for main-track + Option F1 (workshop) / F2 (empirical-only with 5pp bar) fallback. Pre-committed; no post-hoc venue rationalization.

## Round 3 → Round 4

**Round-4 review (9.0, READY ✓)**: All 3 R3 fixes landed cleanly. Reviewer confirms:
- Clopper-Pearson + grid + union-bound valid; bound informative at α=0.20 and usable at α=0.10.
- Supervision-validation strong enough.
- 4 attribution baselines sufficient.
- Robustness features + pre-registered rescue analysis prevent overclaim.
- 31-run matrix realistic for one person.
- Novelty defensible *narrowly*: not new CRC theory, but a new clean-set risk object for reader-visible memory evidence selection.
- Path A/B acceptance logic correctly handles the fallback case.

**Operational requirement** (only caveat at READY): "honor the pre-committed venue logic. If neither Path A nor Path B lands, do not rationalize it into a main-track theory paper after the fact."

No round-4 refinement needed; proceed to Phase 5.

## Why this trajectory worked

Three structural reasons the score climbed 6.7 → 9.0 cleanly:

1. **The anchor was right by R1.** The 88.2 % B+C gating evidence (`results/gating_decomposition.json`) gave an empirical commitment that **no reviewer could attack**. Each round, the reviewer explicitly said "do not rethink the problem anchor". This bounded the rework.

2. **Each math correction was structural, not patchy.** R1 fix (per-item coverage → CRC on contamination) was a category-level switch. R2 fix (fraction → indicator) was monotonicity-driven. R3 fix (Clopper-Pearson) was tightness-driven. None were band-aids; each rebuilt the formal object.

3. **Pre-commitments compounded.** R2 added pre-registered Class-B-rescue analysis. R3 added Path (A)/(B) acceptance logic. Both committed-in-advance protocols make the paper bulletproof to post-hoc narrative shaping — a thing reviewers consistently penalize.

## What was NOT changed across the 4 rounds

- Problem Anchor (verbatim across R0-R4).
- Reuse of Path D `ttmg/` substrate (unchanged).
- Frozen reader (`deepseek-v3.2`, no fine-tune).
- 3-tier label semantics (LB / S / D — added in R1, refined in R2 validation, unchanged in R3-R4).
- Single small MLP as the only learned component.
- 1–2 RTX-4090 + MAAS API + 3-week budget constraints.
- LongMemEval-S as primary benchmark; Memora secondary; LoCoMo parity.

## Files produced

| File | Purpose |
|---|---|
| `round-0-initial-proposal.md` | Original CalRR proposal (per-item coverage object) |
| `round-1-review.md` | R1 critique (6.7, RETHINK) — found broken math direction |
| `round-1-refinement.md` | CalRR → CalLB rewrite (CRC contamination + 3-tier labels + attribution baselines + FAMA downgrade) |
| `round-2-review.md` | R2 critique (7.6, REVISE) — found non-monotone risk |
| `round-2-refinement.md` | Clean-set indicator + Clopper-Pearson + robustness features + pre-registered rescue + shrunk eval matrix |
| `round-3-review.md` | R3 critique (8.5, REVISE) — cleanliness ≠ utility + CRC go/no-go |
| `round-3-refinement.md` | Non-vacuity metrics + Clopper-Pearson theorem + Path (A)/(B) + Options F1/F2 |
| `round-4-review.md` | R4 confirmation (9.0, READY ✓) |
| `score-history.md` | Per-round score table + per-dimension trajectory |
| `FINAL_PROPOSAL.md` | Consolidated final proposal (this is what `/experiment-plan` reads) |
| `REVIEW_SUMMARY.md` | Top-level review summary |
| `REFINEMENT_REPORT.md` | This file |
| `REFINE_STATE.json` | `{phase: done, status: completed}` after this report |

## Next step

```
/experiment-plan "CalLB"
```

Read `FINAL_PROPOSAL.md` for the full method spec; `REVIEW_SUMMARY.md` for the score trajectory; this file for the meta-evolution.
