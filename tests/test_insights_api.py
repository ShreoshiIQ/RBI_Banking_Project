import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from regintel.api.app import create_app
from regintel.api.routes.auth import get_current_user
from regintel.models.user import UserRecord


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    monkeypatch.setattr("regintel.api.routes.insights.get_settings", lambda: SimpleNamespace(data_root=str(tmp_path)))
    return tmp_path


@pytest.fixture
def client(data_root):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: UserRecord(id=1, username="t", role="viewer", is_active=True)
    with TestClient(app) as c:
        yield c


def write(root, relative, payload):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")


def test_requires_authentication():
    with TestClient(create_app()) as c:
        assert c.get("/api/v1/insights/summary").status_code == 401


def test_missing_files_are_reported_not_raised(client):
    body = client.get("/api/v1/insights/summary").json()
    assert body["evidence"]["available"] is False and "not found" in body["evidence"]["reason"]
    assert client.get("/api/v1/insights/watch-events").json() == {**client.get("/api/v1/insights/watch-events").json(), "items": []}
    assert client.get("/api/v1/insights/cross-regulation").json()["available"] is False


def test_summary_and_events_read_from_data_root(client, data_root):
    write(data_root, "data/processed/validation/evidence_pack_v2/summary.json", {"silent_errors": 0})
    write(data_root, "data/processed/validation/ai_labelled_retrieval_summary.json", {"methods": {"hybrid": {"precision@5": 0.73}}})
    events = [{"event_id": f"e{i}", "title": f"Notice {i}", "classification": {"kind": "untracked"},
               "applicability": {"hint": "needs_review"}, "secret_internal": "x"} for i in range(3)]
    write(data_root, "data/processed/watch/events.jsonl", "\n".join(json.dumps(e) for e in events) + "\n")
    body = client.get("/api/v1/insights/summary").json()
    assert body["evidence"]["silent_errors"] == 0 and body["retrieval"]["methods"]["hybrid"]["precision@5"] == 0.73
    feed = client.get("/api/v1/insights/watch-events", params={"limit": 2}).json()
    assert feed["total"] == 3 and [e["event_id"] for e in feed["items"]] == ["e2", "e1"]  # newest first
    assert "secret_internal" not in feed["items"][0]


def test_cross_regulation_limits_families(client, data_root):
    report = {"summary": {"families": 3}, "corpus": {"provisions": 9}, "method": {}, "notice": "n",
              "families": [{"family_id": str(i)} for i in range(3)], "contradiction_candidates": []}
    write(data_root, "data/processed/crossreg/cross_regulation_report.json", report)
    body = client.get("/api/v1/insights/cross-regulation", params={"families": 2}).json()
    assert body["available"] and [f["family_id"] for f in body["families"]] == ["0", "1"]


def test_webapp_served_when_built():
    app = create_app()
    built = any(getattr(route, "path", None) == "/app" for route in app.routes)
    from pathlib import Path

    import regintel.api.app as module
    assert built == (Path(module.__file__).parent / "webapp" / "index.html").is_file()
