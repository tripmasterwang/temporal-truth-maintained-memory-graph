# Round 3 Refinement (final round)

## Problem Anchor (verbatim from round 0)

- **Bottom-line problem.** When an LLM agent accumulates conversational memory across many sessions, statements about facts (preferences, schedules, plans, attributes) get *updated, contradicted, and superseded* over time. Current agent-memory systems organize memory semantically or hierarchically, but **none explicitly maintains *which fact is true at each point in time***. The result: under knowledge updates and temporal-validity questions, retrievers surface stale facts; under outright contradictions, readers fabricate confident answers instead of abstaining.
- **Must-solve bottleneck.** (i) record `valid_from / valid_to` and an explicit `supersede / contradict` relation between claims; (ii) at read time, return the largest temporally-consistent claim subset that matches the query; (iii) abstain when residual contradiction cannot be resolved.
- **Non-goals.** Not general memory replacement; not token-efficiency wins; not a static KG builder; not a slot-in conflict layer (Path A, deferred); not a benchmark-creation paper.
- **Constraints.** 1–2 RTX-4090; MAAS API; reuse `ttmg/{schema, writer_temporal, conflict_linker, truth_retriever, system}.py`; 2–3 weeks; NeurIPS / ICML main track.

## Anchor Check

- **Original bottleneck.** Truth maintenance — which fact holds at time *τ*, which one supersedes which, when to abstain — for agent memory.
- **Why the revised method still addresses it.** Round-3 changes close the last decision-rule loophole (all-optima MWIS agreement) and replace legacy retrieval with deterministic key-fetch on the applicable slice. The bottleneck is unchanged; the operator is now *adversarially correct*: it cannot answer when any optimal consistent subset disagrees on the value.
- **Reviewer suggestions rejected as drift.** None. Drift = NONE in all 3 rounds; round-3 critiques are all decision-rule and interface refinements.

## Simplicity Check

- **Dominant contribution after revision.** A *slot-scoped truth-maintenance operator* whose semantics are: (i) typed claim graph with canonical `(entity_id, slot_name)` keys, normalized values (`object_norm`), and validity intervals; (ii) agreement-hard typed `{contradict, supersede}` edges; (iii) for applicable queries, fetch all canonical-key claims, time-filter, then **answer iff *every* maximum-weight independent set of the conflict subgraph induces the same `object_norm`** — otherwise abstain; (iv) gated by an intrinsically audited and locked applicability router.
- **Components removed or merged.**
  - **Hybrid `topK(emb) ∪ topK(bm25)` retrieval removed from the applicable path.** Replaced by canonical-key fetch + time filter. Hybrid retrieval kept only as a **fallback** when the keyed fetch returns 0 candidates (typically a writer-canonicalization miss; logged for audit).
  - **`writer_confidence` weighting de-emphasized in the main paper story.** With all-optima agreement, the weight choice no longer changes which queries get answered (it can only change which optimum is reported when all agree on the value). Weights become an implementation detail in supplementary.
- **Reviewer suggestions rejected as unnecessary complexity.** None. Each round-3 critique either closes a logical hole (all-optima), removes legacy code (hybrid retrieval on applicable), or sharpens an audit protocol (object_norm).
- **Why the remaining mechanism is still the smallest adequate route.** Three new schema fields (`claim_key`, `slot_type`, `object_norm`) emitted by the writer LLM; one canonicalizer (deterministic post-processor); one linker (3-call agreement); one **all-optima** MWIS enumerator (k ≤ 8, ≤ 2^k subset checks, microseconds); one applicability router (sharing the parser call). No new module, no training, no architecture, no auxiliary head. The novelty is the *semantics* — what the operator means and where it applies — not the solver.

## Changes Made

