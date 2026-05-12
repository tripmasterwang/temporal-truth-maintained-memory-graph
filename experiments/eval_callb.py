"""CalLB evaluation on LongMemEval-S (and Memora) for all M1/M2 methods.

Methods:
  callb               — Full CalLB: 13-feat MLP + Clopper-Pearson CRC at α
  no_crc              — CalLB ablation: same MLP + fixed threshold (no conformal)
  ttmg                — Path D baseline (existing truth_retrieve reader)
  flat_hybrid         — Flat semantic+lexical+raw RRF, no claim graph (R009)
  prompt_only         — Path D retrieval + load-bearing reader prompt (R010)
  rerank_only         — CalLB MLP top-K + standard prompt, no CRC (R011)
  agreement_heuristic — Cross-substrate agreement rank + load-bearing prompt (R012)

Usage:
  python -m experiments.eval_callb \\
      --method callb \\
      --callb-model results/lb_mlp.json \\
      --callb-crc   results/lb_crc.json \\
      --callb-alpha 0.20 \\
      --limit 500 --seed 0 \\
      --out results/r005_callb_s0.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from sentence_transformers import SentenceTransformer

from ttmg import TTMGConfig, TTMGSystem
from ttmg.maas_client import DEFAULT_MODEL, chat_json, chat_text

LME_PATH = "/home/workspace/lww/project0412/projects/dataset/LongMemEval-main/data/longmemeval_s.json"


# ---------------------------------------------------------------------------
# Reader prompt variants
# ---------------------------------------------------------------------------

_STD_READER_SYS = (
    "You are a helpful assistant with access to long-term memory. "
    "Answer the user's question using the provided memory. "
    "Only say 'I do not know' if neither source contains the answer."
)

_LB_READER_SYS = (
    "You are a careful assistant. You have been given a small set of "
    "load-bearing memory facts — these are the claims directly relevant to "
    "the question. Answer ONLY from these facts. Do NOT infer, extrapolate, "
    "or add adjacent detail not explicitly stated. If the facts are insufficient, "
    "say 'I do not know'."
)

_STD_READER_TMPL = """\
Question: {question}

Relevant memory claims (ranked by relevance):
{claim_block}

{extra_context}

Answer concisely."""

_LB_READER_TMPL = """\
Question: {question}

Load-bearing memory facts (answer using ONLY these):
{claim_block}

{extra_context}

Answer concisely from the facts above only."""


# ---------------------------------------------------------------------------
# Judge (reuse LME-S paper-style)
# ---------------------------------------------------------------------------

_JUDGE_SYS = (
    "You are a strict grader. Decide whether the model answer correctly answers "
    "the question given the reference answer. Respond in JSON only."
)

_JUDGE_USER_TMPL = """\
Question: {question}
Reference answer: {gold}
Model answer: {pred}

For abstention questions (reference says the user did NOT mention something), \
correct iff model also abstains or says information is not present.

Grade:
- "correct": 0 or 1.
- "reason": short justification (<=20 words).

