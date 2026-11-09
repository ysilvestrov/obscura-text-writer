import json

import pytest

from storygen.domain import PromptContract, SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.memory.core import SLOTS
from storygen.memory.journal import MemoryJournal
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository
from tests.memory.wire_helpers import core_unchanged, v4_response

SLOT_NAMES = [s.name for s in SLOTS]


def role(**update):
    return RoleSettings(**{'provider': ProviderSettings(model='fake'), 'memory_mode': 'evidence_delta', 'context_tokens': 32768, **update})


def prepared(tmp_path, beats='Анна чекає.'):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Ядро'))
    scene = repo.create_scene(story.id, SceneCreate(title='Тест', beats=beats, character_ids=['A']))
    prose = repo.save_version(story.id, scene.id, 'manual', 'Анна чекає біля дверей.', [])
    repo.set_head(scene.id, 'prose', prose.id, scene.revision)
    return repo, story, repo.get_scene(scene.id)


def two_scenes(tmp_path, first, second):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Дні'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=f'С{i}', beats=beats, character_ids=['A'])) for i, beats in enumerate((first, second))]
    p1 = repo.save_version(story.id, scenes[0].id, 'manual', 'Анна вдома.', [])
    repo.set_head(scenes[0].id, 'prose', p1.id, repo.get_scene(scenes[0].id).revision)
    memory = repo.save_version(story.id, scenes[0].id, 'memory', MemoryJournal(schema_version=3, source_prose_ids=[p1.id]).model_dump_json(), [p1.id])
    repo.set_head(scenes[0].id, 'memory', memory.id, repo.get_scene(scenes[0].id).revision)
    p2 = repo.save_version(story.id, scenes[1].id, 'manual', 'Анна на роботі.', [])
    repo.set_head(scenes[1].id, 'prose', p2.id, repo.get_scene(scenes[1].id).revision)
    return repo, story, repo.get_scene(scenes[1].id)


def custom(repo, story, version):
    return repo.save_version(story.id, None, 'prompt', 'Власний промпт пам’яті.', [],
        prompt_contract=PromptContract(stage='memory', mode='evidence_delta', schema_version=version))


def test_expected_memory_contract_is_v4():
    from storygen.prompt_contracts import compatible_contract, expected_contract, memory_wire_version
    expected = expected_contract('memory', role())
    assert expected == PromptContract(stage='memory', mode='evidence_delta', schema_version=4)
    assert memory_wire_version(None) == 4
    assert not any(compatible_contract(expected, PromptContract(stage='memory', mode='evidence_delta', schema_version=v)) for v in (1, 2, 3))


@pytest.mark.req('PROMPT-CONTRACT')
def test_custom_v2_and_v3_memory_prompts_are_incompatible(tmp_path):
    from storygen.prompt_contracts import memory_wire_version, validate_role_prompt
    repo, story, scene = prepared(tmp_path)
    for version in (2, 3):
        prompt = custom(repo, story, version)
        with pytest.raises(ValueError, match='Несумісний промпт: потрібно memory/evidence_delta/4'):
            validate_role_prompt(repo, story.id, 'memory', role(prompt_version_id=prompt.id))
        with pytest.raises(ValueError, match='memory/evidence_delta/4'):
            build_context(repo, scene.id, 'memory', role(prompt_version_id=prompt.id))
    prompt = custom(repo, story, 4)
    ref = validate_role_prompt(repo, story.id, 'memory', role(prompt_version_id=prompt.id))
    assert memory_wire_version(ref) == 4


def test_upgrade_flag_assigns_v4(tmp_path):
    from storygen.web.routes_settings import SettingsChange, configure_prompts
    repo, story, _ = prepared(tmp_path)
    for version in (2, 3):
        old = custom(repo, story, version)
        settings = role(prompt_version_id=old.id)
        change = SettingsChange(expected_revision=repo.get_story(story.id).revision, role='memory', settings=settings,
            prompt_text='Оновлений промпт пам’яті.', upgrade_memory_wire=True)
        upgraded = configure_prompts(repo, story.id, change, settings)
        assert upgraded.prompt_version_id != old.id
        assert repo.get_version(upgraded.prompt_version_id).prompt_contract.schema_version == 4
        assert repo.get_version(old.id).prompt_contract.schema_version == version
        # Without the explicit flag the stored old contract stays and preflight keeps rejecting it.
        kept = configure_prompts(repo, story.id, change.model_copy(update={'upgrade_memory_wire': False}), settings)
        assert repo.get_version(kept.prompt_version_id).prompt_contract.schema_version == version


@pytest.mark.req('PROMPT-CONTRACT')
def test_snapshot_mode_reads_as_evidence_delta():
    stored = RoleSettings.model_validate({'memory_mode': 'snapshot', 'provider': {'model': 'fake'}})
    assert stored.memory_mode == 'evidence_delta'
    with pytest.raises(ValueError):
        RoleSettings.model_validate({'memory_mode': 'other', 'provider': {'model': 'fake'}})


