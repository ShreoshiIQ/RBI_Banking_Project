
"""
Generate and persist embeddings for internal policy sections.

Run:
    uv run python -m regintel.mapping.index_policy_embeddings

Existing embeddings for the same model are skipped.
"""

from sqlalchemy import select

from regintel.db.session import SessionLocal

from regintel.models.policy import PolicySection
from regintel.models.policy_embedding import PolicySectionEmbedding

from regintel.mapping.embedding_service import (
    MODEL_NAME,
    embed_text,
)


def main():
    inserted = 0
    skipped = 0

    with SessionLocal.begin() as session:

        sections = session.scalars(
            select(PolicySection)
            .order_by(PolicySection.id)
        ).all()

        print("Policy sections found:", len(sections))

        for section in sections:

            existing = session.scalar(
                select(PolicySectionEmbedding).where(
                    PolicySectionEmbedding.policy_section_id
                    == section.id,
                    PolicySectionEmbedding.embedding_model
                    == MODEL_NAME,
                )
            )

            if existing is not None:
                skipped += 1
                continue

            text = (
                (section.section_title or "")
                + "\n"
                + section.section_text
            )

            vector = embed_text(text)

            record = PolicySectionEmbedding(
                policy_section_id=section.id,
                embedding_model=MODEL_NAME,
                embedding=vector,
            )

            session.add(record)
            inserted += 1

            print(
                f"Embedded policy section "
                f"{section.section_number}"
            )

    print("\nEMBEDDING INDEXING COMPLETED")
    print("Inserted:", inserted)
    print("Skipped:", skipped)


if __name__ == "__main__":
    main()
