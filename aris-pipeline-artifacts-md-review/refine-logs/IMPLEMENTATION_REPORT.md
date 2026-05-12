# β Implementation Report (pre-MAAS-call)

**Date.** 2026-04-26
**Status.** **Code complete; reviewed; not yet executed against MAAS.**
**Total LOC delta.** ~1 700 LOC (8 files touched / created), substantially more than the FINAL_PROPOSAL's "~140 LOC" estimate (which assumed Path D round-2 substrate was already in code — it was not; FINAL_PROPOSAL described it as proposed-but-built; it was proposed-but-only-on-paper).

---

## What was built in this pass

### Substrate (Path D round-2 — was not actually in code before this pass)

| File | Δ LOC | What |
|------|------:|------|
| `ttmg/schema.py` | +30 | Added `claim_key: Optional[Tuple[str,str]]`, `slot_type ∈ {single_valued, multi_valued}`, `object_norm: str` to `Claim`. JSON round-trip preserves tuple. New helper `Claim.canonical_key_str()`. Backward-compat preserved (legacy claims load with new fields unset). |
| `ttmg/canonicalize.py` | +184 (new) | Deterministic post-processor: lowercase + non-alnum→underscore + static pronoun aliases (`I/me/myself → user`; `you/the AI → assistant`) + per-process growing alias map for proper nouns. Stateful `Canonicalizer` shared by writer + parser within one run; thread-safe via internal lock. Exposes `alias_audit()` for paper reproducibility. |
| `ttmg/conflict_linker.py` | +148 | Added `link_claim_3call()` — 3 independent calls with varied (temperature, prompt) → max-agreement-fraction → admit edge iff label ∈ {contradict, supersede} AND hardness ≥ 2/3. Materialises supersede as `valid_to ← new.valid_from` only when both claims are `single_valued` AND share canonical `claim_key`. Original `link_claim()` unchanged for Path D pilots. |
| `ttmg/writer_temporal.py` | +131 | Added `extract_claims_session_beta()` — same as `_session` variant but emits `claim_key`, `slot_type`, `object_norm` in the writer prompt; `Canonicalizer` applied post-hoc to make `claim_key` byte-equal across writer + parser. |
| `ttmg/truth_retriever.py` | +391 | Added `parse_query_beta()` (emits canonical claim_key + applicability flag), `_canonical_key_fetch()`, `_valid_at()` (anchor + active + asks_history), `_hard_edges_within()`, `_all_optima_mwis()` (bounded by `_MWIS_CAP_K = 12` with deterministic top-K pruning), `_hardness_for()`, `truth_retrieve_beta()` (full β read-time path). Original `truth_retrieve()` unchanged. |

### β additions (the actual contribution layer)

| File | Δ LOC | What |
|------|------:|------|
| `ttmg/crc.py` | +591 (new) | Conformal Risk Control layer. `_clopper_pearson_upper()` via scipy or pure-Python continued-fraction fallback, with `conf` clamped to `1 − 1e-15`. `freeze_candidate_thresholds()` builds 5 quantiles per group on dev. `hierarchical_merge()` merges sparse cells along `update_pattern` axis first, then `pmi_bin`. `calibrate_thresholds()` runs single-threshold CP UCB per (g, α) with Bonferroni correction over `|G_eff| × |A| × n_cand_max`. `CRCThresholdTable` defensive lookup falls through to wildcard cells when group unseen. Plus `compute_S()`, `risk_coverage_curve()`, `aurc()`, `empirical_selective_risk()`. |
| `ttmg/pmi.py` | +122 (new) | Frozen-LM PMI estimator via OpenAI-compatible `chat.completions.create(logprobs=True, top_logprobs=1)`. Returns `None` if MAAS does not support logprobs (graceful degradation per FINAL_PROPOSAL failure mode C2). |
| `ttmg/system.py` | +220 | Added β config flags (`enable_beta`, `enable_beta_writer`, `enable_beta_linker`, `enable_pmi`, `crc_table_path`, `crc_alpha`, `score_w_h/w_u/w_p`, `pmi_scale`, `pmi_model`, `beta_no_groups`, `beta_no_canonical_key`, `beta_no_3call`). Added `_answer_beta()` dispatcher that (a) parses with applicability gate, (b) fetches via canonical key, (c) builds `S(q)` + group, (d) checks CRC threshold, (e) returns route ∈ {ttmg, abstain, flat}. Added `_pmi_bin()` and `_update_pattern_bin()` Mondrian binners (graph-feature-based; `_update_pattern_bin()` uses `n_supersede_edges`, `n_active_values`, `n_temporal_updates`, `conflict_degree`). Added `set_pmi_bins()` for dev-tuning. |

