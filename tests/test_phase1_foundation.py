"""Actual foundation inputs plus isolated append-only ingestion checks."""

import copy
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from regintel.foundation.candidates import review_candidates
from regintel.foundation.inventory import file_inventory
from regintel.foundation.policies import ingest_prepared, prepare_policies
from regintel.foundation.registry import build_registry, local_path
from regintel.models.policy import PolicyDocument, PolicyDocumentVersion, PolicySection
from regintel.models.policy_provenance import PolicyVersionProvenance

ROOT = Path(__file__).resolve().parents[1]


def test_registry_keeps_withdrawn_and_unverified_sources_out_of_current_catalog():
    result = build_registry(ROOT)
    assert len(result["sources"]) == 10
    assert (
        sum(s["status"] == "historical_withdrawal_marker" for s in result["sources"])
        == 4
    )
    assert all(
        not s["eligible_for_current_approved_catalog"]
        and s["applicability"]["decision"] == "pending"
        for s in result["sources"]
    )


def test_inventory_is_reproducible_and_counts_drafts_separately():
    result = file_inventory(ROOT)
    assert result == file_inventory(ROOT)
    assert result["extracted_candidate_rows"] == 1150
    assert result["policy_files"] == 21
    assert result["draft_scenarios"] == 100 and result["unique_draft_prompts"] == 25
    assert result["candidate_review_status"] == {"pending": 1150}


def test_candidate_review_preserves_pending_status_and_original_input():
    result = review_candidates(ROOT)
    assert result["summary"]["candidates"] == 312
    assert result["summary"]["human_approved"] == 0
    assert all(r["review_status"] == "pending" for r in result["candidates"])
    assert (
        len(result["canonical_candidate_indexes"])
        + result["summary"]["exact_duplicates"]
        == 312
    )


def test_paths_cannot_escape_project():
    with pytest.raises(ValueError):
        local_path(ROOT, "../outside.pdf")


def test_exact_duplicates_grouped_but_distinct_conditions_preserved(monkeypatch):
    from regintel.foundation import candidates

    report = candidates.load(
        ROOT / "data/processed/validation/e525b18753fd_validation.json"
    )
    a = copy.deepcopy(report["candidates"][0])
    b = copy.deepcopy(a)
    b["candidate_index"] = 1000
    c = copy.deepcopy(a)
    c["candidate_index"] = 1001
    c["source"]["condition"] = "A distinct legal condition"
    report["candidates"] = [a, b, c]
    monkeypatch.setattr(candidates, "load", lambda path: report)
    result = candidates.review_candidates(ROOT)
    assert result["summary"]["exact_duplicates"] == 1
    assert result["summary"]["canonical_candidates"] == 2
    assert result["candidates"][1]["exact_duplicate_of"] == a["candidate_index"]


def test_human_decisions_cannot_be_reset_by_review(monkeypatch):
    from regintel.foundation import candidates

    report = candidates.load(
        ROOT / "data/processed/validation/e525b18753fd_validation.json"
    )
    report["candidates"][0]["human_review_status"] = "approved"
    monkeypatch.setattr(candidates, "load", lambda path: report)
    with pytest.raises(ValueError):
        candidates.review_candidates(ROOT)


@pytest.mark.parametrize(
    "field,value",
    [
        ("sha256", "0" * 64),
        ("review_status", "approved"),
        ("policy_code", "REAL-BANK"),
        ("source_anchor", {"content_hash": "0" * 64}),
    ],
)
def test_draft_manifest_tampering_rejected_before_ingestion(monkeypatch, field, value):
    from regintel.foundation import policies

    original = policies.load

    def changed(path):
        data = original(path)
        if Path(path).name == "synthetic_policy_drafts.json":
            data["policies"][0][field] = value
        return data

    monkeypatch.setattr(policies, "load", changed)
    with pytest.raises(ValueError):
        policies.prepare_policies(ROOT)


def test_synthetic_ingestion_is_atomic_idempotent_and_preserves_old_policy():
    engine = create_engine("sqlite+pysqlite://")
    for model in (
        PolicyDocument,
        PolicyDocumentVersion,
        PolicySection,
        PolicyVersionProvenance,
    ):
        model.__table__.create(engine)
    prepared = prepare_policies(ROOT)
    assert len(prepared) == 20
    with Session(engine) as db, db.begin():
        db.add(PolicyDocument(title="Existing policy", policy_code="OLD"))
    with Session(engine) as db, db.begin():
        result = ingest_prepared(db, prepared)
    assert result["inserted_documents"] == 20
    with Session(engine) as db, db.begin():
        assert ingest_prepared(db, prepared)["skipped_versions"] == 20
        assert (
            db.scalar(select(func.count()).select_from(PolicyVersionProvenance)) == 20
        )
        assert (
            db.scalar(
                select(PolicyDocument.title).where(PolicyDocument.policy_code == "OLD")
            )
            == "Existing policy"
        )
    modified = copy.deepcopy(prepared)
    modified[-1]["item"]["topic"] = "tampered"
    with pytest.raises(ValueError), Session(engine) as db, db.begin():
        ingest_prepared(db, modified)
    engine.dispose()


def test_conflict_rolls_back_earlier_new_documents():
    engine = create_engine("sqlite+pysqlite://")
    for model in (
        PolicyDocument,
        PolicyDocumentVersion,
        PolicySection,
        PolicyVersionProvenance,
    ):
        model.__table__.create(engine)
    drafts = prepare_policies(ROOT)
    with Session(engine) as db, db.begin():
        db.add(
            PolicyDocument(
                title="Unrelated existing document",
                policy_code=drafts[-1]["item"]["policy_code"],
            )
        )
    with pytest.raises(ValueError), Session(engine) as db, db.begin():
        ingest_prepared(db, drafts)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(PolicyDocument)) == 1
    engine.dispose()
