"""MODEL-001: the structured answer of an audit stage and its threshold."""
import json

import pytest

from storygen.generation.audit_output import AUDIT_STAGES, LINK_STAGE, AuditResponse, outcome, parse_audit


@pytest.mark.req('MODEL-001')
@pytest.mark.parametrize('raw, expected', [
    ('{"confidence":95,"discrepancies":[],"summary":"ok"}', 'valid'),
    ('```json\n{"confidence":90,"discrepancies":[],"summary":"ok"}\n```', 'valid'),
    ('{"confidence":89,"discrepancies":[],"summary":"ok"}', 'discrepancy'),
    ('{"confidence":99,"discrepancies":[{"text":"Анна в іншому місті","quote":null}],"summary":"x"}', 'discrepancy'),
])
def test_threshold(raw, expected):  # MODEL-001-S03
    assert outcome(parse_audit(raw)) == expected


@pytest.mark.req('MODEL-001')
@pytest.mark.parametrize('raw', [
    'не json', '{"confidence":101,"discrepancies":[],"summary":""}', '{"confidence":-1,"discrepancies":[],"summary":""}',
    '{"confidence":90,"discrepancies":[],"summary":"","extra":1}', '[]', '{"confidence":90,"summary":""}',
    '{"confidence":"90","discrepancies":[],"summary":""}', '{"confidence":90.5,"discrepancies":[],"summary":""}',
    '{"confidence":90,"discrepancies":[{"text":"x","quote":"y","extra":1}],"summary":""}',
    json.dumps({'confidence': 90, 'discrepancies': [{'text': 'x', 'quote': None}] * 21, 'summary': ''}),
    json.dumps({'confidence': 90, 'discrepancies': [{'text': 'x' * 2001, 'quote': None}], 'summary': ''}),
    json.dumps({'confidence': 90, 'discrepancies': [{'text': 'x', 'quote': 'q' * 2001}], 'summary': ''}),
    json.dumps({'confidence': 90, 'discrepancies': [], 'summary': 's' * 2001}),
])
def test_invalid_answer_raises(raw):  # MODEL-001-S03
    with pytest.raises(ValueError):
        parse_audit(raw)


@pytest.mark.req('MODEL-001')
def test_limits_are_inclusive_and_error_is_ukrainian():  # MODEL-001-S03
    edge = {'confidence': 0, 'discrepancies': [{'text': 't' * 2000, 'quote': 'q' * 2000}] * 20, 'summary': 's' * 2000}
    assert isinstance(parse_audit(json.dumps(edge)), AuditResponse)
    with pytest.raises(ValueError, match='Ревізор'):
        parse_audit('не json')


@pytest.mark.req('MODEL-001')
def test_stage_constants():  # MODEL-001-S03
    assert AUDIT_STAGES == ('audit_brief', 'audit_prose', 'audit_memory')
    assert LINK_STAGE == {'brief': 'audit_brief', 'prose': 'audit_prose', 'memory': 'audit_memory'}
