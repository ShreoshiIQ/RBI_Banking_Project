from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from regintel.api.app import create_app
from regintel.api.dependencies import get_db
from regintel.core.config import get_settings
from regintel.models.user import UserRecord as User
from regintel.security.passwords import hash_password, verify_password

SECRET = "test-secret-key-with-at-least-32-characters"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    User.__table__.create(engine)
    with Session(engine) as db:
        db.add_all([
            User(username="officer", hashed_password=hash_password("password")),
            User(username="inactive", hashed_password=hash_password("password"),
                 is_active=False),
        ])
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()
    get_settings.cache_clear()


def test_login_and_me(client):
    response = client.post("/api/v1/auth/login", data={
        "username": "officer", "password": "password",
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    response = client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {token}",
    })
    assert response.status_code == 200
    assert response.json() == {"id": 1, "username": "officer", "is_active": True, "role": "viewer"}


@pytest.mark.parametrize("username,password", [
    ("officer", "wrong"), ("missing", "password"), ("inactive", "password"),
])
def test_rejected_login(client, username, password):
    response = client.post("/api/v1/auth/login", data={
        "username": username, "password": password,
    })
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("subject,expired,secret", [
    ("1", True, SECRET), ("1", False, "wrong-secret" * 4),
    ("999", False, SECRET), ("2", False, SECRET),
    ("invalid", False, SECRET),
])
def test_rejected_tokens(client, subject, expired, secret):
    now = datetime.now(timezone.utc)
    token = jwt.encode({
        "sub": subject, "iat": now,
        "exp": now + timedelta(minutes=-1 if expired else 1), "type": "access",
    }, secret, algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {token}",
    }).status_code == 401


def test_missing_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_password_hashing():
    hashed = hash_password("password")
    assert hashed != "password"
    assert verify_password("password", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("password", "malformed")
