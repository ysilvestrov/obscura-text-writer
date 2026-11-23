"""Answer of an audit stage of the auditor role (MODEL-001): a verdict on one link of a scene."""
from typing import Literal

from pydantic import Field, ValidationError

from ..domain import DomainModel
from ..model_json import unwrap_model_json

AUDIT_STAGES = ('audit_brief', 'audit_prose', 'audit_memory')
# Link of a scene -> the stage that checks it.
LINK_STAGE = {'brief': 'audit_brief', 'prose': 'audit_prose', 'memory': 'audit_memory'}
VALID_CONFIDENCE = 90


class Discrepancy(DomainModel):
    text: str = Field(max_length=2000)
    quote: str | None = Field(default=None, max_length=2000)


class AuditResponse(DomainModel):
    confidence: int = Field(ge=0, le=100, strict=True)
    discrepancies: list[Discrepancy] = Field(max_length=20)
    summary: str = Field(max_length=2000)


def parse_audit(raw: str) -> AuditResponse:
    """The answer of the model; anything else is a failed attempt, never a verdict."""
    try:
        return AuditResponse.model_validate_json(unwrap_model_json(raw.strip()))
    except (ValidationError, ValueError) as exc:
        raise ValueError('Відповідь Ревізора не відповідає схемі: потрібен JSON з confidence (0–100), discrepancies і summary') from exc


def outcome(response: AuditResponse) -> Literal['valid', 'discrepancy']:
    return 'valid' if response.confidence >= VALID_CONFIDENCE and not response.discrepancies else 'discrepancy'
