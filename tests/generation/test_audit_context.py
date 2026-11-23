import json
import pytest
from storygen.authoring.blueprints import save_role_settings
from storygen.domain import PromptContract, StoryCreate, SceneCreate
from storygen.generation.audit_context import AuditUnavailable, build_audit_context
from storygen.generation.context import build_context
from storygen.generation.dependencies import save_manual_prose
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.links import link_state
from storygen.storage.link_records import LinkInvalidation, new_verdict_id, write_invalidation
from storygen.storage.repository import Repository
from tests.storage.test_links import book, save_manual_brief

KEYS = {'brief': ['plan', 'previous_memory', 'brief', 'reference'],
        'prose': ['brief', 'previous_memory', 'prose', 'reference'],
        'memory': ['prose', 'own_memory_records', 'reference']}
STAGES = {'brief': 'audit_brief', 'prose': 'audit_prose', 'memory': 'audit_memory'}


def auditor(repo, story, **changes):
    settings = RoleSettings(provider=ProviderSettings(model='auditor'), temperature=0.2, memory_mode='snapshot',
                            context_tokens=200000, max_input_chars=400000, max_output_tokens=4096)
    save_role_settings(repo, story.id, 'auditor', settings.model_copy(update=changes), repo.get_story(story.id).revision)


def add_canon(repo, story, text='Канон: у студії завжди тихо.'):
    ref = repo.save_version(story.id, None, 'canon', text, [])
    with repo.db.connection() as db:
        current = repo.get_story(story.id)
        db.execute('UPDATE stories SET payload=? WHERE id=?',
                   (current.model_copy(update={'canon_version_id': ref.id}).model_dump_json(), story.id))
    return ref


@pytest.mark.parametrize('link', ['brief', 'prose', 'memory'])
def test_second_scene_inputs_by_link(tmp_path, link):
    repo, story, scenes = book(tmp_path, 2)
    auditor(repo, story)
    add_canon(repo, story)
    context = build_audit_context(repo, scenes[1].id, link)
    assert not isinstance(context, AuditUnavailable)
    payload = json.loads(context.user_text)
    assert list(payload) == KEYS[link]
    assert context.stage == STAGES[link] and context.policy_role == 'auditor'
    view = repo.context_view(story.id)
    assert context.fragments['audit_link'] == link
    assert context.fragments['audit_fingerprint'] == link_state(view, scenes[1].id, link).fingerprint
    assert context.fragments['invalidation_marker'] == '0'
    assert 'Канон: у студії завжди тихо.' in payload['reference']
    heads = repo.get_scene(scenes[1].id).heads
    if 'brief' in payload:
        assert payload['brief'] == repo.read_text(heads['brief'])
    if 'prose' in payload:
        assert payload['prose'] == repo.read_text(heads['prose'])
    if 'previous_memory' in payload:
        assert isinstance(payload['previous_memory'], str) and payload['previous_memory']
    if link == 'brief':
        assert payload['plan'] == 'Студія'
    if link == 'memory':
        records = payload['own_memory_records']
        assert records and all('source_version_id' not in r and 'event_id' not in r and 'evidence_version_id' not in r
                               for r in records)
        assert all(r['text'] for r in records)
    assert context.system_text.startswith('Ти — ревізор оповідання')


