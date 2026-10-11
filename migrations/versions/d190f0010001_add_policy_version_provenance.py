"""Add synthetic policy provenance without altering existing tables."""

import sqlalchemy as sa
from alembic import op

revision = "d190f0010001"
down_revision = "ac89bf0264c5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "policy_version_provenance",
        sa.Column("version_id", sa.Uuid(), primary_key=True),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
        sa.Column("profile_id", sa.String(100), nullable=False),
        sa.Column("file_sha256", sa.String(64), nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("variant", sa.String(100), nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False),
        sa.Column("source_anchor", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"], ["policy_document_versions.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "review_status = 'pending'", name="ck_policy_provenance_pending"
        ),
        sa.CheckConstraint("synthetic = true", name="ck_policy_provenance_synthetic"),
    )


def downgrade():
    raise RuntimeError(
        "Automatic downgrade disabled: export provenance and obtain explicit removal authorization."
    )
