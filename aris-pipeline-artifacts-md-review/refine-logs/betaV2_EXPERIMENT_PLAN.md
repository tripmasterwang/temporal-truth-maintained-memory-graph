# Experiment Plan — Pivot β v2 (Conformal-Selective-Risk-Controlled Memory)

**Problem.** When an LLM agent answers from accumulated long-conversation memory, two failures recur and no current method handles either with a guarantee: (1) silent reliance on obsolete memory; (2) over-confident answering on contradictions. EverMemOS (Jan 2026, 92.3 % LoCoMo) already does validity intervals; SmartSearch (Feb 2026, 91.9 %) does deterministic retrieval — the *system-level* race is over. The structural white-space (keyword-scan-confirmed across 141 .tex files of `MemMachine/competitor/`) is *statistical / information-theoretic*: zero memory papers use conformal / calibration / MI / PAC / sequential testing. The new Memora benchmark with the FAMA metric measures forgetting-aware accuracy, and **no memory system has published FAMA scores yet**.

**Method Thesis.** *For each retrieved memory subset relevant to a query, compute a hardness-weighted scalar confidence score `S(q)`; on a held-out dev split fix candidate-threshold sets per inference-time-defined group; on a calibration split, evaluate one pre-frozen threshold per (g, α) using Clopper-Pearson exact one-sided UCB with Bonferroni correction; at inference, answer iff `S(q) ≥ τ̂_g(α; δ)` and unique-value, else abstain — yielding **exact finite-sample** `Pr[ wrong | answered, g ] ≤ α` with probability ≥ 1 − δ.*

**Date.** 2026-04-26
**Source proposal.** `refine-logs/FINAL_PROPOSAL.md` (refine score 9.15 / 10, READY).

---

## Claim Map

| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|-------|----------------|-----------------------------|---------------|
| **C1 (Dominant) — Selective-risk guarantee on Memora.** Per-group + aggregate `r̂_g(τ̂_g(α; δ))` ≤ α + 0.02 for all 5 α ∈ {0.05, 0.10, 0.15, 0.20, 0.25} on Memora test, all g ∈ G_eff. Theorem-backed (Clopper-Pearson + Bonferroni). | First memory operator with an *exact, finite-sample, distribution-free* selective-risk guarantee. The keyword-scan-confirmed structural white-space the field has not entered. | Memora calibration → test pipeline; per-group reliability plot with Clopper-Pearson UCB band at 5 α; per-cell `(n_g, abstain_mass_g)` table. | B1, B2 |
| **C2 (Supporting) — Risk-coverage Pareto-dominance + AURC win on Memora's temporal-forgetting subset.** TTMG-β's risk-coverage curve dominates A-Mem, Mem0, LightMem, EverMemOS at every answer rate ∈ [0.4, 0.9] on `update_pattern ∈ {multi-update, supersede-heavy}` ∧ time-sensitive. AURC strictly lower (paired-bootstrap p<0.05). | Anchors the empirical centre of the paper to the *temporal-forgetting* failure mode (per round-1 reviewer mandate); preempts the trivial "abstain more to look safer" objection by reporting the full curve. | Memora test with all baselines; per-method risk-coverage curves on the temporal-forgetting subset; AURC + cluster-bootstrap CIs over (persona × duration). | B1, B2 |
| **C3 (Supporting) — Parity preservation on LongMemEval-S + selective-risk guarantee transfers.** TTMG-β within 2 pp of best of (Flat, A-Mem) on LongMemEval-S overall accuracy; per-group selective-risk guarantee also holds at all 5 α on LongMemEval-S calibrated on its own train split. | Satisfies the **two-public-benchmark continuation gate** (Memora + LongMemEval-S — both public, both standard splits, both showing the *guarantee* dominantly and parity-or-better on accuracy). Preempts the "your guarantee only holds on one benchmark" objection. | LongMemEval-S full N=500 with Flat + A-Mem + TTMG-β; selective-risk reliability plot replicated on LongMemEval-S. | B3 |
| **A1 (Anti-claim to rule out) — "The gain comes from substrate, not the conformal layer."** Removing the conformal layer (`no_conformal`, revert to Path D's MWIS abstention) breaks the selective-risk guarantee on Memora. | Rules out the reading "the contribution is the validity-intervals + linker substrate"; the substrate is reused but the guarantee is *not* there without the CRC layer. | Memora `no_conformal` ablation — show coverage no longer holds + AURC degrades. | B4 |
| **A2 (Anti-claim to rule out) — "The gain comes from abstaining more."** Risk-coverage curve as primary baseline comparison + matched-rate marker at α = 0.10. | Standard objection to any selective-classification paper; defused *by design* via the curve. | Risk-coverage curves with matched-rate markers per method (B1). | B1 |
| **A3 (Anti-claim to rule out) — "PMI is decoration; same result without it."** `no_pmi` ablation: drop PMI from S; collapse pmi_bin to 1; show selective-risk guarantee weaker on the high-PMI subset, AURC gap shrinks on the temporal-forgetting subset. | Defends the *frontier primitive* (PMI as frozen-LM gauge) against the trivial "you didn't need it" reviewer attack. | Memora `no_pmi` ablation; PMI phase diagram on dev. | B4, B5 |

> Two **public** benchmarks (Memora + LongMemEval-S) gate continuation per the **two-benchmark** rule below.

---

## Paper Storyline

- **Main paper must prove:**
  - **C1** (selective-risk guarantee on Memora; theorem + empirical reliability plot).
  - **C2** (risk-coverage Pareto-dominance + AURC win on Memora's temporal-forgetting subset).
  - **C3** (parity on LongMemEval-S + guarantee transfers).
  - **A1, A2, A3** (rule out the three obvious counter-narratives).
- **Appendix can support:**
  - LoCoMo runs (parity diagnostic — TTMG-β substrate is known to lose on LoCoMo per current pilot; reported with applicability-rate analysis).
  - Secondary backbone (Qwen3-30B-A3B-Instruct-2507) on {Flat, TTMG-β} — robustness check.
  - EverMemOS reproduction from `MemMachine/competitor/2601.02163_EverMemOS/code/` on Memora.
  - `no_canonical_key` and `no_3call_agreement` ablations (substrate-level — these are *Path D substrate* checks, not β-contribution checks).
  - KS drift diagnostic on `(pmi_bin, update_pattern)` calibration vs test distributions.
- **Experiments intentionally cut:**
  - Multi-hop benchmarks (HotpotQA / WikiMultiHop) — out of paper scope; SmartSearch is the natural baseline for that, not TTMG-β.
  - DialSim — A-Mem-specific, not in the survey corpus.
  - Token-efficiency / latency cost-curve — explicit non-claim per FINAL_PROPOSAL non-goals.
  - Path D's `no_validity`, `no_supersede`, `no_abstain` ablations — these tested *substrate* claims that β does not own; substrate is reused without re-justifying.
  - Token cost / latency comparisons against SmartSearch / EverMemOS — substrate matters but β does not claim to win on this axis; cost numbers reported in supplementary as transparency, not as a claim.

---

## Baseline 对照与豁免

> Per `docs/ARIS_RESEARCH_QUALITY_POLICY.md` 第 5 节 — every block whose results support a paper-level superiority / mechanism / efficiency claim names ≥1 non-trivial baseline; pure self-ablation is allowed only for narrow component-necessity claims when the broader Ours-vs-baseline comparison appears elsewhere.

**Named strong baselines (frozen in this plan):**
- **Flat hybrid-RAG** — the standing internal baseline; cheap, strong on LongMemEval-S in TTMG's existing pilot (70 % overall at N=500).
- **A-Mem (NeurIPS 2025, arXiv 2502.12110)** — the structured-memory baseline TTMG was designed against; reimplemented in this project's `ttmg/amem_base/`.
- **Mem0 (arXiv 2504.19413, 2025)** — production memory baseline with optional graph variant; reproduce from upstream code where feasible.
- **LightMem (ICLR 2026, arXiv 2510.18866)** — efficiency-frontier memory; reproduce from upstream code.
- **EverMemOS (arXiv 2601.02163, Jan 2026)** — the LoCoMo SOTA structured-memory system that already does validity intervals; best-effort reproduction from `MemMachine/competitor/2601.02163_EverMemOS/code/`. **Appendix only**, with paired comparison on Memora (where neither side has published numbers).
- *Not used as baselines:* SmartSearch (deterministic-retrieval; off-axis to a guarantee paper), SimpleMem (use the published LongMemEval-S 76.87 % only as a citation in related work).

**Block ↔ baseline anchoring (Ours vs … per policy 第 5 节):**
- **B1 (Memora main):** Ours (TTMG-β) vs **Flat, A-Mem, Mem0, LightMem** (5-way). EverMemOS in B1-appendix as a 6th comparator on Memora only. *Main superiority/dominance claim.*
- **B2 (Novelty isolation, Memora ablations):** Ours vs **Ours-no_conformal, Ours-no_groups** (component-necessity, narrow scope). Anchored to B1 for Ours-vs-baseline.
- **B3 (LongMemEval-S parity):** Ours vs **Flat, A-Mem** (3-way; smaller because parity is the claim). *Parity / non-regression claim.*
- **B4 (Frontier necessity, PMI):** Ours vs **Ours-no_pmi** + Ours vs **a "PMI-free confidence" simpler alternative** (e.g. just `S = w_h · hardness + w_u · 1[|Vals|==1]` with thresholds tuned by the same CRC procedure). Anchored to B1 for Ours-vs-baseline.
- **B5 (Diagnostics):** sanity / debug only — per-cell `(n_g, abstain_mass_g)` table, KS drift descriptive, `update_pattern` proxy ρ on dev, EverMemOS reproduction sanity. **No paper-level superiority claim drawn from B5 in isolation.**

**Sanity / debug-only blocks (no superiority claim):** the Wk-1 smoke test (M0-1 below), per-cell counts table (B5-a), KS drift diagnostic (B5-b), `update_pattern` proxy validation on dev (B5-c).

**Rationale for ablation-only blocks:** B2 and B4 contain ablations; the *Ours-vs-baseline* comparison they implicitly rely on lives in B1 (Memora) and B3 (LongMemEval-S). The ablations only support narrow component-necessity claims (A1, A3), not standalone superiority. **No waiver requested.**

---

## 双榜门闸

> Per `docs/ARIS_RESEARCH_QUALITY_POLICY.md` 第 6 节 — clear, consistent gains on ≥2 independent public benchmarks before scaling or paper-readiness.

**Two public benchmarks gating continuation:**

| # | Benchmark | Citation / link | Split | Decisive metric | Pass criterion (TTMG-β specific) |
|---|-----------|-----------------|-------|-----------------|----------------------------------|
| 1 | **Memora** | arXiv 2604.20006 (2026); HuggingFace dataset card released by paper authors | 60 % train (40 % calibration / 60 % dev) + held-out test (one-shot) | **(a) selective-risk** `r̂_g(τ̂_g(α; δ)) ≤ α + 0.02` for all 5 α, all g ∈ G_eff, on test; **(b) AURC** strictly lower vs ≥ 3 of 4 baselines on the temporal-forgetting subset (paired-bootstrap p<0.05); **(c) FAMA aggregate** non-regression (within 5 FAMA-pts of best baseline at matched answer rate) | Both (a) AND (b) AND (c). |
| 2 | **LongMemEval-S** | arXiv 2410.10813 (Wu et al. 2024); standard N = 500 split | own 60 / 40 calibration split + held-out test | **(a) selective-risk** guarantee transfers (per-group risk ≤ α + 0.02 for all 5 α on its test) AND **(b) overall accuracy** within 2 pp of best of (Flat, A-Mem) | Both (a) AND (b). |

**Pass / fail / failure-mode actions:**
- *Pass on both* → continue to paper writing + appendix runs (LoCoMo, secondary backbone, EverMemOS reproduction).
- *Pass on Memora only* → narrow C3 to "selective-risk guarantee verified on Memora; LongMemEval-S accuracy parity is a non-result and we report it as such"; downgrade venue target from NeurIPS / ICML main to ICLR or the ICLR 2026 MemAgents Workshop; **no waiver needed** because the dominant claim still holds.
- *Pass on LongMemEval-S only* → STOP. The paper is no longer about Memora-FAMA leadership; refine method or pivot.
- *Fail on both* → STOP. Refine method or escalate to user; explicit waiver logged in `EXPERIMENT_PLAN.md` + `AUTO_REVIEW.md` if user wants to proceed anyway.

**Rationale:** Memora is the natural validation for the dominant claim (FAMA forgetting metric directly tracks the failure mode β was designed for). LongMemEval-S is the second public benchmark and the project's existing N=500 test infrastructure makes it cheap to run; it is also the dataset where Path D's pilot regression occurred, so demonstrating *guarantee transfer* is meaningful even at parity accuracy.

---

## 主表 seed / N 矩阵

> Per `TABLE_SEED_FAIRNESS` — every row in a given table uses the same N and seed protocol; if N must differ, separate tables.

| Table (paper destination) | Rows | N (seeds) | Seed list | Notes |
|---------------------------|------|----------:|-----------|-------|
| **Table 1 (main): Memora full test, 5 methods × selective risk + FAMA** | Flat, A-Mem, Mem0, LightMem, TTMG-β | **3** | {0, 7, 17} | All 5 methods on identical 3 seeds; mean ± std reported (`TABLE_DISPERSION`). |
| **Table 2 (main): Memora temporal-forgetting subset, 5 methods × AURC + matched-rate FAMA** | Flat, A-Mem, Mem0, LightMem, TTMG-β | **3** | {0, 7, 17} | Same 3 seeds. Cluster-bootstrap CIs over (persona × duration). |
| **Table 3 (main): Ablations on Memora** | TTMG-β full, no_conformal, no_groups | **3** | {0, 7, 17} | Same seeds. |
| **Table 4 (main): LongMemEval-S parity** | Flat, A-Mem, TTMG-β | **3** | {0, 7, 17} | Same seeds. |
| **Appendix Table A1: EverMemOS reproduction on Memora** | EverMemOS, TTMG-β | **1** | {0} | Single seed for EverMemOS due to upstream-code reproduction risk; TTMG-β included at seed=0 for direct comparability. **Separate table** because N differs. |
| **Appendix Table A2: secondary backbone (Qwen3-30B-A3B)** | Flat, TTMG-β | **1** | {0} | Single seed; robustness check only. **Separate table** because N differs. |
| **Appendix Table A3: substrate ablations** | TTMG-β, no_canonical_key, no_3call_agreement, no_pmi | **3** | {0, 7, 17} | Same seeds; PMI moved here per round-1 reviewer (PMI is supporting, not headline). |
| **Appendix Table A4: LoCoMo applicability-rate diagnostic** | Flat, A-Mem, TTMG-β | **1** | {0} | Single seed; appendix-only; reports applicability rate per slice + composed end-to-end accuracy. |

**Notation in captions / footnotes:** *"Mean ± std over N seeds; CI = bootstrap 95 % over (persona × duration) clusters where applicable."*

---

## Experiment Blocks

### Block 1 — Memora main: selective-risk guarantee + temporal-forgetting Pareto-dominance (B1)
- **Claims tested.** C1, C2; rules out A2 by design.
- **Why this block exists.** The dominant + first supporting claims of the paper. Without B1, neither C1 nor C2 has evidence.
- **Dataset / split / task.** Memora (arXiv 2604.20006). 60 % train (split into 60 % dev / 40 % calibration), held-out test (one-shot, no tuning). 10 personas × 3 memory types × 3 tasks (remembering / reasoning / recommending) × multiple temporal durations (week / month / quarter / year). Temporal-forgetting subset = `update_pattern ∈ {multi-update, supersede-heavy}` ∧ time-sensitive slot type, computed via the inference-time graph proxy.
- **Compared systems.** Flat hybrid-RAG, A-Mem (reimpl), Mem0 (reproduced), LightMem (reproduced), **TTMG-β** (full). Five rows in Table 1 / Table 2.
- **Metrics.**
  - *Decisive:* per-group + aggregate empirical selective risk `r̂_g(τ̂_g(α; δ))` at 5 α; risk-coverage curve (answer rate vs selective risk); AURC; matched-rate FAMA on temporal-forgetting subset.
  - *Secondary:* per-cell `(n_g, abstain_mass_g)` table; aggregate FAMA non-regression; tokens/q + latency (transparency only).
- **Setup details.**
  - Backbone: deepseek-v3.2 reader (consistent with Path D pilot); writer + linker + parser also via MAAS (Kimi-K2 / GLM-5.1 as in Path D `system.py`).
  - Frozen substrate: Path D schema + canonicalizer + 3-call linker + applicability gate + canonical-key fetch (rounds 0-4). New: `ttmg/crc.py`, `ttmg/pmi.py`, `scripts/calibrate_crc.py`.
  - Hyperparameters dev-tuned + locked: `(w_h, w_u, w_p) ≈ (0.5, 0.3, 0.2)`, `PMI_scale`, pmi_bin boundaries (3-quantile of S on dev), update_pattern bin boundaries, `T_cand(g) = 5 quantiles per cell`, `N_min = 30`, `δ = 0.10` (95 % per-(g, α, τ) confidence), Bonferroni `δ_corr = δ / (|G_eff|·|A|·|T_cand|)`.
  - Seeds: {0, 7, 17}; identical for all rows in Tables 1-3.
  - Reader temperature 0; abstain-on-non-applicable → Flat fallback unchanged.
- **Success criterion.**
  - C1: per-group + aggregate `r̂_g(τ̂_g(α; δ))` ≤ α + 0.02 for all 5 α and all g ∈ G_eff, on test.
  - C2 (a): AURC strictly lower for TTMG-β vs ≥ 3 of 4 baselines on temporal-forgetting subset (paired-bootstrap p<0.05).
  - C2 (b): risk-coverage curve TTMG-β Pareto-dominates baselines at every answer rate ∈ [0.4, 0.9] on temporal-forgetting subset (or AURC fallback satisfied).
  - C3 (c): aggregate FAMA non-regression (within 5 FAMA-pts of best baseline at matched answer rate).
- **Failure interpretation.**
  - C1 fails → guarantee miscoverage on test → either (a) calibration / test exchangeability violated (check KS drift descriptor), or (b) `T_cand(g)` too coarse (re-define on dev *before lock* if discovered pre-test); paper falls back to *aggregate-only* guarantee.
  - C2 fails → β beats nothing on the headline subset → STOP per failure clause; refine method.
  - C3 (c) fails → β regresses on aggregate → reframe as "specialist on temporal-forgetting subset" (workshop track).
- **Table / figure target.**
  - Table 1 (main): per-group selective risk at 5 α with Clopper-Pearson UCB band; Per-method aggregate FAMA at α = 0.10.
  - Table 2 (main): per-method AURC on temporal-forgetting subset + matched-rate FAMA.
  - Figure 1 (main): per-group reliability plot (nominal α vs empirical risk per g, with UCB band, identity line).
  - Figure 2 (main): risk-coverage curves (one curve per method), temporal-forgetting subset.
  - Table A0 (main supplementary): per-cell `(n_g, abstain_mass_g)` with G_eff merging trace.
- **Priority.** **MUST-RUN.**

### Block 2 — Novelty isolation: `no_conformal`, `no_groups` ablations on Memora (B2)
- **Claim tested.** A1 (rules out "the gain comes from substrate") + necessity of Mondrian groups.
- **Why this block exists.** Without `no_conformal`, a reviewer can read β as "validity intervals + linker" (Path D substrate) with cosmetic abstention. Without `no_groups`, conditional coverage cannot be distinguished from marginal coverage.
- **Dataset / split / task.** Same as B1 (Memora full test).
- **Compared systems.** TTMG-β full, **TTMG-β-no_conformal** (revert read-time abstention to Path D's all-optima MWIS rule, no CRC layer, no thresholds), **TTMG-β-no_groups** (CRC layer present but marginal-only — single threshold per α across all queries).
- **Metrics.** Per-group + aggregate selective risk at 5 α (Table 3); FAMA on temporal-forgetting subset (Table 3 supplementary).
- **Setup details.** Identical to B1 except for the variant. Same seeds, same backbone, same calibration protocol where applicable (no_groups still calibrates marginally; no_conformal skips calibration entirely).
- **Success criterion.**
  - `no_conformal`: empirical selective risk on test exceeds α + 0.04 for ≥ 2 of 5 α (i.e. *no guarantee*).
  - `no_groups`: marginal coverage holds but per-group violations on ≥ 2 of |G_eff| cells at α = 0.10.
- **Failure interpretation.**
  - `no_conformal` doesn't break coverage → either β substrate is over-engineered or Memora's failure mode is too easy; reframe.
  - `no_groups` preserves per-group coverage too → Mondrian is decoration; collapse to marginal-only and trim the paper's per-group story.
- **Table / figure target.** Table 3 (main).
- **Priority.** **MUST-RUN.**

### Block 3 — LongMemEval-S parity + selective-risk guarantee transfer (B3)
- **Claim tested.** C3 (parity + guarantee transfers); satisfies the **two-public-benchmark gate**.
- **Why this block exists.** Per the two-benchmark continuation rule, the dominant claim must hold on ≥ 2 independent public benchmarks. LongMemEval-S is the natural second benchmark — it shares the *truth-maintenance / forgetting* failure mode in its KU + TR + abstention slices.
- **Dataset / split / task.** LongMemEval-S full N = 500 (Wu et al. 2024, arXiv 2410.10813). Standard split. Project already has the N=500 infrastructure from Path D (`results/full500_*.json`).
- **Compared systems.** Flat hybrid-RAG, A-Mem, **TTMG-β** (full).
- **Metrics.**
  - *Decisive:* overall accuracy (parity check); per-group selective risk at 5 α calibrated on LongMemEval-S's own 60 / 40 dev / calibration split.
  - *Secondary:* KU + TR + abstention slice accuracy.
- **Setup details.** Same backbone + seeds as B1. Calibrate CRC layer on LongMemEval-S's own train (split 60 dev / 40 cal); test held out. *Re-fix `T_cand` and bin boundaries on LongMemEval-S dev — do not reuse Memora's locked thresholds*; CRC is a benchmark-distribution-specific calibration.
- **Success criterion.**
  - C3 (a): per-group + aggregate selective risk ≤ α + 0.02 for all 5 α on LongMemEval-S test.
  - C3 (b): TTMG-β within 2 pp of best of (Flat, A-Mem) on overall accuracy.
- **Failure interpretation.**
  - (a) fails → guarantee doesn't transfer → β's CRC layer is benchmark-overfit; reframe to "Memora-only specialist".
  - (b) fails (gap > 2 pp) → substrate has a regression on LongMemEval-S; weaken parity claim and report honestly.
- **Table / figure target.** Table 4 (main); Figure A1 (appendix) — reliability plot replicated on LongMemEval-S.
- **Priority.** **MUST-RUN** (gates the two-benchmark continuation rule).

### Block 4 — Frontier necessity: `no_pmi` ablation + PMI-free simpler alternative (B4)
- **Claim tested.** A3 (rules out "PMI is decoration") + necessity of the frontier primitive (PMI as frozen-LM gauge).
- **Why this block exists.** PMI is the single FM-era primitive added to the score function; it must demonstrably earn its keep, otherwise the paper should drop it.
- **Dataset / split / task.** Memora full test (subset of B1's runs) + dev-side PMI Spearman.
- **Compared systems.** TTMG-β full, **TTMG-β-no_pmi** (drop PMI from S; collapse pmi_bin to single bin → Mondrian becomes 1 × 3 = 3 cells). Plus a "**PMI-free confidence**" simpler alternative: the same CRC procedure but `S(q) = w_h · mean(hardness in ⋃Opts) + w_u · 1[|Vals|==1]` only (no clip / PMI), with `T_cand` re-fitted on dev for fairness.
- **Metrics.**
  - PMI-bin AURC gap on temporal-forgetting subset (does the gap concentrate in the high-PMI bin as predicted by Claim 2 phase diagram?);
  - PMI Spearman ρ on dev (intrinsic gate ρ ≥ 0.5);
  - matched-rate FAMA on temporal-forgetting subset.
- **Setup details.** Same backbone + seeds as B1. The PMI-free alternative re-runs CRC calibration with the simpler `S`.
- **Success criterion.**
  - `no_pmi` causes coverage looseness on the high-PMI subset (per-group selective risk at α = 0.10 exceeds α + 0.04 on the high-PMI cell), AND AURC gap on temporal-forgetting subset shrinks by ≥ 1 AURC-point vs full TTMG-β.
  - PMI-free alternative loses on AURC by ≥ 1 AURC-point vs full TTMG-β.
- **Failure interpretation.**
  - PMI-removed-and-no-effect → drop PMI from main paper, move to "future-work conditional refinements" appendix.
  - PMI-free-alternative-matches → simplify the paper to the PMI-free version; the contribution is still CRC-on-typed-conflict-graph.
- **Table / figure target.** Table A3 (appendix) per the seed/N matrix; Figure 3 (main) — PMI phase diagram (PMI bin × AURC gap on temporal-forgetting subset).
- **Priority.** **MUST-RUN** if PMI is in the headline; **NICE-TO-HAVE** if Wk-1 dev gates indicate PMI ρ < 0.5 (in which case PMI is dropped and B4 becomes a negative-result appendix).

### Block 5 — Diagnostics: per-cell counts, KS drift, `update_pattern` proxy validation, EverMemOS reproduction (B5)
- **Claim tested.** Transparency on the calibration / coverage assumptions; sanity of inference-time `update_pattern` proxy; comparability of EverMemOS results.
- **Why this block exists.** Pre-empts reviewer questions about whether the 9 cells are populated, whether the calibration / test distributions are exchangeable, whether `update_pattern` is a meaningful proxy, and whether EverMemOS (the Jan-2026 SOTA) was reproduced fairly.
- **Dataset / split / task.** Memora dev (`update_pattern` proxy ρ vs Memora ground truth update count); Memora calibration vs test (KS on `(pmi_bin, update_pattern)`); EverMemOS on Memora (single seed, appendix).
- **Compared systems.** B5-a (per-cell): TTMG-β only. B5-b (KS drift): TTMG-β only. B5-c (`update_pattern` proxy): TTMG-β only. B5-d (EverMemOS reproduction): EverMemOS vs TTMG-β at seed=0 on Memora.
- **Metrics.** Per-cell (n_g, abstain_mass_g, n_test); KS statistic + p-value; Spearman ρ; EverMemOS published-vs-reproduced LoCoMo number (if reproducing on LoCoMo too as a sanity check).
- **Setup details.** B5-a / B5-b / B5-c run on the same data as B1 (no extra runs). B5-d requires running EverMemOS from `MemMachine/competitor/2601.02163_EverMemOS/code/`; budget 1 GPU-day Wk-2 for install + LoCoMo sanity reproduction + Memora run.
- **Success criterion.** B5-a all cells ≥ N_min after merging; B5-b KS p reported descriptively (no decision gate); B5-c ρ ≥ 0.6 (pre-test gate per FINAL_PROPOSAL §pre-test); B5-d EverMemOS reproduces published LoCoMo within 5 pp.
- **Failure interpretation.** B5-c ρ < 0.4 → drop `update_pattern` axis (marginal-only Mondrian); B5-d EverMemOS doesn't reproduce → cite published numbers, do not run direct comparison.
- **Table / figure target.** Table A0 (per-cell); §Discussion paragraph (KS + ρ); Table A1 (EverMemOS reproduction).
- **Priority.** **MUST-RUN** for B5-a / B5-b / B5-c (cheap, run alongside B1); **NICE-TO-HAVE** for B5-d (only if Wk-2 budget allows).

---

## Run Order and Milestones

| Milestone | Goal | Runs | Decision Gate | Cost | Risk |
|-----------|------|------|---------------|------|------|
| **M0 — Sanity (Wk 1, days 1-3)** | Pull Memora; integrate `crc.py`, `pmi.py`, `calibrate_crc.py`; smoke-test pipeline on 50 q × 1 method × 1 seed; verify output schema. | M0-1 (smoke). | Pipeline runs end-to-end; Memora data loads correctly; `crc.py` returns sane thresholds on a 50-q toy calibration. | ~1 GPU-h-eq | Memora API / data format surprises. **Mitigation:** keep the data-pull script idempotent + checkpointed. |
| **M1 — Dev tuning + intrinsic gates + lock (Wk 1, days 4-7)** | Tune `(w_h, w_u, w_p, PMI_scale)` on dev; fix pmi_bin + update_pattern bin boundaries; validate `update_pattern` proxy ρ ≥ 0.6; PMI Spearman ρ ≥ 0.5; per-group dev coverage ≤ α + 0.02 for all 5 α; lock `T_cand(g)`; tune baseline confidence thresholds for matched-abstention reporting; lock `threshold_table` + commit hash. | M1-1 (dev), M1-2 (per-group dev coverage), M1-3 (proxy validation). | **Lock-stop gate**: if any of (`update_pattern` ρ < 0.4) OR (PMI ρ < 0.3) OR (per-group dev coverage > α + 0.04 at any α) → iterate dev-side parameters; do *not* proceed to test until gates clear. | ~3 GPU-h-eq | `update_pattern` proxy weak (Memora's labelling differs from our graph features); PMI signal weak on memory-slot context. **Mitigation:** B4 has explicit fallback paths; reframe is documented in failure modes C2 / C8. |
| **M2 — Baseline reproduction (Wk 2)** | Reproduce A-Mem on Memora (existing `ttmg/amem_base/` reused); install Mem0 + LightMem from upstream code; reproduce on Memora at seed=0 to confirm install. EverMemOS install + LoCoMo sanity reproduction. | M2-1 (A-Mem), M2-2 (Mem0), M2-3 (LightMem), M2-4 (EverMemOS install + LoCoMo sanity). | Mem0 / LightMem run on Memora at seed=0 with sensible numbers (not crashing, FAMA in published-similar range); EverMemOS reproduces LoCoMo within 5 pp. | ~6 GPU-h-eq | Upstream code may not run cleanly on our MAAS API; EverMemOS may not reproduce. **Mitigation:** if a baseline doesn't install in 1 day, drop it and note in §limitations; EverMemOS appendix-only with explicit caveat. |
| **M3 — Main runs (Wk 2-3)** | Memora full test × 5 methods × 3 seeds (Tables 1, 2). LongMemEval-S parity × 3 methods × 3 seeds (Table 4). Compute risk-coverage curves + AURC + matched-rate markers + per-cell counts + KS drift descriptor. | M3-1 (Memora 5×3), M3-2 (LongMemEval-S 3×3), M3-3 (curves + AURC + per-cell). | **Two-benchmark gate**: both Memora (Table 1 coverage + Table 2 AURC dominance + Table 1 FAMA non-regression) AND LongMemEval-S (Table 4 parity + LongMemEval-S coverage). If both pass → proceed to M4. If only Memora passes → narrow C3 to "Memora-only specialist", proceed but downgrade venue. If only LongMemEval-S passes → STOP. If neither → STOP / refine / waiver. | ~18 GPU-h-eq | Calibration / test exchangeability fails on Memora (KS p < 0.05); β regresses on LongMemEval-S accuracy by > 5 pp. **Mitigation:** weighted conformal as future work (mentioned only); honest reporting per failure clause. |
| **M4 — Decision-stage ablations (Wk 3)** | `no_conformal`, `no_groups` on Memora (Table 3 main). `no_pmi`, `no_canonical_key`, `no_3call_agreement`, PMI-free alternative on Memora (Table A3 appendix). PMI phase diagram (Figure 3 main) on Memora dev. | M4-1, M4-2, M4-3 (Memora ablations × 3 seeds), M4-4 (PMI phase diagram), M4-5 (PMI-free alternative — appendix). | **A1 must hold**: `no_conformal` breaks coverage. **A3 must hold**: `no_pmi` causes coverage looseness on high-PMI cell OR PMI-free loses on AURC. If A1 fails → reframe (substrate = main contribution); if A3 fails → drop PMI from main, move to appendix. | ~6 GPU-h-eq | `no_conformal` doesn't break coverage on this dataset → β substrate is over-engineered; honest reframe. | 
| **M5 — Polish + appendix (Wk 4)** | Secondary backbone (Qwen3-30B-A3B) at seed=0 for {Flat, TTMG-β} on Memora + LongMemEval-S (Table A2 appendix). LoCoMo full at seed=0 for {Flat, A-Mem, TTMG-β} (Table A4 appendix). EverMemOS on Memora at seed=0 (Table A1 appendix). Cluster-bootstrap CIs over (persona × duration). KS drift descriptor table. Paper rewrite. | M5-1 (secondary backbone), M5-2 (LoCoMo appendix), M5-3 (EverMemOS Memora), M5-4 (cluster-bootstrap CIs), M5-5 (paper). | None — purely additive. | ~7 GPU-h-eq + writing | Time pressure on paper writing. **Mitigation:** start paper outline at end of Wk 2; figures finalised by mid-Wk 4. |

**Total compute estimate.** ≈ **41 GPU-h-equivalents** on 1–2× RTX-4090 (slightly over the 35 estimated in FINAL_PROPOSAL because M2 baseline-reproduction costs were under-counted in the proposal). All inference via MAAS API; no local training.

**Total elapsed time.** 4 weeks (consistent with FINAL_PROPOSAL's Wk 1-4).

**Sequential dependencies.** M0 → M1 (must lock thresholds before M3); M2 in parallel with M1; M3 needs M1 (locked thresholds) + M2 (baselines installed); M4 needs M3 (main results computed); M5 in parallel with paper rewrite.

---

## Compute and Data Budget

- **Total estimated GPU-h-equivalents.** ~41 (was 35 in FINAL_PROPOSAL; +6 for under-counted baseline-reproduction in M2).
- **Data preparation needs.**
  - Memora train + test from upstream (HuggingFace dataset card released by paper authors); ~1 hour to pull + verify.
  - LongMemEval-S N=500 already in the project (`results/full500_*.json` infrastructure from Path D).
  - LoCoMo already in the project (Path D appendix runs; reused for M5-2).
  - No new annotation. Per-cell `(n_g, abstain_mass_g)` table generated programmatically in M3-3.
- **Human evaluation needs.** None for the main pipeline. The FAMA metric is automated by the Memora benchmark's own LLM-as-judge protocol. *Optional:* if a reviewer requests human-eval to validate FAMA-LLM-judge on the temporal-forgetting subset, allocate 2 author-hours to label 60 randomly-sampled answers and report agreement (per the SeCom human-eval methodology in `MemMachine/competitor/2502.05589_SeCom/`).
- **Biggest bottleneck.** M2-4 (EverMemOS reproduction) — upstream code may need 1+ days of engineering to install on the project's MAAS API; if it stalls, EverMemOS is appendix-cite-only. Second bottleneck: M3-1 (Memora 5 × 3 = 15 main runs, each ~30-60 min depending on Memora test size).

---

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Memora calibration / test distribution shift fails KS-test (descriptive) | Medium | Medium — dilutes the guarantee transfer claim | Report KS as descriptive only (per round-3 reviewer); weighted conformal as future work; if shift is severe, narrow C3 to aggregate-only guarantee. |
| `update_pattern` proxy fails ρ ≥ 0.6 on dev | Medium | High — core inference-time grouping breaks | Re-tune bin boundaries on dev (allowed before lock); if still failing (ρ < 0.4), drop axis → marginal-only Mondrian; reframe C1 as marginal coverage only. |
| PMI Spearman ρ < 0.5 on dev | Medium | Medium — frontier necessity (A3) becomes harder | Drop PMI from S; collapse pmi_bin; PMI phase diagram becomes a *negative result* in appendix; main contribution is unchanged (CRC-on-typed-conflict-graph). |
| EverMemOS upstream code does not reproduce LoCoMo within 5 pp | Medium | Low — appendix-only impact | Cite published LoCoMo numbers; pair-compare on Memora only (where neither side has published numbers); explicit reproduction-caveat in §limitations. |
| Mem0 / LightMem upstream code doesn't install on MAAS | Low-medium | Medium — drops baseline coverage | If a baseline can't install in 1 day → use its published Memora-comparable numbers; declare in §limitations. *Floor:* keep at minimum Flat + A-Mem as baselines (both already in the project). |
| LongMemEval-S parity breaks (β regresses by > 5 pp) | Low (Path D substrate is identical, so LongMemEval-S behaviour is known from prior pilot) | High — fails two-benchmark gate | If failing: reframe to "Memora-only specialist", downgrade venue to ICLR / MemAgents Workshop. |
| `no_conformal` doesn't break coverage on Memora | Low (theoretically improbable: without calibration there's no guarantee) | High — A1 fails | Reframe: substrate is the contribution, conformal is an over-engineered wrapper. Workshop-track paper. |
| Calibration sample fragmentation: per-cell `n_g < N_min` even after hierarchical merging | Medium | Medium — collapses Mondrian to fewer effective cells | Hierarchical merging is automatic per `crc.py`; if collapse to ≤ 2 cells, paper still claims marginal-only guarantee + reports `G_eff` transparently. |
| Compute over-budget (> 50 GPU-h-eq) | Low | Low | M5 polish runs are nice-to-have; can drop secondary backbone (Table A2) and EverMemOS-on-Memora (Table A1) without impacting main story. |

---

## Final Checklist

- [x] Main paper tables are covered: Tables 1, 2, 3, 4 + Figures 1, 2, 3 from B1–B4.
- [x] Baseline coverage for main, mechanism, and efficiency blocks per policy 第 5 节: B1 (5-way Ours-vs-baseline), B2 (component-necessity ablations anchored to B1), B3 (3-way parity), B4 (necessity ablation + simpler alternative anchored to B1), B5 (diagnostic-only).
- [x] Novelty is isolated: B2 (`no_conformal`, `no_groups`) provides A1.
- [x] Simplicity is defended: B4 PMI-free alternative tests whether the simpler version is enough; the substrate is reused (Path D is the simpler-substrate baseline implicitly via `no_conformal`).
- [x] Frontier contribution is justified or explicitly not claimed: B4 frontier-necessity check on PMI as the FM-era primitive; if PMI fails its dev gate, paper drops it explicitly and notes in §limitations.
- [x] Nice-to-have runs are separated from must-run runs: M5 + B4 (conditional) + B5-d (EverMemOS) flagged NICE-TO-HAVE.
- [x] Two-public-benchmark gate documented: Memora + LongMemEval-S in §双榜门闸 with explicit pass / fail criteria and failure-mode actions.
- [x] Seed / N matrix documented per `TABLE_SEED_FAIRNESS`: §主表 seed / N 矩阵 (8 tables, 4 with N=3, 4 with N=1; separate-table convention applied).
- [x] Variance / std reporting per `TABLE_DISPERSION`: every multi-seed table caption notes mean ± std + cluster-bootstrap CIs.
- [x] Public-benchmark-only main eval per `MAIN_EVAL_PUBLIC_BENCHMARKS`: Memora (public), LongMemEval-S (public), LoCoMo (appendix, public). No private / self-built data in the main tables.
