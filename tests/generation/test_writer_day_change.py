"""Core state and day change for the writer and the brief (CONTEXT-002-S04…S06, MCP-BRIDGE-S26)."""
import pytest

from storygen.application.writing_context import writing_context
from storygen.domain import ExternalOrigin, RevisionConflict, SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.dependencies import save_manual_draft, writing_fingerprint
from storygen.generation.prompts import default_prompt
from storygen.language import load_prompt
from storygen.memory.journal import MemoryJournal, _add_event
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository
from storygen.storage.snapshots import resolve_freshness

BRIEF = '{"objective":"Анна йде на роботу","beats":["Анна йде на роботу"],"constraints":[],"proposed_changes":[],"introduced":[]}'
NOTE = 'ЗМІНИВСЯ ДЕНЬ: день 1 → день 2 ('
DAY_FIELDS = {'memory_day_key', 'tracked_characters'}


def role():
    return RoleSettings(provider=ProviderSettings(model='fake'), context_tokens=262144)


def two_scenes(tmp_path, first='Початок: день 1, 20:00', second='Початок: день 2, 08:00', cast=('A',), language='uk'):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Дні', language=language))
    s1 = repo.create_scene(story.id, SceneCreate(title='Вечір', beats=first, character_ids=['A']))
    s2 = repo.create_scene(story.id, SceneCreate(title='Ранок', beats=second, character_ids=list(cast)))
    prose = repo.save_version(story.id, s1.id, 'manual', 'Анна вдома в синьому халаті.', [])
    repo.set_head(s1.id, 'prose', prose.id, repo.get_scene(s1.id).revision)
    events = [_add_event('character_states', 'Синій халат', prose.id, 'в синьому халаті', 0, ['A'], slot='clothing')]
    journal = MemoryJournal(schema_version=3, source_prose_ids=[prose.id], events=events)
    memory = repo.save_version(story.id, s1.id, 'memory', journal.model_dump_json(), [prose.id])
    repo.set_head(s1.id, 'memory', memory.id, repo.get_scene(s1.id).revision)
    return repo, story, repo.get_scene(s1.id), repo.get_scene(s2.id)


def with_brief(repo, story, scene):
    brief = repo.save_version(story.id, scene.id, 'brief', BRIEF, [])
    repo.set_head(scene.id, 'brief', brief.id, repo.get_scene(scene.id).revision)
    return repo.get_scene(scene.id)


def saved(repo, story, scene, kind, bundle):
    return repo.save_version(story.id, scene.id, kind, 'Текст.', bundle.input_refs, dependency_snapshot=bundle.dependency_snapshot)


def reasons(repo, story, ref):
    return [(r.reason, r.selector.field if r.selector else None) for r in resolve_freshness(repo.context_view(story.id), ref.id).reasons]


@pytest.mark.req('CONTEXT-002')
def test_day_change_note_follows_memory_in_brief_and_draft(tmp_path):
    repo, story, _, scene = two_scenes(tmp_path)
    brief = build_context(repo, scene.id, 'brief', role())
    text = brief.user_text
    assert NOTE + 'протагоніст)' in text
    assert text.index('ЯДРО СТАНУ — ') < text.index(NOTE) < text.index('ЗАВЕРШЕННЯ ПОПЕРЕДНЬОЇ СЦЕНИ')
    assert 'Одяг, речі при собі й тілесний стан у «ЯДРО СТАНУ» — з попереднього дня' in text
    draft = build_context(repo, with_brief(repo, story, scene).id, 'draft', role())
    assert NOTE in draft.user_text


@pytest.mark.req('CONTEXT-002')
def test_no_day_change_note_without_change_or_hero(tmp_path):
    repo, _, _, scene = two_scenes(tmp_path, second='Початок: день 1, 23:00')
    assert 'ЗМІНИВСЯ ДЕНЬ' not in build_context(repo, scene.id, 'brief', role()).user_text
    repo, _, _, scene = two_scenes(tmp_path / 'plain', first='Анна вдома.')
    assert 'ЗМІНИВСЯ ДЕНЬ' not in build_context(repo, scene.id, 'brief', role()).user_text
    repo, _, _, scene = two_scenes(tmp_path / 'absent', cast=('B',))
    assert 'ЗМІНИВСЯ ДЕНЬ' not in build_context(repo, scene.id, 'brief', role()).user_text


@pytest.mark.req('CONTEXT-002')
def test_day_change_note_in_english_story(tmp_path):
    repo, _, _, scene = two_scenes(tmp_path, language='en')
    text = build_context(repo, scene.id, 'brief', role()).user_text
    assert 'DAY CHANGED: day 1 → day 2 (' in text
    assert 'Clothing, items carried and bodily state in "CORE STATE" are from the previous day' in text


