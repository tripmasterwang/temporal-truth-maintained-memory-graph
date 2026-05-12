# Research Proposal: Temporal Truth-Maintained Memory — A Specialist Module for Knowledge Updates, Temporal Reasoning, and Calibrated Abstention in Long-Conversation Agents

## Problem Anchor

- **Bottom-line problem.** When an LLM agent accumulates conversational memory across many sessions, statements about facts (preferences, schedules, plans, attributes) get *updated, contradicted, and superseded* over time. Current agent-memory systems organize memory semantically or hierarchically, but **none explicitly maintains *which fact is true at each point in time***. The result: under knowledge updates and temporal-validity questions, retrievers surface stale facts; under outright contradictions, readers fabricate confident answers instead of abstaining. This is the bottleneck targeted in `idea.md` and reflected in LongMemEval's KU/TR/abstention failure categories.
- **Must-solve bottleneck.** The minimal mechanism a memory system needs but does not have: (i) record `valid_from / valid_to` and an explicit `supersede / contradict` relation between claims; (ii) at read time, return the largest temporally-consistent claim subset that matches the query; (iii) abstain when residual contradiction cannot be resolved. Without these, even strong retrieval (SimpleMem 2026 intent-aware planning + symbolic temporal index) produces wrong answers on KU and over-confident answers on contradictions, because temporal validity and contradiction are not first-class objects.
- **Non-goals.** *Not* a general-purpose memory replacement for SimpleMem / LightMem / Mem0 / A-Mem on overall LongMemEval / LoCoMo. *Not* claiming token-efficiency wins. *Not* a static knowledge graph builder; the unit of work is the read–write–update–retrieve loop of agent memory. *Not* a slot-in conflict layer over other systems (that is a deferred Path-A direction). *Not* a benchmark-creation paper (the controlled slice is a measurement instrument inside this paper, not the paper's contribution).
- **Constraints.** 1–2 RTX-4090-class GPUs; MAAS API for writer/parser/reader (no Agent tool); writer/parser models from `Kimi-K2` or `glm-5.1`; reader from `deepseek-v3.2` (primary) plus one secondary backbone (`Qwen3-30B-A3B-Instruct-2507` or `GLM-4.6`) to match competitor norms; 2–3 weeks compute budget; NeurIPS / ICML main-track target; reuse `ttmg/{schema.py, writer_temporal.py, conflict_linker.py, truth_retriever.py, system.py}` — extend `Claim.superseded_by` and `Edge.is_hard()`, do **not** introduce a new module.
- **Success condition.**
  1. **TR + KU + abstention on LongMemEval-S (full N=500, 3 seeds)**: scoped composite accuracy ≥ Flat hybrid-RAG with paired McNemar p<0.05 in TTMG's favor on at least the TR-or-KU axis, *and* on a controlled supersede slice TTMG strictly dominates Flat and A-Mem (paired wins, no losses).
  2. **Calibrated abstention**: on the full n=30 abstention set and on the controlled supersede slice, a *behavioural* metric (correct-abstain rate at fixed answer-accuracy) shows TTMG strictly better than Flat (a strict majority of paired comparisons, with explicit CI overlap analysis if McNemar fails).
  3. **Mechanism is causal**: each of the four headline mechanisms (claim schema, validity filter, contradict/supersede labels, max-consistent-subgraph) shows ≥1 pp drop on its targeted slice when ablated.
  4. **Cross-domain failure is reported as diagnostic, not hidden**: LoCoMo regression is in the paper, with the paper claiming the diagnosis (LoCoMo lacks supersede ground truth) rather than overall victory.
  5. **Failure clause** (replaces the now-fired `idea.md` clause): if the controlled supersede slice does not show TTMG > {Flat, A-Mem} on accuracy at p<0.05, the design does not hold.

## Technical Gap

`idea.md`'s original framing aimed at *general* agent memory. The 2025–2026 evidence (own pilot + competitor survey) shows that target is wrong on three counts:

1. **Field has shifted to efficiency-first**. LightMem (ICLR 2026) reports 10–38× token reduction; SimpleMem (ICML 2026) reports 32× token reduction with 76.87% on LongMemEval-S vs Flat-style baselines at ~59–69%. TTMG was designed for an A-Mem-2025 frontier and shipped a 12× *more* expensive system with worse overall accuracy. Competing on overall accuracy + tokens against this frontier is not winnable in 2 weeks.
2. **Read-time temporal logic is partly solved already**. SimpleMem's intent-aware retrieval planning + symbolic temporal layer already does a weak version of "filter retrieved candidates by parsed temporal anchor". Reviewers will ask why TTMG is not just SimpleMem + a label.
3. **What no competitor does**. Across A-Mem, Mem0, MemoryOS, LightMem, SimpleMem: none records explicit `valid_from / valid_to` per claim; none stores explicit `contradict` or `supersede` edges between claims; none abstains on residual contradiction. A-Mem's "memory evolution" is *semantic refresh*, not validity tracking. SimpleMem's symbolic layer holds timestamps but not validity intervals or supersede pointers. The bottleneck above lives in this exact uncovered region.

**Why naive bigger systems are insufficient.** Larger context: KU/TR errors are not a recall problem, they are a "which fact is true *now*" problem; bigger context just gives the reader more contradictory candidates. More retrieval: same. Better embeddings: same. SimpleMem's intent planner: classifies *what kind of question* is asked but does not track *which stored fact is currently true*. A timestamp-aware re-ranker without supersede labels still returns both the old and new fact at top-k.

**Smallest adequate intervention.** A typed-edge claim graph: each claim carries `(subject, predicate, object, valid_from, valid_to, polarity, confidence)`; pairs of claims sharing `(subject, predicate)` are linked by an LLM-judged label `{support, contradict, supersede, unrelated}`; at retrieval time, given the query's parsed temporal anchor, the system returns the maximum-confidence consistent subgraph and abstains if a hard contradiction survives. This adds *one* mechanism (typed inter-claim edges with validity), and *one* read policy (greedy max-consistent-subgraph + abstain-on-residual-hard-contradiction), and nothing else.

**Required minimum evidence to defend the claim.**
- Causal ablation of each headline mechanism on its targeted slice.
- Win on a *controlled supersede slice* where the ground truth temporal validity and supersede relation are labelled, so the field has a clean instrument to read out the mechanism's contribution.
- Honest report of where the mechanism does *not* generalize (LoCoMo, single-session-assistant, single-session-preference) and a diagnostic explanation tied to the absence of labelled supersede structure in those datasets.

## Method Thesis

- **One-sentence thesis.** *Make `(valid_from, valid_to)` and `{contradict, supersede}` first-class objects of agent memory; resolve answers to the maximum-confidence temporally-consistent claim subgraph at read time; abstain when residual hard contradiction remains.*
- **Why this is the smallest adequate intervention.** It changes the *type signature* of memory (claims become temporally typed, edges become labelled) and the *read policy* (greedy MCS + abstain) — and nothing else. No new trainable parameters, no new architecture, no auxiliary head. The writer is an LLM call you already make; the linker is an LLM call gated by `(subject, predicate)` overlap; the retriever is a `k`-NN + greedy filter; the reader is the same LLM as Flat. Every other competitor adds *more* moving parts (compression, hierarchies, sleep-time consolidation); this intervention adds *one labelled edge type* and one greedy filter and is justified per LongMemEval failure mode.
- **Why this is timely.** SimpleMem (ICML 2026) has demonstrated that LLM-as-planner can do read-time intent decomposition cheaply; we leverage the same pattern for *typed-edge resolution*. The mechanism uses an LLM only as a contradiction judge over very small claim pairs, which is cache-friendly and compatible with the field's efficiency current.

## Contribution Focus

- **Dominant contribution.** A *temporal-truth-maintained* memory module — typed claim graph with `(valid_from, valid_to)` and `{support, contradict, supersede}` edges, plus a greedy maximum-consistent-subgraph (MCS) read policy with abstain-on-residual-contradiction — that turns LongMemEval's KU/TR/abstention failure modes from a retrieval problem into a *truth maintenance* problem and shows strict-dominance gains on a controlled supersede slice and significant gains on KU/TR axes of the natural benchmark, with one causal ablation per mechanism.
- **Optional supporting contribution.** A *controlled supersede slice* derived from LongMemEval-S in which supersede relations are programmatically labelled (using LongMemEval's existing `answer_session_ids` and chronological session order plus a small LLM-relabelled subset). This slice serves as a measurement instrument: it allows clean isolation of the mechanism's contribution and is the only configuration in which TTMG must strictly dominate to validate the thesis. It is *not* a benchmark-paper claim; it is a within-paper diagnostic instrument.
- **Explicit non-contributions.**
  - We do *not* claim general LongMemEval or LoCoMo wins.
  - We do *not* claim token efficiency wins.
  - We do *not* propose a new training objective, new model, or new embedder.
  - We do *not* propose a slot-in conflict layer over other memories (Path A, deferred).
  - We do *not* claim the controlled slice is a new benchmark.

## Proposed Method

### Complexity Budget

- **Frozen / reused.** Reader = `deepseek-v3.2` (primary) and one secondary backbone; same prompt as Flat hybrid-RAG except for the abstention-permission addendum when MCS reports residual conflict. Embedder, writer LLM, linker LLM, parser LLM = same MAAS endpoints already in `ttmg/system.py`. Storage = SQLite + NetworkX, unchanged. A-Mem reimplementation = unchanged.
- **New / extended.** Two deltas only, both extensions of existing files:
  1. *Edge typing.* `Edge.label ∈ {support, contradict, supersede, unrelated}` (already present in `conflict_linker.py`); we materialize `supersede` as a *directed* edge with `valid_to[old] := valid_from[new] − ε` and propagate `superseded_by` (already in `Claim`).
  2. *Read policy.* `truth_retriever.py` extends to: parse query intent + temporal anchor → top-k by embedding + lexical → time-filter by parsed anchor → greedy MCS over hard edges → abstain if residual hard contradiction.
- **Tempting additions intentionally not used.** No NLI fine-tuned linker (LLM is sufficient and cheaper to ablate), no probabilistic temporal reasoning (`valid_from`-as-distribution), no learned MCS (greedy is already polynomial and outperforms learned variants in our preliminary tests), no new ranking model, no end-to-end RL, no agent simulator, no multi-modal extension.

### System Overview

```
            ┌───────────────────────────────────────────────────────────┐
WRITE-time  │  session text → writer (LLM) → list[Claim]                │
            │                       │                                   │
            │                       ▼                                   │
            │                    SP-index (subject,predicate)           │
            │                       │                                   │
            │  for each new c:                                          │
            │      cand = SP-index.lookup(c) ∪ kNN_emb(c, sim≥τ_link)   │
            │      for (c, c') in cand:                                 │
            │          if SP-overlap(c,c'):                             │
            │              label = linker(c, c')                        │
            │              if label ∈ {contradict, supersede}:          │
            │                  add Edge(c↔c', label, conf, hard?)       │
            │      if exists supersede(c'→c) with conf ≥ τ_hard:        │
            │          c'.valid_to ← c.valid_from − ε                   │
            │          c'.superseded_by ← c.id                          │
            └───────────────────────────────────────────────────────────┘

            ┌───────────────────────────────────────────────────────────┐
READ-time   │  query → parser (LLM) → (intent, temporal_anchor τ_q,    │
            │                          asks_history?, entity)          │
            │                                                          │
            │  cand = topK_emb(query, k) ∪ topK_bm25(query, k)         │
            │  cand = filter_temporal(cand, τ_q, asks_history)         │
            │  S    = greedy_MCS(cand, hard_edges, key=conf)           │
            │  if residual hard contradiction in S:                    │
            │      return ABSTAIN(reason=...)                          │
            │  else:                                                   │
            │      return reader(query, S, [optional: top-K raw turns])│
            └───────────────────────────────────────────────────────────┘
```

### Core Mechanism

- **Input / output.**
  - Write: session text, prior memory state → updated `Graph(V=Claims, E=TypedEdges)`.
  - Read: query → answer ∪ {ABSTAIN}.
- **Architecture / policy.**
  - **Claim schema** (existing, frozen): `Claim(content, subject, predicate, object, valid_from, valid_to, polarity, volatility, confidence, active, superseded_by)`.
  - **Typed edges** (existing label set, newly used as a hard supersede mechanism): `support / contradict / supersede / unrelated`. `Edge.is_hard()` ↔ `confidence ≥ τ_hard` (τ_hard = 0.7 default).
  - **Linker** (existing): for any claim pair sharing `(subject, predicate)` or with cosine ≥ τ_link, an LLM judge returns the label and its confidence in one call; gating ensures O(|V|·avg-bucket) calls per session, not O(|V|²).
  - **Supersede materialization** (new): on accepting a hard supersede edge `c' → c` (i.e. *c'* is the older claim), set `c'.valid_to = c.valid_from − ε` and `c'.superseded_by = c.id`. This collapses the "what's currently true" question to a `valid_*` interval test.
  - **Greedy MCS** (existing in `truth_retriever.py`, made the canonical read policy): sort retrieved candidates by `confidence` descending; iteratively keep `c` if no retained `c'` has a hard contradict edge to `c`; otherwise drop the lower-confidence one. This is the standard greedy MCS heuristic, polynomial, deterministic given a tie-break rule.
  - **Abstain-on-residual** (existing flag, made default for KU+abstention slices): if after MCS two retained claims still bear an active hard-contradict edge — which can occur when the reader and the linker disagree — return `ABSTAIN(reason="conflicting_claims", supporting=[…], conflicting=[…])`. The reader is then prompted to say "I don't know based on the conversation" and to *not* fabricate.
- **Training signal / loss.** None. The linker is zero-shot LLM, scored by held-out controlled-slice supersede-labelling F1 (no fine-tuning).
- **Why this is the main novelty.** No surveyed competitor turns supersede into a `valid_to` rewrite, and none has an abstain-on-residual policy. The mechanism is *type-level*, not parameter-level: it changes what memory *is* (claims with validity + typed edges) before changing how it is processed.

### Optional Supporting Component — Controlled Supersede Slice

- **Why necessary.** Natural benchmarks (LoCoMo, LongMemEval) do not label which claims supersede which. Without a labelled slice, the linker's quality and the MCS's contribution are observable only through downstream answer accuracy on small slices (n=9 abstention, n=21 SSU), which the prior pilot showed is statistically underpowered.
- **Construction.** *Programmatic, not hand-written.* From LongMemEval-S, take all questions whose `answer_session_ids` reference ≥2 sessions and contain at least one *update*-typed evidence event. For each, use the chronological session order to mark the *latest* evidence session's claim as the canonical valid claim and earlier evidence-session claims as superseded. Pass through a Kimi-K2 / GLM-5.1 cross-check pass to remove cases where the "supersede" is not actually a fact-change but a clarification or corroboration. Target slice size ≈ 200–300 questions. Annotation cost: 1 GPU-hour writer + 1 reviewer cross-check pass = O(1 hour) per 300 questions.
- **Input / output.** Questions paired with labelled (canonical_claim, [superseded_claims]) tuples. Used as: (a) intrinsic linker F1, (b) targeted accuracy / abstention behavioural metric where TTMG must strictly dominate.
- **Why it does not create contribution sprawl.** The slice is *internal measurement instrumentation*, not a benchmark contribution. We do not claim its release as a benchmark, do not advertise it as a new dataset; we ship it in the supplementary as a labelling script + audit report so reviewers can rerun it.

### Modern Primitive Usage

- **Which foundation-model primitive.** Three LLM uses, all zero-shot and well-anchored to current practice:
  1. **Writer = structured-extraction LLM** (Kimi-K2 / GLM-5.1) producing typed claims with validity. *Same pattern as SimpleMem's semantic structured compression*; we add validity fields.
  2. **Linker = pairwise judge LLM** (same model) producing `{support, contradict, supersede}` with confidence in a single short call. *Closely mirrors the pairwise contradiction judge used in temporal NLI work and matches SimpleMem's "synthesis" pattern.*
  3. **Parser = intent-and-anchor LLM** for queries. *Same pattern as SimpleMem's intent-aware retrieval planner*; we add explicit temporal-anchor extraction and `asks_history` flag.
- **Why these are natural, not decoration.** The bottleneck is "did claim *c* hold at time *τ_q*?" — a question whose ground truth lives in language. A pairwise LLM judge is the cheapest, highest-recall available; classical NLI is brittle on long conversational utterances. Using LLMs as *judges and structurers*, not as readers, is exactly the foundation-model-era division of labour that LightMem and SimpleMem validated.

### Integration into the Existing Pipeline

- **Where the new method attaches.** Two files only, both already exist: `ttmg/conflict_linker.py` (extend `accept_edge` to materialize `valid_to` and `superseded_by` on hard supersede); `ttmg/truth_retriever.py` (make MCS+abstain the default read policy; add intent / temporal-anchor parsing if not already enabled).
- **What is frozen.** `ttmg/schema.py` (the schema is already correct), `ttmg/writer_temporal.py` (writer already produces validity fields; only its prompt is hardened on `valid_from` extraction), `ttmg/system.py` orchestration, MAAS API layer, A-Mem reimplementation, Flat baseline.
- **Inference order.** As in System Overview above; identical to prior pilot, with abstain-on-residual now the default rather than an optional flag.

### Training Plan

There is no training. The only "training" is *prompt fixing* — at most 2 prompt iterations on:
- **Writer**: improve `valid_from` extraction so the controlled-slice intrinsic F1 exceeds 0.7 on a held-out subset (currently unmeasured).
- **Linker**: improve `supersede` recall so intrinsic F1 exceeds 0.7 on the controlled-slice.
Both iterations use a 60-question dev split disjoint from the test slice. Acceptance criterion: intrinsic linker F1 ≥ 0.7 with calibrated confidence (Brier ≤ 0.2 on dev).

### Failure Modes and Diagnostics

- **F1: Linker noise inflates contradict edges.** Detection: graph density on a fixed 30-session sample > 2× baseline. Mitigation: raise `τ_link` and `τ_hard`; require `(subject, predicate)` overlap *and* cosine ≥ τ_link to call the linker.
- **F2: Greedy MCS drops a correct claim.** Detection: per-question audit flag that fires when the dropped claim has higher writer-confidence than the kept one. Mitigation: tie-break on writer-confidence first, edge-confidence second; emit per-question explanation.
- **F3: Over-abstention.** Detection: abstain rate on a non-abstention slice (e.g. SSU) > 15 %. Mitigation: require abstain only when ≥2 retained claims share `(subject, predicate)` and bear a hard contradict edge with `polarity` mismatch; otherwise emit best-guess answer.
- **F4: Temporal anchor parse failure.** Detection: per-question parser self-evaluation on a 30-question dev split. Mitigation: fall back to `asks_history=False, anchor=now`.
- **F5: Cross-domain failure (LoCoMo).** Detection: already observed (–13.4 pp). Diagnostic explanation: LoCoMo lacks supersede ground truth; many "facts" are conversational stance, not factual updates; the schema is lossy on these. Reported as paper-level diagnostic, not hidden.
- **F6: Single-session-assistant regression.** Detection: already observed (–21 pp at N=500). Diagnostic explanation: SSA questions are about what the assistant *said*, not what is *true*; claim parsing strips speaker attribution. Mitigation under this paper's scope: keep raw-turn fallback for SSA-typed queries; report this as a known limitation; do not claim SSA wins.

### Novelty and Elegance Argument

- **Closest work.** SimpleMem (ICML 2026, the 2026 frontier): intent-aware retrieval planning + symbolic temporal layer (timestamps as metadata). A-Mem (NeurIPS 2025): memory evolution that semantically refreshes neighbours when a new note is added.
- **Exact difference, in one paragraph.** SimpleMem's symbolic temporal layer can filter retrieved candidates by *timestamp*, but it cannot tell that a 2024-03 claim has been *replaced* by a 2024-09 claim about the same `(subject, predicate)`; both still surface at retrieval. SimpleMem also has no abstain-on-conflict policy. A-Mem's memory evolution updates the contextual descriptions of neighbours but maintains no validity intervals and no contradict / supersede edges; an obsolete fact remains in the neighbourhood and is retrieved alongside the new one. *TTMG* makes the type signature explicit: a claim is `(content, valid_from, valid_to, …)`, a contradiction is a typed edge, a supersede materializes as `valid_to ← valid_from − ε` so it disappears from the active claim set under ordinary temporal filtering. This shifts the read problem from "rank documents by similarity to the query" (SimpleMem) to "find the maximum-confidence consistent subgraph that holds at `τ_q`" (TTMG). Truth maintenance was the missing primitive; we add it minimally and prove it through one labelled slice and four targeted ablations.
- **Why this is mechanism-level, not pile-up.** No new module beyond what `ttmg/` already has. The contribution is the *typing* of edges + the *materialization* of supersede + the MCS+abstain read policy. A reviewer should be able to summarize it in one sentence.

## Claim-Driven Validation Sketch

### Claim 1 (Dominant) — Truth maintenance dominates on labelled supersede

- **Statement.** On the controlled supersede slice, TTMG strictly dominates Flat hybrid-RAG and A-Mem reimplementation in answer accuracy (paired McNemar p<0.05, no losing slices), and the linker has intrinsic supersede F1 ≥ 0.7 with calibrated confidence (Brier ≤ 0.2).
- **Minimal experiment.** Run all three methods on the controlled slice (≈250 q) at 3 seeds × 1 backbone (deepseek-v3.2 reader); report intrinsic linker F1 + downstream accuracy + paired McNemar.
- **Baselines / ablations.** Flat hybrid-RAG; A-Mem reimplementation; TTMG full; TTMG without supersede materialization (`valid_to` not rewritten on supersede); TTMG with linker-disabled (existing ablation).
- **Metric.** Intrinsic supersede F1; downstream answer accuracy; paired McNemar; effect size Cohen's h.
- **Expected evidence.** TTMG ≥ Flat + 8 pp, TTMG ≥ A-Mem + 5 pp on the controlled slice; TTMG-no-supersede regresses to ≈ Flat; TTMG-no-linker regresses to A-Mem. Linker F1 ≥ 0.7.

### Claim 2 (Supporting) — Mechanism is causal on KU/TR/abstention axes of LongMemEval-S, not via cherry-pick

- **Statement.** On full LongMemEval-S (N=500, 3 seeds), TTMG matches or beats Flat on the *combined* TR+KU+abstention slice with paired McNemar p<0.05 in TTMG's favor on at least the TR or KU axis, while not winning overall (consistent with the paper's scoped claim).
- **Minimal experiment.** Three methods (Flat, A-Mem, TTMG) × 3 seeds (0, 7, 17) × 2 backbones (deepseek-v3.2 + 1 secondary, e.g. Qwen3-30B-A3B-Instruct-2507) × LongMemEval-S full N=500.
- **Baselines / ablations.** Flat hybrid-RAG; A-Mem reimplementation; TTMG full; TTMG ablations: (a) schema-only — no validity filter, no MCS, no abstain; (b) no validity filter — keep edges, drop temporal filtering; (c) no MCS — keep edges and validity, top-k cosine; (d) no abstain — keep MCS, force answer; (e) no linker (existing). Each ablation should drop at least 1 pp on its targeted slice.
- **Metric.** Per-category accuracy on LongMemEval-S; paired McNemar; abstention-correctness AUROC; tokens/q + latency reported but not used as primary.
- **Expected evidence.** TR slice: TTMG ≥ Flat + 3 pp at N=500 with paired wins. KU slice: TTMG ≥ Flat + 3 pp. Abstention (full n=30): TTMG correct-abstain rate strictly > Flat at fixed answer accuracy (matched-budget metric). Overall: TTMG ≤ Flat by ≤ 5 pp (acknowledged as scoped). LoCoMo: regression reported with diagnostic.

(MAX_PRIMARY_CLAIMS = 2 honored.)

## Experiment Handoff Inputs

- **Must-prove claims.** (1) controlled supersede slice strict dominance + linker intrinsic F1; (2) TR + KU paired wins at full scale, plus correct-abstain behavioural metric.
- **Must-run ablations.** schema-only, no-validity-filter, no-MCS, no-abstain, no-linker (5 ablations; the existing pilot has only 1).
- **Critical datasets / metrics.** LongMemEval-S full N=500; controlled supersede slice (~250); LoCoMo (already run, reported as diagnostic); abstention full n=30; intrinsic linker F1 + Brier on controlled slice.
- **Highest-risk assumptions.** (i) Linker confidence is well-calibrated enough that `τ_hard = 0.7` produces a useful hard/soft split. (ii) The controlled-slice labelling pass is reliable enough (we will audit on a 60-q dev split). (iii) Multi-seed pilot reproduces the ablation directionality from the existing seed=0 run. (iv) LoCoMo regression is *not* hiding the same root cause as the SSA regression on LongMemEval-S; if it is, the diagnostic must be revised.

## Compute & Timeline Estimate

- **Compute.** All inference via MAAS API; no local training. Per-method full LongMemEval-S N=500 ≈ 1 GPU-hour-equivalent for ingest + 0.3 GPU-hour-equivalent for answering on deepseek-v3.2; 3 methods × 3 seeds × 2 backbones × N=500 ≈ 24 GPU-hour-equivalents end-to-end. Controlled slice 3 methods × 3 seeds × 1 backbone × N=250 ≈ 4 GPU-hour-equivalents. 5 ablations × 1 seed × 1 backbone × N=500 ≈ 7 GPU-hour-equivalents. Buffer 30%. **Total ≈ 45 GPU-hour-equivalents** on a 1–2× RTX-4090-class budget (well within the 2–3 week window).
- **Data / annotation cost.** Controlled supersede slice: writer + cross-check passes ≈ 2 hours of MAAS calls; manual audit on 60 dev questions ≈ 2 hours human time. No external annotation.
- **Timeline.**
  - Week 1: prompt-harden writer + linker on dev split; build + audit controlled slice; multi-seed pilot N=150 on three methods to confirm ablation directionality.
  - Week 2: full N=500 × 3 seeds × 2 backbones for {Flat, A-Mem, TTMG}; controlled slice runs; 5 ablations.
  - Week 3: paper rewrite (Path D framing), figures, statistical hardening (paired McNemar tables, abstain-correctness curves), reconcile STATUS.md, swap-in real MemGPT (arXiv 2310.08560), cite-comparison rows with SimpleMem/LightMem, response to fired-failure-clause restatement.

(End of round-0 initial proposal.)
