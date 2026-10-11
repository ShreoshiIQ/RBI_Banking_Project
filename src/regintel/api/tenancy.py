"""Tenant-scoped database sessions for row-level security.

Each transaction on the request's session sets app.tenant_id locally, so the value
never leaks to another request through the connection pool.
"""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from regintel.api.dependencies import get_db
from regintel.api.routes.auth import get_current_user
from regintel.core.config import get_settings
from regintel.models.user import UserRecord

SET_TENANT = text("SELECT set_config('app.tenant_id', :tenant, true)")


def scope_session(session: Session, tenant: str) -> None:
    def set_tenant(_session, _transaction, connection):
        connection.execute(SET_TENANT, {"tenant": tenant})

    event.listen(session, "after_begin", set_tenant)
    if session.in_transaction():  # authentication already opened a transaction
        session.execute(SET_TENANT, {"tenant": tenant})


def get_tenant_db(
    user: Annotated[UserRecord, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Generator[Session, None, None]:
    if get_settings().tenant_isolation_enabled:
        tenant = db.scalar(select(UserRecord.tenant_id).where(UserRecord.id == user.id))
        if not tenant:
            raise PermissionError("User has no tenant")
        scope_session(db, tenant)
    yield db
