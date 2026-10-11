"""Blind packet safety and fixture-only offline relevance scoring."""

import copy
from pathlib import Path

import pytest

from regintel.foundation.registry import load
from regintel.mapping.relevance_review import (
    build_packet,
    score_packet,
    suggest,
    template,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/processed/validation/phase4_candidate_snapshot.json"
RESULTS = ROOT / "data/processed/validation/phase4_scalability_warm_results.json"


def packet():
    return build_packet(ROOT, SNAPSHOT, RESULTS)


def test_blind_packet_has_entire_frozen_subset_and_no_predictions():
    result = packet()
    assert len(result["records"]) == 500
    assert len(result["queries"]) == 6
    assert "methods" not in result and "rankings" not in result
    assert all(r["review_status"] == "pending" for r in result["records"])
    assert all(
        c["review_status"] == "pending" and not c["relevant_section_ids"]
        for c in template(result)["cases"]
    )


def test_pending_labels_cannot_publish_scores():
    result = packet()
    with pytest.raises(ValueError, match="reviewed"):
        score_packet(result, template(result), load(RESULTS))


def fixture_reviews(result):
    # Simulated unit-test annotations, never persisted human approvals or benchmark labels.
    reviews = template(result)
    for case in reviews["cases"]:
        case.update(
            review_status="approved",
            reviewer="UNIT TEST FIXTURE",
            rationale="Synthetic scoring gate test",
            full_corpus_reviewed=True,
            answerability="no_relevant_document_in_subset",
        )
    return reviews


def test_empty_ground_truth_is_unscored_without_forcing_relevant_ids():
    result = packet()
    scored = score_packet(result, fixture_reviews(result), load(RESULTS))
    assert scored["scorable_cases"] == 0 and scored["recall_scores"] is None
    assert len(scored["unanswerable_cases"]) == 6


@pytest.mark.parametrize(
    "mutation",
    ["reviewer", "rationale", "unknown_id", "answerability", "subset_review", "order"],
)
def test_invalid_annotations_rejected(mutation):
    result = packet()
    reviews = fixture_reviews(result)
    case = reviews["cases"][0]
    if mutation in ("reviewer", "rationale"):
        case[mutation] = ""
    elif mutation == "unknown_id":
        case.update(
            answerability="relevant_documents_present",
            relevant_section_ids=["NOT-IN-CORPUS"],
        )
    elif mutation == "answerability":
        case["answerability"] = "relevant_documents_present"
    elif mutation == "subset_review":
        case["full_corpus_reviewed"] = False
    else:
        reviews["cases"].reverse()
    with pytest.raises(ValueError):
        score_packet(result, reviews, load(RESULTS))


def test_changed_recorded_results_rejected():
    result = packet()
    modified = copy.deepcopy(load(RESULTS))
    modified["targets"][0]["methods"]["bm25"][0]["attempts"][0]["ids"] = []
    with pytest.raises(ValueError, match="benchmark changed"):
        score_packet(result, fixture_reviews(result), modified)


def test_conditional_scoring_excludes_empty_ground_truth():
    # Fixture references exercise the denominator; this does not judge real relevance.
    result = packet()
    reviews = fixture_reviews(result)
    reviews["cases"][0].update(
        answerability="relevant_documents_present",
        relevant_section_ids=[result["records"][0]["id"]],
    )
    scored = score_packet(result, reviews, load(RESULTS))
    assert scored["scorable_cases"] == 1
    assert len(scored["unanswerable_cases"]) == 5
    assert all(r["cases_scored"] == 1 for r in scored["recall_scores"].values())


def test_suggestions_preserve_pending_labels_and_exact_evidence():
    frozen = packet()
    before = copy.deepcopy(frozen)
    result = suggest(frozen, load(RESULTS))
    assert frozen == before
    assert result["new_model_calls"] == 0 and result["human_approvals_created"] == 0
    records = {r["id"]: r for r in frozen["records"]}
    assert len(result["cases"]) == 6
    for case in result["cases"]:
        assert case["review_status"] == "pending" and case["relevant_section_ids"] == []
        assert case["answerability"] == "pending"
        candidates = case["suggested_candidates"]
        assert len(candidates) == len({c["candidate_id"] for c in candidates})
        for candidate in candidates:
            assert (
                candidate["evidence_quote"]
                == records[candidate["candidate_id"]]["text"]
            )
            assert candidate["verification_status"] == "unverified"
            expected = sum(
                1 / (60 + rank)
                for method, rank in candidate["retrieval_ranks"].items()
                if method != "hybrid"
            )
            assert candidate["rrf_score"] == expected
    with pytest.raises(ValueError, match="reviewed"):
        score_packet(frozen, result, load(RESULTS))


def test_suggestions_reject_changed_predictions():
    changed = copy.deepcopy(load(RESULTS))
    changed["model"] = "different-model"
    with pytest.raises(ValueError, match="benchmark changed"):
        suggest(packet(), changed)
