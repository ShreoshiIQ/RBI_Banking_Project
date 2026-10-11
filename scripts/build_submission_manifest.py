"""Record hashes of existing submission artifacts without bundling secrets."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    "dist/regulatory_compliance_ai-0.1.0-py3-none-any.whl",
    "dependency_audit.json", "linux_dependency_audit.json",
    "linux_dependency_audit_before_updates.json", "linux_image_audit_metadata.json",
    "linux_image_requirements.txt", "README.md", "Dockerfile", "pyproject.toml", "uv.lock",
)


def build_manifest():
    artifacts = []
    for relative in (*ARTIFACTS, *(str(path.relative_to(ROOT)).replace('\\', '/') for path in sorted((ROOT / 'docs').glob('*.md')))):
        path = ROOT / relative
        payload = path.read_bytes()
        artifacts.append({"path": relative, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
    image = json.loads((ROOT / 'linux_image_audit_metadata.json').read_text(encoding='utf-8'))
    return {"schema_version": 1, "artifacts": artifacts, "audited_image": image,
            "notice": "Hashes identify files, not correctness or certification. Image identity is from the saved audit snapshot; the current tag may change.",
            "pending": ["reviewed regulatory applicability and obligation catalog", "empirical project benchmarks",
                        "remaining dashboard interaction and accessibility checks", "persisted ingestion jobs",
                        "full assessment deployment", "comprehensive secret and OS-package scanning"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--output', type=Path, default=ROOT / 'submission_manifest.json')
    mode.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify:
        result = verify_manifest(json.loads(args.verify.read_text(encoding='utf-8')))
        print(json.dumps(result, indent=2))
        if not result['passed']:
            raise SystemExit(1)
        return
    result = build_manifest()
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(f"Recorded {len(result['artifacts'])} artifact hashes in {args.output.name}")


def verify_manifest(manifest):
    if manifest.get('schema_version') != 1 or not isinstance(manifest.get('artifacts'), list) or not manifest['artifacts']:
        raise ValueError('A version 1 manifest with artifact entries is required')
    issues, seen = [], set()
    for artifact in manifest['artifacts']:
        relative = artifact['path']
        if not isinstance(relative, str) or not relative or relative in seen:
            raise ValueError('Artifact paths must be nonempty and unique')
        seen.add(relative)
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT.resolve()):
            raise ValueError('Artifact paths must stay inside the project')
        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            issues.append({'path': relative, 'reason': 'missing'})
            continue
        if len(payload) != artifact['bytes'] or hashlib.sha256(payload).hexdigest() != artifact['sha256']:
            issues.append({'path': relative, 'reason': 'changed'})
    return {'passed': not issues, 'artifacts_checked': len(seen), 'issues': issues}


if __name__ == '__main__':
    main()
