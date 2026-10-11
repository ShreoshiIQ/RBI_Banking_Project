
from typing import Any, NotRequired, TypedDict


class VerificationState(TypedDict):
    # Required input
    obligation_id: str
    obligation_text: str
    policy_section_id: str
    policy_text: str

    # Filled by graph nodes
    deterministic: NotRequired[dict[str, Any]]
    cache_key: NotRequired[str]
    cache_status: NotRequired[str]
    route: NotRequired[str]
    result: NotRequired[dict[str, Any] | None]
    final_status: NotRequired[str]
    requires_human_review: NotRequired[bool]
    errors: NotRequired[list[str]]
    trace: NotRequired[list[str]]
