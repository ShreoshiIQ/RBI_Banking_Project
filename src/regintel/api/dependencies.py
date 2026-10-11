
from collections.abc import Generator

from sqlalchemy.orm import Session

from regintel.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Provide a database session for each API request.

    The session is automatically closed when
    the request finishes.
    """
    with SessionLocal() as session:
        yield session
