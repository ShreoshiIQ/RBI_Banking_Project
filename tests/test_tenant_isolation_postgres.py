"""Row-level security against a dedicated, already-migrated PostgreSQL test database."""

import os
import secrets

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from regintel.api.tenancy import scope_session


@pytest.fixture(scope="module")
def engines():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Dedicated TEST_DATABASE_URL required")
    owner = create_engine(url)
    with owner.connect() as conn:
        if conn.execute(text("SELECT to_regclass('regulatory_gap_reports')")).scalar() is None:
            pytest.skip("Test database must be migrated to head")
        if conn.execute(text("SELECT count(*) FROM pg_policies WHERE policyname = 'tenant_isolation'")).scalar() == 0:
            pytest.skip("Tenant isolation migration not applied")
    from regintel.db.roles import provision
    role, password = f"regintel_rls_test_{secrets.token_hex(4)}", secrets.token_urlsafe(24)
    provision(owner, role, password)
    app = create_engine(make_url(url).set(username=role, password=password))
    try:
        with owner.begin() as conn:
            for tenant in ("bank-a", "bank-b"):
                conn.execute(text(
                    "INSERT INTO regulatory_gap_reports (report_id, regulatory_reference, assessment_status, review_status, report_json, tenant_id, created_at, updated_at) "
                    "VALUES (:id, 'RLS test', 'needs_review', 'pending_review', '{}', :t, now(), now())"), {"id": f"rls-{tenant}-{role}", "t": tenant})
        yield owner, app, role
    finally:
        app.dispose()
        with owner.begin() as conn:
            conn.execute(text("DELETE FROM regulatory_gap_reports WHERE report_id LIKE :p"), {"p": f"rls-%-{role}"})
            conn.execute(text(f"DROP OWNED BY {role}"))
            conn.execute(text(f"DROP ROLE {role}"))
    owner.dispose()


def visible(session, role):
    return sorted(session.execute(text("SELECT tenant_id FROM regulatory_gap_reports WHERE report_id LIKE :p"),
                                  {"p": f"rls-%-{role}"}).scalars())


def test_app_role_sees_only_its_tenant(engines):
    _, app, role = engines
    for tenant in ("bank-a", "bank-b"):
        with Session(app) as session:
            scope_session(session, tenant)
            assert visible(session, role) == [tenant]


def test_unscoped_app_session_sees_nothing(engines):
    _, app, role = engines
    with Session(app) as session:
        assert visible(session, role) == []


def test_scope_survives_commit_and_does_not_leak(engines):
    _, app, role = engines
    with Session(app) as session:
        scope_session(session, "bank-a")
        assert visible(session, role) == ["bank-a"]
        session.commit()  # next transaction re-applies the local setting
        assert visible(session, role) == ["bank-a"]
    with app.connect() as conn:  # pooled connection carries no tenant
        assert conn.execute(text("SELECT NULLIF(current_setting('app.tenant_id', true), '')")).scalar() is None


def test_cross_tenant_write_is_rejected(engines):
    _, app, role = engines
    with Session(app) as session:
        scope_session(session, "bank-a")
        with pytest.raises(DBAPIError, match="row-level security"):
            session.execute(text(
                "INSERT INTO regulatory_gap_reports (report_id, regulatory_reference, assessment_status, review_status, report_json, tenant_id, created_at, updated_at) "
                "VALUES (:id, 'x', 'needs_review', 'pending_review', '{}', 'bank-b', now(), now())"), {"id": f"rls-x-{role}"})
        session.rollback()
        updated = session.execute(text("UPDATE regulatory_gap_reports SET review_status = 'approved' WHERE tenant_id = 'bank-b' AND report_id LIKE :p"),
                                  {"p": f"rls-%-{role}"}).rowcount
        assert updated == 0


def test_owner_still_sees_all_tenants_for_operations(engines):
    owner, _, role = engines
    with Session(owner) as session:
        assert visible(session, role) == ["bank-a", "bank-b"]


def test_api_lists_only_the_callers_tenant(engines, monkeypatch):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from regintel.api.app import create_app
    from regintel.api.dependencies import get_db
    from regintel.api.routes.auth import get_current_user
    from regintel.models.user import UserRecord

    owner, app_engine, role = engines
    with owner.begin() as conn:
        ids = {t: conn.execute(text(
            "INSERT INTO users (username, hashed_password, is_active, role, tenant_id, created_at) "
            "VALUES (:u, 'x', true, 'viewer', :t, now()) RETURNING id"), {"u": f"{role}-{t}", "t": t}).scalar()
            for t in ("bank-a", "bank-b")}
    monkeypatch.setattr("regintel.api.tenancy.get_settings", lambda: SimpleNamespace(tenant_isolation_enabled=True))

    def app_session():
        with Session(app_engine) as session:
            yield session

    try:
        for tenant, user_id in ids.items():
            app = create_app()
            app.dependency_overrides[get_db] = app_session
            app.dependency_overrides[get_current_user] = lambda uid=user_id: UserRecord(id=uid, username="t", role="viewer", is_active=True)
            with TestClient(app) as client:
                items = client.get("/api/v1/gap-reports", params={"limit": 100}).json()["items"]
            mine = [i["report_id"] for i in items if i["report_id"].endswith(role)]
            assert mine == [f"rls-{tenant}-{role}"]
            other = "bank-b" if tenant == "bank-a" else "bank-a"
            with TestClient(app) as client:
                assert client.get(f"/api/v1/gap-reports/rls-{other}-{role}").status_code == 404
    finally:
        with owner.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE username LIKE :p"), {"p": f"{role}-%"})
