"""Download queued RBI PDFs using the existing ingestion implementation."""

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from regintel.ingestion.download_rbi import allowed_url, download_document, load_manifest, save_manifest


def main():
    queue = json.loads(Path("data/metadata/rbi_expansion_candidates.json").read_text(encoding="utf-8"))
    records = load_manifest()
    failures = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for item in queue["documents"]:
            try:
                response = client.get(item["source_url"])
                response.raise_for_status()
                if not allowed_url(str(response.url)):
                    raise ValueError("Unexpected source redirect")
                soup = BeautifulSoup(response.text, "html.parser")
                urls = list(dict.fromkeys(
                    urljoin(str(response.url), a["href"])
                    for a in soup.find_all("a", href=True)
                    if allowed_url(urljoin(str(response.url), a["href"]))
                    and urlparse(urljoin(str(response.url), a["href"])).path.lower().endswith(".pdf")
                    and "/notification/" in urlparse(urljoin(str(response.url), a["href"])).path.lower()
                ))
                if len(urls) != 1:
                    raise ValueError(f"Expected one document PDF, found {len(urls)}; manual resolution needed")
                download_document(client, {"title": item["title"], "url": urls[0]}, records)
                record = next(r for r in records if r["source_url"] == urls[0])
                record.update({
                    "discovery_id": item["id"], "source_page_url": item["source_url"],
                    "publication_date": item["publication_date"],
                    "observed_updated_as_on": item.get("observed_updated_as_on"),
                    "applicability_review_status": "pending",
                })
                save_manifest(records)
                print(item["id"], record["sha256"], record["page_count"], "pages")
            except (httpx.HTTPError, ValueError, StopIteration) as exc:
                failures.append(item["id"])
                print(item["id"], type(exc).__name__, str(exc))
    if failures:
        raise SystemExit(f"Unresolved downloads: {', '.join(failures)}")


if __name__ == "__main__":
    main()
