"""Cross-regulation intelligence: obligation families across documents and contradiction candidates.

Families group related provisions from different documents so one control can be
tested once against several sources. Every link and finding is pending review.
"""

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from regintel.crossreg.contradictions import detect, quantities

FAMILY_THRESHOLD = 0.72
CANDIDATE_THRESHOLD = 0.62
QUANT_THRESHOLD = 0.55
TOP_K = 3
STOPWORDS = {"the", "a", "an", "of", "and", "or", "to", "in", "for", "by", "on", "with", "any", "be", "shall", "must", "such", "as", "is", "are", "this", "that", "which", "from", "all", "its", "their", "other", "under", "at", "may", "should", "not", "it", "re", "res"}


def embed(texts: list[str]) -> np.ndarray:
    from regintel.mapping.embedding_service import get_embedding_model
    return get_embedding_model().encode(texts, batch_size=64, normalize_embeddings=True, convert_to_numpy=True)


def cross_document_links(provisions: list[dict], vectors: np.ndarray, *, threshold: float, top_k: int = TOP_K) -> list[tuple[int, int, float]]:
    """Mutual top-k neighbours from different documents above the threshold."""
    docs = np.array([p["content_hash"] for p in provisions])
    sims = vectors @ vectors.T
    sims[docs[:, None] == docs[None, :]] = -1  # never link within one document
    neighbours = [set(np.argsort(-row)[:top_k]) for row in sims]
    links = []
    for i in range(len(provisions)):
        for j in neighbours[i]:
            if i < j and i in neighbours[j] and sims[i, j] >= threshold:
                links.append((i, int(j), round(float(sims[i, j]), 4)))
    return links


def families(provisions: list[dict], links: list[tuple[int, int, float]]) -> list[dict]:
    parent = list(range(len(provisions)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j, _ in links:
        parent[find(i)] = find(j)
    groups = {}
    for i, _, _ in links:
        groups.setdefault(find(i), set())
    for i, j, _ in links:
        groups[find(i)].update((i, j))
    out = []
    for members in groups.values():
        rows = [provisions[i] for i in sorted(members)]
        words = Counter(w for r in rows for w in set(_words(r["text"])))
        out.append({
            "family_id": "fam-" + hashlib.sha256("|".join(sorted(r["provision_id"] for r in rows)).encode()).hexdigest()[:12],
            "label_terms": [w for w, n in words.most_common(6) if n > 1],
            "regulators": sorted({r["regulator"] for r in rows}),
            "documents": sorted({r["document_title"] for r in rows}),
            "cross_regulator": len({r["regulator"] for r in rows}) > 1,
            "members": [{k: r[k] for k in ("provision_id", "regulator", "document_title", "ref", "source_url", "location", "text")} for r in rows],
            "review_status": "pending",
        })
    return sorted(out, key=lambda f: (not f["cross_regulator"], -len(f["documents"]), -len(f["members"]), f["family_id"]))


def _words(text: str) -> list[str]:
    return [w for w in "".join(c.lower() if c.isalpha() else " " for c in text).split() if len(w) > 3 and w not in STOPWORDS]


def quantity_pairs(provisions, vectors, *, threshold: float = QUANT_THRESHOLD) -> list[tuple[int, int, float]]:
    """All cross-document pairs of duration-bearing provisions above the threshold (sparse set, so no top-k)."""
    idx = [i for i, p in enumerate(provisions) if quantities(p["text"])]
    pairs = []
    for x, i in enumerate(idx):
        for j in idx[x + 1:]:
            similarity = float(vectors[i] @ vectors[j])
            if provisions[i]["content_hash"] != provisions[j]["content_hash"] and similarity >= threshold:
                pairs.append((i, j, round(similarity, 4)))
    return pairs


def contradiction_candidates(provisions, vectors, *, judge: Callable[[dict, dict], dict] | None = None) -> list[dict]:
    out, seen = [], set()
    pairs = cross_document_links(provisions, vectors, threshold=CANDIDATE_THRESHOLD) + quantity_pairs(provisions, vectors)
    for i, j, similarity in pairs:
        a, b = provisions[i], provisions[j]
        for finding in detect(a, b):
            key = (min(i, j), max(i, j), finding["type"])
            if key in seen:
                continue
            seen.add(key)
            record = {
                **finding, "similarity": similarity, "status": "candidate", "review_status": "pending",
                "provisions": [{k: p[k] for k in ("provision_id", "regulator", "document_title", "ref", "source_url", "location", "text")} for p in (a, b)],
            }
            if judge is not None:
                record["judgement"] = confirm(judge, a, b)
                record["status"] = "judge_supported" if record["judgement"]["agreed"] else "candidate"
            out.append(record)
    severity = {"high": 0, "medium": 1}
    return sorted(out, key=lambda r: (severity[r["severity"]], -r["similarity"]))


def confirm(judge, a: dict, b: dict) -> dict:
    """Two order-swapped judgements must both find a contradiction; otherwise it stays a candidate."""
    first, second = judge(a, b), judge(b, a)
    return {"agreed": bool(first.get("contradiction")) and bool(second.get("contradiction")),
            "votes": [first, second]}


def analyse(provisions: list[dict], *, vectors: np.ndarray | None = None, judge=None) -> dict:
    vectors = embed([p["text"] for p in provisions]) if vectors is None else vectors
    links = cross_document_links(provisions, vectors, threshold=FAMILY_THRESHOLD)
    fams = families(provisions, links)
    candidates = contradiction_candidates(provisions, vectors, judge=judge)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "method": {"embedding": "sentence-transformers/all-MiniLM-L6-v2", "family_threshold": FAMILY_THRESHOLD,
                   "candidate_threshold": CANDIDATE_THRESHOLD, "duration_pair_threshold": QUANT_THRESHOLD, "mutual_top_k": TOP_K,
                   "detectors": ["quantitative_divergence", "polarity_conflict", "retention_erasure_tension"],
                   "judge": getattr(judge, "method", None)},
        "corpus": {"provisions": len(provisions), "documents": len({p["content_hash"] for p in provisions}),
                   "by_regulator": dict(Counter(p["regulator"] for p in provisions))},
        "summary": {"families": len(fams), "cross_regulator_families": sum(f["cross_regulator"] for f in fams),
                    "contradiction_candidates": dict(Counter(c["type"] for c in candidates))},
        "families": fams,
        "contradiction_candidates": candidates,
        "notice": "Similarity links and detector findings are unreviewed candidates. They are not legal interpretations, confirmed conflicts, or applicability decisions.",
    }


def main():
    from regintel.crossreg.corpus import load_all
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--llm-judge", action="store_true", help="Confirm high-severity candidates with two order-swapped Gemini judgements")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite {args.output}")
    judge = None
    if args.llm_judge:
        from dotenv import load_dotenv

        from regintel.crossreg.judge import GeminiContradictionJudge
        load_dotenv()
        judge = GeminiContradictionJudge()
    report = analyse(load_all(args.root.resolve()), judge=judge)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({**report["corpus"], **report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
