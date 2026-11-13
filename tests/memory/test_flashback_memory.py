"""STORY-TIME-S03: the memory of a flashback adds facts only and passes no core states (neutral examples)."""
import json

import pytest
from fastapi.testclient import TestClient

from storygen.application.settings import AppSettings
from storygen.generation.context import build_context
from storygen.generation.context_labels import label
from storygen.memory.core_review import core_review
from storygen.memory.journal import MemoryJournal, _add_event, _change_event, _extend, load_memory, replay_memory
from storygen.memory.service import save_scene_memory
from storygen.memory.violations import MemoryViolations
from storygen.memory.wire_v4 import check_v4, memory_wire_v4_schema, schema_bounds_v4
from storygen.web.app import create_app
from tests.memory.merge_helpers import arc_book
from tests.memory.test_core_review import PROSE2, role, run_memory, two_scenes
from tests.memory.wire_helpers import core_unchanged, v4_response

PROSE = 'Анна йде містом.\nНа розі стоїть ліхтар.'


def facts(n, first=1):
    return [{'text': f'Факт {i}', 'evidence_ids': ['f000001']} for i in range(first, first + n)]


def flashback_bounds():
    return schema_bounds_v4(MemoryJournal(), PROSE, ['A'], ['A'], {'A': True}, flashback=True)


def flashback_scene(tmp_path):
    """two_scenes with scene 2 marked as a flashback (a flat story: simple mode)."""
    repo, story, s1, s2, journal, claims = two_scenes(tmp_path)
    s2 = repo.update_scene_metadata(s2.id, {'flashback': True}, s2.revision)
    return repo, story, s1, s2, journal, claims


def test_schema_allows_only_fact_adds():
    bounds = flashback_bounds()
    assert bounds['flashback'] is True and bounds['tracked'] == {} and bounds['day_change'] == {}
    assert bounds['threads'] == [] and bounds['mutable'] == {'character_states': []}
    schema = memory_wire_v4_schema(bounds)['properties']
    assert schema['core']['properties'] == {} and schema['threads']['properties'] == {}
    assert schema['facts']['properties']['add']['maxItems'] == 6
    for category in ('character_states', 'open_threads', 'timeline'):
        assert all(group['maxItems'] == 0 for group in schema[category]['properties'].values())


def test_ordinary_bounds_have_no_flashback_key():
    assert 'flashback' not in schema_bounds_v4(MemoryJournal(), PROSE, ['A'], ['A'], {'A': True})


def test_check_rejects_other_actions_and_admits_six_facts():
    bounds = flashback_bounds()
    state = [{'text': 'Пальто', 'evidence_ids': ['f000001'], 'character_ids': ['A']}]
    assert [v.code for v in check_v4(json.loads(v4_response(character_states_add=state)), MemoryJournal(), bounds)] == ['flashback_only_facts']
    assert [v.code for v in check_v4(json.loads(v4_response(timeline_add=facts(1))), MemoryJournal(), bounds)] == ['flashback_only_facts']
    assert check_v4(json.loads(v4_response(facts_add=facts(6))), MemoryJournal(), bounds) == []
    decided = json.loads(v4_response(facts_add=facts(1)))
    decided['threads'] = {'c000009': {'status': 'unchanged', 'evidence_ids': ['f000001']}}
    assert 'flashback_only_facts' in [v.code for v in check_v4(decided, MemoryJournal(), bounds)]
    assert [(v.operation, v.code) for v in check_v4(json.loads(v4_response(facts_add=facts(7))), MemoryJournal(), bounds)] == [('facts.add', 'add_limit')]


def test_simple_mode_memory_stage_gets_no_catalog(tmp_path):
    repo, story, s1, s2, journal, claims = flashback_scene(tmp_path)
    context = build_context(repo, s2.id, 'memory', role())
    assert label('memory_core', 'uk') not in context.user_text and label('memory_claims', 'uk') not in context.user_text
    assert 'Стукав сусід.' in context.user_text
    assert json.loads(context.fragments['memory_schema_bounds'])['flashback'] is True
    assert json.loads(context.fragments['memory_tracked']) == []


