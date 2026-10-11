import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from regintel.api.app import create_app
from regintel.api.dependencies import get_db
from regintel.api.routes.auth import get_current_user
from regintel.models.clause_candidate import RegulatoryClauseCandidate as Clause
from regintel.models.obligation import RegulatoryObligation as Obligation
from regintel.models.regulation import RegulatoryDocument as Document, RegulatoryDocumentVersion as Version
from regintel.models.user import UserRecord
from regintel.models.policy import PolicyDocument, PolicyDocumentVersion, PolicySection


@pytest.fixture
def catalog():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    for model in (Document, Version, Clause, Obligation, PolicyDocument, PolicyDocumentVersion, PolicySection):
        model.__table__.create(engine)
    with Session(engine) as db:
        document = Document(regulator="RBI", title="Toy source", jurisdiction="India", source_url="https://example.invalid")
        db.add(document); db.flush()
        version = Version(document_id=document.id, content_hash="a" * 64, storage_uri="local")
        db.add(version); db.flush()
        clause = Clause(version_id=version.id, clause_number="1", clause_text="Bank shall retain records.", start_page=2, end_page=3)
        db.add(clause); db.flush()
        obligation = Obligation(source_clause_id=clause.id, document_version_id=version.id, obligation_fingerprint="b" * 64,
                                clause_number="1", obligation_type="mandatory", actor="Bank", action="retain records",
                                evidence_quote=clause.clause_text, confidence=0.5, extraction_method="toy", source_url=document.source_url)
        db.add(obligation); db.commit()
        policy = PolicyDocument(title="Toy policy", policy_code="TOY")
        db.add(policy); db.flush()
        policy_version = PolicyDocumentVersion(document_id=policy.id, content_hash="c" * 64, storage_uri="local")
        db.add(policy_version); db.flush()
        db.add(PolicySection(version_id=policy_version.id, section_number="1", section_title="Records", section_text="Bank retains records."))
        db.commit()
        version_id = str(version.id)
    app = create_app()
    def session():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_user] = lambda: UserRecord(id=1, username="viewer", role="viewer", is_active=True)
    yield TestClient(app), version_id, app
    engine.dispose()


def test_counts_traceability_and_filters(catalog):
    client, version, _ = catalog
    result = client.get("/api/v1/catalog/versions").json()
    assert result["items"][0]["clauses"] == result["items"][0]["obligations"] == 1
    result = client.get(f"/api/v1/catalog/obligations?version_id={version}&review_status=pending").json()
    assert result["items"][0]["start_page"] == 2
    assert result["items"][0]["content_hash"] == "a" * 64
    assert client.get("/api/v1/catalog/obligations?review_status=approved").json()["total"] == 0
    assert client.get(f"/api/v1/catalog/obligations?version_id={uuid.uuid4()}").json()["total"] == 0


def test_authentication_and_validation(catalog):
    client, _, app = catalog
    assert client.get("/api/v1/catalog/versions?limit=101").status_code == 422
    assert client.get("/api/v1/catalog/obligations?version_id=bad").status_code == 422
    app.dependency_overrides.pop(get_current_user)
    assert client.get("/api/v1/catalog/versions").status_code == 401
    assert client.get("/api/v1/catalog/obligations").status_code == 401


def test_mapping_reuses_persisted_latest_policy_sections(catalog):
    client, _, _ = catalog
    obligation = client.get("/api/v1/catalog/obligations").json()["items"][0]
    endpoint = f'/api/v1/catalog/obligations/{obligation["id"]}/policy-matches'
    response = client.get(endpoint)
    assert response.status_code == 200
    result = response.json()
    assert result["sections_considered"] == 1
    assert result["matches"][0]["policy_code"] == "TOY"
    assert "records" in result["matches"][0]["matched_terms"]
    assert client.get(endpoint + "?top_k=11").status_code == 422
    assert client.get(f"/api/v1/catalog/obligations/{uuid.uuid4()}/policy-matches").status_code == 404
