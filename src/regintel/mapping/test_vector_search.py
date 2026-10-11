
"""
Quick manual semantic retrieval test.

Run:
    uv run python -m regintel.mapping.test_vector_search
"""

from regintel.mapping.vector_retriever import (
    VectorPolicyRetriever,
)


QUERIES = [
    "Financial institutions must keep transaction records for five years.",
    "Customer identity documents must remain available after an account closes.",
    "Regulators may request customer information from the bank.",
    "Transaction details should allow reconstruction of financial activity.",
]


def main():
    retriever = VectorPolicyRetriever()

    for query in QUERIES:
        print("\n" + "=" * 70)
        print("QUERY:", query)

        matches = retriever.search(
            obligation_text=query,
            top_k=3,
        )

        if not matches:
            print("No indexed policy sections found.")
            continue

        for match in matches:
            print(
                f"Section {match.section_number}: "
                f"{match.section_title}"
            )
            print(
                f"Similarity: {match.similarity:.4f}"
            )


if __name__ == "__main__":
    main()
