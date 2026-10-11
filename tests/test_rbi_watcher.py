import json

import pymupdf
import pytest

from regintel.watch import rbi_watcher as w

# Trimmed from the live RBI notifications feed (October 2026), with one synthetic tracked item.
FEED = """﻿<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>NOTIFICATIONS FROM RBI</title>
<item><title><![CDATA[Reserve Bank of India (Payments Banks – Prudential Norms on Capital Adequacy) Third Amendment Directions, 2026]]></title>
<description><![CDATA[<a href="https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13097">MD</a>]]></description>
<link>https://www.rbi.org.in/scripts/NotificationUser.aspx?Id=13734&amp;Mode=0</link><pubDate>Wed, 07 Oct 2026 17:40:00</pubDate></item>
<item><title><![CDATA[Reserve Bank of India (Commercial Banks – Cybersecurity) Amendment Directions, 2026]]></title>
<description><![CDATA[<a href="https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=900">MD</a> <a href="https://rbidocs.rbi.org.in/rdocs/content/pdfs/NT1.pdf">pdf</a>]]></description>
<link>https://www.rbi.org.in/scripts/NotificationUser.aspx?Id=20001&amp;Mode=0</link><pubDate>Thu, 08 Oct 2026 10:00:00</pubDate></item>
<item><title><![CDATA[Know Your Customer (KYC) Amendment Directions, 2026]]></title><description><![CDATA[none]]></description>
<link>https://www.rbi.org.in/scripts/NotificationUser.aspx?Id=20002&amp;Mode=0</link><pubDate>Thu, 08 Oct 2026 11:00:00</pubDate></item>
</channel></rss>""".encode()


def pdf_bytes(lines):
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 60), "Chapter I\n" + "\n".join(lines), fontsize=10)
    return doc.tobytes()


@pytest.fixture
def root(tmp_path):
    (tmp_path / "data/metadata").mkdir(parents=True)
    (tmp_path / "data/processed/expansion_previews").mkdir(parents=True)
    (tmp_path / "data/processed/clauses").mkdir(parents=True)
    (tmp_path / "data/raw/policies/synthetic_drafts").mkdir(parents=True)
    baseline_hash = "b" * 64
    (tmp_path / "data/metadata/phase3_official_corpora_verified.json").write_text(json.dumps({"corpora": [{"sources": [
        {"regulator": "RBI", "title": "Cyber Directions", "content_hash": baseline_hash,
         "source_page_url": "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=900"}]}]}))
    (tmp_path / "data/metadata/demo_institution_profile.json").write_text(json.dumps(
        {"name": "Demo bank", "excluded_entity_types": ["payments_bank", "small_finance_bank"]}))
    (tmp_path / f"data/processed/expansion_previews/{baseline_hash[:12]}_preview.json").write_text(json.dumps({
        "catalog": {"content_hash": baseline_hash, "source_url": "https://rbidocs.rbi.org.in/x.pdf"},
        "clauses": [{"clause_number": "1", "clause_text": "1. The bank shall report cyber incidents within six hours.", "status": "active"},
                    {"clause_number": "2", "clause_text": "2. The bank shall review access quarterly.", "status": "active"}]}))
    (tmp_path / "data/raw/policies/synthetic_drafts/SYN-INC.txt").write_text(
        "POLICY CODE: SYN-INC\nTITLE: Incidents\nOWNER: Security\nSTATUS: SYNTHETIC\n\nSECTION 1: REPORTING\n"
        "The bank reports cyber incidents to the regulator within six hours.\n", encoding="utf-8")
    return tmp_path


def test_parse_feed_extracts_ids_and_directions():
    items = w.parse_feed(FEED)
    assert [i["notification_id"] for i in items] == ["13734", "20001", "20002"]
    assert items[1]["master_direction_ids"] == ["900"] and items[1]["pdf_links"] == ["https://rbidocs.rbi.org.in/rdocs/content/pdfs/NT1.pdf"]
    assert items[0]["published"].startswith("2026-10-07T17:40")