def test_model_answer_changing_a_state_is_rejected(tmp_path):
    repo, story, s1, s2, journal, claims = flashback_scene(tmp_path)
    core = core_unchanged('A')
    with pytest.raises(AssertionError, match='flashback_only_facts'):
        run_memory(repo, s2, v4_response(core))
    attempt = run_memory(repo, s2, v4_response(facts_add=[{'text': 'Сусід стукав', 'evidence_ids': ['f000002']}]))
    head = load_memory(repo.read_text(repo.get_scene(s2.id).heads['memory']))
    added = head.events[len(journal.events):]
    assert [(e.category, e.text) for e in added] == [('facts', 'Сусід стукав')]


def test_full_mode_memory_stage_keeps_the_catalog(tmp_path):
    repo, story, scenes = arc_book(tmp_path, 'A B A', [['A', 'B']])
    repo.update_scene_metadata(scenes[2].id, {'flashback': True}, scenes[2].revision)
    context = build_context(repo, scenes[2].id, 'memory', role())
    assert label('memory_claims', 'uk') in context.user_text
    assert json.loads(context.fragments['memory_schema_bounds'])['flashback'] is True


def test_next_scene_gets_flashback_facts_and_the_same_states(tmp_path):
    def events(n, prose, previous):
        if n == 1:
            return [_add_event('character_states', 'Халат', prose, 'Анна йде містом', 0, ['c1'], slot='clothing')]
        return [_add_event('facts', f'Подія сцени {n}', prose, 'Анна йде містом', 0)]
    repo, story, scenes = arc_book(tmp_path, 'A A A', [['A']], events)
    repo.update_scene_metadata(scenes[1].id, {'flashback': True}, scenes[1].revision)
    context = build_context(repo, scenes[2].id, 'brief', role())
    assert 'Подія сцени 2' in context.user_text
    before = {k: v for k, v in replay_memory(load_memory(repo.read_text(scenes[0].heads['memory']))).items() if v.category == 'character_states'}
    after = {k: v for k, v in replay_memory(load_memory(repo.read_text(scenes[1].heads['memory']))).items() if v.category == 'character_states'}
    assert before == after


def test_manual_memory_changing_a_state_is_400(tmp_path):
    repo, story, s1, s2, journal, claims = flashback_scene(tmp_path)
    prose = s2.heads['prose']
    changed = _extend(journal, prose, [_change_event('update', claims['cloth'].claim_id, 'Пальто', 'character_states', ['A'], prose, 'Анна вдягла пальто.', slot='clothing')])
    added = _extend(journal, prose, [_add_event('facts', 'Сусід стукав', prose, 'Стукав сусід.', 0)])
    with TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765') as client:
        response = client.post(f'/api/scenes/{s2.id}/memory', json={'text': changed.model_dump_json(), 'expected_revision': s2.revision})
        assert response.status_code == 400 and 'Спогад додає лише факти' in response.text
        response = client.post(f'/api/scenes/{s2.id}/memory', json={'text': added.model_dump_json(), 'expected_revision': s2.revision})
        assert response.status_code == 200


def test_first_scene_flashback_has_only_its_facts(tmp_path):
    repo, story, s1, s2, journal, claims = two_scenes(tmp_path)
    s1 = repo.update_scene_metadata(s1.id, {'flashback': True}, s1.revision)
    context = build_context(repo, s1.id, 'memory', role())
    assert json.loads(context.fragments['previous_memory'])['events'] == []


def test_core_review_of_a_flashback_is_empty(tmp_path):
    repo, story, s1, s2, journal, claims = flashback_scene(tmp_path)
    prose = s2.heads['prose']
    save_scene_memory(repo, s2.id, _extend(journal, prose, [_add_event('facts', 'Сусід стукав', prose, 'Стукав сусід.', 0)]).model_dump_json(), s2.revision)
    review = core_review(repo, s2.id)
    assert review['flashback'] is True and review['slots'] == [] and review['threads'] == [] and review['day_change'] is False
