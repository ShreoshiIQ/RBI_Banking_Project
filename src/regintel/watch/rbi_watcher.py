"""RBI notification watcher: detect new notifications, triage applicability, and run impact analysis.

One pass per invocation (schedule it with cron or a Kubernetes CronJob):
    poll feed -> skip seen notifications -> classify (tracked / title match / untracked)
    -> applicability hint from the entity profile -> for tracked instruments: fetch the
    consolidated direction, compare clauses with the preserved baseline, shortlist
    possibly affected policy sections -> append events and write impact reports.

Every output is a review candidate. Nothing is approved, ingested into the
application database, or treated as a confirmed amendment.
"""

import argparse
import hashlib
import json
import re
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

FEED_URL = "https://www.rbi.org.in/notifications_rss.xml"
USER_AGENT = "RegIntel-research/1.0 (regulatory monitoring prototype)"
MD_LINK = re.compile(r"BS_ViewMasDirections\.aspx\?id=(\d+)", re.IGNORECASE)
TITLE_ALIASES = {"know your customer": "kyc", "kyc": "kyc"}
NOTICE = "Automated monitoring output for review. Not a confirmed amendment, applicability decision, or compliance impact."


def parse_feed(xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes.lstrip(b"\xef\xbb\xbf"))
    items = []
    for item in root.findall("./channel/item"):
        link = (item.findtext("link") or "").strip()
        notification_id = parse_qs(urlparse(link).query, keep_blank_values=True)
        notification_id = next((v[0] for k, v in notification_id.items() if k.lower() == "id"), None)
        description = item.findtext("description") or ""
        published = item.findtext("pubDate")
        items.append({
            "notification_id": notification_id or hashlib.sha256(link.encode()).hexdigest()[:16],
            "title": " ".join((item.findtext("title") or "").replace("�", "-").split()),
            "link": link,
            "published": parsedate_to_datetime(published).isoformat() if published else None,
            "master_direction_ids": sorted(set(MD_LINK.findall(description))),
            "pdf_links": sorted(set(re.findall(r'href="(https://rbidocs\.rbi\.org\.in/[^"]+\.pdf)"', description, re.IGNORECASE))),
        })
    return items


def build_watchlist(root: Path) -> dict:
    """Tracked instruments from preserved corpora, keyed by Master Direction page id."""
    corpora = json.loads((root / "data/metadata/phase3_official_corpora_verified.json").read_text(encoding="utf-8"))["corpora"]
    tracked = {}
    for corpus in corpora:
        for source in corpus["sources"]:
            match = MD_LINK.search(source.get("source_page_url", ""))
            if source["regulator"] == "RBI" and match:
                preview = root / f"data/processed/expansion_previews/{source['content_hash'][:12]}_preview.json"
                tracked[match.group(1)] = {
                    "instrument": source["title"], "page_url": source["source_page_url"],
                    "baseline_hash": source["content_hash"], "baseline_clauses": str(preview.relative_to(root)) if preview.exists() else None,
                }
    kyc = next((root / "data/processed/clauses").glob("*_clauses.json"), None)
    aliases = {"kyc": {"instrument": "Reserve Bank of India (Know Your Customer (KYC)) Directions",
                       "baseline_clauses": str(kyc.relative_to(root)) if kyc else None}}
    return {"by_page_id": tracked, "by_alias": aliases}


def applicability_hint(title: str, profile: dict) -> dict:
    from regintel.applicability.engine import (
        PRESUMED_APPLICABLE,
        feature_rule,
        title_rule,
    )
    found = title_rule(title, profile) or feature_rule(title, profile)
    hint = "needs_review" if found is None else "likely_applicable" if found[0] == PRESUMED_APPLICABLE else "likely_not_applicable"
    return {"hint": hint, "rule": found[1] if found else None, "profile": profile.get("name"),
            "basis": "Title keywords only; applicability requires officer review."}


def classify(item: dict, watchlist: dict) -> dict:
    hits = [pid for pid in item["master_direction_ids"] if pid in watchlist["by_page_id"]]
    if hits:
        return {"kind": "tracked_amendment", "page_ids": hits}
    lowered = item["title"].casefold()
    alias = next((a for phrase, a in TITLE_ALIASES.items() if phrase in lowered), None)
    if alias:
        return {"kind": "title_match", "alias": alias}
    return {"kind": "untracked"}


