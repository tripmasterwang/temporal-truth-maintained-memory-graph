"""Faithful MemoryOS (BAI-LAB 2025) driver.

Wraps `memoryos-pypi`'s `Memoryos` class so each LongMemEval / LoCoMo
dialogue is fed via `add_memory(user_input, agent_response, timestamp)`.
We encode each input session's `session_id` into the `timestamp` field
(prefix `basc::<sid>::<turn_idx>`); after all turns are ingested, we walk
short_term + mid_term + long_term stores, parse back the session_id from
each retained page's timestamp, and assemble a per-input-session
`retained_text`.

Two modes (paper-relevant):
* **Default (extract on)** — MemoryOS's headline pipeline with `dream()`
  triggered by mid-term heat threshold; per-page summarisation + long-term
  knowledge extraction call DeepSeek-V3.2 via MAAS.
* **Lite (extract off, default for synthetic smoke)** — disable mid-term
  promotion by setting short_term_capacity huge, so all sessions stay raw
  in short-term; cost-zero baseline.

Budget enforcement
------------------
MemoryOS does not natively cap retained tokens. After ingestion we walk the
recovered (session_idx → text) map and `post_truncate_to_budget` by
descending mid-term page heat (`H_segment`) plus long-term knowledge length.

Reference: https://github.com/BAI-LAB/MemoryOS — paper arXiv:2506.06326.
"""
from __future__ import annotations

import importlib
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEMOS_BASE = ROOT / "competitors" / "memoryos" / "MemoryOS"
sys.path.insert(0, str(MEMOS_BASE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, "/home/workspace/lww/project0412/projects/dataset")

from competitors._common.protocol import (  # noqa: E402
    ConsolidatedBuffer, Item, post_truncate_to_budget,
)

BUDGET_INDEPENDENT_CONSOLIDATE = True


def _load_memoryos():
    """Hyphenated package name needs explicit importlib + alias."""
    spec = importlib.util.find_spec("memoryos-pypi")
    pkg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pkg)
    sys.modules["memoryos"] = pkg
    return pkg.Memoryos


def _split_dialogue(text: str) -> list[tuple[str, str]]:
    """Convert a raw multi-turn session text into [(user, assistant), ...]
    pairs, robustly handling LME-S 'user:' / 'assistant:' prefixes and
    LoCoMo 'speaker_a:' / 'speaker_b:' style.
    """
    pairs: list[tuple[str, str]] = []
    cur_role: str | None = None
    cur_text: list[str] = []
    chunks: list[tuple[str, str]] = []
    for line in text.splitlines():
        l = line.strip()
        if l.startswith("user:"):
            if cur_role:
                chunks.append((cur_role, " ".join(cur_text).strip()))
            cur_role = "u"; cur_text = [l[5:].strip()]
        elif l.startswith("assistant:"):
            if cur_role:
                chunks.append((cur_role, " ".join(cur_text).strip()))
            cur_role = "a"; cur_text = [l[10:].strip()]
        elif l.startswith("speaker_a:"):
            if cur_role:
                chunks.append((cur_role, " ".join(cur_text).strip()))
            cur_role = "u"; cur_text = [l[10:].strip()]
        elif l.startswith("speaker_b:"):
            if cur_role:
                chunks.append((cur_role, " ".join(cur_text).strip()))
            cur_role = "a"; cur_text = [l[10:].strip()]
        else:
            cur_text.append(l)
    if cur_role:
        chunks.append((cur_role, " ".join(cur_text).strip()))

    # Pair user→assistant runs.
    i = 0
    while i < len(chunks):
        if chunks[i][0] == "u":
            u_text = chunks[i][1]
            a_text = chunks[i + 1][1] if i + 1 < len(chunks) and chunks[i + 1][0] == "a" else ""
            pairs.append((u_text, a_text))
            i += 2 if a_text else 1
        else:
            pairs.append(("", chunks[i][1]))
            i += 1
    if not pairs:
        # Fallback: whole text as a single user-only pair.
        pairs = [(text[:8000], "")]
    return pairs


def _decode_sid(timestamp: str) -> tuple[str | None, int]:
    """Extract our session_id + turn_idx encoding."""
    if isinstance(timestamp, str) and timestamp.startswith("basc::"):
        parts = timestamp.split("::", 2)
        if len(parts) == 3:
            try:
                return parts[1], int(parts[2])
            except ValueError:
                return parts[1], 0
        return parts[1], 0
    return None, 0


