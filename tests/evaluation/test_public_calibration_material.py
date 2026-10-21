import json
from importlib.resources import files
from pathlib import Path
from storygen.evaluation.models import EvaluationCase


def test_packaged_and_fixture_suites_use_neutral_library_material():
    for name in ['calibration_suite_v1.json','calibration_suite_v2.json']:
        suite=json.loads(files('storygen.evaluation').joinpath('resources',name).read_text(encoding='utf-8'))
        clean=next(c for c in suite['cases'] if c['id']=='clean')
        assert 'бібліотек' in json.dumps(clean,ensure_ascii=False).lower()
    fixture=json.loads(Path('tests/fixtures/evaluation/clean/case.json').read_text(encoding='utf-8'))
    assert 'бібліотек' in json.dumps(fixture,ensure_ascii=False).lower()


def test_public_suite_retains_all_evidence_anchors_and_categories():
    suite=json.loads(files('storygen.evaluation').joinpath('resources','calibration_suite_v2.json').read_text(encoding='utf-8'))
    cases={c['id']:EvaluationCase.model_validate(c) for c in suite['cases']}
    assert len(cases)==16 and set(cases)==set(suite['expectations'])
    assert set().union(*map(set,suite['categories'].values()))==set(cases)
    for id,expectation in suite['expectations'].items():
        documents={d.id:d.text for d in cases[id].documents}
        for finding in expectation['findings']+expectation.get('allowed_findings',[]):
            for anchor in finding['anchors']:
                assert anchor['quote'] in documents[anchor['document_id']]
