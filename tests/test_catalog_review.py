from copy import deepcopy

import pytest

from regintel.ingestion.catalog_review import review_template, reviewed_catalog


def fixture():
    report = {"source_metadata": {"sha256": "source"}, "candidates": [{
        "candidate_index": 0, "source": {"actor": "Unresolved", "evidence_quote": "REs shall retain records"},
        "evidence_match": "contiguous",
    }]}
    return report, review_template(report)


def test_template_does_not_approve_or_invent_review():
    report, decisions = fixture()
    result = reviewed_catalog(report, decisions)
    assert result["summary"] == {"pending": 1, "approved": 0, "rejected": 0}
    assert result["approved_candidates"] == []


def test_approval_keeps_original_evidence():
    report, decisions = fixture()
    original = deepcopy(report)
    decisions["decisions"][0].update(
        status="approved", reviewer="human-test-reviewer", rationale="Checked source",
        source_citation="Test source clause 46", actor="REs", applicability="Test scope",
    )
    result = reviewed_catalog(report, decisions)
    assert len(result["approved_candidates"]) == 1
    assert report == original
    assert result["approved_candidates"][0]["original_candidate"]["actor"] == "Unresolved"


@pytest.mark.parametrize("change", ["stale", "duplicate", "unknown", "source", "incomplete"])
def test_invalid_decisions_are_rejected(change):
    report, decisions = fixture()
    if change == "stale":
        report["candidates"][0]["source"]["actor"] = "Changed"
    elif change == "duplicate":
        decisions["decisions"] *= 2
    elif change == "unknown":
        decisions["decisions"][0]["candidate_index"] = 10
    elif change == "source":
        decisions["source_hash"] = "wrong"
    else:
        decisions["decisions"][0]["status"] = "approved"
    with pytest.raises(ValueError):
        reviewed_catalog(report, decisions)
