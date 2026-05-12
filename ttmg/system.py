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

from .canonicalize import Canonicalizer
from .conflict_linker import link_claim, link_claim_3call
from .crc import CRCThresholdTable, ScoreWeights
from .graph import MemoryGraph
from .maas_client import DEFAULT_MODEL, chat_text
from .schema import Claim, Provenance
from .truth_retriever import (
    BetaRetrievalResult,
    RetrievalResult,
    truth_retrieve,
    truth_retrieve_beta,
)
from .writer_temporal import (
    extract_claims,
    extract_claims_session,
    extract_claims_session_beta,
)


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

    # ------------------------------------------------------------------
    # β round-2 (Pivot β v2) flags. All default-off for backward compat.
    # ------------------------------------------------------------------
    enable_beta: bool = False
    enable_beta_writer: bool = False  # use 3-field claim_key writer
    enable_beta_linker: bool = False  # use 3-call agreement linker
    enable_pmi: bool = False          # require MAAS logprobs support
    crc_table_path: Optional[str] = None  # JSON path; load with CRCThresholdTable
    crc_alpha: float = 0.10
    score_w_h: float = 0.5
    score_w_u: float = 0.3
    score_w_p: float = 0.2
    pmi_scale: float = 5.0
    pmi_model: Optional[str] = None
    # β ablation switches
    beta_no_groups: bool = False      # marginal CP (single bin) vs Mondrian
    beta_no_canonical_key: bool = False  # always use sp_key fallback
    beta_no_3call: bool = False       # use single-call linker even when β on

    # ------------------------------------------------------------------
    # CalLB reranker flags (default-off for backward compat)
    # ------------------------------------------------------------------
    enable_callb: bool = False
    callb_model_path: Optional[str] = None   # path to saved LBReranker JSON
    callb_crc_path: Optional[str] = None     # path to saved LBCRCTable JSON
    callb_alpha: float = 0.10                # CRC contamination level
    callb_k_per_substrate: int = 10          # candidates per substrate
    callb_max_candidates: int = 30           # cap on candidate pool


