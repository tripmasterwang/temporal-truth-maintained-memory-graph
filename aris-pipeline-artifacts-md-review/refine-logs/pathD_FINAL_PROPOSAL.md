# Research Proposal: Slot-Scoped Truth-Maintenance Semantics for Agent Memory — A Specialist Operator with an Audited Applicability Gate

## Problem Anchor

- **Bottom-line problem.** When an LLM agent accumulates conversational memory across many sessions, statements about facts (preferences, schedules, plans, attributes) get *updated, contradicted, and superseded* over time. Current agent-memory systems organize memory semantically or hierarchically, but **none explicitly maintains *which fact is true at each point in time***. The result: under knowledge updates and temporal-validity questions, retrievers surface stale facts; under outright contradictions, readers fabricate confident answers instead of abstaining.
- **Must-solve bottleneck.** (i) record `valid_from / valid_to` and an explicit `supersede / contradict` relation between claims; (ii) at read time, return the largest temporally-consistent claim subset that matches the query; (iii) abstain when residual contradiction cannot be resolved.
- **Non-goals.** Not a general-purpose memory replacement; not a token-efficiency win; not a static knowledge-graph builder; not a slot-in conflict layer over other memories (Path A, deferred); not a benchmark-creation paper.
- **Constraints.** 1–2 RTX-4090-class GPUs; MAAS API for writer/parser/reader (no Agent tool); reuse `ttmg/{schema, writer_temporal, conflict_linker, truth_retriever, system}.py`; 2–3 weeks; NeurIPS / ICML main track.

## Success Conditions

1. Within the routed-to-TTMG slice of LongMemEval-S full N=500 (3 seeds, primary backbone `deepseek-v3.2`): TTMG ≥ Flat with paired McNemar p<0.05 in TTMG's favor on the combined TR + KU axis.
2. On both controlled-slice strata (`latest-state KU` ≈150 q, `as-of-time TR` ≈100 q): TTMG strictly dominates Flat and A-Mem (paired McNemar p<0.05 per stratum, no losing stratum); intrinsic linker `supersede`-F1 ≥ 0.7; hardness Brier ≤ 0.2; value-equivalence disagreement ≤ 15 % under author-defined equivalence-class protocol.
3. Full n=30 abstention: TTMG correct-abstain rate strictly > Flat at fixed answer accuracy.
4. Mechanism causality: each of `no_validity`, `no_supersede`, `no_abstain`, `no_linker` produces ≥ 1 pp drop on its targeted slice within the routed-to-TTMG slice.
5. Cross-domain regression: LoCoMo applicability rate < 15 %; on the routed-to-TTMG sub-slice TTMG behaves as predicted; composed end-to-end accuracy reported.
6. Intrinsic router audit: precision and recall ≥ 0.85 each on a 100-q author-labeled audit set, measured *before* test-time runs.
7. Intrinsic key alignment audit: writer-key-precision and parser-key-recall ≥ 0.85 each on the 60-q dev set, *before* test-time runs.
8. Composed end-to-end accuracy reported alongside routed-slice claims on every benchmark.
9. Key-fetch-fallback rate reported on every benchmark; expected ≤ 5 % on LongMemEval-S; > 5 % triggers extended canonicalizer iteration *before lock*.
10. Failure clause: design fails if (a) controlled-slice TTMG > {Flat, A-Mem} at p<0.05 fails on either stratum, OR (b) routed-to-TTMG TR-or-KU paired McNemar p<0.05 fails on full LongMemEval-S, OR (c) intrinsic router or key-alignment audits fail to clear 0.85, OR (d) value-equivalence disagreement > 15 % on dev.

## Technical Gap

Among the 6 surveyed competitors (A-Mem NeurIPS 2025, Mem0, MemoryOS, LightMem ICLR 2026, SimpleMem ICML 2026; the actual MemGPT — arXiv 2310.08560 — to be re-pulled), none records `(valid_from, valid_to)` per claim, none stores typed `{contradict, supersede}` edges between claims, none abstains on residual contradiction. SimpleMem's symbolic temporal layer holds timestamps but not validity intervals or supersede pointers; A-Mem's "memory evolution" is semantic refresh, not validity tracking. The bottleneck above lives in this exact uncovered region.

