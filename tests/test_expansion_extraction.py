import pytest

from regintel.ingestion.extract_expansion import extract_preview


@pytest.mark.parametrize("chapter", ["Chapter I - Preliminary", "CHAPTER – I", "CHAPTER I"])
def test_preview_preserves_evidence_and_defers_preliminary_text(chapter):
    pages = [{"page_number": 1, "text": (
        "Chapter I - Preliminary .......... 2\n" + chapter + "\n"
        "1. These Directions shall be called test directions.\n"
        "2. These Directions shall commence on publication.\n"
        "3. These Directions apply to the test bank.\n"
        "4. Banks shall maintain transaction records for five years."
    )}]
    record = {"sha256": "testhash", "source_url": "https://www.rbi.org.in/test", "page_count": 1}
    result = extract_preview(record, pages)
    assert len(result["clauses"]) == 4
    assert len(result["catalog"]["obligations"]) == 1
    item = result["catalog"]["obligations"][0]
    assert item["review_status"] == "pending"
    assert item["id_scope"] == "local_preview_not_database"
    assert result == extract_preview(record, pages)


def test_withdrawn_preview_rejected():
    with pytest.raises(ValueError, match="Withdrawn"):
        extract_preview({}, [{"page_number": 1, "text": "Withdrawn"}])
