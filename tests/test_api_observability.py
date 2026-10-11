import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from regintel.api.app import create_app
from regintel.api.dependencies import get_db


def test_request_id_and_safe_structured_logging():
    with patch("regintel.api.observability.logger.info") as log:
        with TestClient(create_app()) as client:
            response = client.get("/health?password=secret", headers={"X-Request-ID": "test-id", "Authorization": "Bearer secret-token"})
    assert response.headers["X-Request-ID"] == "test-id"
    record = json.loads(log.call_args.args[0])
    assert record["route"] == "/health"
    assert record["status_code"] == 200
    assert "secret" not in log.call_args.args[0]


def test_invalid_request_id_replaced():
    with TestClient(create_app()) as client:
        response = client.get("/health", headers={"X-Request-ID": "x" * 100})
    assert len(response.headers["X-Request-ID"]) == 32


def test_internal_error_is_redacted_and_correlated():
    app = create_app()

    @app.get("/test-failure")
    def fail():
        raise RuntimeError("database-password-secret")

    with patch("regintel.api.observability.logger.info") as log:
        with TestClient(app) as client:
            response = client.get("/test-failure")
    assert response.status_code == 500
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert "secret" not in response.text + log.call_args.args[0]


def test_readiness_success_and_database_failure():
    class FakeSession:
        failed = False

        def execute(self, statement):
            assert str(statement) == "SELECT 1"
            if self.failed:
                raise OperationalError("SELECT 1", {}, Exception("secret"))

    db = FakeSession()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        assert client.get("/ready").json() == {"status": "ready"}
        db.failed = True
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
