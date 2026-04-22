"""Baseline: vanilla A-Mem style memory system with the same MAAS reader.

We don't import A-Mem's heavy dependencies (chromadb, litellm). Instead we
reimplement the baseline as a flat note store with hybrid embed + BM25
retrieval and the standard "note with keywords/tags/context" generation.
This keeps the comparison fair (same reader, same embedding model,
same data path) and isolates the contribution of the temporal-truth
mechanism.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from .maas_client import DEFAULT_MODEL, chat_json, chat_text

try:
    from rank_bm25 import BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:  # pragma: no cover
    _BM25_AVAILABLE = False


@dataclass
class _Note:
    id: str
    content: str
    keywords: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    context: str = ""
    session_id: str = ""
    turn_id: int = -1
    session_ts: Optional[str] = None
    speaker: str = "user"


@dataclass
class AMemBaselineConfig:
    embed_model: str = "all-MiniLM-L6-v2"
    writer_model: str = DEFAULT_MODEL
    reader_model: str = DEFAULT_MODEL
    k: int = 8
    use_analysis: bool = True  # note generation with keywords/tags/context


_READER_SYS = (
    "You are a helpful assistant with access to long-term memory. "
    "Answer using the retrieved notes. If the memory is clearly "
    "insufficient, say you do not know."
)

_READER_USER_TMPL = """Question: {question}

Retrieved memory notes:
{block}

Answer concisely."""


class AMemBaseline:
    def __init__(self, config: Optional[AMemBaselineConfig] = None, embed_model: Optional[SentenceTransformer] = None):
        self.config = config or AMemBaselineConfig()
        self.notes: Dict[str, _Note] = {}
        self._emb: Dict[str, np.ndarray] = {}
        self._embed_model = embed_model or SentenceTransformer(self.config.embed_model)
        self.metrics = {"writer_calls": 0, "reader_calls": 0}

    def _analyze(self, content: str) -> Dict[str, Any]:
        if not self.config.use_analysis:
            return {"keywords": [], "tags": [], "context": ""}
        prompt = (
            "Analyze this memory note and output JSON {\"keywords\": [...], "
            "\"tags\": [...], \"context\": \"...\"}. Content:\n" + content[:1500]
        )
        return chat_json(
            prompt,
            default={"keywords": [], "tags": [], "context": ""},
            temperature=0.0,
            max_tokens=250,
            model=self.config.writer_model,
        )

    def ingest_turn(self, text: str, provenance: Dict[str, Any]) -> None:
        text = (text or "").strip()
        if not text:
            return
        meta = self._analyze(text)
        if self.config.use_analysis:
            self.metrics["writer_calls"] += 1
        nid = f"n{len(self.notes)}"
        n = _Note(
            id=nid,
            content=text[:2000],
            keywords=meta.get("keywords", []) or [],
            tags=meta.get("tags", []) or [],
            context=meta.get("context", "") or "",
            session_id=provenance.get("session_id", ""),
            turn_id=provenance.get("turn_id", -1),
            session_ts=provenance.get("session_ts"),
            speaker=provenance.get("speaker", "user"),
        )
        self.notes[nid] = n
        v = self._embed_model.encode(text, normalize_embeddings=True)
        self._emb[nid] = np.asarray(v, dtype=np.float32)

    def ingest_conversation(self, sessions: List[Dict[str, Any]], max_sessions: Optional[int] = None, verbose: bool = False) -> None:
        for si, sess in enumerate(sessions):
            if max_sessions is not None and si >= max_sessions:
                break
            sid = sess.get("session_id") or f"s{si}"
            sts = sess.get("session_ts")
            turns = sess.get("turns") or []
            t0 = time.time()
            for ti, t in enumerate(turns):
                if not isinstance(t, dict):
                    continue
                self.ingest_turn(
                    t.get("text") or "",
                    {
                        "session_id": sid,
                        "turn_id": ti,
                        "speaker": t.get("speaker") or "user",
                        "session_ts": sts,
                    },
                )
            if verbose:
                print(f"    [amem] session {sid}: {len(turns)} turns in {time.time()-t0:.1f}s", flush=True)

    def _retrieve(self, query: str, k: int) -> List[_Note]:
        if not self.notes:
            return []
        q = np.asarray(self._embed_model.encode(query, normalize_embeddings=True), dtype=np.float32)
        ids = list(self.notes.keys())
        mat = np.stack([self._emb[i] for i in ids], axis=0)
        sims = mat @ q
        # Hybrid with BM25 if available
        if _BM25_AVAILABLE:
            corpus = [self.notes[i].content.split() for i in ids]
            bm = BM25Okapi(corpus)
            bm_scores = np.asarray(bm.get_scores(query.split()), dtype=np.float32)
            if bm_scores.max() > 0:
                bm_scores = bm_scores / (bm_scores.max() + 1e-9)
            total = 0.7 * sims + 0.3 * bm_scores
        else:
            total = sims
        order = np.argsort(-total)[:k]
        return [self.notes[ids[i]] for i in order]

    def answer(self, question: str) -> Dict[str, Any]:
        cfg = self.config
        t0 = time.time()
        hits = self._retrieve(question, cfg.k)
        t_ret = time.time() - t0
        block = "\n".join(
            f"[{i}] (sess {h.session_id} ts {h.session_ts}): {h.content}"
            for i, h in enumerate(hits, 1)
        ) or "(none)"
        prompt = _READER_USER_TMPL.format(question=question.strip(), block=block)
        t1 = time.time()
        reply = chat_text(
            prompt,
            system=_READER_SYS,
            model=cfg.reader_model,
            temperature=0.0,
            max_tokens=300,
            retries=2,
        )
        t_read = time.time() - t1
        self.metrics["reader_calls"] += 1
        return {
            "answer": reply.strip(),
            "abstain": False,
            "retrieved": [{"id": h.id, "content": h.content} for h in hits],
            "retrieve_time": t_ret,
            "reader_time": t_read,
        }


__all__ = ["AMemBaseline", "AMemBaselineConfig"]
