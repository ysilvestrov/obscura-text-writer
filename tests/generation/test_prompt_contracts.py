import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository


def prepared(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Контракт'))
    scene = repo.create_scene(story.id, SceneCreate(title='Тест', beats='Анна чекає.'))
    draft = repo.save_version(story.id, scene.id, 'draft', 'Анна чекає.', [])
    repo.set_head(scene.id, 'draft', draft.id, scene.revision)
    return repo, story, repo.get_scene(scene.id)


def test_legacy_prompt_blocks_context_before_request(tmp_path):
    repo, story, scene = prepared(tmp_path)
    prompt = repo.save_version(story.id, None, 'prompt', 'Поверни прозу.', [])
    settings = RoleSettings(provider=ProviderSettings(model='fake'), edit_mode='patches', prompt_version_id=prompt.id)
    with pytest.raises(ValueError, match='признач'):
        build_context(repo, scene.id, 'edit', settings)


def test_prose_prompt_cannot_be_used_for_patch_output(tmp_path):
    from storygen.generation.prompts import expected_contract
    repo, story, scene = prepared(tmp_path)
    settings = RoleSettings(provider=ProviderSettings(model='fake'))
    prompt = repo.save_version(story.id, None, 'prompt', 'Поверни прозу.', [],
                               prompt_contract=expected_contract('edit', settings))
    settings = settings.model_copy(update={'prompt_version_id': prompt.id, 'edit_mode': 'patches'})
    with pytest.raises(ValueError, match='edit/patches/1'):
        build_context(repo, scene.id, 'edit', settings)


def test_explicit_legacy_assignment_creates_new_immutable_prompt(tmp_path):
    from storygen.web.routes_settings import SettingsChange, configure_prompts
    repo, story, scene = prepared(tmp_path)
    prompt = repo.save_version(story.id, None, 'prompt', 'Власна редактура.', [])
    settings = RoleSettings(provider=ProviderSettings(model='fake'), edit_mode='patches', prompt_version_id=prompt.id)
    change = SettingsChange(expected_revision=repo.get_story(story.id).revision, role='editor',
                            settings=settings, confirm_prompt_contract=True)
    assigned = configure_prompts(repo, story.id, change, settings)
    assert assigned.prompt_version_id != prompt.id
    assert repo.get_version(prompt.id).prompt_contract is None
    assert repo.read_text(assigned.prompt_version_id) == 'Власна редактура.'
    context = build_context(repo, scene.id, 'edit', assigned)
    # The author's prompt is used verbatim; only the scene rating block follows it.
    custom, rating = context.system_text.split('\n\n', 1)
    assert custom == 'Власна редактура.'
    assert rating.startswith('ВІКОВИЙ РЕЙТИНГ СЦЕНИ')


def test_future_editor_prompt_blocks_run_preflight(tmp_path):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.generation.readiness import preview
    from storygen.run_models import RunRequest
    repo, story, scene = prepared(tmp_path)
    prompt = repo.save_version(story.id, None, 'prompt', 'Невідомий контракт.', [])
    for role in ['planner', 'writer', 'editor', 'memory']:
        # Seed legacy persisted settings directly: a migrated store must be checked at use too.
        settings = RoleSettings(provider=ProviderSettings(model='fake'), prompt_version_id=prompt.id if role == 'editor' else None)
        if role == 'editor':
            import json
            with repo.db.connection() as db:
                db.execute('INSERT OR REPLACE INTO role_settings VALUES(?,?,?)', (story.id, role, settings.model_dump_json()))
        else:
            save_role_settings(repo, story.id, role, settings, repo.get_story(story.id).revision)
    result = preview(repo, RunRequest(story_id=story.id, scene_id=scene.id))
    assert not result['ready'] and 'признач' in result['reason']


def test_builtin_patch_prompt_needs_no_assignment(tmp_path):
    repo, _, scene = prepared(tmp_path)
    context = build_context(repo, scene.id, 'edit', RoleSettings(provider=ProviderSettings(model='fake'), edit_mode='patches'))
    assert '"edits"' in context.system_text


def memory_prepared(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Пам’ять'))
    scene = repo.create_scene(story.id, SceneCreate(title='Тест', beats='Анна чекає.', character_ids=['A']))
    prose = repo.save_version(story.id, scene.id, 'manual', 'Анна чекає біля дверей.', [])
    repo.set_head(scene.id, 'prose', prose.id, scene.revision)
    return repo, story, repo.get_scene(scene.id)


def memory_role(**update):
    return RoleSettings(**{'provider': ProviderSettings(model='fake'), 'memory_mode': 'evidence_delta', 'context_tokens': 32768, **update})


def custom_memory_prompt(repo, story, schema_version):
    from storygen.domain import PromptContract
    return repo.save_version(story.id, None, 'prompt', 'Власний промпт пам’яті.', [],
        prompt_contract=PromptContract(stage='memory', mode='evidence_delta', schema_version=schema_version))


def test_builtin_memory_prompt_is_v4():
    from storygen.domain import PromptContract
    from storygen.generation.prompts import expected_contract, role_prompt
    from storygen.prompt_contracts import memory_wire_version
    role = memory_role()
    assert expected_contract('memory', role) == PromptContract(stage='memory', mode='evidence_delta', schema_version=4)
    assert memory_wire_version(None) == 4
    assert '"schema_version":4' in role_prompt('memory', role)


def test_custom_v4_memory_prompt_is_used_verbatim(tmp_path):
    from storygen.prompt_contracts import memory_wire_version, validate_role_prompt
    repo, story, scene = memory_prepared(tmp_path)
    prompt = custom_memory_prompt(repo, story, 4)
    ref = validate_role_prompt(repo, story.id, 'memory', memory_role(prompt_version_id=prompt.id))
    assert ref.id == prompt.id and memory_wire_version(ref) == 4
    context = build_context(repo, scene.id, 'memory', memory_role(prompt_version_id=prompt.id))
    assert context.fragments['memory_wire_version'] == '4'
    assert context.system_text == 'Власний промпт пам’яті.'


def test_custom_v1_or_other_mode_still_rejected(tmp_path):
    from storygen.domain import PromptContract
    from storygen.prompt_contracts import validate_role_prompt
    repo, story, _ = memory_prepared(tmp_path)
    wrong = [PromptContract(stage='memory', mode='evidence_delta', schema_version=1),
             PromptContract(stage='memory', mode='snapshot', schema_version=2)]
    for contract in wrong:
        prompt = repo.save_version(story.id, None, 'prompt', 'Інший.', [], prompt_contract=contract)
        with pytest.raises(ValueError, match='memory/evidence_delta/4'):
            validate_role_prompt(repo, story.id, 'memory', memory_role(prompt_version_id=prompt.id))
    edit_v2 = repo.save_version(story.id, None, 'prompt', 'Редактор.', [],
        prompt_contract=PromptContract(stage='edit', mode='patches', schema_version=2))
    with pytest.raises(ValueError, match='edit/patches/1'):
        validate_role_prompt(repo, story.id, 'edit', RoleSettings(provider=ProviderSettings(model='fake'), edit_mode='patches', prompt_version_id=edit_v2.id))
    snapshot = repo.save_version(story.id, None, 'prompt', 'Знімок.', [],
        prompt_contract=PromptContract(stage='memory', mode='snapshot', schema_version=2))
    with pytest.raises(ValueError, match='memory/evidence_delta/4'):
        validate_role_prompt(repo, story.id, 'memory', RoleSettings(provider=ProviderSettings(model='fake'), memory_mode='snapshot', prompt_version_id=snapshot.id))


def test_context_records_wire_version_and_catalog_metrics(tmp_path):
    repo, _, scene = memory_prepared(tmp_path)
    context = build_context(repo, scene.id, 'memory', memory_role())
    assert context.fragments['memory_wire_version'] == '4'
    assert context.memory_metrics['projection_version'] == 'memory-catalog-v4'
    assert 'MUTABLE ДЛЯ UPDATE/RETIRE' in context.user_text
    assert '"mutable":[]' in context.user_text


def _run_memory(repo, scene, context, raw):
    import threading
    from storygen.generation.stages import execute_stage
    from storygen.providers.streaming import GenerationEvent
    class Gateway:
        def stream(self, *_):
            yield GenerationEvent(type='delta', text=raw)
            yield GenerationEvent(type='terminal', finish_reason='stop')
    return execute_stage(repo, scene.id, 'memory', context, Gateway(), threading.Event(), lambda _: None)


def test_attempt_without_wire_version_parses_as_v2(tmp_path):
    import json
    repo, _, scene = memory_prepared(tmp_path)
    context = build_context(repo, scene.id, 'memory', memory_role())
    old = context.model_copy(update={'fragments': {k: v for k, v in context.fragments.items() if k != 'memory_wire_version'}})
    raw = json.dumps({'schema_version': 2, 'operations': [{'action': 'add', 'category': 'facts', 'claim_id': None,
        'text': 'Анна біля дверей', 'character_ids': [], 'evidence_id': 'f000001'}]})
    attempt = _run_memory(repo, scene, old, raw)
    assert attempt.state == 'completed', attempt.error
    attempt = _run_memory(repo, scene, build_context(repo, scene.id, 'memory', memory_role()), raw)
    assert attempt.state == 'failed' and 'wire_version' in json.dumps(attempt.context.get('memory_violations'))


def test_json_schema_mode_uses_wire_v3_schema():
    from storygen.providers.requests import generation_request
    role = memory_role(provider=ProviderSettings(model='fake', response_mode='json_schema'))
    v3 = generation_request('memory', role, 's', 'u', {'memory_wire_version': '3'})['response_format']['json_schema']['schema']
    assert {'facts', 'character_states', 'open_threads', 'timeline'} <= set(v3['properties'])
    for fragments in ({'memory_wire_version': '2'}, {}):
        v2 = generation_request('memory', role, 's', 'u', fragments)['response_format']['json_schema']['schema']
        assert 'operations' in v2['properties']


def test_json_schema_mode_uses_dynamic_v4_schema(tmp_path):
    import json
    repo, _, scene = memory_prepared(tmp_path)
    role = memory_role(provider=ProviderSettings(model='fake', response_mode='json_schema'))
    context = build_context(repo, scene.id, 'memory', role)
    bounds = json.loads(context.fragments['memory_schema_bounds'])
    assert bounds['fragment_ids'] == ['f000001'] and bounds['mutable'] == {'character_states': []} and bounds['character_ids'] == ['A']
    schema = context.api_request['response_format']['json_schema']['schema']
    ev = schema['properties']['facts']['properties']['add']['items']['properties']['evidence_ids']
    assert ev['items']['enum'] == ['f000001']


def test_request_without_bounds_uses_static_v3_schema():
    from storygen.memory.wire_v3 import MemoryWireV3
    from storygen.providers.requests import generation_request, strict_schema
    role = memory_role(provider=ProviderSettings(model='fake', response_mode='json_schema'))
    schema = generation_request('memory', role, 's', 'u', {'memory_wire_version': '3'})['response_format']['json_schema']['schema']
    assert schema == strict_schema(MemoryWireV3)


@pytest.mark.req('PLANNER-ACQUAINTANCE')
def test_custom_brief_prompt_gets_introduced_wire_contract(tmp_path):
    from storygen.generation.prompts import expected_contract
    from storygen.prompt_contracts import BRIEF_INTRODUCED_CONTRACT
    repo, story, scene = prepared(tmp_path)
    settings = RoleSettings(provider=ProviderSettings(model='fake', response_mode='json_schema'))
    builtin = build_context(repo, scene.id, 'brief', settings)
    assert BRIEF_INTRODUCED_CONTRACT not in builtin.system_text
    assert '"introduced"' in builtin.system_text  # the built-in v2 prompt already describes the field
    old_form = 'Поверни лише JSON: {"objective":"...","beats":["..."],"constraints":["..."],"proposed_changes":[]}.'
    prompt = repo.save_version(story.id, None, 'prompt', old_form, [], prompt_contract=expected_contract('brief', settings))
    custom = build_context(repo, scene.id, 'brief', settings.model_copy(update={'prompt_version_id': prompt.id}))
    assert custom.system_text.startswith(old_form + '\n\n' + BRIEF_INTRODUCED_CONTRACT)
    assert '"introduced"' in BRIEF_INTRODUCED_CONTRACT and '[]' in BRIEF_INTRODUCED_CONTRACT
    # The stored author version is not rewritten and keeps its contract.
    assert repo.read_text(prompt.id) == old_form
    assert repo.get_version(prompt.id).prompt_contract == expected_contract('brief', settings)
    assert custom.api_request['messages'][0]['content'] == custom.system_text
