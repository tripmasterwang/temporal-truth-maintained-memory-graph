# Memora + FAMA — Setup Notes

**Date.** 2026-04-26
**Source paper.** Memora: A Long-Term Memory Benchmark for Personalized Agents (arXiv 2604.20006, 2026)
**Local data.** `/home/workspace/lww/project0412/projects/MemMachine/competitor/2604.20006_Memora_FAMA/code/Memora/data/`

---

## Data layout

```
Memora/data/
├── weekly/
│   ├── academic_researcher/
│   │   ├── conversations/
│   │   │   ├── session_0001.json
│   │   │   ├── session_0002.json
│   │   │   └── ... (~150 sessions per persona)
│   │   └── evaluation_questions_academic_researcher.json
│   ├── business_executive/
│   ├── content_writer/
│   ├── creative_designer/
│   ├── financial_analyst/
│   ├── management_consultant/
│   ├── marketing_manager/
│   ├── sales_manager/
│   ├── software_engineer/
│   └── startup_founder/
├── monthly/      ← same 10 personas, longer histories
└── quarterly/    ← same 10 personas, longest histories
```

**Total file count:** 27 644 across the 3 durations × 10 personas.

## Session schema (`conversations/session_NNNN.json`)

```json
{
  "session_id": 1,
  "session_type": "no_memory" | "memory_grounded",
  "operation": null | "add" | "update" | "delete",
  "operation_details": {...},
  "date": "2025-06-01",
  "persona": "academic_researcher",
  "conversation": [
    {"turn": 1, "speaker": "ai_agent",   "message": "...", "share_memory": false},
    {"turn": 2, "speaker": "user_agent", "message": "...", "share_memory": false},
    ...
  ]
}
```

**Speaker mapping** (used by our `_convert_session_to_ttmg`):
- `user_agent` → `user`
- `ai_agent` → `assistant`

## Question schema (`evaluation_questions_<persona>.json`)

```json
{
  "persona": "academic_researcher",
  "date_range": {"start_date": "2025-06-01", "end_date": "2025-06-07"},
  "questions": [
    {
      "remembering": [...],
      "reasoning":   [...],
      "recommending": [...]
    },
    ... (one such dict per query date — typically 3 dates per persona)
  ]
}
```

> Note: the top-level `questions` list contains **dicts** (not flat question lists). Each dict has 3 task keys. Our `_flatten_question_groups` flattens to `[(task, question), ...]`.

### Per-question schema

```json
{
  "question_id": "activity_todos_158",
  "question": "What tasks remain on my todo list this week?",
  "question_date": "2025-06-07",
  "memory_evidence": {
    "remaining_tasks": [
      {"value": "Plan field work schedule", "session_id": 100},
      ...
    ],
    "task_count": 5
  },
  "forgetting_evidence": {
    "forgotten_items": [
      {"value": "Visit university library", "session_id": 27},
      ...
    ],
    "total_forgotten_items": 8
  },
  "evaluation": {
    "evaluation_questions": [
      {
        "evaluation_question_id": "activity_todos_158_eval_memory_presence_0",
        "evaluation_question": "Does the response mention the task: Plan field work schedule?",
        "expected_answer": "yes",
        "evaluation_type": "memory_presence"
      },
      {
        "evaluation_question_id": "activity_todos_158_eval_forgetting_absence_0",
        "evaluation_question": "Does the response mention the deleted task: plan academic conference attendance?",
        "expected_answer": "no",
        "evaluation_type": "forgetting_absence"
      },
      ...
    ]
  }
}
```

> **Ground-truth field is `expected_answer`** — this is what our LLM-as-judge compares against. The criterion text in `evaluation_question` is the yes/no question we ask the judge. We never use a model's own output as a ground-truth label.

---

## FAMA scoring

Per the Memora paper §4.1.2 (Forgetting-Aware Memory Accuracy):

```
FAMA = max(0, MPA − λ · (1 − FAA))
λ    = N_forget / (N_presence + N_forget)
```

- **MPA** (Memory Presence Accuracy) = #(memory_presence criteria correctly satisfied) / N_presence.
- **FAA** (Forgetting Absence Accuracy) = #(forgetting_absence criteria correctly satisfied) / N_forget.
- **N_presence**, **N_forget** are per-question counts of each criterion type.
- Per-question FAMA ∈ [0, 1].
- Per-task aggregation: `100 × mean(FAMA across questions in this task within this persona × duration)`. This matches "sum per-question FAMA across all questions within that task and normalize to [0, 100]" (paper §4.1.2 last paragraph).
- Per-duration aggregation: sum of three task scores ∈ [0, 300] (matches table headers in published baselines).

