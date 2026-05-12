# LIT_SURVEY_DELTA — papers added since `AGENT_MEMORY_FRONTIER_REPORT.md`

**Date:** 2026-04-27
**Source dispatch:** 3 parallel general-purpose agents covering: (a) post-March-2026 memory papers, (b) statistical/theoretical tools beyond conformal/PMI/VIB, (c) training-side fixes for writer-parser alignment.
**Cap:** 15 high-signal additions (skill spec).
**Verification status:** arXiv IDs reported by agents; spot-check the most strategically critical ones (APEX-MEM, RoMem, Synthius-Mem, Memory-R1) before paper-writing.

---

## A. Post-March-2026 agent-memory papers (5)

> Window note: today is 2026-04-27. arXiv 2605–2607 not yet populated; only 2604.* and earlier reachable. Repeat this delta query after May 2026 for full coverage.

| # | arXiv ID | Title | Core mechanism (1 line) | Headline | Why it matters for us |
|---|---|---|---|---|---|
| 1 | **2604.14362** | APEX-MEM: Agentic Semi-Structured Memory with Temporal Reasoning | Property graph + append-only temporal storage + multi-tool retrieval agent that resolves conflicting/evolving facts at *query time* (no destructive updates) | 88.88 % LoCoMo, 86.2 % LongMemEval | **Direct competitor** to TTMG / β framing — same "append-only + retrieval-time resolution" axis. Must benchmark against. |
| 2 | **2604.08256** | HyperMem: Hypergraph Memory for Long-Term Conversations | Hypergraph (topics/episodes/facts) with hyperedges to capture high-order joint deps that pairwise graphs miss; coarse-to-fine hybrid retrieval | **92.73 %** LLM-as-judge LoCoMo (claimed SOTA at submission) | Pushes structural-memory line beyond pairwise edges. Threatens TTMG if we only model binary edges. Possible β-style ablation candidate. |
| 3 | **2604.11544** | Time is Not a Label: Continuous Phase Rotation for Temporal Knowledge Graphs / Agentic Memory (RoMem) | Per-relation "Semantic Speed Gate" + continuous phase rotation in complex space → obsolete facts geometrically *shadowed* without deletion | 72.6 MRR ICEWS05-15; "dominates" LoCoMo; 2-3× MRR/answer-acc on MultiTQ | **Most direct theoretical alternative to discrete supersede edges.** Argues you don't need explicit edits if temporal volatility is geometric. Position our work against this "no-delete" paradigm. |
| 4 | **2604.11563** | Synthius-Mem: Brain-Inspired Hallucination-Resistant Persona Memory | Rejects "retrieve what was said" paradigm; extracts structured persona facts across 6 cognitive domains with CategoryRAG | 94.37 % LoCoMo accuracy, 98.64 % core fact accuracy, **99.55 % adversarial robustness** | The only paper reporting adversarial robustness — sets a bar we should match or risk being dismissed for ignoring hallucination resistance. |
| 5 | **2604.18349** | HiGMem: Hierarchical and LLM-Guided Memory for Long-Term Conversational Agents | 2-level event-turn memory; LLM uses event summaries as semantic anchors to predict which raw turns to fetch (replaces vector-similarity retrieval) | Best F1 on 4/5 LoCoMo10 categories; **adversarial F1 0.54 → 0.78 over A-Mem** with 10× fewer turns. **Code released.** | Direct head-to-head against A-Mem on the exact axis we care about (adversarial / abstention). Near-mandatory baseline. |

**Honourable mentions (not in 15-cap, flagged for future)**: Cognis (2604.19771) production system; LightMem-2604.07798 (name collision; *different* paper from 2510.18866); SCM (2604.20943) sleep-consolidation but evidence-light (custom 8-test suite, not LoCoMo).

---

## B. Statistical / theoretical tools (cross-pollination from outside memory subfield) (7)