def test_stale_brief_still_builds(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    auditor(repo, story)
    save_manual_brief(repo, scene)
    assert link_state(repo.context_view(story.id), scene.id, 'brief').status == 'unchecked'
    # The draft and prose heads are stale now: the copyedit context refuses them.
    with pytest.raises(ValueError, match='застарілий'):
        build_context(repo, scene.id, 'edit', RoleSettings(provider=ProviderSettings(model='editor')))
    context = build_audit_context(repo, scene.id, 'prose')
    assert not isinstance(context, AuditUnavailable)
    assert json.loads(context.user_text)['brief'] == repo.read_text(repo.get_scene(scene.id).heads['brief'])


@pytest.mark.parametrize('link', ['brief', 'prose'])
def test_stale_previous_memory_still_builds(tmp_path, link):
    # The previous memory goes stale after manual prose of scene 1: the writer refuses, the audit reads it as it is.
    repo, story, scenes = book(tmp_path, 2)
    auditor(repo, story)
    save_manual_prose(repo, scenes[0].id, 'Олена увійшла до старої бібліотеки.', repo.get_scene(scenes[0].id).revision)
    with pytest.raises(ValueError, match='Спершу оновіть пам’ять попередньої сцени'):
        build_context(repo, scenes[1].id, 'brief', RoleSettings(provider=ProviderSettings(model='planner')))
    context = build_audit_context(repo, scenes[1].id, link)
    assert not isinstance(context, AuditUnavailable)
    assert json.loads(context.user_text)['previous_memory']


def test_first_scene_without_series_has_no_previous_memory(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    auditor(repo, story)
    context = build_audit_context(repo, scene.id, 'brief')
    assert not isinstance(context, AuditUnavailable)
    assert json.loads(context.user_text)['previous_memory'] is None


def drop_memory(repo, scene):
    current = repo.get_scene(scene.id)
    with repo.db.connection() as db:
        payload = current.model_copy(update={'heads': {k: v for k, v in current.heads.items() if k != 'memory'}})
        db.execute('UPDATE scenes SET payload=? WHERE id=?', (payload.model_dump_json(), current.id))


@pytest.mark.parametrize('link,scene_index,reason', [('brief', 1, 'no_previous_memory'), ('prose', 1, 'no_previous_memory'),
                                                     ('memory', 0, 'no_memory')])
def test_unavailable_link_returns_its_reason(tmp_path, link, scene_index, reason):
    # No auditor configured: an unavailable link is reported before the settings are asked for.
    repo, story, scenes = book(tmp_path, 2)
    drop_memory(repo, scenes[0])
    state = link_state(repo.context_view(story.id), scenes[scene_index].id, link)
    result = build_audit_context(repo, scenes[scene_index].id, link)
    assert isinstance(result, AuditUnavailable)
    assert result.reason == state.reason == reason
    assert result.fingerprint == state.fingerprint and result.inputs == state.inputs


def test_missing_link_is_an_error(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Твір'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена', beats='Студія'))
    auditor(repo, story)
    with pytest.raises(ValueError):
        build_audit_context(repo, scene.id, 'brief')


def test_auditor_not_configured(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    with pytest.raises(ValueError, match='Роль не налаштовано: Ревізор'):
        build_audit_context(repo, scene.id, 'brief')


def test_derived_auditor_from_editor(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    save_role_settings(repo, story.id, 'editor', RoleSettings(provider=ProviderSettings(model='editor-model')),
                       repo.get_story(story.id).revision)
    context = build_audit_context(repo, scene.id, 'memory')
    assert context.settings.provider.model == 'editor-model'


def test_overflow_is_unavailable_without_truncation(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    auditor(repo, story, max_input_chars=100)
    result = build_audit_context(repo, scene.id, 'prose')
    assert isinstance(result, AuditUnavailable)
    assert result.reason.startswith('Вхід перевірки перевищує ліміт Ревізора: ')
    assert result.reason.endswith(' символів із 100')
    assert result.fingerprint == link_state(repo.context_view(story.id), scene.id, 'prose').fingerprint


def test_invalidation_marker_is_the_latest_story_invalidation(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    auditor(repo, story)
    rowids = []
    for scene in scenes:
        record = LinkInvalidation(id=new_verdict_id(), story_id=story.id, scene_id=scene.id, links=['brief'],
                                  fingerprints={'brief': 'a' * 64}, reason={'kind': 'character', 'ids': ['c1']},
                                  created_at='2026-11-23T00:00:00+00:00')
        with repo.db.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            write_invalidation(db, record)
            rowids.append(db.execute('SELECT rowid FROM app_settings WHERE key=?',
                                     ('link_invalidation:' + story.id + ':' + record.id,)).fetchone()[0])
    context = build_audit_context(repo, scenes[0].id, 'memory')
    assert context.fragments['invalidation_marker'] == str(rowids[-1])


def test_custom_prompt_version_is_used(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    prompt = repo.save_version(story.id, None, 'prompt', 'Власний промпт Ревізора для пам’яті.', [],
                               prompt_contract=PromptContract(stage='audit_memory', mode='json', schema_version=1))
    auditor(repo, story, stage_prompt_version_ids={'audit_memory': prompt.id})
    context = build_audit_context(repo, scene.id, 'memory')
    assert context.system_text == 'Власний промпт Ревізора для пам’яті.'
    assert prompt.id in context.input_refs


def test_english_story_uses_english_prompt(tmp_path):
    repo, story, (scene,) = book(tmp_path)
    with repo.db.connection() as db:
        db.execute('UPDATE stories SET payload=? WHERE id=?',
                   (repo.get_story(story.id).model_copy(update={'language': 'en'}).model_dump_json(), story.id))
    auditor(repo, story)
    context = build_audit_context(repo, scene.id, 'brief')
    assert context.system_text.startswith('You are a story auditor')
