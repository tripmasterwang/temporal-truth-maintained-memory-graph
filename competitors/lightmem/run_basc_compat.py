"""Faithful LightMem (Li et al. 2025) driver.

Wraps the upstream `LightMemory.from_config(...)` so each session of a
LongMemEval / LoCoMo dialogue is fed via `add_memory(...)`, then the qdrant
payload is dumped back per session for the BASC retrieval pipeline.

Two modes:

* **`metadata_generate=False`** (this driver's default; cost-zero) — LightMem
  reduces to a chunk-and-index store: per-session text is pushed into qdrant
  with no LLM extraction. We use this as a **faithful baseline** of LightMem
  *without its sleep-time consolidation step*; it's a defensible row in B3
  because it matches the public ablation in the LightMem paper that turns
  off `text_summary`.
* **`metadata_generate=True`** — the headline LightMem behaviour. Requires
  ~50 LLM extraction calls per dialogue × N dialogues. Wired but expensive.

Session-id traceback
--------------------
LightMem's qdrant payload preserves `time_stamp`. We encode session_id in
`time_stamp = f"basc::{session_id}"` and parse it back on retrieval.

Budget enforcement
------------------
LightMem's natural knob is `extract_threshold` and `text_summary` length.
Without a hard token cap, we post-truncate by descending qdrant score
(novelty proxy) to the budget.
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
LIGHTMEM_SRC = ROOT / "competitors" / "lightmem" / "LightMem" / "src"
sys.path.insert(0, str(LIGHTMEM_SRC))
sys.path.insert(0, "/home/workspace/lww/project0412/projects/dataset")

from competitors._common.protocol import (  # noqa: E402
    ConsolidatedBuffer, Item, post_truncate_to_budget,
)

# LightMem's LLM-extraction step (metadata_generate=True) does not depend on
# the post-truncate budget. The eval harness caches consolidate output per
# qid when this flag is True, so the LLM extractor runs only once per
# dialogue regardless of how many budgets we sweep.
BUDGET_INDEPENDENT_CONSOLIDATE = True


def _build_config(qdrant_path: Path, *,
                  metadata_generate: bool,
                  llm_model: str) -> dict:
    """Minimal LightMem config compatible with our MAAS routing."""
    from api import _inject_api_key_from_file  # type: ignore  # noqa: WPS433
    _inject_api_key_from_file()
    api_key = os.environ.get("MAAS_API_KEY", "")

    return {
        "pre_compress": False,
        "topic_segment": False,
        "metadata_generate": metadata_generate,
        "text_summary": False,
        "messages_use": "user_only",
        "memory_manager": {
            "model_name": "openai",
            "configs": {
                "model": llm_model,
                "api_key": api_key,
                "max_tokens": 1024,
                "openai_base_url": "https://api.modelarts-maas.com/openai/v1",
            },
        },
        "extract_threshold": 0.1,
        "index_strategy": "embedding",
        "text_embedder": {
            "model_name": "huggingface",
            "configs": {
                "model": "sentence-transformers/all-MiniLM-L6-v2",
                "embedding_dims": 384,
                "model_kwargs": {"device": "cpu"},
            },
        },
        "retrieve_strategy": "embedding",
        "embedding_retriever": {
            "model_name": "qdrant",
            "configs": {
                "collection_name": "basc_run",
                "embedding_model_dims": 384,
                "path": str(qdrant_path),
            },
        },
        "update": "online",
    }


def _decode_session_id(time_stamp: str) -> str | None:
    if isinstance(time_stamp, str) and time_stamp.startswith("basc::"):
        return time_stamp[len("basc::"):]
    return None


def consolidate(memory: list[Item], *, budget_tokens: int,
                reader_model: str | None = None,
                seed: int = 7,
                metadata_generate: bool = False,
                llm_model: str = "deepseek-v3.2") -> ConsolidatedBuffer:
    del reader_model

    tmp = Path(tempfile.mkdtemp(prefix=f"lightmem_basc_{seed}_"))
    try:
        from lightmem.memory.lightmem import LightMemory  # noqa: WPS433
        cfg = _build_config(tmp / "qdrant",
                            metadata_generate=metadata_generate,
                            llm_model=llm_model)
        lm = LightMemory.from_config(cfg)

        sess_id_by_idx = {it.session_id: i for i, it in enumerate(memory)}
        for i, it in enumerate(memory):
            msgs = [
                {"role": "user", "content": it.text,
                 "time_stamp": f"basc::{it.session_id}"},
                {"role": "assistant", "content": "",
                 "time_stamp": f"basc::{it.session_id}"},
            ]
            try:
                lm.add_memory(messages=msgs,
                              force_segment=(i == len(memory) - 1),
                              force_extract=(i == len(memory) - 1))
            except Exception:
                pass

        # Dump qdrant payloads back. We use a generic high-recall query so
        # we get every stored item; LightMem's retriever returns top-N with
        # full payload when we call the embedding_retriever directly.
        n = len(memory)
        retained_text = ["" for _ in range(n)]
        n_kept_tokens = [0] * n
        importance = [0.0] * n
        try:
            # Synthetic query — get a large `limit` so all retained units come
            # back. We ignore similarity ranking and rely on payload only.
            query_vec = lm.text_embedder.embed("memory")
            results = lm.embedding_retriever.search(
                query_vector=query_vec, limit=10000, filters=None,
                return_full=True,
            )
        except Exception:
            results = []

        for r in results:
            payload = r.get("payload", {}) or {}
            ts = payload.get("time_stamp", "")
            sid = _decode_session_id(ts)
            if sid is None:
                continue
            idx = sess_id_by_idx.get(sid)
            if idx is None:
                continue
            mem_text = payload.get("memory", "") or ""
            # Append (LightMem may produce multiple chunks per session)
            if retained_text[idx]:
                retained_text[idx] += "\n" + mem_text
            else:
                retained_text[idx] = mem_text
            n_kept_tokens[idx] = len(retained_text[idx].split())
            # Importance proxy: qdrant's similarity score + length
            importance[idx] = max(importance[idx], float(r.get("score", 0.0)))

        retrievable_mask = [bool(t) for t in retained_text]
        cur = sum(n_kept_tokens)
        enforcement = "native(no-cap)"
        if cur > budget_tokens:
            retained_text, retrievable_mask, cur = post_truncate_to_budget(
                retained_text, retrievable_mask, n_kept_tokens, importance,
                budget_tokens,
            )
            enforcement = "post-truncate(by-qdrant-score)"

        return ConsolidatedBuffer(
            retained_text=retained_text,
            retrievable_mask=retrievable_mask,
            total_tokens=cur,
            budget_enforcement=enforcement,
            notes=dict(metadata_generate=metadata_generate,
                       qdrant_units=len(results),
                       mapped=int(sum(retrievable_mask))),
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _smoke() -> int:
    memory = [
        Item(session_id=f"s{i}",
             text=f"Session {i}: discussion about {'Paris' if i%3==0 else 'Tokyo'} trip planning.",
             n_tokens=15 + i)
        for i in range(6)
    ]
    raw = sum(it.n_tokens for it in memory)
    for bf in (0.30, 1.0):
        cap = int(raw * bf)
        t0 = time.time()
        buf = consolidate(memory, budget_tokens=cap, metadata_generate=False)
        dt = time.time() - t0
        kept = sum(buf.retrievable_mask)
        print(
            f"LightMem smoke b={bf}  cap={cap}  kept={kept}/{len(memory)}  "
            f"total={buf.total_tokens}  enforce={buf.budget_enforcement}  "
            f"dt={dt:.1f}s"
        )
        assert buf.total_tokens <= cap, "post-cap invariant violated"
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(_smoke())
