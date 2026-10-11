import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from regintel.api.app import create_app
from regintel.api.dependencies import get_db
from regintel.models.user import UserRecord
from regintel.security.oidc import OIDCVerifier

ISSUER, AUDIENCE = "https://idp.example.test/realms/bank", "regintel-api"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PUBLIC = KEY.public_key()
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(key=KEY, alg="RS256", **overrides):
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": "abc", "iat": now, "exp": now + 300,
              "preferred_username": "officer.a", **overrides}
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, key, algorithm=alg)


@pytest.fixture
def verifier():
    return OIDCVerifier(issuer=ISSUER, audience=AUDIENCE, jwks_url="https://idp.example.test/jwks",
                        key_resolver=lambda _token: PUBLIC)


def test_valid_token_returns_username(verifier):
    assert verifier.verify(token()) == "officer.a"


@pytest.mark.parametrize("bad", [
    token(aud="another-app"),
    token(iss="https://evil.example.test"),
    token(exp=int(time.time()) - 120, iat=int(time.time()) - 600),
    token(key=OTHER_KEY),
    token(preferred_username=None),
    token(sub=None),
])
def test_invalid_tokens_rejected(verifier, bad):
    with pytest.raises(ValueError):
        verifier.verify(bad)


def test_algorithm_confusion_and_none_rejected(verifier):
    pem = PUBLIC.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    now = int(time.time())
    claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": "abc", "iat": now, "exp": now + 300, "preferred_username": "officer.a"}
    import base64
    import hashlib
    import hmac
    import json

    def b64(data):
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
    signing = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()) + "." + b64(json.dumps(claims).encode())
    forged = signing + "." + b64(hmac.new(pem, signing.encode(), hashlib.sha256).digest())
    with pytest.raises(ValueError):
        verifier.verify(forged)
    unsigned = b64(json.dumps({"alg": "none"}).encode()) + "." + b64(json.dumps(claims).encode()) + "."
    with pytest.raises(ValueError):
        verifier.verify(unsigned)


def test_http_endpoints_rejected():
    with pytest.raises(ValueError):
        OIDCVerifier(issuer="http://idp", audience=AUDIENCE, jwks_url="https://idp/jwks")


USERS = {"officer.a": UserRecord(id=7, username="officer.a", role="compliance_officer", is_active=True),
         "disabled.b": UserRecord(id=8, username="disabled.b", role="viewer", is_active=False)}


class FakeSession:

    def get(self, model, key):
        return None

    def scalar(self, statement):
        wanted = statement.compile(compile_kwargs={"literal_binds": True}).string.split("'")[-2]
        return USERS.get(wanted)


@pytest.fixture
def client(monkeypatch, verifier):
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
    monkeypatch.setattr("regintel.api.routes.auth.get_oidc_verifier", lambda: verifier)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeSession()
    with TestClient(app) as c:
        yield c


def me(client, bearer):
    return client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bearer}"})


def test_sso_user_gets_local_role(client):
    response = me(client, token())
    assert response.status_code == 200
    assert response.json()["role"] == "compliance_officer"  # from the local database, not the token


def test_sso_rejects_unprovisioned_disabled_and_invalid(client):
    assert me(client, token(preferred_username="stranger")).status_code == 401
    assert me(client, token(preferred_username="disabled.b")).status_code == 401
    assert me(client, token(aud="another-app")).status_code == 401


def test_without_oidc_configured_foreign_tokens_fail(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 40)
    monkeypatch.setattr("regintel.api.routes.auth.get_oidc_verifier", lambda: None)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: FakeSession()
    with TestClient(app) as c:
        assert me(c, token()).status_code == 401
