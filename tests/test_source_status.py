from regintel.ingestion.source_status import inspect_source_status


def test_watermark_blocks_current_extraction():
    result = inspect_source_status([{"page_number": 1, "text": "Directions\n Withdrawn \nBanks shall retain records."}])
    assert result["current_obligation_extraction_allowed"] is False
    assert result["withdrawal_marker_pages"] == [1]


def test_mentions_are_not_watermarks():
    result = inspect_source_status([{"page_number": 1, "text": "Authorisation may be withdrawn by RBI."}])
    assert result["withdrawal_marker_pages"] == []
    assert result["current_obligation_extraction_allowed"] is None
