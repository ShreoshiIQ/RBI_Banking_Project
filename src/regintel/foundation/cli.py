"""Phase 1 exports and explicitly selected synthetic ingestion."""

import argparse
import json
from pathlib import Path

from sqlalchemy import text

from regintel.foundation.candidates import review_candidates
from regintel.foundation.inventory import database_inventory, file_inventory
from regintel.foundation.policies import ingest_prepared, prepare_policies
from regintel.foundation.registry import build_registry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["inventory", "registry", "candidates", "policies"]
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--database",
        action="store_true",
        help="Read-only inventory or append synthetic policies",
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Output already exists; choose another snapshot name")
    root = args.root.resolve()
    if args.command == "registry":
        result = build_registry(root)
    elif args.command == "candidates":
        result = review_candidates(root)
    elif args.command == "inventory":
        result = {"schema_version": 1, "files": file_inventory(root)}
        if args.database:
            from regintel.db.session import engine

            with (
                engine.connect().execution_options(
                    isolation_level="REPEATABLE READ"
                ) as c,
                c.begin(),
            ):
                c.execute(text("SET TRANSACTION READ ONLY"))
                c.execute(text("SET LOCAL statement_timeout='10s'"))
                result["database"] = database_inventory(c)
    else:
        prepared = prepare_policies(root)
        result = {
            "schema_version": 1,
            "dry_run": not args.database,
            "policies": len(prepared),
            "sections": sum(len(p["sections"]) for p in prepared),
            "profile_id": "fictional-commercial-bank-demo",
        }
        if args.database:
            from regintel.db.session import SessionLocal

            with SessionLocal.begin() as session:
                result["ingestion"] = ingest_prepared(session, prepared)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
