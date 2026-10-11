"""Append extraction runs without rewriting original evidence snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "d190f0020002"
down_revision = "d190f0020001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evidence_extraction_runs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("evidence_documents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("extraction", sa.JSON(), nullable=False),
    )


def downgrade():
    raise RuntimeError("Extraction-run removal requires explicit authorization")