| # | arXiv ID | Title | Math object | Signal it produces | Retarget to memory |
|---|---|---|---|---|---|
| 6 | **2509.12527** | Selective Risk Certification for LLM Outputs via Information-Lift Statistics: PAC-Bayes, Robustness, and Skeleton Design | Sub-gamma PAC-Bayes bound (heavy-tail-safe McAllester/Maurer variant) over an "information-lift" statistic vs a skeleton baseline | Selective-prediction certificate: rule "abstain or answer" with formal upper bound on conditional risk over the answered set; **77 % coverage at 2 % risk; blocks 96 % of critical errors** | Replace "LLM output" with "retrieved memory item" and "skeleton" with prior memory state → selective-recall certificate. **Best PAC-Bayes hook for memory we found**, heavy-tail-safe (key for long-tailed memory item frequency). |
| 7 | **2508.21141** | Adaptive LLM Routing under Budget Constraints (PILOT) | Preference-prior LinUCB + online cost policy as multi-choice knapsack | Per-query routing decision + per-query cost-share with global budget; sublinear regret | Memory backends (vector / graph / A-MEM / TTMG) become arms; query embedding = context; budget = token/latency. **Per-query backend selection with regret guarantee** — currently absent from memory subfield. |
| 8 | **2506.17670** | Online Multi-LLM Selection via Contextual Bandits under Unstructured Context Evolution | LinUCB variant with provable sublinear regret under *black-box* context evolution | Stop/continue arm choice in multi-turn sequences with non-stationary context | Long conversations are exactly "context evolves through black-box LLM responses." **Only bandit framework that handles unstructured per-step context drift** — fits LongMemEval multi-turn setting. |
| 9 | **2512.03109** | E-valuator: Reliable Agent Verifiers with Sequential Hypothesis Testing | E-process (anytime-valid e-value sequence) wrapping any black-box scalar verifier score | Binary stop-or-continue at each step with formal false-alarm-rate control; works for arbitrarily long sequences | "Should I retrieve another item / call another hop?" gets anytime-valid stopping. Strict generalisation of SPRT (no fixed-N), handles non-i.i.d. memory streams. |
| 10 | **2411.00147** | Mutual Information Preserving Neural Network Pruning (MIPP) | Activation-based pruning rule that preserves MI between adjacent layer activations + sample-efficiency theorem on robustness∝MI(mask; data) | Keep/drop mask with MI-preservation guarantee | Memory pruning = MI-preserving forget rule. **First principled "how much can I forget without harming downstream answer accuracy" budget** for the memory subfield. |
| 11 | **2407.05375** | Online Drift Detection with Maximum Concept Discrepancy (MCD-DD, KDD 2024) | MMD-style 2-sample test in *contrastively-learned* concept-embedding space; label-free, no parametric assumption | Online drift-alarm sensitive to gradual / abrupt / recurring drift on high-dim streams | Run on memory-embedding stream → "the user's world has changed — invalidate or re-weight old memories" signal. Replaces manual recency decay heuristic. No labels needed. |
| 12 | **2405.05736** | Optimal Baseline Corrections for Off-Policy Contextual Bandits (RecSys 2024) | Closed-form variance-optimal *unbiased* OPE estimator unifying additive control variates and self-normalised IPS | Counterfactual reward of any candidate policy from logged behaviour-policy data, minimum variance among unbiased estimators | Memory selection = logged contextual bandit. **Honest A/B for new memory-retrieval policies without re-running full agent.** Replaces today's standard practice of end-to-end re-run per variant. |

**Coverage gap honestly flagged**: Category "calibration via temperature scaling on retrieval scores" — 2024-25 calibration work is on LLM token prob / classifier logits (e.g., 2402.05806), nothing specifically calibrates dense-retrieval similarity with reliability diagrams in the period. Real white-space.

---

## C. Training-side fixes for writer-parser alignment (3)

> Tightly-scoped picks: must train *the writer* with a reader-side or task-side signal (the failure mode β hit). Excluded pure RAG fine-tune work without a writer/memory angle.

