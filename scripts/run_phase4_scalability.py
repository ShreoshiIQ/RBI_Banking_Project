"""Create a fresh isolated benchmark DB and preserve measured results."""

import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from regintel.core.config import get_settings
from regintel.mapping.scalability import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=10)
    parser.add_argument(
        "--labels",
        type=Path,
        help="Externally reviewed test labels, keyed by corpus size",
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Existing results are immutable")
    data = args.snapshot.read_bytes()
    snapshot = json.loads(data)
    database = "regintel_benchmark_" + uuid4().hex
    url = make_url(get_settings().database_url)
    admin = create_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"connect_timeout": 5},
    )
    with admin.connect() as connection:
        connection.execute(text("CREATE DATABASE " + database))
    admin.dispose()
    report = run(
        snapshot,
        url.set(database=database),
        repetitions=args.repetitions,
        labels=json.loads(args.labels.read_text()) if args.labels else None,
    )
    if args.labels:
        report["labels_sha256"] = hashlib.sha256(args.labels.read_bytes()).hexdigest()
    report["benchmark_database"] = database
    report["snapshot_sha256"] = hashlib.sha256(data).hexdigest()
    report["application_database_access"] = (
        "No writes; benchmark DB is separate and retained"
    )
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(database)
    for target in report["targets"]:
        print(target["size"], target["status"])


if __name__ == "__main__":
    main()
