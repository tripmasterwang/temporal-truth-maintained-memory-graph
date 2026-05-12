# Round-1 Review — CalRR (initial proposal)

**Reviewer:** GPT-5.4 xhigh via Codex MCP
**Thread ID:** `019dcdd2-8a56-7c51-8017-9ac14ad3038e`
**Date:** 2026-04-27
**Overall:** **6.7 / 10 — RETHINK**

> Important nuance: **do not rethink the problem anchor**. The anchor is finally right.
> Rethink the **formal object** and the **supervision target**. The current "per-item split
> conformal coverage" layer is not yet the right mechanism-level claim for that problem.

## Scores

| Dimension | Score | Note |
|---|---:|---|
| Problem Fidelity | 8 | Anchor is right; formal object is loosely tied to top-k answer failure. |
| Method Specificity | 7.5 | Implementation path concrete; gaps in label definition + calibration claim. |
| **Contribution Quality** | **5.5** | Per-item conformal coverage is *not* the right statistical object; may be incorrect as stated. |
| Frontier Leverage | 7 | Reasonable LLM-era usage; not a modernity issue, a target-mismatch issue. |
| Feasibility | 6 | Hidden risk: cal-set construction (label count, judge noise, boundary cases). |
| Validation Focus | 5.5 | FAMA dominance aspirational; ablations don't isolate calibration vs prompting. |
| Venue Readiness | 5.5 | Reviewers will attack the statistical guarantee + attribution story immediately. |

## Five most consequential revisions

### Rev-1 (FATAL math) — Replace the calibration claim with an answer-linked object

> Your described split-conformal recipe can at best support `P(S ≥ τ | Y=1) ≥ 1−α` if `τ` is taken from positive-score quantiles. The paper claims `P(Y=1 | S ≥ τ) ≥ 1−α`, which is a precision-style statement. **Those are not the same.**

Smallest non-drifting fix:
- **Option A** (formal): switch to **contamination / false-item control on the reader-visible load-bearing set** — e.g., `E[# distractor items in load-bearing tier] ≤ α · k` via Conformal Risk Control / e-test.
- **Option B** (empirical): drop the formal guarantee entirely, present the score as an empirically calibrated reliability estimate, main claim = answer lift.

### Rev-2 (Label semantics) — Redefine label from "relevant" → "load-bearing"

> Class C is not about relevance in the loose IR sense. It is about whether an item is safe to support answer content without inviting unsupported adjacent detail. A binary relevance label from an LLM judge collapses exactly the distinction you need.

Better target:
- `load-bearing` (item is necessary to support the gold answer)
- `supporting but non-load-bearing` (related but not necessary)
- `distractor / unsafe` (would mislead reader)

Then either binary selector for `load-bearing` or small ordinal model. Without this, you're distilling judge's vague relevance, not solving over-specification.

### Rev-3 (Attribution) — Mandatory baselines that test whether prompting, not calibration, is the real mechanism

These are **mandatory, not optional**:
- `prompt-only`: Path D's existing top-k, same reliability/load-bearing prompt structure, **no** reranker / calibration.
- `rerank-only`: CalRR ranking, but **no** load-bearing/supplementary prompt split.
- `agreement-heuristic-only`: no MLP, no calibration; just simple agreement-based ranking/threshold.

If `prompt-only` gets most of the lift → paper is not about calibration.
If `agreement-heuristic-only` matches the MLP → learned layer is unnecessary.

### Rev-4 (FAMA over-claim) — Downgrade Memora-FAMA dominance to primary lift on B/C slices

As written, "strictly dominates A-Mem / Mem0 / LightMem / EverMemOS on FAMA" reads aspirational. No Memora pilot, mechanism not obviously FAMA-optimized.

Make primary claim:
- Answer-quality improvement on the anchored B/C slices.
- Parity or modest gains on broader metrics.
- FAMA = secondary unless pilot evidence exists.

### Rev-5 (Generality vs moat) — Narrow the generality claim and audit cross-substrate agreement

Several features are TTMG-specific. "Portable to any substrate" claim is too broad.

- Either say this is a **TTMG-coupled read-side operator**.
- Or define a truly portable core feature set + stop selling temporal-graph features as universal.

Also: show empirically whether `cross_substrate_agreement` has independent signal beyond duplicated views of the same raw turns. If raw-turn and claim-graph are mostly collinear, the count feature is weaker than the proposal assumes.

## Lens-by-lens readout

- **L1.** Per-item conformal coverage is **not** meaningful for downstream answer quality. Doesn't compose into a top-k cleanliness guarantee, and the stated precision-style guarantee is **likely not what the split-conformal construction actually provides**.
- **L2.** Item-level labels have **weak construct validity for Class C**. Risks becoming "student mimics deepseek-v3.2 relevance".
- **L3.** Agreement is plausible but **fragile** — substrates aren't independent sources, "agreement" may mainly measure duplication/popularity. Need empirical evidence it specifically rescues Class B.
- **L4.** Memora-FAMA claim is **aspirational**. Downgrade unless pilot evidence exists.
- **L5.** Reader prompt change is **very likely doing real work**. Without `prompt-only` + `rerank-only`, can't claim contribution is calibration rather than prompt engineering.
- **L6.** Method is currently TTMG-coupled. **That is fine.** Claiming broad substrate generality on top of that is not.
- **L7.** Labeling-cost estimate looks **low**. Near-paraphrase boundary cases are exactly where judge noise will matter most.

## Reviewer's smallest salvage

> **"Load-bearing evidence selection for long-conversation memory, with calibrated contamination control of the reader-visible evidence set."**

Same substrate, mostly same features, same read-side bottleneck — but **fixes the object the paper is actually about**.

## Implications for round-2 refinement

1. **Reframe the formal object.** Use Conformal Risk Control (Angelopoulos 2022 — `arXiv:2208.02814`) on the *contamination* of the load-bearing tier: `E[# unsafe items in top-k_load] ≤ α · k`. This is a real risk-control statement that *does* compose into a property the reader cares about (the load-bearing set is mostly safe). Off-the-shelf CRC math, no joint-null issue.
2. **Redefine label.** Three-tier: `load-bearing` / `supporting` / `distractor`. LLM-judge prompt redesigned to ask "would removing this item from the context change the answer's correctness?" (load-bearing) vs "is this item topically relevant but unnecessary?" (supporting) vs "would including this item degrade the answer?" (distractor).
3. **Add attribution baselines.** `prompt-only`, `rerank-only`, `agreement-heuristic-only` are now in the table.
4. **Downgrade FAMA.** Headline claim = B/C slice lift on LongMemEval-S. FAMA = appendix / parity.
5. **Honest TTMG-coupling.** Drop the substrate-agnostic claim. Frame as "calibrated load-bearing selection over a temporal-graph memory substrate". Add a *portable subset* (semantic + lexical + agreement) ablation showing how much works without TTMG features — this is the right way to claim partial generality.
6. **Cost realism.** Re-estimate cal-set size: 2K queries × 30 candidates = 60K items. Subsample aggressively (e.g., 10K items) and document the sampling protocol.

These six revisions are the round-2 work plan.
