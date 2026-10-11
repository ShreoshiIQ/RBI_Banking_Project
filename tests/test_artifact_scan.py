import importlib.util
from pathlib import Path
from zipfile import ZipFile


spec = importlib.util.spec_from_file_location('artifact_scan', Path(__file__).parents[1] / 'scripts/check_submission_artifact.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_reports_paths_and_markers_without_secret_values(tmp_path):
    path = tmp_path / 'toy.whl'
    with ZipFile(path, 'w') as archive:
        archive.writestr('package/.env', 'password=secret-test-content')
        archive.writestr('package/key.pem', '-----BEGIN PRIVATE KEY-----\nsecret-test-content')
    result = module.inspect_wheel(path)
    assert result['passed'] is False
    assert {issue['reason'] for issue in result['issues']} == {'local_runtime_file', 'private_key_marker'}
    assert 'secret-test-content' not in str(result)


def test_clean_wheel_passes(tmp_path):
    path = tmp_path / 'toy.whl'
    with ZipFile(path, 'w') as archive:
        archive.writestr('package/app.py', 'print("hello")')
    assert module.inspect_wheel(path)['passed'] is True
