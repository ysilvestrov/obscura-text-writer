import hashlib
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from .evidence import check_evidence
from .gateway import CompletionGateway, GatewayFailure
from .inputs import parse_json
from .models import EvaluationCase, EvaluationOutcome, EvaluatorConfig, JudgeReport, Rubric, ScoringProfile, FailureDetail
from .failures import refusal_detail, is_text_refusal
from .prompting import build_request
from .reports import write_reports
from .scoring import score_report


def digest(value) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluator_fingerprint(config: EvaluatorConfig, rubric: Rubric) -> str:
    from .prompting import resource_text
    from .suites import canonical_suite_hash
    return digest({"config": config.model_dump(), "rubric": rubric.model_dump(), "prompt": resource_text("evaluator_uk_v1.txt"),
        'protocol_version': 2, 'suite_hash': canonical_suite_hash()})


def fingerprint_inputs(case: EvaluationCase, rubric: Rubric, profile: ScoringProfile, config: EvaluatorConfig, reverse_pair: bool = False) -> str:
    return digest({"case": case.model_dump(), "rubric": rubric.model_dump(), "profile": profile.model_dump(),
        "config": config.model_dump(), "request": build_request(case, rubric, config, reverse_pair).model_dump()})


def current_commit() -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def evaluate(case: EvaluationCase, rubric: Rubric, profile: ScoringProfile, config: EvaluatorConfig,
        gateway: CompletionGateway, output_dir: Path, reverse_pair: bool = False, *, on_refusal=None, on_raw=None) -> EvaluationOutcome:
    request = build_request(case, rubric, config, reverse_pair)
    raw = ""
    usage = {}
    duration = 0.0
    finish_reason = None
    if sum(len(m["content"]) for m in request.messages) > config.max_input_chars:
        outcome = EvaluationOutcome(status="incomplete", reasons=["input_limit_exceeded"])
    else:
        try:
            response = gateway.complete(request)
            raw, usage, duration = response.text, response.usage, response.duration_seconds
            finish_reason = response.finish_reason
            if response.refusal or response.finish_reason == 'content_filter':
                detail = refusal_detail(response.refusal or '', content_filter=response.finish_reason == 'content_filter')
                raise GatewayFailure(detail.message, result=response, detail=detail)
            if response.finish_reason != "stop" or not raw:
                raise GatewayFailure("incomplete_response: Оцінювач не повернув повну відповідь", result=response,
                    detail=FailureDetail(category='invalid_response', message='Незавершена відповідь оцінювача: ' + str(response.finish_reason)))
            payload = parse_json(raw)
            if isinstance(payload, dict) and isinstance(payload.get('refusal'), str) and payload['refusal'].strip():
                detail = refusal_detail(payload['refusal'])
                raise GatewayFailure(detail.message, result=response, detail=detail)
            report = JudgeReport.model_validate(payload)
            evidence = check_evidence(case, report, profile.min_quote_chars)
            outcome = score_report(case, rubric, report, evidence, profile)
            if profile.calibrated:
                if (not profile.calibration_fingerprint
                        or profile.evaluator_fingerprint != evaluator_fingerprint(config, rubric)
                        or config.model is None):
                    outcome.status = "incomplete"
                    outcome.reasons.append("calibration_not_bound_to_evaluator")
        except GatewayFailure as exc:
            if exc.result is not None:
                raw = exc.result.text or exc.result.refusal or ""
                usage, duration = exc.result.usage, exc.result.duration_seconds
                finish_reason = exc.result.finish_reason
            outcome = EvaluationOutcome(status='refused' if exc.detail.category.startswith('refusal_') else 'error',
                reasons=[exc.detail.message], failure=exc.detail)
        except (ValidationError, ValueError, TypeError):
            if is_text_refusal(raw):
                detail = refusal_detail(raw)
                outcome = EvaluationOutcome(status='refused', reasons=[detail.message], failure=detail)
            else:
                outcome = EvaluationOutcome(status="error", reasons=["invalid_judge_report"],
                    failure=FailureDetail(category='invalid_response', message='Відповідь не відповідає схемі звіту.'))
    if outcome.status == 'refused' and on_refusal is not None:
        on_refusal(outcome.failure)  # Persist protection even if subsequent report IO fails.
    if on_raw is not None:
        on_raw(raw)
    outcome.fingerprint = fingerprint_inputs(case, rubric, profile, config, reverse_pair)
    outcome.metadata.update({"schema_version": "2", "run_id": uuid.uuid4().hex, "case_id": case.id,
        "created_at": datetime.now(timezone.utc).isoformat(), "commit": current_commit(), "finish_reason": finish_reason,
        "evaluator_fingerprint": evaluator_fingerprint(config, rubric), "reverse_pair": reverse_pair,
        "snapshots": {"case": case.model_dump(), "rubric": rubric.model_dump(), "profile": profile.model_dump(), "config": config.model_dump()},
        "request": request.model_dump(), "raw_response": raw, "usage": usage,
        "duration_seconds": duration, "reported_cost": str(usage["cost"]) if usage.get("cost") is not None else None,
        "cost_source": config.provider if usage.get("cost") is not None else None})
    folder = write_reports(outcome, output_dir)
    outcome.metadata["report_path"] = str(folder / "report.md")
    return outcome
