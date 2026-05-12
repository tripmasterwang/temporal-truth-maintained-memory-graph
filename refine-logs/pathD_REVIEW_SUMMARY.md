# Review Summary

**Problem.** TTMG underperforms Flat hybrid-RAG overall on LongMemEval-S (-7 pp at N=500), regresses -13.4 pp on cross-domain LoCoMo, and triggered idea.md's own pre-registered failure clause; meanwhile the linker mechanism is causally validated by ablation; the conceptual gap (no surveyed 2025–2026 competitor implements explicit `valid_from/valid_to` + supersede/contradict edges with abstain-on-conflict) is real but novelty must now be argued vs SimpleMem's 2026 intent-aware retrieval + symbolic temporal layer.

**Initial Approach (Path D).** Reframe TTMG as a TR/KU/abstention SPECIALIST, build a small controlled supersede sub-benchmark, add multi-seed + 4 missing ablations + LoCoMo-honest reporting, defend novelty vs SimpleMem (2026 frontier), reuse existing `ttmg/` code.

**Date.** 2026-04-26
**Rounds.** 4 / 4
**Final Score.** **9.15 / 10**
**Final Verdict.** **READY**

## Problem Anchor (verbatim, unchanged across all 4 rounds)

- **Bottom-line problem.** When an LLM agent accumulates conversational memory across many sessions, statements about facts (preferences, schedules, plans, attributes) get *updated, contradicted, and superseded* over time. Current agent-memory systems organize memory semantically or hierarchically, but **none explicitly maintains *which fact is true at each point in time***. The result: under knowledge updates and temporal-validity questions, retrievers surface stale facts; under outright contradictions, readers fabricate confident answers instead of abstaining.
- **Must-solve bottleneck.** (i) record `valid_from / valid_to` and an explicit `supersede / contradict` relation between claims; (ii) at read time, return the largest temporally-consistent claim subset that matches the query; (iii) abstain when residual contradiction cannot be resolved.
- **Non-goals.** Not general memory; not token-eff wins; not a static KG; not a slot-in layer (Path A, deferred); not a benchmark-creation paper.
- **Constraints.** 1–2 RTX-4090; MAAS API; reuse `ttmg/{schema, writer_temporal, conflict_linker, truth_retriever, system}.py`; 2–3 weeks; NeurIPS / ICML main track.

## Round-by-Round Resolution Log

| Round | Main Reviewer Concerns | What This Round Simplified / Modernized | Solved? | Remaining Risk |
|-------|------------------------|------------------------------------------|---------|----------------|
| 1 | Truth-maintenance operator underspecified (`subject,predicate` insufficient; "greedy MCS" misnomer; abstain inconsistent). Validation matrix too busy (5 ablations × 2 backbones bloat). Still summarizable as "wins on constructed slice + sub-axes, no overall win" — hard main-track sell. | Added `claim_key` + `slot_type ∈ {single_valued, multi_valued}` to schema; replaced greedy MCS with **exact MWIS on top-k**; added **applicability gate** (single-valued + claim_key + truth-of-fact) routing non-applicable queries to Flat; dropped `support` from decision policy; replaced scalar confidence with **3-call agreement hardness**; collapsed validation to 4 ablations + 1 primary backbone (secondary → final headline only); split slice into 2 pre-declared strata (latest-state KU + as-of-time TR); deterministic labels + human audit as ground truth (no LLM-cleaning). | Yes — operator now slot-scoped specialist with explicit applicability boundary. | Decision rule still claim-level; key-alignment interface not yet audited. |
| 2 | Unique-survivor at *claim* level not *value* level (paraphrase claims trigger spurious abstention). `claim_key` alignment between writer and parser not guaranteed (silent failure mode). Applicability gate honest but reviewers will test for selective-scoring. Pseudo-novelty risk if MWIS itself is presented as the contribution. | Added `object_norm` to schema and **value-level decision rule** (answer iff |{c.object_norm : c ∈ MWIS}| == 1, else abstain). Made `claim_key = (entity_id, slot_name)` with **deterministic post-processor** (lowercase + lemma + alias map ≤200 entries) applied after writer and parser; new file `ttmg/canonicalize.py`. Added **intrinsic gates**: writer-key-precision + parser-key-recall ≥ 0.85; router precision + recall ≥ 0.85 on 100-q audit; **router locked + git-hashed end-of-Wk-1**; **composed end-to-end accuracy** reported on every benchmark. Reframed novelty as *slot-scoped truth-maintenance semantics*, MWIS is solver, not contribution. Dropped `support` label entirely. Moved secondary-backbone to appendix. | Yes — value-level resolution + canonical-key alignment + audited locked router + composed reporting all in place. | Single-MWIS-tie loophole (heuristic weights can mask conflicts); hybrid retrieval still on applicable path is now legacy baggage; value-equivalence audit protocol not yet specified. |
| 3 | Single-MWIS rule has loophole — a chosen optimum may pick one value while another equally-optimal IS supports a different value. Hybrid retrieval on applicable path is redundant once canonical key is audited. Object-norm audit needs crisp definition. | Replaced single-optimum rule with **all-optima MWIS** enumeration (k≤8 → ≤2⁸ subsets, microsecond-cheap); answer iff *every* maximum-weight independent set induces the same `object_norm`, else abstain. Replaced hybrid retrieval on applicable path with **canonical-key fetch** + time filter; hybrid kept as logged fallback. Specified value-equivalence audit as **author-defined equivalence classes** released as JSON. Failure clause expanded to fire on any audit miss. `writer_confidence` weighting de-emphasized in main story. | Yes — adversarially-correct abstention (no contradiction can be silently masked); canonical-key path eliminates retrieval noise; reproducible value audit. | Polish only (weights wording, candidate-count histogram, fallback framing). |
| 4 | (READY round) | (Polish only) Tighten weight wording (semantics are not weight-free, but weights no longer mask conflicts); add candidate-count histogram; merge intrinsic audits into one compact suite table; keep hybrid fallback as engineering backstop. | Yes — no blocking issues. | None blocking; only narrative polish for the writeup. |

