import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from regintel.api.app import create_app
from regintel.api.dependencies import get_db
from regintel.models.gap_report import RegulatoryGapReportRecord as Report
from regintel.models.gap_report_review import GapReportReviewRecord as Review
from regintel.models.user import UserRecord
from regintel.security.tokens import create_access_token

REPORT_URL = "/api/v1/gap-reports/test-report"


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "isolated-rbac-test-secret-at-least-32-characters")
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Create only portable tables; the full metadata includes pgvector types.
    for table in (UserRecord.__table__, Report.__table__, Review.__table__):
        table.create(engine)
    with Session(engine) as db:
        for user_id, role in enumerate(("viewer", "admin", "compliance_officer"), 1):
            db.add(UserRecord(id=user_id, username=role, role=role, hashed_password="unused"))
        db.add(Report(
            report_id="test-report", regulatory_reference="Synthetic test fixture",
            assessment_status="partial_evidence", review_status="pending_review",
            report_json={"findings": [], "synthetic": True, "review_status": "pending_review"},
        ))
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, engine
    engine.dispose()


def headers(user_id):
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


def assert_state(engine, status="pending_review", count=0):
    with Session(engine) as db:
        assert db.get(Report, "test-report").review_status == status
        assert db.get(Report, "test-report").report_json["review_status"] == status
        assert len(db.scalars(select(Review)).all()) == count


@pytest.mark.parametrize("token", [None, "invalid.token.value"])
@pytest.mark.parametrize("path", ["/api/v1/gap-reports", REPORT_URL, REPORT_URL + "/reviews", REPORT_URL + "/review"])
def test_missing_or_invalid_auth(api, token, path):
    client, engine = api
    auth = {} if token is None else {"Authorization": f"Bearer {token}"}
    if path.endswith("/review"):
        response = client.post(path, headers=auth, json={"decision": "approved", "comment": "Reviewed"})
    else:
        response = client.get(path, headers=auth)
    assert response.status_code == 401
    assert_state(engine)


@pytest.mark.parametrize("user_id", [1, 2, 3])
def test_all_roles_read_reports_and_history(api, user_id):
    client, _ = api
    for path in ("/api/v1/gap-reports", REPORT_URL, REPORT_URL + "/reviews"):
        assert client.get(path, headers=headers(user_id)).status_code == 200


@pytest.mark.parametrize("user_id", [1, 2])
@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_only_officers_review(api, user_id, decision):
    client, engine = api
    response = client.post(REPORT_URL + "/review", headers=headers(user_id), json={
        "decision": decision, "comment": "Reviewed",
    })
    assert response.status_code == 403
    assert_state(engine)


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_officer_reviews_and_cannot_impersonate(api, decision):
    client, engine = api
    response = client.post(REPORT_URL + "/review", headers=headers(3), json={
        "decision": decision, "comment": "Reviewed", "reviewer_id": "forged-admin",
    })
    assert response.status_code == 200
    assert response.json()["reviewer_id"] == "3"
    assert_state(engine, decision, 1)
    with Session(engine) as db:
        audit = db.scalar(select(Review))
        assert audit.reviewer_id == "3"
        assert audit.previous_status == "pending_review"
        assert audit.new_status == decision
    response = client.post(REPORT_URL + "/review", headers=headers(3), json={
        "decision": "approved", "comment": "Second attempt",
    })
    assert response.status_code == 400
    assert_state(engine, decision, 1)


def test_invalid_decision(api):
    client, engine = api
    assert client.post(REPORT_URL + "/review", headers=headers(3), json={
        "decision": "certified", "comment": "Reviewed",
    }).status_code == 422
    assert_state(engine)


def test_whitespace_comment(api):
    client, engine = api
    assert client.post(REPORT_URL + "/review", headers=headers(3), json={
        "decision": "approved", "comment": "   ",
    }).status_code == 400
    assert_state(engine)


@pytest.mark.parametrize("failure_point", ["audit_insert", "commit"])
def test_database_failure_rolls_back(api, failure_point):
    client, engine = api

    def fail_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO GAP_REPORT_REVIEWS"):
            raise RuntimeError("Simulated audit insertion failure")

    def fail_commit(session):
        raise RuntimeError("Simulated commit failure")

    target, name, handler = (
        (engine, "before_cursor_execute", fail_insert)
        if failure_point == "audit_insert" else (Session, "before_commit", fail_commit)
    )
    event.listen(target, name, handler)
    try:
        response = client.post(REPORT_URL + "/review", headers=headers(3), json={
            "decision": "approved", "comment": "Reviewed",
        })
        assert response.status_code == 500
    finally:
        event.remove(target, name, handler)
    assert_state(engine)
