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
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

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


# ----------------------------------------------------------------------
# β round-2 read-time path
# ----------------------------------------------------------------------

from .canonicalize import Canonicalizer, canonical_key_str
from .crc import (
    CRCThresholdTable,
    ScoreWeights,
    compute_S,
)
from .pmi import compute_pmi
from .schema import Edge


_BETA_QUERY_SYS = (
    "You parse a question asked of a personal long-term memory system. "
    "Respond with strict JSON only."
)

_BETA_QUERY_USER_TMPL = """Parse the question below for a memory operator.

Question: {question}

Return JSON with fields:
- claim_key: a (entity, slot_name) pair identifying the slot the question is about, OR null if the question does not have a single well-defined slot. Examples:
    {{"entity": "user", "slot_name": "preferred_coffee_temperature"}}
    {{"entity": "user", "slot_name": "current_to_do_list"}}
- slot_type: "single_valued" | "multi_valued" | "unknown".
- temporal_anchor: ISO time string the question refers to, or "now" / null.
- asks_history: true if the question asks about a PAST state that may have been superseded.
- asks_truth_of_fact: true if the question asks "what is/was the value of slot X" (this is the operator's scope); false for open-ended generation, list-construction, opinion, or assistant-utterance questions.
- intent: short string describing question type.
"""


@dataclass
class BetaRetrievalResult:
    """Result of the β read-time path.

    `route` ∈ {"ttmg", "flat", "abstain"} describes the disposition:
      - "ttmg":    answer with the TTMG-β path (use `value` + `claims`).
      - "flat":    query is out-of-scope, caller should use Flat fallback.
      - "abstain": below CRC threshold or non-unique value; return ABSTAIN.

    `score`, `group`, `pmi`, `vals` are returned for diagnostics + calibration.
    """

    route: str
    value: Optional[str]
    claims: List[Claim]
    discarded: List[Tuple[Claim, str]]
    score: float
    group: Tuple[Any, ...]
    pmi: Optional[float]
    vals: List[str]
    threshold: Optional[float]
    abstain_reason: str
    query_parse: Dict[str, Any]


