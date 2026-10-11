"""Opt-in incremental migration test; only a generated schema in a test DB."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from regintel.foundation.policies import ingest_prepared, prepare_policies
from regintel.models.policy import PolicyDocument, PolicyDocumentVersion, PolicySection


def test_additive_migration_and_policy_ingestion_on_postgres():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Dedicated TEST_DATABASE_URL required")
    if "test" not in (make_url(url).database or "").lower():
        raise ValueError("Refusing a database not explicitly named as a test database")
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "foundation_migration",
        root / "migrations/versions/d190f0010001_add_policy_version_provenance.py",
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    schema = "foundation_test_" + uuid4().hex
    created = False
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE SCHEMA " + schema))
            created = True
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL search_path TO " + schema))
            for model in (PolicyDocument, PolicyDocumentVersion, PolicySection):
                model.__table__.create(connection)
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            with Session(bind=connection) as db:
                db.add(PolicyDocument(title="Existing fixture", policy_code="KEEP"))
                db.flush()
                first = ingest_prepared(db, prepare_policies(root))
                second = ingest_prepared(db, prepare_policies(root))
            assert first["inserted_versions"] == 20 and first["inserted_sections"] == 60
            assert second["skipped_versions"] == 20
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM policy_version_provenance")
                )
                == 20
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM policy_documents WHERE policy_code='KEEP' AND title='Existing fixture'"
                    )
                )
                == 1
            )
    finally:
        if created:
            with engine.begin() as connection:
                connection.execute(text("DROP SCHEMA " + schema + " CASCADE"))
        engine.dispose()
