import json
from pathlib import Path

from bs4 import BeautifulSoup

from regintel.foundation.registry import load
from regintel.mapping.review_screen import render


def test_source_text_cannot_escape_embedded_json_script():
    packet = {
        "queries": [],
        "records": [{"text": '</script><script>alert("fixture")</script>'}],
    }
    html = render(packet)
    parsed = BeautifulSoup(html, "html.parser")
    assert len(parsed.find_all("script")) == 2
    assert json.loads(parsed.find(id="review-data").string)["packet"] == packet


def test_real_screen_starts_with_six_pending_queries_and_full_corpus():
    root = Path(__file__).resolve().parents[1]
    packet = load(
        root / "data/processed/validation/phase4_relevance_review_packet.json"
    )["packet"]
    html = render(packet)
    parsed = BeautifulSoup(html, "html.parser")
    data = json.loads(parsed.find(id="review-data").string)
    assert len(data["packet"]["records"]) == 500
    assert len(data["pending"]["cases"]) == 6
    assert all(
        c["review_status"] == "pending" and not c["relevant_section_ids"]
        for c in data["pending"]["cases"]
    )
    assert parsed.find(id="full-corpus").get("checked") is None
