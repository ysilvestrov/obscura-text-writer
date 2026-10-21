import json

import pytest

from storygen.evaluation.models import EvaluationCase, EvaluationOutcome
from storygen.evaluation.prompting import resource_text, build_request, load_rubric
from storygen.evaluation.calibration import calibrate, load_suite


def test_v2_suite_has_adult_pairs_with_real_anchors_and_no_leaked_answers():
    data = json.loads(resource_text('calibration_suite_v2.json'))
    cases = [EvaluationCase.model_validate(c) for c in data['cases']]
    assert len(cases) == 16 and set(data['expectations']) == {c.id for c in cases}
    for category in ['nudity', 'intimacy', 'violence']:
        ids = data['categories'][category]
        assert len(ids) == 2
        assert sorted(bool(data['expectations'][id]['findings']) for id in ids) == [False, True]
    from storygen.evaluation.models import EvaluatorConfig
    for case in cases:
        docs = {d.id: d.text for d in case.documents}
        for finding in data['expectations'][case.id]['findings']:
            assert all(anchor['quote'] in docs[anchor['document_id']] for anchor in finding['anchors'])
        request = build_request(case, load_rubric(), EvaluatorConfig(provider='local', model='judge', max_input_chars=100000))
        assert 'expectations' not in json.loads(request.messages[1]['content'])
        assert set(request.response_schema['required']) == set(request.response_schema['properties'])


def test_calibration_fingerprint_changes_when_suite_changes(monkeypatch):
    from storygen.evaluation.models import EvaluatorConfig
    from storygen.evaluation.runner import evaluator_fingerprint
    config = EvaluatorConfig(provider='local', model='judge', max_input_chars=100000)
    before = evaluator_fingerprint(config, load_rubric())
    from storygen.evaluation import suites
    monkeypatch.setattr(suites, 'canonical_suite_hash', lambda: 'changed-suite')
    assert evaluator_fingerprint(config, load_rubric()) != before


def test_refusals_are_reported_and_never_eligible(sample_case, good_report):
    from storygen.evaluation.runner import evaluator_fingerprint, fingerprint_inputs
    from storygen.evaluation.models import EvaluatorConfig, ScoringProfile
    config = EvaluatorConfig(provider='local', model='judge', max_input_chars=100000)
    profile = ScoringProfile(version='candidate')
    outcome = EvaluationOutcome(status='refused', metadata={'case_id': sample_case.id, 'run_id': 'refused-1',
        'evaluator_fingerprint': evaluator_fingerprint(config, load_rubric()),
        'snapshots': {'case': sample_case.model_dump(), 'config': config.model_dump(), 'rubric': load_rubric().model_dump(), 'profile': profile.model_dump()}},
        fingerprint=fingerprint_inputs(sample_case, load_rubric(), profile, config))
    metrics = calibrate([sample_case], {sample_case.id: {'findings': []}}, [outcome], required_repeats=3)
    assert metrics['refusal_count'] == 1 and metrics['eligible'] is False