## Overall Evolution

- **Method became more concrete.** From "claim graph + edges + filter + abstain" to a precise operator: `answer(q) = if applicable(q) then ( unique-value(⋃ Opts(canonical-fetch(q))) | ⊥ ) else Flat(q)`, with 3 schema fields, 1 linker (3-call agreement), 1 canonicalizer (deterministic), 1 all-optima MWIS enumerator (k≤8), 1 applicability router.
- **Dominant contribution became more focused.** Started as "general-memory specialist for KU/TR/abstention"; became "slot-scoped truth-maintenance semantics for single-valued, update-bearing memory slots, with audited locked applicability gate and adversarially-correct all-optima value-level abstention".
- **Unnecessary complexity removed.** `support` label dropped. Hybrid retrieval moved to fallback-only on applicable path. Cross-product 2-backbone × 5-ablation matrix collapsed to 1-backbone × 4-ablation main + 1-backbone-1-seed appendix. Greedy MCS misnomer replaced with exact MWIS.
- **Frontier leverage validated as appropriate.** No new training, no agent simulator, no multi-modal extension. LLM-as-structurer (writer), LLM-as-judge (linker, with 3-call self-consistency), LLM-as-router (parser+applicability) — exactly the SimpleMem-2026 / LightMem-2026 division of labour, applied to truth-of-fact instead of intent.
- **Drift avoided.** Reviewer flagged drift = NONE in all 4 rounds. The narrowing to single-valued update slots was deliberate and reviewer-validated, not drift.

## Final Status

- **Anchor status.** Preserved across all 4 rounds. Truth maintenance — which fact holds at time τ, which one supersedes which, when to abstain — for agent memory.
- **Focus status.** Tight. One semantic contribution; one supporting controlled slice; one applicability gate; one decision rule.
- **Modernity status.** Appropriately frontier-aware. FM-era primitives in their natural roles (structurer / judge / router) without forced trendy add-ons. Intrinsic-audit suite is the field's emerging standard for LLM-pipeline papers.
- **Strongest parts of final method.**
  - All-optima MWIS rule is *adversarially correct*: cannot answer when any consistent reading of the conflict graph disagrees on the value.
  - Applicability gate as a first-class part of the contribution (locked + audited + composed end-to-end reported) preempts the "you don't beat Flat overall" reviewer attack.
  - Pre-registered intrinsic gates (linker F1, Brier, key-precision/recall, router-precision/recall, value-equivalence, fallback rate) all run *before* test-time and gate the entire pipeline.
- **Remaining weaknesses (polish only, all from round-4 review).**
  - Wording: "weight-free" is overstating; weights still define the optimal-set family.
  - Need a candidate-count histogram per applicable query to operationally justify exact enumeration.
  - Hybrid retrieval fallback should be framed as engineering backstop, not part of the core contribution.
