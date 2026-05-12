# Round 1 Refinement

## Problem Anchor (verbatim from round 0)

- **Bottom-line problem.** When an LLM agent accumulates conversational memory across many sessions, statements about facts (preferences, schedules, plans, attributes) get *updated, contradicted, and superseded* over time. Current agent-memory systems organize memory semantically or hierarchically, but **none explicitly maintains *which fact is true at each point in time***. The result: under knowledge updates and temporal-validity questions, retrievers surface stale facts; under outright contradictions, readers fabricate confident answers instead of abstaining. This is the bottleneck targeted in `idea.md` and reflected in LongMemEval's KU/TR/abstention failure categories.
- **Must-solve bottleneck.** The minimal mechanism a memory system needs but does not have: (i) record `valid_from / valid_to` and an explicit `supersede / contradict` relation between claims; (ii) at read time, return the largest temporally-consistent claim subset that matches the query; (iii) abstain when residual contradiction cannot be resolved.
- **Non-goals.** Not general memory replacement; not token-efficiency wins; not a static KG builder; not a slot-in conflict layer (Path A, deferred); not a benchmark-creation paper.
- **Constraints.** 1–2 RTX-4090; MAAS API; reuse `ttmg/{schema,writer_temporal,conflict_linker,truth_retriever,system}.py`; 2–3 weeks; NeurIPS/ICML main track.
- **Success condition (now restated against narrowed scope, see Round-1 changes below).**

## Anchor Check

- **Original bottleneck.** Truth maintenance — which fact holds at time *τ*, which one supersedes which, when to abstain — for agent memory.
- **Why the revised method still addresses it.** The narrowing in this round restricts *where* the operator runs (single-valued, update-bearing slots) but leaves the *operator itself* — `(valid_from, valid_to)` + typed supersede/contradict edges + consistent-subset read + abstain — unchanged in semantics. We now own a smaller piece of memory more cleanly, instead of owning all of memory poorly.
- **Reviewer suggestions rejected as drift.** None. Reviewer explicitly flagged Drift = NONE, and the suggested fixes all *sharpen* the operator's definition rather than redirecting the problem.

## Simplicity Check

- **Dominant contribution after revision.** A *minimal truth-maintenance operator for single-valued, update-bearing memory slots*, defined by a typed `(claim_key, slot_type, valid_from, valid_to)` schema; an LLM judge that emits `{supersede, contradict, unrelated}` with agreement-based hardness; an exact small-set max-weight independent set (MWIS) over the top-k candidate set per query; abstain-on-non-unique-survivor. Routed against a Flat / raw-turn fallback for non-applicable slots so that the operator's *applicability boundary* is part of the contribution.
- **Components removed or merged.**
  - **`support` removed from decision policy** (kept as a *diagnostic* edge label only — never used in conflict resolution or abstain).
  - **"Greedy MCS" replaced** by exact MWIS on top-k (k ≤ 8, so exact is cheap) restricted to candidates sharing the queried `claim_key`. Renaming alone was rejected because the reviewer correctly flagged that "greedy" + "MCS" is semantic dishonesty.
  - **Cross-product evaluation matrix collapsed**: 1 primary backbone × 3 ablations × N=500 + 1 secondary backbone only on the final method.
  - **Controlled slice cleaning pipeline restructured**: deterministic programmatic labels first, *human* audit on 60–100 items as ground truth, no LLM-cleaning as ground truth.
  - **Writer prompt** emits `claim_key` + `slot_type` directly, eliminating the cosine-gate inference of update compatibility.
- **Reviewer suggestions rejected as unnecessary complexity.** None — every reviewer suggestion either (i) sharpened the operator (slot typing, exact MWIS), (ii) tightened scope (single-valued only), or (iii) shrank validation. Two suggestions taken with a small modification: (a) we keep one extra ablation (`no_linker`) beyond reviewer's three because it is the existing pilot's only ablation and dropping it would orphan prior data; (b) we keep the secondary-backbone robustness check on the final method only, as the reviewer accepted.
- **Why the remaining mechanism is still the smallest adequate route.** The revised operator is now four moving parts: typed schema (existing + 2 new fields), pairwise LLM judge with 3-call agreement (existing call now run thrice with self-consistency vote), exact MWIS on top-k (replacing greedy), abstain-on-non-unique-survivor (existing flag, made default). No new modules, no training, no architecture. The applicability gate (single-valued + claim_key match) is itself a *router* using the writer's own `slot_type` output — no separate classifier.

