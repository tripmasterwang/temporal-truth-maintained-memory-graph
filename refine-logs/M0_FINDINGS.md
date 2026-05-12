# M0-1 Smoke Findings — Critical Decision Point

**Date.** 2026-04-27
**Runs.** `m0_dryrun_ttmg_beta.json` (1 q), `m0_smoke_ttmg_beta_15q.json` (15 q), `parser_probe_*_weekly.json` (10 personas × 15 q = 150 q).
**Total MAAS calls used:** ~250
**Total wall-clock:** ~25 min

---

## TL;DR

The β code works end-to-end with 0 judge failures, but **β never lands `route=ttmg` on Memora questions** — the global applicability rate is 33 %, and within that 33 % every question is an *aggregation/comparison* query that β correctly abstains on (`non_unique_value` because the writer extracts multiple per-day values).

**The Memora benchmark distribution does not match β's operator scope.** This is a structural mismatch, not a code bug.

---

## Hard numbers from the probe (10 personas × weekly × 15 q = 150 q)

| Persona | Applicable | Rate |
|---|---:|---:|
| All 10 personas | **50 / 150** | **33 %** |

Per-task breakdown (across all personas):

| Task | n | applicable | single_valued | multi_valued | unknown_slot | asks_truth_of_fact |
|---|---:|---:|---:|---:|---:|---:|
| remembering | 50 | **0** | 0 | 12 | 38 | 12 |
| reasoning | 50 | **50** | 50 | 0 | 0 | 50 |
| recommending | 50 | **0** | 0 | 10 | 40 | 1 |

**Reading.** Parser is making *correct* classifications:
- All `remembering` content-generation tasks ("write a project proposal") → `slot_type=unknown` → not applicable. ✓
- All `recommending` ("suggest me a movie") → `asks_truth_of_fact=False` → not applicable. ✓
- All `reasoning` ("what is my total food spending this week?") → applicable, single-valued. ✓ *but* see below.

The 50 applicable questions cluster into 8 single-valued slots:

| Slot | n questions |
|---|---:|
| `user.food_spending` | 10 |
| `user.step_count` | 10 |
| `user.coffee_spending` | 10 |
| `user.daily_step_goal_met` | 7 |
| `user.coffee_budget_goal` | 6 |
| `user.lunch_budget_goal` | 2 |
| `user.daily_step_goal_achieved` | 2 |
| (other singletons) | 3 |

---

## Why β abstains on the applicable 33 %

All 50 applicable questions are **aggregation or comparison** queries. Examples:
- "What is my total food spending this week?" → writer extracts ~7 food-spending claims (one per day, e.g. `$8.50`, `$12.00`, `$15.00`); β's MWIS yields multiple `object_norm` values; rule "answer iff |Vals|==1" correctly fires `non_unique_value` → **abstain**.
- "Am I meeting my lunch budget goal?" → needs to compare current sum vs target; multiple distinct values exist; abstain.

This is the *correct semantics* of the operator: "I don't have a unique current value for this slot." But it means β **never gets to answer** any Memora question — the dominant claim "selective-risk-controlled wins on Memora's temporal-forgetting subset" is unsupportable on the natural Memora distribution.

In the M0-1 smoke (15 q × 5 sessions ingested):
- 5 reasoning → all 5 abstained (`route=abstain`, `non_unique_value_no_crc`)
- 10 non-reasoning → all routed to flat fallback

`beta_route_ttmg = 0` across both runs.

---

## Why this is a structural problem, not a code bug

β was designed for the question type: *"What is the current canonical value of single-valued slot X for entity E at time τ?"*

Memora's question distribution contains:
1. **Open-ended generation** (write proposal / write email / write meeting notes) — out of scope. 33 %.
2. **Multi-valued list recall** (todo list, books, music suggestions) — out of scope. 33 %.
3. **Aggregation / comparison** (total spending, step count, goal-met) — *technically* single-valued (one number) but the underlying data is naturally multi-valued (per-day entries). 33 %.

What's *missing* in Memora: simple "current state of single slot" queries like
- "What is the user's preferred coffee temperature?"
- "Where does the user currently work?"
- "What is the user's favourite movie director?"

