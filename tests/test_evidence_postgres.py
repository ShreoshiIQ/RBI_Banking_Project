"""Isolated PostgreSQL evidence migration and vector integration; no quality scores."""

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

from regintel.evidence.parsers import parse_document
from regintel.evidence.pipeline import (
    index_evidence,
    persist_evidence,
    retrieve_evidence,
)


def test_evidence_migration_and_retrieval_in_isolated_postgres():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Dedicated test database required")
    if "test" not in (make_url(url).database or "").lower():
        raise ValueError("Explicit test database required")
    path = (
        Path(__file__).resolve().parents[1]
        / "migrations/versions/d190f0020001_add_demo_evidence.py"
    )
    spec = importlib.util.spec_from_file_location("evidence_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    schema = "evidence_test_" + uuid4().hex
    created = False
    try:
        with engine.begin() as c:
            c.execute(text("CREATE SCHEMA " + schema))
            created = True
        with engine.begin() as c:
            c.execute(text("SET LOCAL search_path TO " + schema + ",public"))
            with Operations.context(MigrationContext.configure(c)):
                migration.upgrade()
                followup = importlib.util.spec_from_file_location(
                    "evidence_runs",
                    path.parent / "d190f0020002_add_evidence_extraction_runs.py",
                )
                runs = importlib.util.module_from_spec(followup)
                followup.loader.exec_module(runs)
                runs.upgrade()
            with Session(bind=c) as db:
                result = parse_document(
                    b"record_id,last_reviewed\nSYN-001,2026-10-01\n", "synthetic.csv"
                )
                assert persist_evidence(db, result, "synthetic.csv", synthetic=True)[
                    "inserted"
                ]
                embed = lambda text: [1.0] + [0.0] * 383
                assert (
                    index_evidence(db, embed=embed, model="synthetic-test-vector") == 2
                )
                assert (
                    index_evidence(db, embed=embed, model="synthetic-test-vector") == 0
                )
                for method in ("bm25", "vector", "hybrid"):
                    matches = retrieve_evidence(
                        db,
                        "last reviewed SYN",
                        method=method,
                        embed=embed,
                        model="synthetic-test-vector",
                    )
                    assert matches and all(
                        m["location"]["kind"] == "csv" for m in matches
                    )
    finally:
        if created:
            with engine.begin() as c:
                c.execute(text("DROP SCHEMA " + schema + " CASCADE"))
        engine.dispose()
