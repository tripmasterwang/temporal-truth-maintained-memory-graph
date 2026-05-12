"""CalLB feature extraction.

For each (query, candidate item) pair, compute the 13-feature vector:

  Portable (5):
    semantic_sim         — cosine(query, content)
    lexical_sim_bm25     — BM25 score
    cross_substrate_agreement — count over {sem, lex, claim, raw} substrates
    recency_baseline     — Δt_since_creation (raw days, normalized)
    source_type          — one-hot (raw-turn=0, claim=1)

  Robustness (3):
    max_substrate_score          — max over normalized substrate scores
    singleton_raw_turn_hit       — 1 iff item ∈ raw-topk AND ∉ any other top-k
    entity_overlap               — Jaccard of entity-like tokens (length ≥ 4)

  TTMG-specific (5):
    claim_graph_relevance        — substrate('claim') score (0 for raw-turn)
    supersede_edge_count         — # supersede edges *into* this claim
    validity_interval_freshness  — 1 if valid_at(τ_q), else exp-decay
    contradiction_count          — # hard-contradict edges incident
    time_volatility              — Δt_since_creation × topic-volatility (proxy)

We intentionally make features deterministic given (q, item, graph). No LLM
calls in this module (LLM-judge runs only at calibration-time labelling).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

from .schema import Claim


_LME_DATE_RE = re.compile(
    r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})"           # YYYY-MM-DD or YYYY/MM/DD
    r"(?:\s*\([A-Za-z]+\))?"                       # optional " (Mon)" weekday
    r"(?:[T\s]+(\d{1,2}):(\d{2})(?::(\d{2}))?)?"   # optional HH:MM[:SS]
)


FEATURE_NAMES_FULL = (
    "semantic_sim",
    "lexical_sim_bm25",
    "cross_substrate_agreement",
    "recency_baseline",
    "source_type",
    "max_substrate_score",
    "singleton_raw_turn_hit",
    "entity_overlap",
    "claim_graph_relevance",
    "supersede_edge_count",
    "validity_interval_freshness",
    "contradiction_count",
    "time_volatility",
)

# Portable subset (5 portable + 3 robustness = 8) — drop the 5 TTMG features.
FEATURE_NAMES_PORTABLE = (
    "semantic_sim",
    "lexical_sim_bm25",
    "cross_substrate_agreement",
    "recency_baseline",
    "source_type",
    "max_substrate_score",
    "singleton_raw_turn_hit",
    "entity_overlap",
)


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    """Parse a timestamp into a UTC-aware datetime.

    Accepts ISO 8601 ("YYYY-MM-DD" or "YYYY-MM-DDTHH:MM:SS[±HH:MM|Z]") and
    LongMemEval-S' "YYYY/MM/DD (Wed) HH:MM" format. Returns None on failure.
    """
    if not ts:
        return None
    # Try ISO first (cheap path).
    try:
        if "T" in ts:
            s = ts.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
    except Exception:
        pass
    # Generic regex covers ISO YYYY-MM-DD and LME-S YYYY/MM/DD (DOW) HH:MM.
    m = _LME_DATE_RE.search(ts.strip())
    if not m:
        return None
    y, mo, d, h, mi, se = m.groups()
    try:
        return datetime(
            int(y), int(mo), int(d),
            int(h) if h else 0,
            int(mi) if mi else 0,
            int(se) if se else 0,
            tzinfo=timezone.utc,
        )
    except Exception:
        return None


def _now_or(ts_q: Optional[str]) -> datetime:
    """Reference time τ_q for recency / validity. Use the question's anchor
    if provided, else the current wall clock."""
    parsed = _parse_iso(ts_q)
    return parsed or datetime.now(timezone.utc)


def _delta_days(ref: datetime, ts: Optional[str]) -> float:
    """Days from `ts` to `ref`. Negative if `ts` > `ref`. None / unparseable → 0."""
    parsed = _parse_iso(ts)
    if parsed is None:
        return 0.0
    return (ref - parsed).total_seconds() / 86400.0


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _entity_like_tokens(text: str) -> set:
    """Tokens of length ≥ 4 — proxy for named entities without spaCy.

    We deliberately keep this dependency-free. spaCy NER would be a stronger
    signal but adds a heavy dependency for marginal lift.
    """
    return {t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) >= 4}


def _entity_overlap(question: str, content: str) -> float:
    q = _entity_like_tokens(question)
    c = _entity_like_tokens(content)
    if not q or not c:
        return 0.0
    inter = q & c
    union = q | c
    return float(len(inter)) / float(len(union))


def _validity_freshness(claim: Optional[Claim], ref: datetime, decay_days: float = 30.0) -> float:
    """1 if claim is valid_at(ref); exponential decay otherwise (or beyond
    valid_to). 0 baseline for non-claim items handled by caller."""
    if claim is None:
        return 0.0
    vf = _parse_iso(claim.valid_from)
    vt = _parse_iso(claim.valid_to)
    if vf is None and vt is None:
        # No interval recorded → treat as active (claim graph fallback).
        return 1.0 if claim.active else 0.5
    if vf is not None and ref < vf:
        # Future-valid: exp-decay by how far in the future.
        days = (vf - ref).total_seconds() / 86400.0
        return math.exp(-days / decay_days)
    if vt is not None and ref > vt:
        # Past-valid: exp-decay by how far past.
        days = (ref - vt).total_seconds() / 86400.0
        return math.exp(-days / decay_days)
    return 1.0


def _topic_volatility_proxy(subject: Optional[str]) -> float:
    """Proxy for topic_volatility(subject) without an external classifier.

    Uses the claim's volatility tag (set by the writer): preference→0.7,
    state→0.5, stable→0.2. Falls back to 0.5 when subject unknown.
    Higher = more volatile = more drift signal.
    """
    return 0.5  # caller will read claim.volatility directly; this stub used only when subject given alone


def _volatility_weight(claim: Optional[Claim]) -> float:
    if claim is None:
        return 0.5
    v = (claim.volatility or "").lower()
    return {"preference": 0.7, "state": 0.5, "stable": 0.2}.get(v, 0.5)


def _supersede_count(claim_id: str, graph) -> int:
    return sum(1 for e in graph.edges if e.label == "supersede" and e.dst == claim_id)


def _contradiction_count(claim_id: str, graph, hard_threshold: float = 0.7) -> int:
    n = 0
    for e in graph.edges:
        if e.label != "contradict" or e.confidence < hard_threshold:
            continue
        if e.src == claim_id or e.dst == claim_id:
            n += 1
    return n


def extract_features(
    question: str,
    candidate,                # CandidateItem from lb_retrieval
    graph,                    # MemoryGraph
    *,
    ts_q: Optional[str] = None,
    feature_names: tuple = FEATURE_NAMES_FULL,
    recency_norm_days: float = 365.0,
) -> np.ndarray:
    """Return the feature vector in the order specified by `feature_names`.

    `ts_q` is the question-time anchor (e.g., LongMemEval-S `question_date`)
    used for validity / recency computation. Falls back to `datetime.now()`.
    """
    ref = _now_or(ts_q)
    claim = candidate.claim
    is_claim = candidate.source_type == "claim"

    # Portable signals
    sem = candidate.score.get("semantic")
    lex = candidate.score.get("lexical")
    sem_v = float(sem) if sem is not None else 0.0
    lex_v = float(lex) if lex is not None else 0.0
    agree = int(sum(1 for v in candidate.in_topk.values() if v))

    # Recency: use the conversation timestamp (when the claim was *uttered*),
    # NOT `claim.created_at` (which is the writer's wall-clock when the claim
    # was extracted). For claims this is `provenance.session_ts`; falls back
    # to `valid_from` then `created_at` if missing.
    if is_claim and claim is not None:
        prov_ts = (claim.provenance.session_ts if claim.provenance else None)
        ts_for_recency = prov_ts or claim.valid_from or claim.created_at
        days = _delta_days(ref, ts_for_recency)
    elif candidate.raw_turn is not None:
        days = _delta_days(ref, candidate.raw_turn.get("session_ts"))
    else:
        days = 0.0
    recency = max(0.0, days) / recency_norm_days  # normalized [0, ~1+]

    src = 1.0 if is_claim else 0.0

    # Robustness
    norm_scores = []
    if sem is not None:
        norm_scores.append(float(sem))
    if lex is not None:
        # BM25 scores are unbounded; squash for max-pooling fairness.
        norm_scores.append(min(1.0, float(lex) / 20.0))
    cl = candidate.score.get("claim")
    if cl is not None:
        norm_scores.append(float(cl))
    rs = candidate.score.get("raw")
    if rs is not None:
        norm_scores.append(float(rs))
    max_sub = max(norm_scores) if norm_scores else 0.0

    singleton_raw = 0.0
    if candidate.in_topk.get("raw") and not any(
        candidate.in_topk.get(s) for s in ("semantic", "lexical", "claim")
    ):
        singleton_raw = 1.0

    ent_overlap = _entity_overlap(question, candidate.content)

    # TTMG signals (0 if not a claim)
    if is_claim and claim is not None:
        cgr = float(candidate.score.get("claim") or 0.0)
        sup_n = float(_supersede_count(claim.id, graph))
        valid_fresh = _validity_freshness(claim, ref)
        contra_n = float(_contradiction_count(claim.id, graph))
        vol_w = _volatility_weight(claim)
        time_vol = (max(0.0, days) / recency_norm_days) * vol_w
    else:
        cgr = 0.0
        sup_n = 0.0
        valid_fresh = 0.0
        contra_n = 0.0
        time_vol = 0.0

    feature_dict: Dict[str, float] = {
        "semantic_sim": sem_v,
        "lexical_sim_bm25": lex_v,
        "cross_substrate_agreement": float(agree),
        "recency_baseline": recency,
        "source_type": src,
        "max_substrate_score": max_sub,
        "singleton_raw_turn_hit": singleton_raw,
        "entity_overlap": ent_overlap,
        "claim_graph_relevance": cgr,
        "supersede_edge_count": sup_n,
        "validity_interval_freshness": valid_fresh,
        "contradiction_count": contra_n,
        "time_volatility": time_vol,
    }
    vec = np.asarray([feature_dict[n] for n in feature_names], dtype=np.float32)
    return vec


def feature_dim(feature_names: tuple = FEATURE_NAMES_FULL) -> int:
    return len(feature_names)
