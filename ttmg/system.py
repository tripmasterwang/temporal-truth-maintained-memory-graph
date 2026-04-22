"""End-to-end TTMG memory system.

Given a list of conversation sessions, ingest each turn into the graph,
then answer a question using truth-consistent retrieval + an LLM reader.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from sentence_transformers import SentenceTransformer

from .conflict_linker import link_claim
from .graph import MemoryGraph
from .maas_client import DEFAULT_MODEL, chat_text
from .schema import Claim, Provenance
from .truth_retriever import truth_retrieve, RetrievalResult
from .writer_temporal import extract_claims, extract_claims_session


@dataclass
class TTMGConfig:
    embed_model: str = "all-MiniLM-L6-v2"
    writer_model: str = DEFAULT_MODEL
    linker_model: str = DEFAULT_MODEL
    parser_model: str = DEFAULT_MODEL
    reader_model: str = DEFAULT_MODEL
    knn_k_write: int = 6
    knn_k_read: int = 8
    top_keep: int = 3
    hard_threshold: float = 0.7
    # Compute knobs
    batch_writer_per_session: bool = True  # cheap: 1 call per session
    linker_min_similarity: float = 0.65    # skip LLM linker below this cosine
    linker_candidate_k: int = 3            # top-K candidates per new claim
    linker_require_sp_overlap: bool = True # only invoke LLM linker when subject OR predicate matches
    linker_sp_overlap_min_sim: float = 0.85  # OR: extremely high cosine sim bypasses sp gate
    # Raw-turn fallback: keep an embedding index of original conversation turns
    # and surface the top-k alongside claims at read time. This recovers
    # accuracy on non-temporal slices where the writer may not have extracted
    # the relevant fact.
    raw_turn_fallback: bool = True
    raw_turn_k: int = 3
    # Pure-raw fallback: if the best claim's cosine similarity to the query
    # is below this threshold, drop the claim block entirely and let the
    # reader work from raw turns alone. Prevents noisy claims from
    # pulling the reader off a factually correct raw utterance.
    min_claim_similarity: float = 0.35
    # Ablation switches
    disable_temporal: bool = False
    disable_contradict: bool = False
    disable_consistent_subgraph: bool = False
    disable_supersede_flag: bool = False
    disable_writer_claims: bool = False  # if True, store raw turn as a single Claim
    enable_abstention: bool = True


_READER_SYS = (
    "You are a helpful assistant with access to long-term memory. "
    "Answer the user's question using ONLY the provided memory claims. "
    "If the memory is clearly insufficient, say you do not know."
)

_READER_ABSTAIN_SYS = (
    "You are a helpful assistant that values accuracy. The memory contains "
    "contradictory information about this question. Respond that you cannot "
    "answer confidently due to conflicting memory."
)

_READER_USER_TMPL = """Question: {question}

Relevant memory claims (ranked by relevance; temporal-reasoning questions should prefer these):
{claim_block}

{extra_context}