| # | arXiv ID | Title | Training objective | Architecture | Why for us |
|---|---|---|---|---|---|
| 13 | **2508.19828** | Memory-R1: Enhancing LLM Agents to Manage and Utilize Memories via Reinforcement Learning | Outcome-driven RL (PPO + GRPO) with terminal QA-correctness reward propagated back to a Memory Manager that emits ADD/UPDATE/DELETE/NOOP | Two-agent: Memory Manager (writer) + Answer Agent (reader); writer trained explicitly with reader-derived reward — **reader-feedback distillation onto the writer** | **Most direct precedent for solving the alignment failure** — writer is rewarded only when the Answer Agent succeeds; any naming/slot mismatch is penalised. 7B variant on single 24 GB GPU with LoRA. Public code. |
| 14 | **2601.05488** | MemBuilder: Reinforcing LLMs for Long-Term Memory Construction via Attributed Dense Rewards | RL with *attributed dense rewards* — synthetic session-level QA generates intermediate rewards + contribution-aware gradient weighting that scales each writer step's update by its measured downstream impact | Writer-only fine-tune; supervised by reader-side reward — closest in literature to "critic-reward extractor" pattern | **Tells the writer which specific extracted slot led to a downstream failure.** Exact credit assignment that rule-based canonicalisation cannot give. 4B competitive with closed-source per abstract. |
| 15 | **2406.01549** | An Information Bottleneck Perspective for Effective Noise Filtering on RAG (IB-RAG) | Variational IB: maximise I(compression; ground_output) − minimise I(compression; retrieved_passage); reused as both SFT data-selection criterion and RL reward | Trains a *compressor* (writer-shaped module) between retrieval and reader; objective transfers directly to a memory writer's output distribution | **Best theoretical framing**: principled IB objective subsumes rule-based canonicalisation and contrastive losses. Naturally pressures writer to keep only task-relevant slots — exactly those the reader queries. |

---

## Synthesis for `/idea-creator`

The literature gives three crisp white-spaces the next idea could occupy. Each addresses a piece of the β failure:

### S1. **Statistical guarantee at evidence/ranking level (not decision level)** — solves β's "over-abstain" problem
Tools available: PAC-Bayes selective-prediction (#6), bandit routing (#7, #8), e-values (#9), drift detection (#11), OPE (#12). All produce *continuous quality / selection signals* rather than binary abstain/answer. None is yet applied to memory.

### S2. **Cross-system / cross-method composition under risk budget** — solves β's "narrow specialist" problem
Tools available: PILOT bandit routing (#7), off-policy evaluation (#12), risk-budget allocation. Memory subfield has 6+ competing systems (A-Mem, Mem0, MemoryOS, LightMem, SimpleMem, EverMemOS, SmartSearch, APEX-MEM, HyperMem) with different strengths — a calibrated *router* over them gives broad applicability via composition rather than a new specialist. None of the 6+ memory systems does cross-method routing.

### S3. **Training-side writer-parser alignment** — solves β's "canonical-key brittleness" problem
Tools available: Memory-R1 (#13), MemBuilder (#14), IB-RAG (#15). Train the writer with a reader-derived reward signal so writer-output is reader-usable by construction. None of the 6+ memory-frontier systems does this for *temporal-update / supersede* slots specifically.

### Direct architectural threats / mandatory baselines
- APEX-MEM (#1) — append-only graph + retrieval-time resolution = same axis as TTMG
- HyperMem (#2) — pairwise → hypergraph; an ablation question we'd have to answer
- RoMem (#3) — geometric "no-delete" paradigm = different family entirely; possible novel positioning ("explicit truth maintenance vs implicit volatility encoding")
- Synthius-Mem (#4) — sets adversarial robustness floor at 99.55 %
- HiGMem (#5) — direct head-to-head with public code

---

## Reading order for `/idea-creator`

1. This file (`LIT_SURVEY_DELTA.md`)
2. Pre-existing `RESEARCH_BRIEF.md` (Hard constraints in §5; positive constraints §6; direction hints §7)
3. Pre-existing `refine-logs/AGENT_MEMORY_FRONTIER_REPORT.md` (full pre-2026-04 frontier)
4. Optional: pre-existing `refine-logs/M0_FINDINGS.md` for empirical evidence on β's failure mode

`/idea-creator` should brainstorm 8-12 ideas spanning the three white-spaces (S1 / S2 / S3) and check each against the §5 hard constraints in `RESEARCH_BRIEF.md`. Reject anything that would be "another structural-memory variant" or "another narrow specialist".
