"""Faithful mem0 (Chhikara et al. 2025) driver.

Wraps mem0ai's `Memory` so each LongMemEval / LoCoMo dialogue is ingested
end-to-end through their store and the post-write memory units map cleanly
back to source session ids.

Two modes (paper §4 reports both):

* **Extracted (`infer=True`)** — mem0's headline behaviour: per-session LLM
  fact extraction + dedup. Uses MAAS via OpenAI-compatible LLM config.
  Higher fidelity to the paper but ≈ 1 LLM call per session.
* **Stored-as-is (`infer=False`)** — fast smoke / cost-free baseline. Stores
  the raw session text and indexes it. Useful as a sanity floor.

Budget enforcement
------------------
mem0 does not natively cap retained tokens. After ingestion we dump
`memory.get_all(filters={"user_id": qid})`, sort retained units by descending
relevance to the dialogue centroid (training-free proxy for "important"),
and post_truncate_to_budget by ascending score until total tokens fit.

Session-id traceback
--------------------
Each `Memory.add(...)` call passes `metadata={"session_id": <sid>}`; mem0
preserves metadata through search/get_all results, so we can map every
retained unit back to its source session and update `retained_text` /
`retrievable_mask` parallel to the input `memory: list[Item]`.

Cost
----
At `infer=True`: ~50 LLM calls per dialogue × 500 dialogues ≈ 25k calls per
seed; matches the plan's M2 token budget.
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
sys.path.insert(0, str(ROOT / "competitors" / "mem0" / "mem0"))
sys.path.insert(0, "/home/workspace/lww/project0412/projects/dataset")

from competitors._common.protocol import (  # noqa: E402
    ConsolidatedBuffer, Item, post_truncate_to_budget,
)

# mem0's expensive step (LLM fact extraction during add()) does not depend
# on `budget_tokens`; only the final post_truncate does. The eval harness
# caches consolidate output per qid when this flag is True, so we run the
# LLM only once per dialogue regardless of how many budgets we sweep.
BUDGET_INDEPENDENT_CONSOLIDATE = True


def _build_memory(qdrant_path: Path, infer: bool, llm_model: str | None):
    """Construct a mem0 Memory with our embedder and (optionally) MAAS LLM."""
    # mem0 instantiates an LLM client at construction time even when we plan
    # to use infer=False. Make sure MAAS creds are visible as the default
    # OpenAI env vars.
    from api import _inject_api_key_from_file  # type: ignore  # noqa: WPS433
    _inject_api_key_from_file()
    os.environ.setdefault("OPENAI_API_KEY", os.environ.get("MAAS_API_KEY", ""))
    os.environ.setdefault("OPENAI_BASE_URL",
                          "https://api.modelarts-maas.com/openai/v1")

    from mem0 import Memory  # noqa: WPS433
    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "basc_run",
                "embedding_model_dims": 384,
                "path": str(qdrant_path),
            },
        },
        "embedder": {
            "provider": "huggingface",
            "config": {
                "model": "sentence-transformers/all-MiniLM-L6-v2",
                "embedding_dims": 384,
            },
        },
    }
    if infer and llm_model:
        # MAAS via OpenAI-compatible. mem0 will use this for fact extraction.
        config["llm"] = {
            "provider": "openai",
            "config": {
                "model": llm_model,
                "openai_base_url": "https://api.modelarts-maas.com/openai/v1",
                "api_key": os.environ.get(
                    "MAAS_API_KEY",
                    os.environ.get("OPENAI_API_KEY", ""),
                ),
                "max_tokens": 2000,
                "temperature": 0.0,
            },
        }
    return Memory.from_config(config)


def consolidate(memory: list[Item], *, budget_tokens: int,
                reader_model: str | None = None,
                seed: int = 7,
                infer: bool = False,
                llm_model: str | None = "deepseek-v3.2") -> ConsolidatedBuffer:
    """Run mem0 over `memory` and return a ConsolidatedBuffer.

    The default `infer=False` is the cost-free path — useful for the smoke /
    sanity row. For the paper's faithful row use `infer=True` and route LLM
    calls through MAAS via `llm_model`.
    """
    del reader_model

    # Each dialogue gets its own throwaway qdrant path so collections can't
    # leak across calls. Cleaned up at the end of consolidate().
    tmp = Path(tempfile.mkdtemp(prefix=f"mem0_basc_{seed}_"))
    try:
        m = _build_memory(tmp / "qdrant", infer=infer, llm_model=llm_model)

        # Use a deterministic per-call user_id so all sessions share the same
        # mem0 namespace.
        user_id = f"basc_seed{seed}"

        # Track which mem0 memory_ids came from which session_id.
        sess_id_by_idx = {it.session_id: i for i, it in enumerate(memory)}
        added_units: list[dict] = []

        n_failed_adds = 0
        for i, it in enumerate(memory):
            try:
                m.add(
                    messages=it.text,
                    user_id=user_id,
                    metadata={"session_id": it.session_id, "session_idx": i},
                    infer=infer,
                )
            except Exception:
                n_failed_adds += 1

        # mem0's add() return drops metadata; query the store to recover it.
        try:
            all_out = m.get_all(filters={"user_id": user_id})
            if isinstance(all_out, dict):
                added_units = list(all_out.get("results", []))
            elif isinstance(all_out, list):
                added_units = list(all_out)
        except Exception as e:
            # Best-effort fallback: mark every input session as "kept raw".
            added_units = [
                {"id": f"fallback-{i}", "memory": it.text,
                 "metadata": {"session_id": it.session_id, "session_idx": i,
                              "fallback": True}}
                for i, it in enumerate(memory)
            ]
            n_failed_adds += 1

        # Map memory units back to per-session retained_text. Multiple units
        # can come from the same session; we concatenate them so one slot in
        # `retained_text` collects all the facts mem0 extracted for that
        # session.
        retained_per_idx: dict[int, list[str]] = {}
        for u in added_units:
            md = u.get("metadata", {}) or {}
            sidx = md.get("session_idx")
            if sidx is None:
                # Try resolving by session_id if mem0 stripped session_idx.
                sid = md.get("session_id")
                sidx = sess_id_by_idx.get(sid)
            if sidx is None:
                continue
            retained_per_idx.setdefault(int(sidx), []).append(u.get("memory", ""))

        n = len(memory)
        retained_text = [
            "\n".join(retained_per_idx.get(i, [])) for i in range(n)
        ]
        n_kept_tokens = [len(t.split()) for t in retained_text]
        retrievable_mask = [bool(t.strip()) for t in retained_text]

        # Importance proxy = retained-fact length ratio
        importance = [
            n_kept_tokens[i] / max(1, memory[i].n_tokens) for i in range(n)
        ]

        # Enforce token budget.
        cur = sum(n_kept_tokens)
        enforcement = "native(no-cap)"
        if cur > budget_tokens:
            retained_text, retrievable_mask, cur = post_truncate_to_budget(
                retained_text, retrievable_mask, n_kept_tokens, importance,
                budget_tokens,
            )
            enforcement = "post-truncate(by-importance)"

        return ConsolidatedBuffer(
            retained_text=retained_text,
            retrievable_mask=retrievable_mask,
            total_tokens=cur,
            budget_enforcement=enforcement,
            notes=dict(infer=infer, total_units=len(added_units),
                       failed_adds=n_failed_adds,
                       fallback=int(sum(1 for u in added_units
                                        if (u.get("metadata") or {}).get("fallback")))),
        )
    finally:
        # Don't leave qdrant directories behind — they'd accumulate fast on
        # 500-dialogue sweeps.
        shutil.rmtree(tmp, ignore_errors=True)


def _smoke() -> int:
    """Verify driver runs end-to-end on a small synthetic dialogue (no LLM)."""
    memory = [
        Item(session_id=f"s{i}",
             text=f"Session {i}: {'Paris ' if i % 3 == 0 else 'Tokyo '}{'birthday March 12' if i == 4 else ''} discussion.",
             n_tokens=12 + i)
        for i in range(8)
    ]
    raw = sum(it.n_tokens for it in memory)
    for bf in (0.10, 0.50, 1.0):
        cap = int(raw * bf)
        t0 = time.time()
        buf = consolidate(memory, budget_tokens=cap, infer=False)
        dt = time.time() - t0
        kept = sum(buf.retrievable_mask)
        print(
            f"mem0 smoke b={bf}  cap={cap}  kept={kept}/{len(memory)}  "
            f"total={buf.total_tokens}  enforce={buf.budget_enforcement}  "
            f"dt={dt:.1f}s"
        )
        assert buf.total_tokens <= cap, "post-cap invariant violated"
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(_smoke())
