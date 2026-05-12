"""Build LongMemEval-shaped items for CalLB / TTMG eval on PerLTQA and QAConv.

PerLTQA: one synthetic session per question = protagonist memory (description +
structured profile + event summaries). QAConv: one session = segment dialogue
turns from ``article_segment.json`` (``seg_dialog``).
"""

from __future__ import annotations

import json
import os
import random
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

DEFAULT_DATASET_ROOT = Path(
    os.environ.get(
        "DATASET_PROJECT_ROOT",
        "/home/workspace/lww/project0412/projects/dataset",
    )
)


def _chunk_text(text: str, *, max_chunk: int = 2800) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chunk:
        return [text]
    chunks: List[str] = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + max_chunk])
        i += max_chunk
    return chunks


def _perltqa_memory_blob(name: str, mem_entry: Dict[str, Any]) -> str:
    parts: List[str] = []
    pd = mem_entry.get("profile_description")
    if isinstance(pd, str) and pd.strip():
        parts.append(pd.strip())
    prof = mem_entry.get("profile")
    if isinstance(prof, dict) and prof:
        lines = [f"- {k}: {v}" for k, v in prof.items()]
        parts.append("Structured profile:\n" + "\n".join(lines))
    events = mem_entry.get("events") or {}
    if isinstance(events, dict) and events:
        ev_lines: List[str] = []
        for e in list(events.values())[:48]:
            if not isinstance(e, dict):
                continue
            summ = (e.get("summary") or "").strip()
            body = (e.get("content") or "")[:900].strip()
            if summ or body:
                ev_lines.append(f"- {summ}\n  {body}")
        if ev_lines:
            parts.append("Events and episodes:\n" + "\n".join(ev_lines))
    blob = "\n\n".join(parts)
    return blob[:50000]


def _turns_from_memory_blob(blob: str) -> List[Dict[str, str]]:
    turns: List[Dict[str, str]] = []
    for ci, chunk in enumerate(_chunk_text(blob)):
        turns.append(
            {
                "role": "user",
                "content": f"[Memory segment {ci + 1}]\n{chunk}",
            }
        )
    if not turns:
        turns.append({"role": "user", "content": "(empty memory)"})
    return turns


def iter_perltqa_items(
    mem: Dict[str, Any],
    qa_blocks: List[Dict[str, Any]],
    *,
    limit: Optional[int] = None,
    seed: int = 0,
) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """Yield (question_id, lme_shaped_item) for each QA in PerLTQA en layout."""
    flat: List[Tuple[str, str, str, str]] = []
    # (qid, protagonist, question, gold)
    for bi, block in enumerate(qa_blocks):
        if not isinstance(block, dict):
            continue
        for name, body in block.items():
            prof = (body or {}).get("profile") or []
            if not isinstance(prof, list):
                continue
            for qi, qa in enumerate(prof):
                if not isinstance(qa, dict):
                    continue
                q = (qa.get("Question") or "").strip()
                a = (qa.get("Answer") or "").strip()
                if not q or not a:
                    continue
                qid = f"perltqa:{name}:{bi}:{qi}"
                flat.append((qid, name, q, a))
    rng = random.Random(seed)
    rng.shuffle(flat)
    if limit is not None and limit < len(flat):
        flat = flat[:limit]

    for qid, name, question, gold in flat:
        mem_entry = mem.get(name)
        if not isinstance(mem_entry, dict):
            continue
        blob = _perltqa_memory_blob(name, mem_entry)
        turns = _turns_from_memory_blob(blob)
        item = {
            "question_id": qid,
            "question_type": "perltqa",
            "question": question,
            "answer": gold,
            "question_date": None,
            "haystack_session_ids": ["mem_session"],
            "haystack_dates": [""],
            "haystack_sessions": [turns],
        }
        yield qid, item


