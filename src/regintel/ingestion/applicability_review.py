"""Validate offline applicability annotations against a source packet."""

import argparse
import hashlib
import json
from pathlib import Path


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def template(packet: dict) -> dict:
    return {"schema_version": 1, "profile_hash": digest(packet["demo_profile"]), "decisions": [{
        "content_hash": source["content_hash"], "packet_source_hash": digest(source),
        "decision": "pending", "reviewer": "", "rationale": "",
        "cited_clause_numbers": [], "conditions": "",
    } for source in packet["sources"]]}


def validate(packet: dict, reviews: dict) -> dict:
    if reviews.get("schema_version") != 1 or reviews.get("profile_hash") != digest(packet["demo_profile"]):
        raise ValueError("Unsupported review schema or stale institution profile")
    sources = {source["content_hash"]: source for source in packet["sources"]}
    seen = set()
    counts = {"pending": 0, "applicable": 0, "not_applicable": 0, "conditional": 0}
    for row in reviews["decisions"]:
        key = row["content_hash"]
        if key not in sources or key in seen:
            raise ValueError("Unknown or duplicate source")
        seen.add(key)
        source = sources[key]
        if row.get("packet_source_hash") != digest(source):
            raise ValueError("Stale source passages")
        decision = row.get("decision")
        if decision not in counts:
            raise ValueError("Invalid applicability decision")
        if decision != "pending":
            for field in ("reviewer", "rationale"):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    raise ValueError(f"Decision requires {field}")
            citations = row.get("cited_clause_numbers", [])
            known = {passage["clause_number"] for passage in source["passages"]}
            if not citations or any(citation not in known for citation in citations):
                raise ValueError("Decision requires citations to supplied passages")
            if decision == "conditional" and not row.get("conditions", "").strip():
                raise ValueError("Conditional applicability requires conditions")
        counts[decision] += 1
    counts["pending"] += len(sources) - len(seen)
    return {"summary": counts, "decisions": reviews["decisions"], "notice": "Self-reported offline annotations; no authenticated approval or legal certification."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packet = json.loads(Path("data/processed/expansion_reviews/applicability_packet.json").read_text(encoding="utf-8"))
    result = validate(packet, json.loads(args.decisions.read_text(encoding="utf-8"))) if args.decisions else template(packet)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)


if __name__ == "__main__":
    main()
