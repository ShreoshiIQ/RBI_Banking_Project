
import os
from datetime import datetime, timedelta, timezone

import jwt
from regintel.core.config import get_settings
from dotenv import load_dotenv
from jwt import InvalidTokenError


load_dotenv()

JWT_ALGORITHM = "HS256"


def get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY")

    if not secret or len(secret) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must be configured "
            "with at least 32 characters"
        )

    return secret


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(
            minutes=get_settings().access_token_expire_minutes
        ),
        "type": "access",
    }

    return jwt.encode(
        payload,
        get_jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            options={
                "require": ["sub", "iat", "exp", "type"]
            },
        )

        if payload.get("type") != "access":
            raise ValueError("Invalid token type")

        user_id = payload.get("sub")

        if not isinstance(user_id, str) or not user_id:
            raise ValueError("Invalid token subject")

        return user_id

    except InvalidTokenError as exc:
        raise ValueError(
            "Invalid or expired access token"
        ) from exc
