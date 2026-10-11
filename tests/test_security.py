
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from regintel.core.config import get_settings

from regintel.security.passwords import (
    hash_password,
    verify_password,
)
from regintel.security.tokens import (
    create_access_token,
    decode_access_token,
)


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setenv(
        "JWT_SECRET_KEY",
        "test-secret-only-not-for-production-1234567890",
    )


def test_password_hashing():
    password = "ExamplePassword123!"

    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)


def test_wrong_password():
    hashed = hash_password("CorrectPassword123!")

    assert not verify_password(
        "WrongPassword123!",
        hashed,
    )


def test_password_hash_is_salted():
    first = hash_password("SamePassword123!")
    second = hash_password("SamePassword123!")

    assert first != second


def test_create_and_decode_token():
    token = create_access_token("user-001")

    assert decode_access_token(token) == "user-001"


def test_invalid_token():
    with pytest.raises(ValueError):
        decode_access_token("invalid.token.value")


def test_expired_token():
    secret = "test-secret-only-not-for-production-1234567890"

    expired = jwt.encode(
        {
            "sub": "user-001",
            "type": "access",
            "iat": datetime.now(timezone.utc)
            - timedelta(hours=2),
            "exp": datetime.now(timezone.utc)
            - timedelta(hours=1),
        },
        secret,
        algorithm="HS256",
    )

    with pytest.raises(ValueError):
        decode_access_token(expired)


def test_wrong_token_type():
    secret = "test-secret-only-not-for-production-1234567890"

    token = jwt.encode(
        {
            "sub": "user-001",
            "type": "refresh",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc)
            + timedelta(minutes=30),
        },
        secret,
        algorithm="HS256",
    )

    with pytest.raises(ValueError):
        decode_access_token(token)


def test_configured_token_expiry(monkeypatch):
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "7")
    get_settings.cache_clear()
    try:
        token = create_access_token("1")
        payload = jwt.decode(
            token, "test-secret-only-not-for-production-1234567890",
            algorithms=["HS256"],
        )
        assert payload["exp"] - payload["iat"] == 7 * 60
    finally:
        get_settings.cache_clear()
