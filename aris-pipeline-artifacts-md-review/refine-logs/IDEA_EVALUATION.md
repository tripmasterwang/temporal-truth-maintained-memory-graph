# TTMG Idea Evaluation — Competitor-Aware, Evidence-Grounded

**Date:** 2026-04-26
**Inputs:** `idea.md`, `STATUS.md`, current results in `results/`, current paper in `paper/`, 6 competitor papers in `competitors/`.
**Bottom line up front:** The conceptual gap TTMG targets (explicit truth maintenance with temporal validity + supersede edges) is **genuinely uncovered** by the 6 surveyed competitors — the novelty premise is real. But the **execution as it stands does not survive contact with these competitors' evaluation bar, and several of the original idea.md success criteria are already failed.** The paper as currently scoped is unlikely to clear top venue without either a reframe + scope reduction, or substantially more experiments. Concrete recommendations at the end.

---

## 1. What the field's current bar looks like (2025–2026)

Drawn from the 6 papers in `competitors/`. One caveat first:

> **Wrong-file flag.** `competitors/memgpt/` contains "Transformers as Decision Makers" (Lin/Bai/Mei, arXiv 2310.08566), an in-context RL theory paper — **not** the MemGPT memory system (Packer et al., arXiv 2310.08560, six digits off). MemGPT is cited by every other competitor as a baseline; you do **not** currently have the actual MemGPT paper or code in this folder. Fix that before claiming "we surveyed MemGPT."

### 1.1 Common framing patterns
- **Memory-as-organization** — A-Mem (Zettelkasten links + memory evolution), MemoryOS (3-tier OS hierarchy).
- **Memory-as-efficiency** — LightMem, SimpleMem, Mem0 (token cost is the headline).
- **Memory-as-system** — full pipelines with storage + update + retrieval + generation.

**None** of the 6 frame the problem as *temporal truth maintenance, conflict resolution, or supersede semantics*. That is TTMG's white space — and it really is white space.

### 1.2 De facto evaluation backbone
- **Benchmarks**: LoCoMo (5/6 papers), LongMemEval / LongMemEval-S (LightMem, SimpleMem). DialSim only by A-Mem. MemoryAgentBench mostly absent in published comparisons.
- **Baselines (canonical set)**: ReadAgent, MemoryBank, MemGPT, A-Mem; plus Mem0/LangMem/Zep/full-context for newer papers.
- **Backbones**: 3+ LLMs is now standard. SimpleMem uses 4 (GPT-4.1-mini, GPT-4o, Qwen3-8B, smaller). LightMem uses 3 (GPT-4o-mini, Qwen3-30B-A3B, GLM-4.6).
- **Metrics**: F1 + BLEU-1 + LLM-as-Judge + token cost + latency + construction time. Efficiency is now mandatory, not optional.
- **Seeds**: 1–10 (Mem0 reports 10 runs for Judge; most are 1).

### 1.3 Where the bar is on TTMG-relevant axes
| Axis | Field bar (2026) | TTMG today |
|------|------------------|------------|
| LongMemEval-S accuracy | SimpleMem 76.87 % (GPT-4.1-mini); LightMem 68.67 % | **62.8 %** at N=500 (deepseek-v3.2 reader). Below both. |
| LoCoMo improvement | All 5 memory papers report wins vs full-context | **TTMG -13.4 pp vs Flat** (38.3 % vs 51.7 %). The only paper losing on LoCoMo. |
| Token efficiency | LightMem: 10–38× reduction. SimpleMem: 32× (531 vs 16,900). | **TTMG: ≈12× more expensive than Flat (13,603 vs 1,100 tok/q).** Wrong direction. |
| Construction time | SimpleMem: 92.6 s for full corpus. | **TTMG: 80.3 s ingest per question** — at corpus scale this is orders worse. |
| Backbones tested | 3–4 typical | 1 (deepseek-v3.2 reader) |
| Seeds | 1–10 | 1 (seed=0) |

**Read:** the field has, in the 12 months since A-Mem, moved hard toward *efficiency-with-accuracy*. TTMG was conceived against the A-Mem 2025 frontier; it is being evaluated against the LightMem/SimpleMem 2026 frontier. The implicit baseline shifted.

