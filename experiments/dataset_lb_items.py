"""Ordered (qid, LME-shaped item) lists for domain CalLB: split, label, eval.

Stable sort by ``question_id`` before cal/test split (no shuffle inside item
construction). Split uses a seeded shuffle on the **question_id** set.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from experiments.eval_locomo import _answer_session_key, _locomo_sessions
from experiments.transfer_items import (
    _perltqa_memory_blob,
    _turns_from_memory_blob,
    load_perltqa_pair,
    load_qaconv_rows,
    load_qaconv_segment_map,
)


def list_perltqa_items_ordered(
    mem: Dict[str, Any], qa_blocks: List[Dict[str, Any]]
) -> List[Tuple[str, Dict[str, Any]]]:
    out: List[Tuple[str, Dict[str, Any]]] = []
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
                mem_entry = mem.get(name)
                if not isinstance(mem_entry, dict):
                    continue
                blob = _perltqa_memory_blob(name, mem_entry)
                turns = _turns_from_memory_blob(blob)
                item = {
                    "question_id": qid,
                    "question_type": "perltqa",
                    "question": q,
                    "answer": a,
                    "question_date": None,
                    "haystack_session_ids": ["mem_session"],
                    "haystack_dates": [""],
                    "haystack_sessions": [turns],
                }
                out.append((qid, item))
    out.sort(key=lambda x: x[0])
    return out


def list_qaconv_items_ordered(
    rows: List[Dict[str, Any]], seg_map: Dict[str, Any]
) -> List[Tuple[str, Dict[str, Any]]]:
    import re

    out: List[Tuple[str, Dict[str, Any]]] = []
    for ii, row in enumerate(rows):
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
        out.append((qid, item))
    out.sort(key=lambda x: x[0])
    return out


def list_locomo_ssu_items_ordered(
    convs: List[Dict[str, Any]],
    *,
    max_qa_per_conv: Optional[int] = None,
) -> List[Tuple[str, Dict[str, Any]]]:
    """One LME-shaped item per LoCoMo QA that is single-session resolvable."""
    out: List[Tuple[str, Dict[str, Any]]] = []
    gidx = 0
    for conv in convs:
        sample = str(conv.get("sample_id") or "unknown")
        sessions_dict = _locomo_sessions(conv)
        qas = conv.get("qa") or []
        if max_qa_per_conv is not None:
            qas = qas[:max_qa_per_conv]
        for qa in qas:
            sk = _answer_session_key(qa)
            if sk is None:
                continue
            sess_info = sessions_dict.get(sk)
            if sess_info is None:
                continue
            turns: List[Dict[str, str]] = []
            for t in sess_info.get("turns") or []:
                sp = str(t.get("speaker") or "user")
                tx = str(t.get("text") or "").strip()
                if tx:
                    turns.append({"role": sp, "content": tx})
            if not turns:
                continue
            q = (qa.get("question") or "").strip()
            gold = str(qa.get("answer") or "").strip()
            if not q or not gold:
                continue
            qid = f"locomo:{sample}:{sk}:{gidx}"
            gidx += 1
            item = {
                "question_id": qid,
                "question_type": "locomo_ssu",
                "question": q,
                "answer": gold,
                "question_date": None,
                "haystack_session_ids": [sk],
                "haystack_dates": [sess_info.get("session_ts") or ""],
                "haystack_sessions": [turns],
            }
            out.append((qid, item))
    out.sort(key=lambda x: x[0])
    return out


def split_cal_test_qids(
    qids: List[str], *, cal_frac: float, seed: int
) -> Tuple[Set[str], Set[str]]:
    u = sorted(set(qids))
    rng = random.Random(seed)
    rng.shuffle(u)
    n_cal = max(1, int(round(len(u) * cal_frac)))
    cal = set(u[:n_cal])
    test = set(u[n_cal:])
    return cal, test


def save_split(
    path: Path,
    *,
    dataset: str,
    cal_frac: float,
    seed: int,
    cal_qids: Set[str],
    test_qids: Set[str],
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset": dataset,
        "cal_frac": cal_frac,
        "seed": seed,
        "n_cal": len(cal_qids),
        "n_test": len(test_qids),
        "cal_qids": sorted(cal_qids),
        "test_qids": sorted(test_qids),
        "meta": meta or {},
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_split(path: Path) -> Tuple[Set[str], Set[str], Dict[str, Any]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    return set(obj["cal_qids"]), set(obj["test_qids"]), obj
