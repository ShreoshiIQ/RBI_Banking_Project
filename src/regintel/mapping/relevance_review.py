"""Blind, immutable review packets and offline scoring of recorded probes."""

import argparse
import hashlib
import json
from pathlib import Path

from regintel.foundation.registry import digest, load, local_path
from regintel.mapping.retrieval_benchmark import score_retrieval
from regintel.mapping.scalability import QUERIES, unique_rows


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def build_packet(root, snapshot_path, results_path):
    snapshot, results = load(snapshot_path), load(results_path)
    if (
        snapshot.get("workload") != "genuine_source_pending_candidates"
        or results.get("workload") != snapshot["workload"]
    ):
        raise ValueError("Only genuine source candidate probes are accepted")
    if results["snapshot_sha256"] != digest(snapshot_path):
        raise ValueError("Benchmark and snapshot do not match")
    if len(unique_rows(snapshot["records"])) != len(snapshot["records"]):
        raise ValueError("Duplicate source quotes")
    targets = [t for t in results["targets"] if t["status"] == "measured"]
    if len(targets) != 1 or targets[0]["size"] != 500:
        raise ValueError("This packet supports the frozen 500-candidate probe only")
    records = snapshot["records"][:500]
    ids = {r["id"] for r in records}
    if len(ids) != 500:
        raise ValueError("Unique candidate identities required")
    manifest = {r["sha256"]: r for r in load(root / "data/metadata/rbi_manifest.json")}
    sources = {}
    for row in records:
        sha = row["content_hash"]
        if sha not in sources:
            source = manifest[sha]
            path = local_path(root, source["pdf_path"])
            if digest(path) != sha:
                raise ValueError("Original regulatory PDF hash mismatch")
            sources[sha] = {
                "title": source["title"],
                "pdf_path": source["pdf_path"],
                "source_url": source["source_url"],
                "sha256": sha,
                "applicability": "pending",
                "legal_current_status": "pending",
            }
        if (
            type(row["start_page"]) is not int
            or type(row["end_page"]) is not int
            or not 1
            <= row["start_page"]
            <= row["end_page"]
            <= manifest[sha]["page_count"]
        ):
            raise ValueError("Candidate page citation required")
    # Check predictions for consistency, but never show rankings in the blind packet.
    for method in ("bm25", "exact_vector", "hybrid"):
        attempts = targets[0]["methods"][method][0]["attempts"][: len(QUERIES)]
        if len(attempts) != len(QUERIES) or any(
            a["query"] != QUERIES[i]
            or a["error"] is not None
            or len(set(a["ids"])) != len(a["ids"])
            or not set(a["ids"]) <= ids
            for i, a in enumerate(attempts)
        ):
            raise ValueError("Recorded probe predictions are inconsistent")
    return {
        "schema_version": 1,
        "size": 500,
        "profile_id": "fictional-commercial-bank-demo",
        "snapshot_sha256": digest(snapshot_path),
        "results_sha256": digest(results_path),
        "results_canonical_sha256": canonical_hash(results),
        "corpus_sha256": canonical_hash(records),
        "records": records,
        "sources": sources,
        "queries": [
            {"scenario_id": f"probe-{i}", "query": q} for i, q in enumerate(QUERIES)
        ],
        "notice": "Blind relevance review of existing infrastructure probes, not independent held-out compliance evaluation or legal applicability approval.",
    }


def template(packet):
    return {
        "schema_version": 1,
        "packet_sha256": canonical_hash(packet),
        "cases": [
            {
                **q,
                "review_status": "pending",
                "reviewer": None,
                "answerability": "pending",
                "relevant_section_ids": [],
                "rationale": "",
                "full_corpus_reviewed": False,
                "split": "test",
            }
            for q in packet["queries"]
        ],
    }


