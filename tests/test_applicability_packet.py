import hashlib

from regintel.ingestion.applicability_packet import build_packet


def test_packet_preserves_scope_and_repeal_evidence_without_deciding():
    texts = [
        "These Directions shall be applicable to Commercial Banks.",
        "These Directions shall not apply to foreign banks.",
        "Existing directions stand repealed.",
        "Banks shall maintain access controls.",
    ]
    preview = {
        "validation": {"source_metadata": {"title": "Test", "source_url": "source", "sha256": "hash", "pdf_path": "test.pdf"}},
        "clauses": [{"clause_number": str(i), "clause_text": text, "start_page": 1, "end_page": 1} for i, text in enumerate(texts)],
    }
    packet = build_packet([preview], {"synthetic": True})
    source = packet["sources"][0]
    assert source["applicability_decision"] is None
    assert source["review_status"] == "pending"
    assert len(source["passages"]) == 3
    assert source["passages"][0]["quote"] == texts[0]
    assert source["passages"][0]["quote_sha256"] == hashlib.sha256(texts[0].encode()).hexdigest()
