import json

import pytest

from storygen.impact.validation import decode_response
from storygen.generation.planner_output import parse_planner_output
from storygen.generation.editor_output import parse_editor_output
from storygen.generation.edit_classification import parse_classification
from storygen.publication_suggestions import parse_suggestions


WRAPPERS = [("'", "'"), ('`', '`'), ('```json\n', '\n```'), ("'''JSON\r\n", "\r\n'''" )]


@pytest.mark.parametrize('opening,closing', WRAPPERS)
def test_all_model_json_boundaries_accept_one_wrapper_without_changing_strings(opening, closing):
    value = "Пам'ять і `цитата`"
    wrap = lambda payload: opening + json.dumps(payload, ensure_ascii=False) + closing
    assert decode_response(wrap({'quote': value})) == {'quote': value}
    brief, _ = parse_planner_output(wrap({'objective': value, 'beats': [value]}), 'brief', [])
    assert brief.objective == value
    blueprint, _ = parse_planner_output(wrap({'canon': value, 'characters': [], 'scenes': [{'title': value}]}), 'prepare', [])
    assert blueprint.canon == value
    edits, _ = parse_editor_output(wrap({'edits': []}))
    assert edits.edits == []
    advice = parse_classification(wrap({'changes': [{'index': 0, 'category': 'grammar', 'assessment': 'uncertain', 'explanation': value}]}), 1)
    assert advice.changes[0].explanation == value
    assert parse_suggestions(wrap({'title': value}), ['title']) == {'title': value}


@pytest.mark.parametrize('raw', ["'{}", "`{}'", 'Explanation\n```json\n{}\n```', '```json\n{}\n```\n```json\n{}\n```', "''{}''", "'{\"a\":1,\"a\":2}'", "'{\"a\":NaN}'"])
def test_review_json_keeps_ambiguous_or_invalid_payloads_closed(raw):
    with pytest.raises(ValueError):
        decode_response(raw)


def test_manual_json_remains_strict():
    from storygen.evaluation.inputs import parse_json
    with pytest.raises(ValueError):
        parse_json("'{}'")
