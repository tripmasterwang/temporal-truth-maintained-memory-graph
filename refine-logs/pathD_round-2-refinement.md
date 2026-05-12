# Round 2 Refinement

## Problem Anchor (verbatim from round 0)

- **Bottom-line problem.** When an LLM agent accumulates conversational memory across many sessions, statements about facts (preferences, schedules, plans, attributes) get *updated, contradicted, and superseded* over time. Current agent-memory systems organize memory semantically or hierarchically, but **none explicitly maintains *which fact is true at each point in time***. The result: under knowledge updates and temporal-validity questions, retrievers surface stale facts; under outright contradictions, readers fabricate confident answers instead of abstaining.
- **Must-solve bottleneck.** (i) record `valid_from / valid_to` and an explicit `supersede / contradict` relation between claims; (ii) at read time, return the largest temporally-consistent claim subset that matches the query; (iii) abstain when residual contradiction cannot be resolved.
- **Non-goals.** Not general memory replacement; not token-efficiency wins; not a static KG builder; not a slot-in conflict layer (Path A, deferred); not a benchmark-creation paper.
- **Constraints.** 1–2 RTX-4090; MAAS API; reuse `ttmg/{schema, writer_temporal, conflict_linker, truth_retriever, system}.py`; 2–3 weeks; NeurIPS / ICML main track.
- **Success condition.** (See round-1 restated success conditions; round 2 *adds* router-precision/recall + composed-end-to-end-accuracy as mandatory headline numbers.)

## Anchor Check

- **Original bottleneck.** Truth maintenance — which fact holds at time *τ*, which one supersedes which, when to abstain — for agent memory.
- **Why the revised method still addresses it.** Round-2 changes deepen the *resolution* level (value, not claim node) and lock the *interface* (canonical `claim_key`, audited router) without changing the operator's job. The bottleneck is unchanged; the operator is sharper.
- **Reviewer suggestions rejected as drift.** None. Reviewer drift = NONE; the round-2 critiques are all interface-precision issues (value normalization, key canonicalization, router-locking, novelty framing).

## Simplicity Check

- **Dominant contribution after revision.** A *slot-scoped truth-maintenance operator* — typed claim graph with canonical `(entity_id, slot_name)` keys, normalized values (`object_norm`), agreement-hard typed `{contradict, supersede}` edges, exact MWIS over the queried-slot conflict subgraph at *τ_q*, **abstain on multiple distinct surviving values** (not multiple surviving claim nodes), all gated by an *intrinsically audited and locked* applicability router that classifies each query as in-scope or routed-to-Flat.
- **Components removed or merged.**
  - `support` linker label **dropped entirely** (no consumers; reviewer flagged as dead weight).
  - Secondary-backbone robustness check moved to **appendix** (primary story is single-backbone; secondary is robustness, not headline).
  - Decision rule consolidated: not "MWIS unique node" but "MWIS unique normalized value over surviving nodes". One rule replaces two.
- **Reviewer suggestions rejected as unnecessary complexity.** None. Every round-2 critique was either a gap (value-level, key alignment) or a sharpening (router intrinsic audit, novelty framing).
- **Why the remaining mechanism is still the smallest adequate route.** Two new schema fields (`claim_key`, `object_norm`) and one type tag (`slot_type`) — all emitted by the same writer LLM call. One linker call (3-call agreement). One MWIS solver (exact, k≤8). One value-normalization map (deterministic post-processor over `object_norm`). One applicability router (same parser call as `τ_q`). No new module, no training, no architecture, no auxiliary head. The *novelty* is the slot-scoped truth-maintenance *semantics* (validity intervals + legal supersede + value-level abstention under explicit applicability), not the solver.

## Changes Made

### 1. Value-level resolution: add `object_norm` and abstain on multiple distinct values
- **Reviewer said (CRITICAL):** "`|S|=1` is too strict and often wrong. If two surviving claims paraphrase the same current value, the system should answer, not abstain. Add `object_norm` or `value_id`. Decision rule: answer iff MWIS survivors map to exactly one normalized value; abstain iff multiple distinct normalized values survive."
- **Action.** Extend `Claim` schema with `object_norm: str` (canonical normalized representation of the slot value, written by the writer LLM, e.g. `"hot"` for "she likes coffee piping hot"). Read policy becomes:
  ```
  S = exact_MWIS(cand, hard_edges, weights=hardness × writer_conf)
  values = { c.object_norm : c ∈ S }
  if |values| == 1: return reader(query, S, value=values[0])
  else:             return ABSTAIN(reason="multiple_distinct_values", values=values, S=S)
  ```
