
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
)
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from regintel.api.dependencies import get_db
from regintel.models.user import UserRecord as User
from regintel.security.oidc import get_oidc_verifier
from regintel.security.passwords import (
    hash_password,
    verify_password,
)
from regintel.security.tokens import (
    create_access_token,
    decode_access_token,
)

# --------------------------------------------------
# Router and OAuth2 configuration
# --------------------------------------------------

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login"
)


# Dummy hash reduces timing differences between
# nonexistent users and incorrect passwords.
_dummy_hash = hash_password("unused-dummy-password")


# --------------------------------------------------
# Response schemas
# --------------------------------------------------

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str

    id: int
    username: str
    is_active: bool


# --------------------------------------------------
# Authentication error helper
# --------------------------------------------------

def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


# --------------------------------------------------
# Get authenticated user
# --------------------------------------------------

def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:

    try:
        # decode_access_token() returns a user ID
        # as a string, for example "1".
        user_id = int(decode_access_token(token))

        if user_id <= 0:
            raise ValueError("Invalid user ID")

        user = db.get(User, user_id)

    except (ValueError, TypeError):
        # Not a local token: try the configured identity provider, if any.
        verifier = get_oidc_verifier()
        if verifier is None:
            raise _unauthorized() from None
        try:
            username = verifier.verify(token)
        except ValueError:
            raise _unauthorized() from None
        user = db.scalar(select(User).where(User.username == username))

    if user is None or not user.is_active:
        raise _unauthorized()

    return user


# --------------------------------------------------
# Login endpoint
# --------------------------------------------------

@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    form: Annotated[
        OAuth2PasswordRequestForm,
        Depends(),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:

    user = db.scalar(
        select(User).where(
            User.username == form.username
        )
    )

    # Always verify a password hash, even when
    # the username does not exist.
    password_hash = (
        user.hashed_password
        if user is not None
        else _dummy_hash
    )

    valid_password = verify_password(
        form.password,
        password_hash,
    )

    if (
        user is None
        or not valid_password
        or not user.is_active
    ):
        raise _unauthorized()

    access_token = create_access_token(
        str(user.id)
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )


# --------------------------------------------------
# Current user endpoint
# --------------------------------------------------

@router.get(
    "/me",
    response_model=UserResponse,
)
def me(
    user: Annotated[
        User,
        Depends(get_current_user),
    ],
) -> User:

    return user
