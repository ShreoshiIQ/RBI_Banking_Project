import hashlib
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('submission_manifest', Path(__file__).parents[1] / 'scripts/build_submission_manifest.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_changed_and_missing_artifacts_are_detected(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    path = tmp_path / 'report.json'
    path.write_bytes(b'original')
    manifest = {'schema_version': 1, 'artifacts': [{'path': path.name, 'bytes': 8, 'sha256': hashlib.sha256(b'original').hexdigest()}]}
    assert module.verify_manifest(manifest)['passed']
    path.write_bytes(b'changed!')
    assert module.verify_manifest(manifest)['issues'][0]['reason'] == 'changed'
    path.unlink()
    assert module.verify_manifest(manifest)['issues'][0]['reason'] == 'missing'


def test_manifest_cannot_read_outside_project(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    manifest = {'schema_version': 1, 'artifacts': [{'path': '../outside', 'bytes': 0, 'sha256': ''}]}
    with pytest.raises(ValueError, match='inside'):
        module.verify_manifest(manifest)