Return JSON: {{"correct": 0|1, "reason": "..."}}"""


def judge_answer(question: str, gold: str, pred: str) -> Tuple[int, str]:
    payload = chat_json(
        _JUDGE_USER_TMPL.format(question=question, gold=gold, pred=pred),
        system=_JUDGE_SYS,
        default={"correct": 0, "reason": "judge_failed"},
        temperature=0.0,
        max_tokens=120,
    )
    try:
        v = int(payload.get("correct", 0))
    except Exception:
        v = 0
    return (1 if v else 0), str(payload.get("reason", ""))[:200]


def token_f1(pred: str, gold: str) -> float:
    import re
    def tok(s: str) -> List[str]:
        return [w for w in re.findall(r"[A-Za-z0-9]+", s.lower()) if w]
    p, g = tok(pred), tok(gold)
    if not p and not g:
        return 1.0
    if not p or not g:
        return 0.0
    pc: Dict[str, int] = defaultdict(int)
    gc: Dict[str, int] = defaultdict(int)
    for w in p:
        pc[w] += 1
    for w in g:
        gc[w] += 1
    overlap = sum(min(pc[w], gc[w]) for w in pc if w in gc)
    if overlap == 0:
        return 0.0
    prec = overlap / len(p)
    rec = overlap / len(g)
    return 2 * prec * rec / (prec + rec)


# ---------------------------------------------------------------------------
# Dataset helpers
# ---------------------------------------------------------------------------

def load_dataset(
    path: str = LME_PATH,
    limit: Optional[int] = None,
    seed: int = 0,
    stratify: bool = True,
    question_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    with open(path) as fh:
        data = json.load(fh)
    if question_type:
        data = [d for d in data if d.get("question_type") == question_type]
    if limit is None or limit >= len(data):
        return data
    if not stratify or question_type:
        rng = random.Random(seed)
        rng.shuffle(data)
        return data[:limit]
    buckets: Dict[str, List] = defaultdict(list)
    for d in data:
        buckets[d["question_type"]].append(d)
    rng = random.Random(seed)
    for k in buckets:
        rng.shuffle(buckets[k])
    total = len(data)
    out: List[Dict[str, Any]] = []
    for qt, items in buckets.items():
        share = max(1, round(limit * len(items) / total))
        out.extend(items[:share])
    rng.shuffle(out)
    return out[:limit]


def _load_existing(out_path: Path) -> Dict[str, Any]:
    """Return dict qid -> row for resume."""
    seen: Dict[str, Any] = {}
    if not out_path.exists():
        return seen
    with open(out_path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                seen[r["question_id"]] = r
            except Exception:
                continue
    return seen


def _convert_sessions(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    sessions = []
    for sid, sts, sess in zip(
        item["haystack_session_ids"], item["haystack_dates"], item["haystack_sessions"]
    ):
        turns = []
        for turn in sess:
            if not isinstance(turn, dict):
                continue
            turns.append({"speaker": turn.get("role") or "user",
                          "text": turn.get("content") or ""})
        sessions.append({"session_id": sid, "session_ts": sts, "turns": turns})
    return sessions


# ---------------------------------------------------------------------------
# Per-question runners
# ---------------------------------------------------------------------------

def _format_claims(claims) -> str:
    lines = []
    for i, c in enumerate(claims, 1):
        vf = c.valid_from or "?"
        vt = c.valid_to or "open"
        status = "active" if c.active else "past"
        lines.append(f"[{i}] ({status}; valid {vf}..{vt}; polarity={c.polarity}) {c.content}")
    return "\n".join(lines) if lines else "(none)"


def _format_raw(turns: List[Dict]) -> str:
    if not turns:
        return "(none)"
    lines = []
    for i, t in enumerate(turns, 1):
        ts = t.get("session_ts") or "?"
        sp = t.get("speaker") or "?"
        text = (t.get("text") or "").strip().replace("\n", " ")
        lines.append(f"[{i}] ({ts}; {sp}) {text[:500]}")
    return "\n".join(lines)


def run_callb(
    item: Dict[str, Any],
    embed_model: SentenceTransformer,
    callb_model_path: str,
    callb_crc_path: str,
    callb_alpha: float,
    writer_model: str,
    reader_model: str,
) -> Dict[str, Any]:
    """Full CalLB: MLP + CRC threshold."""
    sessions = _convert_sessions(item)
    cfg = TTMGConfig(
        writer_model=writer_model,
        linker_model=writer_model,
        reader_model=reader_model,
        batch_writer_per_session=True,
        linker_min_similarity=0.55,
        linker_candidate_k=4,
        knn_k_read=8,
        top_keep=3,
        hard_threshold=0.7,
        raw_turn_fallback=True,
        enable_callb=True,
        callb_model_path=callb_model_path,
        callb_crc_path=callb_crc_path,
        callb_alpha=callb_alpha,
        callb_k_per_substrate=10,
        callb_max_candidates=30,
    )
    sys_obj = TTMGSystem(cfg, embed_model=embed_model)
    t_ing = time.time()
    sys_obj.ingest_conversation(sessions, verbose=False)
    t_ingest = time.time() - t_ing
    ts_q = item.get("question_date")
    t_ans = time.time()
    try:
        ans = sys_obj.answer(item["question"], ts_q=ts_q)
    except Exception as e:
        traceback.print_exc()
        ans = {"answer": f"(error: {e})", "abstain": False,
               "retrieve_time": 0.0, "reader_time": 0.0}
    t_answer = time.time() - t_ans
    return {
        "ingest_time": t_ingest, "answer_time": t_answer,
        "metrics": sys_obj.metrics,
        **ans,
    }


def run_no_crc(
    item: Dict[str, Any],
    embed_model: SentenceTransformer,
    callb_model_path: str,
    fixed_threshold: float,
    writer_model: str,
    reader_model: str,
) -> Dict[str, Any]:
    """CalLB MLP + fixed threshold (no conformal guarantee)."""
    from ttmg.lb_features import FEATURE_NAMES_FULL, extract_features
    from ttmg.lb_model import load as lb_load, score as lb_score
    from ttmg.lb_retrieval import gather_candidates

    sessions = _convert_sessions(item)
    cfg = TTMGConfig(
        writer_model=writer_model,
        linker_model=writer_model,
        reader_model=reader_model,
        batch_writer_per_session=True,
        linker_min_similarity=0.55,
        linker_candidate_k=4,
        knn_k_read=8,
        top_keep=3,
        hard_threshold=0.7,
        raw_turn_fallback=True,
    )
    sys_obj = TTMGSystem(cfg, embed_model=embed_model)
    t_ing = time.time()
    sys_obj.ingest_conversation(sessions, verbose=False)
    t_ingest = time.time() - t_ing

    model, feat_names = lb_load(callb_model_path)
    question = item["question"]
    ts_q = item.get("question_date")
    t_ans = time.time()
    try:
        cands = gather_candidates(question, sys_obj, k_per_substrate=10, max_candidates=30)
        if not cands:
            raise ValueError("no candidates")
        X = np.stack([
            extract_features(question, c, sys_obj.graph, ts_q=ts_q,
                             feature_names=tuple(feat_names))
            for c in cands
        ])
        s = lb_score(model, X)
        tier = [c for c, sc in zip(cands, s) if sc >= fixed_threshold]
        if not tier:
            order = np.argsort(-s)[:3]
            tier = [cands[int(i)] for i in order]
        # Format and call reader
        from ttmg.system import _format_claim_block, _format_raw_block
        claim_obj = [c.claim for c in tier if c.source_type == "claim" and c.claim is not None]
        raw_dicts = [c.raw_turn for c in tier if c.source_type == "raw-turn" and c.raw_turn is not None]
        claim_block = _format_claim_block(claim_obj) if claim_obj else "(none)"
        raw_block = ("Raw-turn context:\n" + _format_raw_block(raw_dicts)) if raw_dicts else ""
        prompt = _STD_READER_TMPL.format(question=question, claim_block=claim_block, extra_context=raw_block)
        reply = chat_text(prompt, system=_STD_READER_SYS, model=reader_model,
                          temperature=0.0, max_tokens=300, retries=2)
        ans = {"answer": reply.strip(), "abstain": False, "route": "no_crc",
               "no_crc_tier_size": len(tier), "no_crc_threshold": fixed_threshold,
               "retrieve_time": 0.0, "reader_time": 0.0}
    except Exception as e:
        traceback.print_exc()
        ans = {"answer": f"(error: {e})", "abstain": False,
               "retrieve_time": 0.0, "reader_time": 0.0}
    t_answer = time.time() - t_ans
    return {
        "ingest_time": t_ingest, "answer_time": t_answer,
        "metrics": sys_obj.metrics, **ans,
    }


def run_ttmg(
    item: Dict[str, Any],
    embed_model: SentenceTransformer,
    writer_model: str,
    reader_model: str,
    parser_model: str,
) -> Dict[str, Any]:
    """Path D baseline."""
    sessions = _convert_sessions(item)
    cfg = TTMGConfig(
        writer_model=writer_model,
        linker_model=writer_model,
        parser_model=parser_model,
        reader_model=reader_model,
        batch_writer_per_session=True,
        linker_min_similarity=0.55,
        linker_candidate_k=4,
        knn_k_read=8,
        top_keep=3,
        hard_threshold=0.7,
        raw_turn_fallback=True,
    )
    sys_obj = TTMGSystem(cfg, embed_model=embed_model)
    t_ing = time.time()
    sys_obj.ingest_conversation(sessions, verbose=False)
    t_ingest = time.time() - t_ing
    t_ans = time.time()
    try:
        ans = sys_obj.answer(item["question"])
    except Exception as e:
        traceback.print_exc()
        ans = {"answer": f"(error: {e})", "abstain": False,
               "retrieve_time": 0.0, "reader_time": 0.0}
    t_answer = time.time() - t_ans
    return {"ingest_time": t_ingest, "answer_time": t_answer,
            "metrics": sys_obj.metrics, **ans}


def run_flat_hybrid(
    item: Dict[str, Any],
    embed_model: SentenceTransformer,
    reader_model: str,
    k_total: int = 5,
) -> Dict[str, Any]:
    """Flat hybrid-RAG: semantic+lexical+raw RRF, no claim graph."""
    from ttmg.lb_retrieval import gather_candidates

    sessions = _convert_sessions(item)
    cfg = TTMGConfig(
        disable_writer_claims=True,
        disable_contradict=True,
        raw_turn_fallback=True,
        reader_model=reader_model,
    )
    sys_obj = TTMGSystem(cfg, embed_model=embed_model)
    t_ing = time.time()
    # Ingest turns directly as raw claims + raw turn index
    from ttmg.schema import Provenance
    for sess in sessions:
        sid = sess["session_id"]
        sts = sess.get("session_ts") or ""
        for ti, t in enumerate(sess.get("turns") or []):
            text = (t.get("text") or "").strip()
            if not text:
                continue
            prov = Provenance(session_id=sid, turn_id=f"{sid}#{ti}",
                              speaker=t.get("speaker") or "user", session_ts=sts)
            sys_obj.ingest_turn(text, prov)
            sys_obj._register_turn(text, prov)
    t_ingest = time.time() - t_ing

    question = item["question"]
    ts_q = item.get("question_date")
    t_ans = time.time()
    try:
        cands = gather_candidates(question, sys_obj, k_per_substrate=10, max_candidates=30)
        # Simple RRF: take top-k_total by cross-substrate agreement, then by score
        cands_sorted = sorted(
            cands,
            key=lambda c: (
                -sum(1 for v in c.in_topk.values() if v),
                -max((v for v in c.score.values() if v is not None), default=0.0),
            ),
        )
        tier = cands_sorted[:k_total]
        from ttmg.system import _format_raw_block
        # For flat hybrid, everything is a "raw turn" (claims with content=turn text)
        all_content = []
        for i, c in enumerate(tier, 1):
            all_content.append(f"[{i}] {c.content[:400]}")
        claim_block = "\n".join(all_content) if all_content else "(none)"
        prompt = _STD_READER_TMPL.format(question=question, claim_block=claim_block, extra_context="")
        reply = chat_text(prompt, system=_STD_READER_SYS, model=reader_model,
                          temperature=0.0, max_tokens=300, retries=2)
        ans = {"answer": reply.strip(), "abstain": False, "route": "flat_hybrid",
               "retrieve_time": 0.0, "reader_time": 0.0}
    except Exception as e:
        traceback.print_exc()
        ans = {"answer": f"(error: {e})", "abstain": False,
               "retrieve_time": 0.0, "reader_time": 0.0}
    t_answer = time.time() - t_ans
    return {"ingest_time": t_ingest, "answer_time": t_answer,
            "metrics": sys_obj.metrics, **ans}


def run_prompt_only(
    item: Dict[str, Any],
    embed_model: SentenceTransformer,
    writer_model: str,
    reader_model: str,
    parser_model: str,
) -> Dict[str, Any]:
    """Path D retrieval + load-bearing reader prompt framing (R010).
    Same retrieval as ttmg, different system prompt that discourages over-spec."""
    from ttmg.truth_retriever import truth_retrieve
    from ttmg.system import _format_claim_block, _format_raw_block

    sessions = _convert_sessions(item)
    cfg = TTMGConfig(
        writer_model=writer_model,
        linker_model=writer_model,
        parser_model=parser_model,
        reader_model=reader_model,
        batch_writer_per_session=True,
        linker_min_similarity=0.55,
        linker_candidate_k=4,
        knn_k_read=8,
        top_keep=3,
        hard_threshold=0.7,
        raw_turn_fallback=True,
    )
    sys_obj = TTMGSystem(cfg, embed_model=embed_model)
    t_ing = time.time()
    sys_obj.ingest_conversation(sessions, verbose=False)
    t_ingest = time.time() - t_ing

    question = item["question"]
    t_ans = time.time()
    try:
        rr = truth_retrieve(
            question, sys_obj.graph, k=cfg.knn_k_read, top_keep=cfg.top_keep,
            hard_threshold=cfg.hard_threshold, disable_temporal=cfg.disable_temporal,
            disable_contradict=cfg.disable_contradict,
            disable_consistent_subgraph=cfg.disable_consistent_subgraph,
            enable_abstention=cfg.enable_abstention, model=cfg.parser_model,
        )
        claim_block = _format_claim_block(rr.claims)
        raw_hits = sys_obj._raw_knn(question, cfg.raw_turn_k) if sys_obj._raw_turns else []
        raw_block = ("Raw-turn context:\n" + _format_raw_block(raw_hits)) if raw_hits else ""
        prompt = _LB_READER_TMPL.format(question=question, claim_block=claim_block, extra_context=raw_block)
        reply = chat_text(prompt, system=_LB_READER_SYS, model=reader_model,
                          temperature=0.0, max_tokens=300, retries=2)
        ans = {"answer": reply.strip(), "abstain": False, "route": "prompt_only",
               "retrieve_time": 0.0, "reader_time": 0.0}
    except Exception as e:
        traceback.print_exc()
        ans = {"answer": f"(error: {e})", "abstain": False,
               "retrieve_time": 0.0, "reader_time": 0.0}
    t_answer = time.time() - t_ans
    return {"ingest_time": t_ingest, "answer_time": t_answer,
            "metrics": sys_obj.metrics, **ans}


def run_rerank_only(
    item: Dict[str, Any],
    embed_model: SentenceTransformer,
    callb_model_path: str,
    top_k: int,
    writer_model: str,
    reader_model: str,
) -> Dict[str, Any]:
    """CalLB MLP top-K + standard prompt, no CRC (R011)."""
    from ttmg.lb_features import FEATURE_NAMES_FULL, extract_features
    from ttmg.lb_model import load as lb_load, score as lb_score
    from ttmg.lb_retrieval import gather_candidates
    from ttmg.system import _format_claim_block, _format_raw_block

    sessions = _convert_sessions(item)
    cfg = TTMGConfig(
        writer_model=writer_model,
        linker_model=writer_model,
        reader_model=reader_model,
        batch_writer_per_session=True,
        linker_min_similarity=0.55,
        linker_candidate_k=4,
        knn_k_read=8,
        top_keep=3,
        hard_threshold=0.7,
        raw_turn_fallback=True,
    )
    sys_obj = TTMGSystem(cfg, embed_model=embed_model)
    t_ing = time.time()
    sys_obj.ingest_conversation(sessions, verbose=False)
    t_ingest = time.time() - t_ing

    model, feat_names = lb_load(callb_model_path)
    question = item["question"]
    ts_q = item.get("question_date")
    t_ans = time.time()
    try:
        cands = gather_candidates(question, sys_obj, k_per_substrate=10, max_candidates=30)
        if not cands:
            raise ValueError("no candidates")
        X = np.stack([
            extract_features(question, c, sys_obj.graph, ts_q=ts_q,
                             feature_names=tuple(feat_names))
            for c in cands
        ])
        s = lb_score(model, X)
        order = np.argsort(-s)[:top_k]
        tier = [cands[int(i)] for i in order]
        claim_obj = [c.claim for c in tier if c.source_type == "claim" and c.claim is not None]
        raw_dicts = [c.raw_turn for c in tier if c.source_type == "raw-turn" and c.raw_turn is not None]
        claim_block = _format_claim_block(claim_obj) if claim_obj else "(none)"
        raw_block = ("Raw-turn context:\n" + _format_raw_block(raw_dicts)) if raw_dicts else ""
        prompt = _STD_READER_TMPL.format(question=question, claim_block=claim_block, extra_context=raw_block)
        reply = chat_text(prompt, system=_STD_READER_SYS, model=reader_model,
                          temperature=0.0, max_tokens=300, retries=2)
        ans = {"answer": reply.strip(), "abstain": False, "route": "rerank_only",
               "rerank_top_k": top_k, "retrieve_time": 0.0, "reader_time": 0.0}
    except Exception as e:
        traceback.print_exc()
        ans = {"answer": f"(error: {e})", "abstain": False,
               "retrieve_time": 0.0, "reader_time": 0.0}
    t_answer = time.time() - t_ans
    return {"ingest_time": t_ingest, "answer_time": t_answer,
            "metrics": sys_obj.metrics, **ans}


def run_agreement_heuristic(
    item: Dict[str, Any],
    embed_model: SentenceTransformer,
    writer_model: str,
    reader_model: str,
    top_k: int = 3,
) -> Dict[str, Any]:
    """Cross-substrate agreement rank + load-bearing prompt (R012)."""
    from ttmg.lb_retrieval import gather_candidates
    from ttmg.system import _format_claim_block, _format_raw_block

    sessions = _convert_sessions(item)
    cfg = TTMGConfig(
        writer_model=writer_model,
        linker_model=writer_model,
        reader_model=reader_model,
        batch_writer_per_session=True,
        linker_min_similarity=0.55,
        linker_candidate_k=4,
        knn_k_read=8,
        top_keep=3,
        hard_threshold=0.7,
        raw_turn_fallback=True,
    )
    sys_obj = TTMGSystem(cfg, embed_model=embed_model)
    t_ing = time.time()
    sys_obj.ingest_conversation(sessions, verbose=False)
    t_ingest = time.time() - t_ing

    question = item["question"]
    t_ans = time.time()
    try:
        cands = gather_candidates(question, sys_obj, k_per_substrate=10, max_candidates=30)
        if not cands:
            raise ValueError("no candidates")
        cands_sorted = sorted(
            cands,
            key=lambda c: (
                -sum(1 for v in c.in_topk.values() if v),
                -max((v for v in c.score.values() if v is not None), default=0.0),
            ),
        )
        tier = cands_sorted[:top_k]
        claim_obj = [c.claim for c in tier if c.source_type == "claim" and c.claim is not None]
        raw_dicts = [c.raw_turn for c in tier if c.source_type == "raw-turn" and c.raw_turn is not None]
        claim_block = _format_claim_block(claim_obj) if claim_obj else "(none)"
        raw_block = ("Raw-turn context:\n" + _format_raw_block(raw_dicts)) if raw_dicts else ""
        prompt = _LB_READER_TMPL.format(question=question, claim_block=claim_block, extra_context=raw_block)
        reply = chat_text(prompt, system=_LB_READER_SYS, model=reader_model,
                          temperature=0.0, max_tokens=300, retries=2)
        ans = {"answer": reply.strip(), "abstain": False, "route": "agreement_heuristic",
               "agree_top_k": top_k, "retrieve_time": 0.0, "reader_time": 0.0}
    except Exception as e:
        traceback.print_exc()
        ans = {"answer": f"(error: {e})", "abstain": False,
               "retrieve_time": 0.0, "reader_time": 0.0}
    t_answer = time.time() - t_ans
    return {"ingest_time": t_ingest, "answer_time": t_answer,
            "metrics": sys_obj.metrics, **ans}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

METHODS = ("callb", "no_crc", "ttmg", "flat_hybrid",
           "prompt_only", "rerank_only", "agreement_heuristic")
# Deferred: MiCP (arXiv 2604.01413) and Stop-RAG (arXiv 2510.14337).
# These require porting reference implementations from the papers.
# Add as separate methods once implemented (R007, R008).


def run_one(item: Dict[str, Any], args: argparse.Namespace,
            embed_model: SentenceTransformer) -> Dict[str, Any]:
    m = args.method
    if m == "callb":
        r = run_callb(item, embed_model, args.callb_model, args.callb_crc,
                      args.callb_alpha, args.writer_model, args.reader_model)
    elif m == "no_crc":
        r = run_no_crc(item, embed_model, args.callb_model, args.no_crc_threshold,
                       args.writer_model, args.reader_model)
    elif m == "ttmg":
        r = run_ttmg(item, embed_model, args.writer_model,
                     args.reader_model, args.parser_model)
    elif m == "flat_hybrid":
        r = run_flat_hybrid(item, embed_model, args.reader_model, k_total=5)
    elif m == "prompt_only":
        r = run_prompt_only(item, embed_model, args.writer_model,
                            args.reader_model, args.parser_model)
    elif m == "rerank_only":
        r = run_rerank_only(item, embed_model, args.callb_model,
                            args.rerank_top_k, args.writer_model, args.reader_model)
    elif m == "agreement_heuristic":
        r = run_agreement_heuristic(item, embed_model, args.writer_model,
                                    args.reader_model, top_k=3)
    else:
        raise ValueError(f"unknown method: {m}")
    return r


def summarise(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    def _avg(xs):
        return sum(xs) / len(xs) if xs else 0.0

    correct = [r["correct"] for r in rows]
    f1s = [r["f1"] for r in rows]
    abstain = [r.get("abstained", False) for r in rows]
    by_type: Dict[str, List[int]] = defaultdict(list)
    for r in rows:
        by_type[r["question_type"]].append(r["correct"])

    return {
        "n": len(rows),
        "accuracy": _avg(correct),
        "f1": _avg(f1s),
        "abstain_rate": _avg([int(a) for a in abstain]),
        "per_type": {k: {"n": len(v), "acc": _avg(v)} for k, v in sorted(by_type.items())},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--method", choices=METHODS, required=True)
    ap.add_argument("--lme-data", default=LME_PATH)
    ap.add_argument("--out", required=True, help="JSONL output (resumable)")
    ap.add_argument("--limit", type=int, default=None, help="Cap #questions (default: all)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--stratify", action="store_true", default=True)
    # Model paths
    ap.add_argument("--callb-model", default="results/lb_mlp.json")
    ap.add_argument("--callb-crc", default="results/lb_crc.json")
    ap.add_argument("--callb-alpha", type=float, default=0.20)
    ap.add_argument("--no-crc-threshold", type=float, default=0.5)
    ap.add_argument("--rerank-top-k", type=int, default=3)
    # LLM models
    ap.add_argument("--writer-model", default=DEFAULT_MODEL)
    ap.add_argument("--reader-model", default=DEFAULT_MODEL)
    ap.add_argument("--parser-model", default=DEFAULT_MODEL)
    ap.add_argument("--embed-model", default="all-MiniLM-L6-v2")
    ap.add_argument("--question-type", default=None,
                    help="If set, evaluate on this question_type only (e.g. 'single-session-user').")
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    seen = _load_existing(out_path)
    print(f"[eval] resume: {len(seen)} questions already done")

    data = load_dataset(args.lme_data, limit=args.limit, seed=args.seed, stratify=args.stratify,
                        question_type=args.question_type)
    print(f"[eval] {len(data)} questions; method={args.method}; "
          f"question_type={args.question_type or 'all'}; seed={args.seed}")

    embed_model = SentenceTransformer(args.embed_model)

    all_rows = list(seen.values())
    n_new = 0
    t_start = time.time()
    for qi, item in enumerate(data, 1):
        qid = item.get("question_id") or f"q{qi}"
        if qid in seen:
            continue
        print(f"[{qi}/{len(data)}] qid={qid} type={item.get('question_type')}  ", end="", flush=True)
        try:
            r = run_one(item, args, embed_model)
        except Exception as e:
            traceback.print_exc()
            r = {"answer": f"(run_one error: {e})", "abstain": False,
                 "retrieve_time": 0.0, "reader_time": 0.0}
        question = str(item["question"])
        gold = str(item["answer"])
        pred = str(r.get("answer", ""))
        correct, reason = judge_answer(question, gold, pred)
        f1 = token_f1(pred, gold)
        row = {
            "question_id": qid,
            "question_type": item.get("question_type", ""),
            "question": question[:400],
            "gold": gold[:200],
            "pred": pred[:400],
            "correct": correct,
            "judge_reason": reason,
            "f1": f1,
            "abstained": bool(r.get("abstain", False)),
            "route": r.get("route", args.method),
            "callb_tier_size": r.get("callb_tier_size"),
            "callb_threshold": r.get("callb_threshold"),
            "callb_tier_fallback": r.get("callb_tier_fallback"),
            "callb_n_candidates": r.get("callb_n_candidates"),
            "retrieve_time": float(r.get("retrieve_time", 0.0)),
            "reader_time": float(r.get("reader_time", 0.0)),
            "ingest_time": float(r.get("ingest_time", 0.0)),
            "method": args.method,
            "seed": args.seed,
        }
        with open(out_path, "a") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        seen[qid] = row
        all_rows.append(row)
        n_new += 1
        elapsed = time.time() - t_start
        rate = n_new / max(1.0, elapsed)
        print(f"correct={correct} f1={f1:.2f} | done={len(all_rows)} rate={rate:.3f}q/s", flush=True)

    # Write summary
    summary = summarise(all_rows)
    summary_path = out_path.with_suffix(".summary.json")
    with open(summary_path, "w") as fh:
        json.dump({"method": args.method, "seed": args.seed, "summary": summary,
                   "n_new": n_new}, fh, indent=2)
    print(f"\n[eval] done. accuracy={summary['accuracy']:.4f}  n={summary['n']}")
    print(f"  per-type: {json.dumps(summary['per_type'])}")
    print(f"  output: {out_path}")
    print(f"  summary: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