### 1. All-optima MWIS agreement for abstention (CRITICAL)
- **Reviewer said (CRITICAL):** "The current rule `answer iff |{c.object_norm : c ∈ MWIS}| == 1` can still answer under unresolved contradiction — a single optimal MWIS may pick one value due to heuristic weights while another equally-optimal independent set supports a different value. Define `answer` only if **all maximum-weight independent sets** induce the same `object_norm`."
- **Action.** Replace the read-time decision rule:
  ```
  # Round 2 (logical hole)
  S = exact_MWIS(cand, H, weights=hardness × writer_conf)
  values = {c.object_norm : c ∈ S}
  if |values| == 1: answer; else: abstain
  ```
  with the round-3 rule:
  ```
  # Round 3 (adversarially correct)
  W*    = max over independent sets I in (cand, H) of  sum(hardness[c]·writer_conf[c] for c in I)
  Opts  = { I : I is an independent set in (cand, H) and weight(I) == W* }
  Vals  = { c.object_norm : I in Opts and c in I }
  if |Vals| == 1: answer with the unique value (use any I in Opts as supporting context)
  else:           ABSTAIN(reason="optima_disagree", optima=Opts, values=Vals)
  ```
  Implementation: with k ≤ 8, enumerate all subsets (≤ 256), filter to independent ones (no hard edge between any pair), keep max-weight subsets, collect all `object_norm`s appearing in any such subset. O(2^k) — under 256 subset checks per query, microsecond-cheap.
- **Reasoning.** Reviewer's diagnosis is correct: heuristic weights should not mask unresolved contradictions. The fix removes the loophole entirely and makes the system *strictly safer* — it abstains in exactly those cases where the conflict structure cannot uniquely determine the value, regardless of weighting choice.
- **Impact on core method.** The system now refuses to answer iff there exists any consistent reading of the conflict graph that disagrees on the answer. This is the cleanest possible truth-maintenance semantics; it is what a reviewer asked for; and it is computationally trivial.

### 2. Replace hybrid retrieval with canonical-key fetch on applicable queries (IMPORTANT)
- **Reviewer said (IMPORTANT):** "Hybrid `topK(emb) ∪ topK(bm25)` retrieval is now legacy baggage. Once `claim_key = (entity_id, slot_name)` is canonicalized and audited, the applicable-slice operator should be a keyed fetch + time filter + conflict resolution problem. Keep hybrid retrieval only as fallback or justify with a recall study."
- **Action.** New read-path on applicable queries:
  ```
  cand = SP_index.fetch_all(claim_key_q)             # exact canonical-key fetch
  cand = [c for c in cand if valid_at(c, τ_q, asks_history)]
  if len(cand) == 0:
      cand = topK_emb(query) ∪ topK_bm25(query)      # FALLBACK only
      cand = [c for c in cand if c.claim_key == claim_key_q
                              and valid_at(c, τ_q, asks_history)]
      log("key_fetch_miss", q, claim_key_q)            # audited
  H = subgraph of hard edges over cand
  ... (apply round-3 all-optima rule)
  ```
- **Reasoning.** Once canonicalization clears the 0.85 audit bar (writer-key-precision and parser-key-recall), the canonical key is by construction the right index; embedding/BM25 only adds noise unless the writer missed a slot or the parser misclassifies. We instrument the fallback as a logged event, so any meaningful fallback rate is reported as an intrinsic audit number.
- **Impact on core method.** Removes legacy retrieval cost from the applicable path. Makes the operator's recall *deterministic given the canonicalizer*, rather than dependent on embedding noise. Aligns with the round-2 framing that canonicalization is the load-bearing interface.

