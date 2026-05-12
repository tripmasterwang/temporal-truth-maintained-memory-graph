# Experiment Plan — CalLB

**Problem**: 88.2 % of Path D `ttmg` wrong answers on LongMemEval-S are read-side actionable (41 % retrieval-surfaces-wrong-content = Class B; 47 % reader over-specification after correct grounding = Class C; gating decomposition over 186 wrong answers, `results/gating_decomposition.json`). No 2026 frontier system addresses both with a calibrated mechanism.

**Method Thesis**: For each retrieved memory item, fuse semantic + lexical + claim-graph + raw-turn substrate signals into a learned reliability score; calibrate a single threshold `λ̂_α` via **Conformal Risk Control on the clean-set indicator** so that with prob ≥ 1 − α, the load-bearing tier `L_λ̂_α(q)` contains no distractor; reader is given tiered prompt (LOAD-BEARING vs SUPPORTING).

**Date**: 2026-04-27

---

## Claim Map

| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|---|---|---|---|
| **C1 (Dominant, Formal)** Probabilistic clean-set guarantee `Pr_test[L_λ̂_α(q) contains distractor] ≤ α` w.p. ≥ 0.95 over cal-split, validated empirically on **two independent public benchmarks** (LongMemEval-S + Memora). | First memory operator with a coverage-style guarantee on what the reader sees as load-bearing context. CRC is off-the-shelf; the novel object is the clean-set risk for memory evidence selection. | (a) Empirical `R̂_test(λ̂_α) ≤ α + 0.04` for α ∈ {0.10, 0.20, 0.30, 0.40} on **both** LongMemEval-S test and Memora test (Clopper-Pearson UCB + 100-pt grid + δ/m=0.0005 union bound). (b) Non-vacuity: `non_empty(L) ≥ 0.85`, `mean |L| ∈ [2,5]`, `LB_recall ≥ 0.75` at α* = 0.20. (c) Cross-dataset robustness (Path B): when calibrated on LongMemEval-S → tested on Memora directly, CRC bound holds within α + 0.06; `no_CRC`'s fixed dev-threshold violates by > 0.10. | B1, B4, B5 |
| **C2 (Supporting, Empirical)** Calibrated load-bearing selection produces measurable B+C-prone slice lift on LongMemEval-S vs Path D `ttmg` and three frontier-adjacent neighbors (MiCP, Stop-RAG, Flat-RAG). | The formal guarantee must compose into something the reader's accuracy benefits from; otherwise calibration is cosmetic. | ≥ **3 pp lift** on union of B-prone (KU, single-session-preference) + C-prone (single-session-user, multi-session, KU) slices vs Path D `ttmg`; no slice regression > 1 pp; mean ± std over 3 seeds; cluster-bootstrap p < 0.05 vs baseline. | B1, B3 |
| **Anti-claim to rule out** "The gain just comes from the load-bearing prompt change without calibration." OR "A simple agreement-heuristic + dev-tuned threshold matches CalLB; the MLP + CRC machinery is unnecessary." | A reviewer's first attack will be that the prompt or the heuristic is doing the work. | `prompt-only` (Path D top-k + same load-bearing prompt; no MLP/CRC) captures < 50 % of CalLB's slice lift. `agreement-heuristic-only` captures < 70 %. **`no_CRC` (same MLP + dev-tuned fixed threshold) is beaten by CalLB by ≥ 1 pp w/ paired-bootstrap p < 0.05** (Path A) OR cross-dataset transfer test (Path B). | B2, B3 |

(MAX_PRIMARY_CLAIMS = 2 honored: C1 dominant + C2 supporting.)

---

## Paper Storyline

- **Main paper must prove** (3 pieces, in this order):
  1. The empirical clean-set CRC guarantee holds on both LongMemEval-S test and Memora test at four α values (Block B4 → main table + per-α reliability figure).
  2. The guarantee is non-vacuous (`L` is populated and contains LB items; Block B1 → utility-metric panel).
  3. Calibrated load-bearing selection causes ≥ 3 pp B+C-prone slice lift on LongMemEval-S vs Path D + 3 frontier-adjacent neighbors, AND beats the strongest non-calibrated alternative `no_CRC` by ≥ 1 pp w/ p < 0.05 (Block B1 + B2 → main accuracy table + Path A/B verdict).