def load_perltqa_pair(
    *,
    dataset_root: Optional[Path] = None,
    lang: str = "en",
    use_updated_en: bool = True,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Load (mem dict, qa list) from local PerLTQA JSON (no Hub)."""
    root = Path(dataset_root) if dataset_root else DEFAULT_DATASET_ROOT
    ckpt = root / "load_dataset_ckpt.py"
    perltqa_dataset_dir = root / "PerLTQA" / "Dataset"
    if ckpt.is_file():
        import sys

        dr = str(root)
        if dr not in sys.path:
            sys.path.insert(0, dr)
        from load_dataset_ckpt import load_perltqa_from_local  # type: ignore

        mem, qa_obj = load_perltqa_from_local(
            lang=lang,
            use_updated_en=use_updated_en,
            dataset_dir=str(perltqa_dataset_dir) if perltqa_dataset_dir.is_dir() else None,
        )
    else:
        base = perltqa_dataset_dir if perltqa_dataset_dir.is_dir() else root / "PerLTQA" / "Dataset"
        if lang.lower() == "zh":
            mem_p, qa_p = base / "zh" / "perltmem.json", base / "zh" / "perltqa.json"
        elif use_updated_en:
            mem_p = base / "en_v2" / "perltmem_en_v2.json"
            qa_p = base / "en_v2" / "perltqa_en_v2.json"
        else:
            mem_p = base / "en" / "perltmem_en.json"
            qa_p = base / "en" / "perltqa_en.json"
        with mem_p.open(encoding="utf-8") as f:
            mem = json.load(f)
        with qa_p.open(encoding="utf-8") as f:
            qa_obj = json.load(f)
    if not isinstance(mem, dict):
        raise ValueError("PerLTQA mem JSON must be a dict at top level")
    if not isinstance(qa_obj, list):
        raise ValueError("PerLTQA qa JSON must be a list")
    return mem, qa_obj


def load_qaconv_segment_map(
    *,
    dataset_root: Optional[Path] = None,
) -> Dict[str, Any]:
    root = Path(dataset_root) if dataset_root else DEFAULT_DATASET_ROOT
    seg_path = root / "QAConv" / "QAConv-V1.1" / "article_segment.json"
    if not seg_path.is_file():
        raise FileNotFoundError(f"QAConv segments not found: {seg_path}")
    with seg_path.open(encoding="utf-8") as f:
        return json.load(f)


def _qaconv_split_path(split: str, dataset_root: Path) -> Path:
    split_l = split.lower().strip()
    name = {"train": "trn", "trn": "trn", "validation": "val", "val": "val", "test": "tst", "tst": "tst"}.get(
        split_l, split_l
    )
    if name not in ("trn", "val", "tst"):
        raise ValueError(f"Unknown QAConv split {split!r}; use train/validation/test")
    return dataset_root / "QAConv" / "QAConv-V1.1" / f"{name}.json"


def iter_qaconv_items(
    rows: List[Dict[str, Any]],
    seg_map: Dict[str, Any],
    *,
    limit: Optional[int] = None,
    seed: int = 0,
) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """Yield (question_id, item) for QAConv rows that resolve to a segment."""
    idxs = list(range(len(rows)))
    rng = random.Random(seed)
    rng.shuffle(idxs)
    if limit is not None:
        idxs = idxs[:limit]

    for ii in idxs:
        row = rows[ii]
        if not isinstance(row, dict):
            continue
        sid = row.get("article_segment_id") or row.get("segment_id")
        if not sid:
            continue
        seg = seg_map.get(str(sid))
        if not isinstance(seg, dict):
            continue
        dialog = seg.get("seg_dialog")
        if not isinstance(dialog, list) or not dialog:
            continue
        turns: List[Dict[str, str]] = []
        for t in dialog:
            if not isinstance(t, dict):
                continue
            sp = re.sub(r"\s+", " ", str(t.get("speaker") or "user")).strip()
            tx = str(t.get("text") or "").strip()
            if not tx:
                continue
            turns.append({"role": sp[:120], "content": tx})
        if not turns:
            continue
        q = str(row.get("question") or "").strip()
        ans = row.get("answers")
        if isinstance(ans, list) and ans:
            gold = str(ans[0]).strip()
        else:
            gold = str(ans or "").strip()
        if not q or not gold:
            continue
        qid = str(row.get("id") or f"qaconv:{ii}")
        item = {
            "question_id": qid,
            "question_type": "qaconv",
            "question": q,
            "answer": gold,
            "question_date": None,
            "haystack_session_ids": [str(sid)],
            "haystack_dates": [""],
            "haystack_sessions": [turns],
        }
        yield qid, item


def load_qaconv_rows(
    split: str = "test",
    *,
    dataset_root: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    root = Path(dataset_root) if dataset_root else DEFAULT_DATASET_ROOT
    path = _qaconv_split_path(split, root)
    if not path.is_file():
        raise FileNotFoundError(f"QAConv split file missing: {path}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}")
    return data
