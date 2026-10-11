"""Actual synthetic fixture checks; no independent regulatory accuracy claims."""

import argparse
import copy
import json
from pathlib import Path

import pymupdf

from regintel.evidence.controls import records_from_csv, test_access_reviews
from regintel.evidence.parsers import parse_document
from regintel.foundation.registry import digest, load, local_path


def evaluate(root):
    manifest_path = root / "data/metadata/multimodal_synthetic_demo.json"
    manifest = load(manifest_path)
    if manifest.get("synthetic") is not True:
        raise ValueError("Explicit synthetic fixture manifest required")
    results, csv = [], None
    pdf_citation_checks = []
    banner = "SYNTHETIC DEMONSTRATION - NOT REAL BANK EVIDENCE"
    expectations = {
        "SYN-access-native.pdf": [
            banner,
            "Account SYN-001 last reviewed 2026-10-01",
            "Account SYN-002 last reviewed 2026-01-01",
        ],
        "SYN-access-design.docx": [
            banner,
            "Privileged access reviews are documented for this fictional bank.",
        ],
        "SYN-access-records.xlsx": [banner, "SYN-001", "2026-10-01"],
        "SYN-access-records.csv": [
            "record_id",
            "last_reviewed",
            "SYN-001",
            "SYN-002",
            "2026-10-01",
            "2026-01-01",
        ],
    }
    image_hash = None
    for record in manifest["files"]:
        path = local_path(root, record["path"])
        if digest(path) != record["sha256"]:
            raise ValueError("Fixture hash mismatch")
        parsed = parse_document(path.read_bytes(), path.name)
        image_based = path.suffix.lower() in (".png", ".jpg") or "scanned" in path.name
        expected = "ocr_required" if image_based else "native_text"
        joined = "\n".join(c["text"] for c in parsed["chunks"])
        fragment_checks = [
            fragment in joined for fragment in expectations.get(path.name, [])
        ]
        passed = (
            not parsed["chunks"]
            if image_based
            else bool(fragment_checks) and all(fragment_checks)
        )
        if path.name == "SYN-access.png":
            image_hash = record["sha256"]
        # Missing OCR is an abstention expectation, never evidence of OCR accuracy.
        results.append(
            {
                "file": record["path"],
                "sha256": record["sha256"],
                "expected": expected,
                "passed": passed,
                "chunks": len(parsed["chunks"]),
                "synthetic_expected_fragment_checks": fragment_checks,
                "citation_locations_present": all(
                    bool(c["location"]) for c in parsed["chunks"]
                ),
                "source_text_assertion": "pending_independent_multimodal_labels",
            }
        )
        if parsed["format"] == "csv":
            csv = parsed
        if path.name == "SYN-access-native.pdf":
            with pymupdf.open(path) as document:
                for chunk in parsed["chunks"]:
                    location = chunk["location"]
                    source_text = document[location["page"] - 1].get_text(
                        clip=pymupdf.Rect(location["bbox"])
                    )
                    pdf_citation_checks.append(
                        " ".join(source_text.split()) == " ".join(chunk["text"].split())
                    )
    records = records_from_csv(csv, synthetic=True)
    common = {"as_of": "2026-10-11", "maximum_age_days": 90}
    cases = [
        ("operating_gap", True, records, True),
        ("design_gap", False, records, True),
        ("evidence_gap", True, [], True),
        ("insufficient_evidence", None, [], True),
        ("test_passed", True, records[:1], True),
    ]
    unverified = copy.deepcopy(records[:1])
    unverified[0]["transcription_verified"] = False
    cases.append(("insufficient_evidence", True, unverified, True))
    classifications = []
    for expected, design, supplied, evidence_expected in cases:
        predicted = test_access_reviews(
            design_documented=design,
            records=supplied,
            evidence_expected=evidence_expected,
            **common,
        )
        classifications.append(
            {
                "expected": expected,
                "predicted": predicted["classification"],
                "passed": predicted["classification"] == expected,
            }
        )
    operating = test_access_reviews(design_documented=True, records=records, **common)
    citations = operating["evidence_references"]
    cited_chunks = {c["chunk_id"]: c for c in csv["chunks"]}
    citation_checks = [
        reference["file_sha256"] == csv["file_sha256"]
        and reference["location"] == cited_chunks[reference["chunk_id"]]["location"]
        for reference in citations
    ]
    raw_lines = (
        (root / "data/raw/evidence/synthetic_demo/SYN-access-records.csv")
        .read_text()
        .splitlines()
    )
    for record, reference in zip(records, citations):
        location = reference["location"]
        cited_line = raw_lines[location["line_start"] - 1]
        citation_checks.append(
            cited_line.split(",")[:2] == [record["record_id"], record["last_reviewed"]]
            and location["line_start"] == location["line_end"]
        )
    recorded_ocr = None
    ocr_path = root / "data/processed/validation/phase2_live_ocr_preview.json"
    if ocr_path.exists():
        ocr = load(ocr_path)
        if (
            ocr["file_sha256"] != image_hash
            or ocr.get("live_provider_call") is not True
        ):
            raise ValueError("Recorded OCR does not match the synthetic PNG fixture")
        actual = " ".join(" ".join(c["text"] for c in ocr["chunks"]).split())
        expected_text = " ".join(expectations["SYN-access-native.pdf"])
        recorded_ocr = {
            "artifact_sha256": digest(ocr_path),
            "model": ocr["ocr_model"],
            "source": "previous_recorded_live_call_not_a_new_call",
            "synthetic_fixture_exact_normalized_match": actual == expected_text,
            "human_transcription_verified": False,
            "sample_count": 1,
        }
    return {
        "schema_version": 1,
        "workload": "synthetic_fixture_regression",
        "manifest_sha256": digest(manifest_path),
        "extraction": results,
        "gap_classification": classifications,
        "citation_checks": citation_checks,
        "pdf_citation_checks": pdf_citation_checks,
        "operating_failed_ids": operating["failed_records"],
        "independent_ocr_accuracy": None,
        "recorded_live_ocr_fixture": recorded_ocr,
        "regulatory_evidence_correctness": None,
        "human_approvals_created": 0,
        "notice": "Deterministic engineering fixtures, not held-out regulatory or OCR accuracy scores.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve existing evaluation artifact")
    result = evaluate(Path.cwd().resolve())
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)


if __name__ == "__main__":
    main()
