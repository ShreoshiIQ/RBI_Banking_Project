"""Load obligation-bearing provisions from every locally preserved corpus into one shape.

Provisions are unreviewed source text with citations; they are not validated obligations.
"""

import json
import re
from pathlib import Path

OBLIGATION_CUE = re.compile(r"\b(?:shall|must|required|mandatory|prohibited|not permitted|should)\b", re.IGNORECASE)
MIN_CHARS = 60
KYC_TITLE = "Reserve Bank of India (Know Your Customer (KYC)) Directions, 2016"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("�", "-")).strip()


def _keep(text: str) -> bool:
    return len(text) >= MIN_CHARS and bool(OBLIGATION_CUE.search(text))


def _provision(*, regulator, title, content_hash, source_url, ref, text, location):
    return {
        "provision_id": f"{regulator}:{content_hash[:12]}:{ref}",
        "regulator": regulator, "document_title": title, "content_hash": content_hash,
        "source_url": source_url, "ref": ref, "text": text, "location": location,
        "review_status": "pending",
    }


def kyc_provisions(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out, seen = [], set()
    for item in data["obligations"]:
        if item.get("quality_status") == "rejected" or item["clause_number"] in seen:
            continue
        text = _clean(item["evidence_quote"])
        if not _keep(text):
            continue
        seen.add(item["clause_number"])
        out.append(_provision(regulator="RBI", title=KYC_TITLE, content_hash=item["content_hash"],
                              source_url=item["source_url"], ref=f"clause {item['clause_number']}", text=text,
                              location={"start_page": item.get("start_page"), "end_page": item.get("end_page")}))
    return out


def preview_provisions(path: Path, titles: dict[str, str]) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    catalog = data["catalog"]
    out = []
    for clause in data["clauses"]:
        text = _clean(clause["clause_text"])
        if clause.get("status") != "active" or not _keep(text):
            continue
        out.append(_provision(regulator="RBI", title=titles.get(catalog["content_hash"], "RBI direction"),
                              content_hash=catalog["content_hash"], source_url=catalog["source_url"],
                              ref=f"clause {clause['clause_number']}", text=text,
                              location={"start_page": clause.get("start_page"), "end_page": clause.get("end_page")}))
    return out


def sebi_provisions(root: Path, corpus: dict) -> list[dict]:
    from regintel.foundation.expansion_ingestion import sebi_review_packet
    titles = {s["content_hash"]: s["title"] for s in corpus["sources"]}
    out = []
    for block in sebi_review_packet(root, corpus)["source_blocks"]:
        text = _clean(block["evidence_quote"])
        if not _keep(text):
            continue
        page = block["location"]["page"]
        out.append(_provision(regulator="SEBI", title=titles[block["content_hash"]], content_hash=block["content_hash"],
                              source_url=block["source_url"], ref=f"p.{page} block {block['candidate_id'][:8]}", text=text,
                              location=block["location"]))
    return out


def load_all(root: Path) -> list[dict]:
    corpora = json.loads((root / "data/metadata/phase3_official_corpora_verified.json").read_text(encoding="utf-8"))["corpora"]
    titles = {s["content_hash"]: s["title"] for c in corpora for s in c["sources"]}
    provisions = kyc_provisions(next((root / "data/processed/obligations").glob("*_obligations.json")))
    for preview in sorted((root / "data/processed/expansion_previews").glob("*_preview.json")):
        provisions += preview_provisions(preview, titles)
    for corpus in corpora:
        if any(s["regulator"] == "SEBI" for s in corpus["sources"]):
            provisions += sebi_provisions(root, corpus)
    return provisions
