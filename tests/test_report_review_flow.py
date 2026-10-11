"""Synthetic report persistence, real login, API review, and audit integration."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from regintel.api.app import create_app
from regintel.api.dependencies import get_db
from regintel.models.user import UserRecord
from regintel.models.gap_report import RegulatoryGapReportRecord
from regintel.models.gap_report_review import GapReportReviewRecord
from regintel.reporting.persistence import save_gap_report
from regintel.reporting.schemas import RegulatoryGapReport, GapSummary
from regintel.reporting.audit_consistency import inspect_database
from regintel.security.passwords import hash_password


def test_synthetic_report_login_review_and_audit(monkeypatch):
    monkeypatch.setenv('JWT_SECRET_KEY', 'isolated-end-to-end-test-secret-at-least-32-characters')
    engine = create_engine('sqlite+pysqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    try:
        for model in (UserRecord, RegulatoryGapReportRecord, GapReportReviewRecord):
            model.__table__.create(engine)
        with Session(engine) as db:
            db.add(UserRecord(username='test-officer', role='compliance_officer', hashed_password=hash_password('synthetic-test-password')))
            report = RegulatoryGapReport(report_id='synthetic-flow', regulatory_reference='Fictional test instrument',
                assessment_status='needs_review', findings=[],
                summary=GapSummary(total=0, supported=0, partial=0, missing=0, potential_conflicts=0),
                source_policy_sections=[], missing_requirements=[], potential_conflicts=[],
                overall_explanation='Synthetic fixture; no regulatory determination.')
            save_gap_report(db, report)
            db.commit()
        app = create_app()
        def session():
            with Session(engine) as db:
                yield db
        app.dependency_overrides[get_db] = session
        with TestClient(app) as client:
            login = client.post('/api/v1/auth/login', data={'username': 'test-officer', 'password': 'synthetic-test-password'})
            assert login.status_code == 200
            headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
            assert client.get('/api/v1/auth/me', headers=headers).json()['role'] == 'compliance_officer'
            endpoint = '/api/v1/gap-reports/synthetic-flow'
            assert client.get(endpoint, headers=headers).json()['review_status'] == 'pending_review'
            assert client.get(endpoint + '/reviews', headers=headers).json()['reviews'] == []
            decision = client.post(endpoint + '/review', headers=headers, json={'decision': 'rejected', 'comment': 'Synthetic fixture has no supporting evidence.'})
            assert decision.status_code == 200
            detail = client.get(endpoint, headers=headers).json()
            assert detail['review_status'] == 'rejected'
            assert detail['report']['review_status'] == 'rejected'
            history = client.get(endpoint + '/reviews', headers=headers).json()['reviews']
            assert len(history) == 1
            assert history[0]['new_status'] == 'rejected'
            assert history[0]['reviewer_id'] == decision.json()['reviewer_id']
            assert client.post(endpoint + '/review', headers=headers, json={'decision': 'approved', 'comment': 'Duplicate decision'}).status_code == 400
        with Session(engine) as db:
            assert inspect_database(db)['consistent'] is True
    finally:
        engine.dispose()