- **Appendix can support**:
  - Class-B-rescue qualitative analysis on the 77 gating examples (Block B7 → narrative reframe trigger if low-agreement-rescue dominates).
  - LoCoMo parity (Block B6 → just shows we don't regress; LoCoMo SOTA is saturated and not the contribution).
  - EverMemOS-on-Memora (best-effort reproduce; Block B5 sub-row).
  - Mechanism + generality ablations (Block B3) — at least one in main paper, rest in appendix.
- **Experiments intentionally cut**:
  - `random-MLP + CRC` (uninformative — only proves random scores are bad; reviewer R3 rejected).
  - Per-question-type model split (used as reporting stratum, not a model variant).
  - Writer fine-tune (not the bottleneck per gating; out of scope).
  - Memory-architecture innovation (out of scope; Path D substrate frozen).
  - LoCoMo SOTA chase (frontier saturated 92.3 %; parity is the right target).

---

## Baseline 对照与豁免 (per `docs/ARIS_RESEARCH_QUALITY_POLICY.md` 第 5 节)

### Named strong / representative baselines (frozen in this plan)

| Baseline | Family | Why named | Anchors which block(s) |
|---|---|---|---|
| **Path D `ttmg`** | Reader on same TTMG substrate, no CalLB | Direct apples-to-apples baseline; isolates the CalLB delta on identical retrieval | B1 (main), B5, B6 |
| **MiCP-on-Path-D** | Per-query conformal stopping (arXiv 2604.01413) ported to candidate set | Closest statistical neighbor; tests the per-query-vs-per-item granularity claim | B1 (main) |
| **Stop-RAG-on-Path-D** | RL stopping for iterative RAG (arXiv 2510.14337) | Closest RL-based stopping baseline | B1 (main) |
| **Flat hybrid-RAG** | Sem + lex RRF, no claim-graph | Strongest non-TTMG substrate baseline | B1 (main) |
| **A-Mem** | Reimpl from `competitors/A-mem-main` | Memora baseline; CalLB's own reader stub built atop | B5 |
| **Mem0** | Best-effort reproduce | Mem-OS baseline family | B5 |
| **LightMem** | Best-effort reproduce | Lightweight memory baseline | B5 |
| **EverMemOS** | Best-effort reproduce, **appendix only** | LoCoMo SOTA Jan 2026 (92.3 %); Memora-port if available | B5 (appendix sub-row) |
| **SmartSearch** | LoCoMo-only baseline (91.9 %) | LoCoMo parity check | B6 |

### Which blocks include "Ours vs [baseline]"

- **Main table block** (per policy 第 5 节 main): **B1** (CalLB vs {Path D ttmg, MiCP-on-Path-D, Stop-RAG-on-Path-D, Flat hybrid-RAG} on LongMemEval-S full N=500, 3 seeds, mean ± std).
- **Mechanism block**: **B2** (CalLB vs `no_CRC`; the calibration-isolation comparison — `no_CRC` is the strongest non-trivial alternative under the same MLP scores).
- **Resource / efficiency block**: not applicable — CalLB and all baselines run on the same MAAS endpoint (`deepseek-v3.2`); the only added cost is one MLP forward pass per candidate (sub-millisecond).

### Sanity / debug-only blocks (no claim of superiority)

- **B0 intrinsic acceptance gates**: LLM-judge κ ≥ 0.7 / 0.75; MLP dev AUC ≥ 0.75; per-α dev coverage ≤ α + 0.02. These are calibration-time gates, not paper claims.

### Rationale for ablation-only blocks (B3 attribution + mechanism + generality)

These 8 ablations are pure self-ablation. Per policy 第 5 节: "Pure self-ablation is allowed **only** for narrow component-necessity claims **if** the narrative already provides Ours vs baseline elsewhere". B1 provides the four required Ours-vs-baseline rows on the main table, so B3's component-necessity claims are scoped to: "removing component X drops slice lift by Y %". They do not stand alone as evidence of superiority.

### Waivers

None required. Every paper-level claim of superiority has at least one named non-trivial baseline under the same protocol.

---

## 双榜门闸 (per `docs/ARIS_RESEARCH_QUALITY_POLICY.md` 第 6 节, `TWO_BENCHMARK_CONTINUE_GATE`)

**Gate definition.** Before treating CalLB as ready for paper-ready submission, require **clear, consistent gains on at least two independent public benchmarks vs strong baselines**.

### Public benchmarks (both with citation, split, metric)

| Benchmark | Citation | Split | Metric | Baseline(s) |
|---|---|---|---|---|
| **LongMemEval-S** | arXiv 2410.10813 (Wu et al. 2024) | Full N=500 (`longmemeval_s.json` from `/home/workspace/lww/project0412/projects/dataset/LongMemEval-main/`) | LLM-judge accuracy on B+C-prone slice union (single-session-user + KU + single-session-preference + multi-session); per-α empirical CRC risk | Path D `ttmg`, MiCP-on-Path-D, Stop-RAG-on-Path-D, Flat hybrid-RAG |
| **Memora (FAMA-evaluated)** | arXiv 2604.20006 (Memora-FAMA, 2026) | Full test (per `competitors/memora-eval-main/`) | Aggregate FAMA per duration; per-α empirical CRC risk; Path B cross-dataset transfer test | A-Mem, Mem0, LightMem, EverMemOS-appendix |

### Pass / fail criteria

The gate has **two layers** because CalLB has both a formal claim (C1) and an empirical claim (C2):

#### Layer 1 — Dominant claim (C1, formal CRC guarantee)

| Benchmark | Pass criterion |
|---|---|
| LongMemEval-S | Empirical `R̂_test(λ̂_α) ≤ α + 0.04` for ≥ 3 of 4 α ∈ {0.10, 0.20, 0.30, 0.40}; non-vacuity targets met (`non_empty ≥ 0.85`, `LB_recall ≥ 0.75`). |
| Memora | Empirical `R̂_test(λ̂_α) ≤ α + 0.04` for ≥ 3 of 4 α; non-vacuity targets met. |
| **Layer-1 pass = both rows pass** | Formal claim is validated on two independent public benchmarks. |

#### Layer 2 — Supporting claim (C2, empirical lift)

| Benchmark | Pass criterion |
|---|---|
| LongMemEval-S | ≥ 3 pp B+C-prone slice lift over Path D `ttmg`; cluster-bootstrap p < 0.05; no slice regression > 1 pp. **Plus** Path A: beats `no_CRC` by ≥ 1 pp w/ paired-bootstrap p < 0.05 OR Path B: cross-dataset CRC threshold transfers within α + 0.06 while `no_CRC`'s fixed threshold violates by > 0.10. |
| Memora-FAMA | Within 3 pp of best baseline on temporal-forgetting subset (parity claim). |
| **Layer-2 pass = LongMemEval-S clearly wins AND Memora parity holds AND Path A or Path B passes.** | Empirical claim is validated on the primary benchmark; second benchmark provides parity + cross-dataset robustness instead of independent gain. |

### What happens if the gate fails

Pre-committed cascade (no post-hoc venue-shopping):

1. **Layer 1 fails (CRC bound violated on either benchmark)** → Failure clause F1 triggers. Verify Clopper-Pearson computation; if persistent, **drop the formal-guarantee thesis** → activate **Option F2** (empirical-only main-track, requires ≥ 5 pp B+C lift on LongMemEval-S to compensate).
2. **Layer 2 fails (no clear LongMemEval-S lift OR neither Path A nor Path B holds)** → Failure clauses F3/F9 trigger. Activate **Option F1** (workshop / findings track, smaller-scope claim: "first formal guarantee + parity") OR **Option F2** with the 5 pp bar.
3. **Both layers fail** → STOP. Project is not strong enough for current main-track venue. Pivot direction or escalate to user with explicit rationale logged in `AUTO_REVIEW.md`.

### Why this is policy-compliant

- LongMemEval-S provides a clear gain for both layers.
- Memora provides the second-benchmark validation for the **dominant formal claim** (CRC bound holds on both) AND substitutes "clear gain" for the supporting claim with **parity + cross-dataset Path B robustness** — a different but equally rigorous check that the method doesn't overfit to one corpus.
- This is documented here in advance per policy ("explicit waiver logged" — there is no waiver, the gate is satisfied by Layer-1 dual-benchmark validation).

---

## 主表 seed / N 矩阵 (per `TABLE_SEED_FAIRNESS` + `TABLE_DISPERSION`)

| Table | Block | N (runs per row) | Seed list | Dispersion reported |
|---|---|---:|---|---|
| **Main accuracy table** | B1 | **3** | {0, 1, 2} | mean ± std over the 3 seeds |
| **Per-α CRC reliability table** | B4 | 3 (seeds inherited from B1) | {0, 1, 2} | mean ± std of empirical risk per α |
| **Path A acceptance test** | B2 | 3 (paired with B1's seeds) | {0, 1, 2} | paired-bootstrap p-value over 1000 resamples |
| **Path B cross-dataset test** | B2 | 1 (deterministic given locked λ̂) | seed = 0 only | descriptive only (single point estimate) |
| **Ablation table** | B3 | **1** | seed = 0 only | flagged in caption: "single seed; no dispersion reported"; CalLB row inherits its seed-0 number from B1 main table for fair comparison |
| **Memora secondary table** | B5 | **1** | seed = 0 only | flagged single-seed; cluster-bootstrap CIs over (persona × duration) clusters substitute for seed variance |
| **LoCoMo parity table** | B6 | **1** | seed = 0 only | flagged single-seed |
| **Class-B rescue analysis** | B7 | 1 | inherited from B1 seed 0 | descriptive counts on 77 examples |

**Comparability rules** (compliance):
- All rows in any single table use identical N and seed list (TABLE_SEED_FAIRNESS).
- Mixed-N tables are forbidden; B3 / B5 / B6 single-seed tables are explicitly separate from B1 main 3-seed table.
- Mean tables always carry std or CI (TABLE_DISPERSION); single-seed tables explicitly flagged.

---

## Experiment Blocks

### Block B0 — Calibration & intrinsic acceptance gates (Week 1)

- **Claim tested**: CalLB's calibration prerequisites are met before any test-time runs. Sanity / build block; not a paper claim.
- **Why this block exists**: gates the entire downstream pipeline. If LLM-judge κ < 0.7 or MLP AUC < 0.75 or per-α dev coverage misses, no test runs are launched.
- **Dataset / split / task**: LongMemEval-S train (~500 q) + Memora train (~1.2K q) → stratified subsample 10K (q, item) pairs (40 % LME-S, 40 % Memora, 20 % held back as cal-of-cal).
- **Compared systems**: N/A (sanity block).
- **Metrics**:
  - LLM-judge auto-label vs author manual on 100 stratified-borderline items: Cohen's κ on full 3-class (target ≥ 0.7) AND D-vs-non-D binary (target ≥ 0.75). Plus 3×3 confusion matrix.
  - MLP dev AUC on `1[label = LB]` (target ≥ 0.75).
  - Per-α dev empirical risk `R̂_dev(λ̂_α)` for α ∈ {0.10, 0.20, 0.30, 0.40} (target ≤ α + 0.02).
- **Setup details**:
  - LLM-judge: `deepseek-v3.2` via MAAS, sequential, ~3 s/item, ~8.3 hr wall-clock for 10K items.
  - MLP: 13 features → 32 hidden → 1 logit; BCE loss; Adam lr=1e-3 wd=1e-4; 5 epochs; 80/20 query-split (no leakage).
  - CRC: Clopper-Pearson UCB on 100-pt λ-grid, n_cal = 600 cal-of-cal queries, δ/m = 0.0005.
- **Success criterion**: all 3 gates clear → lock `λ̂` table → commit hash → proceed to M1.
- **Failure interpretation**:
  - κ < 0.65 → fall back to binary `LB` vs `not-LB` label and re-derive (Failure clause F4).
  - κ in [0.65, 0.7] → 3-call self-consistency on judge → re-label disagreed → re-audit.
  - MLP AUC < 0.7 → increase hidden dim to 64; add interaction features; check label imbalance.
  - Per-α dev coverage misses → check Clopper-Pearson code; if persistent, larger n_cal or grid refinement.
- **Table / figure target**: Appendix table A1 (LLM-judge κ + confusion matrix); Appendix table A2 (MLP dev curve); Appendix figure A1 (dev per-α calibration plot).
- **Priority**: **MUST-RUN** (Week 1; gates everything else).

### Block B1 — Main anchor: B+C-prone slice lift on LongMemEval-S (Week 2)

- **Claim tested**: C2 (supporting empirical claim). CalLB causes ≥ 3 pp B+C-prone slice lift on LongMemEval-S vs Path D `ttmg` and 3 frontier-adjacent neighbors. Plus C1 layer-1 partial: empirical CRC bound holds on LME-S test.
- **Why this block exists**: the headline empirical result of the paper. Without this, no main-track submission.
- **Dataset / split / task**: LongMemEval-S full N=500 (test split = the entire dataset, since LME-S has no train/test split); evaluation = LLM-judge accuracy per question, stratified by `question_type`.
- **Compared systems** (all on Path D's TTMG substrate where applicable):
  - **CalLB** (ours, with full 13-feature MLP + Clopper-Pearson CRC at α* = 0.20 + tiered prompt).
  - **Path D `ttmg`** (existing reader on same substrate, no CalLB).
  - **MiCP-on-Path-D** (per-query conformal stopping ported to the candidate set; reuse arXiv 2604.01413 reference impl).
  - **Stop-RAG-on-Path-D** (RL stopping ported; arXiv 2510.14337).
  - **Flat hybrid-RAG** (sem + lex RRF, no claim-graph; minimal substrate baseline).
- **Metrics**:
  - **Headline**: B+C-prone slice union accuracy (single-session-user + KU + single-session-preference + multi-session).
  - **Per-slice**: accuracy per `question_type`, no-regression check (no slice drops > 1 pp vs Path D).
  - **Full-set accuracy**: macro-avg over all 6 question_types.
  - **Per-α empirical CRC risk** `R̂_test(λ̂_α)` for α ∈ {0.10, 0.20, 0.30, 0.40} (feeds B4 main table).
  - **Non-vacuity utility metrics**: `non_empty(L)`, `mean |L|`, `LB_recall(L)`, `LB_precision(L)`, mean distractor fraction at α* = 0.20.
- **Setup details**:
  - Reader: `deepseek-v3.2` via MAAS, sequential.
  - 3 seeds: {0, 1, 2}; seeds control Path D candidate retrieval ordering (no model-weight randomness in MAAS).
  - λ̂ table: locked from B0; commit hash printed.
  - Total: 5 methods × 3 seeds × 500 questions × ~30 s/question ≈ 12.5 hr sequential MAAS.
- **Success criterion**:
  - C2: B+C slice lift ≥ 3 pp vs Path D `ttmg` with cluster-bootstrap p < 0.05 over (question_type × persona) clusters; no slice regresses > 1 pp.
  - C1 partial: per-α empirical CRC `R̂_test(λ̂_α) ≤ α + 0.04` for ≥ 3 of 4 α.
  - Non-vacuity: `non_empty ≥ 0.85`, `mean |L| ∈ [2,5]`, `LB_recall ≥ 0.75`.
- **Failure interpretation**:
  - Slice lift < 1 pp on ≥ 2 slices → F3 trigger → pivot direction.
  - CRC bound violated on ≥ 2 α → F1 trigger → check CP computation; if persistent → F2 (empirical-only).
  - Non-vacuity fails (`non_empty < 0.70` OR `LB_recall < 0.50`) → F1' trigger → F2.
- **Table / figure target**: Main paper Table 1 (accuracy headline, mean ± std × 5 methods × 6 slices); Main paper Table 2 (per-α reliability with CP UCB error bars); Main paper Table 3 (non-vacuity utility metrics).
- **Priority**: **MUST-RUN** (the headline; no submission without this).

### Block B2 — Acceptance gate: Path A (downstream lift over `no_CRC`) and Path B (cross-dataset CRC transfer)

- **Claim tested**: Anti-claim refutation. The CRC machinery itself contributes beyond a fixed dev-tuned threshold, OR the calibrated threshold transfers across datasets where a fixed threshold doesn't.
- **Why this block exists**: pre-committed main-track go/no-go (per round-3 reviewer). If neither Path A nor Path B holds, project pivots to Option F1/F2.
- **Dataset / split / task**:
  - Path A: LongMemEval-S full N=500 (B1 results) + Memora full test (B5 results).
  - Path B: λ̂_α calibrated on LongMemEval-S train → applied directly to Memora test (no re-cal); and vice versa.
- **Compared systems**:
  - **CalLB** (Clopper-Pearson CRC threshold).
  - **`no_CRC`** = same MLP scores + dev-tuned **fixed threshold** (median of dev MLP scores OR threshold maximizing dev B+C-prone slice acc; pick the better-on-dev variant before locking).
- **Metrics**:
  - Path A: B+C-prone slice accuracy delta (CalLB − `no_CRC`); paired-bootstrap p-value over 1000 resamples (paired by question_id × seed).
  - Path B: empirical `R̂(λ̂_α)` on the held-out corpus for both CalLB and `no_CRC`.
- **Setup details**:
  - Path A: reuse B1 + B5 results; only need to add `no_CRC` rows (1 method × 3 seeds × LME-S + 1 seed × Memora ≈ 4 hr extra).
  - Path B: deterministic given locked λ̂; ~ 1 hr wall-clock for both directions.
- **Success criterion**:
  - **Path A passes**: CalLB beats `no_CRC` by ≥ 1 pp on B+C-prone slice with paired-bootstrap p < 0.05 on at least one of {LongMemEval-S, Memora}.
  - **Path B passes**: CalLB's CRC bound holds within α + 0.06 on the held-out corpus AND `no_CRC`'s fixed threshold violates by > 0.10.
  - **Acceptance**: Path A OR Path B → main-track contribution validated.
- **Failure interpretation**:
  - Neither Path A nor Path B passes → F9 trigger → Option F1 (workshop) or F2 (empirical-only with 5 pp bar; Memora may not qualify here, so it would default to LME-S only).
- **Table / figure target**: Main paper Table 4 (Path A: CalLB vs `no_CRC` accuracy + p-values, both benchmarks). Main paper Table 5 (Path B: cross-dataset CRC threshold transfer).
- **Priority**: **MUST-RUN** (gates the main-track decision).

### Block B3 — Attribution + mechanism + generality ablations (Week 2)

- **Claim tested**: Anti-claim refutation (the prompt isn't the work; the heuristic isn't the work) + mechanism causality (cross-substrate agreement OR robustness features carry the Class-B fix; drift features carry the KU fix) + portable generality bound.
- **Why this block exists**: defends the contribution against "you could have done X simpler" attacks; bounds the substrate-coupling honestly.
- **Dataset / split / task**: LongMemEval-S full N=500 (single seed = 0).
- **Compared systems** (8 ablations):
  - **Attribution (4)**:
    - `prompt-only` — Path D's existing top-k + same load-bearing prompt; no MLP/CRC.
    - `rerank-only` — CalLB MLP ranking; flat reader prompt (no tiering).
    - `agreement-heuristic-only` — no MLP; rank by `cross_substrate_agreement` count + sem-sim tiebreak; load-bearing prompt.
    - `no_CRC` — already in B2; row reused here for completeness.
  - **Mechanism (3)**:
    - `no_cross_substrate_agreement` — MLP without that feature.
    - `no_drift_features` — MLP without {time_volatility, supersede_edge_count, validity_interval_freshness, contradiction_count}.
    - `no_robustness_features` — MLP without {max_substrate_score, singleton_raw_turn_hit, entity_overlap}.
  - **Generality (1)**:
    - `portable_features_only` — MLP with only 5 portable + 3 robustness = 8 substrate-agnostic features.
- **Metrics**: B+C-prone slice accuracy (same metric as B1, fair comparison via shared seed-0 row from B1).
- **Setup details**: Each ablation requires re-training the MLP if features change (B3 mechanism + generality); attribution baselines (`prompt-only`, `rerank-only`, `agreement-heuristic-only`) reuse the same MLP or skip it entirely. Seed-0 only.
- **Success criterion**:
  - `prompt-only` captures < 50 % of CalLB's slice lift.
  - `rerank-only` < 70 %.
  - `agreement-heuristic-only` < 70 %.
  - At least one of {`no_cross_substrate_agreement`, `no_robustness_features`} drops Class-B-fix lift by ≥ 50 % (narrative adjusts via pre-registered Class-B-rescue analysis).
  - `no_drift_features` drops KU-slice lift by ≥ 30 %.
  - `portable_features_only` achieves ≥ 50 % of CalLB's slice lift.
- **Failure interpretation**:
  - `prompt-only` ≥ 70 % → F2 trigger → reframe paper as "prompt-engineering on TTMG substrate"; demote calibration from headline.
  - `agreement-heuristic-only` ≥ 70 % → drop MLP; deliver heuristic + CRC as simpler method (still valid contribution).
  - Portable subset < 30 % → admit honestly that the method is tightly TTMG-coupled; remove portable framing.
- **Table / figure target**: Main paper Table 6 (4 attribution rows + CalLB; 1 seed flagged). Appendix table A3 (3 mechanism + 1 generality ablations).
- **Priority**: **MUST-RUN** (defends contribution against the standard reviewer attacks).

### Block B4 — Per-α CRC reliability validation on both benchmarks (parallel with B1 + B5)

- **Claim tested**: C1 dominant claim — empirical clean-set CRC bound holds at 4 α on two independent public benchmarks.
- **Why this block exists**: the formal contribution. Validates the Clopper-Pearson UCB theorem empirically.
- **Dataset / split / task**: LongMemEval-S test (from B1) + Memora test (from B5).
- **Compared systems**: CalLB at 4 α values {0.10, 0.20, 0.30, 0.40}.
- **Metrics**: empirical `R̂_test(λ̂_α) = (1/n_test) Σ_q 𝟙[L_λ̂_α(q) contains label-D item]`; report against the Clopper-Pearson theoretical bound `α + slack`.
- **Setup details**: Computed at evaluation time during B1 and B5 (no extra runs); needs labelled D items in test candidate sets (use the LLM-judge labels generated during B0).
- **Success criterion**: `R̂_test(λ̂_α) ≤ α + 0.04` for ≥ 3 of 4 α on **each** benchmark independently.
- **Failure interpretation**: F1 trigger if violated; check Clopper-Pearson code; if persistent, F2 (empirical-only paper).
- **Table / figure target**: Main paper Figure 2 (per-α reliability plot with Clopper-Pearson UCB band, both benchmarks; 4 α points × 2 benchmarks = 8 markers).
- **Priority**: **MUST-RUN** (formal contribution validation).

### Block B5 — Memora-FAMA secondary parity (Week 2)

- **Claim tested**: C1 layer-1 (CRC bound holds on Memora) + C2 secondary parity (within 3 pp of best baseline on FAMA temporal-forgetting subset).
- **Why this block exists**: provides the second public benchmark for the dominant formal claim AND the parity check for the empirical claim. Enables Path B cross-dataset CRC transfer test.
- **Dataset / split / task**: Memora full test (per `competitors/memora-eval-main/`); evaluation = aggregate FAMA per duration + per-α empirical CRC risk.
- **Compared systems**:
  - **CalLB** (ours).
  - **A-Mem** (reimpl from `competitors/A-mem-main`; same reader).
  - **Mem0** (best-effort reproduce).
  - **LightMem** (best-effort reproduce).
  - **EverMemOS** (best-effort reproduce; appendix sub-row only if Memora-port runnable in budget).
- **Metrics**: aggregate FAMA per duration; cluster-bootstrap CIs over (persona × duration) clusters; per-α empirical CRC risk; non-vacuity utility metrics.
- **Setup details**: 5 methods × 1 seed × Memora full ≈ 2.5 hr MAAS. Single seed flagged in caption.
- **Success criterion**:
  - C1 partial: per-α `R̂_test(λ̂_α) ≤ α + 0.04` for ≥ 3 of 4 α (Layer-1 second benchmark).
  - C2 secondary: CalLB FAMA within 3 pp of best baseline on temporal-forgetting subset (parity); if dominates, bonus, not headline.
- **Failure interpretation**:
  - CRC violated → F1 trigger as in B4.
  - FAMA falls behind ≥ 2 of 4 baselines → parity claim becomes honest report; do not over-sell. Triggers reconsideration of Path A or Path B as the path-forward (since C2 layer-2 second benchmark is gone).
- **Table / figure target**: Main paper Table 7 (Memora-FAMA per duration × 5 methods, 1 seed flagged; cluster-bootstrap CIs). Feeds B4 + B2 Path B.
- **Priority**: **MUST-RUN** (second public benchmark for two-benchmark gate).

### Block B6 — LoCoMo parity (Week 2, light)

- **Claim tested**: C2 secondary — CalLB doesn't regress on LoCoMo (frontier saturated 92.3 %).
- **Why this block exists**: avoids reviewer concern that CalLB hurts on the most-saturated memory benchmark; positioning is "TTMG-coupled, but not regressing on the canonical benchmark either".
- **Dataset / split / task**: LoCoMo full (per `competitors/locomo-master/`).
- **Compared systems**: CalLB, Path D `ttmg`, SmartSearch (LoCoMo-only baseline).
- **Metrics**: LoCoMo accuracy (LLM-judge per the LoCoMo eval script).
- **Setup details**: 3 methods × 1 seed × LoCoMo full ≈ 1.5 hr.
- **Success criterion**: CalLB within 2 pp of best of (Path D, SmartSearch).
- **Failure interpretation**: regression > 2 pp → admit honestly; the TTMG substrate may be marginally hurting on LoCoMo's distribution; demote LoCoMo to footnote.
- **Table / figure target**: Appendix Table A4 (LoCoMo parity, 3 methods, 1 seed flagged).
- **Priority**: **NICE-TO-HAVE** (parity check; doesn't gate the paper).

### Block B7 — Pre-registered Class-B-rescue qualitative analysis + non-vacuity utility metrics (Week 3)

- **Claim tested**: Failure analysis / qualitative diagnosis. Determines whether the "agreement is the Class-B fix" narrative is supported or whether it shifts to "learned multi-substrate fusion is the Class-B fix" (per round-2 pre-registration).
- **Why this block exists**: prevents post-hoc narrative-shaping; shows reviewer the team has thought about *why* the method works.
- **Dataset / split / task**: 77 Class-B examples from `results/gating_decomposition.json` (a designated subset of LongMemEval-S, not a separate corpus).
- **Compared systems**: CalLB (with full feature set; reuse B1 seed-0 results).
- **Metrics**:
  - For each rescued question: bucket the rescuing item by `cross_substrate_agreement` count and `singleton_raw_turn_hit` flag.
  - Report fractions: high-agreement rescues (count ≥ 3); low-agreement (count ≤ 1) AND `singleton_raw_turn_hit = 1`; low-agreement no-singleton.
  - Plus non-vacuity utility metrics on L (already computed in B1 at α* = 0.20): `non_empty`, `mean |L|`, `LB_recall`, `LB_precision`, mean distractor fraction.
- **Setup details**: Post-hoc analysis of B1 seed-0 outputs; ~30 min author + spreadsheet.
- **Success criterion**: All four metrics computed and reported regardless of outcome.
- **Failure interpretation** (narrative-reframing trigger):
  - High-agreement rescues < 30 % of total → paper positioning shifts from "cross-substrate agreement is the Class-B fix" to "learned multi-substrate signal fusion is the Class-B fix".
  - Either way, the result is reported transparently.
- **Table / figure target**: Main paper Table 8 (utility metrics on L, headline α* = 0.20); Main paper Figure 3 (Class-B-rescue breakdown + 3 illustrative examples from the gating set).
- **Priority**: **MUST-RUN** (cheap; pre-registration honor).

---

## Run Order and Milestones

| Milestone | Goal | Runs (block IDs) | Decision Gate | Cost (wall-clock) | Risk |
|---|---|---|---|---:|---|
| **M0 — Sanity & calibration (Week 1)** | Build feature extractor + MLP + CRC; auto-label 10K cal pairs; manual audit; lock λ̂ table. | B0 | Intrinsic gates: κ ≥ 0.7 / 0.75; MLP AUC ≥ 0.75; per-α dev coverage ≤ α + 0.02. **If fail** → F4 (binary collapse) or extra dev iteration. | ~15 hr (8.3 hr MAAS labelling + 1 hr audit + ~5 hr dev iteration) | **HIGH**: LLM-judge label quality on borderline cases. Mitigate: 3-call self-consistency on `confidence=low` items; binary fallback if persistent. |
| **M1 — Main headline (Week 2 day 1-3)** | Run B1 (5 methods × 3 seeds × LongMemEval-S full N=500). | B1, B4 (LME-S half), B7 partial | C2 layer headline: ≥ 3 pp B+C slice lift; C1 LME-S half: per-α `R̂ ≤ α + 0.04`; non-vacuity met. **If fail** → F1, F1', or F3. | ~12.5 hr MAAS sequential | **MED**: MAAS rate-limit / outage. Mitigate: chunked runs + checkpoint resume. |
| **M2 — Ablations + secondary benchmarks (Week 2 day 3-5)** | Run B3 (8 ablations × 1 seed) + B5 (Memora 5 methods × 1 seed) + B6 (LoCoMo 3 methods × 1 seed) + B2 Path A `no_CRC` rows. | B3, B5, B6, B2 partial | Attribution gates: `prompt-only` < 50 %; ablations drop appropriately. C1 Memora half: per-α `R̂ ≤ α + 0.04`. **If fail** → F2 or narrative reframe. | ~10 hr MAAS | **MED**: Memora reimpl baselines (A-Mem / Mem0 / LightMem) may need adapter work. Mitigate: pre-build adapters in M0 spare time. |
| **M3 — Acceptance gate decision (Week 2 day 6)** | Compute Path A bootstrap; compute Path B cross-dataset transfer. | B2 (final), B7 (final) | **Acceptance gate**: Path A passes (CalLB > no_CRC by ≥ 1 pp w/ p<0.05) OR Path B passes (CRC threshold transfers, fixed threshold doesn't). **If neither passes** → activate Option F1 (workshop) or F2 (empirical-only with 5 pp bar). | ~2 hr (Path B reuse + bootstrap compute) | **HIGH**: this is the main-track go/no-go. Mitigate: pre-committed pivot logic; do not rationalize. |
| **M4 — Polish + paper (Week 3)** | Generate figures; write paper sections; iterate. | (none — analysis only) | Paper draft v1 ready for `/auto-review-loop`. | ~5 days author time | **LOW**: standard writing risk. |

**Decision-stage rule** (M3): the team commits to honoring the pre-registered Path A / Path B / F1 / F2 decision. Per round-4 reviewer's only operational caveat: "do not rationalize a failed acceptance gate into a main-track theory paper after the fact".

---

## Compute and Data Budget

- **Total estimated GPU-hour-equivalents**: ≈ **30 GPU-h** (all MAAS-only; no local GPU training beyond the MLP at < 5 min CPU). Breakdown:
  - M0 build: ~15 hr (mostly MAAS labelling).
  - M1 headline: ~12.5 hr MAAS (sequential, single in-flight per server-load policy).
  - M2 ablations + secondary: ~10 hr MAAS.
  - M3 acceptance: ~2 hr.
  - **Total wall-clock**: ~40 hr; with 1 day debug buffer = ~50 hr; fits Week-1 (build) + Week-2 (eval, 5 working days) comfortably.
- **Data preparation needs**:
  - 10K stratified-subsampled (q, item) pairs labelled by LLM-judge (built in M0).
  - 100 stratified-borderline manual-audit pairs (built in M0).
  - All test sets are public and already on disk: `LongMemEval-main/longmemeval_s.json`, `competitors/memora-eval-main/`, `competitors/locomo-master/`.
- **Human evaluation needs**: ~1 hr author manual audit on 100 items (M0). No user-study or external annotation.
- **Biggest bottleneck**: MAAS sequential throughput. Server-load policy mandates single in-flight call per host. If MAAS is severely degraded, Path A bootstrapping (1000 resamples) is the only loop that can be parallelized internally; everything else is MAAS-bottlenecked.

---

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| LLM-judge κ < 0.65 on 3-class | MED | HIGH (theory underwriting fails) | 3-call self-consistency on judge; fall back to binary `LB` vs `not-LB` (F4) — theory still holds with binary collapse. |
| `prompt-only` captures ≥ 70 % of slice lift | MED | HIGH (calibration not the contribution) | Pre-committed F2 reframe to "prompt-engineering paper"; CRC supporting; demote calibration from headline. |
| `no_CRC` (same MLP + dev-tuned threshold) ≈ CalLB on downstream | MED-HIGH | HIGH (formal claim becomes practically unnecessary) | Pre-committed Path B cross-dataset robustness test; if Path B also fails, activate F1 (workshop) or F2 (empirical-only with 5 pp bar). |
| Cross-substrate agreement collinear / fails on Class-B | MED | MED (narrative shift, not project-killer) | Pre-registered Class-B-rescue analysis on the 77 examples; narrative reframes per Rev-4 trigger. |
| Memora-FAMA falls behind 4 baselines | MED | MED (loses second-benchmark layer-2 gain) | Layer-1 (CRC bound on both benchmarks) still satisfies dual-benchmark gate for the dominant claim; Layer-2 falls back to Path A on LME-S only + cross-dataset Path B robustness as second-benchmark substitute. |
| MAAS rate-limit / outage during Week 2 | LOW-MED | MED (delays eval) | Chunked checkpoint-resume; backup judge models (`Kimi-K2`, `glm-5.1`) pre-tested on small batches in M0 spare time. |
| Server load (shared host) spikes during runs | MED | LOW (slows MAAS) | Default sequential MAAS per server-load policy; never parallelize MAAS; monitor `uptime` before launching M2. |
| EverMemOS Memora-port not buildable in budget | MED | LOW (loses 1 of 4 Memora baselines; appendix-only anyway) | EverMemOS is appendix-only; A-Mem + Mem0 + LightMem are sufficient for the headline parity check. |

---

## Final Checklist

- [x] Main paper tables are covered: Table 1 (B1 accuracy), Table 2 (B4 reliability), Table 3 (B7 utility), Table 4 (B2 Path A), Table 5 (B2 Path B), Table 6 (B3 attribution), Table 7 (B5 Memora), Figure 2 (B4 reliability plot), Figure 3 (B7 Class-B rescue).
- [x] **Baseline coverage** for main, mechanism, and efficiency blocks per policy 第 5 节: B1 (main, 4 named external baselines), B2 (mechanism, `no_CRC`), efficiency block N/A (same MAAS endpoint, sub-ms MLP overhead). Sanity (B0) and ablation-only (B3) blocks documented per waiver subsection.
- [x] **Two-benchmark gate** (政策 第 6 节, `TWO_BENCHMARK_CONTINUE_GATE`): LongMemEval-S + Memora; Layer-1 CRC bound validated on both; Layer-2 LME-S clear gain + Memora parity + Path B cross-dataset substitute. Failure cascade pre-committed (F1 / F2). No user waiver required.
- [x] **Main-eval public benchmarks** (政策 第 6 节, `MAIN_EVAL_PUBLIC_BENCHMARKS`): all main-paper headline tables use only LongMemEval-S, Memora, LoCoMo (all public). No private / self-built data underwrites a dominant claim. The 186-question gating decomposition is in supplementary as the methodology contribution.
- [x] **Seed / N matrix** (`TABLE_SEED_FAIRNESS` + `TABLE_DISPERSION`): main 3-seed table reports mean ± std; ablation / secondary 1-seed tables explicitly flagged in captions.
- [x] Novelty is isolated: B2 Path A (calibration vs fixed threshold) + B3 attribution (prompt vs rerank vs heuristic).
- [x] Simplicity is defended: B3's `prompt-only` and `agreement-heuristic-only` baselines test whether simpler alternatives match CalLB.
- [x] Frontier contribution is justified: the LLM-judge for calibration-set construction is the only foundation-model primitive central to the method, and the alternative (heuristic string-match labels) was reviewed and rejected — but the paper does NOT claim a "frontier-necessity" headline; the contribution is the statistical machinery, not the LLM judge.
- [x] Nice-to-have runs are separated from must-run runs: B6 LoCoMo and EverMemOS-Memora-port flagged NICE-TO-HAVE / appendix-only.
- [x] Acceptance logic for main-track is **pre-committed** in advance (Path A / Path B / Option F1 / F2); reviewer R4 caveat ("honor the pre-committed venue logic") is logged.
