from regintel.reporting.audit_consistency import inspect_history


def test_embedded_report_status_mismatch_is_detected():
    result = inspect_history([{"report_id": "toy", "review_status": "pending_review", "serialized_review_status": "approved"}], [])
    assert result["consistent"] is False
    assert result["issues"][0]["reason"] == "report_json_status_mismatch"


def test_legacy_report_without_embedded_status_remains_supported():
    assert inspect_history([{"report_id": "toy", "review_status": "pending_review"}], [])["consistent"] is True


def review(**changes):
    row = {"id": 1, "report_id": "test", "reviewer_id": "1", "comment": "Reviewed", "previous_status": "pending_review", "new_status": "approved"}
    row.update(changes)
    return row


def test_pending_and_consistent_approval():
    assert inspect_history([{"report_id": "test", "review_status": "pending_review"}], [])["consistent"]
    assert inspect_history([{"report_id": "test", "review_status": "approved"}], [review()])["consistent"]


def test_terminal_status_without_audit():
    result = inspect_history([{"report_id": "test", "review_status": "approved"}], [])
    assert result["issues"][0]["reason"] == "report_history_status_mismatch"


def test_duplicate_decisions_and_invalid_chain():
    result = inspect_history([{"report_id": "test", "review_status": "rejected"}], [review(), review(id=2, new_status="rejected")])
    reasons = {row["reason"] for row in result["issues"]}
    assert {"multiple_terminal_decisions", "broken_status_chain"} <= reasons


def test_orphan_and_missing_metadata():
    result = inspect_history([], [review(reviewer_id="", comment=" ")])
    assert {row["reason"] for row in result["issues"]} == {"orphan_review", "missing_reviewer", "empty_comment"}