def test_memory_context_has_v4_bounds_and_core_catalog(tmp_path):
    repo, _, scene = prepared(tmp_path)
    context = build_context(repo, scene.id, 'memory', role())
    assert context.fragments['memory_wire_version'] == '4'
    assert json.loads(context.fragments['memory_tracked']) == ['A']
    bounds = json.loads(context.fragments['memory_schema_bounds'])
    assert bounds['tracked'] == {'A': SLOT_NAMES} and bounds['day_change'] == {'A': False}
    assert bounds['threads'] == [] and bounds['fragment_ids'] == ['f000001']
    assert context.memory_metrics['projection_version'] == 'memory-catalog-v4'
    assert 'ЯДРО СТАНУ ВІДСТЕЖУВАНИХ ПЕРСОНАЖІВ — УСІ СЛОТИ ОБОВ’ЯЗКОВІ' in context.user_text
    assert 'АКТИВНІ ЛІНІЇ — ДЛЯ КОЖНОЇ ОБОВ’ЯЗКОВЕ open/closed' in context.user_text
    assert 'ЗМІНИВСЯ ДЕНЬ' not in context.user_text


def test_memory_catalog_v4_shape():
    from storygen.memory.journal import _add_event
    from storygen.memory.projection import memory_catalog_v4
    cloth = _add_event('character_states', 'Халат', 'p1', 'Анна в халаті.', 0, ['A'], slot='clothing')
    key = _add_event('character_states', 'Ключ', 'p1', None, 0, ['A'], slot='carried', source_kind='author')
    mood = _add_event('character_states', 'Сутінки', 'p1', 'Анна в халаті.', 0, ['A'])
    thread = _add_event('open_threads', 'Хто стукав?', 'p1', 'Анна в халаті.', 0)
    fact = _add_event('facts', 'Будинок старий', 'p1', 'Анна в халаті.', 0)
    journal = MemoryJournal(schema_version=3, source_prose_ids=['p1'], events=[cloth, key, mood, thread, fact])
    catalog = json.loads(memory_catalog_v4(journal, ['A'], {'A': 'Анна'}))
    assert set(catalog) == {'names', 'core', 'threads', 'mutable', 'immutable'} and catalog['names'] == {'A': 'Анна'}
    assert catalog['core']['A']['clothing'] == {'value': 'Халат', 'source': 'prose', 'reader_unknown': False}
    assert catalog['core']['A']['carried'] == {'value': 'Ключ', 'source': 'author', 'reader_unknown': True}
    assert catalog['core']['A']['location'] == {'value': None, 'source': None, 'reader_unknown': False}
    assert catalog['threads'] == [{'claim_id': thread.claim_id, 'text': 'Хто стукав?'}]
    assert [m['claim_id'] for m in catalog['mutable']] == [mood.claim_id]
    assert catalog['immutable'] == [{'category': 'facts', 'text': 'Будинок старий'}]


def test_day_change_notice_in_memory_context(tmp_path):
    repo, _, scene = two_scenes(tmp_path, 'Початок: день 1, 08:00', 'Початок: день 2, 09:00')
    context = build_context(repo, scene.id, 'memory', role())
    assert json.loads(context.fragments['memory_schema_bounds'])['day_change'] == {'A': True}
    assert 'ЗМІНИВСЯ ДЕНЬ: day:1 → day:2' in context.user_text
    repo, _, scene = two_scenes(tmp_path / 'plain', 'Анна вдома.', 'Початок: день 2, 09:00')
    context = build_context(repo, scene.id, 'memory', role())
    assert json.loads(context.fragments['memory_schema_bounds'])['day_change'] == {'A': False}
    assert 'ЗМІНИВСЯ ДЕНЬ' not in context.user_text


def test_request_uses_v4_schema(tmp_path):
    from storygen.memory.wire_v4 import memory_wire_v4_schema
    repo, _, scene = prepared(tmp_path)
    context = build_context(repo, scene.id, 'memory', role(provider=ProviderSettings(model='fake', response_mode='json_schema')))
    schema = context.api_request['response_format']['json_schema']['schema']
    assert schema == memory_wire_v4_schema(json.loads(context.fragments['memory_schema_bounds']))
    assert schema['properties']['schema_version']['enum'] == [4]


def _run(repo, scene, context, raw):
    import threading
    from storygen.generation.stages import execute_stage
    from storygen.providers.streaming import GenerationEvent
    class Gateway:
        def stream(self, *_):
            yield GenerationEvent(type='delta', text=raw)
            yield GenerationEvent(type='terminal', finish_reason='stop')
    return execute_stage(repo, scene.id, 'memory', context, Gateway(), threading.Event(), lambda _: None)


def test_stage_publishes_v4_journal(tmp_path):
    repo, _, scene = prepared(tmp_path)
    context = build_context(repo, scene.id, 'memory', role())
    core = core_unchanged('A')
    core['A']['location'] = {'status': 'changed', 'text': 'Біля дверей', 'evidence_ids': ['f000001'], 'reason': ''}
    attempt = _run(repo, scene, context, v4_response(core))
    assert attempt.state == 'completed', attempt.error
    journal = MemoryJournal.model_validate_json(repo.read_text(repo.get_scene(scene.id).heads['memory']))
    assert journal.schema_version == 3
    assert [(e.slot, e.text, e.character_ids) for e in journal.events] == [('location', 'Біля дверей', ['A'])]
    # A v4 answer without the mandatory core fails the attempt instead of publishing.
    attempt = _run(repo, scene, build_context(repo, repo.get_scene(scene.id).id, 'memory', role()), v4_response())
    assert attempt.state == 'failed' and 'core' in json.dumps(attempt.context.get('memory_violations'))


def test_default_memory_prompt_is_v4():
    from importlib.resources import files
    from storygen.generation.prompts import role_prompt
    text = role_prompt('memory', role())
    assert text == files('storygen.generation').joinpath('resources', 'memory_delta_uk_v4.txt').read_text(encoding='utf-8')
    assert '"schema_version":4' in text and '"core"' in text and '"threads"' in text
