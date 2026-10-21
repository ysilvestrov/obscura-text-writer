from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

CriterionId = Literal["ukrainian", "style", "voice", "plan_fidelity", "continuity", "editorial_preservation"]
CRITERIA = ("ukrainian", "style", "voice", "plan_fidelity", "continuity", "editorial_preservation")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Document(StrictModel):
    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    kind: Literal["plan", "canon", "brief", "scene", "draft", "revision"]
    text: str = Field(min_length=1)


class Coverage(StrictModel):
    expected_scene_ids: list[str] = Field(default_factory=list)
    unchecked_links: list[str] = Field(default_factory=list)


class EvaluationCase(StrictModel):
    id: str = Field(min_length=1)
    mode: Literal["scene", "revision", "story"]
    documents: list[Document] = Field(min_length=1)
    target_ids: list[str] = Field(min_length=1)
    required_criteria: list[CriterionId] = Field(default_factory=list)
    coverage: Coverage = Field(default_factory=Coverage)

    @model_validator(mode="after")
    def references(self):
        ids = [doc.id for doc in self.documents]
        if len(ids) != len(set(ids)) or len(self.target_ids) != len(set(self.target_ids)):
            raise ValueError("Ідентифікатори мають бути унікальними")
        if not set(self.target_ids) <= set(ids):
            raise ValueError("Невідома цільова сцена")
        if self.mode == "revision" and len(self.target_ids) != 2:
            raise ValueError("Для редактури потрібні два тексти: оригінал і редактура")
        if len(self.required_criteria) != len(set(self.required_criteria)):
            raise ValueError("Повтор критерію")
        return self


class RubricCriterion(StrictModel):
    id: CriterionId
    description: str
    levels: dict[str, str]
    required_modes: list[Literal["scene", "revision", "story"]]

    @model_validator(mode="after")
    def levels_complete(self):
        if set(self.levels) != {"0", "1", "2", "3", "4"}:
            raise ValueError("Потрібні описи всіх п’яти балів")
        return self


class Rubric(StrictModel):
    version: str
    criteria: list[RubricCriterion]

    @model_validator(mode="after")
    def unique_criteria(self):
        ids = [c.id for c in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("Повтор критерію рубрики")
        return self


class Citation(StrictModel):
    document_id: str
    document_version: str
    quote: str = Field(min_length=1)


class Finding(StrictModel):
    criterion_id: CriterionId
    severity: Literal["minor", "major", "critical"]
    explanation: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)
    citations: list[Citation] = Field(min_length=1)


class CriterionAssessment(StrictModel):
    criterion_id: CriterionId
    status: Literal["assessed", "not_checked", "not_applicable"]
    score: int | None = Field(ge=0, le=4)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def status_matches_score(self):
        if (self.status == "assessed") != (self.score is not None):
            raise ValueError("Бал дозволено лише для перевіреного критерію")
        return self


class JudgeReport(StrictModel):
    assessments: list[CriterionAssessment]
    findings: list[Finding]
    checked_document_ids: list[str]
    limitations: list[str]
    refusal: str | None = None

    @model_validator(mode="after")
    def unique_criteria(self):
        if self.refusal is not None:
            if not self.refusal.strip() or self.assessments or self.findings or self.checked_document_ids:
                raise ValueError('Відмова не може містити оцінки або підтверджене покриття')
        ids = [a.criterion_id for a in self.assessments]
        if len(ids) != len(set(ids)):
            raise ValueError("Повтор оцінки критерію")
        return self


class EvidenceCheck(StrictModel):
    confirmed: list[Finding] = Field(default_factory=list)
    unconfirmed: list[Finding] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class ScoringProfile(StrictModel):
    version: str
    calibrated: bool = False
    minimum_scores: dict[CriterionId, int] = Field(default_factory=lambda: {key: 3 for key in CRITERIA})
    blocking_severities: list[Literal["minor", "major", "critical"]] = Field(default_factory=lambda: ["major", "critical"])
    min_quote_chars: int = Field(default=12, ge=1)
    evaluator_fingerprint: str | None = None
    calibration_fingerprint: str | None = None

    @model_validator(mode="after")
    def valid_thresholds(self):
        if any(type(v) is not int or not 0 <= v <= 4 for v in self.minimum_scores.values()):
            raise ValueError("Пороги повинні бути цілими числами від 0 до 4")
        return self


class EvaluatorConfig(StrictModel):
    provider: Literal["local", "openrouter", "codex_cli", "venice"]
    base_url: str | None = None
    model: str | None = None
    api_key_env: str | None = None
    timeout_seconds: float | int | None = Field(default=None, gt=0)
    max_output_tokens: int = Field(default=6000, ge=1)
    temperature: float | int | None = Field(default=None, ge=0, le=2)
    response_mode: Literal["json_schema", "prompt_json"] = "json_schema"
    max_input_chars: int = Field(gt=0)
    codex_command: str = "codex"
    venice_include_system_prompt: bool = False
    venice_disable_thinking: bool = False

    @model_validator(mode="after")
    def check_provider(self):
        endpoints = {'local': 'http://localhost:1235/v1', 'openrouter': 'https://openrouter.ai/api/v1', 'venice': 'https://api.venice.ai/api/v1', 'codex_cli': 'http://localhost:1235/v1'}
        self.base_url = self.base_url or endpoints[self.provider]
        self.api_key_env = self.api_key_env or ('VENICE_API_KEY' if self.provider == 'venice' else 'OPENROUTER_API_KEY')
        if self.provider != "codex_cli" and (self.model is None or not self.model.strip()):
            raise ValueError("Потрібен точний ідентифікатор моделі")
        if self.model is not None and not self.model.strip():
            raise ValueError("Порожня назва моделі")
        url = urlparse(self.base_url)
        if url.username or url.password or url.query or url.fragment:
            raise ValueError("Адреса не повинна містити ключів або облікових даних")
        if self.provider == "openrouter" and self.base_url.rstrip("/") != "https://openrouter.ai/api/v1":
            raise ValueError("Для OpenRouter потрібна офіційна адреса API")
        if self.provider == 'venice' and self.base_url.rstrip('/') != endpoints['venice']:
            raise ValueError('Для Venice потрібна офіційна адреса API')
        if self.provider == "local" and (url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.scheme not in {"http", "https"}):
            raise ValueError("Локальний API має використовувати loopback-адресу")
        return self


class EvaluationRequest(StrictModel):
    messages: list[dict[str, str]]
    response_schema: dict
    response_mode: Literal["json_schema", "prompt_json"]
    max_output_tokens: int
    temperature: float | int | None


class GatewayResult(StrictModel):
    text: str
    finish_reason: str | None
    refusal: str | None = None
    usage: dict = Field(default_factory=dict)
    duration_seconds: float = 0.0


class FailureDetail(StrictModel):
    category: Literal['refusal_content', 'refusal_unknown', 'missing_key', 'authentication', 'permission',
        'quota', 'rate_limit', 'timeout', 'connection', 'capability', 'invalid_response', 'provider_error', 'blocked']
    message: str
    http_status: int | None = None
    provider_code: str | None = None
    provider_type: str | None = None
    provider_message: str | None = None
    request_id: str | None = None


class EvaluationOutcome(StrictModel):
    status: Literal["passed", "failed", "incomplete", "error", "refused"]
    failure: FailureDetail | None = None
    reasons: list[str] = Field(default_factory=list)
    report: JudgeReport | None = None
    evidence: EvidenceCheck = Field(default_factory=EvidenceCheck)
    fingerprint: str = ""
    metadata: dict = Field(default_factory=dict)
