"""Synthetic privileged-access review test; no inferred regulatory deadlines."""

import json
from datetime import date


def records_from_csv(extraction, *, synthetic):
    if synthetic is not True:
        raise ValueError("Explicit synthetic record label required")
    if extraction["format"] != "csv" or not extraction["chunks"]:
        raise ValueError("Native CSV evidence required")
    header = json.loads(extraction["chunks"][0]["text"])
    if len(header) != len(set(header)) or not {"record_id", "last_reviewed"} <= set(
        header
    ):
        raise ValueError("CSV requires unique record_id and last_reviewed columns")
    result = []
    for chunk in extraction["chunks"][1:]:
        values = json.loads(chunk["text"])
        if len(values) != len(header):
            raise ValueError("CSV row width mismatch")
        row = dict(zip(header, values))
        if "synthetic" in row and row["synthetic"].strip().lower() != "true":
            raise ValueError("CSV record contradicts synthetic declaration")
        result.append(
            {
                **row,
                "synthetic": True,
                "transcription_verified": chunk["transcription_verified"],
                "evidence_reference": {
                    "file_sha256": extraction["file_sha256"],
                    "chunk_id": chunk["chunk_id"],
                    "location": chunk["location"],
                },
            }
        )
    return result


def test_access_reviews(
    *, design_documented, records, as_of, maximum_age_days, evidence_expected=True
):
    if type(maximum_age_days) is not int or maximum_age_days < 0:
        raise ValueError("A nonnegative synthetic control threshold is required")
    cutoff = date.fromisoformat(as_of)
    result = {
        "synthetic": True,
        "control": "privileged_access_review",
        "threshold_days": maximum_age_days,
        "as_of": as_of,
        "review_status": "pending",
        "failed_records": [],
        "evidence_references": [],
    }
    if design_documented is False:
        result["classification"] = "design_gap"
    elif design_documented is not True:
        result["classification"] = "insufficient_evidence"
    elif not records:
        result["classification"] = (
            "evidence_gap" if evidence_expected else "insufficient_evidence"
        )
    else:
        ids, insufficient = set(), False
        for record in records:
            identifier = record.get("record_id")
            if not identifier or identifier in ids:
                raise ValueError("Synthetic record identities must be unique")
            ids.add(identifier)
            reference = record.get("evidence_reference")
            if (
                record.get("synthetic") is not True
                or record.get("transcription_verified") is not True
                or not reference
            ):
                insufficient = True
                continue
            try:
                reviewed = date.fromisoformat(record["last_reviewed"])
            except (ValueError, KeyError, TypeError):
                insufficient = True
                continue
            if reviewed > cutoff:
                insufficient = True
                continue
            result["evidence_references"].append(reference)
            if (cutoff - reviewed).days > maximum_age_days:
                result["failed_records"].append(identifier)
        result["classification"] = (
            "operating_gap"
            if result["failed_records"]
            else "insufficient_evidence"
            if insufficient
            else "test_passed"
        )
        result["incomplete_evidence"] = insufficient
    result["notice"] = (
        "Deterministic synthetic control test, not certification or a human approval. A passing sample does not establish population effectiveness."
    )
    return result
