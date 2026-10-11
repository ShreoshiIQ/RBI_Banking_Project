from copy import deepcopy

from fastapi.testclient import TestClient
import pytest

from regintel.api.app import create_app
from regintel.api.routes.auth import get_current_user
from regintel.models.user import UserRecord


@pytest.fixture
def payload():
    return {
        "baseline": {"document_id": "synthetic", "content_hash": "v1", "clauses": [{"clause_number": "1", "clause_text": "Keep records for five years"}]},
        "proposal": {"base_content_hash": "v1", "edits": [{"clause_number": "1", "operation": "modify", "clause_text": "Keep records for ten years"}]},
        "policy_sections": [],
    }


def test_missing_auth(payload):
    with TestClient(create_app()) as client:
        assert client.post("/api/v1/changes/simulate", json=payload).status_code == 401


@pytest.mark.parametrize("role", ["viewer", "admin", "compliance_officer"])
def test_authenticated_roles_can_simulate(payload, role):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: UserRecord(id=1, username="test", role=role, is_active=True)
    original = deepcopy(payload)
    with TestClient(app) as client:
        response = client.post("/api/v1/changes/simulate", json=payload)
    assert response.status_code == 200
    assert response.json()["simulation"] is True
    assert response.json()["comparison"]["summary"] == {"modified": 1}
    assert payload == original


@pytest.mark.parametrize("invalid", ["stale", "missing_target", "oversized", "whitespace", "extra"])
def test_invalid_requests(payload, invalid):
    if invalid == "stale": payload["proposal"]["base_content_hash"] = "wrong"
    elif invalid == "missing_target": payload["proposal"]["edits"][0]["clause_number"] = "999"
    elif invalid == "oversized": payload["baseline"]["clauses"] *= 51
    elif invalid == "whitespace": payload["proposal"]["edits"][0]["clause_text"] = "   "
    else: payload["approve"] = True
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: UserRecord(id=1, username="test", role="viewer", is_active=True)
    with TestClient(app) as client:
        assert client.post("/api/v1/changes/simulate", json=payload).status_code == 422
