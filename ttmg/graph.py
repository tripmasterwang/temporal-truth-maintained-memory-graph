"""In-memory graph store for claims + edges.

Backed by a dict of `Claim` objects, a list of `Edge` objects, and a
sentence-transformer index (numpy-backed FAISS-free k-NN) for cheap
nearest-neighbour search at write and read time.
"""

from __future__ import annotations

import json
import os
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None  # type: ignore

from .schema import Claim, Edge


class MemoryGraph:
    def __init__(
        self,
        embed_model_name: str = "all-MiniLM-L6-v2",
        embed_model: Optional["SentenceTransformer"] = None,
    ):
        self.claims: Dict[str, Claim] = {}
        self.edges: List[Edge] = []
        self._emb: Dict[str, np.ndarray] = {}
        self._embed_model_name = embed_model_name
        if embed_model is not None:
            self._embed_model = embed_model
        else:
            if SentenceTransformer is None:
                raise RuntimeError("sentence-transformers is required for MemoryGraph")
            self._embed_model = SentenceTransformer(embed_model_name)

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------
    def add_claim(self, claim: Claim) -> None:
        self.claims[claim.id] = claim
        v = self._embed_model.encode(claim.content, normalize_embeddings=True)
        self._emb[claim.id] = np.asarray(v, dtype=np.float32)

    def add_edges(self, edges: List[Edge]) -> None:
        self.edges.extend(edges)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def knn(self, query: str, k: int = 8, active_only: bool = False) -> List[Tuple[str, float]]:
        if not self.claims:
            return []
        q = self._embed_model.encode(query, normalize_embeddings=True)
        q = np.asarray(q, dtype=np.float32)
        ids = list(self.claims.keys())
        if active_only:
            ids = [i for i in ids if self.claims[i].active]
        if not ids:
            return []
        mat = np.stack([self._emb[i] for i in ids], axis=0)
        scores = mat @ q
        order = np.argsort(-scores)[:k]
        return [(ids[i], float(scores[i])) for i in order]

    # ------------------------------------------------------------------
    # Helpers for retrievers
    # ------------------------------------------------------------------
    def edges_for(self, claim_id: str) -> List[Edge]:
        return [e for e in self.edges if e.src == claim_id or e.dst == claim_id]

    def contradict_set(self, claim_id: str, hard_threshold: float = 0.7) -> List[str]:
        out = []
        for e in self.edges:
            if e.label != "contradict" or e.confidence < hard_threshold:
                continue
            if e.src == claim_id:
                out.append(e.dst)
            elif e.dst == claim_id:
                out.append(e.src)
        return out

    def superseded_by(self, claim_id: str) -> Optional[str]:
        c = self.claims.get(claim_id)
        return c.superseded_by if c else None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "claims": {cid: c.to_dict() for cid, c in self.claims.items()},
            "edges": [e.to_dict() for e in self.edges],
            "emb_keys": list(self._emb.keys()),
            "embed_model_name": self._embed_model_name,
        }
        with open(path + ".json", "w") as fh:
            json.dump(data, fh, ensure_ascii=False)
        np.savez(
            path + ".emb.npz",
            **{k: v for k, v in self._emb.items()},
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------
    def stats(self) -> Dict[str, int]:
        by_label: Dict[str, int] = {}
        for e in self.edges:
            by_label[e.label] = by_label.get(e.label, 0) + 1
        active = sum(1 for c in self.claims.values() if c.active)
        return {
            "claims": len(self.claims),
            "active_claims": active,
            "edges": len(self.edges),
            **{f"edges_{k}": v for k, v in by_label.items()},
        }


__all__ = ["MemoryGraph"]
