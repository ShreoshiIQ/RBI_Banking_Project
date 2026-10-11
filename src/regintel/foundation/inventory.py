"""Reproducible inventory; database queries must run in a read-only transaction."""

from collections import Counter

from sqlalchemy import text

from regintel.foundation.registry import build_registry, digest, load

REGULATORS = ("RBI", "SEBI", "IRDAI", "BIS", "DORA", "FFIEC")


def file_inventory(root):
    registry = build_registry(root)
    counts = Counter(s["regulator"] for s in registry["sources"])
    policies = list((root / "data/raw/policies").rglob("*.txt"))
    catalogs = [
        root / "data/processed/obligations/e525b18753fd_obligations.json",
        *sorted((root / "data/processed/expansion_previews").glob("*_preview.json")),
    ]
    extracted = 0
    for p in catalogs:
        data = load(p)
        extracted += len(data.get("catalog", data)["obligations"])
    scenarios = load(root / "data/evaluation/synthetic_draft_scenarios.json")[
        "scenarios"
    ]
    review_files = [
        root / "data/processed/validation/e525b18753fd_review_decisions.json",
        *sorted((root / "data/processed/expansion_reviews").glob("*_decisions.json")),
    ]
    reviewed = Counter(
        d.get("status", "pending")
        for p in review_files
        if p.name != "applicability_decisions.json"
        for d in load(p)["decisions"]
    )
    files = [
        root / "data/metadata/rbi_manifest.json",
        root / "data/metadata/synthetic_policy_drafts.json",
        root / "data/metadata/demo_institution_profile.json",
        root / "data/evaluation/synthetic_draft_scenarios.json",
        *catalogs,
        *policies,
        *review_files,
    ]
    result = {
        "regulatory_pdf_snapshots": {k: counts[k] for k in REGULATORS},
        "historical_sources": sum(
            s["status"] == "historical_withdrawal_marker" for s in registry["sources"]
        ),
        "extracted_candidate_rows": extracted,
        "candidate_review_status": dict(reviewed),
        "policy_files": len(policies),
        "synthetic_policy_drafts": len(
            load(root / "data/metadata/synthetic_policy_drafts.json")["policies"]
        ),
        "synthetic_profiles": 1,
        "draft_scenarios": len(scenarios),
        "unique_draft_prompts": len({s["prompt"] for s in scenarios}),
        "source_artifacts": [
            {"path": p.relative_to(root).as_posix(), "sha256": digest(p)}
            for p in sorted(set(files))
        ],
        "notice": "Candidate rows are not unique validated coverage. File-only drafts are not persisted records.",
    }
    evidence_manifest = root / "data/metadata/multimodal_synthetic_demo.json"
    if evidence_manifest.exists():
        from regintel.foundation.registry import local_path

        evidence = load(evidence_manifest)
        if evidence.get("synthetic") is not True:
            raise ValueError("Synthetic evidence manifest label required")
        for record in evidence["files"]:
            if digest(local_path(root, record["path"])) != record["sha256"]:
                raise ValueError("Evidence fixture hash mismatch")
        result["synthetic_evidence_files"] = len(evidence["files"])
        result["source_artifacts"].append(
            {
                "path": evidence_manifest.relative_to(root).as_posix(),
                "sha256": digest(evidence_manifest),
            }
        )
    expansion_manifest = root / "data/metadata/phase3_official_corpora_verified.json"
    if expansion_manifest.exists():
        from regintel.foundation.expansion import verify_corpus

        expansion = load(expansion_manifest)
        unique = {(s["regulator"], s["source_version_id"]) for s in registry["sources"]}
        for corpus in expansion["corpora"]:
            for source in verify_corpus(root, corpus, corpus["profile_id"]):
                unique.add((source["regulator"], source["content_hash"]))
        result["regulatory_pdf_snapshots"] = {
            regulator: sum(r == regulator for r, _ in unique)
            for regulator in REGULATORS
        }
        result["synthetic_profiles"] = len(
            {
                "fictional-commercial-bank-demo",
                *(c["profile_id"] for c in expansion["corpora"]),
            }
        )
        result["source_artifacts"].append(
            {
                "path": expansion_manifest.relative_to(root).as_posix(),
                "sha256": digest(expansion_manifest),
            }
        )
        result["phase3_corpus_access"] = "SEBI offline only; no shared tenant access"
    return result


def database_inventory(connection):
    queries = {
        "regulators": "SELECT regulator, count(*) AS documents FROM regulatory_documents GROUP BY regulator ORDER BY regulator",
        "counts": "SELECT (SELECT count(*) FROM regulatory_document_versions) AS versions,(SELECT count(*) FROM regulatory_obligations) AS obligations,(SELECT count(*) FROM policy_documents) AS policies,(SELECT count(*) FROM policy_document_versions) AS policy_versions,(SELECT count(*) FROM policy_sections) AS policy_sections,(SELECT count(*) FROM policy_section_embeddings) AS embeddings,(SELECT count(DISTINCT policy_section_id) FROM policy_section_embeddings) AS vector_searchable_sections",
        "reviews": "SELECT review_status, count(*) AS obligations FROM regulatory_obligations GROUP BY review_status ORDER BY review_status",
        "indexes": "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname=current_schema() ORDER BY tablename,indexname",
        "embedding_storage": "SELECT pg_relation_size('policy_section_embeddings') AS table_bytes,pg_indexes_size('policy_section_embeddings') AS index_bytes,pg_total_relation_size('policy_section_embeddings') AS total_bytes",
        "rls": "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relkind='r' ORDER BY relname",
        "entity_columns": "SELECT table_name,column_name FROM information_schema.columns WHERE table_schema=current_schema() AND (column_name ILIKE '%tenant%' OR column_name ILIKE '%bank%' OR column_name ILIKE '%institution%' OR column_name ILIKE '%applicab%') ORDER BY table_name,column_name",
        "revision": "SELECT version_num FROM alembic_version",
    }
    if connection.scalar(text("SELECT to_regclass('evidence_documents')")):
        queries["evidence_counts"] = (
            "SELECT (SELECT count(*) FROM evidence_documents) AS documents,(SELECT count(*) FROM evidence_chunks) AS chunks,(SELECT count(*) FROM evidence_embeddings) AS embeddings,(SELECT count(*) FROM evidence_chunks WHERE NOT transcription_verified) AS unverified_chunks"
        )
    if connection.scalar(text("SELECT to_regclass('evidence_extraction_runs')")):
        queries["evidence_extraction_runs"] = (
            "SELECT count(*) AS runs FROM evidence_extraction_runs"
        )
    return {
        name: [dict(row._mapping) for row in connection.execute(text(query))]
        for name, query in queries.items()
    }