### Orchestration

| File | LOC | What |
|------|----:|------|
| `scripts/calibrate_crc.py` | 426 (new) | Full β calibration runner. Loads Memora persona × duration; **disjoint dev/cal split** (Codex-fix CRITICAL #1) via deterministic seed-controlled shuffle; ingests sessions; runs TTMG-β `answer()` on each question; judges every criterion against Memora's `expected_answer` ground truth; computes per-question MPA / FAA / λ / FAMA via `_question_correct_overall` (Codex-fix CRITICAL #3: failed judge → INCORRECT, full denominators); calls `freeze_candidate_thresholds(dev_samples, ...)` then `calibrate_thresholds(cal_samples, ...)`; persists locked `threshold_table` + git hash + code sha256 + per-cell audit. |
| `experiments/eval_memora.py` | 276 (new) | Method-agnostic Memora runner. Supports `--method ∈ {flat, amem, ttmg_pathd, ttmg_beta}`. Loads + ingests + answers + scores via the same `_question_correct_overall` from `calibrate_crc.py`. Aggregates per-task FAMA × 100 / N (Memora paper formula). `--max-parallel-questions 1` by default (server-load policy). |

---

## Codex GPT-5.4 cross-model code review

Single review pass + one follow-up. **3 CRITICAL + 1 MAJOR + 1 MINOR + 1 follow-up CRITICAL caught and fixed.**

| ID | Severity | Codex finding | Fix applied |
|----|----------|---------------|-------------|
| 1 | CRITICAL | `calibrate_crc.py` was building `T_cand` from cal_samples (calibration-leak; theorem requires dev-only). | `dev_samples` now collected separately; `freeze_candidate_thresholds(dev_samples)` then `calibrate_thresholds(cal_samples, cand)`. Stable sort before deterministic shuffle so order is reproducible across runs. |
| 2 | CRITICAL | `CRCThresholdTable.lookup` could silently return `+∞` on unseen-at-calibration groups, even when wildcard cells exist. | Added `_fallback_groups()` that yields progressively-coarser cells: `(b1,b2)` → `('*',b2)` → `(b1,'*')` → `('*','*')`. Verified with hand-crafted table: `('z1','z2')` falls through to `'*::*'` instead of `+∞`. |
| 3 | CRITICAL | `_question_correct_overall` skipped failed-judge criteria, inflating MPA/FAA and over-crediting `overall_correct`. | Failed judge now treated as INCORRECT (after 1 retry), denominators kept at full `n_presence + n_forget`. `overall_correct` requires zero `judge_failures` AND every criterion correctly judged. |
| 4 | MAJOR | `_all_optima_mwis` had no cap for `k > 8` → 2^k blow-up. | Added `_MWIS_CAP_K = 12` (`2^12 = 4096`). When exceeded: deterministic top-K by `(weight desc, id asc)`; drops dangling hard pairs; logs warning via `logging.getLogger("ttmg.truth_retriever.mwis")` so paper-side appendix can report frequency. |
| 5 | MINOR | `_clopper_pearson_upper(... conf=1.0)` could be unstable on the fallback path. | Added `conf = min(max(conf, 0.0), 1.0 - 1e-15)` clamp on both the scipy and the dependency-free paths. |
| 6 | CRITICAL (round 2) | `calibrate_thresholds` was backfilling missing cand_per_eff entries from `cal_samples` scores → still a calibration-leak for merged cells. | Removed cal-side backfill. Empty `cand_per_eff[eff] = []` cells now correctly produce `+∞` (always-abstain) per the theorem. Verified with synthetic test: a `('B','y')` cell that exists only in cal stays at INF. |

After fixes, all smoke tests pass (`canonicalize`, `compute_S`, `risk_coverage_curve`, `aurc`, `freeze_candidate_thresholds → calibrate_thresholds → CRCThresholdTable.lookup`, MWIS pruning at k=20, judge-failure FAMA accounting, dev/cal split disjointness).

---

## What is *not* yet done (and is OUT OF SCOPE for this pass per user instruction)

- **No MAAS API calls.** No writer / linker / parser / reader / judge has been invoked. The dev-tuning of `(w_h, w_u, w_p, PMI_scale)`, the `update_pattern` proxy ρ validation, the PMI Spearman ρ probe, and the per-group dev coverage gate are **not yet run**.
- **No EverMemOS reproduction.** The path `MemMachine/competitor/2601.02163_EverMemOS/code/` exists but has not been installed or run.
- **No Mem0 / LightMem reproduction.** Same — code paths in tracker R008 / R009 not yet exercised.
- **No real Memora calibration.** `scripts/calibrate_crc.py` has been smoke-tested with synthetic data only.
- **No full-test run on Memora.** `experiments/eval_memora.py` smoke-tested with imports only.
- **No paper writeup.** All paper-side artifacts (figures, tables, statistical analyses, citations) are still TODO.

---

## Concurrency / server-load policy

All test scripts default to `--max-parallel-questions 1` (sequential MAAS calls). The shared host's load average was **51 / 54 / 47** at implementation time (multiple in-flight training jobs from other users); per `CLAUDE.md` policy "严禁在高 load 时继续叠加多 job", we should not deploy any parallel runs without re-checking `uptime` first.

---

## Known caveats (carry into paper § Limitations)

1. **Single-judge FAMA vs 3-judge published protocol.** Cost-driven deviation; document with a 100-question 3-judge agreement audit if reviewers ask.
2. **Backbone differs from Memora baselines.** Paper baselines used GPT-4o-mini; default reader is deepseek-v3.2.
3. **MWIS pruning at k > 12** changes semantics: the operator becomes "exact MWIS over the top-12 candidates by writer confidence" rather than "exact MWIS over all retrieved candidates". The cap should fire rarely (canonical-key fetch typically returns ≤ 8 claims per slot), but its frequency must be reported as a paper-side audit number.
4. **PMI graceful degradation.** If MAAS doesn't expose logprobs, PMI returns `None`; `S(q)` weights re-balance to `(0.7, 0.3, 0.0)` automatically; `pmi_bin` collapses to `'mid'` for all queries → effectively kills the Mondrian PMI axis. The PMI phase diagram becomes a negative result in this case (FINAL_PROPOSAL §C2).
5. **Wildcard fallback in lookup may smooth away per-group nuance.** When an inference-time group is unseen at calibration, the operator falls back to coarser cells. This is conservative-correct (the wildcard cell's threshold is a valid CRC bound for any sub-population sampled from the same exchangeable distribution), but we should report fall-through rate per benchmark as a transparency diagnostic.

---

## Next step (requires user go-ahead)

**M0-1 (sanity smoke)**: pull Memora data, integrate `crc.py` + `pmi.py`, run TTMG-β on a 50-q toy slice at seed 0; verify pipeline runs end-to-end + `crc.py` returns sane thresholds. Cost: ~1 GPU-h-equivalent, ~50 sequential MAAS calls.

After M0-1 succeeds, the per-FINAL_PROPOSAL gating order is:
- Wk 1: dev tuning + intrinsic gates + lock threshold_table.
- Wk 2: full Memora test 5 methods × 3 seeds + LongMemEval-S parity 3 methods × 3 seeds + EverMemOS reproduction (appendix).
- Wk 3: ablations (`no_conformal`, `no_groups`); risk-coverage curves; PMI phase diagram; cluster-bootstrap CIs.
- Wk 4: paper rewrite + figures.

Estimated total compute: ~41 GPU-h-equivalents per `EXPERIMENT_PLAN.md`. All sequential MAAS calls; no local GPU training.
