import pytest


@pytest.mark.parametrize('text,code,quote', [
    ('Олена сказала: это дивно.', 'non_ukrainian_letters', 'э'),
    ('Cлужанки зайшли.', 'mixed_alphabet', 'Cлужанки'),
    ('Вона вона чекала.', 'repeated_word', 'Вона вона'),
    ('- Я прийшла.', 'dialogue_dash', '-'),
    ('Це не ваші провина.', 'known_regression', 'ваші провина'),
    ('Серце, що відбиваючи аритмічний пульс.', 'known_regression', 'що відбиваючи аритмічний пульс'),
    ('Вона торкалається скла.', 'known_regression', 'торкалається'),
])
def test_local_warnings_have_exact_evidence(text, code, quote):
    from storygen.generation.language import language_warnings
    warnings = language_warnings(text)
    warning = next(w for w in warnings if w['code'] == code)
    assert warning['quote'] == quote
    assert text[warning['start']:warning['end']] == quote


@pytest.mark.parametrize('text', [
    'Вона йшла, відбиваючи ритм кроками.',
    '— Це не ваша провина.',
    'Олена знімає дорослу клієнтку оголеною. Вони погодили деталі фотосесії.',
    'Він ударив нападника. На підлогу впала крапля крові.',
    '',
])
def test_clean_counterexamples_are_not_penalized(text):
    from storygen.generation.language import language_warnings
    assert language_warnings(text) == []


def test_regression_fixture_identity_invalidates_evaluator_admission(monkeypatch):
    from storygen.evaluation.runner import evaluator_fingerprint
    from storygen.evaluation.models import EvaluatorConfig
    from storygen.evaluation.prompting import load_rubric
    from storygen.generation import language
    config = EvaluatorConfig(provider='codex_cli', model='test', max_input_chars=30000)
    before = evaluator_fingerprint(config, load_rubric())
    monkeypatch.setattr(language, 'language_suite_hash', lambda: 'changed-regressions')
    assert evaluator_fingerprint(config, load_rubric()) != before


def test_confirmed_fixture_examples_and_clean_controls():
    from storygen.generation.language import language_suite, language_warnings
    suite = language_suite()
    for case in suite['cases']:
        assert any(w['code'] == 'known_regression' for w in language_warnings(case['bad']))
        assert language_warnings(case['clean']) == []
