"""R-memoryos env smoke.

Verifies MemoryOS (memoryos-pypi flavour) instantiates against MAAS-routed
OpenAI-compatible endpoint and ingests a single QA pair without crashing.
Does NOT call get_response (would burn LLM tokens); just exercises
add_memory + retriever.retrieve_context.
"""
from __future__ import annotations

import os
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# memoryos-pypi uses relative imports; add its **parent** so it resolves as
# a package, then alias the unhyphenated name.
MEMOS_BASE = ROOT / "competitors" / "memoryos" / "MemoryOS"
sys.path.insert(0, str(MEMOS_BASE))
import importlib  # noqa: E402
_pkg = importlib.import_module("memoryos-pypi")  # type: ignore  # hyphen
sys.modules.setdefault("memoryos", _pkg)
sys.path.insert(0, "/home/workspace/lww/project0412/projects/dataset")

# Inject MAAS API key
from api import _inject_api_key_from_file  # type: ignore  # noqa: E402
_inject_api_key_from_file()
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("MAAS_API_KEY", ""))

DATA_DIR = ROOT / "cache" / "memoryos_smoke"
if DATA_DIR.exists():
    shutil.rmtree(DATA_DIR)
DATA_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    from memoryos import Memoryos  # noqa: WPS433

    print("Instantiating Memoryos...")
    mos = Memoryos(
        user_id="smoke_user",
        openai_api_key=os.environ["MAAS_API_KEY"],
        openai_base_url="https://api.modelarts-maas.com/openai/v1",
        data_storage_path=str(DATA_DIR),
        llm_model="deepseek-v3.2",
        embedding_model_name="all-MiniLM-L6-v2",
        short_term_capacity=4,
        mid_term_capacity=20,
        long_term_knowledge_capacity=10,
    )
    print("OK — class:", type(mos).__name__)

    print("\nadd_memory pair 1...")
    mos.add_memory(
        user_input="I'm planning a trip to Paris in July.",
        agent_response="Sounds great! Let me know if you want recommendations.",
        timestamp="2025-01-01 10:00",
    )
    print("\nadd_memory pair 2...")
    mos.add_memory(
        user_input="My birthday is March 12.",
        agent_response="Noted, March 12.",
        timestamp="2025-01-02 11:00",
    )

    print("\nretrieve via retriever.retrieve_context (no LLM)...")
    res = mos.retriever.retrieve_context(
        user_query="When is the user's birthday?",
        user_id=mos.user_id,
    )
    pages = res.get("retrieved_pages", [])
    knowledge = res.get("retrieved_user_knowledge", [])
    print(f"retrieved_pages={len(pages)}  retrieved_user_knowledge={len(knowledge)}")
    if pages:
        print("first page keys:", list(pages[0].keys())[:8])
    print("\nMemoryOS smoke PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
