from fastapi.testclient import TestClient

from regintel.api.app import create_app


def test_dashboard_and_assets_are_available_without_database_queries():
    client = TestClient(create_app())
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Evidence first. Human decisions." in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    for asset in ("app.js", "style.css"):
        assert client.get(f"/dashboard/assets/{asset}").status_code == 200
    assert client.get("/api/v1/gap-reports").status_code == 401


def test_api_errors_are_not_cached():
    client = TestClient(create_app())
    response = client.get("/api/v1/gap-reports")
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    response = client.get("/api/v1/catalog/unknown")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
