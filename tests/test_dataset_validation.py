from copy import deepcopy

from regintel.ingestion.validate_dataset import evidence_match, validate_catalog


def fixture():
    text = "Banks shall maintain transaction records for five years."
    item = {
        "clause_number": "46", "actor": "Banks", "evidence_quote": text,
        "source_clause_id": "clause-id", "document_version_id": "version-id",
        "source_url": "https://www.rbi.org.in/example", "content_hash": "hash",
        "start_page": 1, "end_page": 1, "review_status": "pending",
    }
    return ({"obligations": [item]}, [{"clause_number": "46", "clause_text": text,
        "status": "active", "start_page": 1, "end_page": 1}],
        {"sha256": "hash", "source_url": item["source_url"], "page_count": 2})


def test_preserves_source_and_never_approves():
    catalog, clauses, manifest = fixture()
    original = deepcopy(catalog)
    report = validate_catalog(catalog, clauses, manifest)
    assert report["summary"]["needs_review"] == 0
    assert report["candidates"][0]["validation_status"] == "candidate"
    assert report["candidates"][0]["human_review_status"] == "pending"
    assert catalog == original


def test_duplicates_normalize_whitespace():
    catalog, clauses, manifest = fixture()
    second = deepcopy(catalog["obligations"][0])
    second["evidence_quote"] = second["evidence_quote"].replace(" ", "\n")
    catalog["obligations"].append(second)
    report = validate_catalog(catalog, clauses, manifest)
    assert report["candidates"][1]["duplicate_of"] == 0
    assert "duplicate_evidence" in report["candidates"][1]["issues"]


def test_traceability_and_metadata_failures():
    catalog, clauses, manifest = fixture()
    item = catalog["obligations"][0]
    item.update(evidence_quote="Invented evidence", content_hash="wrong", end_page=3, actor="Unresolved")
    reasons = validate_catalog(catalog, clauses, manifest)["candidates"][0]["issues"]
    assert {"evidence_not_in_source_clause", "source_hash_mismatch", "invalid_page_range", "unresolved_actor"} <= set(reasons)


def test_inactive_and_missing_clauses():
    catalog, clauses, manifest = fixture()
    clauses[0]["status"] = "deleted"
    assert "inactive_source_clause" in validate_catalog(catalog, clauses, manifest)["candidates"][0]["issues"]
    assert "missing_source_clause" in validate_catalog(catalog, [], manifest)["candidates"][0]["issues"]


def test_inherited_evidence_requires_source_reconstruction():
    clause = {
        "clause_number": "46", "status": "active",
        "clause_text": "REs shall,\n(a) maintain transaction records;\n(b) preserve identification records;",
    }
    item = {
        "extraction_method": "rule_based_v4_1_inherited",
        "evidence_quote": "REs shall,\n(b) preserve identification records;",
    }
    assert evidence_match(item, clause) == "inherited_reconstruction"
    item["evidence_quote"] = "REs shall,\n(b) destroy identification records;"
    assert evidence_match(item, clause) == "unmatched"
    item["evidence_quote"] = "REs shall,\n(b) preserve identification records;"
    item["extraction_method"] = "rule_based_v4_1_explicit"
    assert evidence_match(item, clause) == "unmatched"


def test_inheritance_does_not_cross_unrelated_text():
    clause = {
        "clause_number": "46", "status": "active",
        "clause_text": "REs shall,\n(a) maintain transaction records.\nUnrelated explanation.\n(b) preserve identification records;",
    }
    item = {
        "extraction_method": "rule_based_v4_1_inherited",
        "evidence_quote": "REs shall,\n(b) preserve identification records;",
    }
    assert evidence_match(item, clause) == "unmatched"