def parse_query_beta(
    question: str,
    canonicaliser: Canonicalizer,
    *,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """β query parser: emits canonical claim_key + applicability flag."""
    prompt = _BETA_QUERY_USER_TMPL.format(question=question.strip()[:1000])
    parsed = chat_json(
        prompt,
        system=_BETA_QUERY_SYS,
        model=model,
        default={
            "claim_key": None,
            "slot_type": "unknown",
            "temporal_anchor": None,
            "asks_history": False,
            "asks_truth_of_fact": False,
            "intent": "lookup",
        },
        temperature=0.0,
        max_tokens=200,
    )
    raw_key = parsed.get("claim_key")
    if isinstance(raw_key, dict) and raw_key.get("entity") and raw_key.get("slot_name"):
        ck = canonicaliser.canonical_claim_key(raw_key.get("entity"), raw_key.get("slot_name"))
        parsed["_canonical_claim_key"] = ck
        parsed["_canonical_claim_key_str"] = canonical_key_str(ck)
    else:
        parsed["_canonical_claim_key"] = None
        parsed["_canonical_claim_key_str"] = ""
    slot_type_q = parsed.get("slot_type") or "unknown"
    asks_truth = bool(parsed.get("asks_truth_of_fact", False))
    parsed["_applicable"] = (
        slot_type_q == "single_valued"
        and parsed["_canonical_claim_key"] is not None
        and asks_truth
    )
    return parsed


def _canonical_key_fetch(graph: MemoryGraph, key_str: str) -> List[Claim]:
    """All claims sharing the canonical key string."""
    if not key_str:
        return []
    return [c for c in graph.claims.values() if c.canonical_key_str() == key_str]


def _valid_at(c: Claim, anchor: Optional[str], asks_history: bool) -> bool:
    """Is the claim active at the temporal anchor?

    `asks_history=True` includes superseded claims (the question asks about
    a past state). Otherwise we require active=True AND anchor is within
    [valid_from, valid_to].
    """
    if asks_history:
        return True  # include all candidates with the same key for history queries
    if not c.active:
        return False
    if anchor is None or anchor == "now":
        return c.valid_to is None or c.valid_to == "" or c.valid_to >= "9999"
    if c.valid_from and anchor < c.valid_from:
        return False
    if c.valid_to and c.valid_to <= anchor:
        return False
    return True


def _hard_edges_within(graph: MemoryGraph, claim_ids: Set[str], hard_threshold: float) -> List[Tuple[str, str]]:
    """Return (i, j) pairs in `claim_ids` connected by a hard contradict edge."""
    edges: List[Tuple[str, str]] = []
    for e in graph.edges:
        if e.label != "contradict":
            continue
        if e.confidence < hard_threshold:
            continue
        if e.src in claim_ids and e.dst in claim_ids:
            edges.append((e.src, e.dst))
    return edges


_MWIS_CAP_K = 12  # Codex-fix MAJOR: explicit cap; 2^12 = 4096 subset checks.

import logging  # local-scoped at module load

_mwis_logger = logging.getLogger("ttmg.truth_retriever.mwis")
# Codex-fix follow-up: surface truncation events so paper appendix can
# report how often the cap fires and on which keys.


def _all_optima_mwis(
    cand: List[Claim],
    hard_pairs: List[Tuple[str, str]],
    weights_by_id: Dict[str, float],
) -> Tuple[List[List[str]], float]:
    """Enumerate ALL maximum-weight independent sets on the hard-edge subgraph.

    With k = |cand| ≤ `_MWIS_CAP_K` (default 12) exhaustive subset enumeration
    is trivial. If k exceeds the cap, we PRUNE to the top-K candidates by
    writer confidence to keep the operator deterministic + bounded; callers
    that need exact MWIS on larger sets must implement a branch-and-bound
    solver. The pruning is logged via the returned tuple's claim ordering
    (callers can detect via `len(cand) > _MWIS_CAP_K`).
    """
    n = len(cand)
    if n == 0:
        return [], 0.0
    if n > _MWIS_CAP_K:
        n_in = n
        # Deterministic top-K by (weight desc, id asc) tie-break
        cand = sorted(
            cand,
            key=lambda c: (-weights_by_id.get(c.id, 0.0), c.id),
        )[:_MWIS_CAP_K]
        n = len(cand)
        kept = {c.id for c in cand}
        # Drop any pair that references a pruned id
        hard_pairs = [(a, b) for a, b in hard_pairs if a in kept and b in kept]
        _mwis_logger.warning(
            "MWIS truncation: n_in=%d → kept=%d (cap=%d). claim_keys: %s",
            n_in,
            n,
            _MWIS_CAP_K,
            [c.canonical_key_str() for c in cand[:3]],
        )
    ids = [c.id for c in cand]
    pair_index = set()
    for a, b in hard_pairs:
        i = ids.index(a) if a in ids else None
        j = ids.index(b) if b in ids else None
        if i is not None and j is not None and i != j:
            pair_index.add((min(i, j), max(i, j)))
    best_w = -1.0
    best_sets: List[List[str]] = []
    for mask in range(1 << n):
        # Independence check
        chosen = [i for i in range(n) if mask & (1 << i)]
        ok = True
        for a in chosen:
            for b in chosen:
                if a >= b:
                    continue
                if (a, b) in pair_index:
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue
        w = sum(weights_by_id[ids[i]] for i in chosen)
        if w > best_w + 1e-12:
            best_w = w
            best_sets = [[ids[i] for i in chosen]]
        elif abs(w - best_w) <= 1e-12:
            best_sets.append([ids[i] for i in chosen])
    if best_w < 0:
        return [[]], 0.0
    return best_sets, best_w


def _hardness_for(graph: MemoryGraph, claim_id: str) -> float:
    """Aggregate edge hardness for a claim: max over its hard-edge confidences.

    Used as the per-claim hardness component of the CRC score function.
    """
    h = 0.0
    for e in graph.edges:
        if e.confidence <= 0:
            continue
        if e.label not in ("contradict", "supersede"):
            continue
        if e.src == claim_id or e.dst == claim_id:
            h = max(h, e.confidence)
    return h


def truth_retrieve_beta(
    question: str,
    graph: MemoryGraph,
    canonicaliser: Canonicalizer,
    *,
    crc_table: Optional[CRCThresholdTable] = None,
    score_weights: Optional[ScoreWeights] = None,
    pmi_scale: float = 5.0,
    pmi_enabled: bool = False,
    pmi_model: Optional[str] = None,
    update_pattern_binner: Optional[Callable[[List[Claim], List[Edge]], str]] = None,
    pmi_binner: Optional[Callable[[Optional[float]], str]] = None,
    alpha: float = 0.10,
    hard_threshold: float = 2 / 3,
    parser_model: Optional[str] = None,
    fallback_to_knn: bool = True,
    knn_k: int = 6,
) -> BetaRetrievalResult:
    """β read-time path: parse → applicability gate → canonical-key fetch
    → time-filter → all-optima MWIS → S(q) score → CRC threshold → answer/abstain.

    Falls back to k-NN when (i) the question is in-scope but the canonical
    fetch returns 0 candidates and `fallback_to_knn=True`, or (ii) the
    question is out-of-scope (returns route="flat" so caller uses Flat-RAG).
    """
    weights = score_weights or ScoreWeights()
    qp = parse_query_beta(question, canonicaliser, model=parser_model)
    if not qp.get("_applicable"):
        return BetaRetrievalResult(
            route="flat",
            value=None,
            claims=[],
            discarded=[],
            score=0.0,
            group=("not_applicable",),
            pmi=None,
            vals=[],
            threshold=None,
            abstain_reason="",
            query_parse=qp,
        )

    key_str = qp["_canonical_claim_key_str"]
    asks_history = bool(qp.get("asks_history", False))
    anchor = qp.get("temporal_anchor")

    cand = _canonical_key_fetch(graph, key_str)
    cand = [c for c in cand if _valid_at(c, anchor, asks_history)]
    fallback_used = False
    if not cand and fallback_to_knn:
        # Recall-safety net: writer / parser disagreement on canonical key.
        # Logged so per-benchmark fallback_rate diagnostics can be reported.
        hits = graph.knn(question, k=knn_k, active_only=not asks_history)
        cand = [graph.claims[cid] for cid, _ in hits]
        cand = [c for c in cand if _valid_at(c, anchor, asks_history)]
        fallback_used = True
    if not cand:
        return BetaRetrievalResult(
            route="abstain",
            value=None,
            claims=[],
            discarded=[],
            score=0.0,
            group=("empty_fetch",),
            pmi=None,
            vals=[],
            threshold=None,
            abstain_reason="no_candidates_after_fetch",
            query_parse={**qp, "_fallback_used": fallback_used},
        )

    # All-optima MWIS over hard-edge subgraph
    weights_by_id: Dict[str, float] = {c.id: c.confidence for c in cand}
    cand_ids: Set[str] = {c.id for c in cand}
    hard_pairs = _hard_edges_within(graph, cand_ids, hard_threshold=hard_threshold)
    optima, _best_w = _all_optima_mwis(cand, hard_pairs, weights_by_id)

    # Vals = ⋃ {c.object_norm : c ∈ I, I ∈ Opts}
    vals: Set[str] = set()
    for opt in optima:
        for cid in opt:
            v = graph.claims[cid].object_norm.strip().lower()
            if v:
                vals.add(v)
    unique_value = (len(vals) == 1)

    # Hardness mean across the union of optima
    union_ids: Set[str] = set()
    for opt in optima:
        union_ids.update(opt)
    union_ids = union_ids or cand_ids
    hardness_mean = sum(_hardness_for(graph, cid) for cid in union_ids) / max(1, len(union_ids))

    # PMI (optional, may be None when MAAS doesn't support logprobs)
    pmi_val: Optional[float] = None
    if pmi_enabled:
        ctx = " ".join(graph.claims[cid].content for cid in list(union_ids)[:8])
        pmi_val = compute_pmi(question, ctx, model=pmi_model)
        if pmi_val is None:
            weights = weights.with_no_pmi()

    score = compute_S(
        hardness_mean=hardness_mean,
        unique_value=unique_value,
        pmi=pmi_val,
        pmi_scale=pmi_scale,
        weights=weights,
    )

    # Mondrian group at inference time
    pmi_bin = pmi_binner(pmi_val) if pmi_binner is not None else "*"
    update_pattern = (
        update_pattern_binner(cand, [Edge(src=a, dst=b, label="contradict", confidence=1.0) for a, b in hard_pairs])
        if update_pattern_binner is not None
        else "*"
    )
    group = (pmi_bin, update_pattern)

    # CRC threshold check (when table available)
    threshold: Optional[float] = None
    abstain_reason = ""
    if crc_table is not None:
        threshold = crc_table.lookup(group, alpha)
        if score < threshold or threshold == float("inf") or not unique_value:
            return BetaRetrievalResult(
                route="abstain",
                value=None,
                claims=[graph.claims[cid] for cid in union_ids],
                discarded=[],
                score=score,
                group=group,
                pmi=pmi_val,
                vals=sorted(vals),
                threshold=None if threshold == float("inf") else threshold,
                abstain_reason=(
                    "below_threshold" if score < threshold else "non_unique_value"
                ),
                query_parse={**qp, "_fallback_used": fallback_used},
            )
    else:
        # No CRC table → fall back to all-optima rule alone (Path D round-3
        # behaviour without calibration). Useful for the `no_conformal`
        # ablation and for quick smoke tests.
        if not unique_value:
            return BetaRetrievalResult(
                route="abstain",
                value=None,
                claims=[graph.claims[cid] for cid in union_ids],
                discarded=[],
                score=score,
                group=group,
                pmi=pmi_val,
                vals=sorted(vals),
                threshold=None,
                abstain_reason="non_unique_value_no_crc",
                query_parse={**qp, "_fallback_used": fallback_used},
            )

    # Answer with the unique value; surface the supporting claim subset
    # (any optimum is sufficient since they all agree on object_norm).
    chosen_set_ids = optima[0] if optima else list(union_ids)
    chosen_claims = [graph.claims[cid] for cid in chosen_set_ids]
    return BetaRetrievalResult(
        route="ttmg",
        value=next(iter(vals)) if vals else None,
        claims=chosen_claims,
        discarded=[],
        score=score,
        group=group,
        pmi=pmi_val,
        vals=sorted(vals),
        threshold=None if threshold is None else (threshold if threshold != float("inf") else None),
        abstain_reason="",
        query_parse={**qp, "_fallback_used": fallback_used},
    )


__all__ = [
    "truth_retrieve",
    "truth_retrieve_beta",
    "parse_query",
    "parse_query_beta",
    "RetrievalResult",
    "BetaRetrievalResult",
]
