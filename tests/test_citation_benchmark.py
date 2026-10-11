import pytest

from regintel.mapping.citation_benchmark import score_citations


def citation(page=2, digest="a" * 64):
    return {"source_sha256": digest, "page": page, "clause_number": "4.1"}


def cases():
    return [{"scenario_id": item, "review_status": "approved", "split": "test", "acceptable_citations": [citation()]}
            for item in ("a", "b")]


def test_hand_calculated_location_precision_and_coverage():
    result = score_citations(cases(), {"a": [citation(), citation(3)], "b": []})
    assert result["citation_location_precision"] == 0.5
    assert result["case_coverage"] == 0.5
    assert result["per_case"][0]["incorrect_citations"] == [citation(3)]


def test_wrong_version_and_clause_do_not_match():
    wrong_clause = citation()
    wrong_clause["clause_number"] = "4.2"
    result = score_citations(cases(), {"a": [citation(digest="b" * 64)], "b": [wrong_clause]})
    assert result["correct_citations"] == 0


@pytest.mark.parametrize("page", [0, -1, True, "2"])
def test_invalid_page_rejected(page):
    with pytest.raises(ValueError):
        score_citations(cases(), {"a": [citation(page)], "b": []})


def test_pending_labels_duplicates_and_missing_case_rejected():
    rows = cases()
    rows[0]["review_status"] = "pending"
    with pytest.raises(ValueError):
        score_citations(rows, {"a": [], "b": []})
    with pytest.raises(ValueError):
        score_citations(cases(), {"a": [citation(), citation()], "b": []})
    with pytest.raises(ValueError):
        score_citations(cases(), {"a": []})


def test_no_citations_counts_as_uncovered():
    result = score_citations(cases(), {"a": [], "b": []})
    assert result["citation_location_precision"] == result["case_coverage"] == 0
