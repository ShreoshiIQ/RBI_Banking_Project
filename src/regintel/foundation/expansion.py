"""Isolated, hash-bound Phase 3 corpora; never grant legal or tenant approval."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
import pymupdf
from bs4 import BeautifulSoup

from regintel.foundation.registry import digest, load, local_path
from regintel.ingestion.source_status import inspect_source_status

BANK = "fictional-commercial-bank-demo"
BROKER = "fictional-sebi-stockbroker-demo"
HOSTS = {
    "RBI": {"www.rbi.org.in", "rbi.org.in", "rbidocs.rbi.org.in"},
    "SEBI": {"www.sebi.gov.in", "sebi.gov.in"},
}
LIMIT = 30 * 1024 * 1024
SEBI_PAGES = [
    "https://www.sebi.gov.in/legal/circulars/aug-2024/cybersecurity-and-cyber-resilience-framework-cscrf-for-sebi-regulated-entities-res-_85964.html",
    "https://www.sebi.gov.in/legal/circulars/dec-2024/clarifications-to-cybersecurity-and-cyber-resilience-framework-cscrf-for-sebi-regulated-entities-res-_90401.html",
    "https://www.sebi.gov.in/legal/circulars/aug-2025/technical-clarifications-to-cybersecurity-and-cyber-resilience-framework-cscrf-for-sebi-regulated-entities-res-_96329.html",
]


def allowed(url, regulator):
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname in HOSTS[regulator]
        and not parsed.username
        and not parsed.password
        and parsed.port in (None, 443)
    )


def fetch(client, url, regulator):
    for attempt in range(3):
        try:
            return _fetch(client, url, regulator)
        except httpx.TransportError:
            if attempt == 2:
                raise


def _fetch(client, url, regulator):
    """Check each redirect before sending; bound decoded response bytes."""
    for _ in range(6):
        if not allowed(url, regulator):
            raise ValueError("Non-official source or redirect")
        with client.stream("GET", url, follow_redirects=False) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers["location"])
                continue
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > LIMIT:
                    raise ValueError("Source exceeds bounded download size")
                chunks.append(chunk)
            return b"".join(chunks), str(response.url)
    raise ValueError("Too many source redirects")


def pdf_links(html, page_url, regulator):
    links = []
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all(["a", "iframe", "embed"]):
        reference = anchor.get("href") if anchor.name == "a" else anchor.get("src")
        if not reference:
            continue
        url = urljoin(page_url, reference)
        wrapped = parse_qs(urlparse(url).query).get("file")
        if wrapped:
            url = wrapped[0]
        if allowed(url, regulator) and urlparse(url).path.lower().endswith(".pdf"):
            links.append(url)
    return list(dict.fromkeys(links))


def preserve(root, relative, data):
    path = local_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError("Existing immutable artifact differs")
    else:
        with path.open("xb") as stream:
            stream.write(data)
    return path.relative_to(root).as_posix()


def source_snapshot(root, client, regulator, page_url, expected=None):
    page, resolved_page = fetch(client, page_url, regulator)
    links = pdf_links(page, resolved_page, regulator)
    if expected:
        if expected["pdf_urls"][0] not in links:
            raise ValueError("Queued PDF is no longer linked from official page")
        pdf_url = expected["pdf_urls"][0]
    else:
        if len(links) != 1:
            raise ValueError("Ambiguous official PDF links; manual resolution required")
        pdf_url = links[0]
    pdf, resolved_pdf = fetch(client, pdf_url, regulator)
    if not pdf.startswith(b"%PDF-"):
        raise ValueError("Official response is not a PDF")
    sha = hashlib.sha256(pdf).hexdigest()
    if expected and sha != expected["pdf_sha256"]:
        raise ValueError(
            "Live PDF differs from queued preview; regenerate and review separately"
        )
    with pymupdf.open(stream=pdf, filetype="pdf") as document:
        if document.is_encrypted or len(document) > 500:
            raise ValueError("Unsupported PDF")
        pages = [
            {"page_number": i + 1, "text": p.get_text()} for i, p in enumerate(document)
        ]
    status = inspect_source_status(pages)
    soup = BeautifulSoup(page, "html.parser")
    title = soup.find("h1") or soup.find("title")
    page_sha = hashlib.sha256(page).hexdigest()
    folder = f"data/raw/phase3/{regulator.lower()}"
    record = {
        "regulator": regulator,
        "content_hash": sha,
        "source_page_url": page_url,
        "resolved_page_url": resolved_page,
        "source_url": resolved_pdf,
        "pdf_path": preserve(root, f"{folder}/{sha}.pdf", pdf),
        "page_path": preserve(root, f"{folder}/{page_sha}.html", page),
        "page_sha256": page_sha,
        "text_path": preserve(
            root,
            f"{folder}/{sha}.json",
            json.dumps(pages, ensure_ascii=False, sort_keys=True).encode(),
        ),
        "title": expected["observed_title"]
        if expected
        else (title.get_text(" ", strip=True) if title else "Title review required"),
        "page_count": len(pages),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source_status": status,
        "snapshot_verification": "official_page_link_and_pdf_bytes_verified",
        "legal_current_status": "pending",
        "amendment_completeness": "pending",
        "applicability": {
            "profile_id": BANK if regulator == "RBI" else BROKER,
            "decision": "pending",
            "reviewer": None,
        },
        "eligible_for_current_approved_catalog": False,
    }
    return record


def verify_corpus(root, corpus, profile_id):
    """Fail closed on profile mismatch, altered artifacts, or foreign sources."""
    expected = {BANK: "RBI", BROKER: "SEBI"}
    if profile_id not in expected or corpus.get("profile_id") != profile_id:
        raise ValueError("Entity profile mismatch")
    profile = local_path(root, corpus["profile_path"])
    if (
        digest(profile) != corpus["profile_sha256"]
        or load(profile).get("synthetic") is not True
    ):
        raise ValueError("Stale or non-synthetic profile")
    seen = set()
    for source in corpus["sources"]:
        if (
            source["regulator"] != expected[profile_id]
            or source["content_hash"] in seen
        ):
            raise ValueError("Foreign regulator or duplicate source version")
        seen.add(source["content_hash"])
        if source["applicability"] != {
            "profile_id": profile_id,
            "decision": "pending",
            "reviewer": None,
        }:
            raise ValueError("This ingestion path accepts pending applicability only")
        if source["eligible_for_current_approved_catalog"] is not False:
            raise ValueError("No automatic catalog approval")
        if (
            source["snapshot_verification"]
            != "official_page_link_and_pdf_bytes_verified"
        ):
            raise ValueError("Official snapshot verification required")
        if not allowed(source["source_url"], expected[profile_id]):
            raise ValueError("Non-official source URL")
        for field, hash_field in (
            ("pdf_path", "content_hash"),
            ("page_path", "page_sha256"),
            ("text_path", "text_sha256"),
        ):
            if digest(local_path(root, source[field])) != source[hash_field]:
                raise ValueError("Source artifact hash mismatch")
    return corpus["sources"]


def build_corpora(root, client):
    profiles = {
        BANK: "data/metadata/demo_institution_profile.json",
        BROKER: "data/metadata/sebi_stockbroker_profile.json",
    }
    queue = load(root / "data/metadata/rbi_replacement_candidates.json")["documents"]
    corpora = []
    for regulator, profile_id, candidates in (
        ("RBI", BANK, queue),
        ("SEBI", BROKER, SEBI_PAGES),
    ):
        sources = []
        for candidate in candidates:
            source = source_snapshot(
                root,
                client,
                regulator,
                candidate["source_url"] if regulator == "RBI" else candidate,
                candidate if regulator == "RBI" else None,
            )
            source["text_sha256"] = digest(local_path(root, source["text_path"]))
            sources.append(source)
        corpus = {
            "schema_version": 1,
            "profile_id": profile_id,
            "profile_path": profiles[profile_id],
            "profile_sha256": digest(root / profiles[profile_id]),
            "sources": sources,
            "runtime_access": "offline_only",
            "notice": "Separate review corpus, not a tenant or current legally approved catalog.",
        }
        verify_corpus(root, corpus, profile_id)
        corpora.append(corpus)
    return corpora


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve existing snapshot; use another output name")
    with httpx.Client(timeout=30) as client:
        corpora = build_corpora(args.root.resolve(), client)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(
            {"schema_version": 1, "corpora": corpora},
            stream,
            indent=2,
            ensure_ascii=False,
        )


if __name__ == "__main__":
    main()