Answer concisely. Use the claim list first; if the claim list does not contain the answer, consult the raw-turn list."""


def _format_raw_block(turns: List[Dict[str, Any]]) -> str:
    if not turns:
        return "(none)"
    lines = []
    for i, t in enumerate(turns, 1):
        ts = t.get("session_ts") or "?"
        sp = t.get("speaker") or "?"
        text = (t.get("text") or "").strip().replace("\n", " ")
        lines.append(f"[{i}] ({ts}; {sp}) {text[:500]}")
    return "\n".join(lines)


def _format_claim_block(claims: List[Claim]) -> str:
    lines = []
    for i, c in enumerate(claims, 1):
        vf = c.valid_from or "?"
        vt = c.valid_to or "open"
        status = "active" if c.active else "past"
        lines.append(
            f"[{i}] ({status}; valid {vf}..{vt}; polarity={c.polarity}) {c.content}"
        )
    return "\n".join(lines) if lines else "(none)"


class TTMGSystem:
    def __init__(self, config: Optional[TTMGConfig] = None, embed_model: Optional[SentenceTransformer] = None):
        self.config = config or TTMGConfig()
        self.graph = MemoryGraph(
            embed_model_name=self.config.embed_model,
            embed_model=embed_model,
        )
        # Raw-turn fallback index (parallel to the claim graph)
        self._embed_model = self.graph._embed_model
        self._raw_turns: List[Dict[str, Any]] = []
        self._raw_emb: List[Any] = []
        self.metrics: Dict[str, Any] = {
            "writer_calls": 0,
            "linker_calls": 0,
            "parser_calls": 0,
            "reader_calls": 0,
            "abstentions": 0,
        }

    def _register_turn(self, text: str, provenance: Provenance) -> None:
        """Store the raw turn text in the fallback index."""
        import numpy as np
        if not self.config.raw_turn_fallback:
            return
        text = (text or "").strip()
        if not text:
            return
        v = self._embed_model.encode(text, normalize_embeddings=True)
        self._raw_turns.append({
            "text": text[:1000],
            "speaker": provenance.speaker,
            "session_id": provenance.session_id,
            "session_ts": provenance.session_ts,
        })
        self._raw_emb.append(np.asarray(v, dtype=np.float32))

    def _raw_knn(self, query: str, k: int) -> List[Dict[str, Any]]:
        import numpy as np
        if not self._raw_turns:
            return []
        q = np.asarray(self._embed_model.encode(query, normalize_embeddings=True), dtype=np.float32)
        mat = np.stack(self._raw_emb, axis=0)
        scores = mat @ q
        order = np.argsort(-scores)[:k]
        return [self._raw_turns[int(i)] for i in order]

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    def ingest_turn(self, text: str, provenance: Provenance) -> List[Claim]:
        cfg = self.config
        if cfg.disable_writer_claims:
            claim = Claim(
                content=text.strip()[:500],
                subject=provenance.speaker,
                predicate="",
                object="",
                valid_from=provenance.session_ts,
                polarity="assert",
                volatility="state",
                confidence=0.6,
                provenance=provenance,
            )
            new_claims = [claim] if text and text.strip() else []
        else:
            new_claims = extract_claims(text, provenance, model=cfg.writer_model)
            self.metrics["writer_calls"] += 1
        for c in new_claims:
            # Link against nearest neighbours BEFORE adding to index.
            neighbours = self.graph.knn(c.content, k=cfg.knn_k_write, active_only=False)
            cand = [self.graph.claims[cid] for cid, _ in neighbours]
            self.graph.add_claim(c)
            if not cfg.disable_contradict and cand:
                edges = link_claim(c, cand, model=cfg.linker_model, hard_threshold=cfg.hard_threshold)
                if cfg.disable_supersede_flag:
                    # Keep edges but do not actually deactivate the superseded claim
                    for e in edges:
                        if e.label == "supersede":
                            old = self.graph.claims.get(e.dst)
                            if old is not None:
                                old.active = True
                                old.superseded_by = None
                self.graph.add_edges(edges)
                self.metrics["linker_calls"] += 1
        return new_claims

    def _link_new_claim(self, c: Claim) -> None:
        cfg = self.config
        if cfg.disable_contradict:
            self.graph.add_claim(c)
            return
        neighbours = self.graph.knn(c.content, k=max(cfg.linker_candidate_k, 5), active_only=False)
        # Similarity gate: cheap skip of obviously unrelated claims
        sim_ok = [(cid, sim) for cid, sim in neighbours if sim >= cfg.linker_min_similarity]
        cand: List[Claim] = []
        new_subj = (c.subject or "").strip().lower()
        new_pred = (c.predicate or "").strip().lower()
        for cid, sim in sim_ok:
            old = self.graph.claims[cid]
            if cfg.linker_require_sp_overlap:
                s = (old.subject or "").strip().lower()
                p = (old.predicate or "").strip().lower()
                subj_match = bool(new_subj and s and (new_subj == s or new_subj in s or s in new_subj))
                pred_match = bool(new_pred and p and (new_pred == p or new_pred in p or p in new_pred))
                if not (subj_match or pred_match or sim >= cfg.linker_sp_overlap_min_sim):
                    continue
            cand.append(old)
            if len(cand) >= cfg.linker_candidate_k:
                break
        self.graph.add_claim(c)
        if not cand:
            return
        edges = link_claim(c, cand, model=cfg.linker_model, hard_threshold=cfg.hard_threshold)
        if cfg.disable_supersede_flag:
            for e in edges:
                if e.label == "supersede":
                    old = self.graph.claims.get(e.dst)
                    if old is not None:
                        old.active = True
                        old.superseded_by = None
        self.graph.add_edges(edges)
        self.metrics["linker_calls"] += 1

    def ingest_conversation(
        self,
        sessions: List[Dict[str, Any]],
        *,
        max_sessions: Optional[int] = None,
        verbose: bool = False,
    ) -> None:
        """Sessions: list of {session_id, session_ts, turns: [{speaker, text}]}."""
        cfg = self.config
        for si, sess in enumerate(sessions):
            if max_sessions is not None and si >= max_sessions:
                break
            sid = sess.get("session_id") or f"s{si}"
            sts = sess.get("session_ts")
            turns = sess.get("turns") or []
            if cfg.batch_writer_per_session and not cfg.disable_writer_claims:
                t_w = time.time()
                claims = extract_claims_session(sid, sts, turns, model=cfg.writer_model)
                dt_w = time.time() - t_w
                self.metrics["writer_calls"] += 1
                if verbose:
                    print(f"    [writer] session {sid}: {len(claims)} claims in {dt_w:.1f}s", flush=True)
                n_links = 0
                t_l = time.time()
                for c in claims:
                    had = len(self.graph.edges)
                    self._link_new_claim(c)
                    n_links += len(self.graph.edges) - had
                dt_l = time.time() - t_l
                if verbose:
                    print(f"    [linker] session {sid}: {n_links} edges in {dt_l:.1f}s (cumul_metrics={self.metrics})", flush=True)
                # Also index raw turns (cheap, no LLM call)
                for ti, t in enumerate(turns):
                    if not isinstance(t, dict):
                        continue
                    self._register_turn(
                        (t.get("text") or ""),
                        Provenance(
                            session_id=sid, turn_id=ti,
                            speaker=(t.get("speaker") or "user"),
                            session_ts=sts,
                        ),
                    )
            else:
                for ti, t in enumerate(turns):
                    if not isinstance(t, dict):
                        continue
                    text = (t.get("text") or "").strip()
                    if not text:
                        continue
                    speaker = t.get("speaker") or "user"
                    prov = Provenance(session_id=sid, turn_id=ti, speaker=speaker, session_ts=sts)
                    self.ingest_turn(text, prov)
                    self._register_turn(text, prov)
            if verbose:
                print(f"[ingest] session {sid}: graph stats={self.graph.stats()}")

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def answer(self, question: str) -> Dict[str, Any]:
        cfg = self.config
        t0 = time.time()
        rr: RetrievalResult = truth_retrieve(
            question,
            self.graph,
            k=cfg.knn_k_read,
            top_keep=cfg.top_keep,
            hard_threshold=cfg.hard_threshold,
            disable_temporal=cfg.disable_temporal,
            disable_contradict=cfg.disable_contradict,
            disable_consistent_subgraph=cfg.disable_consistent_subgraph,
            enable_abstention=cfg.enable_abstention,
            model=cfg.parser_model,
        )
        if not cfg.disable_temporal:
            self.metrics["parser_calls"] += 1
        t_retrieve = time.time() - t0

        # Abstain path
        if rr.should_abstain:
            self.metrics["abstentions"] += 1
            reply = "I don't know — my memory contains conflicting information about this."
            return {
                "answer": reply,
                "abstain": True,
                "retrieved": [c.to_dict() for c in rr.claims],
                "query_parse": rr.query_parse,
                "retrieve_time": t_retrieve,
                "reader_time": 0.0,
            }

        qp = rr.query_parse if isinstance(rr.query_parse, dict) else {}
        # Low-similarity fallback: if the best retrieved claim has cosine
        # below the threshold, the claim graph likely has nothing relevant
        # and the reader should work from raw turns only (behaves as Flat RAG).
        best_sim = float(qp.get("_best_claim_sim", 1.0))
        claim_block = _format_claim_block(rr.claims) if best_sim >= cfg.min_claim_similarity else "(none)"
        raw_block = ""
        intent = qp.get("intent")
        asks_history = bool(qp.get("asks_history", False))
        # Narrow temporal gate: exclude raw turns only for "what/when is currently"
        # questions (intent=temporal_reasoning and NOT asks_history). For history
        # recall (asks_history=True) we keep raw turns because original wording
        # is useful. We also cross-check with a lexical heuristic so the parser
        # cannot silently drop us off the claim-only path.
        q_lower = question.lower()
        _temporal_keywords = (
            " when ", " what time ", " what date ", " how long ago",
            " last ", " latest ", " current ", " currently ", " now ",
            " ago ", " since ", " until ", " before ", " after ",
            " yesterday", " today", " tomorrow",
        )
        lexical_temporal = any(k in " " + q_lower + " " for k in _temporal_keywords)
        temporal_question = (
            ((intent == "temporal_reasoning") or lexical_temporal)
            and not asks_history
        )
        # Always include raw turns when the claim block is empty (low-sim
        # fallback), regardless of the temporal gate.
        force_raw = best_sim < cfg.min_claim_similarity
        if cfg.raw_turn_fallback and self._raw_turns and (not temporal_question or force_raw):
            raw_hits = self._raw_knn(question, cfg.raw_turn_k)
            raw_block = "Raw-turn fallback (ranked by relevance; use when claims are insufficient):\n" \
                        + _format_raw_block(raw_hits)
        prompt = _READER_USER_TMPL.format(
            question=question.strip(),
            claim_block=claim_block,
            extra_context=raw_block,
        )
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
            "retrieved": [c.to_dict() for c in rr.claims],
            "query_parse": rr.query_parse,
            "retrieve_time": t_retrieve,
            "reader_time": t_read,
        }


__all__ = ["TTMGConfig", "TTMGSystem"]
