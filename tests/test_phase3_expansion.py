"""Real snapshots plus isolated fixture-only ingestion and boundary checks."""

import copy
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from regintel.foundation.expansion import (
    BANK,
    BROKER,
    fetch,
    pdf_links,
    preserve,
    verify_corpus,
)
from regintel.foundation.expansion_ingestion import (
    append_bank,
    prepare_bank,
    sebi_review_packet,
)
from regintel.foundation.registry import load
from regintel.models.clause_candidate import RegulatoryClauseCandidate
from regintel.models.obligation import RegulatoryObligation
from regintel.models.regulation import RegulatoryDocument, RegulatoryDocumentVersion

ROOT = Path(__file__).resolve().parents[1]


def corpora():
    return load(ROOT / "data/metadata/phase3_official_corpora_verified.json")["corpora"]


def test_real_sources_are_verified_separate_and_pending():
    bank, broker = corpora()
    assert len(verify_corpus(ROOT, bank, BANK)) == 4
    assert len(verify_corpus(ROOT, broker, BROKER)) == 3
    assert all(
        s["legal_current_status"] == "pending"
        for c in (bank, broker)
        for s in c["sources"]
    )
    with pytest.raises(ValueError, match="profile mismatch"):
        verify_corpus(ROOT, broker, BANK)
    with pytest.raises(ValueError, match="profile mismatch"):
        append_bank(None, ROOT, broker)


@pytest.mark.parametrize(
    "mutation", ["hash", "profile", "regulator", "approval", "duplicate"]
)
def test_modified_registry_rejected(mutation):
    bank = copy.deepcopy(corpora()[0])
    if mutation == "hash":
        bank["sources"][0]["text_sha256"] = "0" * 64
    elif mutation == "profile":
        bank["profile_sha256"] = "0" * 64
    elif mutation == "regulator":
        bank["sources"][0]["regulator"] = "SEBI"
    elif mutation == "approval":
        bank["sources"][0]["applicability"]["decision"] = "applicable"
    else:
        bank["sources"].append(bank["sources"][0])
    with pytest.raises(ValueError):
        verify_corpus(ROOT, bank, BANK)


def test_untrusted_redirect_not_requested():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            302, headers={"location": "https://evil.example/file.pdf"}
        )

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ValueError, match="Non-official"),
    ):
        fetch(client, "https://www.sebi.gov.in/page", "SEBI")
    assert len(calls) == 1


def test_bounded_download_and_embed_resolution(monkeypatch):
    from regintel.foundation import expansion

    monkeypatch.setattr(expansion, "LIMIT", 4)
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, content=b"12345")
            )
        ) as c,
        pytest.raises(ValueError, match="bounded"),
    ):
        fetch(c, "https://www.sebi.gov.in/a", "SEBI")
    html = '<iframe src="/web/?file=https%3A%2F%2Fwww.sebi.gov.in%2Fa.pdf"></iframe>'
    assert pdf_links(html, "https://www.sebi.gov.in/page", "SEBI") == [
        "https://www.sebi.gov.in/a.pdf"
    ]


def test_existing_artifacts_cannot_be_overwritten(tmp_path):
    preserve(tmp_path, "a.pdf", b"original")
    preserve(tmp_path, "a.pdf", b"original")
    with pytest.raises(ValueError, match="differs"):
        preserve(tmp_path, "a.pdf", b"changed")
    assert (tmp_path / "a.pdf").read_bytes() == b"original"


def test_real_bank_extraction_and_sebi_block_citations():
    bank, broker = corpora()
    prepared = prepare_bank(ROOT, bank)
    assert sum(len(p["preview"]["catalog"]["obligations"]) for p in prepared) == 838
    packet = sebi_review_packet(ROOT, broker)
    assert packet["source_blocks"]
    assert all(
        r["profile_id"] == BROKER and r["review_status"] == "pending"
        for r in packet["source_blocks"]
    )
    assert any("stock" in r["evidence_quote"].lower() for r in packet["source_blocks"])
    import pymupdf

    source = broker["sources"][0]
    row = next(
        r
        for r in packet["source_blocks"]
        if r["content_hash"] == source["content_hash"]
    )
    with pymupdf.open(ROOT / source["pdf_path"]) as pdf:
        assert row["evidence_quote"] in pdf[row["location"]["page"] - 1].get_text()


def test_append_only_idempotent_and_review_preserving():
    engine = create_engine("sqlite://")
    exercise_append(engine)


def test_append_only_in_isolated_postgres():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Dedicated test database required")
    if "test" not in (make_url(url).database or "").lower():
        raise ValueError("Explicit test database required")
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    schema = "expansion_test_" + uuid4().hex
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("CREATE SCHEMA " + schema))
            connection.execute(text("SET LOCAL search_path TO " + schema + ",public"))
            exercise_append(connection)
        finally:
            transaction.rollback()  # removes only this uncommitted schema and fixtures
    engine.dispose()


def exercise_append(engine):
    tables = [
        m.__table__
        for m in (
            RegulatoryDocument,
            RegulatoryDocumentVersion,
            RegulatoryClauseCandidate,
            RegulatoryObligation,
        )
    ]
    for table in tables:
        table.create(engine)
    with Session(engine) as db, db.begin():
        db.add(
            RegulatoryDocument(
                regulator="RBI",
                title="Unrelated test fixture",
                jurisdiction="India",
                source_url="https://example.test",
            )
        )
        first = append_bank(db, ROOT, corpora()[0])
        assert first["obligations_inserted"] == 838
        assert (
            db.scalar(
                select(func.count())
                .select_from(RegulatoryObligation)
                .where(RegulatoryObligation.review_status == "pending")
            )
            == 838
        )
        fixture = db.scalar(select(RegulatoryObligation))
        fixture.review_status = "approved"  # simulated test review, never app data
        db.flush()
        second = append_bank(db, ROOT, corpora()[0])
        assert (
            second["obligations_inserted"] == 0 and second["obligations_skipped"] == 838
        )
        assert fixture.review_status == "approved"
        assert db.scalar(select(func.count()).select_from(RegulatoryDocument)) == 5
