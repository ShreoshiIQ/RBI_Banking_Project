
"""
Local sentence-transformer embedding service.

The model is downloaded automatically on first use.
Subsequent executions reuse the cached model.
"""

from functools import lru_cache

from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def embed_text(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text.")

    model = get_embedding_model()

    vector = model.encode(
        text,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    result = vector.tolist()

    if len(result) != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Expected {EMBEDDING_DIMENSION} dimensions, "
            f"received {len(result)}."
        )

    return result