### Judge protocol

- **Memora paper:** 3-judge majority vote (GPT-4.1 + Claude Haiku 4.5 + Gemini 2.5 Flash). Validated against humans at 88.3% agreement, Cohen's κ = 0.86–0.90.
- **Our deviation (cost):** single judge (`deepseek-v3.2` by default) with 1 retry on JSON-parse / no-yes-no-answer failures. Failed judges count the criterion as INCORRECT (not skipped) so denominators stay at full N_presence + N_forget — see Codex-fix CRITICAL #3.
- **Caveat for paper writeup:** if the single-judge protocol disagrees with the published baselines by > 5 FAMA-points (where the paper uses 3-judge), we should rerun a small sample (e.g. 100 questions) with the 3-judge protocol and report the agreement rate. This is documented as a known limitation in IMPLEMENTATION_REPORT.md.

### Memora paper baselines (commented in `latex/tex/experiments.tex`, aggregated FAMA across week + month + quarter, max 300)

| Method | Remembering | Recommending | Reasoning | Sum |
|--------|------------:|-------------:|----------:|----:|
| **Long-term agents (avg)** | **119.62** | **138.37** | **27.30** | — |
| A-Mem | 155.50 | 107.51 | 9.00 | 272.01 |
| LangMem | 152.30 | 126.81 | 55.00 | 334.11 |
| Mem-0 | 81.40 | 127.25 | 18.00 | 226.65 |
| MemoBase | 78.86 | 173.02 | 26.00 | 277.88 |
| MemoryOS | 106.67 | 155.20 | 32.16 | 294.03 |
| Nemori | 142.97 | 140.42 | 23.66 | 307.05 |
| **LLMs no memory (avg)** | **65.60** | **144.72** | **12.37** | — |
| GPT-5.2 | 68.63 | 159.28 | 5.66 | 233.57 |
| Claude Sonnet 4.5 | 68.17 | 126.64 | 15.16 | 209.97 |
| Gemini 3 Pro Preview | 59.08 | 143.62 | 14.66 | 217.36 |
| Qwen3-32B | 66.51 | 149.34 | 14.00 | 229.85 |

> **Important:** The numbers above are aggregated across all three durations. Our `eval_memora.py` reports *per-duration* and per-task, summed at the duration level. To compare to the paper, sum across the three durations. Also note all baselines used **GPT-4o-mini** as the answer LLM; we use **deepseek-v3.2** by default — backbone differences will affect raw numbers, but the *guarantee claim* (selective risk ≤ α) is backbone-independent.

---

## How the loader maps Memora → TTMG

`scripts/calibrate_crc.py:_convert_session_to_ttmg()` produces:

```python
{
  "session_id": "1",
  "session_ts": "2025-06-01",
  "turns": [
    {"speaker": "user", "text": "..."},
    {"speaker": "assistant", "text": "..."},
    ...
  ]
}
```

This is the input format `TTMGSystem.ingest_conversation()` already accepts (no schema changes needed in Path D code).

`scripts/calibrate_crc.py:_flatten_question_groups()` flattens the per-persona `questions` blob into `[(task, question), ...]`.

---

## Concurrency note

All Memora runs are **sequential by default** (`--max-parallel-questions 1` in `experiments/eval_memora.py`). This is intentional: server load on the shared box was 51 / 54 / 47 when β code was implemented. Do **not** raise parallelism without first checking `uptime` and `nproc`.

---

## Known caveats (for paper §Methods)

1. **Single-judge vs 3-judge.** We run single-judge for cost; document agreement against 3-judge on a held-out 100-question sample if reviewers ask.
2. **Backbone mismatch.** Memora baselines used GPT-4o-mini; our default reader is deepseek-v3.2. Section §Discussion or §Limitations should make this explicit.
3. **Calibration / test exchangeability.** The Memora train/test split is per-persona × per-duration. Our calibration uses 60 % of train → dev, 40 % → cal. Test is held out. The `KS-test calibration vs test on (pmi_bin, update_pattern)` diagnostic from FINAL_PROPOSAL is a *descriptive* drift check, not a decision gate.
4. **`update_pattern` proxy.** Our inference-time `update_pattern` label is computed from observable graph features (`n_supersede_edges`, `n_active_values`, `n_temporal_updates`, `conflict_degree`). Memora's metadata gives the ground-truth update count per question; we validate the proxy on dev with Spearman ρ ≥ 0.6 as a pre-test gate (see FINAL_PROPOSAL §pre-test gates).
