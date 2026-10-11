import hashlib

import pymupdf
from fastapi.testclient import TestClient

from regintel.api.app import create_app
from regintel.api.routes.auth import get_current_user
from regintel.api.dependencies import get_db


def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: object()
    def no_database():
        raise AssertionError("Preview must not access the database")
    app.dependency_overrides[get_db] = no_database
    return TestClient(app)


def test_preview_traceability_and_no_persistence():
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((50, 50), "CHAPTER I\n1. The bank shall retain all transaction records securely.\n2. The bank shall retrieve account records upon request.")
        payload = document.tobytes()
    response = client().post('/api/v1/ingestion/preview', files={'file': ('toy.pdf', payload, 'application/pdf')})
    assert response.status_code == 200
    result = response.json()
    assert result['sha256'] == hashlib.sha256(payload).hexdigest()
    assert result['clauses_found'] == 2
    assert result['clauses'][0]['start_page'] == 1


def test_invalid_and_oversized_uploads_rejected():
    for payload, status in ((b'hello', 422), (b'%PDF-broken', 422), (b'%PDF-' + b'x' * 5_000_000, 413)):
        assert client().post('/api/v1/ingestion/preview', files={'file': ('file.pdf', payload)}).status_code == status


def test_authentication_required():
    assert TestClient(create_app()).post('/api/v1/ingestion/preview', files={'file': ('file.pdf', b'hello')}).status_code == 401


def test_page_limit_and_encrypted_document_rejected():
    with pymupdf.open() as document:
        for _ in range(151):
            document.new_page()
        oversized = document.tobytes()
    assert client().post('/api/v1/ingestion/preview', files={'file': ('pages.pdf', oversized)}).status_code == 413
    with pymupdf.open() as document:
        document.new_page()
        encrypted = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw='toy-password', owner_pw='toy-owner')
    assert client().post('/api/v1/ingestion/preview', files={'file': ('encrypted.pdf', encrypted)}).status_code == 422


def test_withdrawn_marker_and_unsupported_layout_are_explicit():
    with pymupdf.open() as document:
        document.new_page().insert_text((50, 50), 'Withdrawn\nAn unsupported source layout without numbered chapters.')
        payload = document.tobytes()
    result = client().post('/api/v1/ingestion/preview', files={'file': ('withdrawn.pdf', payload)}).json()
    assert result['source_status']['current_obligation_extraction_allowed'] is False
    assert result['source_status']['withdrawal_marker_pages'] == [1]
    assert result['clauses_found'] == 0
