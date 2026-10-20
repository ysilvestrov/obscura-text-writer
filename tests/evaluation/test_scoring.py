import pytest

from storygen.evaluation.models import Finding, ScoringProfile
from storygen.evaluation.evidence import check_evidence
from storygen.evaluation.scoring import score_report
from storygen.evaluation.prompting import load_rubric


def finding(quote="Лєра відчинила двері студії.", version="1", criterion="ukrainian", extra=None):
    citations = [dict(document_id="s1", document_version=version, quote=quote)]
    if extra:
        citations.append(extra)
    return Finding(criterion_id=criterion, severity="critical", explanation="Проблема", suggestion="Перевірити", citations=citations)


@pytest.mark.parametrize("quote,version", [("Вигадана фраза, якої тут немає.", "1"), ("Лєра", "1"), ("Лєра відчинила двері студії.", "0")])
def test_fabricated_wrong_version_and_short_quote_rejected(sample_case, good_report, quote, version):
    good_report.findings = [finding(quote, version)]
    result = check_evidence(sample_case, good_report)
    assert not result.confirmed
    assert len(result.unconfirmed) == 1


def test_contradiction_requires_two_sources(sample_case, good_report):
    good_report.findings = [finding(criterion="continuity")]
    assert len(check_evidence(sample_case, good_report).unconfirmed) == 1
    good_report.findings[0].citations.append(dict_to_citation())
    assert len(check_evidence(sample_case, good_report).confirmed) == 1


def dict_to_citation():
    from storygen.evaluation.models import Citation
    return Citation(document_id="canon", document_version="1", quote="Лєра має двадцять сім років.")


def test_critical_finding_blocks_despite_high_language_scores(sample_case, good_report, calibrated_profile):
    good_report.findings = [finding()]
    outcome = score_report(sample_case, load_rubric(), good_report, check_evidence(sample_case, good_report), calibrated_profile)
    assert outcome.status == "failed"


@pytest.mark.parametrize("change", ["missing", "not_checked", "not_applicable", "uncovered", "unknown_checked"])
def test_unchecked_required_or_uncovered_scene_is_incomplete(sample_case, good_report, calibrated_profile, change):
    if change == "missing":
        good_report.assessments.pop()
    elif change in {"not_checked", "not_applicable"}:
        good_report.assessments[0].status = change
        good_report.assessments[0].score = None
    elif change == "uncovered":
        sample_case.coverage.expected_scene_ids = ["s1", "s2"]
    else:
        good_report.checked_document_ids.append("unknown")
    result = score_report(sample_case, load_rubric(), good_report, check_evidence(sample_case, good_report), calibrated_profile)
    assert result.status == "incomplete"


def test_candidate_profile_cannot_pass(sample_case, good_report):
    result = score_report(sample_case, load_rubric(), good_report, check_evidence(sample_case, good_report), ScoringProfile(version="candidate"))
    assert result.status == "incomplete"
    assert "profile_uncalibrated" in result.reasons


def test_calibrated_thresholds_are_applied(sample_case, good_report, calibrated_profile):
    evidence = check_evidence(sample_case, good_report)
    assert score_report(sample_case, load_rubric(), good_report, evidence, calibrated_profile).status == "passed"
    good_report.assessments[0].score = 2
    assert score_report(sample_case, load_rubric(), good_report, evidence, calibrated_profile).status == "failed"


def test_scope_note_does_not_invalidate_checked_scene(sample_case, good_report, calibrated_profile):
    good_report.limitations = ["Оцінено лише одну сцену; майбутні сцени не надано."]
    result = score_report(sample_case, load_rubric(), good_report, check_evidence(sample_case, good_report), calibrated_profile)
    assert result.status == "passed"


def test_overlapping_quotes_do_not_count_as_two_anchors(sample_case, good_report):
    good_report.findings = [finding(criterion="continuity", extra=dict(document_id="s1",document_version="1",quote="Лєра відчинила двері студії"))]
    assert not check_evidence(sample_case, good_report).confirmed


def test_separate_passages_in_same_document_are_two_anchors(sample_case, good_report):
    good_report.findings = [finding(criterion="continuity",extra=dict(document_id="s1",document_version="1",quote="Їй було двадцять сім років."))]
    assert len(check_evidence(sample_case, good_report).confirmed) == 1
