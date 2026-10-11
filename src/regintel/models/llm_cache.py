
"""
Persistent cache for validated LLM verification results.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from regintel.db.base import Base


class LLMVerificationCache(Base):
    __tablename__ = "llm_verification_cache"

    cache_key: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    model_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    result_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
