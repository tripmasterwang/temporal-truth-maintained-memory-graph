"""R003 — LightMem env smoke.

Goal: verify LightMem (Li et al. 2025) instantiates and runs end-to-end on
a single session without requiring the llmlingua-2 model. We use:

* `pre_compress: False`  (skips llmlingua)
* `topic_segment: False` (also skips llmlingua-based segmenter)
* `metadata_generate: False`  (skips LLM-extraction LLM call → fast smoke)
* huggingface all-MiniLM-L6-v2 embedder (already cached in HF hub cache)
* qdrant local file store under cache/qdrant_smoke/
* memory_manager openai-compatible pointed at MAAS (stored but unused
  during this smoke since metadata_generate=False)

This is intentionally a "shell" smoke — it confirms the dependency chain
works, the qdrant store creates, embeddings flow, and `retrieve` returns
something. The full faithful run (R007) will flip metadata_generate=True.
"""
from __future__ import annotations

import os
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIGHTMEM_SRC = ROOT / "competitors" / "lightmem" / "LightMem" / "src"
sys.path.insert(0, str(LIGHTMEM_SRC))
sys.path.insert(0, "/home/workspace/lww/project0412/projects/dataset")

# Make MAAS API key visible if LightMem hits the LLM (it shouldn't in this smoke)
from api import _inject_api_key_from_file  # type: ignore  # noqa: E402
_inject_api_key_from_file()
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("MAAS_API_KEY", ""))
os.environ.setdefault("OPENAI_BASE_URL", "https://api.modelarts-maas.com/openai/v1")

QDRANT_DIR = ROOT / "cache" / "qdrant_lightmem_smoke"
if QDRANT_DIR.exists():
    shutil.rmtree(QDRANT_DIR)
QDRANT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    from lightmem.memory.lightmem import LightMemory  # noqa: WPS433

    config = {
        "pre_compress": False,
        "topic_segment": False,
        "metadata_generate": False,
        "text_summary": False,
        "messages_use": "user_only",
        "memory_manager": {
            "model_name": "openai",
            "configs": {
                "model": "deepseek-v3.2",
                "api_key": os.environ["MAAS_API_KEY"],
                "max_tokens": 1024,
                "openai_base_url": os.environ["OPENAI_BASE_URL"],
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
                "collection_name": "smoke",
                "embedding_model_dims": 384,
                "path": str(QDRANT_DIR),
            },
        },
        "update": "online",
    }
    print("Instantiating LightMemory...")
    lm = LightMemory.from_config(config)
    print("OK — class:", type(lm).__name__)
    print("methods:", [m for m in ("add_memory", "retrieve", "summarize") if hasattr(lm, m)])

    # Single-turn add — mimic LightMem's experiments/longmemeval driver shape.
    msgs = [
        {"role": "user", "content": "I went to Paris last summer.", "time_stamp": "2025-01-01"},
        {"role": "assistant", "content": "Paris is lovely.", "time_stamp": "2025-01-01"},
    ]
    print("\nadd_memory(...) on a 1-turn message...")
    try:
        out = lm.add_memory(messages=msgs, force_segment=True, force_extract=True)
        print("add_memory OK — result keys:", list(out.keys()) if isinstance(out, dict) else type(out).__name__)
    except Exception as e:
        print("add_memory FAIL:", type(e).__name__, str(e)[:300])
        return 1

    # Retrieve
    print("\nretrieve('Where did I go?', limit=5)...")
    try:
        r = lm.retrieve("Where did I go?", limit=5)
        print("retrieve OK — result type:", type(r).__name__)
        if isinstance(r, str):
            print("len:", len(r))
            print("head:", r[:200])
        else:
            print("repr:", repr(r)[:200])
    except Exception as e:
        print("retrieve FAIL:", type(e).__name__, str(e)[:300])
        return 1

    print("\nLightMem smoke PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