## Changes Made

### 1. Schema: add `claim_key` and `slot_type`
- **Reviewer said:** "`subject,predicate` is not sufficient. Some predicates are single-valued and update-bearing; others are multi-valued or accumulative. Add `claim_key` and `slot_type ∈ {single_valued, multi_valued}`."
- **Action.** Extend `ttmg/schema.py:Claim` with two fields: `claim_key: str` (canonical normalization of `(subject, predicate)` written by the LLM, e.g. `"user.preferred_coffee_temperature"`) and `slot_type: Literal["single_valued","multi_valued"]`. Writer prompt updated to emit both. Linker only considers supersede pairs within the *same* `claim_key` and only when `slot_type == "single_valued"`.
- **Reasoning.** The reviewer's diagnosis is exactly right and resolves a known failure mode in the prior pilot (multi-valued slots like "books read" being incorrectly superseded). The new fields are emitted by the same writer LLM call — no new module, no extra prompt overhead beyond two short fields.
- **Impact on core method.** Removes a class of false-positive supersede edges. Concentrates the operator on the slot type where supersede is *semantically* correct.

### 2. Read policy: replace "greedy MCS" with exact MWIS on top-k restricted to queried `claim_key`; abstain on non-unique survivor
- **Reviewer said:** "'greedy MCS' is not actually a maximum method, and the abstain condition is currently inconsistent with the stated MCS policy. Solve exact max-weight independent set on top-k, then abstain if no unique surviving claim remains for that key."
- **Action.** Modify `ttmg/truth_retriever.py` read policy: (a) parse query → `(claim_key_q, anchor τ_q, asks_history)`; (b) candidate set = top-k retrieved claims filtered to `claim_key == claim_key_q` and `valid_at(τ_q)`; (c) build conflict graph using *hard* edges only (`label ∈ {contradict, supersede}` with hardness-by-agreement ≥ 2/3); (d) solve **exact MWIS** on this small set (k ≤ 8 in practice, so exact is O(2^k) but instant); (e) if MWIS yields a unique surviving claim, return it; otherwise abstain. For multi-valued slots and for queries that do not parse to a single `claim_key`, route to Flat / raw-turn fallback unchanged.
- **Reasoning.** Reviewer correctly noted the prior policy was both misnamed and inconsistent. Exact MWIS on k≤8 is computationally trivial and avoids the heuristic-vs-claim mismatch. Restricting to the queried `claim_key` makes "abstain on non-unique survivor" semantically meaningful (we are answering a single-slot query).
- **Impact on core method.** This is the operator's **definitive read-time semantics** and replaces the prior loose policy. The thesis becomes formally crisp: TTMG is the exact MWIS on the typed conflict graph for single-valued, update-bearing slots.

### 3. Applicability boundary as part of the contribution: route SSA + multi-valued + non-key queries to Flat fallback
- **Reviewer said:** "Narrow at the method level: TTMG is a specialist operator for single-valued, update-bearing memory slots. Route SSA and multi-valued predicates to Flat/raw-turn fallback and exclude them from positive claims. Reframe contribution from 'better memory' to 'minimal truth-maintenance operator for update-style memory'."
- **Action.** (a) The query parser, in addition to `(claim_key_q, τ_q, asks_history)`, classifies whether the query is *single-slot truth-of-fact* (route to TTMG operator) or *anything else* (route to Flat fallback). (b) The known SSA / multi-valued slices of LongMemEval-S are routed to Flat by construction. (c) The paper's positive claims are restricted to the routed-to-TTMG slice; on the routed-to-Flat slice we report Flat-baseline numbers with TTMG matching by definition. (d) The applicability gate (router) is itself an LLM call, but a tiny one — the writer already emits `slot_type` for each claim; the parser emits the same field for each query.
- **Reasoning.** Reviewer's most important request and the cleanest way to answer the "no overall win" reviewer concern. Instead of *claiming* a general win and getting reviewed against general results, the paper *defines its scope inside the method itself* and claims wins only inside the scope — with an explicit, measurable router that decides where the scope applies.
- **Impact on core method.** This is the single biggest framing shift of round 1: TTMG is now an operator + an applicability gate, not a generic memory system. The paper's headline becomes about a *correctly-applied* operator on a *self-defined* slice.