def policy_sections(root: Path) -> list[dict]:
    from regintel.ingestion.policy_ingestor import extract_metadata, extract_sections
    sections = []
    for path in sorted((root / "data/raw/policies/synthetic_drafts").glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        policy = extract_metadata(text).get("policy_code") or path.stem
        for s in extract_sections(text):
            sections.append({"id": f"{policy}:{s.section_number}", "section_number": s.section_number,
                             "section_title": s.section_title, "section_text": s.section_text, "synthetic": True})
    return sections


def _baseline_version(root: Path, relative: str, document_id: str) -> dict:
    data = json.loads((root / relative).read_text(encoding="utf-8"))
    clauses = data["clauses"]
    content_hash = data.get("catalog", {}).get("content_hash") or data.get("content_hash") or hashlib.sha256(relative.encode()).hexdigest()
    return {"document_id": document_id, "content_hash": content_hash,
            "clauses": [{"clause_number": str(c["clause_number"]), "clause_text": c["clause_text"], "status": c.get("status", "active")} for c in clauses]}


def _dedupe(clauses: list[dict]) -> list[dict]:
    # Extraction can repeat numbers (annexures); keep the first so comparison stays well-defined.
    seen, out = set(), []
    for clause in clauses:
        if clause["clause_number"] not in seen and clause["clause_text"].strip():
            seen.add(clause["clause_number"])
            out.append(clause)
    return out


def direction_pdf_link(links: list[str]) -> str | None:
    """The direction's own PDF; site-wide content PDFs on the same page are ignored. None if ambiguous."""
    candidates = [u for u in links if "/rdocs/notification/pdfs/" in urlparse(u).path.lower()]
    return candidates[0] if len(candidates) == 1 else None


def impact_for_tracked(root: Path, client, page_id: str, entry: dict, sections: list[dict], out_dir: Path) -> dict:
    from regintel.foundation.expansion import fetch, pdf_links

    html, resolved = fetch(client, entry["page_url"], "RBI")
    links = pdf_links(html.decode("utf-8", "replace"), resolved, "RBI")
    link = direction_pdf_link(links)
    if link is None:
        return {"status": "error", "error": "ambiguous_or_missing_direction_pdf", "pdf_links": links}
    pdf, pdf_url = fetch(client, link, "RBI")
    if not pdf.startswith(b"%PDF-"):
        # E.g. a bot-protection challenge page. Never treat it as a new version; retry next run
        # or have an officer supply the PDF with --direction-pdf.
        return {"status": "error", "error": "source_blocked_or_not_pdf", "pdf_url": pdf_url}
    return analyse_direction_pdf(root, page_id, entry, pdf, pdf_url, sections, out_dir)


def analyse_direction_pdf(root: Path, page_id: str, entry: dict, pdf: bytes, pdf_url: str, sections: list[dict], out_dir: Path) -> dict:
    from regintel.changes.compare import compare_versions
    from regintel.changes.impact import shortlist_impacts
    from regintel.foundation.expansion import preserve
    from regintel.ingestion.clause_extractor import extract_clauses
    from regintel.ingestion.pdf_parser import extract_pdf_text

    if not pdf.startswith(b"%PDF-"):
        raise ValueError("Direction file is not a PDF")
    digest = hashlib.sha256(pdf).hexdigest()
    stored = preserve(root, f"data/raw/watch/rbi/{digest}.pdf", pdf)
    if digest == entry["baseline_hash"]:
        return {"status": "unchanged_from_baseline", "sha256": digest, "pdf_url": pdf_url}
    if not entry.get("baseline_clauses"):
        return {"status": "changed_no_baseline_clauses", "sha256": digest, "pdf_url": pdf_url, "stored": stored}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "direction.pdf"
        path.write_bytes(pdf)
        pages = extract_pdf_text(str(path))
    document_id = f"rbi-md-{page_id}"
    new = {"document_id": document_id, "content_hash": digest, "clauses": _dedupe([
        {"clause_number": str(c.clause_number), "clause_text": c.clause_text, "status": c.status} for c in extract_clauses(pages)])}
    if not new["clauses"]:
        # An empty extraction would report every clause as removed; send it to review instead.
        return {"status": "error", "error": "no_clauses_extracted", "sha256": digest, "stored": stored}
    baseline = _baseline_version(root, entry["baseline_clauses"], document_id)
    baseline["clauses"] = _dedupe(baseline["clauses"])
    comparison = compare_versions(baseline, new)
    impacts = shortlist_impacts(comparison, sections)
    report = {"schema_version": 1, "page_id": page_id, "instrument": entry["instrument"], "pdf_url": pdf_url,
              "new_sha256": digest, "baseline_sha256": entry["baseline_hash"], "comparison_summary": comparison["summary"],
              "comparison": comparison, "policy_impacts": impacts, "notice": NOTICE}
    path = out_dir / f"impact_{page_id}_{digest[:12]}.json"
    if not path.exists():
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    affected = sum(1 for i in impacts["impacts"] if i["candidate_policy_sections"])
    return {"status": "changed", "sha256": digest, "pdf_url": pdf_url, "stored": stored,
            "summary": comparison["summary"], "changes_with_policy_candidates": affected, "report": str(path.relative_to(root))}


def run_once(root: Path, *, client, feed_bytes: bytes | None = None, analyse: bool = True) -> dict:
    root = root.resolve()
    out_dir = root / "data/processed/watch"
    out_dir.mkdir(parents=True, exist_ok=True)
    state_path = out_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"seen": {}}
    if feed_bytes is None:
        response = client.get(FEED_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
        response.raise_for_status()
        feed_bytes = response.content
    profile = json.loads((root / "data/metadata/demo_institution_profile.json").read_text(encoding="utf-8"))
    watchlist = build_watchlist(root)
    sections = policy_sections(root) if analyse else []
    started = datetime.now(UTC).isoformat()
    events = []
    for item in parse_feed(feed_bytes):
        if item["notification_id"] in state["seen"]:
            continue
        event = {"event_id": f"rbi-notif-{item['notification_id']}", "detected_at": started, **item,
                 "classification": classify(item, watchlist), "applicability": applicability_hint(item["title"], profile),
                 "review_status": "pending"}
        if analyse and event["classification"]["kind"] == "tracked_amendment":
            event["impact"] = {}
            for page_id in event["classification"]["page_ids"]:
                try:
                    event["impact"][page_id] = impact_for_tracked(root, client, page_id, watchlist["by_page_id"][page_id], sections, out_dir)
                except (httpx.HTTPError, ValueError) as exc:
                    # Leave the notification unseen so the next run retries it.
                    event["impact"][page_id] = {"status": "error", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
        retry = any(v.get("status") == "error" for v in event.get("impact", {}).values())
        if not retry:
            state["seen"][item["notification_id"]] = started
        events.append(event)
    with (out_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
        for event in events:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    kinds = {}
    for event in events:
        kinds[event["classification"]["kind"]] = kinds.get(event["classification"]["kind"], 0) + 1
    return {"run_at": started, "new_notifications": len(events), "by_kind": kinds,
            "likely_applicable": sum(e["applicability"]["hint"] == "likely_applicable" for e in events),
            "events": events, "notice": NOTICE}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--feed-file", type=Path, help="Replay a saved RSS file instead of polling RBI")
    parser.add_argument("--no-analysis", action="store_true", help="Triage only; skip fetching directions")
    parser.add_argument("--interval-minutes", type=int, default=0, help="Repeat every N minutes (0 = single pass)")
    parser.add_argument("--direction-pdf", action="append", default=[], metavar="PAGE_ID=PATH",
                        help="Analyse an officer-downloaded direction PDF for a tracked page id instead of polling")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.direction_pdf:
        watchlist, sections = build_watchlist(root), policy_sections(root)
        out_dir = root / "data/processed/watch"
        out_dir.mkdir(parents=True, exist_ok=True)
        for spec in args.direction_pdf:
            page_id, _, path = spec.partition("=")
            if page_id not in watchlist["by_page_id"]:
                raise SystemExit(f"Page id {page_id} is not a tracked instrument")
            result = analyse_direction_pdf(root, page_id, watchlist["by_page_id"][page_id], Path(path).read_bytes(),
                                           f"manual:{Path(path).name}", sections, out_dir)
            print(page_id, json.dumps({k: v for k, v in result.items() if k != "stored"}))
        return
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60) as client:
        while True:
            result = run_once(root, client=client, analyse=not args.no_analysis,
                              feed_bytes=args.feed_file.read_bytes() if args.feed_file else None)
            print(json.dumps({k: v for k, v in result.items() if k != "events"}, indent=2))
            for event in result["events"]:
                impact = {pid: v.get("status") for pid, v in event.get("impact", {}).items()}
                print(f"- [{event['classification']['kind']}/{event['applicability']['hint']}] {event['title'][:100]} {impact or ''}")
            if args.interval_minutes <= 0:
                break
            time.sleep(args.interval_minutes * 60)


if __name__ == "__main__":
    main()
