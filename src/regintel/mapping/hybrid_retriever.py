
"""
Hybrid policy retrieval using BM25, pgvector and RRF.

BM25: lexical retrieval
pgvector: semantic retrieval
RRF: combines ranked candidate lists

A retrieved match is not proof of regulatory compliance.
"""

from dataclasses import dataclass

from regintel.mapping.bm25_retriever import BM25PolicyRetriever
from regintel.mapping.vector_retriever import VectorPolicyRetriever


@dataclass
class HybridPolicyMatch:
    policy_section_id: str
    section_number: str
    section_title: str
    policy_text: str
    rrf_score: float
    bm25_rank: int | None
    vector_rank: int | None
    retrieval_sources: list[str]


def reciprocal_rank_fusion(
    bm25_matches,
    vector_matches,
    top_k: int = 5,
    rrf_k: int = 60,
) -> list[HybridPolicyMatch]:

    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    if rrf_k < 1:
        raise ValueError("rrf_k must be >= 1")

    candidates = {}

    for rank, match in enumerate(bm25_matches, start=1):
        section_id = match.policy_section_id

        if section_id not in candidates:
            candidates[section_id] = {
                "match": match,
                "score": 0.0,
                "bm25_rank": None,
                "vector_rank": None,
                "sources": [],
            }

        candidates[section_id]["score"] += (
            1.0 / (rrf_k + rank)
        )

        candidates[section_id]["bm25_rank"] = rank
        candidates[section_id]["sources"].append("bm25")

    for rank, match in enumerate(vector_matches, start=1):
        section_id = match.policy_section_id

        if section_id not in candidates:
            candidates[section_id] = {
                "match": match,
                "score": 0.0,
                "bm25_rank": None,
                "vector_rank": None,
                "sources": [],
            }

        candidates[section_id]["score"] += (
            1.0 / (rrf_k + rank)
        )

        candidates[section_id]["vector_rank"] = rank
        candidates[section_id]["sources"].append("vector")

    results = []

    for section_id, candidate in candidates.items():
        match = candidate["match"]

        results.append(
            HybridPolicyMatch(
                policy_section_id=section_id,
                section_number=match.section_number,
                section_title=match.section_title,
                policy_text=match.policy_text,
                rrf_score=round(candidate["score"], 8),
                bm25_rank=candidate["bm25_rank"],
                vector_rank=candidate["vector_rank"],
                retrieval_sources=candidate["sources"],
            )
        )

    results.sort(
        key=lambda item: (
            -item.rrf_score,
            item.section_number,
            item.policy_section_id,
        )
    )

    return results[:top_k]


class HybridPolicyRetriever:

    def __init__(self, policy_sections: list[dict]):
        self.bm25 = BM25PolicyRetriever(policy_sections)
        self.vector = VectorPolicyRetriever()

    def search(
        self,
        obligation_text: str,
        top_k: int = 5,
        candidate_k: int = 10,
    ) -> list[HybridPolicyMatch]:

        if top_k < 1 or candidate_k < 1:
            raise ValueError(
                "top_k and candidate_k must be >= 1"
            )

        if not obligation_text.strip():
            return []

        candidate_k = max(candidate_k, top_k)

        bm25_matches = self.bm25.search(
            obligation_text=obligation_text,
            top_k=candidate_k,
        )

        vector_matches = self.vector.search(
            obligation_text=obligation_text,
            top_k=candidate_k,
        )

        return reciprocal_rank_fusion(
            bm25_matches=bm25_matches,
            vector_matches=vector_matches,
            top_k=top_k,
        )