### 1.4 Closest prior art to TTMG's mechanism
| Competitor | Closest mechanism | Why it isn't truth maintenance |
|------------|-------------------|--------------------------------|
| **A-Mem** | "Memory evolution" — new note can update neighbours' contextual descriptions | Semantic refresh, not validity; no supersede edges, no contradiction labels, no temporal windows |
| **SimpleMem** | "Temporal anchoring" (relative→ISO-8601) + symbolic-layer index + intent-aware retrieval planning | Enables ordering and time-sliced filtering, but no `valid_from/valid_to`, no contradict/supersede edges, no abstain-on-conflict |
| **MemoryOS** | Heat-based eviction, dialogue-chain FIFO | Recency proxy, not truth maintenance |
| **LightMem** | "Sleep-time" offline consolidation | Compaction, not validity tracking |
| **Mem0** | NL + optional graph | Storage layout choice; no validity, no conflict |

**Verdict on novelty.** Truth maintenance + temporal validity + supersede edges is a real conceptual gap. **But the gap is narrower than idea.md implies** — SimpleMem's intent-aware retrieval planning + symbolic temporal layer already does a weak version of "use temporal anchors at read time", and A-Mem's evolution mechanism already does a semantic version of "update past memory in light of new memory". A reviewer who has read SimpleMem will ask: *what does TTMG do that SimpleMem's planning + symbolic temporal index does not already do?* That question must be answerable in one paragraph of the intro.

---

## 2. Hard issues in `idea.md`, ranked

### Issue H1 — Several pre-registered success criteria are already failed
`idea.md` set explicit failure thresholds:

| Promised | Delivered (N=150) | Delivered (N=500) | Status |
|----------|-------------------|-------------------|--------|
| KU/TR absolute +3–6 pp | KU +0 pp, TR +0 pp | KU −2.6 pp, TR +0.75 pp | **Missed** |
| Abstention error −20–30 % | n=9 subset: +44.5 pp accuracy. **Full n=30: 0 pp, p=1.0** | — | **Missed on full set** |
| Token cost ≤ +15 % | +1,137 % vs Flat | — | **Massively missed** |
| Latency ≤ +20 % | +64.8 % | — | **Missed** |
| Failure clause: "if abs gain <2 pp or latency >20 % w/o gain → design does not hold" | Overall −6.7 pp, latency +64.8 % | Overall −7.2 pp | **Triggered by author's own rule** |

`idea.md` has a self-described kill criterion, and the criterion has fired. STATUS.md works around this by selecting "TR +15.3 pp" — a number that **does not appear in any actual results JSON**. The audit could not reproduce it from `pilot_n150_*.json`; the real TR slice at N=150 is 52.5 % (Flat) vs 52.5 % (TTMG). The "+15.3 pp" headline used to maintain morale through 11 review rounds is not supported by data.

This is the single most important issue. The internal narrative and the actual experimental record have diverged.

### Issue H2 — Standalone TTMG underperforms the simplest baseline
Overall accuracy (LongMemEval-S):
- **N=150**: Flat 68.0 %, A-Mem 67.3 %, **TTMG 61.3 %** (−6.7 pp)
- **N=500**: Flat 70.0 %, **TTMG v5.1 62.8 %** (−7.2 pp)

The audit's per-slice breakdown shows the regression concentrates on **single-session-assistant** (−21.4 pp at N=500), **multi-session** (−12.0 pp), and **single-session-preference** (−13.3 pp). These are exactly the slices where having a *parsed claim graph* discards information that a flat hybrid retriever still has access to (raw turn surface form, full assistant utterance).

Reviewer reading: "Your method is strictly worse than RAG on 4 of 6 slices, and the only slice where it actually helps (TR) ties Flat." That is fatal at top venue unless the paper explicitly reframes around the slice where it wins.

