import numpy as np
import pytest
from fastapi.testclient import TestClient

from regintel.api.app import create_app
from regintel.api.routes.auth import get_current_user
from regintel.crossreg.analysis import analyse, confirm, cross_document_links
from regintel.crossreg.contradictions import detect, quantities
from regintel.models.user import UserRecord


def prov(pid, doc, text, regulator="RBI"):
    return {"provision_id": pid, "regulator": regulator, "document_title": doc, "content_hash": doc,
            "source_url": f"https://example.test/{doc}", "ref": pid, "location": {}, "text": text}


def test_quantities_need_one_action_context():
    assert quantities("Incidents shall be reported within six hours of detection.")["reporting"][0]["hours"] == 6
    assert quantities("Records shall be preserved for five years.")["retention"][0]["hours"] == 5 * 8760
    assert quantities("The board shall meet within 30 days.") == {}  # no action class: do not guess
    assert quantities("Report and review findings within 2 days.") == {}  # ambiguous action class


def test_reporting_divergence_names_shorter_period_as_stricter():
    a = prov("rbi-56", "rbi", "The bank shall report cyber incidents to the regulator within six hours of detection.")
    b = prov("sebi-198", "sebi", "Entities shall report cyber incidents within 24 hours of detection.", "SEBI")
    [finding] = detect(a, b)
    assert finding["type"] == "quantitative_divergence" and "rbi-56" in finding["explanation"]


def test_retention_divergence_names_longer_period_as_stricter():
    a = prov("a", "d1", "Records shall be retained for five years.")
    b = prov("b", "d2", "Records shall be retained for eight years.")
    assert "(b)" in detect(a, b)[0]["explanation"]


def test_polarity_conflict_requires_shared_predicate():
    prohibits = prov("a", "d1", "The bank shall not share customer data with third parties without consent.")
    requires = prov("b", "d2", "The bank shall share customer data with third parties engaged for collection.")
    unrelated = prov("c", "d3", "The CISO shall be a senior official responsible for cyber risk.")
    assert [f["type"] for f in detect(prohibits, requires)] == ["polarity_conflict"]
    assert detect(prohibits, unrelated) == []


def test_retention_erasure_tension():
    keep = prov("a", "d1", "The bank shall preserve transaction records for five years.")
    erase = prov("b", "d2", "Entities shall delete customer records once the purpose is served.")
    assert "retention_erasure_tension" in {f["type"] for f in detect(keep, erase)}


def test_links_are_mutual_and_cross_document_only():
    provisions = [prov("a1", "A", "x"), prov("a2", "A", "x"), prov("b1", "B", "x")]
    vectors = np.array([[1.0, 0.0], [1.0, 0.0], [0.99, 0.141]])
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    links = cross_document_links(provisions, vectors, threshold=0.5, top_k=1)
    assert all(provisions[i]["content_hash"] != provisions[j]["content_hash"] for i, j, _ in links)
    assert len(links) == 1


def test_analyse_families_and_candidates_with_injected_vectors():
    provisions = [
        prov("rbi-ciso", "rbi", "A senior executive shall be designated as the CISO for cyber security."),
        prov("sebi-ciso", "sebi", "Entities shall designate a senior official as CISO for cyber security.", "SEBI"),
        prov("rbi-report", "rbi", "The bank shall report cyber incidents within six hours of detection."),
        prov("sebi-report", "sebi", "Entities shall report cyber incidents within 24 hours of detection.", "SEBI"),
    ]
    vectors = np.array([[1, 0.05, 0], [1, 0, 0.05], [0, 1, 0.05], [0.05, 1, 0]], dtype=float)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    report = analyse(provisions, vectors=vectors)
    assert report["summary"]["families"] == 2 and report["summary"]["cross_regulator_families"] == 2
    assert report["summary"]["contradiction_candidates"] == {"quantitative_divergence": 1}
    assert all(c["review_status"] == "pending" for c in report["contradiction_candidates"])


def test_judge_needs_both_order_swapped_votes():
    a, b = prov("a", "d1", "x"), prov("b", "d2", "y")
    assert confirm(lambda x, y: {"contradiction": True}, a, b)["agreed"] is True
    assert confirm(lambda x, y: {"contradiction": x["provision_id"] == "a"}, a, b)["agreed"] is False


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: UserRecord(id=1, username="t", role="viewer", is_active=True)
    with TestClient(app) as c:
        yield c


def test_compare_endpoint(client):
    body = {"a": {"regulator": "RBI", "ref": "56", "text": "The bank shall report incidents within six hours of detection."},
            "b": {"regulator": "SEBI", "ref": "p.198", "text": "Entities shall report incidents within 24 hours of detection."}}
    response = client.post("/api/v1/cross-regulation/compare", json=body)
    assert response.status_code == 200
    assert response.json()["findings"][0]["type"] == "quantitative_divergence"
    assert client.post("/api/v1/cross-regulation/compare", json={**body, "extra": 1}).status_code == 422


def test_compare_endpoint_requires_auth():
    with TestClient(create_app()) as c:
        assert c.post("/api/v1/cross-regulation/compare", json={}).status_code == 401
