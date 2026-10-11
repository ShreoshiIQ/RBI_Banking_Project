
import json
from pathlib import Path

from regintel.db.session import SessionLocal
from regintel.reporting.persistence import (
    save_gap_report,
)
from regintel.reporting.schemas import (
    RegulatoryGapReport,
)


REPORT_PATH = Path(
    "data/processed/reports/rbi_46f_gap_report.json"
)


def main():
    if not REPORT_PATH.exists():
        raise FileNotFoundError(
            f"Report not found: {REPORT_PATH}"
        )

    data = json.loads(
        REPORT_PATH.read_text(encoding="utf-8")
    )

    report = RegulatoryGapReport.model_validate(data)

    with SessionLocal() as session:
        record, created = save_gap_report(
            session,
            report,
        )

        session.commit()

        print("\nREGULATORY GAP REPORT PERSISTENCE")
        print("-" * 50)
        print(
            "Operation:",
            "INSERTED" if created else "ALREADY EXISTS",
        )
        print("Report ID:", record.report_id)
        print(
            "Regulation:",
            record.regulatory_reference,
        )
        print(
            "Assessment:",
            record.assessment_status,
        )
        print("Review status:", record.review_status)
        print("Database: PostgreSQL")


if __name__ == "__main__":
    main()