def test_classification_and_applicability(root):
    watchlist = w.build_watchlist(root)
    items = w.parse_feed(FEED)
    assert [w.classify(i, watchlist)["kind"] for i in items] == ["untracked", "tracked_amendment", "title_match"]
    profile = {"name": "Demo", "excluded_entity_types": ["payments_bank"]}
    assert w.applicability_hint(items[0]["title"], profile)["hint"] == "likely_not_applicable"
    assert w.applicability_hint(items[1]["title"], profile)["hint"] == "likely_applicable"
    assert w.applicability_hint(items[2]["title"], profile)["hint"] == "needs_review"


def test_direction_pdf_link_ignores_site_pdfs_and_rejects_ambiguity():
    own = "https://rbidocs.rbi.org.in/rdocs/notification/PDFs/171MD.PDF"
    site = "https://rbidocs.rbi.org.in/rdocs/content/pdfs/Accessibility20012026.pdf"
    assert w.direction_pdf_link([own, site]) == own
    assert w.direction_pdf_link([own, own.replace("171", "172")]) is None
    assert w.direction_pdf_link([site]) is None


def test_changed_direction_produces_clause_diff_and_policy_candidates(root):
    entry = w.build_watchlist(root)["by_page_id"]["900"]
    pdf = pdf_bytes(["1. The bank shall report cyber incidents within two hours.", "2. The bank shall review access quarterly.",
                     "3. The bank shall test backup restoration every month."])
    out = root / "data/processed/watch"
    out.mkdir(parents=True)
    result = w.analyse_direction_pdf(root, "900", entry, pdf, "manual:test.pdf", w.policy_sections(root), out)
    assert result["status"] == "changed" and result["summary"] == {"modified": 1, "unchanged": 1, "added": 1}
    report = json.loads((root / result["report"]).read_text(encoding="utf-8"))
    modified = next(i for i in report["policy_impacts"]["impacts"] if i["change_type"] == "modified")
    assert modified["candidate_policy_sections"][0]["policy_section"]["id"] == "SYN-INC:1"
    assert (root / result["stored"]).read_bytes() == pdf


def test_non_pdf_and_empty_extraction_never_become_changes(root):
    entry = w.build_watchlist(root)["by_page_id"]["900"]
    with pytest.raises(ValueError):
        w.analyse_direction_pdf(root, "900", entry, b"<!DOCTYPE html>challenge", "x", [], root)
    empty = pymupdf.open()
    empty.new_page()
    result = w.analyse_direction_pdf(root, "900", entry, empty.tobytes(), "x", [], root)
    assert result["status"] == "error" and result["error"] == "no_clauses_extracted"


class BlockedClient:
    """Direction page links one PDF; the PDF host answers with a challenge page."""


def test_run_once_retries_blocked_sources_and_skips_seen(root, monkeypatch):
    calls = []

    def fake_fetch(client, url, regulator):
        calls.append(url)
        if "BS_ViewMasDirections" in url:
            return b'<a href="https://rbidocs.rbi.org.in/rdocs/notification/PDFs/900MD.PDF">pdf</a>', url
        return b"<!DOCTYPE html><script>challenge</script>", url

    monkeypatch.setattr("regintel.foundation.expansion.fetch", fake_fetch)
    first = w.run_once(root, client=BlockedClient(), feed_bytes=FEED)
    tracked = next(e for e in first["events"] if e["classification"]["kind"] == "tracked_amendment")
    assert tracked["impact"]["900"]["error"] == "source_blocked_or_not_pdf"
    state = json.loads((root / "data/processed/watch/state.json").read_text())
    assert set(state["seen"]) == {"13734", "20002"}  # blocked item stays unseen for retry
    second = w.run_once(root, client=BlockedClient(), feed_bytes=FEED)
    assert [e["notification_id"] for e in second["events"]] == ["20001"]
    lines = (root / "data/processed/watch/events.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