These are exactly what LongMemEval-S's KU and TR slices test, and are why FINAL_PROPOSAL §3 listed LongMemEval-S as a parity benchmark — but the actual β-applicable slice may be larger on LongMemEval-S than on Memora.

---

## Implications for FINAL_PROPOSAL

The headline claim **C1 — "Risk-coverage Pareto-dominance + AURC win on Memora's temporal-forgetting subset"** depends on β having meaningful coverage on Memora. The probe shows that coverage is effectively zero. Three options:

### Option A — Pivot benchmark order: lead with LongMemEval-S, demote Memora to "applicability transparency report"

- *What changes:* C1 becomes "selective-risk guarantee + AURC win on LongMemEval-S KU+TR slice". Memora becomes a §6 honesty audit ("here is where the operator does NOT apply, and we report the coverage diagnostic").
- *Cost:* low. LongMemEval-S infrastructure exists in this project (`results/full500_*.json`); we can run β on it within Wk 1.
- *Risk:* medium. Need to verify LongMemEval-S applicability rate is meaningfully > 33 %.
- *Two-benchmark gate:* still satisfied (LongMemEval-S as primary + Memora as transparency).

### Option B — Build a synthetic "current-state-tracking" sub-slice from Memora

- *What changes:* Use Memora's memory traces (`session_id` references in `memory_evidence`) to manufacture single-valued lookup questions like "What is the user's current lunch budget goal as of session 124?" This becomes the controlled supersede slice.
- *Cost:* 2-4 days of data engineering; ~200-400 questions; non-trivial validation.
- *Risk:* medium-high. Reviewers may push back: "you only win on a slice you constructed yourselves". But FINAL_PROPOSAL § Optional Supporting already anticipated this.

### Option C — Broaden β's applicability gate to handle aggregation

- *What changes:* Add a fourth route `route=aggregate` that uses MWIS to surface ALL valid claims for a slot, then asks the reader to compute the aggregate. Dropping the "unique value" requirement on aggregation slot_types.
- *Cost:* method change; needs re-refinement and theorem re-statement (the CRC guarantee was conditional on the single-value decision rule; aggregation needs a different risk definition).
- *Risk:* high. This is a method pivot, not a code pivot.

---

## Recommendation

**Option A.** Pivot the benchmark hierarchy: LongMemEval-S becomes the primary benchmark (where we expect the operator to fire), Memora demotes to "applicability transparency" appendix. This keeps the FINAL_PROPOSAL theorem and code intact; only the empirical centre changes.

Concretely, the next step is to run a **parser-only probe on LongMemEval-S** — same cheap protocol we used here — and verify that the applicability rate on LongMemEval-S's KU + TR slices is materially higher than Memora's 33 %. If yes, pivot. If no, escalate to Option B.

---

## Side findings (worth recording)

1. **`query_parse` field was missing from per-question JSON output.** Patched in `eval_memora.py` (now persists `claim_key`, `slot_type`, `asks_truth_of_fact`, `applicable`, `canonical_key_str`, `fallback_used`).
2. **0 judge failures across 81 + 16 = 97 binary criteria.** LLM-as-judge on `deepseek-v3.2` is reliable enough for the FAMA pipeline.
3. **Wall-clock per question ≈ 35 sec including ingestion overhead** (5 sessions × 21 turns embedding + writer + linker + parser + reader + judge).
4. **Bun all-MiniLM-L6-v2 model load takes ~10 sec, dominates short runs.** Negligible for full-scale runs.
5. **`activity_todos_158` parser correctly tags `asks_truth_of_fact=True` but `slot_type=multi_valued`** → applicable=False. Demonstrates the gate is robust.

---

## Decision log

- [x] M0-1 dry run passed (1 q, 215 sec)
- [x] M0-1 smoke passed (15 q, 555 sec, 0 judge fails)
- [x] Global parser probe completed (150 q, ~5 min, 33 % applicable)
- [ ] **DECISION**: pivot to LongMemEval-S as primary benchmark? (recommended A)
- [ ] If A: parser-only probe on LongMemEval-S to verify applicability rate is > 50 % on KU + TR slices.