- **Reasoning.** Reviewer's diagnosis was exactly right. The prior rule mistook *paraphrase redundancy* for *contradiction*. Value-level resolution is the natural decision unit because the answer the reader emits is *a value*, not *a claim node*. Adding `object_norm` is a one-line writer-prompt change and uses the same LLM call.
- **Impact on core method.** The system stops over-abstaining when retrieved claims are paraphrases. The *contradiction* signal moves from "any two retained claims" to "two retained claims with distinct normalized values" — semantically correct.

### 2. Canonical `claim_key` protocol with deterministic post-processor and intrinsic alignment audit
- **Reviewer said (CRITICAL):** "Make `claim_key` a normalized schema field such as `(entity_id, normalized_slot_name)` with a deterministic post-processor; audit parser-to-writer key agreement on a held-out labeled set."
- **Action.** (a) `claim_key` is now a structured field: `(entity_id: str, slot_name: str)` with a *deterministic* post-processor:
  - `entity_id`: lowercased, lemmatized, canonical-alias-mapped (small static alias table for "user", "the user", "I", "me" → `user`; for proper nouns the writer LLM's first emission is registered in an alias map and reused).
  - `slot_name`: lowercased, lemmatized, canonical-alias-mapped against a small registry built incrementally from prior writer outputs (`preferred_temperature_for_coffee` ↔ `coffee_temperature_preference` ↔ `likes_coffee_temperature` collapse to `coffee_temperature_preference`).
  - The post-processor runs after both writer (write time) and parser (read time), so storage and query keys go through the same canonicalizer.
  (b) Intrinsic audit: on a 60-q dev split labeled by the author with ground-truth `(entity_id, slot_name)`, measure parser-key-recall (does the read-time parser emit a `claim_key` that *matches the writer-side claim's canonicalized key*?) and writer-key-precision (does the writer emit a `claim_key` that, after canonicalization, matches the author's labelled key?). Acceptance: both ≥ 0.85 before any test-time runs.
- **Reasoning.** Reviewer correctly identified the silent-failure mode. Without canonicalization, parser/writer disagreement is an unobservable error sink. The static-alias + lemma + lowercased-string approach is the cheapest defensible canonicalization and matches the field's "structured-extraction with rule-based post-processing" pattern (used in mem0, SimpleMem write paths).
- **Impact on core method.** Routing and retrieval are now *measurably* aligned. The applicability gate's "slot match" decision is grounded in a measurable interface, not in LLM-string equality.

### 3. Applicability router: predeclared, locked, intrinsically audited
- **Reviewer said (IMPORTANT):** "Pre-declared, query-only, intrinsically audited. Report router precision/recall on human-labeled set. Lock the router before full runs. Always report composed end-to-end overall accuracy and applicability rate alongside routed-slice claims."
- **Action.** (a) Router prompt + applicability-decision rules are *frozen* at end of Week 1 and committed to git with a hash; no test-time change. (b) Intrinsic router metric on a 100-q human-labeled set across LongMemEval-S and LoCoMo (50 from each): router-precision = #(query labelled in-scope ∧ router=in-scope) / #(router=in-scope); router-recall = #(query labelled in-scope ∧ router=in-scope) / #(query labelled in-scope). Acceptance: both ≥ 0.85; report both as headline numbers in the paper. (c) End-to-end results table reports, for each benchmark, three columns: applicability rate (router-coverage), routed-to-TTMG accuracy, *composed end-to-end accuracy* (TTMG on routed-in + Flat on routed-out). The composed accuracy is what a deployer would actually see.
- **Reasoning.** Reviewer's "selective-scoring" concern is a real reviewer attack surface. Pre-registration + intrinsic audit + composed-end-to-end reporting collectively make the framing reviewer-proof. The composed-end-to-end column also gives a practical "you would deploy this and get X" number that does not depend on accepting the routed-slice framing.
- **Impact on core method.** The applicability gate becomes a *measured component* of the contribution, not a hidden free parameter.

### 4. Novelty framing: the operator (semantics), not the solver (MWIS)
- **Reviewer said (IMPORTANT):** "Pseudo-novelty risk if MWIS itself is presented as the novelty. Frame novelty as the slot-scoped truth-maintenance operator: validity intervals + legal supersede semantics + conflict resolution + abstention under explicit applicability conditions."
- **Action.** Paper-level title and abstract (and round-2 thesis statement here) reframed: novelty = *slot-scoped truth-maintenance semantics*, of which the components are (i) `(claim_key, object_norm)` typed schema with `valid_from/valid_to`, (ii) legal-supersede rule (same `claim_key`, `slot_type==single_valued`, agreement-hardness ≥ 2/3), (iii) conflict resolution = exact MWIS at *τ_q* (a *means*, not the contribution), (iv) value-level abstention under explicit applicability gating. MWIS is named as the solver but never as the contribution.
- **Reasoning.** Reviewer's framing is more defensible: MWIS-on-k≤8 is well-known; the paper's contribution is the *type-level* and *semantic* design, not the solver. This also pre-empts the "you just used algorithm X" reviewer attack.
- **Impact on core method.** Mechanism unchanged; positioning sharper. The paper's "what is new" claim becomes summarisable in one phrase: *slot-scoped truth-maintenance semantics for agent memory*.

### 5. Drop `support` linker label entirely
- **Reviewer said (Simplification):** "Drop `support` from linker output entirely unless you truly use it in analysis; otherwise dead weight."
- **Action.** Linker output is now `{contradict, supersede, unrelated}` only. `unrelated` is the catch-all for "same `claim_key`, no temporal conflict, no contradiction" cases (which were previously labelled `support`). Existing `Edge.label` enum is reduced.
- **Reasoning.** No consumer for `support`; removing it shrinks the decision surface.
- **Impact on core method.** One fewer label to defend in the paper.

### 6. Move secondary-backbone robustness to appendix
- **Reviewer said (Simplification):** "Move the secondary-backbone robustness run to the appendix; the primary story is already single-backbone."
- **Action.** Main paper claims and ablations all on `deepseek-v3.2`. Appendix A.x reports {Flat, TTMG} on `Qwen3-30B-A3B-Instruct-2507` at seed=0 as a robustness check.
- **Reasoning.** Single-backbone main story is already well-bounded; the secondary is for "does this generalize" addendum.
- **Impact on core method.** Cleaner main paper; same total experiments.

## Revised Proposal

# Research Proposal: Slot-Scoped Truth-Maintenance Semantics for Agent Memory — A Specialist Operator with an Audited Applicability Gate

## Problem Anchor

(verbatim from round 0; see top of this document.)

## Updated Success Condition (round 2 = round 1 + intrinsic audits)

1. **Within the routed-to-TTMG slice of LongMemEval-S full N=500** (3 seeds, primary backbone `deepseek-v3.2`): TTMG ≥ Flat with paired McNemar p<0.05 in TTMG's favor on the combined TR + KU axis.
2. **On both controlled-slice strata** (`latest-state KU` ≈150q, `as-of-time TR` ≈100q): TTMG strictly dominates Flat and A-Mem (paired McNemar p<0.05 per stratum, no losing stratum), intrinsic linker `supersede`-F1 ≥ 0.7, hardness Brier ≤ 0.2, **value-level disagreement (intrinsic) on the dev set ≤ 15%** (i.e. when the system answers, the chosen value matches the human-audited canonical value at least 85% of the time).
3. **Abstention behavioural metric** on full n=30: TTMG correct-abstain rate strictly > Flat at fixed answer accuracy.
4. **Mechanism causality**: each of `no_validity`, `no_supersede`, `no_abstain`, `no_linker` produces a ≥1 pp drop on its targeted slice within the routed-to-TTMG slice.
5. **Cross-domain regression report**: LoCoMo applicability rate <15% (predicted); on routed-to-TTMG sub-slice TTMG behaves as predicted; composed end-to-end accuracy reported on the full LoCoMo set as the deployer-relevant headline.
6. **Intrinsic router audit (NEW round 2)**: router precision and recall ≥ 0.85 each on the 100-q human-labeled audit set, *measured before any test-time run* on the locked router prompt. Reported as headline numbers.
7. **Intrinsic key alignment audit (NEW round 2)**: parser-key-recall and writer-key-precision ≥ 0.85 each on the 60-q dev set, measured before test-time runs.
8. **Composed end-to-end accuracy reported alongside routed-slice claims** on every benchmark, so the deployer-relevant number is always visible.
9. **Failure clause** (now reflects intrinsic audits): the design fails if (a) controlled-slice TTMG > {Flat, A-Mem} at p<0.05 fails on either stratum, or (b) routed-to-TTMG slice on full LongMemEval-S does not show paired McNemar p<0.05 on TR-or-KU, or (c) intrinsic router or key-alignment audits fail to clear 0.85.

## Technical Gap

Same gap as round 0 (no surveyed competitor implements explicit truth maintenance with validity intervals + typed supersede/contradict edges + abstain-on-conflict). Round-2 framing makes the claim sharper: the contribution is *semantic* (the operator's type-level design), not algorithmic (MWIS).

## Method Thesis

- **One-sentence thesis (round 2).** *For single-valued, update-bearing memory slots, the answer to "what is the value of slot s for entity e at time τ?" is the unique surviving normalized value of the maximum-weight independent set on the typed conflict subgraph restricted to that slot at that time; the system abstains when multiple distinct normalized values survive, and applies only when an audited query-side router declares the query in-scope.*
- **Why smallest adequate.** The operator is one schema extension (`claim_key`, `slot_type`, `object_norm`), one writer-LLM prompt change, one linker with 3-call agreement, one MWIS solver, one value-equivalence check, and one applicability router (sharing the parser call). No new model, no training, no architecture, no auxiliary head.
- **Why timely.** Same LLM-as-structurer / judge / router primitives that LightMem (ICLR 2026) and SimpleMem (ICML 2026) validated, applied to the *truth-of-fact* sub-problem those papers skip, with an audited applicability boundary that aligns the operator's cost with the slice where it wins.

## Contribution Focus

- **Dominant contribution.** Slot-scoped truth-maintenance semantics for agent memory: typed schema with canonical `(entity_id, slot_name)` keys + normalized values; agreement-hard typed `{contradict, supersede}` edges; value-level decision rule (unique surviving normalized value or abstain); audited applicability router. Demonstrated on a 2-stratum controlled supersede slice and on the routed-to-TTMG slice of LongMemEval-S full N=500. Intrinsic router audit and intrinsic key-alignment audit reported as first-class numbers.
- **Optional supporting contribution.** Two-stratum controlled supersede slice as internal measurement instrument (released as labelling script + human-audit table).
- **Explicit non-contributions.**
  - Not a general LongMemEval/LoCoMo win.
  - Not a token-efficiency win.
  - Not a new training objective.
  - Not a benchmark contribution.
  - Not a slot-in conflict layer (Path A, deferred).
  - Not a contribution about MWIS — MWIS is the solver, not the novelty.
  - **No claim on routed-to-Flat slice.**

## Proposed Method

### Complexity Budget

- **Frozen / reused.** Reader = `deepseek-v3.2` primary; embedder, MAAS endpoints, A-Mem reimplementation, Flat baseline, storage = unchanged. `Qwen3-30B-A3B-Instruct-2507` used in appendix only.
- **New / extended (5 deltas, all in existing files).**
  1. *Schema*: add `claim_key: (entity_id, slot_name)`, `slot_type: Literal["single_valued","multi_valued"]`, `object_norm: str` to `Claim`.
  2. *Writer*: prompt now emits all three new fields per claim.
  3. *Canonicalizer*: deterministic post-processor (lowercase, lemma, alias map) applied after both writer and parser to make `claim_key` canonical.
  4. *Linker*: 3-call agreement-based hardness; supersede only within same canonical `claim_key` and `slot_type==single_valued`; label set reduced to `{contradict, supersede, unrelated}`.
  5. *Read policy*: parser emits `(claim_key_q, slot_type_q, τ_q, asks_history, applicable?)`; if not applicable → Flat; else exact MWIS on top-k restricted to canonical-key match + `valid_at(τ_q)`; **answer iff surviving normalized values ≡ 1; otherwise abstain**.
- **Tempting additions intentionally not used.** No NLI fine-tune; no probabilistic temporal reasoning; no learned MWIS; no new ranker; no new training; no agent simulator; no multi-modal; no `support` label.

### System Overview

```
            ┌────────────────────────────────────────────────────────────┐
WRITE-time  │  session text → writer (LLM) →                             │
            │   list[Claim(content, claim_key=(entity, slot),            │
            │              slot_type, object_norm,                       │
            │              valid_from, valid_to, polarity, conf)]        │
            │                                                            │
            │  for each new c:                                           │
            │      c.claim_key = canonicalize(c.claim_key)               │
            │      cand = SP-index.lookup(c.claim_key) ∪ kNN_emb(c)      │
            │      for c' in cand with same canonical claim_key:         │
            │          if slot_type[c]=slot_type[c']=single_valued:      │
            │              # 3-call self-consistency                     │
            │              labels = [linker(c,c'; T=t,prompt=p)          │
            │                       for (t,p) in 3 variants]             │
            │              hardness = max_l |[L=l for L in labels]| / 3  │
            │              top_label = mode(labels)                      │
            │              if top_label in {contradict, supersede}       │
            │                 and hardness ≥ 2/3:                        │
            │                  add hard Edge(c↔c', top_label, hardness)  │
            │                  if top_label=supersede and c' older:      │
            │                      c'.valid_to ← c.valid_from − ε        │
            │                      c'.superseded_by ← c.id               │
            └────────────────────────────────────────────────────────────┘

            ┌────────────────────────────────────────────────────────────┐
READ-time   │  query → parser (LLM) →                                    │
            │      (claim_key_q, slot_type_q, τ_q, asks_history,         │
            │       applicable?)                                         │
            │  claim_key_q = canonicalize(claim_key_q)                   │
            │                                                            │
            │  if not applicable:                                        │
            │      return Flat(query)                                    │
            │                                                            │
            │  cand = topK_emb(query) ∪ topK_bm25(query)                 │
            │  cand = [c for c in cand                                   │
            │            if c.claim_key == claim_key_q                   │
            │            and valid_at(c, τ_q, asks_history)]             │
            │  H    = subgraph of hard edges over cand                   │
            │  S    = exact_MWIS(cand, H, weights=hardness×writer_conf)  │
            │  values = { c.object_norm : c ∈ S }                        │
            │  if |values| == 1:                                         │
            │      return reader(query, S, value=values.pop())           │
            │  else:                                                     │
            │      return ABSTAIN(reason="multiple_distinct_values",     │
            │                     values=values, S=S, H=H)               │
            └────────────────────────────────────────────────────────────┘
```

### Core Mechanism

- **Schema.** `Claim(content, subject, predicate, object, claim_key=(entity_id, slot_name), slot_type, object_norm, valid_from, valid_to, polarity, confidence, active, superseded_by)`. Three new fields.
- **Canonicalizer.** Deterministic post-processor: lowercase + lemma + static alias map (small, ≤200 entries built from dev set + universal pronoun aliases). Applied after both writer and parser. Result: `claim_key` strings are byte-equal across write and read sides whenever they refer to the same slot.
- **Linker.** `{contradict, supersede, unrelated}` only. Hardness = max-agreement-fraction across 3 calls (varied temperature 0.0/0.3/0.6 + 1-of-3 prompt phrasing). Edge admitted iff label ∈ `{contradict, supersede}` and hardness ≥ 2/3.
- **Supersede materialization.** On accepting hard `supersede(c'→c)` (older `c'`), set `c'.valid_to = c.valid_from − ε`, `c'.superseded_by = c.id`.
- **Exact MWIS.** Top-k ≤ 8 restricted to canonical-key match + `valid_at(τ_q)`; weights = `hardness × writer_confidence`.
- **Value-level decision rule.** Compute `values = {c.object_norm : c ∈ S}`; **answer iff |values| == 1; else abstain.** This is the round-2 fix: paraphrase-equivalent claims no longer trigger spurious abstention.
- **Why this is the main novelty.** No surveyed competitor: (i) types memory by `slot_type`, (ii) materializes supersede as a `valid_to` rewrite, (iii) uses agreement-hard typed edges for read-time MWIS, (iv) abstains on multiple distinct surviving *values* inside an *audited* applicability gate. The novelty is the *semantics* — what the operator means and where it applies — not the MWIS solver.

### Applicability Gate (locked + intrinsically audited, round-2 sharpening)

- **Implementation.** Same parser call extended to emit `(claim_key_q, slot_type_q, applicable: bool)`. `applicable = (slot_type_q == single_valued) ∧ (claim_key_q is not None) ∧ asks_truth_of_fact`.
- **Locking protocol.** Router prompt + post-processor + decision rule frozen at end of Week 1, committed to git with hash, hash printed in paper. No test-time change.
- **Intrinsic audit (NEW round 2).** 100-q human-labeled set (50 LongMemEval-S, 50 LoCoMo) author-labeled in 1 hour. Router-precision, router-recall ≥ 0.85 each on this set, reported as headline. If a router fails the audit, prompt is iterated *before lock*, audit re-run; once locked, no further changes.
- **Composed end-to-end reporting (NEW round 2).** Every results table includes three numbers per benchmark: (a) applicability rate (router-coverage), (b) routed-to-TTMG accuracy, (c) composed end-to-end accuracy = `(routed-to-TTMG-accuracy × applicability rate) + (Flat-on-routed-out × (1 − applicability rate))`. Column (c) is the deployer-relevant number; columns (a) and (b) defend the scoped claim.

### Modern Primitive Usage

Three LLM uses, all zero-shot, all field-standard:
1. **Writer**: structured-extraction LLM emitting typed claims with `claim_key`, `slot_type`, `object_norm`, validity. Mirrors SimpleMem's structured compression with three extra schema fields.
2. **Linker**: pairwise judge LLM with 3-call self-consistency for hardness.
3. **Parser + applicability router**: intent + temporal-anchor + canonical claim-key + applicability classification, in a single call. Mirrors SimpleMem's intent-aware planner.

All three are existing MAAS API calls; the round-2 changes are prompt-only.

### Integration into the Existing Pipeline

- **Files touched.** `ttmg/schema.py` (+3 fields), `ttmg/writer_temporal.py` (prompt update), `ttmg/conflict_linker.py` (3-call agreement; reduced label set; canonical-key filter), `ttmg/truth_retriever.py` (parser augmentation; canonicalizer; exact MWIS; value-level decision rule), `ttmg/system.py` (config flags for 4 ablations + applicability-router on/off + canonicalizer on/off), **NEW: `ttmg/canonicalize.py` (deterministic post-processor + alias map)**.
- **Files frozen.** A-Mem reimplementation, Flat baseline, MAAS API layer, storage backend, embedding model.

### Training Plan

None. Prompt-iteration on writer (`claim_key`, `slot_type`, `object_norm`, `valid_from` extraction) and linker (`supersede` recall + hardness calibration) using the 60-q dev split disjoint from the controlled-slice test items. Acceptance gates *before* test-time runs:
- Linker `supersede`-F1 ≥ 0.7 with hardness Brier ≤ 0.2 on dev.
- Writer-key-precision and parser-key-recall ≥ 0.85 each on 60-q dev.
- Router precision and recall ≥ 0.85 each on 100-q human-labeled audit set.
- Value-equivalence intrinsic ≤ 15% disagreement vs author canonical value on dev.

### Failure Modes and Diagnostics

- **F1 Linker noise inflates hard contradict edges.** Detect: hard-edge density on a fixed 30-session sample > 2× baseline. Mitigate: raise hardness threshold from 2/3 to 3/3 on diagnostic samples.
- **F2 MWIS drops a correct claim.** Detect: per-question audit when MWIS solution's writer-confidence sum < single-vertex alternative's. Mitigate: weights = `hardness × writer_confidence` (already the rule).
- **F3 Over-abstention.** Detect: abstain rate on routed-to-TTMG slice > 20%. Mitigate: tighten applicability gate; raise hardness threshold; check `object_norm` granularity (over-fine normalization causes false abstentions).
- **F4 Applicability misroute.** Detect: router-precision/recall < 0.85 on audit set. Mitigate: prompt iteration *before lock*; if locked-and-failing, the design fails per success condition (9c).
- **F5 LoCoMo cross-domain regression.** Already observed (–13.4 pp). Round-2 diagnosis: applicability rate on LoCoMo expected < 15%; on routed-to-TTMG sub-slice TTMG behaves as predicted; composed end-to-end accuracy reported as deployer-relevant headline.
- **F6 SSA regression.** Already observed (–21 pp at N=500). SSA queries fail applicability gate by design (asks-what-was-said, not asks-truth-of-fact). Routed to Flat. Removed from TTMG-claimed numbers.
- **F7 (NEW) Key-alignment silent failure.** Detect: writer-key-precision or parser-key-recall < 0.85. Mitigate: extend alias map; iterate canonicalizer rules *before lock*.
- **F8 (NEW) Value-normalization mismatch.** Detect: value-equivalence intrinsic > 15% disagreement on dev (system answers but value disagrees with author canonical). Mitigate: tighten writer prompt; expand `object_norm` style guide.

### Novelty and Elegance Argument

- **Closest work.** SimpleMem (ICML 2026) intent-aware retrieval planning + symbolic temporal layer; A-Mem (NeurIPS 2025) memory evolution.
- **Exact difference.** SimpleMem's symbolic temporal layer can filter retrieved candidates by *timestamp* but cannot tell that a 2024-03 single-valued claim about `(user, coffee_temperature_preference)` has been *replaced* by a 2024-09 claim about the same canonical key with a different `object_norm`; both still surface, and SimpleMem has no abstain-on-conflict policy. A-Mem semantically refreshes neighbours but maintains no validity intervals, no typed edges, no `slot_type`, no `claim_key`, no `object_norm` — its memory evolution can refresh stale neighbours but cannot deactivate them and cannot resolve them at the value level. *TTMG* introduces three minimal type-level additions — canonical `claim_key`, `slot_type`, `object_norm` — and one read-time semantic — *value-level unique-survivor under applicability* — that together constitute the first explicit truth-maintenance operator for the slot-update sub-problem of agent memory, *with its applicability boundary intrinsically audited and locked*.
- **Why mechanism-level (semantic), not pile-up.** Three new schema fields + one calibrated linker + one exact small-set solver + one canonicalizer + one applicability router. The paper's contribution can be summarised in one equation:
  `answer(q) = if applicable(q) then ( unique-value(MWIS(cand_q, hard_edges)) | ⊥ ) else Flat(q)`
  where `unique-value` returns the answer iff `|{c.object_norm : c ∈ MWIS}| == 1` and `⊥` denotes abstain.

## Claim-Driven Validation Sketch

### Claim 1 (Dominant) — Truth maintenance dominates on labelled supersede in both strata

- **Statement.** On both controlled-slice strata (`latest-state KU` ≈150q, `as-of-time TR` ≈100q), TTMG strictly dominates Flat hybrid-RAG and A-Mem reimplementation on answer accuracy (paired McNemar p<0.05 per stratum, no losing stratum), with intrinsic linker `supersede`-F1 ≥ 0.7, hardness Brier ≤ 0.2 on the human-audited dev set, and value-level disagreement ≤ 15%.
- **Minimal experiment.** 3 methods × 3 seeds × 1 backbone (deepseek-v3.2) × controlled slice (~250q across 2 strata).
- **Baselines / ablations.** Flat hybrid-RAG; A-Mem reimplementation; TTMG full; ablations: `no_validity`, `no_supersede`, `no_abstain`, `no_linker` (4 ablations).
- **Metric.** Intrinsic supersede F1 + hardness Brier + value-equivalence; downstream accuracy per stratum; paired McNemar; effect size Cohen's h.
- **Expected evidence.** TTMG ≥ Flat + 8 pp, ≥ A-Mem + 5 pp per stratum. `no_supersede` collapses on `latest-state KU`; `no_validity` collapses on `as-of-time TR`; `no_abstain` shrinks correct-abstain rate to ≈ 0; `no_linker` collapses both strata to ≈ A-Mem. Linker F1 ≥ 0.7, Brier ≤ 0.2, value-disagreement ≤ 15%.

### Claim 2 (Supporting) — On the routed-to-TTMG slice of LongMemEval-S, the operator is causal on TR / KU; on the routed-to-Flat slice, no claim is made; intrinsic audits clear; composed end-to-end accuracy reported

- **Statement.** On full LongMemEval-S (N=500, 3 seeds), restricted to the routed-to-TTMG slice (expected ~30–50% applicability), TTMG ≥ Flat with paired McNemar p<0.05 in TTMG's favor on the combined TR + KU axis. **Intrinsic router precision and recall ≥ 0.85** on the 100-q human-labeled audit set. **Composed end-to-end accuracy** (TTMG-on-applicable + Flat-on-rest) reported as deployer-relevant headline.
- **Minimal experiment.** 3 methods × 3 seeds (0, 7, 17) × 1 primary backbone (deepseek-v3.2) × N=500. Final-method robustness check on Qwen3-30B-A3B for {Flat, TTMG} only at seed=0 → appendix.
- **Baselines / ablations.** Flat; A-Mem; TTMG full; same 4 ablations.
- **Metric.** Per-category accuracy; paired McNemar on routed-to-TTMG slice; correct-abstain rate at fixed answer accuracy on full n=30; applicability rate per slice; composed end-to-end accuracy; tokens/q + latency reported but not primary.
- **Expected evidence.** Routed-to-TTMG slice TR + KU: paired McNemar p<0.05 in TTMG's favor. Applicability rate on LongMemEval-S: ~30–50%; on LoCoMo: <15%. Router precision and recall ≥ 0.85 on audit. Correct-abstain on n=30 strictly > Flat. Overall LongMemEval-S accuracy: TTMG within 5 pp of Flat (acknowledged scoped). Composed end-to-end accuracy: TTMG-composed ≥ Flat on LongMemEval-S; ≈ Flat on LoCoMo (the diagnostic).

(MAX_PRIMARY_CLAIMS = 2 honored.)

## Experiment Handoff Inputs

- **Must-prove claims.** (1) Both controlled-slice strata strict dominance + linker intrinsic F1 + hardness Brier + value-equivalence; (2) Routed-to-TTMG TR + KU paired wins on full LongMemEval-S + composed end-to-end accuracy + intrinsic router/key-alignment audits clearing 0.85 + correct-abstain on full n=30.
- **Must-run ablations.** `no_validity`, `no_supersede`, `no_abstain`, `no_linker` (4, all on primary backbone).
- **Critical datasets / metrics.** Controlled supersede slice (~250q, two strata, human-audited); LongMemEval-S full N=500; full abstention n=30; LoCoMo (already run, reported as diagnostic); 100-q router audit set; 60-q dev split for linker + writer + parser intrinsic gates.
- **Highest-risk assumptions.** (i) Writer LLM produces stable canonicalizable `claim_key` strings (will check on dev: same fact → same key after canonicalization). (ii) 3-call agreement gives meaningful hardness signal (Brier on dev). (iii) Applicability router agrees with author labels on 100-q audit at ≥ 85% precision and recall. (iv) Multi-seed reproduces ablation directionality from existing seed=0 run. (v) On LoCoMo, applicability rate < 15%; if higher, the diagnostic story is revised. (vi) `object_norm` granularity is right (over-fine → false abstentions; over-coarse → missed contradictions).

## Compute & Timeline Estimate

- **Compute.** All inference via MAAS API; no local training. ≈ **30 GPU-hour-equivalents** on 1–2× RTX-4090 (unchanged from round 1).
- **Data / annotation cost.** Controlled slice writer + cross-check ≈ 2 h MAAS calls. Human audit ≈ 4 h author time across 2 strata + ≈ 1 h on 100-q router audit + ≈ 1 h on 60-q key-alignment / value-equivalence audit. Total ≈ 6 h author time. No external annotation.
- **Timeline.**
  - **Week 1.** Schema extension (`claim_key`, `slot_type`, `object_norm`); canonicalizer + alias map; prompt-harden writer + linker + parser+router on dev split; build + human-audit two-stratum controlled slice + 100-q router audit + 60-q key/value audit; intrinsic gates (linker F1, Brier, key-precision/recall, router-precision/recall, value-equivalence) all clear ≥ thresholds. **Lock router prompt at end of Week 1; commit hash printed in paper.** Multi-seed pilot N=150 on three methods to confirm ablation directionality.
  - **Week 2.** Full N=500 × 3 seeds × deepseek-v3.2 for {Flat, A-Mem, TTMG, 4 ablations}. Both controlled-slice strata × 3 seeds × 3 methods. Compute applicability rate per slice. Compute composed end-to-end accuracy per benchmark. Secondary-backbone robustness check (Qwen3-30B-A3B, seed=0) for {Flat, TTMG} → appendix.
  - **Week 3.** Paper rewrite with round-2 framing (slot-scoped semantic operator + audited applicability gate); figures (router-coverage × accuracy plot, composed-end-to-end vs routed-slice plot, per-stratum strict-dominance plot, per-ablation drop bar chart, Brier-calibration plot); statistical hardening (paired McNemar tables per slice + per stratum, abstain-correctness curves, hardness Brier plot, value-equivalence histogram); reconcile STATUS.md with reality; swap in real MemGPT (arXiv 2310.08560); cite-comparison rows with SimpleMem, LightMem.

(End of round-2 refinement.)
