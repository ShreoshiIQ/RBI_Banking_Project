
from types import SimpleNamespace

import pytest

from regintel.mapping.hybrid_retriever import (
    reciprocal_rank_fusion,
)


def make_match(section_id, number):
    return SimpleNamespace(
        policy_section_id=section_id,
        section_number=str(number),
        section_title=f"Section {number}",
        policy_text=f"Policy content {number}",
    )


def test_shared_candidate_gets_combined_score():
    bm25 = [
        make_match("a", 1),
        make_match("b", 2),
    ]

    vector = [
        make_match("b", 2),
        make_match("a", 1),
    ]

    results = reciprocal_rank_fusion(
        bm25,
        vector,
    )

    assert len(results) == 2

    assert all(
        item.bm25_rank is not None
        and item.vector_rank is not None
        for item in results
    )


def test_candidate_in_one_retriever():
    results = reciprocal_rank_fusion(
        bm25_matches=[make_match("a", 1)],
        vector_matches=[],
    )

    assert len(results) == 1
    assert results[0].bm25_rank == 1
    assert results[0].vector_rank is None


def test_empty_results():
    assert reciprocal_rank_fusion([], []) == []


def test_top_k():
    bm25 = [
        make_match("a", 1),
        make_match("b", 2),
        make_match("c", 3),
    ]

    results = reciprocal_rank_fusion(
        bm25,
        [],
        top_k=2,
    )

    assert len(results) == 2


def test_invalid_top_k():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion(
            [],
            [],
            top_k=0,
        )


def test_invalid_rrf_k():
    with pytest.raises(ValueError):
        reciprocal_rank_fusion(
            [],
            [],
            rrf_k=0,
        )


def test_both_retrievers_contribute():
    bm25 = [
        make_match("a", 1),
        make_match("b", 2),
    ]

    vector = [
        make_match("b", 2),
        make_match("c", 3),
    ]

    results = reciprocal_rank_fusion(
        bm25,
        vector,
    )

    by_id = {
        item.policy_section_id: item
        for item in results
    }

    assert set(by_id) == {"a", "b", "c"}

    assert by_id["b"].retrieval_sources == [
        "bm25",
        "vector",
    ]
