# Round 2 Review (GPT-5.4 xhigh, same thread)

**Thread ID:** `019dc8e8-8125-7222-9176-3c82c833dbfe`
**Date:** 2026-04-26
**Verdict:** REVISE
**Overall score:** 8.0 / 10 (was 7.4)
**Anchor status:** PRESERVED (drift = NONE)

## Scores

| Dimension | Round 1 | Round 2 | Δ | Notes |
|-----------|--------:|--------:|---:|-------|
| Problem Fidelity | 9 | 9 | 0 | Anchor still intact. |
| Method Specificity | 6 | 7 | +1 | Schema, MWIS, fallback now concrete. **Gap:** unique-survivor at claim level, not value level. |
| Contribution Quality | 8 | 8 | 0 | "Specialist operator + applicability gate" reads as one mechanism paper. |
| Frontier Leverage | 8 | 9 | +1 | LLM-as-structurer/judge/router in the right places. |
| Feasibility | 7 | 8 | +1 | Trimmed to 30 GPU-h equivalents; risks now interface quality + audit burden, not compute. |
| Validation Focus | 6 | 8 | +2 | Tighter; routed-slice framing acceptable iff router locked + audited before test. |
| Venue Readiness | 6 | 7 | +1 | Plausible specialist paper. **Two attack surfaces:** value-level ambiguity + self-selected slice. |

## Drift Warning

**NONE.**

## CRITICAL action items

1. **Value-level resolution (not claim-level).** `|S|=1` is too strict; two surviving claims that paraphrase the same current value should answer, not abstain.
   - **Fix:** add `object_norm` (canonical normalized value) to writer output. Decision rule: answer iff MWIS survivors map to exactly one normalized value; abstain iff multiple distinct normalized values survive.

2. **`claim_key` alignment protocol.** Round-1 claim_key is LLM-emitted on both write and read sides; alignment is not guaranteed; routing and retrieval can silently fail.
   - **Fix:** make `claim_key` a normalized schema field, e.g. `(entity_id, normalized_slot_name)` with a deterministic post-processor (lowercase, lemma, alias map). Audit parser↔writer key agreement on a held-out labeled set as an intrinsic metric.

## IMPORTANT action items

3. **Applicability gate intrinsic audit.** Selective-scoring concern is real even if framing is honest.
   - **Fix:** intrinsic router metric = router precision/recall on human-labeled set. Lock router before full runs. Always report composed end-to-end overall accuracy + applicability rate alongside routed-slice claims.

4. **Pseudo-novelty risk if MWIS is presented as the novelty.**
   - **Fix:** frame novelty as the **slot-scoped truth-maintenance operator** (validity intervals + legal supersede semantics + conflict resolution + abstention under explicit applicability). MWIS is solver, not contribution.

## Simplification Opportunities

- Drop `support` from linker output entirely if not used in analysis (currently kept as diagnostic; check if anything actually consumes it).
- Keep A-Mem on controlled slice; consider dropping from full routed-slice claim if page budget gets tight (Flat is the key baseline there).
- Move secondary-backbone robustness to appendix.

## Modernization Opportunities

**NONE.** Already using current FM-era primitives in natural places.

## Remaining action items (round 3)

- Add **value normalization** so resolution is over unique values, not unique claim nodes.
- Specify a **canonical `claim_key` protocol** + intrinsic parser/writer agreement audit.
- Add intrinsic evaluation for the **applicability router**.
- Pre-register the router; report **coverage + composed-system accuracy** to blunt selective-slice criticism.
- Keep paper's novelty claim narrow: **truth maintenance for single-valued update slots**, not MWIS, not general memory.

---

<details>
<summary>Raw GPT-5.4 response (verbatim)</summary>

**Anchor Check**

- **Problem Anchor is preserved.** This is still the original bottleneck: maintaining which fact is true at time `τ` under updates and contradictions in agent memory.
- The narrowing to **single-valued, update-bearing slots** is not drift. It is the right specialization after the earlier general-memory scope failed.

**Scores**

