"""R-amem env smoke.

Verifies A-Mem (`A-mem-sys`) instantiates and `add_note` works without
hitting the LLM-extraction pathway during the smoke. We keep llm calls
to a minimum by adding only one note and skipping `consolidate_memories`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "competitors" / "amem" / "A-mem-sys"))
sys.path.insert(0, "/home/workspace/lww/project0412/projects/dataset")

from api import _inject_api_key_from_file  # type: ignore  # noqa: E402
_inject_api_key_from_file()
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("MAAS_API_KEY", ""))
# A-Mem uses LiteLLM under the hood; OPENAI_BASE_URL is the standard knob.
os.environ.setdefault("OPENAI_BASE_URL",
                      "https://api.modelarts-maas.com/openai/v1")


def main() -> int:
    from agentic_memory.memory_system import AgenticMemorySystem  # noqa: WPS433

    print("Instantiating AgenticMemorySystem...")
    sys_ = AgenticMemorySystem(
        model_name="all-MiniLM-L6-v2",
        llm_backend="openai",
        llm_model="deepseek-v3.2",
        evo_threshold=1000000,  # disable evolution to avoid LLM calls
        api_key=os.environ["MAAS_API_KEY"],
    )
    print("OK — class:", type(sys_).__name__)

    print("\nadd_note (one short note)...")
    note_id = sys_.add_note(
        content="The user's birthday is March 12.",
    )
    print("note_id:", note_id)

    print("\nsearch...")
    res = sys_.search("when is the user's birthday?", k=5)
    print("results count:", len(res) if res else 0)
    if res:
        first = res[0]
        print("first repr (truncated):", str(first)[:200])

    print("\nA-Mem smoke PASS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
