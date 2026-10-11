
"""
PostgreSQL-backed cache for LLM verification.

The cache key changes when the source text, model,
prompt version, or schema/validation version changes.
"""

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from regintel.db.session import SessionLocal
from regintel.models.llm_cache import LLMVerificationCache
from regintel.verification.llm_schemas import ValidatedVerification


# Increment these when you change the relevant logic.
PROMPT_VERSION = "gemini_verifier_v1"
SCHEMA_VERSION = "verification_schema_v1"
VALIDATOR_VERSION = "evidence_validator_v1"


def make_cache_key(
    *,
    obligation_id: str,
    obligation_text: str,
    policy_section_id: str,
    policy_text: str,
    model_name: str,
) -> str:
    """
    Build a deterministic SHA-256 cache key.

    JSON serialization prevents ambiguous concatenation
    of individual fields.
    """

    payload = {
        "obligation_id": obligation_id,
        "obligation_text": obligation_text,
        "policy_section_id": policy_section_id,
        "policy_text": policy_text,
        "model_name": model_name,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "validator_version": VALIDATOR_VERSION,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    api_calls: int = 0
    writes: int = 0


class VerificationCache:

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory
        self.stats = CacheStats()

    def get(
        self,
        cache_key: str,
    ) -> ValidatedVerification | None:

        with self.session_factory() as session:
            record = session.get(
                LLMVerificationCache,
                cache_key,
            )

            if record is None:
                self.stats.misses += 1
                return None

            try:
                result = ValidatedVerification.model_validate(
                    record.result_json
                )
            except Exception as exc:
                raise ValueError(
                    "Cached verification has an invalid schema. "
                    "Investigate or invalidate the cache entry."
                ) from exc

            # Never reuse an entry that failed validation.
            if result.validation_errors:
                raise ValueError(
                    "Cached verification contains validation errors."
                )

            if not result.requires_human_review:
                raise ValueError(
                    "Cached verification unexpectedly disables "
                    "human review."
                )

            self.stats.hits += 1
            return result

    def put(
        self,
        *,
        cache_key: str,
        result: ValidatedVerification,
    ) -> bool:
        """
        Store only a fully parsed result whose source
        quotations passed the current validator.

        Returns True if a new entry was inserted.
        """

        if result.validation_errors:
            return False

        if not result.requires_human_review:
            return False

        record = LLMVerificationCache(
            cache_key=cache_key,
            model_name=result.model_name,
            result_json=result.model_dump(mode="json"),
        )

        with self.session_factory() as session:
            session.add(record)

            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                # Another process may have inserted
                # this exact key concurrently.
                existing = session.scalar(
                    select(LLMVerificationCache).where(
                        LLMVerificationCache.cache_key
                        == cache_key
                    )
                )
                if existing is not None:
                    return False
                raise

        self.stats.writes += 1
        return True
