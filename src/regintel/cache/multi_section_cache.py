
from sqlalchemy.exc import IntegrityError

from regintel.db.session import SessionLocal
from regintel.models.llm_cache import LLMVerificationCache
from regintel.cache.verification_cache import CacheStats


class MultiSectionCache:

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory
        self.stats = CacheStats()

    def get(self, key: str) -> dict | None:
        with self.session_factory() as session:
            record = session.get(
                LLMVerificationCache,
                key,
            )

            if record is None:
                self.stats.misses += 1
                return None

            result = record.result_json

            if (
                not isinstance(result, dict)
                or result.get("validation_errors")
                or result.get("requires_human_review") is not True
                or not isinstance(result.get("findings"), list)
                or not isinstance(result.get("citations"), list)
                or not result.get("findings")
            ):
                raise ValueError(
                    "Invalid multi-section cache entry"
                )

            self.stats.hits += 1
            return result

    def put(self, key: str, result: dict) -> bool:
        if (
            result.get("validation_errors")
            or result.get("requires_human_review") is not True
            or not result.get("findings")
        ):
            return False

        with self.session_factory() as session:
            session.add(
                LLMVerificationCache(
                    cache_key=key,
                    model_name=result["model_name"],
                    result_json=result,
                )
            )

            try:
                session.commit()
            except IntegrityError:
                session.rollback()

                if session.get(
                    LLMVerificationCache, key
                ) is not None:
                    return False

                raise

        self.stats.writes += 1
        return True
