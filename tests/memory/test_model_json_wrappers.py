import json
import threading

import pytest

from storygen.memory.journal import MemoryJournal, decode_memory, parse_memory_result


WRAPPERS = [("```json\n", "\n```"), ("```\n", "\n```"), ("'''json\n", "\n'''"), ("'", "'"), ("`", "`")]


@pytest.mark.parametrize('opening,closing', WRAPPERS)
@pytest.mark.parametrize('mode', ['evidence_delta', 'snapshot'])
def test_model_wrappers_preserve_json_content_and_warn(opening, closing, mode):
    if mode == 'snapshot':
        data = {'facts': [{'text': "It's `quoted`", 'source_version_id': 'p', 'quote': "It's `quoted`"}], 'source_prose_ids': ['p']}
    else:
        data = {'schema_version': 2, 'operations': [{'action': 'add', 'category': 'facts', 'text': "It's `quoted`", 'evidence_id': 'f000001'}]}
    raw = ' \n' + opening + json.dumps(data) + closing + '\n '
    warnings = []
    journal = parse_memory_result(raw, MemoryJournal(), 'p', "It's `quoted`", mode, [], warnings=warnings)
    assert journal.events[0].text == "It's `quoted`"
    assert len(warnings) == 1 and 'JSON' in warnings[0]
    assert "It's" not in warnings[0]
    with pytest.raises(ValueError):
        decode_memory(raw)  # Stored/manual material stays strict.


@pytest.mark.parametrize('raw', [
    '```json\n{"schema_version":2,"operations":[],"operations":[]}\n```',
    '```json\n{"schema_version":2,"operations":[]}\n',
    'Explanation\n```json\n{"schema_version":2,"operations":[]}\n```',
    '```json\n{"schema_version":2,"operations":[]}\n```\nMore text',
    '```json\n{}\n```\n```json\n{}\n```',
    "'{invalid}'",
    '```json\n{"schema_version":2,"facts":[]}\n```',
])
def test_wrappers_never_repair_invalid_or_ambiguous_payload(raw):
    with pytest.raises(ValueError):
        parse_memory_result(raw, MemoryJournal(), 'p', 'Evidence.', 'evidence_delta', [])


def test_fenced_unknown_evidence_is_still_rejected():
    raw = '```json\n' + json.dumps({'schema_version': 2, 'operations': [{'action': 'add', 'category': 'facts', 'text': 'Claim', 'evidence_id': 'f999999'}]}) + '\n```'
    with pytest.raises(ValueError, match='Невідомий фрагмент'):
        parse_memory_result(raw, MemoryJournal(), 'p', 'Evidence.', 'evidence_delta', [])


def test_fenced_model_stage_keeps_original_partial(tmp_path):
    from storygen.domain import StoryCreate, SceneCreate
    from storygen.storage.repository import Repository
    from storygen.providers.models import RoleSettings, ProviderSettings
    from storygen.providers.streaming import GenerationEvent
    from storygen.generation.context import build_context
    from storygen.generation.stages import execute_stage

    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Synthetic'))
    scene = repo.create_scene(story.id, SceneCreate(title='Scene'))
    prose = repo.save_version(story.id, scene.id, 'manual', 'Evidence.', [])
    repo.set_head(scene.id, 'prose', prose.id, scene.revision)
    role = RoleSettings(provider=ProviderSettings(model='fake'), memory_mode='evidence_delta', context_tokens=32768)
    context = build_context(repo, scene.id, 'memory', role)
    raw = '```json\n' + json.dumps({'schema_version': 2, 'operations': [{'action': 'add', 'category': 'facts', 'text': 'Claim', 'evidence_id': 'f000001'}]}) + '\n```'

    class Gateway:
        def stream(self, *_):
            yield GenerationEvent(type='delta', text=raw)
            yield GenerationEvent(type='terminal', finish_reason='stop')

    attempt = execute_stage(repo, scene.id, 'memory', context, Gateway(), threading.Event(), lambda _: None)
    assert attempt.state == 'completed'
    assert repo.files.read_partial(attempt.partial_path) == raw
    assert len(attempt.context['memory_warnings']) == 1
    assert repo.get_scene(scene.id).heads['memory'] == attempt.result_version_id
