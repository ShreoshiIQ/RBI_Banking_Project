"""PostgreSQL locking test, using a disposable schema on an explicit test DB."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from regintel.models.gap_report import RegulatoryGapReportRecord as Report
from regintel.models.gap_report_review import GapReportReviewRecord as Review
from regintel.reporting.review_service import ReviewError, review_gap_report


def test_concurrent_reviews_have_one_winner():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a dedicated PostgreSQL test database")
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    if engine.dialect.name != "postgresql":
        engine.dispose()
        pytest.fail("TEST_DATABASE_URL must point to PostgreSQL")
    schema = "review_test_" + uuid4().hex
    scoped = engine.execution_options(schema_translate_map={None: schema})
    created = False
    try:
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        created = True
        with scoped.begin() as connection:
            Report.__table__.create(connection)
            Review.__table__.create(connection)
        with Session(scoped) as db:
            db.add(Report(
                report_id="concurrent-fixture", regulatory_reference="Synthetic fixture",
                assessment_status="partial_evidence", review_status="pending_review",
                report_json={"synthetic": True},
            ))
            db.commit()
        barrier = Barrier(2)

        def decide(decision):
            with Session(scoped) as db:
                barrier.wait(timeout=10)
                try:
                    review_gap_report(
                        db, report_id="concurrent-fixture", reviewer_id=decision,
                        decision=decision, comment="Synthetic concurrency test",
                    )
                    db.commit()
                    return decision
                except ReviewError:
                    db.rollback()
                    return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(decide, ("approved", "rejected")))
        assert results.count("conflict") == 1
        with Session(scoped) as db:
            audits = db.scalars(select(Review)).all()
            assert len(audits) == 1
            assert db.get(Report, "concurrent-fixture").review_status == audits[0].new_status
            assert audits[0].new_status in results
    finally:
        if created:
            # Remove only this test's generated schema, never application tables.
            with engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()
