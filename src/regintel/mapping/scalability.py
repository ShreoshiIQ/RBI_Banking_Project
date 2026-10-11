"""Measured retrieval in fresh isolated databases, without invented coverage."""

import argparse
import hashlib
import json
import os
import platform
import re
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from regintel.mapping.keyword_matcher import tokenize
from regintel.mapping.retrieval_benchmark import score_retrieval

TARGETS = (500, 2000, 5000, 10000)
QUERIES = (
    "customer identity verification and ongoing due diligence",
    "outsourcing risk assessment and vendor monitoring",
    "incident reporting and cybersecurity controls",
    "credit card customer consent and dispute resolution",
    "digital payment authentication and access review",
    "business continuity and disaster recovery testing",
)


def unique_rows(rows):
    seen, result = set(), []
    for row in sorted(rows, key=lambda r: (r["content_hash"], r["id"])):
        key = (row["content_hash"], " ".join(row["text"].split()))
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result


def percentile(values, p):
    if not values:
        return None
    return float(np.percentile(values, p))


def validate_url(url):
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not re.fullmatch(
        r"regintel_benchmark_[a-f0-9]{32}", parsed.database or ""
    ):
        raise ValueError("A fresh, explicitly named benchmark database is required")
    return parsed


def export_snapshot():
    from regintel.db.session import engine

    with (
        engine.connect().execution_options(isolation_level="REPEATABLE READ") as c,
        c.begin(),
    ):
        c.execute(text("SET TRANSACTION READ ONLY"))
        rows = [
            dict(r._mapping)
            for r in c.execute(
                text(
                    "SELECT o.id::text AS id,o.evidence_quote AS text,v.content_hash,o.source_url,o.start_page,o.end_page,o.review_status "
                    "FROM regulatory_obligations o JOIN regulatory_document_versions v ON v.id=o.document_version_id "
                    "JOIN regulatory_documents d ON d.id=v.document_id WHERE d.regulator='RBI' ORDER BY v.content_hash,o.id"
                )
            )
        ]
    unique = unique_rows(rows)
    return {
        "schema_version": 1,
        "workload": "genuine_source_pending_candidates",
        "raw_candidate_rows": len(rows),
        "unique_rows": len(unique),
        "records": unique,
        "notice": "Source-derived candidates, not validated obligations or human-reviewed test labels.",
    }


def measure(search, queries, workers):
    def attempt(query):
        started = time.perf_counter()
        try:
            ids = search(query)
            return {
                "latency_ms": (time.perf_counter() - started) * 1000,
                "error": None,
                "ids": ids,
                "query": query,
            }
        except Exception as exc:  # noqa: BLE001 - count failed benchmark attempts
            return {
                "latency_ms": (time.perf_counter() - started) * 1000,
                "error": type(exc).__name__,
                "ids": [],
                "query": query,
            }

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        attempts = list(pool.map(attempt, queries))
    elapsed = time.perf_counter() - start
    successes = [r["latency_ms"] for r in attempts if r["error"] is None]
    return {
        "workers": workers,
        "attempts": attempts,
        "elapsed_seconds": elapsed,
        "requests_per_second": len(attempts) / elapsed,
        "successful_requests_per_second": len(successes) / elapsed,
        "p50_ms": percentile(successes, 50),
        "p95_ms": percentile(successes, 95),
        "error_rate": (len(attempts) - len(successes)) / len(attempts),
        "recall_at_5": None,
        "recall_at_10": None,
        "recall_status": "unscored_no_reviewed_relevance_labels",
    }


def stress_snapshot(size=10000):
    if type(size) is not int or not 1 <= size <= 10000:
        raise ValueError("Synthetic stress size must be between 1 and 10000")
    records = [
        {
            "id": f"SYN-STRESS-{i:05d}",
            "content_hash": "synthetic-not-regulatory",
            "text": f"SYNTHETIC infrastructure record {i:05d}: {QUERIES[i % len(QUERIES)]}. Fictional control sample; not a regulatory obligation.",
        }
        for i in range(size)
    ]
    return {
        "schema_version": 1,
        "workload": "synthetic_infrastructure_only",
        "synthetic": True,
        "records": records,
        "regulatory_coverage_rows": 0,
        "notice": "Repeated topic templates with unique synthetic identities; infrastructure stress only, no legal coverage or relevance ground truth.",
    }


