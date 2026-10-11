
"""
Compare keyword cosine and BM25 retrieval.

Run:
    uv run python -m regintel.mapping.compare_retrievers
"""

from sqlalchemy import select

from regintel.db.session import SessionLocal
from regintel.models.obligation import RegulatoryObligation
from regintel.mapping.keyword_matcher import rank_policy_sections
from regintel.mapping.bm25_retriever import BM25PolicyRetriever
from regintel.mapping.run_policy_mapping import load_policy_sections


def main():
    with SessionLocal() as session:
        sections = load_policy_sections(session)

        obligations = session.scalars(
            select(RegulatoryObligation)
            .order_by(
                RegulatoryObligation.clause_number,
                RegulatoryObligation.id,
            )
        ).all()

        if not sections:
            raise ValueError("No policy sections found.")

        retriever = BM25PolicyRetriever(sections)

        print("\nRETRIEVAL COMPARISON")
        print("=" * 75)
        print("Policy sections:", len(sections))
        print("Obligations:", len(obligations))

        inspected = 0

        for obligation in obligations:
            if obligation.clause_number != "46":
                continue

            if obligation.extraction_method != (
                "rule_based_v4_1_inherited"
            ):
                continue

            text = obligation.evidence_quote

            keyword_matches = rank_policy_sections(
                obligation_text=text,
                policy_sections=sections,
                top_k=3,
            )

            bm25_matches = retriever.search(
                obligation_text=text,
                top_k=3,
            )

            print("\n" + "-" * 75)
            print("OBLIGATION:")
            print(text[:350])

            print("\nKEYWORD COSINE:")
            for match in keyword_matches:
                print(
                    f"  Section {match.section_number}: "
                    f"{match.section_title} "
                    f"| score={match.score:.4f}"
                )

            print("\nBM25:")
            for match in bm25_matches:
                print(
                    f"  Section {match.section_number}: "
                    f"{match.section_title} "
                    f"| score={match.score:.4f}"
                )

            inspected += 1

        print("\nInherited Section 46 obligations inspected:", inspected)


if __name__ == "__main__":
    main()
