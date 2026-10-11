
"""
Compare BM25, vector and hybrid retrieval for RBI Section 46.

Run:
    uv run python -m regintel.mapping.compare_hybrid
"""

from sqlalchemy import select

from regintel.db.session import SessionLocal
from regintel.models.obligation import RegulatoryObligation

from regintel.mapping.run_policy_mapping import (
    load_policy_sections,
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


def main():

    with SessionLocal() as session:
        sections = load_policy_sections(session)

        obligations = session.scalars(
            select(RegulatoryObligation)
            .where(
                RegulatoryObligation.clause_number == "46",
                RegulatoryObligation.extraction_method
                == "rule_based_v4_1_inherited",
            )
            .order_by(RegulatoryObligation.id)
        ).all()

    if not sections:
        raise ValueError("No policy sections found.")

    bm25 = BM25PolicyRetriever(sections)
    vector = VectorPolicyRetriever()
    hybrid = HybridPolicyRetriever(sections)

    print("\nHYBRID RETRIEVAL COMPARISON")
    print("=" * 75)
    print("Policy sections:", len(sections))
    print("Section 46 inherited obligations:", len(obligations))

    for obligation in obligations:

        query = obligation.evidence_quote

        print("\n" + "=" * 75)
        print("RBI OBLIGATION:")
        print(query[:300])

        bm25_results = bm25.search(query, top_k=3)
        vector_results = vector.search(query, top_k=3)
        hybrid_results = hybrid.search(query, top_k=3)

        print("\nBM25 RESULTS:")
        for item in bm25_results:
            print(
                f"  Section {item.section_number} "
                f"| score={item.score:.4f}"
            )

        print("\nVECTOR RESULTS:")
        for item in vector_results:
            print(
                f"  Section {item.section_number} "
                f"| similarity={item.similarity:.4f}"
            )

        print("\nHYBRID RESULTS:")
        for item in hybrid_results:
            print(
                f"  Section {item.section_number} "
                f"| RRF={item.rrf_score:.6f} "
                f"| BM25 rank={item.bm25_rank} "
                f"| Vector rank={item.vector_rank}"
            )


if __name__ == "__main__":
    main()
