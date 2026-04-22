"""MAAS (ModelArts) OpenAI-compatible chat client wrapper for TTMG.

Reuses `/home/workspace/lww/project0412/projects/dataset/api.py` for auth and transport.
Provides two entry points used across TTMG modules:
  - `chat_json(prompt, schema, ...)`: returns parsed JSON (retries + fallback).
  - `chat_text(prompt, ...)`: returns raw text.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Sequence

_DATASET_DIR = "/home/workspace/lww/project0412/projects/dataset"
if _DATASET_DIR not in sys.path:
    sys.path.insert(0, _DATASET_DIR)

from api import chat as _chat  # type: ignore  # noqa: E402
from api import get_client as _get_client  # type: ignore  # noqa: E402

DEFAULT_MODEL = os.environ.get("TTMG_MODEL", "deepseek-v3.2")
DEFAULT_JUDGE_MODEL = os.environ.get("TTMG_JUDGE_MODEL", "deepseek-v3.2")
DEFAULT_SMALL_MODEL = os.environ.get("TTMG_SMALL_MODEL", "qwen3-30b-a3b")


def _extract_json_blob(text: str) -> Optional[str]:
    """Extract the first {...} or [...] JSON blob from an LLM reply."""
    if text is None:
        return None
    text = text.strip()
    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```\s*$", "", text)
    if text.startswith("{") or text.startswith("["):
        return text
    # Fall back to scanning for first balanced blob
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start < 0:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == opener:
                depth += 1
            elif text[i] == closer:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
    return None


def chat_text(
    prompt: str,
    *,
    system: str = "You are a helpful assistant.",
    model: Optional[str] = None,
    messages: Optional[Sequence[Dict[str, str]]] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    retries: int = 2,
) -> str:
    model = model or DEFAULT_MODEL
    kwargs: Dict[str, Any] = {"temperature": temperature}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    last_err: Optional[BaseException] = None
    for attempt in range(retries + 1):
        try:
            if messages is not None:
                return _chat(user="", messages=list(messages), model=model, **kwargs)
            return _chat(user=prompt, system=system, model=model, **kwargs)
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.0 + attempt * 1.5)
    raise RuntimeError(f"chat_text failed after {retries + 1} attempts: {last_err}")


def chat_json(
    prompt: str,
    *,
    default: Optional[Dict[str, Any]] = None,
    system: str = (
        "You respond ONLY with a single valid JSON object. "
        "Never include prose, never wrap in markdown fences."
    ),
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
    retries: int = 2,
) -> Dict[str, Any]:
    """Ask the LLM and return parsed JSON. Falls back to `default` on failure."""
    err: Optional[BaseException] = None
    for attempt in range(retries + 1):
        try:
            raw = chat_text(
                prompt,
                system=system,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                retries=0,
            )
            blob = _extract_json_blob(raw)
            if blob is None:
                raise ValueError("no JSON blob in reply")
            return json.loads(blob)
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(0.8 + attempt * 1.2)
    if default is not None:
        return dict(default)
    raise RuntimeError(f"chat_json failed after {retries + 1} attempts: {err}")


__all__ = [
    "chat_text",
    "chat_json",
    "DEFAULT_MODEL",
    "DEFAULT_JUDGE_MODEL",
    "DEFAULT_SMALL_MODEL",
]
