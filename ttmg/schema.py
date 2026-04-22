"""Claim-level schema for the Temporal Truth-Maintained Memory Graph (TTMG).

A *claim* is the atomic memory unit. A raw utterance may yield zero or more
claims. Each claim carries:
  - `content`: natural-language statement
  - `subject`, `predicate`, `object`: shallow triple for indexing (optional)
  - `valid_from`, `valid_to`: ISO-8601 strings or None (open-ended)
  - `provenance`: session_id + turn_id + speaker
  - `confidence`: writer's confidence in the claim (0.0–1.0)
  - `polarity`: "assert" or "deny"
  - `volatility`: "stable" (biographical facts) | "preference" (changeable) |
                  "state" (short-lived)

Edges in the graph represent one of four labels:
  - `support`: two claims make the same assertion
  - `contradict`: two claims disagree (same subject+predicate, incompatible object)
  - `supersede`: a claim invalidates an earlier one (same (s,p), later `valid_from`)
  - `unrelated`: default; usually not materialised
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

EDGE_LABELS = ("support", "contradict", "supersede", "unrelated")
VOLATILITY = ("stable", "preference", "state")
POLARITY = ("assert", "deny")


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class Provenance:
    session_id: str = ""
    turn_id: int = -1
    speaker: str = "user"
    session_ts: Optional[str] = None  # original-scene timestamp (if given)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Claim:
    content: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    subject: str = ""
    predicate: str = ""
    object: str = ""
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    polarity: str = "assert"
    volatility: str = "state"
    confidence: float = 0.7
    provenance: Provenance = field(default_factory=Provenance)
    created_at: str = field(default_factory=_now_iso)
    # Indexing scaffolding
    keywords: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    # Truth-maintenance status
    active: bool = True  # may be set False if a later claim supersedes it
    superseded_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Claim":
        prov_d = d.get("provenance") or {}
        if isinstance(prov_d, dict):
            prov = Provenance(**prov_d)
        else:
            prov = Provenance()
        data = {k: v for k, v in d.items() if k != "provenance"}
        return Claim(provenance=prov, **data)

    def sp_key(self) -> str:
        """Shallow (subject, predicate) key used for grouping updates."""
        return f"{self.subject.strip().lower()}||{self.predicate.strip().lower()}"

    def overlaps(self, other: "Claim") -> bool:
        """Do the validity intervals overlap? Open-ended sides treated as infinity."""
        a0 = self.valid_from or "0000"
        a1 = self.valid_to or "9999"
        b0 = other.valid_from or "0000"
        b1 = other.valid_to or "9999"
        return not (a1 < b0 or b1 < a0)


@dataclass
class Edge:
    src: str
    dst: str
    label: str  # one of EDGE_LABELS
    confidence: float = 0.0
    rationale: str = ""
    created_at: str = field(default_factory=_now_iso)

    def is_hard(self, hard_threshold: float = 0.75) -> bool:
        return self.confidence >= hard_threshold

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


__all__ = [
    "Claim",
    "Edge",
    "Provenance",
    "EDGE_LABELS",
    "VOLATILITY",
    "POLARITY",
]
