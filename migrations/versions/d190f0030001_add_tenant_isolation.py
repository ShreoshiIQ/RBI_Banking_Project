"""Tenant column on bank-specific tables, with row-level security for non-owner roles.

Existing rows are assigned to the demonstration tenant. Regulatory reference data
(regulations, clauses, obligations, candidates, LLM cache) stays shared.
Superusers and the table owner bypass these policies; the API must connect as a
non-owner role (scripts/provision_app_role.py) for isolation to apply.
"""

from alembic import op

revision = "d190f0030001"
down_revision = "d190f0020002"
branch_labels = None
depends_on = None

DEMO_TENANT = "fictional-commercial-bank-demo"
SCOPED = (
    "regulatory_gap_reports", "gap_report_reviews",
    "policy_documents", "policy_document_versions", "policy_sections",
    "policy_section_embeddings", "policy_version_provenance",
    "evidence_documents", "evidence_chunks", "evidence_embeddings", "evidence_extraction_runs",
)
CURRENT = "NULLIF(current_setting('app.tenant_id', true), '')"


def upgrade():
    for table in (*SCOPED, "users"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN tenant_id varchar(100) NOT NULL DEFAULT '{DEMO_TENANT}'")
        op.execute(f"CREATE INDEX ix_{table}_tenant_id ON {table} (tenant_id)")
    for table in SCOPED:
        # New rows default to the session's tenant; owner scripts without a setting keep the demo tenant.
        op.execute(f"ALTER TABLE {table} ALTER COLUMN tenant_id SET DEFAULT COALESCE({CURRENT}, '{DEMO_TENANT}')")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} FOR ALL TO PUBLIC "
            f"USING (tenant_id = {CURRENT}) WITH CHECK (tenant_id = {CURRENT})"
        )


def downgrade():
    for table in SCOPED:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    for table in (*SCOPED, "users"):
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_tenant_id")
        op.execute(f"ALTER TABLE {table} DROP COLUMN tenant_id")
