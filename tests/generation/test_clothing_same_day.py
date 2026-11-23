"""Clothing of the same story day in the writing context (CONTEXT-002-S07, S08; #225)."""
import pytest

from storygen.application.writing_context import writing_context
from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.memory.journal import MemoryJournal, _add_event, _change_event
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository
from storygen.storage.snapshots import resolve_freshness
from tests.link_helpers import approve_links

BRIEF = '{"objective":"Анна вечеряє","beats":["Анна вечеряє"],"constraints":[],"proposed_changes":[],"introduced":[]}'
HINT = 'одяг: Гола (раніше цього дня: Сукня, сандалі)'


def role():
    return RoleSettings(provider=ProviderSettings(model='fake'), context_tokens=262144)


def three_scenes(tmp_path, days=('день 2', 'день 2', 'день 2')):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Дні'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=f'Сцена {n}', beats=f'Початок: {day}, {8 + n}:00', character_ids=['A']))
              for n, day in enumerate(days, 1)]
    p1 = repo.save_version(story.id, scenes[0].id, 'manual', 'Анна в сукні й сандалях.', [])
    repo.set_head(scenes[0].id, 'prose', p1.id, repo.get_scene(scenes[0].id).revision)
    p2 = repo.save_version(story.id, scenes[1].id, 'manual', 'Анна роздяглася й попливла.', [])
    repo.set_head(scenes[1].id, 'prose', p2.id, repo.get_scene(scenes[1].id).revision)
    add = _add_event('character_states', 'Сукня, сандалі', p1.id, 'в сукні й сандалях', 0, ['A'], slot='clothing')
    update = _change_event('update', add.claim_id, 'Гола', 'character_states', ['A'], p2.id, 'роздяглася', slot='clothing')
    journal = MemoryJournal(schema_version=3, source_prose_ids=[p1.id, p2.id], events=[add, update])
    memory = repo.save_version(story.id, scenes[1].id, 'memory', journal.model_dump_json(), [p1.id, p2.id])
    repo.set_head(scenes[1].id, 'memory', memory.id, repo.get_scene(scenes[1].id).revision)
    approve_links(repo, story.id)
    return repo, story, [repo.get_scene(s.id) for s in scenes]


def with_brief(repo, story, scene):
    brief = repo.save_version(story.id, scene.id, 'brief', BRIEF, [])
    repo.set_head(scene.id, 'brief', brief.id, repo.get_scene(scene.id).revision)
    approve_links(repo, story.id)
    return repo.get_scene(scene.id)


def reasons(repo, story, ref):
    return [(r.reason, r.selector.field if r.selector else None, r.selector.owner_id if r.selector else None)
            for r in resolve_freshness(repo.context_view(story.id), ref.id).reasons]


@pytest.mark.req('CONTEXT-002')
def test_brief_draft_and_mcp_see_clothing_of_the_same_day(tmp_path):
    repo, story, (_, _, s3) = three_scenes(tmp_path)
    assert HINT in build_context(repo, s3.id, 'brief', role()).user_text
    assert HINT in build_context(repo, with_brief(repo, story, s3).id, 'draft', role()).user_text
    assert HINT in writing_context(repo, s3.id)['memory']


@pytest.mark.req('CONTEXT-002')
def test_no_hint_when_the_earlier_value_is_from_another_day(tmp_path):
    repo, _, (_, _, s3) = three_scenes(tmp_path, days=('день 1', 'день 2', 'день 2'))
    text = build_context(repo, s3.id, 'brief', role()).user_text
    assert 'одяг: Гола\n' in text and 'раніше цього дня' not in text


@pytest.mark.req('CONTEXT-002')
def test_draft_goes_stale_when_the_source_scene_changes_day(tmp_path):
    repo, story, (s1, _, s3) = three_scenes(tmp_path)
    s3 = with_brief(repo, story, s3)
    bundle = build_context(repo, s3.id, 'draft', role())
    assert any(s.field == 'memory_day_key' and s.owner_id == s1.id for s in bundle.dependency_snapshot.selectors)
    draft = repo.save_version(story.id, s3.id, 'draft', 'Текст.', bundle.input_refs, dependency_snapshot=bundle.dependency_snapshot)
    assert reasons(repo, story, draft) == []
    repo.update_scene_plan(s1.id, 'Початок: день 1, 09:00', repo.get_scene(s1.id).revision)
    assert ('selector_changed', 'memory_day_key', s1.id) in reasons(repo, story, draft)


@pytest.mark.req('CONTEXT-002')
def test_snapshot_without_the_new_selectors_stays_fresh(tmp_path):
    repo, story, (s1, _, s3) = three_scenes(tmp_path)
    s3 = with_brief(repo, story, s3)
    bundle = build_context(repo, s3.id, 'draft', role())
    old = bundle.dependency_snapshot.model_copy(update={'selectors': [
        s for s in bundle.dependency_snapshot.selectors if not (s.field == 'memory_day_key' and s.owner_id == s1.id)]})
    draft = repo.save_version(story.id, s3.id, 'draft', 'Текст.', bundle.input_refs, dependency_snapshot=old)
    repo.update_scene_plan(s1.id, 'Початок: день 1, 09:00', repo.get_scene(s1.id).revision)
    assert reasons(repo, story, draft) == []


@pytest.mark.req('MEMORY-002')
def test_builtin_memory_prompt_keeps_where_removed_clothing_is():
    from storygen.generation.prompts import role_prompt
    from storygen.prompt_contracts import expected_contract
    uk, en = role_prompt('memory', role(), 'uk'), role_prompt('memory', role(), 'en')
    assert ('clothing: коли персонаж знімає одяг або переодягається, а проза показує, де лишився знятий одяг, '
            'додай це до значення: "гола; сукня й сандалі лишилися на березі".') in uk
    assert ('clothing: when a character takes clothes off or changes, and the prose shows where the removed clothes are, '
            'add that to the value: "naked; the dress and sandals are left on the shore".') in en
    contract = expected_contract('memory', role())
    assert (contract.stage, contract.mode, contract.schema_version) == ('memory', 'evidence_delta', 4)


@pytest.mark.req('CONTEXT-002')
def test_mcp_draft_goes_stale_when_the_source_scene_changes_day(tmp_path):
    from storygen.domain import ExternalOrigin
    from storygen.generation.dependencies import save_manual_draft
    repo, story, (s1, _, s3) = three_scenes(tmp_path)
    data = writing_context(repo, s3.id)
    assert HINT in data['memory']
    external = save_manual_draft(repo, s3.id, 'Анна вдяглася.', repo.get_scene(s3.id).revision,
        external_origin=ExternalOrigin(client='test'), expected_context_fingerprint=data['context_fingerprint'],
        expected_draft_version_id=None)
    assert reasons(repo, story, external) == []
    repo.update_scene_plan(s1.id, 'Початок: день 1, 09:00', repo.get_scene(s1.id).revision)
    assert ('selector_changed', 'memory_day_key', s1.id) in reasons(repo, story, external)
