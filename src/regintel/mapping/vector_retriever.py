
"""
Semantic policy retrieval using PostgreSQL pgvector.

Returns policy sections ranked by cosine distance.
"""

from dataclasses import dataclass

from sqlalchemy import select

from regintel.db.session import SessionLocal
from regintel.models.policy import PolicySection
from regintel.models.policy_embedding import PolicySectionEmbedding

from regintel.mapping.embedding_service import (
    MODEL_NAME,
    embed_text,
)


@dataclass
class VectorPolicyMatch:
    policy_section_id: str
    section_number: str
    section_title: str
    similarity: float
    policy_text: str


class VectorPolicyRetriever:

    def search(
        self,
        obligation_text: str,
        top_k: int = 3,
    ) -> list[VectorPolicyMatch]:

        if top_k < 1:
            raise ValueError("top_k must be >= 1")

        if not obligation_text.strip():
            return []

        query_vector = embed_text(obligation_text)

        distance = (
            PolicySectionEmbedding.embedding.cosine_distance(
                query_vector
            )
        )

        with SessionLocal() as session:

            rows = session.execute(
                select(
                    PolicySection,
                    distance.label("distance"),
                )
                .join(
                    PolicySectionEmbedding,
                    PolicySectionEmbedding.policy_section_id
                    == PolicySection.id,
                )
                .where(
                    PolicySectionEmbedding.embedding_model
                    == MODEL_NAME
                )
                .order_by(
                    distance.asc(),
                    PolicySection.id,
                )
                .limit(top_k)
            ).all()

        return [
            VectorPolicyMatch(
                policy_section_id=str(section.id),
                section_number=section.section_number,
                section_title=section.section_title or "",
                similarity=round(
                    1.0 - float(cosine_distance),
                    4,
                ),
                policy_text=section.section_text,
            )
            for section, cosine_distance in rows
        ]
