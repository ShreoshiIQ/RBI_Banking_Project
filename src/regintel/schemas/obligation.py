
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ObligationType(str, Enum):
    MANDATORY = "mandatory"
    PROHIBITION = "prohibition"
    PERMISSION = "permission"
    CONDITIONAL = "conditional"


class ObligationExtraction(BaseModel):
    source_clause_id: UUID

    clause_number: str = Field(min_length=1)

    actor: str = Field(min_length=1)

    action: str = Field(min_length=1)

    obligation_type: ObligationType

    condition: str | None = None

    evidence_quote: str = Field(min_length=1)

    confidence: float = Field(ge=0.0, le=1.0)

    extraction_method: str = "rule_based_v1"

    @model_validator(mode="after")
    def validate_condition(self):
        if (
            self.obligation_type == ObligationType.CONDITIONAL
            and not self.condition
        ):
            raise ValueError(
                "Conditional obligations require a condition"
            )

        return self
