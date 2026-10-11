
"""
Retrieval evaluation metrics.

Recall@K:
Fraction of relevant documents retrieved in the top K.

MRR:
Mean reciprocal rank of the first relevant document.
"""

from collections.abc import Sequence


def recall_at_k(
    retrieved_ids: Sequence[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    if k < 1:
        raise ValueError("k must be >= 1")

    if not relevant_ids:
        raise ValueError(
            "Recall is undefined when no relevant documents exist."
        )

    retrieved = set(retrieved_ids[:k])

    return len(retrieved & relevant_ids) / len(relevant_ids)


def reciprocal_rank(
    retrieved_ids: Sequence[str],
    relevant_ids: set[str],
) -> float:
    if not relevant_ids:
        raise ValueError(
            "Reciprocal rank requires a relevant document."
        )

    for rank, document_id in enumerate(retrieved_ids, start=1):
        if document_id in relevant_ids:
            return 1.0 / rank

    return 0.0


def mean_reciprocal_rank(
    ranked_results: list[list[str]],
    relevance_sets: list[set[str]],
) -> float:
    if len(ranked_results) != len(relevance_sets):
        raise ValueError(
            "Results and relevance sets must have equal lengths."
        )

    if not ranked_results:
        raise ValueError("At least one query is required.")

    return sum(
        reciprocal_rank(results, relevant)
        for results, relevant in zip(
            ranked_results,
            relevance_sets,
        )
    ) / len(ranked_results)
