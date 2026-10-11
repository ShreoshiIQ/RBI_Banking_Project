
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, deferred, mapped_column

from regintel.db.base import Base


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    role: Mapped[str] = mapped_column(
    String(50),
    nullable=False,
    default="viewer",
    server_default="viewer",
)

    username: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    # Deferred so the model still loads against schemas migrated before tenancy.
    tenant_id: Mapped[str] = deferred(mapped_column(String(100), nullable=False,
                                                    server_default="fictional-commercial-bank-demo"))

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
