
"""
Tests for persistent verification caching.

Uses SQLite in memory.
No PostgreSQL or Gemini API required.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from regintel.db.base import Base
from regintel.models.llm_cache import LLMVerificationCache

from regintel.cache.verification_cache import (
    VerificationCache,
    make_cache_key,
)

from regintel.verification.llm_schemas import (
    AssessmentStatus,
    ValidatedVerification,
)


def make_test_cache():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    # Create only the cache table, not the entire
    # application's PostgreSQL-specific schema.
    LLMVerificationCache.__table__.create(engine)

    session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    return VerificationCache(
        session_factory=session_factory
    )


def make_result():
    return ValidatedVerification(
        obligation_id="ob-1",
        policy_section_id="policy-2",
        status=AssessmentStatus.ATTRIBUTES_MATCHED,
        regulatory_quote="Retain records for five years.",
        policy_quote="Maintain records for five years.",
        explanation="Requirements appear aligned.",
        model_name="test-gemini",
        requires_human_review=True,
    )


def make_key(
    policy_text="Maintain records for five years.",
    model_name="test-gemini",
):
    return make_cache_key(
        obligation_id="ob-1",
        obligation_text="Retain records for five years.",
        policy_section_id="policy-2",
        policy_text=policy_text,
        model_name=model_name,
    )


def test_cache_miss():
    cache = make_test_cache()

    assert cache.get(make_key()) is None
    assert cache.stats.misses == 1


def test_cache_write_and_hit():
    cache = make_test_cache()
    key = make_key()

    assert cache.put(
        cache_key=key,
        result=make_result(),
    )

    loaded = cache.get(key)

    assert loaded is not None
    assert loaded.status == AssessmentStatus.ATTRIBUTES_MATCHED
    assert loaded.model_name == "test-gemini"

    assert cache.stats.hits == 1
    assert cache.stats.writes == 1


def test_policy_change_invalidates_key():
    old_key = make_key(
        policy_text="Maintain records for five years."
    )

    new_key = make_key(
        policy_text="Maintain records for three years."
    )

    assert old_key != new_key


def test_model_change_invalidates_key():
    first = make_key(model_name="model-a")
    second = make_key(model_name="model-b")

    assert first != second


def test_duplicate_insert_not_repeated():
    cache = make_test_cache()
    key = make_key()

    assert cache.put(
        cache_key=key,
        result=make_result(),
    )

    assert not cache.put(
        cache_key=key,
        result=make_result(),
    )

    assert cache.stats.writes == 1


def test_invalid_evidence_not_cached():
    cache = make_test_cache()

    result = make_result()
    result.validation_errors = [
        "Policy quote not found in source."
    ]

    stored = cache.put(
        cache_key=make_key(),
        result=result,
    )

    assert stored is False
    assert cache.get(make_key()) is None
