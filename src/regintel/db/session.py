
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url

from regintel.core.config import get_settings


settings = get_settings()
connection_options = (
    {"connect_timeout": settings.database_connect_timeout_seconds}
    if make_url(settings.database_url).get_backend_name() == "postgresql"
    else {}
)
engine = create_engine(
    settings.database_url,
    connect_args=connection_options,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=5,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db():
    with SessionLocal() as session:
        yield session
