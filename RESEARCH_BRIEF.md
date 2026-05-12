# RESEARCH_BRIEF — Long-conversation Agent Memory (post-Path-D, post-β reset)

**Project root:** `/home/workspace/lww/project0412/projects/Temporal Truth-Maintained Memory Graph`
**Date:** 2026-04-27
**Purpose:** Single grounding document for `/idea-discovery`. Consolidates everything we've learned across two failed pivots (Path D + β) so that idea generation does not repeat the same mistakes.

---

## 1. Problem area

Long-conversation agent memory: an LLM agent accumulates many sessions of dialogue with a user; later, it is asked questions whose answers depend on facts the user mentioned (and possibly updated) over time. Three failure modes recur and no current method handles them with a guarantee:

1. **Stale-fact reliance** — facts get updated; retrievers surface obsolete claims; the new Memora benchmark with **FAMA** metric (arXiv 2604.20006, 2026) measures this directly, and shows long-term memory agents lose 18–30 pp from naive accuracy to FAMA.
2. **Over-confident answering on contradictions** — when retrieved evidence disagrees, every existing system (A-Mem, Mem0, MemoryOS, LightMem 2025, SimpleMem 2026, EverMemOS 2026, SmartSearch 2026) returns *some* answer, none provides a coverage guarantee on the abstention decision.
3. **Knowledge-update slice on LongMemEval** — KU questions need "what is the *current* canonical value of X after several updates"; Path D pilot showed even the best 2026 systems fluctuate 60-80 % on this slice with no theoretical bound.

## 2. The 2026 frontier (what we already know — see `refine-logs/AGENT_MEMORY_FRONTIER_REPORT.md` for full survey)

**LoCoMo SOTA (2026):**
- EverMemOS (arXiv 2601.02163, Jan 2026) — **92.3 %** with MemCell foresight + agentic recollection.
- SmartSearch (arXiv 2603.15599, Feb 2026) — **91.9 %** with deterministic CPU pipeline (no LLM in retrieval), 650 ms.
- Structural-memory race on LoCoMo is over. Anything new must differentiate on a non-accuracy axis.

**LongMemEval-S SOTA (2026):**
- SmartSearch — **88.4 %**. SimpleMem — **76.87 %**. LightMem — 68.67 %.

**Memora + FAMA (new benchmark, 2026):**
- A-Mem aggregate FAMA = 154.50 (max 300). MemoryOS 106.67. No memory paper has reported FAMA scores under any other system.