def consolidate(memory: list[Item], *, budget_tokens: int,
                reader_model: str | None = None,
                seed: int = 7,
                extract: bool = True,
                llm_model: str = "deepseek-v3.2") -> ConsolidatedBuffer:
    del reader_model

    from api import _inject_api_key_from_file  # type: ignore  # noqa: WPS433
    _inject_api_key_from_file()
    os.environ.setdefault("OPENAI_API_KEY", os.environ.get("MAAS_API_KEY", ""))

    Memoryos = _load_memoryos()
    tmp = Path(tempfile.mkdtemp(prefix=f"memoryos_basc_{seed}_"))

    # Tune capacities so:
    #   - extract=True: mid-term promotion fires normally; dream() triggers
    #   - extract=False: short-term holds all turns (no promotion → no LLM)
    n_input_pairs = sum(max(1, len(_split_dialogue(it.text))) for it in memory)
    if extract:
        st_cap = 4
        mt_cap = max(64, n_input_pairs)  # plenty of headroom
        lt_cap = 64
    else:
        st_cap = max(64, n_input_pairs * 2)
        mt_cap = 0  # never promote
        lt_cap = 0

    try:
        mos = Memoryos(
            user_id=f"basc_seed{seed}",
            openai_api_key=os.environ["MAAS_API_KEY"],
            openai_base_url="https://api.modelarts-maas.com/openai/v1",
            data_storage_path=str(tmp),
            llm_model=llm_model,
            embedding_model_name="all-MiniLM-L6-v2",
            short_term_capacity=st_cap,
            mid_term_capacity=mt_cap if mt_cap > 0 else 1,
            long_term_knowledge_capacity=lt_cap if lt_cap > 0 else 1,
        )
    except Exception as e:
        # Defensive: if instantiation fails, return all-dropped buffer.
        return ConsolidatedBuffer(
            retained_text=["" for _ in memory],
            retrievable_mask=[False for _ in memory],
            total_tokens=0,
            budget_enforcement="instantiation-failed",
            notes=dict(error=str(e)[:200]),
        )

    # Ingest every (session, turn) → mos.add_memory with our timestamp encoding.
    for i, it in enumerate(memory):
        for t_idx, (u, a) in enumerate(_split_dialogue(it.text)):
            try:
                mos.add_memory(
                    user_input=u or "",
                    agent_response=a or "",
                    timestamp=f"basc::{it.session_id}::{t_idx}",
                )
            except Exception:
                pass

    # Walk all stores and recover (session_id → text snippets) provenance.
    sid_to_idx = {it.session_id: i for i, it in enumerate(memory)}
    n = len(memory)
    retained_per_idx: dict[int, list[str]] = {}
    importance: list[float] = [0.0] * n

    # Short-term raw QA pairs
    for qa in mos.short_term_memory.get_all():
        sid, _ = _decode_sid(qa.get("timestamp", ""))
        idx = sid_to_idx.get(sid)
        if idx is None:
            continue
        merged = f"{qa.get('user_input', '')} {qa.get('agent_response', '')}".strip()
        if merged:
            retained_per_idx.setdefault(idx, []).append(merged)
            importance[idx] = max(importance[idx], 0.5)

    # Mid-term sessions (compacted summaries + per-page details)
    try:
        for sess in mos.mid_term_memory.sessions.values():
            heat = float(sess.get("H_segment", 0.0)) or 0.5
            for page in sess.get("details", []):
                sid, _ = _decode_sid(page.get("timestamp", ""))
                idx = sid_to_idx.get(sid)
                if idx is None:
                    continue
                seg = f"{page.get('user_input', '')} {page.get('agent_response', '')}".strip()
                if seg:
                    retained_per_idx.setdefault(idx, []).append(seg)
                    importance[idx] = max(importance[idx], heat)
            # Each session also has a top-level summary; attach to all of its
            # source sessions for retrieval boost.
            summ = sess.get("summary", "")
            if summ:
                source_sids = {_decode_sid(p.get("timestamp", ""))[0]
                               for p in sess.get("details", [])}
                for sid in source_sids:
                    idx = sid_to_idx.get(sid)
                    if idx is not None:
                        retained_per_idx.setdefault(idx, []).append(f"[summary] {summ}")
    except Exception:
        pass

    # Long-term knowledge — does not preserve session_id provenance natively;
    # we attach each entry to the *most recent* session as a coarse proxy
    # so the retriever still has access to extracted knowledge.
    try:
        last_idx = n - 1
        for ent in mos.long_term_memory.get_user_knowledge():
            txt = ent.get("knowledge", "") if isinstance(ent, dict) else str(ent)
            if txt:
                retained_per_idx.setdefault(last_idx, []).append(f"[lt-user] {txt}")
        for ent in mos.long_term_memory.get_assistant_knowledge():
            txt = ent.get("knowledge", "") if isinstance(ent, dict) else str(ent)
            if txt:
                retained_per_idx.setdefault(last_idx, []).append(f"[lt-asst] {txt}")
    except Exception:
        pass

    retained_text = [" ".join(retained_per_idx.get(i, [])) for i in range(n)]
    n_kept_tokens = [len(t.split()) for t in retained_text]
    retrievable_mask = [bool(t.strip()) for t in retained_text]

    cur = sum(n_kept_tokens)
    enforcement = f"native({'extract' if extract else 'lite'})"
    if cur > budget_tokens:
        retained_text, retrievable_mask, cur = post_truncate_to_budget(
            retained_text, retrievable_mask, n_kept_tokens, importance,
            budget_tokens,
        )
        enforcement += "+post-truncate"

    # Cleanup tempdir.
    try:
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass

    return ConsolidatedBuffer(
        retained_text=retained_text,
        retrievable_mask=retrievable_mask,
        total_tokens=cur,
        budget_enforcement=enforcement,
        notes=dict(extract=extract, mapped=int(sum(retrievable_mask))),
    )


def _smoke() -> int:
    memory = [
        Item(session_id=f"s{i}",
             text=("user: I went to Paris. assistant: Lovely. " * 3
                   if i % 2 == 0 else
                   "user: birthday March 12. assistant: Noted. " * 2),
             n_tokens=80 + i * 10)
        for i in range(5)
    ]
    raw = sum(it.n_tokens for it in memory)
    for bf in (0.3, 1.0):
        cap = int(raw * bf)
        t0 = time.time()
        buf = consolidate(memory, budget_tokens=cap, extract=False)
        dt = time.time() - t0
        kept = sum(buf.retrievable_mask)
        print(f"MemoryOS smoke b={bf} cap={cap} kept={kept}/{len(memory)} "
              f"total={buf.total_tokens} enforce={buf.budget_enforcement} dt={dt:.1f}s")
        assert buf.total_tokens <= cap, "post-cap invariant violated"
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(_smoke())