The round-1–3 sharpening adds one diagnosis: prior memory work treats memory as one undifferentiated thing. The truth-maintenance operator is *only* meaningful for single-valued, update-bearing slots; defining the applicability boundary inside the method is the cleaner contribution.

**Why naive bigger systems are insufficient.** Larger context, more retrieval, better embeddings: all leave the reader with both stale and current candidates. SimpleMem's intent planner classifies *what kind of question* is asked but does not track *which stored fact is currently true*. A timestamp-aware re-ranker without supersede labels returns both old and new top-k. Without a value-level abstention rule, a reader will pick one of the conflicting candidates and present it confidently.

## Method Thesis

*For single-valued, update-bearing memory slots, the answer to "what is the value of slot s for entity e at time τ?" is the unique normalized value that survives across **all** maximum-weight independent sets of the typed conflict subgraph at time τ; the system abstains when any optimal independent set disagrees on the value, and applies only when an audited query-side router declares the query in-scope.*

- **Why smallest adequate.** Three schema fields (`claim_key`, `slot_type`, `object_norm`), one writer prompt change, one canonicalizer (deterministic post-processor), one linker with 3-call agreement, one all-optima MWIS enumerator (k ≤ 8), one applicability router (sharing the parser call). No new model, no training, no architecture, no auxiliary head.
- **Why timely.** Same LLM-as-structurer / judge / router primitives validated by SimpleMem (ICML 2026) and LightMem (ICLR 2026), applied to the truth-of-fact sub-problem with *adversarially-correct* abstention semantics absent in any surveyed competitor.

## Contribution Focus

- **Dominant contribution.** *Slot-scoped truth-maintenance semantics for agent memory with all-optima abstention*: typed schema with canonical `(entity_id, slot_name)` keys + normalized values + validity intervals + agreement-hard typed `{contradict, supersede}` edges + the all-optima MWIS-agreement decision rule; gated by an audited locked applicability router; retrieved via deterministic canonical-key fetch on the applicable path. Intrinsic router audit, intrinsic key-alignment audit, value-equivalence audit, and key-fetch-fallback rate reported as first-class numbers.
- **Optional supporting contribution.** Two-stratum controlled supersede slice + author-defined value-equivalence classes as internal measurement instruments (released as labelling script + JSON in supplementary).
- **Explicit non-contributions.** Not a general LongMemEval/LoCoMo win; not a token-efficiency win; not new training; not Path-A slot-in; not a benchmark contribution; not a contribution about MWIS or canonical-key fetch in isolation (both are mechanisms, not novelties); **no claim on routed-to-Flat slice**.

## Proposed Method

### Complexity Budget