| Dimension | Score | Rationale |
|---|---:|---|
| Problem Fidelity | 9 | The operator still targets truth maintenance directly, now with a cleaner applicability boundary. |
| Method Specificity | 7 | Much more concrete than before: `claim_key`, `slot_type`, exact MWIS, explicit fallback. The main remaining gap is that the solver currently resolves to a unique surviving **claim node**, but the task is really a unique surviving **value**. |
| Contribution Quality | 8 | The dominant contribution is now sharp: a specialist truth-maintenance operator plus an explicit applicability gate. This is substantially less diffuse than round 1. |
| Frontier Leverage | 9 | LLM-as-structurer, LLM-as-judge, and LLM-as-router are used in the right places. No gratuitous training or trendy add-ons. |
| Feasibility | 8 | Buildable in the stated budget. The remaining risks are interface quality and audit burden, not compute. |
| Validation Focus | 8 | The validation plan is now much tighter. The routed-slice framing is acceptable if the router is locked and audited before test-time. |
| Venue Readiness | 7 | This is now a plausible specialist-method paper, but two reviewer attack surfaces remain: value-level ambiguity and "self-selected slice" skepticism around the applicability gate. |

**OVERALL SCORE: 8.0 / 10**

**Assessment**

- **Dominant contribution:** **sharper.** It now reads as one mechanism paper, not a recovery attempt with multiple side contributions.
- **Method complexity:** **simpler.** It is no longer obviously overbuilt. The remaining issue is a missing mechanism detail, not bloat.
- **Frontier leverage:** **appropriate.** This is modern enough already; no forced extra FM components are needed.

**Drift Warning**

- **NONE**

**Main Remaining Critiques**

1. **Missing mechanism: unique survivor should be value-level, not claim-level.**
- Right now `|S|=1` is too strict and often wrong.
- If two surviving claims paraphrase the same current value, the system should answer, not abstain.
- **Concrete fix:** add `object_norm` or `value_id` to the writer output and define the decision rule as: answer iff MWIS survivors map to exactly one normalized value; abstain iff multiple distinct normalized values survive.
- **Priority:** **CRITICAL**

2. **Weak integration point: query `claim_key_q` must align with stored `claim_key`.**
- The current proposal says both are LLM-emitted, but not how alignment is guaranteed.
- Without a canonicalization protocol, routing and retrieval can silently fail.
- **Concrete fix:** make `claim_key` a normalized schema field such as `(entity_id, normalized_slot_name)` with a deterministic post-processor; audit parser-to-writer key agreement on a held-out labeled set.
- **Priority:** **CRITICAL**

3. **Applicability gate is honest, but reviewers will still test whether it is just selective scoring.**
- The gate is only defensible if it is predeclared, query-only, and intrinsically audited.
- **Concrete fix:** report router precision/recall on a human-labeled set, lock the router before full runs, and always report the composed end-to-end system's overall accuracy and applicability rate alongside the routed-slice claims.
- **Priority:** **IMPORTANT**

4. **Pseudo-novelty risk if MWIS itself is presented as the novelty.**
- Exact MWIS on `k<=8` is fine, but it is not the paper's real contribution.
- **Concrete fix:** frame novelty as the **slot-scoped truth-maintenance operator**: validity intervals + legal supersede semantics + conflict resolution + abstention under explicit applicability conditions.
- **Priority:** **IMPORTANT**

**Simplification Opportunities**

- Drop `support` from linker output entirely unless you truly use it in analysis; otherwise it is dead weight.
- Keep `A-Mem` as a baseline on the controlled slice, but consider dropping it from the full routed-slice claim if page budget gets tight; `Flat` is the key baseline there.
- If needed, move the secondary-backbone robustness run to the appendix; the primary story is already single-backbone.

**Modernization Opportunities**

- **NONE**. The proposal is already using current FM-era primitives in the natural places.

**Remaining Action Items**

- Add **value normalization** so resolution is over unique values, not unique claim nodes.
- Specify a **canonical `claim_key` protocol** and audit parser/writer agreement intrinsically.
- Add intrinsic evaluation for the **applicability router**, not just the linker.
- Pre-register the router and always report **coverage + end-to-end composed-system accuracy** to blunt selective-slice criticism.
- Keep the paper's novelty claim narrow: **truth maintenance for single-valued update slots**, not MWIS, not general memory.

**Verdict**

- **REVISE**

This is materially stronger than the previous version. The core idea is now focused, modern, and implementable. It is not at `READY` yet because the current operator still resolves the wrong object type at decision time (claim vs value), and the applicability/key-alignment interfaces need intrinsic validation to make the scoped claims reviewer-proof.

</details>