### 3. Object-norm audit protocol made crisp (MINOR)
- **Reviewer said (MINOR):** "`value-equivalence disagreement ≤ 15 %` needs a crisp audit definition. Specify whether disagreement is measured against (a) human-normalized `object_norm`, (b) pairwise paraphrase labeling, or (c) canonical-value clustering."
- **Action.** Use **(c) canonical-value clustering with author-defined equivalence classes**, rigorously defined:
  - For each of the 60 dev questions, the author manually defines an equivalence class `E_q ⊆ {strings}` enumerating the acceptable normalized values (e.g. for "user's preferred coffee temperature" the class might be `{"hot","warm-hot","piping_hot"}` if the author considers them equivalent for the answer).
  - The system's `object_norm` for a retained claim is **disagreeing** iff `object_norm ∉ E_q^canonical_value`. The author-defined class is the source of truth.
  - Audit metric: `value_equivalence_disagreement = #(disagreeing answers) / #(answers given)` on the 60-q dev set. Target ≤ 15%.
  - This is *intrinsic* (no downstream-task dependence), *reproducible* (the equivalence classes are released as a small JSON), and *cheap* (60 author-defined classes ≈ 1 hour author time).
- **Reasoning.** Among the three options, (c) is the most reproducible and the least sensitive to LLM stochasticity. (a) requires the author to *normalize* every dev value, which is heavier and conflates labelling with measurement. (b) requires N² paraphrase comparisons which is expensive. Equivalence classes are the standard machine-translation / QA evaluation protocol (e.g. SQuAD's allowed-answer sets).
- **Impact on core method.** No change to the operator. Adds one small, releasable artifact (equivalence-class JSON) to the supplementary.

## Revised Proposal

# Research Proposal: Slot-Scoped Truth-Maintenance Semantics for Agent Memory — A Specialist Operator with an Audited Applicability Gate (Round 3, final)

## Problem Anchor

(verbatim from round 0; see top of this document.)

## Updated Success Condition (round 3)

1. **Within the routed-to-TTMG slice of LongMemEval-S full N=500** (3 seeds, primary backbone `deepseek-v3.2`): TTMG ≥ Flat with paired McNemar p<0.05 in TTMG's favor on the combined TR + KU axis.
2. **On both controlled-slice strata** (`latest-state KU` ≈150q, `as-of-time TR` ≈100q): TTMG strictly dominates Flat and A-Mem (paired McNemar p<0.05 per stratum, no losing stratum); intrinsic linker `supersede`-F1 ≥ 0.7; hardness Brier ≤ 0.2; **value-equivalence disagreement ≤ 15% under author-defined equivalence-class protocol**.
3. **Abstention behavioural metric** on full n=30: TTMG correct-abstain rate strictly > Flat at fixed answer accuracy.
4. **Mechanism causality**: each of `no_validity`, `no_supersede`, `no_abstain`, `no_linker` produces ≥1 pp drop on its targeted slice within the routed-to-TTMG slice.
5. **Cross-domain regression report**: LoCoMo applicability rate < 15%; on routed-to-TTMG sub-slice TTMG behaves as predicted; **composed end-to-end accuracy** reported.
6. **Intrinsic router audit**: precision and recall ≥ 0.85 each on 100-q audit set, *before* test-time runs.
7. **Intrinsic key alignment audit**: writer-key-precision and parser-key-recall ≥ 0.85 each on 60-q dev, *before* test-time runs.
8. **Composed end-to-end accuracy** reported alongside routed-slice claims on every benchmark.
9. **(NEW R3) Key-fetch-fallback rate** (a fallback to hybrid retrieval) is reported on every benchmark and is expected ≤ 5% on LongMemEval-S; > 5% triggers extended canonicalizer iteration *before lock*.
10. **Failure clause**: design fails if (a) controlled-slice TTMG > {Flat, A-Mem} at p<0.05 fails on either stratum, OR (b) routed-to-TTMG TR-or-KU paired McNemar p<0.05 fails on full LongMemEval-S, OR (c) intrinsic router or key-alignment audits fail to clear 0.85, OR (d) value-equivalence disagreement > 15% on dev.

## Method Thesis (round 3, final)

- **One-sentence thesis.** *For single-valued, update-bearing memory slots, the answer to "what is the value of slot s for entity e at time τ?" is the unique normalized value that survives across **all** maximum-weight independent sets of the typed conflict subgraph at time τ; the system abstains when any optimal independent set disagrees on the value, and applies only when an audited query-side router declares the query in-scope.*
- **Why smallest adequate.** Three schema fields, one writer prompt change, one canonicalizer, one all-optima MWIS enumerator, one applicability router — and the canonical-key fetch makes the applicable-path retrieval deterministic. No model, no training, no architecture, no auxiliary head.
- **Why timely.** Same LLM-as-structurer / judge / router primitives validated by SimpleMem (ICML 2026) and LightMem (ICLR 2026), applied to the truth-of-fact sub-problem with *adversarially-correct* abstention semantics absent in any surveyed competitor.

## Contribution Focus (round 3, final)

- **Dominant contribution.** Slot-scoped truth-maintenance semantics for agent memory with **all-optima abstention** — typed schema with canonical `(entity_id, slot_name)` keys + normalized values + validity intervals + agreement-hard typed `{contradict, supersede}` edges + the all-optima MWIS-agreement decision rule; gated by an audited locked applicability router; retrieved via deterministic canonical-key fetch on the applicable path. Demonstrated on a 2-stratum controlled supersede slice and on the routed-to-TTMG slice of LongMemEval-S full N=500. Intrinsic router audit, intrinsic key-alignment audit, value-equivalence audit, and key-fetch-fallback rate reported as first-class numbers.
- **Optional supporting contribution.** Two-stratum controlled supersede slice + author-defined value-equivalence classes as internal measurement instruments (released as labelling script + JSON in supplementary).
- **Explicit non-contributions.** Not a general LongMemEval/LoCoMo win; not a token-efficiency win; not new training; not Path-A slot-in; not a benchmark contribution; not a contribution about MWIS (MWIS is the solver); **no claim on routed-to-Flat slice**.

## Proposed Method

### Complexity Budget

- **Frozen.** Reader = `deepseek-v3.2` primary; embedder, MAAS endpoints, A-Mem reimpl, Flat baseline, storage = unchanged. `Qwen3-30B-A3B-Instruct-2507` → appendix only.
- **5 deltas, all in existing or one new file.**
  1. *Schema*: add `claim_key=(entity_id, slot_name)`, `slot_type`, `object_norm`.
  2. *Writer*: prompt emits all three.
  3. *Canonicalizer* (new file `ttmg/canonicalize.py`): lowercase + lemma + static alias map; applied after both writer and parser.
  4. *Linker*: 3-call agreement; supersede only within same canonical key + `slot_type==single_valued`; label set = `{contradict, supersede, unrelated}`.
  5. *Read policy*: parser emits `(claim_key_q, slot_type_q, τ_q, asks_history, applicable?)`; if not applicable → Flat; else **canonical-key fetch + time-filter**, then **all-optima MWIS** enumeration; answer iff `|⋃_{I ∈ Opts} {c.object_norm : c ∈ I}| == 1`; else abstain. Hybrid retrieval kept only as fallback when key-fetch returns 0 (logged).
- **Tempting additions intentionally not used.** No NLI fine-tune; no probabilistic temporal reasoning; no learned MWIS; no new ranker; no new training; no agent simulator; no multi-modal; no `support` label; no soft constraints in the conflict graph.

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
            │      cand = SP-index.fetch_all(c.claim_key)                │
            │      for c' in cand with same canonical claim_key:         │
            │          if slot_type[c]=slot_type[c']=single_valued:      │
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
            │  cand = SP_index.fetch_all(claim_key_q)        # canonical │
            │  cand = [c for c in cand                                   │
            │            if valid_at(c, τ_q, asks_history)]              │
            │  if len(cand) == 0:                                        │
            │      cand = topK_emb(query) ∪ topK_bm25(query)  # FALLBACK │
            │      cand = [c for c in cand                               │
            │               if c.claim_key == claim_key_q                │
            │               and valid_at(c, τ_q, asks_history)]          │
            │      log("key_fetch_miss", q, claim_key_q)     # audited   │
            │                                                            │
            │  H    = subgraph of hard edges over cand                   │
            │  W*   = max{ Σ hardness[c]·writer_conf[c]                  │
            │              : I ⊆ cand, no hard edge in I }               │
            │  Opts = { I : I is hard-edge-independent, weight(I)=W* }   │
            │  Vals = ⋃_{I in Opts} { c.object_norm : c in I }           │
            │                                                            │
            │  if |Vals| == 1:                                           │
            │      return reader(query, any I in Opts, value=Vals.pop()) │
            │  else:                                                     │
            │      return ABSTAIN(reason="optima_disagree",              │
            │                     Opts=Opts, Vals=Vals)                  │
            └────────────────────────────────────────────────────────────┘
```

### Core Mechanism

- **Schema.** `Claim(content, subject, predicate, object, claim_key=(entity_id, slot_name), slot_type, object_norm, valid_from, valid_to, polarity, confidence, active, superseded_by)`.
- **Canonicalizer.** Deterministic: lowercase + lemma + static alias map (≤ 200 entries built incrementally on dev). Applied after both writer and parser. Result: `claim_key` strings byte-equal across write and read sides whenever they refer to the same slot.
- **Linker.** `{contradict, supersede, unrelated}`. Hardness = max-agreement-fraction across 3 calls (varied temperature 0.0/0.3/0.6 + 1-of-3 prompt phrasing). Edge admitted iff label ∈ `{contradict, supersede}` AND hardness ≥ 2/3.
- **Supersede materialization.** On accepting hard `supersede(c'→c)` (older `c'`), set `c'.valid_to = c.valid_from − ε`, `c'.superseded_by = c.id`.
- **Canonical-key fetch.** On applicable queries, `SP_index.fetch_all(claim_key_q)` returns *all* claims with the canonicalized key. No top-k truncation on the applicable path (set is naturally bounded to ≤ a few dozen for any single slot, and the time-filter further reduces it).
- **All-optima MWIS rule (round-3 critical fix).**
  - Compute `W* = max{weight(I) : I ⊆ cand, I has no hard edge}` via subset enumeration (k ≤ 8 → ≤ 2⁸ subsets, microsecond-cheap).
  - Collect `Opts = {I : I is independent and weight(I) == W*}`.
  - `Vals = ⋃_{I ∈ Opts} {c.object_norm : c ∈ I}`.
  - **Answer iff `|Vals| == 1`; else abstain.**
- **Why this is the main novelty.** No surveyed competitor: (i) types memory by `slot_type`, (ii) materializes supersede as a `valid_to` rewrite, (iii) uses agreement-hard typed edges with all-optima MWIS abstention, (iv) gates the operator with an *audited locked* applicability router, (v) fetches via canonical key. The novelty is the *semantics* (the all-optima abstention rule under canonical keying), not the solver.

### Applicability Gate (locked + intrinsically audited, unchanged from round 2)

- Same parser call extended to emit `(claim_key_q, slot_type_q, applicable: bool)`.
- Locking protocol: router prompt + post-processor + decision rule frozen end-of-Week-1, git-hashed, hash printed in paper.
- Intrinsic audit: 100-q author-labeled (50 LongMemEval, 50 LoCoMo); router precision + recall ≥ 0.85, headline.
- Composed end-to-end reporting: `(applicability_rate, routed-to-TTMG accuracy, composed end-to-end accuracy)` on every benchmark.

### Modern Primitive Usage

Three LLM uses, all zero-shot, all field-standard:
1. **Writer**: structured-extraction LLM emitting `claim_key`, `slot_type`, `object_norm`, validity.
2. **Linker**: pairwise judge LLM with 3-call self-consistency.
3. **Parser + applicability router**: intent + temporal-anchor + canonical claim-key + applicability classification, single call.

### Integration into the Existing Pipeline

- **Files touched.** `ttmg/schema.py` (+3 fields), `ttmg/writer_temporal.py` (prompt update), `ttmg/conflict_linker.py` (3-call agreement; reduced label set; canonical-key filter), `ttmg/truth_retriever.py` (parser augmentation; canonicalizer; canonical-key fetch + fallback; **all-optima MWIS**; value-level decision rule), `ttmg/system.py` (config flags for 4 ablations + applicability-router on/off + canonical-key-only-vs-fallback toggle), NEW: `ttmg/canonicalize.py`.
- **Files frozen.** A-Mem reimplementation, Flat baseline, MAAS API layer, storage backend, embedding model.

### Training Plan

None. Prompt-iteration on writer (`claim_key`, `slot_type`, `object_norm`, `valid_from` extraction) and linker (`supersede` recall + hardness calibration) and parser+router using a 60-q dev split disjoint from controlled-slice test items. Acceptance gates *before* test-time runs:
- Linker `supersede`-F1 ≥ 0.7, hardness Brier ≤ 0.2.
- Writer-key-precision and parser-key-recall ≥ 0.85.
- Router precision + recall ≥ 0.85 on 100-q audit set.
- Value-equivalence disagreement ≤ 15% under author-defined equivalence-class protocol on 60-q dev.
- Key-fetch-fallback rate < 5% on dev.

### Failure Modes and Diagnostics

- **F1 Linker noise inflates hard edges.** Detect: hard-edge density > 2× baseline. Mitigate: raise hardness to 3/3.
- **F2 MWIS arbitrary tie-break.** **Resolved structurally** by the all-optima rule: ties in optimum value never produce an answer.
- **F3 Over-abstention.** Detect: abstain rate > 20% on routed-to-TTMG slice. Mitigate: tighten applicability gate; check `object_norm` granularity.
- **F4 Applicability misroute.** Detect: router-precision/recall < 0.85 on audit. Mitigate: prompt iteration *before lock*; if locked-and-failing, the design fails per success condition (10c).
- **F5 LoCoMo cross-domain.** Already observed (–13.4 pp). Diagnostic: applicability rate < 15% expected.
- **F6 SSA regression.** Already observed (–21 pp at N=500). SSA fails applicability gate by design; routed to Flat.
- **F7 Key-alignment silent failure.** Detect: writer-key-precision or parser-key-recall < 0.85, OR key-fetch-fallback rate > 5%. Mitigate: extend alias map; iterate canonicalizer rules *before lock*.
- **F8 Value-normalization mismatch.** Detect: value-equivalence disagreement > 15% under equivalence-class protocol. Mitigate: tighten writer prompt; expand `object_norm` style guide; refine equivalence classes.
- **F9 (NEW R3) High key-fetch-fallback rate.** Detect: > 5% on LongMemEval-S. Mitigate: extend alias map; if persistent, reframe: hybrid retrieval is a load-bearing component on this benchmark and report it as such.

### Novelty and Elegance Argument

- **Closest work.** SimpleMem (ICML 2026) intent-aware retrieval planning + symbolic temporal layer; A-Mem (NeurIPS 2025) memory evolution.
- **Exact difference.** SimpleMem's symbolic temporal layer can filter retrieved candidates by *timestamp* but cannot tell that a 2024-03 single-valued claim about `(user, coffee_temperature_preference)` has been *replaced* by a 2024-09 claim about the same canonical key with a different `object_norm`; both still surface; no abstain-on-conflict and certainly no all-optima abstention. A-Mem semantically refreshes neighbours but maintains no validity intervals, no typed edges, no `slot_type`, no canonical `claim_key`, no `object_norm` — it cannot deactivate stale neighbours and cannot resolve them at the value level. *TTMG* introduces three minimal type-level additions — canonical `claim_key`, `slot_type`, `object_norm` — and one read-time semantic — *all-optima value-level unique-survivor under audited applicability* — that together constitute the first explicit truth-maintenance operator for the slot-update sub-problem of agent memory, with a *deterministic canonical-key fetch* on the applicable path and an *adversarially-correct* abstention rule.
- **Why mechanism-level (semantic), not pile-up.** Three new schema fields + one calibrated linker + one all-optima MWIS enumerator + one canonicalizer + one applicability router. The paper's contribution is one equation:
  `answer(q) = if applicable(q) then ( unique-value(⋃ Opts(canonical-fetch(q))) | ⊥ ) else Flat(q)`
  where `Opts` are the maximum-weight independent sets of the hard-edge subgraph and `⊥` denotes abstain. The novelty is the *all-optima* operator under *audited applicability*, not MWIS or canonical-key fetch in isolation.

## Claim-Driven Validation Sketch

### Claim 1 (Dominant) — Truth maintenance dominates on labelled supersede in both strata

- **Statement.** On both controlled-slice strata (`latest-state KU` ≈ 150q, `as-of-time TR` ≈ 100q), TTMG strictly dominates Flat hybrid-RAG and A-Mem reimplementation on answer accuracy (paired McNemar p<0.05 per stratum, no losing stratum); intrinsic linker `supersede`-F1 ≥ 0.7; hardness Brier ≤ 0.2; value-equivalence disagreement ≤ 15% under equivalence-class protocol; key-fetch-fallback rate < 5%.
- **Minimal experiment.** 3 methods × 3 seeds × 1 backbone (deepseek-v3.2) × controlled slice (~250q across 2 strata).
- **Baselines / ablations.** Flat hybrid-RAG; A-Mem reimplementation; TTMG full; ablations: `no_validity`, `no_supersede`, `no_abstain`, `no_linker` (4 ablations, all main-text).
- **Metric.** Intrinsic supersede F1 + hardness Brier + value-equivalence + fallback rate; downstream accuracy per stratum; paired McNemar; effect size Cohen's h.
- **Expected evidence.** TTMG ≥ Flat + 8 pp, ≥ A-Mem + 5 pp per stratum. `no_supersede` collapses on KU; `no_validity` collapses on TR; `no_abstain` shrinks correct-abstain to ≈ 0; `no_linker` collapses both to ≈ A-Mem. All intrinsic gates clear.

### Claim 2 (Supporting) — Routed-slice TR/KU wins + intrinsic audits clear + composed end-to-end reported

- **Statement.** On full LongMemEval-S (N=500, 3 seeds, deepseek-v3.2), routed-to-TTMG slice shows TTMG ≥ Flat with paired McNemar p<0.05 in TTMG's favor on combined TR + KU axis. Intrinsic router precision and recall ≥ 0.85 on 100-q audit. Key-fetch-fallback rate < 5% on full benchmark. Composed end-to-end accuracy reported per benchmark as deployer-relevant headline.
- **Minimal experiment.** 3 methods × 3 seeds (0, 7, 17) × 1 primary backbone (deepseek-v3.2) × N=500. Final-method robustness check on Qwen3-30B-A3B for {Flat, TTMG} only at seed=0 → appendix.
- **Baselines / ablations.** Flat; A-Mem; TTMG; same 4 ablations on controlled slice; `no_linker` only on controlled slice (compressed to appendix on full benchmark per reviewer simplification).
- **Metric.** Per-category accuracy; paired McNemar on routed-to-TTMG slice; correct-abstain at fixed accuracy on full n=30; applicability rate per slice; key-fetch-fallback rate per slice; composed end-to-end accuracy; tokens/q + latency reported but not primary.
- **Expected evidence.** Routed-to-TTMG TR + KU paired McNemar p<0.05. Applicability rate ~30–50% on LongMemEval-S; <15% on LoCoMo. Router precision and recall ≥ 0.85. Key-fetch-fallback < 5%. Correct-abstain on n=30 strictly > Flat. Overall LongMemEval within 5 pp of Flat (acknowledged scoped). Composed end-to-end TTMG-composed ≥ Flat on LongMemEval-S, ≈ Flat on LoCoMo (the diagnostic).

(MAX_PRIMARY_CLAIMS = 2 honored.)

## Experiment Handoff Inputs

- **Must-prove claims.** (1) Both controlled-slice strata strict dominance + linker intrinsic F1 + hardness Brier + value-equivalence + fallback rate; (2) Routed-to-TTMG TR + KU paired wins on full LongMemEval-S + composed end-to-end accuracy + intrinsic router/key-alignment audits clearing 0.85 + correct-abstain on full n=30.
- **Must-run ablations.** `no_validity`, `no_supersede`, `no_abstain`, `no_linker` (4, all main-text on controlled slice; `no_linker` on full benchmark moves to appendix per reviewer simplification).
- **Critical datasets / metrics.** Controlled supersede slice (~250q, two strata, human-audited); LongMemEval-S full N=500; full abstention n=30; LoCoMo (already run, reported as diagnostic); 100-q router audit; 60-q dev split (linker + writer + parser intrinsic gates + value-equivalence equivalence-class JSON).
- **Highest-risk assumptions.** (i) Writer LLM produces stable canonicalizable `claim_key` strings (audited). (ii) 3-call agreement gives meaningful hardness signal (Brier audited). (iii) Applicability router agrees with author labels at ≥ 0.85 precision/recall (audited). (iv) Key-fetch-fallback rate stays < 5% on LongMemEval-S (audited). (v) Multi-seed reproduces ablation directionality. (vi) `object_norm` granularity is right under equivalence-class protocol (audited).

## Compute & Timeline Estimate

- **Compute.** All inference via MAAS API; no local training. ≈ **30 GPU-hour-equivalents** on 1–2× RTX-4090 (unchanged).
- **Data / annotation cost.** Controlled slice writer + cross-check ≈ 2 h MAAS calls. Human audit total ≈ 7 h author time (4h slice audit + 1h router audit + 1h key-alignment audit + 1h equivalence-class JSON for value audit).
- **Timeline.**
  - **Week 1.** Schema extension (`claim_key`, `slot_type`, `object_norm`); canonicalizer + alias map; prompt-harden writer + linker + parser+router on dev; build + human-audit two-stratum controlled slice + 100-q router audit + 60-q key-alignment + author equivalence-class JSON; **all intrinsic gates clear**: linker F1 ≥ 0.7, Brier ≤ 0.2, key-precision/recall ≥ 0.85, router-precision/recall ≥ 0.85, value-equivalence disagreement ≤ 15%, fallback rate < 5%. **Lock router prompt; commit hash printed in paper.** Multi-seed pilot N=150 directionality.
  - **Week 2.** Full N=500 × 3 seeds × deepseek-v3.2 for {Flat, A-Mem, TTMG, 4 ablations}. Both controlled-slice strata × 3 seeds × 3 methods. Compute applicability rate, fallback rate, composed end-to-end accuracy per benchmark. Secondary-backbone robustness (Qwen3-30B-A3B, seed=0) for {Flat, TTMG} → appendix.
  - **Week 3.** Paper rewrite (round-3 framing: slot-scoped truth-maintenance semantics with audited applicability + all-optima abstention + canonical-key fetch); figures (router-coverage × accuracy plot, composed-vs-routed plot, per-stratum strict-dominance plot, per-ablation drop bar chart, Brier-calibration plot, fallback-rate histogram); statistical hardening (paired McNemar tables per slice + per stratum, abstain-correctness curves, Brier plot, value-equivalence histogram, key-fetch-fallback per slice); reconcile STATUS.md with reality; swap in real MemGPT (arXiv 2310.08560); cite-comparison rows with SimpleMem and LightMem.

(End of round-3 refinement.)