def suggest(packet, results):
    """Unverified shortlists from recorded lexical/semantic results, not labels."""
    if canonical_hash(results) != packet["results_canonical_sha256"]:
        raise ValueError("Recorded benchmark changed")
    if canonical_hash(packet["records"]) != packet["corpus_sha256"]:
        raise ValueError("Altered review corpus")
    records = {r["id"]: r for r in packet["records"]}
    target = next(
        t
        for t in results["targets"]
        if t["status"] == "measured" and t["size"] == packet["size"]
    )
    cases = []
    for i, query in enumerate(packet["queries"]):
        signals = {}
        for method in ("bm25", "exact_vector", "hybrid"):
            attempt = target["methods"][method][0]["attempts"][i]
            ranked = attempt["ids"]
            if (
                attempt["query"] != query["query"]
                or attempt["error"] is not None
                or len(set(ranked)) != len(ranked)
                or not set(ranked) <= records.keys()
            ):
                raise ValueError("Invalid recorded suggestions")
            for rank, identifier in enumerate(ranked, 1):
                signals.setdefault(identifier, {})[method] = rank
        # Hybrid depends on the other two methods, so isn't independent evidence.
        fused = {
            identifier: sum(
                1 / (60 + ranks[m]) for m in ("bm25", "exact_vector") if m in ranks
            )
            for identifier, ranks in signals.items()
        }
        candidates = []
        for identifier in sorted(fused, key=lambda k: (-fused[k], k)):
            row = records[identifier]
            candidates.append(
                {
                    "candidate_id": identifier,
                    "suggested_relevance": "potentially_relevant",
                    "verification_status": "unverified",
                    "retrieval_ranks": signals[identifier],
                    "rrf_score": fused[identifier],
                    "evidence_quote": row["text"],
                    "content_hash": row["content_hash"],
                    "source_url": row["source_url"],
                    "start_page": row["start_page"],
                    "end_page": row["end_page"],
                    "source_title": packet["sources"][row["content_hash"]]["title"],
                }
            )
        cases.append(
            {
                **query,
                "review_status": "pending",
                "reviewer": None,
                "answerability": "pending",
                "relevant_section_ids": [],
                "suggested_candidates": candidates,
            }
        )
    return {
        "schema_version": 1,
        "packet_sha256": canonical_hash(packet),
        "results_canonical_sha256": canonical_hash(results),
        "recorded_embedding_model": results["model"],
        "new_model_calls": 0,
        "human_approvals_created": 0,
        "cases": cases,
        "notice": "Machine suggestions reuse recorded retrieval predictions. Ranking scores are not probabilities, proof of relevance, or independent ground truth. Review the full corpus; neither method can certify absence of relevant documents.",
    }


def score_packet(packet, reviews, results):
    if reviews.get("schema_version") != 1 or reviews.get(
        "packet_sha256"
    ) != canonical_hash(packet):
        raise ValueError("Stale review packet")
    if canonical_hash(packet["records"]) != packet["corpus_sha256"]:
        raise ValueError("Altered review corpus")
    if canonical_hash(results) != packet["results_canonical_sha256"]:
        raise ValueError("Recorded benchmark changed")
    cases = reviews.get("cases", [])
    if len(cases) != len(packet["queries"]):
        raise ValueError("All probe cases require review")
    known = {r["id"] for r in packet["records"]}
    positive, unanswerable = [], []
    for case, query in zip(cases, packet["queries"]):
        if any(case.get(k) != query[k] for k in ("scenario_id", "query")):
            raise ValueError("Unknown or reordered probe")
        if (
            case.get("review_status") != "approved"
            or case.get("split") != "test"
            or case.get("full_corpus_reviewed") is not True
        ):
            raise ValueError("Full-corpus reviewed test annotations required")
        if any(
            not isinstance(case.get(k), str) or not case[k].strip()
            for k in ("reviewer", "rationale")
        ):
            raise ValueError("Reviewer and rationale required")
        relevant = case.get("relevant_section_ids")
        if (
            not isinstance(relevant, list)
            or any(not isinstance(i, str) for i in relevant)
            or len(set(relevant)) != len(relevant)
            or not set(relevant) <= known
        ):
            raise ValueError("Unknown or duplicate relevant IDs")
        if case.get("answerability") == "relevant_documents_present" and relevant:
            positive.append(case)
        elif (
            case.get("answerability") == "no_relevant_document_in_subset"
            and not relevant
        ):
            unanswerable.append(case["scenario_id"])
        else:
            raise ValueError("Answerability must agree with relevant IDs")
    target = next(
        t
        for t in results["targets"]
        if t["size"] == packet["size"] and t["status"] == "measured"
    )
    predictions = {
        name: {
            q["scenario_id"]: target["methods"][key][0]["attempts"][i]["ids"]
            for i, q in enumerate(packet["queries"])
            if q["scenario_id"] not in unanswerable
        }
        for name, key in (
            ("bm25", "bm25"),
            ("vector", "exact_vector"),
            ("hybrid", "hybrid"),
        )
    }
    return {
        "schema_version": 1,
        "scorable_cases": len(positive),
        "unanswerable_cases": unanswerable,
        "recall_scores": {
            str(k): score_retrieval(positive, predictions, k=k) for k in (5, 10)
        }
        if positive
        else None,
        "notice": "Recall is conditional on nonempty ground truth. Supplied reviewer identities are not authenticated. Relevance approval does not approve regulatory obligations.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "score", "suggest"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("data/processed/validation/phase4_scalability_warm_results.json"),
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path("data/processed/validation/phase4_candidate_snapshot.json"),
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve existing review artifact")
    if args.command == "prepare":
        packet = build_packet(args.root.resolve(), args.snapshot, args.results)
        result = {"packet": packet, "review_template": template(packet)}
    else:
        if not args.packet:
            parser.error("--packet is required for score or suggest")
        packet = load(args.packet)["packet"]
        if args.command == "suggest":
            result = suggest(packet, load(args.results))
        else:
            if not args.reviews:
                parser.error("--reviews is required for score")
            result = score_packet(packet, load(args.reviews), load(args.results))
            result["reviews_sha256"] = digest(args.reviews)
        result["packet_sha256"] = digest(args.packet)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)


if __name__ == "__main__":
    main()
