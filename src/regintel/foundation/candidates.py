"""Non-destructive candidate review and conservative exact deduplication."""

import hashlib
import json
from collections import Counter

from regintel.foundation.registry import digest, load


def normalize(value):
    return " ".join(str(value or "").split()).casefold()


def review_candidates(root):
    path = root / "data/processed/validation/e525b18753fd_validation.json"
    report = load(path)
    groups, evidence_groups, rows = {}, {}, []
    for row in report["candidates"]:
        item = row["source"]
        if (
            row.get("human_review_status", "pending") != "pending"
            or item.get("review_status", "pending") != "pending"
        ):
            raise ValueError(
                "This pending-candidate review must not replace existing human decisions"
            )
        # Clause and source identity prevent collapsing distinct legal requirements.
        fields = [
            item.get(k)
            for k in (
                "content_hash",
                "clause_number",
                "obligation_type",
                "actor",
                "action",
                "condition",
                "evidence_quote",
            )
        ]
        key = hashlib.sha256(
            json.dumps([normalize(v) for v in fields]).encode()
        ).hexdigest()
        evidence_key = (item.get("content_hash"), normalize(item.get("evidence_quote")))
        duplicate = groups.get(key)
        if duplicate is None:
            groups[key] = row["candidate_index"]
        evidence_groups.setdefault(evidence_key, []).append(row["candidate_index"])
        rows.append(
            {
                "candidate_index": row["candidate_index"],
                "candidate_identity": key,
                "exact_duplicate_of": duplicate,
                "issues": row["issues"],
                "evidence_match": row["evidence_match"],
                "review_status": "pending",
            }
        )
    return {
        "schema_version": 1,
        "input_sha256": digest(path),
        "source_hash": report["source_metadata"]["sha256"],
        "summary": {
            "candidates": len(rows),
            "canonical_candidates": len(groups),
            "exact_duplicates": len(rows) - len(groups),
            "human_approved": 0,
            "issues": dict(Counter(issue for row in rows for issue in row["issues"])),
        },
        "candidates": rows,
        "canonical_candidate_indexes": list(groups.values()),
        "repeated_evidence_groups": [v for v in evidence_groups.values() if len(v) > 1],
        "notice": "Deterministic review only. No original records removed or approved; repeated evidence is not automatically a duplicate obligation.",
    }