### Issue H3 — Cross-domain failure on LoCoMo is the hardest fact to spin
Every other memory paper in the survey reports **wins** on LoCoMo. TTMG reports **−13.4 pp vs Flat** (38.3 % vs 51.7 %). And LoCoMo isn't even in the paper currently — STATUS.md from 2026-04-22 still says "loader at experiments/eval_locomo.py, never run", but the JSONs exist and are bad. This is the result that:
- Makes TTMG the only paper in the cohort with a published cross-domain regression.
- Cannot be hidden by writing-only changes (a reviewer running the code on LoCoMo will reproduce the failure).
- Strongly suggests the claim schema is **lossy on long, dense, coreference-heavy multi-turn dialogues** — exactly what LoCoMo is.

### Issue H4 — Cost/efficiency story runs against the field's current
LightMem and SimpleMem are 2025-Q4/2026-Q1 papers whose **entire contribution is efficiency**. TTMG ships the opposite: 12× tokens vs Flat, 80 s/question ingest. Even the "we beat A-Mem on tokens by 64 %" claim is dead on arrival, because no current memory paper compares to A-Mem on tokens — they compare to LightMem (10–38× reduction) and SimpleMem (32× reduction). TTMG's token efficiency claim is two generations stale.

### Issue H5 — Novelty is real but argued from the wrong reference frame
`idea.md` argues novelty against A-Mem ("we add validity intervals and supersede edges to A-Mem"). The relevant 2026 frontier is SimpleMem's intent-aware retrieval planning + symbolic temporal index, which already does a weaker version of read-time temporal filtering. If the paper's intro doesn't crisply answer "why isn't this just SimpleMem + a contradict label?", the contribution will be downgraded from "new mechanism" to "small addition on top of SimpleMem". The ablation `--disable-contradict` (−33.3 pp on n=9 abstention, −5 pp on TR) **could** carry that argument — but only if it's run against SimpleMem-style retrieval, not against TTMG-with-claims-only.

### Issue H6 — Single ablation, single seed, single backbone
- **One ablation** (linker on/off). Field standard is 4–6 (schema, temporal validity, consistent-subgraph, raw-turn fallback, NLI threshold sensitivity, etc.). The audit lists exactly this set as missing.
- **One seed** (seed=0). Field is 1–10; without seed=7 + seed=17 you cannot make any "significant" claim, and you currently make none — but you also can't *defend* against "your effects are noise".
- **One backbone** (deepseek-v3.2 reader, Kimi-K2 writer/parser). Competitors use 3–6. A reviewer will say "does this work because TTMG helps, or because deepseek-v3.2 happens to like claim-formatted context?"

### Issue H7 — Statistical claims rest on n=9 / n=21 slices
The "abstention 44.4 → 88.9" win is on n=9 stratified subset. The "SSU 90.5 → 100" win is on n=21. McNemar p-values reported in the paper itself acknowledge non-significance (p=0.21 overall, p=1.0 on full abstention n=30). This is honest but it means **none of the headline numbers are statistically supported**.

### Issue H8 — Drift between idea.md, STATUS.md, paper, and reality
- `idea.md`: aspirational, success criteria explicit, kill criterion explicit.
- `STATUS.md` (2026-04-22): claims "+15.3 pp on TR" which the audit cannot reproduce; claims "LoCoMo never run" although three LoCoMo JSONs exist showing TTMG loses.
- `paper/sections/4_experiments.tex`: reports the −6.7 pp overall regression honestly with McNemar p=0.21.
- `results/`: ground truth is the −6.7/−7.2 pp regression, plus LoCoMo loss, plus full-n=30 abstention tie.
- Latest review `review_tri_r10.json`: average 5.5/10 (target 8.5), GLM reviewers all weak-reject.

The narrative the project is operating under no longer matches the experimental record. This shows up in 11 rounds of writing-only review with peak score 7.0 and now down to 5.5 — you have hit a wall that prose cannot get past.

### Issue H9 — Per project policy ("不得仅写进 limitation 即结案"), the failures must be addressed, not papered over
CLAUDE.md states reviewer concerns answerable by experiments / scope-tightening cannot be deflected to limitations. H1, H2, H3, H6, H7 are all answerable by experiments or by reframing claims — so per the project's own quality policy they must be acted on, not parked in limitations.

