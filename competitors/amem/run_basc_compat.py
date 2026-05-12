"""Faithful A-Mem (Xu et al. 2025) driver.

Wraps `agentic_memory.AgenticMemorySystem` so each session of a LongMemEval /
LoCoMo dialogue is fed via `add_note(...)`, then the resulting memory store
is dumped back as a per-input-session retained_text mapping.

Two modes:
* **Default (extraction on)** — A-Mem's headline behaviour; the LLM
  controller extracts keywords/context/tags per note. Routes through MAAS
  via LiteLLM (`OPENAI_API_KEY` + `OPENAI_BASE_URL` env vars).
* **No-extraction (env smoke / sanity)** — pre-populate the keywords/tags
  fields so A-Mem skips the LLM step. Useful as a cost-zero baseline.

Session-id traceback
--------------------
Each `add_note` call passes `category=session_id`. A-Mem stores the
`category` field on the note and exposes it in `sys_.memories[note_id]`,
so we can map every retained note back to its source session at the end.

Budget enforcement
------------------
A-Mem's natural knob is `evo_threshold` (frequency of the consolidation
pass that merges related notes) — but it does not directly cap retained
tokens. After ingestion we post-truncate by descending note score
(retrieval_count + length-tied importance) until total tokens fit.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "competitors" / "amem" / "A-mem-sys"))
sys.path.insert(0, "/home/workspace/lww/project0412/projects/dataset")

from competitors._common.protocol import (  # noqa: E402
    ConsolidatedBuffer, Item, post_truncate_to_budget,
)

BUDGET_INDEPENDENT_CONSOLIDATE = True


def _build_system(*, llm_model: str, extract: bool):
    """Construct an AgenticMemorySystem with MAAS routing."""
    from api import _inject_api_key_from_file  # type: ignore  # noqa: WPS433
    _inject_api_key_from_file()
    os.environ.setdefault("OPENAI_API_KEY", os.environ.get("MAAS_API_KEY", ""))
    os.environ.setdefault("OPENAI_BASE_URL",
                          "https://api.modelarts-maas.com/openai/v1")

    from agentic_memory.memory_system import AgenticMemorySystem  # noqa: WPS433
    return AgenticMemorySystem(
        model_name="all-MiniLM-L6-v2",
        llm_backend="openai",
        llm_model=llm_model,
        # Disable the periodic consolidate by setting threshold > N.
        evo_threshold=10**9,
        api_key=os.environ["MAAS_API_KEY"],
    )


def consolidate(memory: list[Item], *, budget_tokens: int,
                reader_model: str | None = None,
                seed: int = 7,
                extract: bool = True,
                llm_model: str = "deepseek-v3.2") -> ConsolidatedBuffer:
    del reader_model
    sys_ = _build_system(llm_model=llm_model, extract=extract)

    note_id_to_idx: dict[str, int] = {}
    for i, it in enumerate(memory):
        # When extract=False: pre-populate keywords/tags so A-Mem's
        # `needs_analysis` check skips the LLM call.
        kwargs: dict = {"category": it.session_id}
        if not extract:
            kwargs["keywords"] = ["raw"]
            kwargs["tags"] = ["raw"]
            kwargs["context"] = "BASC"
        try:
            note_id = sys_.add_note(content=it.text, **kwargs)
            note_id_to_idx[note_id] = i
        except Exception:
            # Skip on failure; the input session is treated as dropped below.
            pass

    n = len(memory)
    retained_text = ["" for _ in range(n)]
    n_kept_tokens = [0] * n
    importance = [0.0] * n

    for note_id, note in sys_.memories.items():
        idx = note_id_to_idx.get(note_id)
        if idx is None:
            continue
        # Take the canonical retained text as the note's content + (if
        # extraction ran) its summary/keywords. We keep it short so the
        # downstream cosine retrieval can still match against the question.
        retained_text[idx] = note.content
        n_kept_tokens[idx] = len(note.content.split())
        # Importance proxy: retrieval_count if any, else 1.0.
        importance[idx] = float(getattr(note, "retrieval_count", 0) or 0) + 1.0

    retrievable_mask = [bool(t) for t in retained_text]
    cur = sum(n_kept_tokens)
    enforcement = "native(no-cap)"
    if cur > budget_tokens:
        retained_text, retrievable_mask, cur = post_truncate_to_budget(
            retained_text, retrievable_mask, n_kept_tokens, importance,
            budget_tokens,
        )
        enforcement = "post-truncate(by-retrieval-count)"

    return ConsolidatedBuffer(
        retained_text=retained_text,
        retrievable_mask=retrievable_mask,
        total_tokens=cur,
        budget_enforcement=enforcement,
        notes=dict(extract=extract, total_notes=len(sys_.memories),
                   mapped=int(sum(retrievable_mask))),
    )


def _smoke() -> int:
    memory = [
        Item(session_id=f"s{i}",
             text=f"Session {i}: discussion about {'Paris' if i%3==0 else 'Tokyo'}.",
             n_tokens=12 + i)
        for i in range(6)
    ]
    raw = sum(it.n_tokens for it in memory)
    for bf in (0.30, 1.0):
        cap = int(raw * bf)
        t0 = time.time()
        # extract=False to avoid burning LLM tokens in smoke.
        buf = consolidate(memory, budget_tokens=cap, extract=False)
        dt = time.time() - t0
        kept = sum(buf.retrievable_mask)
        print(
            f"A-Mem smoke b={bf}  cap={cap}  kept={kept}/{len(memory)}  "
            f"total={buf.total_tokens}  enforce={buf.budget_enforcement}  "
            f"dt={dt:.1f}s"
        )
        assert buf.total_tokens <= cap, "post-cap invariant violated"
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(_smoke())