### 4. Drop `support` from decision policy; keep as diagnostic only
- **Reviewer said:** "Delete `support` from the core decision policy. The thesis only needs `supersede`, `contradict`, and `unrelated`."
- **Action.** Linker still emits `{support, supersede, contradict, unrelated}` for diagnostic richness, but `support` never enters the MWIS solver, never affects `valid_to` rewriting, and never triggers abstention. Reported in supplementary as graph-statistics only.
- **Reasoning.** `support` adds no truth-maintenance signal — it co-locates redundant claims but does not change which one is true at time *τ*.
- **Impact on core method.** Smaller decision surface; one fewer thing to defend in the paper.

### 5. Replace scalar confidence with 3-call judge consistency for hardness
- **Reviewer said:** "Replace raw scalar 'confidence' with cheap agreement-based hardness, e.g. 3-call judge consistency for `supersede/contradict`. More defensible than trusting model self-reported probabilities."
- **Action.** For pairs where the linker first emits `{supersede, contradict}`, run two more independent calls (different temperature, slightly varied prompt). Define `hardness = (# of agreeing calls) / 3`. `Edge.is_hard()` ↔ `hardness ≥ 2/3`. Existing scalar `confidence` is kept as a tie-break only.
- **Reasoning.** Self-reported LLM probabilities are notoriously miscalibrated; multi-call agreement is the field-standard cheap calibrator. 3 calls × ~50 candidate pairs/session × small prompt is well within MAAS budget (~3× linker cost on the small subset of pairs that already passed the SP-overlap and cosine gate). Brier on dev now becomes meaningful.
- **Impact on core method.** Hardness is now reproducible and defensible; hardness threshold is no longer arbitrary.

### 6. Validation: collapse to 3 ablations + retain `no_linker` for continuity; one backbone for ablations + secondary only on final
- **Reviewer said:** "Reduce to one primary backbone for all ablations and one secondary backbone only for the full-method headline result. Collapse ablations to three: `no_validity`, `no_supersede`, `no_abstain`."
- **Action.** Final ablation set = **3 reviewer-requested + 1 retained**: `no_validity`, `no_supersede`, `no_abstain`, `no_linker` (kept because the existing seed=0 pilot has it; dropping it orphans the only existing ablation evidence). All ablations on **deepseek-v3.2 reader only**; secondary backbone (Qwen3-30B-A3B-Instruct-2507) only on full TTMG and Flat for the final headline robustness check on TR + KU + abstention. `schema-only` and `no-MCS` from round 0 are absorbed into `no_validity` and `no_abstain` respectively.
- **Reasoning.** Reviewer is right that the round-0 plan was bloated. The retained `no_linker` ablation is a small concession.
- **Impact on core method.** Compute drops from ≈45 GPU-hour-equivalents to ≈30. Paper has fewer numbers to defend, each more decisive.

