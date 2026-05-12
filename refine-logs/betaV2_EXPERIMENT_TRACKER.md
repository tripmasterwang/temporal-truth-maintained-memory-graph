# Experiment Tracker — Pivot β v2

**Source plan.** `refine-logs/EXPERIMENT_PLAN.md`
**Date.** 2026-04-26

| Run ID | Milestone | Purpose | System / Variant | Split / Dataset | Seed | Metrics | Priority | Status | Notes |
|--------|-----------|---------|------------------|-----------------|------|---------|----------|--------|-------|
| R001 | M0-1 | Sanity smoke | TTMG-β | Memora 50-q toy slice | 0 | end-to-end pipeline OK; CRC returns sane thresholds | MUST | TODO | First run; verify Memora data loader + `crc.py` integration. |
| R002 | M1-1 | Dev tuning | TTMG-β | Memora train (60 % dev) | 0 | tune `(w_h, w_u, w_p, PMI_scale)` | MUST | TODO | Lock weights before M1-2. |
| R003 | M1-2 | Per-group dev coverage gate | TTMG-β | Memora train (10 % held-back of dev) | 0 | per-group `r̂_g(τ̂_g(α; δ))` ≤ α + 0.02 for 5 α | MUST | TODO | **Lock-stop gate.** |
| R004 | M1-3 | `update_pattern` proxy validation | TTMG-β | Memora dev | 0 | Spearman ρ ≥ 0.6 vs Memora ground truth | MUST | TODO | **Lock-stop gate.** Re-tune bins if ρ < 0.6; drop axis if ρ < 0.4 after re-tune. |
| R005 | M1-3 | PMI Spearman intrinsic | TTMG-β | Memora dev | 0 | ρ ≥ 0.5 between PMI and answer correctness | MUST | TODO | **Lock-stop gate.** Drop PMI from S if ρ < 0.3. |
| R006 | M1 (final) | Lock `threshold_table` + commit hash | TTMG-β | Memora train (40 % calibration) | n/a | git-hashed threshold table | MUST | TODO | Print hash in paper. No further tuning past this point. |
| R007 | M2-1 | Baseline reproduction: A-Mem | A-Mem (project's `ttmg/amem_base/`) | Memora full test | 0 | smoke run; FAMA in published-similar range | MUST | TODO | A-Mem already reimpl in project; quick check. |
| R008 | M2-2 | Baseline reproduction: Mem0 | Mem0 (upstream) | Memora full test | 0 | install + smoke FAMA | MUST | TODO | If install fails > 1 day → drop, declare in §limitations. |
| R009 | M2-3 | Baseline reproduction: LightMem | LightMem (upstream) | Memora full test | 0 | install + smoke FAMA | MUST | TODO | Same install policy as Mem0. |
| R010 | M2-4 | EverMemOS install + LoCoMo sanity | EverMemOS (`MemMachine/competitor/.../code/`) | LoCoMo full | 0 | reproduces published LoCoMo within 5 pp | NICE | TODO | Appendix-only. If fails → cite published numbers. |
| R011 | M3-1 | **Memora main**: Flat | Flat hybrid-RAG | Memora full test | 0 | per-group risk @ 5 α; risk-coverage curve; AURC; FAMA | MUST | TODO | Table 1, 2 row. |
| R012 | M3-1 | Memora main: Flat | Flat hybrid-RAG | Memora full test | 7 | same | MUST | TODO | Table 1, 2 row. |
| R013 | M3-1 | Memora main: Flat | Flat hybrid-RAG | Memora full test | 17 | same | MUST | TODO | Table 1, 2 row. |
| R014 | M3-1 | Memora main: A-Mem | A-Mem | Memora full test | 0 | same | MUST | TODO | Table 1, 2 row. |
| R015 | M3-1 | Memora main: A-Mem | A-Mem | Memora full test | 7 | same | MUST | TODO | Table 1, 2 row. |
| R016 | M3-1 | Memora main: A-Mem | A-Mem | Memora full test | 17 | same | MUST | TODO | Table 1, 2 row. |
| R017 | M3-1 | Memora main: Mem0 | Mem0 | Memora full test | 0 | same | MUST | TODO | Table 1, 2 row. |
| R018 | M3-1 | Memora main: Mem0 | Mem0 | Memora full test | 7 | same | MUST | TODO | Table 1, 2 row. |
| R019 | M3-1 | Memora main: Mem0 | Mem0 | Memora full test | 17 | same | MUST | TODO | Table 1, 2 row. |
| R020 | M3-1 | Memora main: LightMem | LightMem | Memora full test | 0 | same | MUST | TODO | Table 1, 2 row. |
| R021 | M3-1 | Memora main: LightMem | LightMem | Memora full test | 7 | same | MUST | TODO | Table 1, 2 row. |
| R022 | M3-1 | Memora main: LightMem | LightMem | Memora full test | 17 | same | MUST | TODO | Table 1, 2 row. |
| R023 | M3-1 | **Memora main: TTMG-β** | TTMG-β full | Memora full test | 0 | same | MUST | TODO | **Headline row.** Table 1, 2. |
| R024 | M3-1 | Memora main: TTMG-β | TTMG-β full | Memora full test | 7 | same | MUST | TODO | Table 1, 2 row. |
| R025 | M3-1 | Memora main: TTMG-β | TTMG-β full | Memora full test | 17 | same | MUST | TODO | Table 1, 2 row. |
| R026 | M3-2 | LongMemEval-S parity calibration | TTMG-β | LongMemEval-S train (60 / 40) | 0 | per-group dev coverage; lock LME-S `threshold_table` | MUST | TODO | Re-fit `T_cand`, bins on LME-S dev. |
| R027 | M3-2 | LongMemEval-S parity: Flat | Flat | LongMemEval-S N=500 test | 0 | overall accuracy + per-group risk | MUST | TODO | Table 4 row. |
| R028 | M3-2 | LongMemEval-S parity: Flat | Flat | LongMemEval-S N=500 test | 7 | same | MUST | TODO | Table 4 row. |
| R029 | M3-2 | LongMemEval-S parity: Flat | Flat | LongMemEval-S N=500 test | 17 | same | MUST | TODO | Table 4 row. |
| R030 | M3-2 | LongMemEval-S parity: A-Mem | A-Mem | LongMemEval-S N=500 test | 0 | same | MUST | TODO | Table 4 row. |
| R031 | M3-2 | LongMemEval-S parity: A-Mem | A-Mem | LongMemEval-S N=500 test | 7 | same | MUST | TODO | Table 4 row. |
| R032 | M3-2 | LongMemEval-S parity: A-Mem | A-Mem | LongMemEval-S N=500 test | 17 | same | MUST | TODO | Table 4 row. |
| R033 | M3-2 | LongMemEval-S parity: TTMG-β | TTMG-β | LongMemEval-S N=500 test | 0 | same | MUST | TODO | Table 4 row. |
| R034 | M3-2 | LongMemEval-S parity: TTMG-β | TTMG-β | LongMemEval-S N=500 test | 7 | same | MUST | TODO | Table 4 row. |
| R035 | M3-2 | LongMemEval-S parity: TTMG-β | TTMG-β | LongMemEval-S N=500 test | 17 | same | MUST | TODO | Table 4 row. |
| R036 | M3-3 | Risk-coverage curves + AURC + matched-rate markers | n/a (post-hoc) | Memora results from R011-R025 | n/a | curves, AURC, cluster-bootstrap CIs | MUST | TODO | Figure 2; Table 2. |
| R037 | M3-3 | Per-cell `(n_g, abstain_mass_g)` | n/a (post-hoc) | Memora results | n/a | per-cell counts table | MUST | TODO | Table A0. |
| R038 | M3-3 | KS drift descriptor | n/a (post-hoc) | Memora calibration vs test | n/a | KS statistic + p-value on `(pmi_bin, update_pattern)` | MUST | TODO | §Discussion paragraph; descriptive only. |
| R039 | **GATE** | Two-benchmark continuation gate | n/a | Memora + LongMemEval-S | n/a | Memora coverage + AURC + FAMA non-regression AND LongMemEval-S coverage + parity | MUST | TODO | **Stop / refine / waiver decision point.** |
| R040 | M4-1 | Ablation: TTMG-β-no_conformal | no_conformal (revert to Path D MWIS abstention) | Memora full test | 0 | per-group risk; FAMA | MUST | TODO | Table 3 row. |
| R041 | M4-1 | Ablation: TTMG-β-no_conformal | no_conformal | Memora full test | 7 | same | MUST | TODO | Table 3 row. |
| R042 | M4-1 | Ablation: TTMG-β-no_conformal | no_conformal | Memora full test | 17 | same | MUST | TODO | Table 3 row. |
| R043 | M4-2 | Ablation: TTMG-β-no_groups | no_groups (marginal CP only) | Memora full test | 0 | per-group risk; FAMA | MUST | TODO | Table 3 row. |
| R044 | M4-2 | Ablation: TTMG-β-no_groups | no_groups | Memora full test | 7 | same | MUST | TODO | Table 3 row. |
| R045 | M4-2 | Ablation: TTMG-β-no_groups | no_groups | Memora full test | 17 | same | MUST | TODO | Table 3 row. |
| R046 | M4-3 | Ablation: TTMG-β-no_pmi | no_pmi (drop PMI from S; collapse pmi_bin) | Memora full test | 0 | per-group risk; AURC; FAMA | MUST (if PMI in headline) / NICE (if dropped at M1) | TODO | Table A3 row. |
| R047 | M4-3 | Ablation: TTMG-β-no_pmi | no_pmi | Memora full test | 7 | same | MUST/NICE | TODO | Table A3 row. |
| R048 | M4-3 | Ablation: TTMG-β-no_pmi | no_pmi | Memora full test | 17 | same | MUST/NICE | TODO | Table A3 row. |
| R049 | M4-4 | PMI phase diagram | TTMG-β | Memora dev | 0 | PMI-bin × AURC gap on temporal-forgetting subset | MUST (if PMI in headline) | TODO | Figure 3. |
| R050 | M4-5 | PMI-free simpler alternative | `S = w_h · hardness + w_u · 1[|Vals|==1]` only | Memora full test | 0 | per-group risk; AURC | NICE | TODO | Re-fit `T_cand` on dev. Table A3. |
| R051 | M4 | Substrate ablation: `no_canonical_key` | TTMG-β minus canonical-key fetch | Memora full test | 0 | per-group risk; AURC; FAMA | NICE | TODO | Table A3. |
| R052 | M4 | Substrate ablation: `no_3call_agreement` | TTMG-β minus 3-call linker (use 1-call) | Memora full test | 0 | per-group risk; AURC; FAMA | NICE | TODO | Table A3. |
| R053 | M5-1 | Secondary backbone: Flat | Flat | Memora full test | 0 | overall + FAMA | NICE | TODO | Backbone = Qwen3-30B-A3B-Instruct-2507. Table A2. |
| R054 | M5-1 | Secondary backbone: TTMG-β | TTMG-β | Memora full test | 0 | overall + per-group risk + FAMA | NICE | TODO | Table A2. |
| R055 | M5-1 | Secondary backbone: Flat | Flat | LongMemEval-S N=500 test | 0 | overall accuracy | NICE | TODO | Table A2. |
| R056 | M5-1 | Secondary backbone: TTMG-β | TTMG-β | LongMemEval-S N=500 test | 0 | overall + per-group risk | NICE | TODO | Table A2. |
| R057 | M5-2 | LoCoMo appendix: Flat | Flat | LoCoMo full | 0 | overall accuracy + applicability rate | NICE | TODO | Table A4. Reuse Path D LoCoMo runs if still valid. |
| R058 | M5-2 | LoCoMo appendix: A-Mem | A-Mem | LoCoMo full | 0 | same | NICE | TODO | Table A4. |
| R059 | M5-2 | LoCoMo appendix: TTMG-β | TTMG-β | LoCoMo full | 0 | overall + per-group risk + applicability rate + composed end-to-end | NICE | TODO | Table A4. |
| R060 | M5-3 | EverMemOS on Memora | EverMemOS (best-effort reproduction) | Memora full test | 0 | overall + FAMA | NICE | TODO | Table A1. Single seed for EverMemOS; pair-compare TTMG-β at seed=0. |
| R061 | M5-4 | Cluster-bootstrap CIs | n/a (post-hoc) | All Memora results | n/a | bootstrap 95 % CI over (persona × duration) | MUST | TODO | Annotates Tables 1-3 + Figure 2. |
| R062 | M5-5 | Paper rewrite + figures | n/a | n/a | n/a | n/a | MUST | TODO | Outline started end-Wk 2; figures finalised mid-Wk 4. |

**Status legend.** TODO / IN_PROGRESS / DONE / BLOCKED / SKIPPED.

**Notes on tracker hygiene.**
- Mark a row IN_PROGRESS only when actively running it.
- Mark BLOCKED with the reason (e.g. "Mem0 install failed; awaiting decision to drop").
- Mark SKIPPED for runs that were planned but rendered unnecessary by an earlier gate result (e.g. if PMI fails M1-3 gate and is dropped, R046-R049 become SKIPPED with a note).
- The two-benchmark gate at R039 is the central decision point of the experiment; do not start M4 / M5 until R039 is resolved.
