import pytest

from regintel.changes.compare import compare_versions
from regintel.changes.impact import shortlist_impacts


def test_removed_and_added_requirements_search_both_sides():
    comparison = compare_versions(
        {"document_id": "test", "content_hash": "old", "clauses": [{"clause_number": "1", "clause_text": "Preserve customer records"}]},
        {"document_id": "test", "content_hash": "new", "clauses": [{"clause_number": "2", "clause_text": "Monitor payment fraud"}]},
    )
    sections = [
        {"id": "retention", "section_number": "1", "section_title": "Records", "section_text": "Preserve customer records", "synthetic": True},
        {"id": "fraud", "section_number": "2", "section_title": "Fraud", "section_text": "Monitor payment fraud", "synthetic": True},
    ]
    result = shortlist_impacts(comparison, sections)
    assert len(result["impacts"]) == 2
    for impact, expected, side in zip(result["impacts"], ("retention", "fraud"), ("before", "after")):
        candidates = impact["candidate_policy_sections"]
        assert any(c["policy_section"]["id"] == expected for c in candidates)
        assert candidates[0]["matches"][0]["source_side"] == side
        assert candidates[0]["review_status"] == "pending"
        assert candidates[0]["policy_section"]["synthetic"] is True


def test_empty_policy_corpus_does_not_imply_no_impact():
    comparison = {"document_id": "test", "before_hash": "a", "after_hash": "b", "changes": [
        {"clause_number": "1", "change_type": "added", "before": None, "after": {"clause_text": "Keep records"}},
    ]}
    assert shortlist_impacts(comparison, [])["impacts"][0]["match_status"] == "no_lexical_match"
    with pytest.raises(ValueError):
        shortlist_impacts(comparison, [], 0)