_READER_SYS = (
    "You are a helpful assistant with access to long-term memory. "
    "Answer the user's question using the provided memory. The memory "
    "comes in two forms: a ranked list of structured CLAIMS (self-"
    "contained paraphrases of user/assistant statements, each with a "
    "validity interval and polarity) and, when provided, a ranked list "
    "of RAW TURNS (verbatim conversation snippets). Prefer the claim "
    "list for current-fact and current-state questions; use the raw-"
    "turn list when the question asks about assistant-authored content, "
    "specific named entities, exact numeric values, or preference "
    "reasoning that requires combining multiple statements. Only say "
    "'I do not know' if neither source contains the answer."
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
            # β-only counters
            "beta_route_ttmg": 0,
            "beta_route_flat": 0,
            "beta_route_abstain": 0,
            "beta_fallback_used": 0,
        }
        # β state (None unless enable_beta=True)
        self.canonicaliser: Optional[Canonicalizer] = None
        self.crc_table: Optional[CRCThresholdTable] = None
        # CalLB state (None unless enable_callb=True and model files exist)
        self._callb_model: Optional[Any] = None
        self._callb_feature_names: Optional[List[str]] = None
        self._callb_crc_table: Optional[Any] = None
        if self.config.enable_callb:
            from pathlib import Path as _Path
            if self.config.callb_model_path and _Path(self.config.callb_model_path).exists():
                from .lb_model import load as _lb_load
                self._callb_model, self._callb_feature_names = _lb_load(
                    self.config.callb_model_path
                )
            if self.config.callb_crc_path and _Path(self.config.callb_crc_path).exists():
                from .lb_crc import LBCRCTable as _LBCRCTable
                self._callb_crc_table = _LBCRCTable.load(self.config.callb_crc_path)
        if self.config.enable_beta:
            self.canonicaliser = Canonicalizer()
            if self.config.crc_table_path:
                try:
                    self.crc_table = CRCThresholdTable.from_file(
                        self.config.crc_table_path
                    )
                except FileNotFoundError:
                    self.crc_table = None

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
        if cfg.enable_beta and cfg.enable_beta_linker and not cfg.beta_no_3call:
            edges = link_claim_3call(
                c, cand, model=cfg.linker_model, hard_threshold=2 / 3
            )
            self.metrics["linker_calls"] += 3  # three independent calls per pair-batch
        else:
            edges = link_claim(
                c, cand, model=cfg.linker_model, hard_threshold=cfg.hard_threshold
            )
            self.metrics["linker_calls"] += 1
        if cfg.disable_supersede_flag:
            for e in edges:
                if e.label == "supersede":
                    old = self.graph.claims.get(e.dst)
                    if old is not None:
                        old.active = True
                        old.superseded_by = None
        self.graph.add_edges(edges)

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
                if cfg.enable_beta and cfg.enable_beta_writer and self.canonicaliser is not None:
                    claims = extract_claims_session_beta(
                        sid, sts, turns, self.canonicaliser, model=cfg.writer_model
                    )
                else:
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
    def answer(self, question: str, ts_q: Optional[str] = None) -> Dict[str, Any]:
        cfg = self.config
        if cfg.enable_callb and self._callb_model is not None and self._callb_crc_table is not None:
            return self._answer_callb(question, ts_q=ts_q)
        if cfg.enable_beta and self.canonicaliser is not None:
            return self._answer_beta(question)
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
        # Always include raw turns as a secondary source. For clearly temporal
        # current-state questions we keep the preference for claims (the
        # temporal gate); for everything else raw turns are presented
        # alongside the claim list so the reader can combine them.
        force_raw = best_sim < cfg.min_claim_similarity
        if cfg.raw_turn_fallback and self._raw_turns:
            # Skip raw turns only when we are confident the question is a
            # pure temporal-current query (temporal_question=True) and the
            # claim retrieval is confident (best_sim high).
            skip_raw = temporal_question and not force_raw and best_sim >= 0.55
            if not skip_raw:
                raw_hits = self._raw_knn(question, cfg.raw_turn_k)
                raw_block = "Raw-turn context (ranked by relevance; use for named entities, numeric values, preference reasoning, or when claims are insufficient):\n" \
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


    # ------------------------------------------------------------------
    # CalLB read-time path
    # ------------------------------------------------------------------
    def _answer_callb(self, question: str, ts_q: Optional[str] = None) -> Dict[str, Any]:
        import numpy as np
        from .lb_features import FEATURE_NAMES_FULL, extract_features
        from .lb_model import score as _lb_score
        from .lb_retrieval import gather_candidates

        cfg = self.config
        t0 = time.time()

        # Step 1: gather multi-substrate candidates
        cands = gather_candidates(
            question, self,
            k_per_substrate=cfg.callb_k_per_substrate,
            max_candidates=cfg.callb_max_candidates,
        )
        if not cands:
            return self._callb_flat_fallback(question, t0)

        # Step 2: extract 13-d features
        feat_names = self._callb_feature_names or list(FEATURE_NAMES_FULL)
        X = np.stack([
            extract_features(question, c, self.graph, ts_q=ts_q, feature_names=tuple(feat_names))
            for c in cands
        ])

        # Step 3: score with MLP
        s = _lb_score(self._callb_model, X)

        # Step 4: apply CRC threshold
        lam = self._callb_crc_table.threshold(cfg.callb_alpha)
        if np.isinf(lam):
            tier_mask = np.zeros(len(s), dtype=bool)
        else:
            tier_mask = s >= lam
        tier = [c for c, m in zip(cands, tier_mask) if m]
        tier_fallback = False
        if not tier:
            # Non-vacuity fallback: take top-3 by score
            top_k = min(3, len(cands))
            order = np.argsort(-s)[:top_k]
            tier = [cands[int(i)] for i in order]
            tier_fallback = True

        t_retrieve = time.time() - t0

        # Step 5: format tier for reader
        claim_obj = [c.claim for c in tier if c.source_type == "claim" and c.claim is not None]
        claim_block = _format_claim_block(claim_obj) if claim_obj else "(none)"
        raw_dicts = [c.raw_turn for c in tier if c.source_type == "raw-turn" and c.raw_turn is not None]
        raw_block = ""
        if raw_dicts:
            raw_block = "Raw-turn context (CalLB load-bearing tier):\n" + _format_raw_block(raw_dicts)

        prompt = _READER_USER_TMPL.format(
            question=question.strip(),
            claim_block=claim_block,
            extra_context=raw_block,
        )
        t1 = time.time()
        reply = chat_text(
            prompt, system=_READER_SYS, model=cfg.reader_model,
            temperature=0.0, max_tokens=300, retries=2,
        )
        t_read = time.time() - t1
        self.metrics["reader_calls"] += 1
        return {
            "answer": reply.strip(),
            "abstain": False,
            "route": "callb",
            "callb_tier_size": len(tier),
            "callb_threshold": (float(lam) if not np.isinf(lam) else None),
            "callb_tier_fallback": tier_fallback,
            "callb_alpha": cfg.callb_alpha,
            "callb_n_candidates": len(cands),
            "retrieved": [
                {"id": c.id, "content": c.content, "source_type": c.source_type,
                 "in_tier": bool(m), "score": float(sc)}
                for c, m, sc in zip(cands, tier_mask, s)
            ],
            "retrieve_time": t_retrieve,
            "reader_time": t_read,
        }

    def _callb_flat_fallback(self, question: str, t0: float) -> Dict[str, Any]:
        cfg = self.config
        t_retrieve = time.time() - t0
        raw_hits = self._raw_knn(question, cfg.raw_turn_k) if self._raw_turns else []
        raw_block = "Raw-turn context:\n" + (_format_raw_block(raw_hits) if raw_hits else "(none)")
        prompt = _READER_USER_TMPL.format(
            question=question.strip(),
            claim_block="(none — no candidates gathered)",
            extra_context=raw_block,
        )
        t1 = time.time()
        reply = chat_text(
            prompt, system=_READER_SYS, model=cfg.reader_model,
            temperature=0.0, max_tokens=300, retries=2,
        )
        t_read = time.time() - t1
        self.metrics["reader_calls"] += 1
        return {
            "answer": reply.strip(),
            "abstain": False,
            "route": "callb_flat_fallback",
            "callb_tier_size": 0,
            "callb_n_candidates": 0,
            "retrieve_time": t_retrieve,
            "reader_time": t_read,
        }

    # ------------------------------------------------------------------
    # β read-time path
    # ------------------------------------------------------------------
    def _answer_beta(self, question: str) -> Dict[str, Any]:
        cfg = self.config
        assert self.canonicaliser is not None
        t0 = time.time()
        # In `beta_no_groups` ablation we use a constant binner → marginal CP.
        if cfg.beta_no_groups:
            pmi_binner = lambda _v: "*"
            update_pattern_binner = lambda _c, _e: "*"
        else:
            pmi_binner = self._pmi_bin
            update_pattern_binner = self._update_pattern_bin

        weights = ScoreWeights(
            w_h=cfg.score_w_h, w_u=cfg.score_w_u, w_p=cfg.score_w_p
        )
        rr: BetaRetrievalResult = truth_retrieve_beta(
            question,
            self.graph,
            self.canonicaliser,
            crc_table=self.crc_table,
            score_weights=weights,
            pmi_scale=cfg.pmi_scale,
            pmi_enabled=cfg.enable_pmi,
            pmi_model=cfg.pmi_model,
            update_pattern_binner=update_pattern_binner,
            pmi_binner=pmi_binner,
            alpha=cfg.crc_alpha,
            parser_model=cfg.parser_model,
        )
        self.metrics["parser_calls"] += 1
        t_retrieve = time.time() - t0
        if rr.query_parse.get("_fallback_used"):
            self.metrics["beta_fallback_used"] += 1

        if rr.route == "flat":
            self.metrics["beta_route_flat"] += 1
            return self._flat_fallback(question, rr.query_parse, t_retrieve)
        if rr.route == "abstain":
            self.metrics["beta_route_abstain"] += 1
            self.metrics["abstentions"] += 1
            return {
                "answer": "I don't know — my memory is not confident enough to answer.",
                "abstain": True,
                "route": "abstain",
                "score": rr.score,
                "threshold": rr.threshold,
                "group": list(rr.group),
                "vals": rr.vals,
                "abstain_reason": rr.abstain_reason,
                "retrieved": [c.to_dict() for c in rr.claims],
                "query_parse": rr.query_parse,
                "retrieve_time": t_retrieve,
                "reader_time": 0.0,
            }
        # route == "ttmg"
        self.metrics["beta_route_ttmg"] += 1
        claim_block = _format_claim_block(rr.claims)
        prompt = _READER_USER_TMPL.format(
            question=question.strip(),
            claim_block=claim_block,
            extra_context=(
                f"The CRC layer has a unique surviving normalised value: {rr.value!r}. "
                "Answer the question using this value."
            ),
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
            "route": "ttmg",
            "score": rr.score,
            "threshold": rr.threshold,
            "group": list(rr.group),
            "value": rr.value,
            "vals": rr.vals,
            "retrieved": [c.to_dict() for c in rr.claims],
            "query_parse": rr.query_parse,
            "retrieve_time": t_retrieve,
            "reader_time": t_read,
        }

    def _flat_fallback(
        self, question: str, query_parse: Dict[str, Any], t_retrieve: float
    ) -> Dict[str, Any]:
        """When β routes a query out-of-scope, fall back to raw-turn RAG."""
        cfg = self.config
        raw_hits = self._raw_knn(question, cfg.raw_turn_k) if self._raw_turns else []
        raw_block = "Raw-turn context:\n" + (_format_raw_block(raw_hits) if raw_hits else "(none)")
        prompt = _READER_USER_TMPL.format(
            question=question.strip(),
            claim_block="(none — out of TTMG scope)",
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
            "route": "flat",
            "retrieved": [],
            "query_parse": query_parse,
            "retrieve_time": t_retrieve,
            "reader_time": t_read,
        }

    # ------------------------------------------------------------------
    # β Mondrian binners (overridable; default rules pre-frozen on dev)
    # ------------------------------------------------------------------
    _pmi_bin_low: float = -1.0
    _pmi_bin_high: float = 1.0

    def _pmi_bin(self, pmi: Optional[float]) -> str:
        if pmi is None:
            return "mid"
        if pmi < self._pmi_bin_low:
            return "low"
        if pmi >= self._pmi_bin_high:
            return "high"
        return "mid"

    def _update_pattern_bin(
        self, candidates: List[Claim], hard_edges: List[Any]
    ) -> str:
        """Inference-time pattern label from observable graph features."""
        n_supersede = sum(
            1
            for e in self.graph.edges
            if e.label == "supersede" and e.confidence >= 2 / 3
        )
        active_vals = {c.object_norm for c in candidates if c.active and c.object_norm}
        n_active_values = len(active_vals)
        n_temporal_updates = len({c.valid_from for c in candidates if c.valid_from})
        conflict_degree = len(hard_edges)
        if n_supersede >= 2 or (n_active_values >= 2 and conflict_degree >= 1):
            return "supersede_heavy"
        if n_temporal_updates >= 2 and n_supersede <= 1:
            return "multi_update"
        return "single_trace"

    def set_pmi_bins(self, low: float, high: float) -> None:
        """Override default PMI bin boundaries with dev-tuned values."""
        self._pmi_bin_low = low
        self._pmi_bin_high = high


__all__ = ["TTMGConfig", "TTMGSystem"]
