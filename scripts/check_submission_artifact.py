"""Limited wheel hygiene scan. Never print suspected secret contents."""

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----")


def inspect_wheel(path: Path) -> dict:
    issues = []
    with ZipFile(path) as archive:
        for member in archive.infolist():
            parts = PurePosixPath(member.filename).parts
            if any(part in {".git", ".venv", "__pycache__"} or part == ".env" or part.startswith(".env.") for part in parts):
                issues.append({"file": member.filename, "reason": "local_runtime_file"})
            if member.is_dir():
                continue
            # Bound inspection of individual members rather than expanding arbitrary archives.
            if member.file_size > 10_000_000:
                issues.append({"file": member.filename, "reason": "member_exceeds_scan_limit"})
                continue
            if PRIVATE_KEY.search(archive.read(member)):
                issues.append({"file": member.filename, "reason": "private_key_marker"})
    return {"artifact": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "passed": not issues, "issues": issues,
            "scope": "Wheel runtime-file paths and private-key markers only; API keys, passwords, tokens and dependency vulnerabilities are not exhaustively checked."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    result = inspect_wheel(args.wheel)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
