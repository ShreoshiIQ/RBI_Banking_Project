"""Generate a standalone local HTML review screen for the frozen packet."""

import argparse
import json
from pathlib import Path

from regintel.foundation.registry import load
from regintel.mapping.relevance_review import build_packet, canonical_hash, template


def render(packet):
    data = json.dumps(
        {"packet": packet, "pending": template(packet)}, ensure_ascii=False
    )
    data = data.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    script = Path(__file__).with_name("review_screen.js").read_text(encoding="utf-8")
    return (
        """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Local relevance review</title>
<style>body{font:16px system-ui;max-width:1100px;margin:24px auto;padding:0 18px;color:#172439;background:#f8fafc}article{padding:16px;background:white;border:1px solid #cbd5e1;margin:14px 0}pre{white-space:pre-wrap;font:inherit;line-height:1.55}label{display:block;margin:10px 0}input:not([type=checkbox]),select,textarea{box-sizing:border-box;max-width:100%;padding:8px;font:inherit}textarea{width:100%;min-height:90px}button{padding:10px;margin:4px;font:inherit}#message{font-weight:600;color:#843500}#status{font-weight:600}a{color:#0759a8}</style>
<h1>Local relevance review</h1>
<p>Review the complete frozen 500-candidate subset for each of the six queries. These are infrastructure probes, not independent held-out compliance questions. Source obligations and legal applicability remain pending.</p>
<p>This form records your self-reported decisions. It does not authenticate reviewers. No database writes or automatic approvals occur. Save a draft before closing this tab.</p>
<label>Query <select id="query"></select></label>
<p id="status" aria-live="polite"></p>
<label>Reviewer name <input id="reviewer" autocomplete="name"></label>
<label>Answerability <select id="answerability"><option value="pending">Pending decision</option><option value="relevant_documents_present">Relevant documents are present</option><option value="no_relevant_document_in_subset">No relevant document in this subset</option></select></label>
<label>Source-backed rationale <textarea id="rationale"></textarea></label>
<label><input type="checkbox" id="full-corpus"> I reviewed the entire 500-candidate subset for this query, beyond any search results or machine shortlist.</label>
<button id="approve">Mark this query reviewed</button>
<button id="draft">Export draft</button><button id="export">Export completed labels</button>
<label>Restore a saved draft (reviews will return to pending) <input id="import" type="file" accept="application/json,.json"></label>
<p id="message" role="status"></p>
<h2>Candidate evidence</h2>
<p>This subset covers card conduct and cybersecurity sources. Some topic queries may have no relevant document. Select candidates only after inspecting their relevance; use the official PDF for context.</p>
<label>Search candidate text, ID or source title <input id="search" type="search"></label>
<button id="previous">Previous page</button><button id="next">Next page</button><span id="paging"></span>
<div id="candidates"></div>
<script type="application/json" id="review-data">"""
        + data
        + """</script><script>"""
        + script
        + """</script></html>"""
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--packet",
        type=Path,
        default=Path("data/processed/validation/phase4_relevance_review_packet.json"),
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve the existing review screen")
    packet = load(args.packet)["packet"]
    verified = build_packet(
        Path.cwd().resolve(),
        Path("data/processed/validation/phase4_candidate_snapshot.json"),
        Path("data/processed/validation/phase4_scalability_warm_results.json"),
    )
    if canonical_hash(packet) != canonical_hash(verified):
        raise ValueError("Packet differs from the source-verified frozen corpus")
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(render(packet))


if __name__ == "__main__":
    main()
