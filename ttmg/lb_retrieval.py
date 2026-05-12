"""CalLB multi-substrate candidate retrieval.

Path D's `truth_retrieve` only returns a single semantic-cosine top-k over
claims. CalLB needs the *union* of multiple substrates' top-k lists so that
per-item `cross_substrate_agreement` is meaningful.

This module implements the candidate-gathering layer:

    candidates(question, system, ks=10) -> List[CandidateItem]

Each `CandidateItem` carries:
  - `id`: stable identifier (claim_id for claim items; raw-turn-index for raw items)
  - `content`: the text the reader / reranker will see
  - `source_type`: 'claim' | 'raw-turn'
  - `claim`: Optional[Claim] (None for raw-turn items)
  - `raw_turn`: Optional[Dict] (None for claim items)
  - `in_topk`: Dict[str, bool] for substrates {'semantic', 'lexical', 'claim', 'raw'}
  - `score`: Dict[str, Optional[float]] per substrate (None if not retrieved)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from rank_bm25 import BM25Okapi

from .schema import Claim


SUBSTRATES = ("semantic", "lexical", "claim", "raw")


def _stable_claim_id(claim: Claim) -> str:
    """Deterministic candidate id for a Claim, stable across re-ingestion.

    `Claim.id` is `uuid4()` so it changes every run. CalLB resume needs a
    stable handle on the (question, item) pair. We hash provenance + canonical
    fields + content prefix.
    """
    prov = claim.provenance
    parts = [
        str(prov.session_id) if prov else "",
        str(prov.turn_id) if prov else "",  # turn_id may be int from ingest_conversation
        str(prov.speaker) if prov else "",
        (claim.subject or ""),
        (claim.predicate or ""),
        (claim.object or ""),
        (claim.content or "")[:200],
    ]
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return "claim:" + h


def _stable_raw_id(turn: Dict[str, Any]) -> str:
    """Deterministic id for a raw-turn dict from `system._raw_turns`."""
    parts = [
        str(turn.get("session_id") or ""),
        str(turn.get("session_ts") or ""),
        str(turn.get("speaker") or ""),
        (turn.get("text", "") or "")[:200],
    ]
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return "raw:" + h


@dataclass
class CandidateItem:
    id: str
    content: str
    source_type: str  # 'claim' | 'raw-turn'
    claim: Optional[Claim] = None
    raw_turn: Optional[Dict[str, Any]] = None
    in_topk: Dict[str, bool] = field(default_factory=lambda: {s: False for s in SUBSTRATES})
    score: Dict[str, Optional[float]] = field(default_factory=lambda: {s: None for s in SUBSTRATES})

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "content": self.content[:500],
            "source_type": self.source_type,
            "in_topk": dict(self.in_topk),
            "score": {k: (float(v) if v is not None else None) for k, v in self.score.items()},
        }
        if self.claim is not None:
            d["claim_id"] = self.claim.id
        return d


def _tokenize(text: str) -> List[str]:
    """Cheap tokenizer for BM25 (lowercase + alphanum split)."""
    out = []
    cur = []
    for ch in (text or "").lower():
        if ch.isalnum():
            cur.append(ch)
        else:
            if cur:
                out.append("".join(cur))
                cur = []
    if cur:
        out.append("".join(cur))
    return out


def _claim_repr(claim: Claim) -> str:
    """Structured representation used by the 'claim' substrate.

    Distinct from `claim.content` (the full sentence) so that the substrate
    actually adds signal vs the semantic substrate. Mirrors how a claim graph
    is searched: by canonical (subject, predicate, object) triple text.
    """
    parts = []
    if claim.subject:
        parts.append(claim.subject)
    if claim.predicate:
        parts.append(claim.predicate)
    if claim.object:
        parts.append(claim.object)
    return " ".join(parts).strip() or claim.content[:200]


def gather_candidates(
    question: str,
    system,                   # ttmg.system.TTMGSystem
    k_per_substrate: int = 10,
    max_candidates: int = 30,
    active_only: bool = False,
) -> List[CandidateItem]:
    """Gather the union of 4 substrates' top-k items as CalLB candidates.

    Substrates:
      - semantic: cosine(question, claim.content) over `system.graph` claim embeddings.
      - lexical:  BM25 over claim.content (built ad-hoc per query batch).
      - claim:    cosine(question, claim_repr(claim)) — structured-triple substrate (TTMG-specific).
      - raw:      cosine(question, raw_turn.text) over `system._raw_turns`.

    Returns deduplicated list (by canonical id), capped at `max_candidates`.
    Items get per-substrate presence flags + scores.
    """
    if system.graph._embed_model is None:
        raise RuntimeError("system.graph has no embed model")
    embed_model = system.graph._embed_model
    q_vec = np.asarray(embed_model.encode(question, normalize_embeddings=True), dtype=np.float32)

    # Build a working index: stable_id → CandidateItem (UUID-stable across re-ingestion)
    items: Dict[str, CandidateItem] = {}

    def _claim_to_item(claim: Claim) -> CandidateItem:
        sid = _stable_claim_id(claim)
        return items.setdefault(sid, CandidateItem(
            id=sid, content=claim.content, source_type="claim", claim=claim,
        ))

    # --- Substrate 1: semantic over claims ---
    sem_pairs: List[Tuple[str, float]] = system.graph.knn(question, k=k_per_substrate, active_only=active_only)
    for cid, score in sem_pairs:
        claim = system.graph.claims.get(cid)
        if claim is None:
            continue
        item = _claim_to_item(claim)
        item.in_topk["semantic"] = True
        item.score["semantic"] = float(score)

    # --- Substrate 2: lexical (BM25) over claim contents ---
    # Build BM25 over the candidate pool of claims (use the union of all
    # active claims for a small per-query corpus; if too large, restrict to
    # KNN expansion). For typical LongMemEval-S sizes (~hundreds of claims),
    # full corpus is fine.
    all_claims = list(system.graph.claims.values())
    if active_only:
        all_claims = [c for c in all_claims if c.active]
    if all_claims:
        corpus_tokens = [_tokenize(c.content) for c in all_claims]
        bm25 = BM25Okapi(corpus_tokens)
        q_tokens = _tokenize(question)
        bm25_scores = bm25.get_scores(q_tokens)
        order = np.argsort(-bm25_scores)[:k_per_substrate]
        for idx in order:
            claim = all_claims[int(idx)]
            sc = float(bm25_scores[int(idx)])
            if sc <= 0:
                continue
            item = _claim_to_item(claim)
            item.in_topk["lexical"] = True
            item.score["lexical"] = sc

    # --- Substrate 3: claim-repr substrate (cosine over structured triple text) ---
    # MINOR fix: skip claims with empty (subject, predicate, object); without
    # a structured triple this substrate degenerates to semantic and inflates
    # `cross_substrate_agreement` with pseudo-diversity.
    claim_reprs: List[str] = []
    rep_claim_objs: List[Claim] = []
    for c in all_claims:
        if not (c.subject or c.predicate or c.object):
            continue
        rep = _claim_repr(c)
        if rep and rep != c.content[:200]:
            claim_reprs.append(rep)
            rep_claim_objs.append(c)
    if claim_reprs:
        rep_emb = embed_model.encode(claim_reprs, normalize_embeddings=True, show_progress_bar=False)
        rep_emb = np.asarray(rep_emb, dtype=np.float32)
        rep_scores = rep_emb @ q_vec
        order = np.argsort(-rep_scores)[:k_per_substrate]
        for idx in order:
            claim = rep_claim_objs[int(idx)]
            sc = float(rep_scores[int(idx)])
            item = _claim_to_item(claim)
            item.in_topk["claim"] = True
            item.score["claim"] = sc

    # --- Substrate 4: raw-turn substrate ---
    if system._raw_turns and system._raw_emb:
        mat = np.stack(system._raw_emb, axis=0)
        scores = mat @ q_vec
        order = np.argsort(-scores)[:k_per_substrate]
        for idx in order:
            idx = int(idx)
            turn = system._raw_turns[idx]
            rid = _stable_raw_id(turn)
            item = items.setdefault(rid, CandidateItem(
                id=rid, content=turn.get("text", ""), source_type="raw-turn",
                raw_turn=dict(turn),
            ))
            item.in_topk["raw"] = True
            item.score["raw"] = float(scores[idx])

    # Dedupe + cap. Sort first by cross-substrate presence (more substrates =
    # more agreement), then by NORMALIZED max score across substrates so
    # unbounded BM25 doesn't dominate over [0,1] cosines.
    def _normalized_score(it: CandidateItem, name: str) -> Optional[float]:
        v = it.score.get(name)
        if v is None:
            return None
        if name == "lexical":
            return min(1.0, float(v) / 20.0)  # mirror lb_features._max_substrate_score normalisation
        return float(v)

    def _sort_key(it: CandidateItem) -> Tuple[int, float]:
        agree = sum(1 for v in it.in_topk.values() if v)
        normed = [_normalized_score(it, n) for n in SUBSTRATES]
        max_sc = max((v for v in normed if v is not None), default=0.0)
        return (-agree, -float(max_sc))
    cands = list(items.values())
    cands.sort(key=_sort_key)
    return cands[:max_candidates]
