"""Phase 3 dry run or locked, append-only RBI ingestion with preservation receipt."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from regintel.foundation.expansion_ingestion import (
    append_bank,
    prepare_bank,
    sebi_review_packet,
)
from regintel.foundation.registry import load


def snapshot(connection, tables):
    quote = connection.dialect.identifier_preparer.quote
    return {
        table: Counter(
            hashlib.sha256(row.encode()).hexdigest()
            for row in connection.scalars(
                text(f"SELECT row_to_json(t)::text FROM {quote(table)} t")
            )
        )
        for table in tables
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", action="store_true", help="Append RBI only; never SEBI"
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve prior receipt; choose a new output")
    root = Path.cwd().resolve()
    bank, broker = load(root / "data/metadata/phase3_official_corpora_verified.json")[
        "corpora"
    ]
    prepared = prepare_bank(root, bank)
    packet = sebi_review_packet(root, broker)
    result = {
        "schema_version": 1,
        "database_changed": False,
        "rbi_sources": len(prepared),
        "rbi_candidate_rows": sum(
            len(p["preview"]["catalog"]["obligations"]) for p in prepared
        ),
        "sebi_source_blocks": len(packet["source_blocks"]),
        "sebi_review_packet": packet,
        "human_approvals_created": 0,
        "schema_changes": 0,
        "legal_applicability": "pending",
    }
    if args.database:
        from regintel.db.session import engine

        with engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout='5s'"))
            connection.execute(text("SET LOCAL statement_timeout='30s'"))
            tables = list(
                connection.scalars(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname=current_schema() ORDER BY tablename"
                    )
                )
            )
            quote = connection.dialect.identifier_preparer.quote
            for table in tables:
                connection.execute(
                    text(f"LOCK TABLE {quote(table)} IN SHARE ROW EXCLUSIVE MODE")
                )
            before = snapshot(connection, tables)
            with Session(bind=connection) as session:
                inserted = append_bank(session, root, bank)
                repeat = append_bank(session, root, bank)
                session.flush()
            after = snapshot(connection, tables)
            allowed = {
                "regulatory_documents",
                "regulatory_document_versions",
                "regulatory_clause_candidates",
                "regulatory_obligations",
            }
            for table in tables:
                if before[table] - after[table]:
                    raise ValueError("Existing row changed; rollback")
                if table not in allowed and before[table] != after[table]:
                    raise ValueError("Unrelated table changed; rollback")
            if any(
                repeat[k]
                for k in (
                    "documents_inserted",
                    "versions_inserted",
                    "clauses_inserted",
                    "obligations_inserted",
                )
            ):
                raise ValueError("Rerun is not idempotent; rollback")
            result.update(
                {
                    "database_changed": bool(inserted["obligations_inserted"]),
                    "ingestion": inserted,
                    "rerun": repeat,
                    "all_existing_rows_preserved": True,
                    "table_counts": {
                        t: {"before": before[t].total(), "after": after[t].total()}
                        for t in tables
                    },
                }
            )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "sebi_review_packet"}, indent=2
        )
    )


if __name__ == "__main__":
    main()