---

## 3. What the idea still has going for it

Listing the load-bearing wins so they don't get thrown out:

1. **Real conceptual gap.** Truth maintenance + temporal validity + supersede semantics genuinely is missing from the 6 surveyed methods. SimpleMem comes closest (intent-aware retrieval + symbolic temporal index) but does not do contradict/supersede.
2. **Linker is causally validated.** Removing the LLM linker drops abstention by 33.3 pp and TR by 5 pp — the mechanism does *something* real, even if the overall regression masks it.
3. **TR slice at N=500 is ≥ Flat (+0.75 pp).** Not statistically significant, but at least *not worse* — meaning the targeted axis is at minimum non-degraded, while the off-target slices regress. This is a "specialist not generalist" signature, which is publishable if reframed honestly.
4. **Full claim schema + edge typology + greedy consistent-subgraph algorithm is implemented and clean** (`ttmg/schema.py:49–98`, `conflict_linker.py:68–150`, `truth_retriever.py:70–150`). Code asset is real.
5. **A-Mem reimplementation lets you ablate against an apples-to-apples agentic baseline** with the same backbone. The competitors all use whatever wrapper their own repo provides; you have the only actually-controlled A-Mem comparison in this stack.
6. **Abstention behaviour is observable** (80 % explicit "I don't know" on abstention questions). Even though n=30 accuracy doesn't move, the *behavioural* metric (calibrated abstention rate, correct-decline ratio) is something competitors don't report at all and could be a small genuine contribution.

---

## 4. Where to go from here — three honest paths

These are not implementation plans (use `/research-refine` then `/experiment-plan` for that). They are three distinct strategic choices, each viable, with different costs.

### Path A — **Reframe as a slot-in conflict-aware retrieval/abstain layer**
Drop the "full memory system" claim. Position TTMG as a *retrieval-time* module that takes any agent-memory base (A-Mem, Mem0, LightMem, SimpleMem) and adds: (i) claim parsing of retrieved candidates, (ii) contradict/supersede labelling, (iii) consistent-subgraph filtering, (iv) abstention on residual conflict.

Pros: side-steps H2/H3 (you no longer compete with Flat overall — you compose on top of strong baselines). Maps cleanly to the H5 reviewer concern ("isn't this SimpleMem + a label?" — answer: yes, and it adds 5 pp on TR + N pp on abstention when stacked). Uses the existing code with minimal changes.
Cons: requires running TTMG-on-top-of-SimpleMem and TTMG-on-top-of-LightMem (need their code). Needs at least one of those collaborations to run cleanly.
Cost estimate: 2–3 weeks integration + 1 week of stacked evaluations.

### Path B — **Reframe as a temporal-reasoning specialist; tighten claims**
Keep TTMG as a standalone system but **explicitly and honestly** scope to temporal-reasoning + knowledge-update + abstention. Drop "general agent memory" framing entirely. Headline claim becomes: "On the TR slice, TTMG matches Flat at N=500 with linker causally responsible for 5–10 pp on the harder TR sub-slices, plus calibrated abstention behaviour absent from baselines."

Pros: matches the experimental signature you actually have. Honest. Can be a workshop or applied-track paper at NeurIPS/ICLR without much new compute. Survives the H1 failure clause if the failure clause itself is re-stated.
Cons: this is a smaller paper. Probably not main track at NeurIPS/ICML. Requires multi-seed runs (seed 7, 17) for any significance claims.
Cost estimate: ~1 week (multi-seed + slice-focused writing). This is also closest to the path STATUS.md outlines.

### Path C — **Pivot to a controlled conflict / temporal-validity benchmark**
Build a synthetic/semi-synthetic benchmark where temporal validity, supersedes, and contradictions are *labelled ground truth* — e.g. extend LongMemEval-KU with timestamped fact updates, or wrap LoCoMo with injected fact contradictions. Then TTMG can show clean wins on the constructed slice + partial transfer to natural data.

