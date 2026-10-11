
from typing import Annotated

from fastapi import Depends, HTTPException, status

from regintel.api.routes.auth import get_current_user
from regintel.models.user import UserRecord


def require_roles(*allowed_roles: str):
    """
    Require an authenticated user with one of
    the specified roles.
    """

    def check_role(
        user: Annotated[
            UserRecord,
            Depends(get_current_user),
        ],
    ) -> UserRecord:

        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

        return user

    return check_role