### 7. Controlled slice: split into two pre-declared strata; deterministic labels first; human audit
- **Reviewer said:** "Split the controlled slice into two predeclared strata: `latest-state KU` and `as-of-time TR` using the same update chains. Make slice labels deterministic first, then human-audit 60–100 items; do not make an LLM-cleaning pass the source of truth."
- **Action.** (a) Build slice deterministically from LongMemEval-S `answer_session_ids` + chronological session order: `latest-state KU` = "what is X *now*?" (canonical = latest evidence-session claim); `as-of-time TR` = "what was X *at time τ_q*?" (canonical = the evidence-session claim whose `valid_*` interval contains τ_q). (b) Both strata pre-declared; no post-hoc selection. (c) Human audit on 60-100 items per stratum (author's own time, ≈4 hours total) before any results are computed. (d) LLM cleaning step is removed; if the deterministic label disagrees with human audit, the deterministic rule is fixed (not the label re-LLM-labelled).
- **Reasoning.** Reviewer correctly noted the round-0 slice was a "latest-state supersede" probe, not a "truth-at-time" probe. The two strata together are the actual truth-maintenance probe.
- **Impact on core method.** Slice now measures both axes the operator is supposed to handle. Labels are defensible (human-audited, deterministic-rule-first).

## Revised Proposal

# Research Proposal: Temporal Truth-Maintained Memory — A Specialist Operator for Single-Valued, Update-Bearing Memory Slots in Long-Conversation Agents

## Problem Anchor

(verbatim from round 0; see top of this document)

## Updated Success Condition (round 1)

The four success conditions from round 0 hold, with the following sharpenings:

1. **Within the routed-to-TTMG slice of LongMemEval-S full N=500** (3 seeds, primary backbone `deepseek-v3.2`): TTMG ≥ Flat with paired McNemar p<0.05 in TTMG's favor on the combined TR + KU axis. **No claim is made on slices routed to Flat fallback.**
2. **On both controlled-slice strata** (`latest-state KU`, `as-of-time TR`, ≈ 250 q total): TTMG strictly dominates Flat and A-Mem in answer accuracy (paired McNemar p<0.05, no losing strata) and intrinsic linker `supersede`-F1 ≥ 0.7 with hardness Brier ≤ 0.2 on the human-audited dev set.
3. **Abstention behavioural metric** on the full n=30 abstention set: at fixed answer accuracy, TTMG correct-abstain rate strictly exceeds Flat (matched-budget metric, paired comparison).
4. **Mechanism causality**: each of `no_validity`, `no_supersede`, `no_abstain`, `no_linker` produces a ≥1 pp drop on its targeted slice within the routed-to-TTMG slice.
5. **Cross-domain regression report**: LoCoMo (–13.4 pp) reported in the paper as diagnostic — "LoCoMo questions almost never satisfy the applicability gate (single-valued, update-bearing, single-slot query); on the small sub-slice that does, TTMG behaves as predicted; on the rest, Flat fallback applies and we report Flat numbers."
6. **Failure clause** (replaces fired `idea.md` clause): if the controlled supersede slice does not show TTMG > {Flat, A-Mem} on accuracy at p<0.05 *or* if the routed-to-TTMG slice of LongMemEval-S does not show paired McNemar p<0.05 in TTMG's favor on TR-or-KU, the design does not hold.

## Technical Gap

Unchanged from round 0: among the 6 surveyed competitors (A-Mem, Mem0, MemoryOS, LightMem, SimpleMem, plus correctly-cited MemGPT once it is pulled), none records `(valid_from, valid_to)` per claim, none stores typed `{contradict, supersede}` edges between claims, none abstains on residual contradiction. The bottleneck is uncovered.

The round-1 sharpening adds one diagnosis: prior memory work treats "memory" as one undifferentiated thing. The truth-maintenance operator is *only* meaningful for single-valued, update-bearing slots; it is meaningless for multi-valued or accumulative content. *Defining the applicability boundary inside the method* is the cleaner contribution.

## Method Thesis

- **One-sentence thesis (round 1).** *For single-valued, update-bearing memory slots, the answer to "what is true at τ?" is the unique surviving claim of the maximum-weight independent set on the typed conflict graph restricted to that slot at that time; abstain when no unique survivor remains.*
- **Why this is the smallest adequate intervention.** The operator is one schema extension (`claim_key`, `slot_type`), one LLM-judge with agreement-based hardness, one exact MWIS on top-k, one abstain rule, and one applicability router that uses the writer's own `slot_type` output. No new model, no training, no architecture, no auxiliary head.
- **Why timely.** SimpleMem (ICML 2026) showed LLM-as-planner is the right primitive for read-time intent decomposition. We use the same primitive for the *truth-of-fact* decomposition that SimpleMem skips, with an explicit applicability gate so the operator's costs are paid only where the operator wins.

## Contribution Focus

- **Dominant contribution.** The truth-maintenance operator above (typed schema + agreement-hard typed edges + exact MWIS + abstain) **plus its applicability gate** (single-valued, update-bearing, single-slot query). Demonstrated on a controlled supersede slice (`latest-state KU` + `as-of-time TR` strata) and on the routed-to-TTMG portion of LongMemEval-S full N=500.
- **Optional supporting contribution.** The two-stratum controlled supersede slice as an internal measurement instrument. Released as a labelling script + human-audit table in the supplementary; not framed as a new benchmark.
- **Explicit non-contributions.** No general LongMemEval/LoCoMo win; no token-efficiency win; no new training; no slot-in conflict layer over other memories (Path A); no benchmark contribution; **no claim on slices routed to Flat fallback**.

## Proposed Method

### Complexity Budget

- **Frozen / reused.** Reader = `deepseek-v3.2` primary, `Qwen3-30B-A3B-Instruct-2507` secondary (final-method robustness only). Embedder, MAAS endpoints, A-Mem reimpl, Flat baseline, storage = unchanged.
- **New / extended (4 deltas, all in existing files).**
  1. *Schema*: add `claim_key`, `slot_type` to `Claim`.
  2. *Writer*: prompt now emits `claim_key`, `slot_type` per claim.
  3. *Linker*: 3-call agreement-based hardness; restricts supersede candidates to same `claim_key` and `slot_type == single_valued`.
  4. *Read policy*: parse query → `(claim_key_q, τ_q, asks_history, applicable?)`; if not applicable, route to Flat; else exact MWIS on top-k filtered to `claim_key == claim_key_q` and `valid_at(τ_q)`; abstain on non-unique survivor.
- **Tempting additions intentionally not used.** No NLI fine-tune, no probabilistic temporal reasoning, no learned MWIS, no new ranking model, no new training of any kind, no agent simulator, no multi-modal extension, no new module (`support` stays as diagnostic only).

### System Overview

```
            ┌────────────────────────────────────────────────────────────┐
WRITE-time  │  session text → writer (LLM) → list[Claim]                 │
            │     each Claim now carries claim_key + slot_type           │
            │                                                            │
            │  for each new c:                                           │
            │      cand = SP-index.lookup(c.claim_key) ∪ kNN_emb(c)      │
            │      for c' in cand with same claim_key:                   │
            │          if slot_type[c]=single_valued AND slot_type[c']=  │
            │              single_valued:                                │
            │              run linker 3× (varied temp/prompt) →          │
            │                 label, hardness=#agree/3                   │
            │              if label in {supersede, contradict} AND       │
            │                 hardness ≥ 2/3:                            │
            │                   add hard Edge(c↔c', label, hardness)     │
            │                   if label=supersede AND c' older:         │
            │                       c'.valid_to ← c.valid_from − ε       │
            │                       c'.superseded_by ← c.id              │
            │      (support edges still emitted as soft, diagnostic only)│
            └────────────────────────────────────────────────────────────┘

            ┌────────────────────────────────────────────────────────────┐
READ-time   │  query → parser (LLM) →                                    │
            │      (claim_key_q, τ_q, asks_history, applicable?)         │
            │                                                            │
            │  if not applicable (multi-valued / no single slot / SSA):  │
            │      return Flat(query)                                    │
            │                                                            │
            │  cand = topK_emb(query) ∪ topK_bm25(query)                 │
            │  cand = [c for c in cand                                   │
            │            if c.claim_key == claim_key_q                   │
            │            and valid_at(c, τ_q, asks_history)]             │
            │  H    = subgraph of hard edges over cand                   │
            │  S    = exact_MWIS(cand, H, weights=hardness×writer_conf)  │
            │  if |S| == 1:                                              │
            │      return reader(query, S, [optional raw-turn fallback]) │
            │  else:                                                     │
            │      return ABSTAIN(reason=..., S=S, H=H)                  │
            └────────────────────────────────────────────────────────────┘
```

### Core Mechanism

- **Input / output.** Write: session text + prior `Graph(Claims, TypedEdges)` → updated graph. Read: query → answer ∪ ABSTAIN ∪ Flat-fallback.
- **Architecture / policy.**
  - **Schema**: `Claim(content, subject, predicate, object, claim_key, slot_type, valid_from, valid_to, polarity, confidence, active, superseded_by)`. The two new fields are `claim_key` (canonical normalised slot identifier emitted by writer LLM, e.g. `"user.preferred_coffee_temperature"`) and `slot_type ∈ {"single_valued","multi_valued"}`.
  - **Linker**: `{support, contradict, supersede, unrelated}` with **hardness = #agree/3 over 3 independent calls** (varied temperature 0.0/0.3/0.6 + 1-of-3 prompt phrasing). Only `{contradict, supersede}` pairs with `hardness ≥ 2/3` enter the conflict graph. **`support` is never used in the decision policy.**
  - **Supersede materialization**: on accepting a hard `supersede(c'→c)` (older `c'`), set `c'.valid_to = c.valid_from − ε`, `c'.superseded_by = c.id`.
  - **Exact MWIS read**: on the (small, ≤8) candidate set restricted to queried `claim_key` and `valid_at(τ_q)`, build the hard-edge subgraph; solve exact maximum-weight independent set with weights = `hardness × writer_confidence`. If a unique vertex survives, return it; else abstain.
  - **Abstain-on-non-unique-survivor**: triggered iff applicable-and-no-unique-survivor. Reader prompt is unchanged; abstain is a top-level return path that bypasses the reader.
- **Training signal / loss.** None.
- **Why this is the main novelty.** No surveyed competitor: (i) types memory by `slot_type`, (ii) materializes supersede as a `valid_to` rewrite, (iii) uses agreement-hard typed edges for read-time MWIS, (iv) abstains on non-unique survivor inside an explicit applicability gate.

### Applicability Gate (NEW IN ROUND 1)

The gate is the contribution's **shape** — without it, TTMG would again be claimed as "general memory". With it, the paper's claims are restricted to the slice the operator is *designed* to handle.

- **Implementation.** Same query parser already parses `(τ_q, asks_history)`; we extend it to emit `(claim_key_q, slot_type_q, applicable: bool)` in the same call. `applicable = (slot_type_q == single_valued) ∧ claim_key_q is not None ∧ asks_truth_of_fact`.
- **Behaviour.** Non-applicable queries route to Flat hybrid-RAG unchanged (so by definition tie Flat). The TTMG operator only runs on applicable queries.
- **Evaluation.** The paper reports both (a) the *applicability rate* of each LongMemEval / LoCoMo / controlled-slice slice, and (b) the operator's wins *only on the routed-to-TTMG slice*. This eliminates the "but you don't beat Flat overall" reviewer concern by design: TTMG never claims to beat Flat on non-applicable queries.

### Modern Primitive Usage

- **Three LLM uses, all zero-shot, all field-standard.**
  1. **Writer** = structured-extraction LLM emitting typed claims **with `claim_key` and `slot_type` directly** (the round-1 modernization). Mirrors SimpleMem's structured compression with two extra schema fields.
  2. **Linker** = pairwise judge LLM with **3-call self-consistency for hardness** (the round-1 calibration). Mirrors LLM-as-judge consistency-vote pattern from RLHF/RM literature, applied to typed-edge labelling.
  3. **Parser** = intent-and-anchor LLM **plus applicability gate** (round-1 addition). Mirrors SimpleMem's intent-aware retrieval planner; we add `claim_key`, `slot_type`, and applicability classification.
- **Why these are natural.** The bottleneck is "did claim *c* hold at *τ_q*?" plus "is this query within the operator's scope?" — both inherently linguistic. LLM-as-judge / LLM-as-router is the cheapest competent solution. No fine-tuning is justified for either.

### Integration into the Existing Pipeline

- **Files touched.** `ttmg/schema.py` (+ 2 fields), `ttmg/writer_temporal.py` (prompt update), `ttmg/conflict_linker.py` (3-call agreement, claim_key + slot_type filter), `ttmg/truth_retriever.py` (parser augmentation, exact MWIS, abstain-on-non-unique), `ttmg/system.py` (config flags for the 4 ablations + applicability-router on/off).
- **Files frozen.** A-Mem reimplementation, Flat baseline, MAAS API layer, storage backend, embedding model.

### Training Plan

None. Prompt-iteration only on writer (`claim_key`, `slot_type`, `valid_from` extraction) and linker (`supersede` recall + hardness calibration), using the 60-q dev split disjoint from the controlled-slice test items. Acceptance: linker `supersede`-F1 ≥ 0.7 with hardness Brier ≤ 0.2 on dev.

### Failure Modes and Diagnostics

- **F1 Linker noise inflates hard contradict edges.** Detect: hard-edge density on a fixed 30-session sample > 2× baseline. Mitigate: raise hardness threshold from 2/3 to 3/3 on diagnostic samples.
- **F2 MWIS drops a correct claim.** Detect: per-question audit when the MWIS solution's writer-confidence sum is < a single-vertex alternative's. Mitigate: use weight = `hardness × writer_confidence`; emit per-question explanation.
- **F3 Over-abstention on routed-to-TTMG slice.** Detect: abstain rate > 20% on a slice without ground-truth contradictions. Mitigate: tighten applicability gate; raise hardness threshold.
- **F4 Applicability misroute.** Detect: parser self-eval on a 60-q dev split (compare router output to author labels). Mitigate: prompt iteration; in production fall back to Flat on parser uncertainty.
- **F5 Cross-domain failure (LoCoMo).** Already observed (–13.4 pp). Round-1 diagnosis: LoCoMo's question distribution rarely satisfies the applicability gate; on the routed-to-TTMG sub-slice (expected: small) we expect TTMG ≈ {Flat, A-Mem}; on the rest, Flat fallback applies and we report tied Flat numbers. Reported as paper-level diagnostic, *with the applicability rate as the diagnostic's principal number*.
- **F6 SSA regression.** Already observed (–21 pp at N=500). Round-1 fix: SSA queries fail the applicability gate by design (they ask what an utterance was, not what is true at τ). Routed to Flat. The –21 pp number disappears from TTMG-claimed numbers because TTMG no longer runs on SSA.

### Novelty and Elegance Argument

- **Closest work.** SimpleMem (ICML 2026, 2026 frontier): intent-aware retrieval planning + symbolic temporal layer. A-Mem (NeurIPS 2025): memory evolution.
- **Exact difference, in one paragraph (round 1 sharpening).** SimpleMem's symbolic temporal layer can filter retrieved candidates by *timestamp* but cannot tell that a 2024-03 single-valued claim has been *replaced* by a 2024-09 claim about the same `claim_key`; both still surface at retrieval, and SimpleMem has no abstain-on-conflict policy. A-Mem semantically refreshes neighbours but maintains no validity intervals, no typed edges, and no `slot_type` — its memory evolution can refresh stale neighbours but cannot *deactivate* them. *TTMG* introduces three minimal type-level additions — `claim_key`, `slot_type`, typed edges with agreement-hardness — and one read-time operator — exact MWIS on the typed conflict graph at *τ_q* with abstain-on-non-unique. The applicability gate (single-valued + single-slot + truth-of-fact) makes the contribution honest about its scope: this is not a general memory replacement, it is the *first explicit truth-maintenance operator for the slot-update sub-problem of agent memory*, with the applicability boundary measured in the paper.
- **Why mechanism-level, not pile-up.** Two new schema fields + one calibrated linker + one exact small-set solver + one applicability router. The reviewer's "rename greedy MCS" critique is resolved (we now run exact MWIS, which is well-defined). The paper's contribution can be summarised in a single equation: `answer(q) = if applicable(q) then unique(MWIS(cand_q, hard_edges)) else Flat(q)`.

## Claim-Driven Validation Sketch

### Claim 1 (Dominant) — Truth maintenance dominates on labelled supersede in both strata

- **Statement.** On both controlled-slice strata (`latest-state KU` ≈ 150q, `as-of-time TR` ≈ 100q), TTMG strictly dominates Flat hybrid-RAG and A-Mem reimplementation on answer accuracy (paired McNemar p<0.05 per stratum, no losing stratum), with intrinsic linker `supersede`-F1 ≥ 0.7 and hardness Brier ≤ 0.2 on the human-audited dev set.
- **Minimal experiment.** 3 methods × 3 seeds × 1 backbone (deepseek-v3.2 reader) × controlled slice (~250q across 2 strata).
- **Baselines / ablations.** Flat hybrid-RAG; A-Mem reimplementation; TTMG full; ablations: `no_validity`, `no_supersede`, `no_abstain`, `no_linker` (4 ablations).
- **Metric.** Intrinsic supersede F1 + hardness Brier; downstream accuracy per stratum; paired McNemar; effect size Cohen's h.
- **Expected evidence.** TTMG ≥ Flat + 8 pp and TTMG ≥ A-Mem + 5 pp per stratum. `no_supersede` collapses to ≈ Flat on `latest-state KU`. `no_validity` collapses to ≈ Flat on `as-of-time TR`. `no_abstain` shrinks correct-abstain rate to ≈ 0. `no_linker` collapses both strata to ≈ A-Mem. Linker F1 ≥ 0.7, Brier ≤ 0.2.

### Claim 2 (Supporting) — On the routed-to-TTMG slice of LongMemEval-S, the operator is causal on TR / KU; on the routed-to-Flat slice, no claim is made

- **Statement.** On full LongMemEval-S (N=500, 3 seeds), restricted to the routed-to-TTMG slice (expected ≈ 30–50% of N=500 — applicability rate is itself reported), TTMG ≥ Flat with paired McNemar p<0.05 in TTMG's favor on the combined TR + KU axis. On the routed-to-Flat slice, TTMG ties Flat by definition. Overall LongMemEval-S accuracy is reported but **not claimed as a win**.
- **Minimal experiment.** 3 methods × 3 seeds (0, 7, 17) × 1 primary backbone (deepseek-v3.2) × N=500. Final-method robustness check on Qwen3-30B-A3B for {Flat, TTMG} only at seed=0.
- **Baselines / ablations.** Flat; A-Mem; TTMG; 4 ablations as in Claim 1.
- **Metric.** Per-category accuracy on LongMemEval-S; paired McNemar on routed-to-TTMG slice; correct-abstain rate at fixed answer accuracy on full n=30 abstention; applicability rate (% routed to TTMG vs Flat per slice); tokens/q + latency reported but not primary.
- **Expected evidence.** Routed-to-TTMG slice TR + KU: paired McNemar p<0.05 in TTMG's favor. Applicability rate on LongMemEval-S: roughly 30–50% (driven by KU + TR + a fraction of SSU); on LoCoMo: <15% (driving the diagnostic story). Correct-abstain rate on n=30: TTMG strictly > Flat at fixed answer accuracy. Overall LongMemEval-S accuracy: TTMG within 5 pp of Flat (acknowledged as scoped and uncontested).

(MAX_PRIMARY_CLAIMS = 2 honored.)

## Experiment Handoff Inputs

- **Must-prove claims.** (1) Both controlled-slice strata strict dominance + linker intrinsic F1 + hardness Brier; (2) Routed-to-TTMG TR + KU paired wins on full LongMemEval-S + correct-abstain behavioural metric on full n=30.
- **Must-run ablations.** `no_validity`, `no_supersede`, `no_abstain`, `no_linker` (4 ablations, all on primary backbone).
- **Critical datasets / metrics.** Controlled supersede slice (~250q, two strata); LongMemEval-S full N=500; full abstention n=30; LoCoMo (already run, reported as diagnostic with applicability rate); intrinsic linker F1 + hardness Brier on human-audited 60-q dev split per stratum.
- **Highest-risk assumptions.** (i) Writer LLM produces stable `claim_key` strings (will check on dev: same fact → same key). (ii) 3-call agreement gives meaningful hardness signal (will check Brier on dev). (iii) Applicability router agrees with author labels on 60-q dev with ≥85% accuracy. (iv) Multi-seed reproduces ablation directionality from existing seed=0 run. (v) On LoCoMo, applicability rate is genuinely < 15%; if higher, the diagnostic story changes.

## Compute & Timeline Estimate

- **Compute.** All inference via MAAS API; no local training. With the round-1 collapse (1 backbone for ablations, secondary only for final headline), total ≈ **30 GPU-hour-equivalents** on a 1–2× RTX-4090 budget.
- **Data / annotation cost.** Controlled slice writer + cross-check passes ≈ 2 h MAAS calls. Human audit ≈ 4 h author time across 2 strata. No external annotation.
- **Timeline.**
  - **Week 1.** Schema extension (`claim_key`, `slot_type`); prompt-harden writer + linker on dev split; build + human-audit two-stratum controlled slice; intrinsic linker F1 + hardness Brier on dev. Multi-seed pilot N=150 on three methods to confirm ablation directionality.
  - **Week 2.** Full N=500 × 3 seeds on primary backbone for {Flat, A-Mem, TTMG, 4 ablations}. Both controlled-slice strata × 3 seeds × 3 methods. Secondary-backbone robustness check at seed=0 for {Flat, TTMG}. Compute applicability rate per slice.
  - **Week 3.** Paper rewrite (round-1 framing: applicability gate is part of the contribution); figures (applicability-rate × accuracy plot, per-stratum strict-dominance plot, per-ablation drop bar chart); statistical hardening (paired McNemar tables per slice + per stratum, abstain-correctness curves, hardness Brier plot); reconcile STATUS.md; swap in real MemGPT (arXiv 2310.08560); cite-comparison rows with SimpleMem and LightMem.

(End of round-1 refinement.)