- **Frozen / reused.** Reader = `deepseek-v3.2` primary; embedder, MAAS endpoints, A-Mem reimplementation, Flat baseline, storage = unchanged. `Qwen3-30B-A3B-Instruct-2507` used in appendix only.
- **5 deltas, all in existing or one new file.**
  1. *Schema*: add `claim_key=(entity_id, slot_name)`, `slot_type ∈ {single_valued, multi_valued}`, `object_norm: str` to `Claim`.
  2. *Writer*: prompt now emits all three new fields per claim.
  3. *Canonicalizer* (NEW file `ttmg/canonicalize.py`): deterministic post-processor (lowercase + lemma + static alias map ≤ 200 entries) applied after both writer and parser to make `claim_key` canonical.
  4. *Linker*: 3-call agreement-based hardness; supersede only within same canonical `claim_key` and `slot_type==single_valued`; label set reduced to `{contradict, supersede, unrelated}`.
  5. *Read policy*: parser emits `(claim_key_q, slot_type_q, τ_q, asks_history, applicable?)`; if not applicable → Flat; else canonical-key fetch + time filter, then **all-optima MWIS** enumeration; answer iff every optimum induces the same `object_norm`; else abstain. Hybrid retrieval kept only as logged fallback when canonical-key fetch returns 0.
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
            │      cand = SP-index.fetch_all(c.claim_key)                │
            │      for c' in cand with same canonical claim_key:         │
            │          if slot_type[c]=slot_type[c']=single_valued:      │
            │              labels   = [linker(c,c'; T=t, prompt=p)       │
            │                          for (t,p) in 3 variants]          │
            │              hardness = max_l |[L=l for L in labels]| / 3  │
            │              top_label= mode(labels)                       │
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
- **Canonicalizer.** Deterministic post-processor: lowercase + lemma + static alias map (≤200 entries built incrementally on dev). Applied after both writer and parser. Result: `claim_key` strings are byte-equal across write and read sides whenever they refer to the same slot.
- **Linker.** `{contradict, supersede, unrelated}` only. Hardness = max-agreement-fraction across 3 calls (varied temperature 0.0/0.3/0.6 + 1-of-3 prompt phrasing). Edge admitted iff label ∈ `{contradict, supersede}` AND hardness ≥ 2/3.
- **Supersede materialization.** On accepting hard `supersede(c'→c)` (older `c'`), set `c'.valid_to = c.valid_from − ε`, `c'.superseded_by = c.id`.
- **Canonical-key fetch.** On applicable queries, `SP_index.fetch_all(claim_key_q)` returns *all* claims with the canonicalized key. No top-k truncation on the applicable path. Hybrid retrieval is fallback only (logged).
- **All-optima MWIS rule.** With k ≤ 8, enumerate all subsets (≤ 256), filter to independent ones (no hard edge between any pair), keep max-weight subsets, collect all `object_norm`s appearing in any such subset. **Answer iff `|Vals| == 1`; else abstain.** Note: weights still define the optimal-set family; they no longer act as an arbitrary tie-break loophole.
- **Why this is the main novelty.** No surveyed competitor: (i) types memory by `slot_type`, (ii) materializes supersede as a `valid_to` rewrite, (iii) uses agreement-hard typed edges with all-optima MWIS abstention, (iv) gates the operator with an *audited locked* applicability router, (v) fetches via canonical key on the applicable path. The novelty is the *semantics* (slot-scoped truth-maintenance + adversarially-correct abstention), not the solver.

### Applicability Gate (locked + intrinsically audited)

- Same parser call extended to emit `(claim_key_q, slot_type_q, applicable: bool)`. `applicable = (slot_type_q == single_valued) ∧ (claim_key_q is not None) ∧ asks_truth_of_fact`.
- **Locking protocol.** Router prompt + post-processor + decision rule frozen at end of Week 1, committed to git with hash, hash printed in paper. No test-time change.
- **Intrinsic audit.** 100-q author-labeled set (50 LongMemEval-S, 50 LoCoMo) author-labeled in 1 hour. Router-precision, router-recall ≥ 0.85 each, reported as headline. If failed → prompt iteration *before lock*; once locked, no further changes.
- **Composed end-to-end reporting.** Every results table includes three numbers per benchmark: (a) applicability rate, (b) routed-to-TTMG accuracy, (c) composed end-to-end accuracy = `(routed-to-TTMG-acc × applicability-rate) + (Flat-on-rest × (1 − applicability-rate))`. Column (c) is the deployer-relevant number.

### Object-norm Audit Protocol

- For each of 60 dev questions, the author manually defines an equivalence class `E_q ⊆ {strings}` enumerating acceptable normalized values (e.g. `{"hot","warm-hot","piping_hot"}`).
- The system's `object_norm` is *disagreeing* iff `object_norm ∉ E_q`. The author class is the source of truth.
- Audit metric: `value_equivalence_disagreement = #(disagreeing answers) / #(answers given)`. Target ≤ 15 % on the 60-q dev.
- Released as small JSON in supplementary; intrinsic, reproducible, cheap (~1 h author time).

### Modern Primitive Usage

Three LLM uses, all zero-shot, all field-standard:
1. **Writer**: structured-extraction LLM emitting typed claims with `claim_key`, `slot_type`, `object_norm`, validity. Mirrors SimpleMem's structured compression with three extra schema fields.
2. **Linker**: pairwise judge LLM with 3-call self-consistency for hardness.
3. **Parser + applicability router**: intent + temporal-anchor + canonical claim-key + applicability classification, in a single call. Mirrors SimpleMem's intent-aware planner.

### Integration into the Existing Pipeline

- **Files touched.** `ttmg/schema.py` (+3 fields), `ttmg/writer_temporal.py` (prompt update), `ttmg/conflict_linker.py` (3-call agreement; reduced label set; canonical-key filter), `ttmg/truth_retriever.py` (parser augmentation; canonicalizer; canonical-key fetch + fallback; all-optima MWIS; value-level decision rule), `ttmg/system.py` (config flags for 4 ablations + applicability-router on/off + canonical-key-only-vs-fallback toggle), NEW: `ttmg/canonicalize.py`.
- **Files frozen.** A-Mem reimplementation, Flat baseline, MAAS API layer, storage backend, embedding model.

### Training Plan

There is no training. Prompt-iteration only on writer (`claim_key`, `slot_type`, `object_norm`, `valid_from` extraction), linker (`supersede` recall + hardness calibration), and parser+router using a 60-q dev split disjoint from controlled-slice test items. Acceptance gates *before* any test-time runs:
- Linker `supersede`-F1 ≥ 0.7, hardness Brier ≤ 0.2.
- Writer-key-precision and parser-key-recall ≥ 0.85.
- Router precision + recall ≥ 0.85 on the 100-q audit set.
- Value-equivalence disagreement ≤ 15 % under equivalence-class protocol.
- Key-fetch-fallback rate < 5 % on dev.

### Failure Modes and Diagnostics

- **F1 Linker noise inflates hard edges.** Detect: hard-edge density > 2× baseline. Mitigate: raise hardness to 3/3 on diagnostic samples.
- **F2 MWIS arbitrary tie-break.** **Resolved structurally** by the all-optima rule; ties never produce an answer.
- **F3 Over-abstention.** Detect: abstain rate > 20 % on routed-to-TTMG slice. Mitigate: tighten applicability gate; check `object_norm` granularity.
- **F4 Applicability misroute.** Detect: router-precision/recall < 0.85 on audit. Mitigate: prompt iteration *before lock*; if locked-and-failing, the design fails per success condition (10c).
- **F5 LoCoMo cross-domain regression.** Already observed (–13.4 pp). Diagnostic: applicability rate < 15 % expected; composed end-to-end accuracy reported as deployer-relevant headline.
- **F6 SSA regression.** Already observed (–21 pp at N=500). SSA queries fail the applicability gate by design (asks-what-was-said, not asks-truth-of-fact); routed to Flat; removed from TTMG-claimed numbers.
- **F7 Key-alignment silent failure.** Detect: writer-key-precision or parser-key-recall < 0.85, OR key-fetch-fallback rate > 5 %. Mitigate: extend alias map; iterate canonicalizer rules *before lock*.
- **F8 Value-normalization mismatch.** Detect: equivalence-class disagreement > 15 %. Mitigate: tighten writer prompt; expand `object_norm` style guide; refine equivalence classes.
- **F9 High key-fetch-fallback rate.** Detect: > 5 % on LongMemEval-S. Mitigate: extend alias map; if persistent, reframe (hybrid retrieval is a load-bearing component on this benchmark and report it as such).

### Novelty and Elegance Argument

- **Closest work.** SimpleMem (ICML 2026, the 2026 frontier): intent-aware retrieval planning + symbolic temporal layer (timestamps as metadata). A-Mem (NeurIPS 2025): memory evolution that semantically refreshes neighbours when a new note is added.
- **Exact difference.** SimpleMem's symbolic temporal layer can filter retrieved candidates by *timestamp* but cannot tell that a 2024-03 single-valued claim about `(user, coffee_temperature_preference)` has been *replaced* by a 2024-09 claim about the same canonical `claim_key` with a different `object_norm`; both still surface, and SimpleMem has no abstain-on-conflict policy and certainly no all-optima abstention. A-Mem semantically refreshes neighbours but maintains no validity intervals, no typed edges, no `slot_type`, no canonical `claim_key`, no `object_norm` — its memory evolution can refresh stale neighbours but cannot deactivate them and cannot resolve them at the value level. *TTMG* introduces three minimal type-level additions — canonical `claim_key`, `slot_type`, `object_norm` — and one read-time semantic — *all-optima value-level unique-survivor under audited applicability* — that together constitute the first explicit truth-maintenance operator for the slot-update sub-problem of agent memory, with a *deterministic canonical-key fetch* on the applicable path and an *adversarially-correct* abstention rule.
- **Why mechanism-level (semantic), not pile-up.** Three new schema fields + one calibrated linker + one all-optima MWIS enumerator + one canonicalizer + one applicability router. The paper's contribution is one equation:
  `answer(q) = if applicable(q) then ( unique-value(⋃ Opts(canonical-fetch(q))) | ⊥ ) else Flat(q)`
  where `Opts` are the maximum-weight independent sets of the hard-edge subgraph and `⊥` denotes abstain. The novelty is the *all-optima* operator under *audited applicability*, not MWIS or canonical-key fetch in isolation.

## Claim-Driven Validation Sketch

### Claim 1 (Dominant) — Truth maintenance dominates on labelled supersede in both strata

- **Statement.** On both controlled-slice strata (`latest-state KU` ≈150 q, `as-of-time TR` ≈100 q), TTMG strictly dominates Flat hybrid-RAG and A-Mem reimplementation on answer accuracy (paired McNemar p<0.05 per stratum, no losing stratum); intrinsic linker `supersede`-F1 ≥ 0.7; hardness Brier ≤ 0.2; value-equivalence disagreement ≤ 15 %; key-fetch-fallback rate < 5 %.
- **Minimal experiment.** 3 methods × 3 seeds × 1 backbone (deepseek-v3.2) × controlled slice (~250 q across 2 strata).
- **Baselines / ablations.** Flat hybrid-RAG; A-Mem reimplementation; TTMG full; ablations: `no_validity`, `no_supersede`, `no_abstain`, `no_linker` (4 ablations, all main-text on slice).
- **Metric.** Intrinsic supersede F1 + hardness Brier + value-equivalence + fallback rate; downstream accuracy per stratum; paired McNemar; effect size Cohen's h.
- **Expected evidence.** TTMG ≥ Flat + 8 pp, ≥ A-Mem + 5 pp per stratum. `no_supersede` collapses on `latest-state KU`. `no_validity` collapses on `as-of-time TR`. `no_abstain` shrinks correct-abstain rate to ≈ 0. `no_linker` collapses both strata to ≈ A-Mem. Linker F1 ≥ 0.7, Brier ≤ 0.2, value-disagreement ≤ 15 %.

### Claim 2 (Supporting) — Routed-slice TR/KU wins + intrinsic audits clear + composed end-to-end reported

- **Statement.** On full LongMemEval-S (N=500, 3 seeds, deepseek-v3.2), restricted to the routed-to-TTMG slice (expected ~30–50 % applicability), TTMG ≥ Flat with paired McNemar p<0.05 in TTMG's favor on the combined TR + KU axis. Intrinsic router precision and recall ≥ 0.85 on 100-q audit. Key-fetch-fallback rate < 5 % on full benchmark. Composed end-to-end accuracy reported per benchmark as deployer-relevant headline.
- **Minimal experiment.** 3 methods × 3 seeds (0, 7, 17) × 1 primary backbone (deepseek-v3.2) × N=500. Final-method robustness check on Qwen3-30B-A3B for {Flat, TTMG} only at seed=0 → appendix. `no_linker` on the full benchmark moves to appendix per simplification.
- **Baselines / ablations.** Flat; A-Mem; TTMG full; same 4 ablations.
- **Metric.** Per-category accuracy on LongMemEval-S; paired McNemar on routed-to-TTMG slice; correct-abstain rate at fixed answer accuracy on full n=30; applicability rate per slice; key-fetch-fallback rate per slice; composed end-to-end accuracy; tokens/q + latency reported but not primary.
- **Expected evidence.** Routed-to-TTMG slice TR + KU: paired McNemar p<0.05 in TTMG's favor. Applicability rate on LongMemEval-S: ~30–50 %; on LoCoMo: <15 %. Router precision and recall ≥ 0.85 on audit. Key-fetch-fallback < 5 %. Correct-abstain on n=30 strictly > Flat at fixed accuracy. Overall LongMemEval-S accuracy: TTMG within 5 pp of Flat (acknowledged scoped). Composed end-to-end accuracy: TTMG-composed ≥ Flat on LongMemEval-S; ≈ Flat on LoCoMo (the diagnostic).

(MAX_PRIMARY_CLAIMS = 2 honored.)

## Experiment Handoff Inputs

- **Must-prove claims.** (1) Both controlled-slice strata strict dominance + linker intrinsic F1 + hardness Brier + value-equivalence + fallback rate; (2) Routed-to-TTMG TR + KU paired wins on full LongMemEval-S + composed end-to-end accuracy + intrinsic router/key-alignment audits clearing 0.85 + correct-abstain on full n=30.
- **Must-run ablations.** `no_validity`, `no_supersede`, `no_abstain`, `no_linker` (4, all main-text on controlled slice; `no_linker` on full benchmark moves to appendix).
- **Critical datasets / metrics.** Controlled supersede slice (~250 q, two strata, human-audited); LongMemEval-S full N=500; full abstention n=30; LoCoMo (already run, reported as diagnostic); 100-q router audit; 60-q dev split for linker + writer + parser intrinsic gates + value-equivalence equivalence-class JSON.
- **Highest-risk assumptions.** (i) Writer LLM produces stable canonicalizable `claim_key` strings (audited). (ii) 3-call agreement gives meaningful hardness signal (Brier audited). (iii) Applicability router agrees with author labels at ≥ 0.85 precision/recall (audited). (iv) Key-fetch-fallback rate stays < 5 % on LongMemEval-S (audited). (v) Multi-seed reproduces ablation directionality from existing seed=0 run. (vi) `object_norm` granularity is right under equivalence-class protocol (audited).

## Compute & Timeline Estimate

- **Compute.** All inference via MAAS API; no local training. ≈ **30 GPU-hour-equivalents** on 1–2× RTX-4090.
- **Data / annotation cost.** Controlled slice writer + cross-check ≈ 2 h MAAS calls. Human audit total ≈ 7 h author time (4 h slice + 1 h router + 1 h key-alignment + 1 h equivalence-class JSON).
- **Timeline.**
  - **Week 1.** Schema extension; canonicalizer + alias map; prompt-harden writer + linker + parser+router on dev; build + human-audit two-stratum controlled slice + 100-q router audit + 60-q key-alignment + author equivalence-class JSON; **all intrinsic gates clear** (linker F1 ≥ 0.7, Brier ≤ 0.2, key-precision/recall ≥ 0.85, router-precision/recall ≥ 0.85, value-equivalence disagreement ≤ 15 %, fallback rate < 5 %). **Lock router prompt; commit hash printed in paper.** Multi-seed pilot N=150 directionality.
  - **Week 2.** Full N=500 × 3 seeds × deepseek-v3.2 for {Flat, A-Mem, TTMG, 4 ablations}. Both controlled-slice strata × 3 seeds × 3 methods. Compute applicability rate, fallback rate, composed end-to-end accuracy per benchmark. Secondary-backbone robustness (Qwen3-30B-A3B, seed=0) for {Flat, TTMG} → appendix.
  - **Week 3.** Paper rewrite with the round-3 framing (slot-scoped semantic operator + audited applicability gate + all-optima abstention + canonical-key fetch); figures (router-coverage × accuracy plot, composed-vs-routed plot, per-stratum strict-dominance plot, per-ablation drop bar chart, Brier-calibration plot, fallback-rate histogram, post-filter candidate-count histogram); statistical hardening (paired McNemar tables per slice + per stratum, abstain-correctness curves, hardness Brier plot, value-equivalence histogram, key-fetch-fallback per slice); reconcile STATUS.md with reality; swap in real MemGPT (arXiv 2310.08560); cite-comparison rows with SimpleMem and LightMem.

## Polish Items (from round 4 reviewer)

- Tighten wording around the role of weights so the semantics are not oversold as weight-free; weights still define the optimal-set family, they no longer act as an arbitrary tie-break loophole.
- Add one small table or histogram showing applicable-query candidate counts and fallback rate.
- Keep the paper's main headline narrow: **slot-scoped truth-maintenance semantics with an audited applicability gate**, not "better general memory."
- Merge router + key-alignment + value-equivalence + fallback-rate checks into one compact **intrinsic audit suite** table in the main paper.
- Keep `writer_confidence` weighting entirely supplementary in the narrative.
- Keep hybrid fallback + secondary-backbone robustness in appendix unless reviewer explicitly asks for more.
