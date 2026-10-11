"""Add separate synthetic evidence corpus; existing tables remain unchanged."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "d190f0020001"
down_revision = "d190f0010001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evidence_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("file_sha256", sa.String(64), unique=True, nullable=False),
        sa.Column("filename", sa.String(300), nullable=False),
        sa.Column("profile_id", sa.String(100), nullable=False),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
        sa.Column("extraction", sa.JSON(), nullable=False),
        sa.CheckConstraint("synthetic = true", name="ck_evidence_synthetic"),
        sa.CheckConstraint(
            "profile_id = 'fictional-commercial-bank-demo'",
            name="ck_evidence_single_profile",
        ),
    )
    op.create_table(
        "evidence_chunks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("evidence_documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("location", sa.JSON(), nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("transcription_verified", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "evidence_embeddings",
        sa.Column(
            "chunk_id",
            sa.String(64),
            sa.ForeignKey("evidence_chunks.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("model", sa.String(200), primary_key=True),
        sa.Column("embedding", Vector(384), nullable=False),
    )


def downgrade():
    raise RuntimeError(
        "Evidence deletion requires explicit authorization; automatic downgrade disabled"
    )
