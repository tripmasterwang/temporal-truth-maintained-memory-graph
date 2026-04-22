"""Truth-consistent retrieval over the memory graph.

For an incoming question, we:
  1. Parse the query for (a) temporal anchor, (b) entity slot, (c) update/
     knowledge-state intent. This is a lightweight LLM call returning JSON.
  2. k-NN over active claims on the embedding index.
  3. Expand to include superseded ancestors only if the question asks
     "what did I used to …".
  4. Greedy construction of the maximum-consistent subgraph: drop any claim
     whose hard-contradiction edge to a retained claim exceeds threshold.
  5. If two incompatible claim clusters both survive → trigger abstention.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from .maas_client import chat_json
from .graph import MemoryGraph
from .schema import Claim


@dataclass
class RetrievalResult:
    claims: List[Claim]
    discarded: List[Tuple[Claim, str]]  # (claim, reason)
    should_abstain: bool
    abstain_reason: str
    query_parse: Dict[str, Any]


_QUERY_SYS = (
    "You parse a question asked of a long-term memory system. "
    "Respond with strict JSON only."
)

_QUERY_USER_TMPL = """Parse the question below.

Question: {question}

Return JSON with fields:
- temporal_anchor: a time string the question refers to, or null. Examples: "2025-06", "before 2024", "currently", "when I was in Paris".
- asks_history: true if the question asks about a PAST state that may have been superseded (e.g., "what did I used to...", "what was my previous..."); else false.
- asks_current: true if the question asks about the CURRENT state (default for most questions without explicit past framing); else false.
- entity: the main subject the question is about, or null.
- intent: one of "lookup", "update_check", "temporal_reasoning", "small_talk".
"""


def parse_query(question: str, model: Optional[str] = None) -> Dict[str, Any]:
    prompt = _QUERY_USER_TMPL.format(question=question.strip()[:1000])
    return chat_json(
        prompt,
        system=_QUERY_SYS,
        model=model,
        default={
            "temporal_anchor": None,
            "asks_history": False,
            "asks_current": True,
            "entity": None,
            "intent": "lookup",
        },
        temperature=0.0,
        max_tokens=200,
    )


def _maximum_consistent_subgraph(
    candidates: List[Claim],
    graph: MemoryGraph,
    hard_threshold: float = 0.7,
) -> Tuple[List[Claim], List[Tuple[Claim, str]]]:
    """Greedy: sort by confidence desc, drop claims with hard contradict to kept set."""
    sorted_c = sorted(
        candidates,
        key=lambda c: (c.confidence, c.created_at),
        reverse=True,
    )
    kept: List[Claim] = []
    discarded: List[Tuple[Claim, str]] = []
    kept_ids: Set[str] = set()
    for c in sorted_c:
        conflict_ids = set(graph.contradict_set(c.id, hard_threshold=hard_threshold))
        if conflict_ids & kept_ids:
            discarded.append((c, "hard_contradict_with_kept"))
            continue
        kept.append(c)
        kept_ids.add(c.id)
    return kept, discarded


def truth_retrieve(
    question: str,
    graph: MemoryGraph,
    *,
    k: int = 8,
    top_keep: int = 3,
    hard_threshold: float = 0.7,
    disable_temporal: bool = False,
    disable_contradict: bool = False,
    disable_consistent_subgraph: bool = False,
    enable_abstention: bool = True,
    model: Optional[str] = None,
) -> RetrievalResult:
    if disable_temporal:
        qp: Dict[str, Any] = {
            "temporal_anchor": None,
            "asks_history": False,
            "asks_current": True,
            "entity": None,
            "intent": "lookup",
        }
    else:
        qp = parse_query(question, model=model)

    asks_history = bool(qp.get("asks_history", False))
    active_only = not asks_history  # if asking about past, include superseded claims

    hits = graph.knn(question, k=k, active_only=active_only)
    # Best similarity (top-1 cosine) is surfaced so the system can decide
    # to drop the claim block when claims look unrelated to the query.
    best_sim = hits[0][1] if hits else 0.0
    qp["_best_claim_sim"] = float(best_sim)
    cand_claims = [graph.claims[cid] for cid, _ in hits]

    if disable_consistent_subgraph or disable_contradict:
        kept = cand_claims[:top_keep]
        discarded: List[Tuple[Claim, str]] = []
    else:
        kept, discarded = _maximum_consistent_subgraph(
            cand_claims, graph, hard_threshold=hard_threshold
        )
        kept = kept[:top_keep]

    # Abstention: if there is a hard contradiction WITHIN the top semantic hits
    # that cannot be resolved by supersede (two equal-confidence active claims
    # disagreeing), abstain.
    should_abstain = False
    abstain_reason = ""
    if enable_abstention and not asks_history:
        top_ids = {c.id for c in cand_claims[:top_keep + 2]}
        for c in cand_claims[:top_keep + 2]:
            bad = set(graph.contradict_set(c.id, hard_threshold=hard_threshold)) & top_ids
            # If conflict and neither supersedes the other
            for other_id in bad:
                other = graph.claims.get(other_id)
                if other is None:
                    continue
                if c.active and other.active and c.superseded_by is None and other.superseded_by is None:
                    should_abstain = True
                    abstain_reason = (
                        f"Contradictory active claims {c.id} vs {other.id} among top-k retrieval."
                    )
                    break
            if should_abstain:
                break

    return RetrievalResult(
        claims=kept,
        discarded=discarded,
        should_abstain=should_abstain,
        abstain_reason=abstain_reason,
        query_parse=qp,
    )


__all__ = ["truth_retrieve", "parse_query", "RetrievalResult"]
