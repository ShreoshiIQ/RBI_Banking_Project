
"""
BM25 retrieval for regulatory obligation-to-policy matching.

Uses the same tokenization as our keyword baseline.
BM25 scores rank lexical relevance, not compliance.
"""

from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from regintel.mapping.keyword_matcher import tokenize


@dataclass
class BM25Match:
    policy_section_id: str
    section_number: str
    section_title: str
    score: float
    matched_terms: list[str]
    policy_text: str


class BM25PolicyRetriever:
    def __init__(self, policy_sections: list[dict]):
        self.sections = policy_sections

        self.tokenized_corpus = [
            tokenize(
                section["section_title"]
                + "\n"
                + section["section_text"]
            )
            for section in policy_sections
        ]

        self.model = (
            BM25Okapi(self.tokenized_corpus)
            if self.tokenized_corpus
            else None
        )

    def search(
        self,
        obligation_text: str,
        top_k: int = 3,
    ) -> list[BM25Match]:

        if top_k < 1:
            raise ValueError("top_k must be >= 1")

        if self.model is None:
            return []

        query_tokens = tokenize(obligation_text)

        if not query_tokens:
            return []

        scores = self.model.get_scores(query_tokens)

        results = []

        for section, section_tokens, score in zip(
            self.sections,
            self.tokenized_corpus,
            scores,
        ):
            matched_terms = sorted(
                set(query_tokens) & set(section_tokens)
            )

            # Some BM25 implementations can produce
            # zero or negative scores for small corpora.
            # Preserve meaningful overlapping candidates.
            if not matched_terms:
                continue

            results.append(
                BM25Match(
                    policy_section_id=str(section["id"]),
                    section_number=section["section_number"],
                    section_title=section["section_title"],
                    score=float(score),
                    matched_terms=matched_terms,
                    policy_text=section["section_text"],
                )
            )

        results.sort(
            key=lambda item: (
                -item.score,
                -len(item.matched_terms),
                item.section_number,
                item.policy_section_id,
            )
        )

        return results[:top_k]