def score_labels(cases, methods, selected):
    ids = {r["id"] for r in selected}
    if len(cases) != len(QUERIES) or any(
        case.get("query") != QUERIES[i]
        or case.get("scenario_id") != f"probe-{i}"
        or not set(case.get("relevant_section_ids", [])) <= ids
        for i, case in enumerate(cases)
    ):
        raise ValueError("Labels must match probes and this exact corpus subset")
    rankings = {
        name: {
            f"probe-{i}": attempt["ids"]
            for i, attempt in enumerate(methods[key][0]["attempts"][: len(QUERIES)])
        }
        for name, key in (
            ("bm25", "bm25"),
            ("vector", "exact_vector"),
            ("hybrid", "hybrid"),
        )
    }
    return {str(k): score_retrieval(cases, rankings, k=k) for k in (5, 10)}


def run(snapshot, url, *, repetitions=10, labels=None):
    validate_url(url)
    if snapshot.get("workload") not in (
        "genuine_source_pending_candidates",
        "synthetic_infrastructure_only",
    ):
        raise ValueError("Synthetic workloads require an explicit separate label")
    if snapshot["workload"] == "synthetic_infrastructure_only" and (
        snapshot.get("synthetic") is not True
        or snapshot.get("regulatory_coverage_rows") != 0
    ):
        raise ValueError("Synthetic stress cannot contribute regulatory coverage")
    records = snapshot["records"]
    if len(unique_rows(records)) != len(records) or len(
        {r["id"] for r in records}
    ) != len(records):
        raise ValueError("Duplicate corpus records are not allowed")
    if not 1 <= repetitions <= 100:
        raise ValueError("Bounded positive repetitions required")
    from sentence_transformers import SentenceTransformer

    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    model = SentenceTransformer(model_name, local_files_only=True, device="cpu")
    model.eval()
    qvectors = model.encode(list(QUERIES), normalize_embeddings=True)
    query_vectors = dict(zip(QUERIES, qvectors))
    engine = create_engine(
        url, pool_size=4, max_overflow=0, connect_args={"connect_timeout": 5}
    )
    with engine.begin() as c:
        if c.scalar(text("SELECT count(*) FROM pg_tables WHERE schemaname='public'")):
            raise ValueError("Benchmark database is not empty; refuse overwrite")
        c.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    start = time.perf_counter()
    with ExitStack() as stack:
        connections = [stack.enter_context(engine.connect()) for _ in range(4)]
        for connection in connections:
            connection.execute(text("SELECT 1"))
    connection_warmup_seconds = time.perf_counter() - start
    report = {
        "schema_version": 1,
        "workload": snapshot["workload"],
        "model": model_name,
        "platform": platform.platform(),
        "packages": {
            name: version(name)
            for name in (
                "sentence-transformers",
                "torch",
                "numpy",
                "rank-bm25",
                "pgvector",
                "sqlalchemy",
                "psycopg",
            )
        },
        "model_cached_revision": getattr(
            model[0].auto_model.config, "_commit_hash", None
        ),
        "connection_pool_warmup_seconds": connection_warmup_seconds,
        "latency_scope": "Retrieval and pool acquisition; excludes query encoding and executor waiting. All four pool connections prewarmed.",
        "query_embedding_time_in_latency": False,
        "retrieval_scope": "obligation-to-obligation infrastructure probe, not policy mapping quality",
        "targets": [],
        "query_count": len(QUERIES),
        "repetitions": repetitions,
        "warmup_queries_per_method": len(QUERIES),
    }
    for size in TARGETS:
        if len(records) < size:
            report["targets"].append(
                {
                    "size": size,
                    "status": "unavailable",
                    "available_unique_candidates": len(records),
                    "reason": "No duplication or synthetic substitution for genuine coverage",
                }
            )
            continue
        table = "corpus_" + str(size)
        selected = records[:size]
        start = time.perf_counter()
        vectors = model.encode(
            [r["text"] for r in selected], normalize_embeddings=True, batch_size=32
        )
        if vectors.shape != (size, 384) or not np.isfinite(vectors).all():
            raise ValueError("Invalid measured embeddings")
        embedding_seconds = time.perf_counter() - start
        tokenized = [tokenize(r["text"]) for r in selected]
        start = time.perf_counter()
        bm25 = BM25Okapi(tokenized)
        bm25_seconds = time.perf_counter() - start
        lexical_index_bytes = len(
            json.dumps(
                {
                    "idf": bm25.idf,
                    "doc_freqs": bm25.doc_freqs,
                    "doc_len": bm25.doc_len,
                    "avgdl": bm25.avgdl,
                },
                sort_keys=True,
            ).encode()
        )
        start = time.perf_counter()
        with engine.begin() as c:
            c.execute(
                text(
                    f"CREATE TABLE {table} (id text PRIMARY KEY,quote text NOT NULL,embedding vector(384) NOT NULL)"
                )
            )
            c.execute(
                text(
                    f"INSERT INTO {table} VALUES (:id,:quote,CAST(:vector AS vector))"
                ),
                [
                    {
                        "id": r["id"],
                        "quote": r["text"],
                        "vector": json.dumps(v.tolist()),
                    }
                    for r, v in zip(selected, vectors)
                ],
            )
            c.execute(text(f"ANALYZE {table}"))
        database_seconds = time.perf_counter() - start

        def lexical(
            query, bm25=bm25, tokenized=tokenized, selected=selected, size=size
        ):
            scores = bm25.get_scores(tokenize(query))
            overlapping = set(tokenize(query))
            ids = [i for i in range(size) if overlapping.intersection(tokenized[i])]
            return [
                selected[i]["id"]
                for i in sorted(ids, key=lambda i: (-scores[i], selected[i]["id"]))[:10]
            ]

        def vector(query, table=table):
            encoded = json.dumps(query_vectors[query].tolist())
            with engine.connect() as c:
                return list(
                    c.scalars(
                        text(
                            f"SELECT id FROM {table} ORDER BY embedding <=> CAST(:vector AS vector),id LIMIT 10"
                        ),
                        {"vector": encoded},
                    )
                )

        def hybrid(query, lexical=lexical, vector=vector):
            scores = {}
            for ranked in (lexical(query), vector(query)):
                for rank, identifier in enumerate(ranked, 1):
                    scores[identifier] = scores.get(identifier, 0) + 1 / (60 + rank)
            return sorted(scores, key=lambda k: (-scores[k], k))[:10]

        methods = {}
        for name, search in (
            ("bm25", lexical),
            ("exact_vector", vector),
            ("hybrid", hybrid),
        ):
            for query in QUERIES:
                search(query)
            methods[name] = [
                measure(search, list(QUERIES) * repetitions, workers)
                for workers in (1, 4)
            ]
        relevance = None
        if labels and str(size) in labels:
            relevance = score_labels(labels[str(size)], methods, selected)
        with engine.connect() as c:
            storage = dict(
                c.execute(
                    text(
                        "SELECT pg_relation_size(:t) AS table_bytes,pg_indexes_size(:t) AS index_bytes,pg_total_relation_size(:t) AS total_bytes"
                    ),
                    {"t": table},
                )
                .one()
                ._mapping
            )
        total = embedding_seconds + bm25_seconds + database_seconds
        report["targets"].append(
            {
                "size": size,
                "status": "measured",
                "storage": storage,
                "embedding_seconds": embedding_seconds,
                "bm25_build_seconds": bm25_seconds,
                "bm25_serialized_index_bytes": lexical_index_bytes,
                "database_load_seconds": database_seconds,
                "ingestion_seconds": total,
                "ingestion_rows_per_second": size / total,
                "methods": methods,
                "reviewed_relevance_scores": relevance,
                "vector_index": "exact scan; no ANN index",
                "bm25_storage": "process memory, not included in PostgreSQL storage",
            }
        )
    engine.dispose()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["export", "run", "synthetic"])
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument("--labels", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve previous benchmark artifact")
    if args.command == "export":
        result = export_snapshot()
    elif args.command == "synthetic":
        result = stress_snapshot()
    else:
        data = args.snapshot.read_bytes()
        result = run(
            json.loads(data),
            os.environ["BENCHMARK_DATABASE_URL"],
            repetitions=args.repetitions,
            labels=json.loads(args.labels.read_text()) if args.labels else None,
        )
        if args.labels:
            result["labels_sha256"] = hashlib.sha256(
                args.labels.read_bytes()
            ).hexdigest()
        result["snapshot_sha256"] = hashlib.sha256(data).hexdigest()
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)


if __name__ == "__main__":
    main()
