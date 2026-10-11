import pytest

from regintel.changes.compare import compare_versions


def version(hash_value, clauses, document_id="test-instrument"):
    return {"document_id": document_id, "content_hash": hash_value, "clauses": [
        {"clause_number": number, "clause_text": text} for number, text in clauses
    ]}


def test_added_removed_and_material_changes():
    a = version("old", [("1", "Banks shall retain records for five years."), ("2", "Banks may outsource.")])
    b = version("new", [("1", "Banks shall retain records for ten years."), ("3", "Banks shall not outsource.")])
    report = compare_versions(a, b)
    assert report["summary"] == {"modified": 1, "removed": 1, "added": 1}
    assert "-five" in report["changes"][0]["word_diff"]
    assert "+ten" in report["changes"][0]["word_diff"]


def test_whitespace_only_change_and_renumbering_hint():
    a = version("old", [("1", "Keep records."), ("2", "Preserve evidence.")])
    b = version("new", [("1", "Keep\n records."), ("3", "Preserve evidence.")])
    report = compare_versions(a, b)
    assert report["summary"]["unchanged"] == 1
    assert report["possible_renumberings"] == [{"from_clause": "2", "to_clause": "3", "review_status": "pending"}]


def test_replacement_is_not_a_revision():
    with pytest.raises(ValueError, match="same instrument"):
        compare_versions(version("old", [], "old-instrument"), version("new", [], "replacement"))


def test_duplicate_clause_and_inconsistent_source_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        compare_versions(version("old", [("1", "A"), ("1", "B")]), version("new", []))
    with pytest.raises(ValueError, match="Same source hash"):
        compare_versions(version("same", [("1", "A")]), version("same", [("1", "B")]))
