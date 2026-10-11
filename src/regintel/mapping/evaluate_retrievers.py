
"""
Benchmark keyword cosine, BM25, vector and hybrid retrieval.

Run:
    uv run python -m regintel.mapping.evaluate_retrievers

Evaluation labels are provisional and topic-based.
They are not compliance determinations.
"""

import json
import re

from pathlib import Path

from sqlalchemy import select

from regintel.db.session import SessionLocal
from regintel.models.obligation import RegulatoryObligation

from regintel.mapping.keyword_matcher import (
    rank_policy_sections,
)
from regintel.mapping.bm25_retriever import (
    BM25PolicyRetriever,
)
from regintel.mapping.vector_retriever import (
    VectorPolicyRetriever,
)
from regintel.mapping.hybrid_retriever import (
    HybridPolicyRetriever,
)
from regintel.mapping.run_policy_mapping import (
    load_policy_sections,
)
from regintel.mapping.evaluation_metrics import (
    recall_at_k,
    mean_reciprocal_rank,
)


LABEL_PATH = Path(
    "data/evaluation/section46_retrieval_labels.json"
)

OUTPUT_PATH = Path(
    "data/evaluation/section46_retrieval_results.json"
)

# Capture the first inherited list marker following "REs shall,"
SUFFIX_PATTERN = re.compile(
    r"REs\s+shall\s*,\s*\(([a-f])\)",
    re.IGNORECASE,
)


def extract_suffix(text: str) -> str | None:
    match = SUFFIX_PATTERN.search(text)

    if match is None:
        return None

    return f"({match.group(1).lower()})"


def rank_ids(matches) -> list[str]:
    return [
        match.policy_section_id
        for match in matches
    ]


def main():
    labels_data = json.loads(
        LABEL_PATH.read_text(encoding="utf-8")
    )

    labels = {
        item["obligation_suffix"]: set(
            item["relevant_policy_sections"]
        )
        for item in labels_data["labels"]
    }

    with SessionLocal() as session:
        sections = load_policy_sections(session)

        obligations = session.scalars(
            select(RegulatoryObligation)
            .where(
                RegulatoryObligation.clause_number == "46",
                RegulatoryObligation.extraction_method
                == "rule_based_v4_1_inherited",
            )
        ).all()

    if not sections:
        raise ValueError("No policy sections found.")

    # Translate section numbers into actual database UUIDs.
    section_id_by_number = {
        section["section_number"]: section["id"]
        for section in sections
    }

    if len(section_id_by_number) != len(sections):
        raise ValueError(
            "Duplicate section numbers across policies. "
            "Scope the benchmark to one policy version."
        )

    bm25 = BM25PolicyRetriever(sections)
    vector = VectorPolicyRetriever()
    hybrid = HybridPolicyRetriever(sections)

    methods = {
        "keyword": [],
        "bm25": [],
        "vector": [],
        "hybrid": [],
    }

    relevant_sets = []
    details = []
    observed_suffixes = set()

    for obligation in obligations:
        query = obligation.evidence_quote
        suffix = extract_suffix(query)

        if suffix not in labels:
            raise ValueError(
                f"Cannot map obligation {obligation.id} "
                f"to an evaluation label. Extracted suffix: {suffix}"
            )

        if suffix in observed_suffixes:
            raise ValueError(
                f"Duplicate obligation for suffix {suffix}"
            )

        observed_suffixes.add(suffix)

        relevant_numbers = labels[suffix]

        missing_sections = (
            relevant_numbers - set(section_id_by_number)
        )

        if missing_sections:
            raise ValueError(
                f"Missing labeled sections: {missing_sections}"
            )

        relevant_ids = {
            section_id_by_number[number]
            for number in relevant_numbers
        }

        # Retrieve all six policy sections where possible.
        top_k = len(sections)

        keyword_results = rank_policy_sections(
            query,
            sections,
            top_k=top_k,
        )

        bm25_results = bm25.search(
            query,
            top_k=top_k,
        )

        vector_results = vector.search(
            query,
            top_k=top_k,
        )

        hybrid_results = hybrid.search(
            query,
            top_k=top_k,
            candidate_k=top_k,
        )

        retrieved = {
            "keyword": rank_ids(keyword_results),
            "bm25": rank_ids(bm25_results),
            "vector": rank_ids(vector_results),
            "hybrid": rank_ids(hybrid_results),
        }

        if relevant_ids:
            relevant_sets.append(relevant_ids)

            for method, ids in retrieved.items():
                methods[method].append(ids)

        details.append(
            {
                "obligation_id": str(obligation.id),
                "suffix": suffix,
                "relevant_section_numbers": sorted(
                    relevant_numbers
                ),
                "retrieved": {
                    method: [
                        next(
                            (
                                section["section_number"]
                                for section in sections
                                if section["id"] == result_id
                            ),
                            "unknown",
                        )
                        for result_id in ids
                    ]
                    for method, ids in retrieved.items()
                },
            }
        )

    missing_labels = set(labels) - observed_suffixes

    if missing_labels:
        raise ValueError(
            f"Missing obligation candidates: {missing_labels}"
        )

    metrics = {}

    for method, ranked_lists in methods.items():
        metrics[method] = {
            "recall_at_1": sum(
                recall_at_k(ids, relevant, 1)
                for ids, relevant in zip(
                    ranked_lists,
                    relevant_sets,
                )
            ) / len(relevant_sets),
            "recall_at_3": sum(
                recall_at_k(ids, relevant, 3)
                for ids, relevant in zip(
                    ranked_lists,
                    relevant_sets,
                )
            ) / len(relevant_sets),
            "mrr": mean_reciprocal_rank(
                ranked_lists,
                relevant_sets,
            ),
        }

    report = {
        "dataset": labels_data["dataset_name"],
        "evaluated_queries": len(details),
        "queries_with_relevance_labels": len(relevant_sets),
        "excluded_from_ranking_metrics": (
            len(details) - len(relevant_sets)
        ),
        "metrics": metrics,
        "details": details,
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("\nRETRIEVAL EVALUATION")
    print("=" * 65)

    print(
        f"{'Method':<12}"
        f"{'Recall@1':>12}"
        f"{'Recall@3':>12}"
        f"{'MRR':>12}"
    )

    for method, scores in metrics.items():
        print(
            f"{method:<12}"
            f"{scores['recall_at_1']:>12.3f}"
            f"{scores['recall_at_3']:>12.3f}"
            f"{scores['mrr']:>12.3f}"
        )

    print("\nResults saved to:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