Pros: turns the LoCoMo failure into a *diagnostic*: "natural benchmarks don't isolate truth-maintenance error modes; here is a benchmark that does, and TTMG is the only method that wins on it." Most defensible novelty story. Aligns with where benchmarks for memory systems are going (MemoryAgentBench, OG-Mem, etc.).
Cons: most expensive path. Requires building + validating a benchmark, which is its own paper. ~6–10 weeks if it's the next step.

### Path D — **Combination (recommended for top-venue probability)**
**B + a small slice of C.** Keep the system standalone, scope to TR/KU/abstention, *and* construct a small (~200 question) controlled conflict-update sub-benchmark on top of LongMemEval-S where TTMG can demonstrate clean wins. Run multi-seed. Report the LoCoMo loss honestly with the diagnostic framing from C ("LoCoMo lacks labelled supersede relations; on the supersede-labelled slice, TTMG wins by X").

This concedes H2 (you are no longer claiming to beat Flat overall), addresses H3 (LoCoMo gets reframed instead of hidden), addresses H1 (kill criteria are restated against the scoped task), and addresses H6/H7 (multi-seed + new slice provide actual evidence). Linker ablation H6 still needs the missing 4–5 ablations.

---

## 5. The non-negotiables before any path

Independent of which path you pick, these must happen — most are 1-day-each fixes:

1. **Reconcile STATUS.md with results.** The "+15.3 pp on TR" claim is not in any JSON. Either find the file it came from, or correct STATUS.md. Currently this number propagates into your own planning.
2. **Add LoCoMo to the paper.** Hiding a known regression is worse than reporting it; the JSONs exist on disk and a reviewer running your repo will find them.
3. **Run seeds 7, 17 on N=150** for at least the three core methods (Flat, A-Mem, TTMG). All headline numbers need CIs or they fail H7.
4. **Run the four missing ablations**: schema-only, no-validity-filter, no-consistent-subgraph, no-raw-turn-fallback. Field-standard. Without these the H6 critique is unanswerable.
5. **Pull the actual MemGPT paper** (arXiv 2310.08560) into `competitors/memgpt/` and re-survey. Currently you are missing the most-cited baseline in this subfield.
6. **Add SimpleMem and LightMem as comparison baselines** — at minimum, cite their LongMemEval-S numbers in the paper's results table. They were published before your submission window and a reviewer will ask why you don't compare.
7. **Restate the success / failure criteria** against the scoped task (e.g. "TR + KU + abstention combined accuracy ≥ Flat at p<0.05 with ≤1.5× tokens"), and judge the design against the new criterion explicitly. The original `idea.md` criterion has fired; ignoring it is the single biggest credibility risk.

---

## 6. Suggested next concrete step

Pick a path (recommend D), then run `/research-refine` with a **focused** PROBLEM/APPROACH like:

```
PROBLEM: TTMG underperforms Flat overall on LongMemEval-S (-7 pp) and on LoCoMo (-13 pp),
but the linker is causally responsible for +33 pp on abstention and +5 pp on TR sub-slices,
and the conceptual gap (no competitor does explicit supersede / temporal-validity edges)
is real. The paper currently fails its own pre-registered success criteria.

APPROACH: Reframe as a TR/KU/abstention specialist with a small controlled supersede slice;
add multi-seed + 4 missing ablations + LoCoMo-honest reporting + SimpleMem/LightMem cite-comparison;
defend novelty against SimpleMem's intent-aware retrieval rather than against A-Mem.
```

That input has a real problem, a real anchor (the gap from §1.4), an explicit method change (reframe + scope), and concrete experimental commitments — exactly what `/research-refine` is meant to sharpen.

If you want, I can also run `/research-refine` directly on Path A or Path C as alternatives so you have refined plans for all three before committing.

---

## 7. One-line summary

> The conceptual hole TTMG aims at is real and uncovered. The current execution lost the race against the 2026 efficiency-first frontier (SimpleMem, LightMem) and is failing its own pre-registered success criteria, including a cross-domain regression on LoCoMo it does not currently report. The paper needs a reframe + scope reduction + statistical hardening before more review rounds will help; another round of writing-only iteration will not move the score.
