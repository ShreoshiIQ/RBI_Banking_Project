
import pytest

from regintel.mapping.bm25_retriever import (
    BM25PolicyRetriever,
)


@pytest.fixture
def policy_sections():
    return [
        {
            "id": "section-1",
            "section_number": "1",
            "section_title": "Transaction Record Retention",
            "section_text": (
                "Transaction records must be maintained "
                "for five years."
            ),
        },
        {
            "id": "section-2",
            "section_number": "2",
            "section_title": "Customer Identification",
            "section_text": (
                "Customer identity documents must be "
                "preserved after account closure."
            ),
        },
        {
            "id": "section-3",
            "section_number": "3",
            "section_title": "Employee Training",
            "section_text": (
                "Employees complete annual training "
                "and workplace safety courses."
            ),
        },
    ]


def test_bm25_returns_relevant_match(policy_sections):
    retriever = BM25PolicyRetriever(policy_sections)

    matches = retriever.search(
        "Maintain transaction records for five years"
    )

    assert matches
    assert matches[0].policy_section_id == "section-1"


def test_bm25_empty_query(policy_sections):
    retriever = BM25PolicyRetriever(policy_sections)

    assert retriever.search("") == []


def test_bm25_empty_corpus():
    retriever = BM25PolicyRetriever([])

    assert retriever.search("transaction records") == []


def test_bm25_top_k(policy_sections):
    retriever = BM25PolicyRetriever(policy_sections)

    matches = retriever.search(
        "customer records training",
        top_k=1,
    )

    assert len(matches) <= 1


def test_bm25_no_overlapping_terms(policy_sections):
    retriever = BM25PolicyRetriever(policy_sections)

    matches = retriever.search(
        "quantum entanglement cryptography"
    )

    assert matches == []


def test_bm25_invalid_top_k(policy_sections):
    retriever = BM25PolicyRetriever(policy_sections)

    with pytest.raises(ValueError):
        retriever.search(
            "transaction records",
            top_k=0,
        )
