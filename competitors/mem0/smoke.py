"""R-mem0 env smoke.

Verifies mem0 (mem0ai package) instantiates against MAAS-routed OpenAI-
compatible endpoint and ingests a few messages without crashing. Uses
`infer=False` to skip LLM extraction (no token spend during smoke).
"""
from __future__ import annotations

import os
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEM0_PKG = ROOT / "competitors" / "mem0" / "mem0"
sys.path.insert(0, str(MEM0_PKG))
sys.path.insert(0, "/home/workspace/lww/project0412/projects/dataset")

from api import _inject_api_key_from_file  # type: ignore  # noqa: E402
_inject_api_key_from_file()
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("MAAS_API_KEY", ""))
os.environ.setdefault("OPENAI_BASE_URL",
                      "https://api.modelarts-maas.com/openai/v1")

DATA_DIR = ROOT / "cache" / "mem0_smoke"
if DATA_DIR.exists():
    shutil.rmtree(DATA_DIR)
DATA_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    from mem0 import Memory  # noqa: WPS433

    # Local-only config: in-process qdrant under cache/, MAAS for embedder
    # not used because we use infer=False (stores raw text). Use a tiny
    # default config and let mem0 pick its in-process backend.
    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "smoke",
                "embedding_model_dims": 384,
                "path": str(DATA_DIR / "qdrant"),
            },
        },
        "embedder": {
            "provider": "huggingface",
            "config": {
                "model": "sentence-transformers/all-MiniLM-L6-v2",
                "embedding_dims": 384,
            },
        },
        # No LLM provider — we'll only call add(infer=False).
    }
    print("Instantiating mem0.Memory...")
    m = Memory.from_config(config)
    print("OK — class:", type(m).__name__)

    print("\nadd(infer=False) for two messages...")
    out1 = m.add(
        messages="I'm planning a trip to Paris in July.",
        user_id="smoke", infer=False,
        metadata={"session_id": "s001"},
    )
    print("add#1 result:", str(out1)[:120])
    out2 = m.add(
        messages="My birthday is March 12.",
        user_id="smoke", infer=False,
        metadata={"session_id": "s002"},
    )
    print("add#2 result:", str(out2)[:120])

    print("\nsearch...")
    res = m.search(query="When is the user's birthday?",
                   filters={"user_id": "smoke"})
    if isinstance(res, dict):
        items = res.get("results", [])
    else:
        items = res
    print(f"results: {len(items) if hasattr(items, '__len__') else 'n/a'}")
    if items:
        first = items[0] if isinstance(items, list) else next(iter(items.values()))
        print("first item keys:", list(first.keys()) if isinstance(first, dict) else type(first).__name__)

    print("\nmem0 smoke PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
