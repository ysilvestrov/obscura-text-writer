import json
import threading

import pytest

from storygen.memory.journal import MemoryJournal, normalize_manual_memory, load_memory, parse_memory_result, unwrap_model_memory


WARNING = 'Пам’ять: прибрано зовнішню обгортку JSON; вміст і докази не змінено.'
WRAPPERS = [("```json\n", "\n```"), ("```\n", "\n```"), ("'''json\n", "\n'''"), ("'", "'"), ("`", "`"), ("```JSON\r\n", "\r\n```")]


@pytest.mark.parametrize('opening,closing', WRAPPERS)
@pytest.mark.parametrize('mode,data', [
    ('snapshot', {'facts': [{'text': "It's `quoted`", 'source_version_id': 'p', 'quote': "It's `quoted`"}], 'source_prose_ids': ['p']}),
    ('evidence_delta', {'schema_version': 2, 'operations': [{'action': 'add', 'category': 'facts', 'text': "It's `quoted`", 'evidence_id': 'f000001'}]}),
])
def test_model_wrappers_preserve_json_content_and_warn(opening, closing, mode, data):
    raw = ' \n' + opening + json.dumps(data) + closing + '\n '
    warnings = []
    journal = parse_memory_result(raw, MemoryJournal(), 'p', "It's `quoted`", mode, [], warnings=warnings)
    assert journal.events[0].text == "It's `quoted`"
    assert warnings == [WARNING]
    with pytest.raises(json.JSONDecodeError):
        normalize_manual_memory(raw, MemoryJournal(), 'p', "It's `quoted`", [])
    with pytest.raises(json.JSONDecodeError):
        load_memory(raw)


@pytest.mark.parametrize('raw,error', [
    ('```json\n{"schema_version":2,"operations":[],"operations":[]}\n```', 'Повтор JSON ключа'),
    ('```json\n{"schema_version":2,"operations":[]}\n', 'Expecting value'),
    ('Explanation\n```json\n{"schema_version":2,"operations":[]}\n```', 'Expecting value'),
    ('```json\n{"schema_version":2,"operations":[]}\n```\nMore text', 'Expecting value'),
    ('```json\n{}\n```\n```json\n{}\n```', 'Expecting value'),
    ("'{invalid}'", 'Expecting property name'),
    ('```json\n{"schema_version":2,"facts":[]}\n```', 'Порушено схему операції пам’яті'),
])
def test_wrappers_never_repair_invalid_or_ambiguous_payload(raw, error):
    warnings = []
    with pytest.raises(ValueError, match=error):
        parse_memory_result(raw, MemoryJournal(), 'p', 'Evidence.', 'evidence_delta', [], warnings=warnings)
    assert warnings == []


@pytest.mark.parametrize('raw', ['', "''", "'", "`{}'", '```json{}```', '```json\n[]\n```', "```json\n{}\n'''", '```json\n{}\n```\n```json\n{}\n```'])
def test_unsupported_boundaries_stay_unchanged(raw):
    assert unwrap_model_memory(raw) == raw
    with pytest.raises(json.JSONDecodeError):
        parse_memory_result(raw, MemoryJournal(), 'p', 'Evidence.', 'evidence_delta', [])


def test_fenced_unknown_evidence_is_still_rejected():
    raw = '```json\n' + json.dumps({'schema_version': 2, 'operations': [{'action': 'add', 'category': 'facts', 'text': 'Claim', 'evidence_id': 'f999999'}]}) + '\n```'
    warnings = []
    with pytest.raises(ValueError, match='Невідомий фрагмент'):
        parse_memory_result(raw, MemoryJournal(), 'p', 'Evidence.', 'evidence_delta', [], warnings=warnings)
    assert warnings == []


def test_fenced_model_stage_keeps_original_partial(tmp_path):
    from storygen.domain import StoryCreate, SceneCreate
    from storygen.storage.repository import Repository
    from storygen.providers.models import RoleSettings, ProviderSettings
    from storygen.providers.streaming import GenerationEvent
    from storygen.generation.context import build_context
    from storygen.generation.stages import execute_stage
    from tests.memory.wire_helpers import v4_answer

    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Synthetic'))
    scene = repo.create_scene(story.id, SceneCreate(title='Scene'))
    prose = repo.save_version(story.id, scene.id, 'manual', 'Evidence.', [])
    repo.set_head(scene.id, 'prose', prose.id, scene.revision)
    role = RoleSettings(provider=ProviderSettings(model='fake'), memory_mode='evidence_delta', context_tokens=32768)
    context = build_context(repo, scene.id, 'memory', role)
    raw = '```json\n' + v4_answer(context, facts_add=[{'text': 'Claim', 'evidence_ids': ['f000001']}]) + '\n```'

    class Gateway:
        def stream(self, *_):
            yield GenerationEvent(type='delta', text=raw)
            yield GenerationEvent(type='terminal', finish_reason='stop')

    attempt = execute_stage(repo, scene.id, 'memory', context, Gateway(), threading.Event(), lambda _: None)
    assert attempt.state == 'completed'
    assert repo.files.read_partial(attempt.partial_path) == raw
    assert attempt.context['memory_warnings'] == [WARNING]
    assert repo.get_scene(scene.id).heads['memory'] == attempt.result_version_id
