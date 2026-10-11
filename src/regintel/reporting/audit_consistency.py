"""Read-only consistency checks for persisted compliance review history."""

import json
from collections import defaultdict

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from regintel.models.gap_report import RegulatoryGapReportRecord as Report
from regintel.models.gap_report_review import GapReportReviewRecord as Review
from regintel.reporting.review_service import ALLOWED_TRANSITIONS


def inspect_history(reports: list[dict], reviews: list[dict]) -> dict:
    statuses = {row["report_id"]: row["review_status"] for row in reports}
    histories = defaultdict(list)
    issues = []

    def flag(report_id, reason, review_id=None):
        issues.append({"report_id": report_id, "reason": reason, "review_id": review_id})

    for report in reports:
        if "serialized_review_status" in report and report["serialized_review_status"] != report["review_status"]:
            flag(report["report_id"], "report_json_status_mismatch")

    for review in reviews:
        histories[review["report_id"]].append(review)
        if review["report_id"] not in statuses:
            flag(review["report_id"], "orphan_review", review["id"])
        if not str(review.get("reviewer_id") or "").strip():
            flag(review["report_id"], "missing_reviewer", review["id"])
        if not str(review.get("comment") or "").strip():
            flag(review["report_id"], "empty_comment", review["id"])
    for report_id, status in statuses.items():
        history = histories[report_id]
        if len(history) > 1:
            flag(report_id, "multiple_terminal_decisions")
        expected = "pending_review"
        for review in sorted(history, key=lambda row: row["id"]):
            if review["previous_status"] != expected:
                flag(report_id, "broken_status_chain", review["id"])
            if review["new_status"] not in ALLOWED_TRANSITIONS.get(review["previous_status"], set()):
                flag(report_id, "invalid_transition", review["id"])
            expected = review["new_status"]
        if status != expected:
            flag(report_id, "report_history_status_mismatch")
        if status not in ALLOWED_TRANSITIONS:
            flag(report_id, "unknown_report_status")
    return {"reports_checked": len(reports), "reviews_checked": len(reviews), "consistent": not issues, "issues": issues}


def inspect_database(session: Session) -> dict:
    reports = []
    for row in session.scalars(select(Report)):
        report = {"report_id": row.report_id, "review_status": row.review_status}
        if "review_status" in row.report_json:
            report["serialized_review_status"] = row.report_json["review_status"]
        reports.append(report)
    reviews = [{field: getattr(row, field) for field in ("id", "report_id", "reviewer_id", "comment", "previous_status", "new_status")} for row in session.scalars(select(Review))]
    return inspect_history(reports, reviews)


def main():
    from regintel.db.session import engine

    # A consistent read snapshot prevents concurrent commits from creating false alarms.
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '10s'"))
            with Session(bind=connection) as session:
                result = inspect_database(session)
    print(json.dumps(result, indent=2))
    if not result["consistent"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
