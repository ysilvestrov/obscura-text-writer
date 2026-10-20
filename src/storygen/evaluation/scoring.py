from pathlib import Path

from .inputs import read_json
from .models import EvaluationCase, EvaluationOutcome, EvidenceCheck, JudgeReport, Rubric, ScoringProfile
from .prompting import required_criteria


def load_profile(path: Path) -> ScoringProfile:
    return ScoringProfile.model_validate(read_json(path))


def score_report(case: EvaluationCase, rubric: Rubric, report: JudgeReport, evidence: EvidenceCheck, profile: ScoringProfile) -> EvaluationOutcome:
    required = required_criteria(case, rubric)
    assessments = {a.criterion_id: a for a in report.assessments}
    reasons = list(evidence.reasons)
    blocked = []
    for key in sorted(required):
        entry = assessments.get(key)
        if entry is None or entry.status != "assessed":
            reasons.append(f"criterion_not_checked:{key}")
        elif key not in profile.minimum_scores:
            reasons.append(f"threshold_missing:{key}")
        elif entry.score < profile.minimum_scores[key]:
            blocked.append(f"below_threshold:{key}")
    known = {d.id for d in case.documents}
    checked = set(report.checked_document_ids)
    expected = set(case.coverage.expected_scene_ids) | known
    if not expected <= checked or not checked <= known:
        reasons.append("coverage_incomplete")
    if case.coverage.unchecked_links:
        reasons.append("unchecked_story_links")
    for finding in evidence.confirmed:
        if finding.severity in profile.blocking_severities:
            blocked.append(f"blocking_finding:{finding.criterion_id}:{finding.severity}")
    if not profile.calibrated:
        reasons.append("profile_uncalibrated")
    status = "incomplete" if reasons else "failed" if blocked else "passed"
    return EvaluationOutcome(status=status, reasons=reasons + blocked, report=report, evidence=evidence,
        metadata={"preliminary_verdict": "failed" if blocked else "passed"})