**Diagnosing-Memory (arXiv 2603.02473, ICLR'26):**
- 3×3 factorial on LoCoMo — **retrieval method spread = 20 pp; write strategy spread = 3-8 pp**. ROI is on the retrieval side, not on more sophisticated write-time pipelines.

## 3. Structural white-space (what nobody in the 2026 memory subfield does)

Keyword scan of all 141 .tex files in `MemMachine/competitor/`: **zero matches** for *conformal*, *calibrat-* (in method context), *off-policy / importance sampling*, *mutual information*, *PAC*, *sequential test*, *Lagrang-*, *bandit*. The structural white-space is **statistical / information-theoretic** machinery imported from the RAG / classical-ML literature. Concrete reusable tools:

- **Conformal-RAG** (arXiv 2506.20978, SIGIR'25) — calibrated coverage on retrieval-grounded sub-claims.
- **PMI-RAG** (arXiv 2411.07773) — `PMI(q,C) = log[P(q|C)/P(q)]` correlates affinely with answer log-odds; r > 0.8 across 5 LMs.
- **Swin-VIB** (arXiv 2504.12982) — variational information bottleneck on RAG knowledge conflicts.
- **CRC + Selective Classification** (Angelopoulos 2022, Geifman & El-Yaniv 2017, Bates 2021).

## 4. What we tried, why it didn't work

### Path D (`refine-logs/pathD_FINAL_PROPOSAL.md`, refine score 9.15/10 on paper)
- **Pitch:** "Slot-scoped truth-maintenance specialist with audited applicability gate + all-optima MWIS abstention."
- **Pilot result on LongMemEval-S N=500:** TTMG 62.8 % vs Flat 70 % overall. KU/TR slices flat (0-1 pp). Single-session-assistant **regressed -21 pp**.
- **Why it failed:** Method was reviewer-safe but *another* structural-memory variant in a saturated field. Validity-intervals-as-novelty was already done by EverMemOS (Jan 2026).

### Pivot β (`refine-logs/FINAL_PROPOSAL.md`, refine score 9.15/10 on paper)
- **Pitch:** "Conformal-Selective-Risk-Controlled Memory — first memory operator with provable `Pr[wrong | answered, g] ≤ α`."
- **What we built:** ~1700 LOC across 8 files. Schema + canonicalizer + 3-call linker + applicability gate + canonical-key fetch + all-optima MWIS + Clopper-Pearson UCB + Bonferroni + hierarchical merging.
- **M0-1 smoke results (`refine-logs/M0_FINDINGS.md`):**
  - On Memora (`weekly` × 1 persona × 15 q): **0/15 questions routed to `route=ttmg`**. 5 reasoning q routed to `abstain` (writer extracted multi-day per-event values; β correctly fired `non_unique_value`); 10 non-reasoning routed to `flat` fallback. Parser was correctly classifying — Memora's question distribution simply doesn't fit β's "single-value lookup" scope.
  - **Global parser probe (10 personas × 15 q = 150 q):** applicability = **33 %** uniformly across personas. All applicable questions are aggregation/comparison — β operationally answers **0 %** of Memora.
  - On LongMemEval-S KU (3 q × 3 sessions): β scored 1/3 (and that 1 was a virtue-rewarded false-positive abstention — gold = "132 points", β said "I don't know", judge said "abstains appropriately"). **Path D control on identical 3 q: 2/3.**
- **Why it failed:** Three coupled reasons:
  1. **Strict canonical-key matching is paraphrase-fragile.** Writer extracts `user.preferred_bbq_sauce`; parser asks for `user.bbq_sauce_brand`; canonicalizer's lemma+lowercase doesn't bridge them; β can't fetch; falls back to k-NN over claims (still empty); abstains. Path D escapes this via `raw_turn_fallback` (raw text reader-side).
  2. **"Answer iff |Vals|==1" is too brittle on noisy claim graphs.** Even when canonical_key matches, multiple per-day values for "food_spending" force abstention even though the user clearly wants the sum.
  3. **Single-valued-only scope** rules out > 60 % of natural questions (multi-valued lists, recommendation, content generation, aggregation). Applicability gate fires `route=flat` and β's CRC contribution is dead in those cases.

### Cross-cutting lesson
**β's CRC layer is mathematically clean but coupled to a brittle decision rule on a brittle write-read interface.** The `Pr[wrong | answered, g] ≤ α` guarantee technically holds but is vacuous when the operator answers nothing. The narrow specialist framing didn't generalize.

## 5. Hard constraints for the next idea (must avoid)

1. ❌ **No "specialist on N % slice" framing** with N < 50 %. Methods that only cover a narrow slice of the question distribution will get reviewer-rejected as "demos, not methods".
2. ❌ **No requirement for writer-parser canonical naming alignment.** Paraphrastic natural language breaks any "exact match on (entity, slot_name)" decision rule. Soft / fuzzy / learned matching is OK; rule-based exact match is not.
3. ❌ **No over-abstain decision rules.** "Answer iff X" rules where X is rarely true → method dies. Bias should be toward graceful degradation (rank quality, partial credit, soft routing) not hard abstain.
4. ❌ **No "single-valued slot only" scope.** Real questions are multi-valued (lists), aggregation (sums/counts), recommendation, comparison. The method must work on at least the major fraction of these.
5. ❌ **No exact (subject, predicate, object) triple dependence** — LLM-extracted triples are too noisy.
6. ❌ **No "more sophisticated write-time pipeline".** Diagnosing-Memory has shown this has poor ROI vs read-side. Don't pile on writer modules.
7. ❌ **No re-litigation of A-Mem / SimpleMem / LightMem-style structured memory.** That race is over.

## 6. What we want to keep (positive constraints)

1. ✅ **Statistical / information-theoretic guarantee or theoretical contribution** — the structural white-space is real and is the field's biggest unexplored axis. Conformal coverage, PMI gauges, VIB bottlenecks, sequential testing — all reusable.
2. ✅ **Forgetting-aware metric (FAMA)** as one of the validation surfaces — first-mover advantage on Memora.
3. ✅ **Hybrid retrieval (semantic + lexical + raw-turn)** — Path D's `raw_turn_fallback` is empirically strong; any new method should keep it as fallback, not throw it away.
4. ✅ **Read-side investment** — Diagnosing-Memory says retrieval drives 20 pp; new mechanism should attack the read side.
5. ✅ **Path D substrate as engineering scaffolding** (claim graph + supersede edges + active flag) — reusable but optional, not core.
6. ✅ **Validation on at least 2 public benchmarks** — LongMemEval-S, LoCoMo, Memora-FAMA all available locally.

## 7. Direction hints (not binding — `/idea-creator` may rewrite)

The user's intuition (worth seeding into idea generation):

- **Generalisability over specialisation.** Whatever we propose must apply broadly across question types, not just to a narrow slice.
- **Move "guarantee" from decision-level (abstain or not) to ranking-level or evidence-level.** Examples:
  - Calibrated *quality scores* on retrieved memory items (rank-aware conformal) instead of binary abstain.
  - Forgetting-aware *retrieval reranker* that fuses supersede / contradict signals into a continuous score.
  - Cross-method *conformal router* that selects between A-Mem / Mem0 / LightMem / SmartSearch dynamically with a guarantee on "selecting the worst method".
  - Information-theoretic *retrieval evaluation metric* (analogue of FAMA but for retrieval, not answer) with conformal coverage.
- **Or training-side:** RL / preference signal teaching writer to extract claims that maximize downstream KU accuracy — solving the writer-parser alignment problem by training instead of by canonicalization rules.
- **Or completely orthogonal:** memory **compression with provable information preservation** (information-theoretic compression bound on retained memory), tying conformal + VIB.

## 8. Available compute, data, time

- **Compute:** 1-2 RTX-4090 class GPUs, MAAS API for writer/parser/reader/judge (`deepseek-v3.2`, `Kimi-K2`, `glm-5.1` accessible), shared host load varies wildly (1.7-100+ during this project; check `uptime` before any parallel launch).
- **Data:** All locally available — Memora, LongMemEval-S full N=500, LoCoMo (Path D pilot results in `results/`), PopQA/NQ/EntityQuestions/HotpotQA/AmbigQA/FEVER/QASPER as supplementary factoid baselines.
- **Time:** 3-5 weeks for full implementation + paper.
- **Code:** Path D substrate (`ttmg/`) is committed and runnable; β additions (`ttmg/crc.py`, `ttmg/pmi.py`, `scripts/calibrate_crc.py`) work but are off-by-default with `enable_beta=False` flag.
- **Existing baselines reproducible:** Path D's `ttmg`, A-Mem reimpl in `ttmg/baseline_amem.py`. Mem0 / LightMem / EverMemOS upstream code in `MemMachine/competitor/*/code/` (not yet installed).

## 9. Venue target

NeurIPS / ICML main track preferred. Acceptable fallbacks: ICLR, ICLR 2026 MemAgents Workshop, AAAI.

---

## What `/idea-discovery` should produce

A **non-incremental, broadly-applicable** idea that:
- Brings statistical / info-theoretic / training machinery from outside the memory subfield into it
- Passes hard constraints in §5
- Has at least 50 % applicability across natural question types
- Has a clear empirical claim verifiable on LongMemEval-S OR LoCoMo OR Memora
- Distinguishes cleanly from EverMemOS, SmartSearch, SimpleMem, LightMem, A-Mem, Mem0
- Survives a /research-review round at score ≥ 8

If `/idea-creator` produces only narrow specialist ideas again, regenerate with stronger "must be broad" constraint.

## Reference reading order for sub-skills

1. This brief (RESEARCH_BRIEF.md)
2. `refine-logs/AGENT_MEMORY_FRONTIER_REPORT.md` — full 2026 frontier survey + per-paper cards
3. `refine-logs/M0_FINDINGS.md` — what β actually did when run (the empirical falsification of "narrow specialist" framing)
4. `refine-logs/IDEA_EVALUATION.md` — original diagnosis of Path D being incremental
5. `refine-logs/LIT_SURVEY.md` — the user's own white-space scan (where conformal / PMI / etc tools come from)
