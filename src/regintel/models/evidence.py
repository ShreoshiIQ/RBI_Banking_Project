"""Separate append-only evidence corpus for one synthetic demo profile."""

import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from regintel.db.base import Base


class EvidenceDocument(Base):
    __tablename__ = "evidence_documents"
    __table_args__ = (
        CheckConstraint("synthetic = true", name="ck_evidence_synthetic"),
        CheckConstraint(
            "profile_id = 'fictional-commercial-bank-demo'",
            name="ck_evidence_single_profile",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    file_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    profile_id: Mapped[str] = mapped_column(String(100), nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False)
    extraction: Mapped[dict] = mapped_column(JSON, nullable=False)


class EvidenceChunk(Base):
    __tablename__ = "evidence_chunks"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_documents.id", ondelete="RESTRICT"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[dict] = mapped_column(JSON, nullable=False)
    method: Mapped[str] = mapped_column(String(30), nullable=False)
    transcription_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)


class EvidenceEmbedding(Base):
    __tablename__ = "evidence_embeddings"
    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("evidence_chunks.id", ondelete="RESTRICT"), primary_key=True
    )
    model: Mapped[str] = mapped_column(String(200), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)


class EvidenceExtractionRun(Base):
    __tablename__ = "evidence_extraction_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evidence_documents.id", ondelete="RESTRICT"), nullable=False
    )
    extraction: Mapped[dict] = mapped_column(JSON, nullable=False)