@pytest.mark.req('CONTEXT-002')
def test_brief_and_draft_go_stale_on_comparison_day_change_only(tmp_path):
    repo, story, s1, s2 = two_scenes(tmp_path, first='Початок: 1.3.2024, 20:00', second='Початок: 2.3.2024, 08:00')
    bundle = build_context(repo, s2.id, 'brief', role())
    assert {s.field for s in bundle.dependency_snapshot.selectors} >= DAY_FIELDS
    brief = saved(repo, story, s2, 'brief', bundle)
    draft_bundle = build_context(repo, with_brief(repo, story, s2).id, 'draft', role())
    assert {s.field for s in draft_bundle.dependency_snapshot.selectors} >= DAY_FIELDS
    draft = saved(repo, story, s2, 'draft', draft_bundle)
    repo.update_scene_plan(s1.id, 'Початок: 01.03.24, 20:00', repo.get_scene(s1.id).revision)
    assert reasons(repo, story, brief) == [] and reasons(repo, story, draft) == []
    repo.update_scene_plan(s1.id, 'Початок: 29.2.2024, 20:00', repo.get_scene(s1.id).revision)
    for ref in (brief, draft):
        assert ('selector_changed', 'memory_day_key') in reasons(repo, story, ref)


@pytest.mark.req('CONTEXT-002')
def test_rules_in_builtin_writer_and_brief_prompts(tmp_path):
    for stage in ('draft', 'brief'):
        uk, en = default_prompt(stage, 'uk'), default_prompt(stage, 'en')
        assert '«ЯДРО СТАНУ»' in uk and '«ЗМІНИВСЯ ДЕНЬ»' in uk
        assert '"CORE STATE"' in en and '"DAY CHANGED"' in en
    # Earlier texts stay loadable for historical requests.
    assert 'ЯДРО' not in load_prompt('writer_v1', 'uk') and 'ЯДРО' not in load_prompt('brief_v2', 'uk')
    # A built-in prompt is not a dependency: changing it cannot stale existing versions.
    repo, story, _, scene = two_scenes(tmp_path)
    bundle = build_context(repo, with_brief(repo, story, scene).id, 'draft', role())
    assert all(repo.get_version(id).kind != 'prompt' for id in bundle.input_refs)
    assert all(repo.get_version(id).kind != 'prompt' for id in bundle.dependency_snapshot.refs)


@pytest.mark.req('MCP-BRIDGE')
def test_mcp_writing_context_has_day_change_and_external_draft_selectors(tmp_path):
    repo, story, s1, s2 = two_scenes(tmp_path)
    data = writing_context(repo, s2.id)
    assert data['day_change'].startswith(NOTE)
    assert data['day_change'] in build_context(repo, s2.id, 'brief', role()).user_text
    plain = writing_context(repo, s1.id)
    assert plain['day_change'] is None
    # A client holding the context from before a day change is rejected without a new version.
    old_fingerprint = data['context_fingerprint']
    repo.update_scene_plan(s1.id, 'Початок: день 0, 20:00', repo.get_scene(s1.id).revision)
    with pytest.raises(RevisionConflict, match='Контекст сцени змінився'):
        save_manual_draft(repo, s2.id, 'Анна в пальті.', repo.get_scene(s2.id).revision, external_origin=ExternalOrigin(client='test'),
            expected_context_fingerprint=old_fingerprint, expected_draft_version_id=None)
    assert repo.get_scene(s2.id).heads.get('draft') is None
    fresh = writing_context(repo, s2.id)
    assert fresh['day_change'].startswith('ЗМІНИВСЯ ДЕНЬ: день 0 → день 2 (')
    external = save_manual_draft(repo, s2.id, 'Анна в пальті.', repo.get_scene(s2.id).revision,
        external_origin=ExternalOrigin(client='test'), expected_context_fingerprint=fresh['context_fingerprint'],
        expected_draft_version_id=None)
    assert {s.field for s in external.dependency_snapshot.selectors} >= DAY_FIELDS
    own = save_manual_draft(repo, s1.id, 'Анна вдома.', repo.get_scene(s1.id).revision)
    assert not {s.field for s in own.dependency_snapshot.selectors} & DAY_FIELDS
    repo.update_scene_plan(s1.id, 'Початок: день 1, 20:00', repo.get_scene(s1.id).revision)
    assert ('selector_changed', 'memory_day_key') in reasons(repo, story, external)
