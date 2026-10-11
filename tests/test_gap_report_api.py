
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from regintel.api.app import create_app
from regintel.api.dependencies import get_db
from regintel.db.base import Base
from regintel.models.gap_report import RegulatoryGapReportRecord
from regintel.models.gap_report_review import GapReportReviewRecord
from regintel.models.user import UserRecord
from regintel.security.tokens import create_access_token


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "isolated-report-api-test-secret-1234567890")
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(
        engine,
        tables=[
            UserRecord.__table__,
            RegulatoryGapReportRecord.__table__,
            GapReportReviewRecord.__table__,
        ],
    )

    with Session(engine) as session:
        session.add(UserRecord(id=1, username="viewer", role="viewer", hashed_password="unused"))
        session.add(
            RegulatoryGapReportRecord(
                report_id="gap-test-001",
                regulatory_reference="RBI KYC Section 46(f)",
                assessment_status="partial_evidence",
                review_status="pending_review",
                report_json={
                    "report_id": "gap-test-001",
                    "findings": [],
                },
            )
        )
        session.commit()

    def override_get_db():
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        test_client.headers["Authorization"] = f"Bearer {create_access_token('1')}"
        yield test_client

    app.dependency_overrides.clear()
    engine.dispose()


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_reports(client):
    response = client.get("/api/v1/gap-reports")

    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["report_id"] == "gap-test-001"


def test_get_report_detail(client):
    response = client.get(
        "/api/v1/gap-reports/gap-test-001"
    )

    assert response.status_code == 200

    data = response.json()
    assert data["assessment_status"] == "partial_evidence"
    assert data["review_status"] == "pending_review"
    assert data["report"]["findings"] == []


def test_missing_report_returns_404(client):
    response = client.get(
        "/api/v1/gap-reports/not-found"
    )

    assert response.status_code == 404


def test_empty_review_history(client):
    response = client.get(
        "/api/v1/gap-reports/gap-test-001/reviews"
    )

    assert response.status_code == 200
    assert response.json()["reviews"] == []


def test_missing_report_review_history_returns_404(client):
    response = client.get(
        "/api/v1/gap-reports/not-found/reviews"
    )

    assert response.status_code == 404


def test_pagination(client):
    response = client.get(
        "/api/v1/gap-reports?limit=1&offset=1"
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"] == []


def test_invalid_pagination(client):
    response = client.get(
        "/api/v1/gap-reports?limit=101"
    )

    assert response.status_code == 422


def test_review_submission_not_exposed(client):
    response = client.post(
        "/api/v1/gap-reports/gap-test-001/reviews",
        json={
            "decision": "approved",
            "reviewer_id": "fake-officer",
            "comment": "Approve",
        },
    )

    assert response.status_code == 405
