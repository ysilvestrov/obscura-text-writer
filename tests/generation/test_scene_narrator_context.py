"""SCENE-NARRATOR-S01, S03, S04: the narrator section of the writing context and its dependency (#214)."""
import json

import pytest

from storygen.domain import SceneCreate, SceneNarrator, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.models import StyleProfile
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository
from storygen.storage.snapshots import build_dependency_snapshot, resolve_freshness
from tests.link_helpers import approve_links

BRIEF = '{"objective":"Юлія чекає","beats":["Юлія чекає"],"constraints":[],"proposed_changes":[],"introduced":[]}'
HEAD = 'ОПОВІДАЧ СЦЕНИ — ДЛЯ ЦІЄЇ СЦЕНИ ЗАМІНЯЄ point_of_view ЗІ СТИЛЮ'


def role(edit_mode='prose'):
    return RoleSettings(provider=ProviderSettings(model='fake'), context_tokens=262144, edit_mode=edit_mode)


def setup(tmp_path, beats='Хто бере участь: Юлія\nЮлія чекає.', language='uk'):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Пристань', language=language))
    cards = [{'schema_version': 2, 'id': id, 'name': name, 'entries': []} for id, name in (('j', 'Юлія'), ('o', 'Олег'))]
    ref = repo.save_version(story.id, None, 'character_cards', json.dumps(cards, ensure_ascii=False), [])
    repo.publish_story_material(story.id, 'characters_version_id', ref.id, repo.get_story(story.id).revision)
    style = repo.save_version(story.id, None, 'style', StyleProfile().model_dump_json(), [])
    repo.publish_story_material(story.id, 'style_version_id', style.id, repo.get_story(story.id).revision)
    scene = repo.create_scene(story.id, SceneCreate(title='Пристань', beats=beats, character_ids=['j']))
    following = repo.create_scene(story.id, SceneCreate(title='Дім', beats='Хто бере участь: Юлія\nЮлія вдома.', character_ids=['j']))
    return repo, repo.get_story(story.id), scene, following


def narrate(repo, scene, narrator):
    return repo.update_scene_metadata(scene.id, {'narrator': narrator}, repo.get_scene(scene.id).revision)


def with_brief(repo, story, scene):
    brief = repo.save_version(story.id, scene.id, 'brief', BRIEF, [])
    repo.set_head(scene.id, 'brief', brief.id, repo.get_scene(scene.id).revision)
    approve_links(repo, story.id)
    return repo.get_scene(scene.id)


def section(text):
    return text.split(HEAD + '\n')[1].split('\n\n')[0] if HEAD in text else None


@pytest.mark.req('SCENE-NARRATOR')
def test_field_reaches_brief_and_draft_after_the_style(tmp_path):
    repo, story, scene, _ = setup(tmp_path)
    before = build_context(repo, scene.id, 'brief', role()).user_text
    assert HEAD not in before
    narrate(repo, scene, SceneNarrator(person='first', character_id='j'))
    text = build_context(repo, scene.id, 'brief', role()).user_text
    assert section(text) == 'Перша особа: розповідає Юлія.'
    assert text.index('ПРОФІЛЬ ПИСЬМА') < text.index(HEAD)
    draft = build_context(repo, with_brief(repo, story, scene).id, 'draft', role()).user_text
    assert section(draft) == 'Перша особа: розповідає Юлія.'
    # Removing the narrator gives the request built before, byte for byte.
    narrate(repo, scene, None)
    assert build_context(repo, scene.id, 'brief', role()).user_text == before


@pytest.mark.req('SCENE-NARRATOR')
def test_limited_and_omniscient_lines_and_english(tmp_path):
    repo, story, scene, _ = setup(tmp_path, beats='Хто бере участь: Юлія\nОповідач: третя особа, Олег')
    assert section(build_context(repo, scene.id, 'brief', role()).user_text) == 'Третя особа через героя: Олег (лише його сприйняття й знання).'
    repo, story, scene, _ = setup(tmp_path / 'omni')
    narrate(repo, scene, SceneNarrator(person='third_omniscient'))
    assert section(build_context(repo, scene.id, 'brief', role()).user_text) == 'Третя особа, всезнаючий оповідач.'
    repo, story, scene, _ = setup(tmp_path / 'en', language='en')
    narrate(repo, scene, SceneNarrator(person='first', character_id='j'))
    text = build_context(repo, scene.id, 'brief', role()).user_text
    assert 'SCENE NARRATOR — FOR THIS SCENE REPLACES point_of_view FROM THE STYLE\nFirst person: told by Юлія.' in text


@pytest.mark.req('SCENE-NARRATOR')
def test_hero_outside_the_cast_and_unparsed_line_warn(tmp_path):
    repo, story, scene, _ = setup(tmp_path)
    narrate(repo, scene, SceneNarrator(person='first', character_id='o'))
    bundle = build_context(repo, scene.id, 'brief', role())
    assert section(bundle.user_text) == 'Перша особа: розповідає Олег.'
    assert any('Оповідача немає серед учасників сцени' in w for w in bundle.context_warnings)
    repo, story, scene, _ = setup(tmp_path / 'bad', beats='Хто бере участь: Юлія\nОповідач: Марта, перша особа')
    bundle = build_context(repo, scene.id, 'brief', role())
    assert HEAD not in bundle.user_text and any('Оповідач:' in w for w in bundle.context_warnings)


@pytest.mark.req('SCENE-NARRATOR')
def test_patches_get_no_section(tmp_path):
    repo, story, scene, _ = setup(tmp_path)
    narrate(repo, scene, SceneNarrator(person='first', character_id='j'))
    scene = with_brief(repo, story, scene)
    draft = repo.save_version(story.id, scene.id, 'draft', 'Юлія чекала.', [])
    repo.set_head(scene.id, 'draft', draft.id, repo.get_scene(scene.id).revision)
    assert HEAD not in build_context(repo, scene.id, 'edit', role('patches')).user_text
    assert section(build_context(repo, scene.id, 'edit', role('prose')).user_text) == 'Перша особа: розповідає Юлія.'


def saved(repo, story, scene, kind, bundle):
    return repo.save_version(story.id, scene.id, kind, 'Текст.', bundle.input_refs, dependency_snapshot=bundle.dependency_snapshot)


def stale_fields(repo, story, ref):
    return [(r.reason, r.selector.field if r.selector else None) for r in resolve_freshness(repo.context_view(story.id), ref.id).reasons]


@pytest.mark.req('SCENE-NARRATOR')
def test_narrator_change_stales_brief_draft_and_prose_of_the_scene_only(tmp_path):
    from storygen.memory.journal import MemoryJournal
    repo, story, first, scene = setup(tmp_path)
    narrate(repo, first, SceneNarrator(person='first', character_id='j'))
    first = repo.get_scene(first.id)
    brief = saved(repo, story, first, 'brief', build_context(repo, first.id, 'brief', role()))
    repo.set_head(first.id, 'brief', brief.id, repo.get_scene(first.id).revision)
    approve_links(repo, story.id)
    draft = saved(repo, story, first, 'draft', build_context(repo, first.id, 'draft', role()))
    repo.set_head(first.id, 'draft', draft.id, repo.get_scene(first.id).revision)
    prose = saved(repo, story, first, 'edited', build_context(repo, first.id, 'edit', role()))
    repo.set_head(first.id, 'prose', prose.id, repo.get_scene(first.id).revision)
    journal = MemoryJournal(schema_version=3, source_prose_ids=[prose.id], events=[])
    memory = repo.save_version(story.id, first.id, 'memory', journal.model_dump_json(), [prose.id])
    repo.set_head(first.id, 'memory', memory.id, repo.get_scene(first.id).revision)
    approve_links(repo, story.id)
    # The next scene's brief is built on the first scene's prose.
    following = saved(repo, story, scene, 'brief', build_context(repo, scene.id, 'brief', role()))
    assert all(stale_fields(repo, story, ref) == [] for ref in (brief, draft, prose, following))
    narrate(repo, first, SceneNarrator(person='third_omniscient'))
    assert ('selector_changed', 'narrator') in stale_fields(repo, story, draft)
    # VALID-LINKS: the brief and prose heads are marked only by their links; a narrator change does not touch them
    for ref in (brief, prose):
        assert stale_fields(repo, story, ref) == []
    assert stale_fields(repo, story, following) == []


@pytest.mark.req('SCENE-NARRATOR')
def test_snapshot_without_the_selector_stays_fresh(tmp_path):
    repo, story, scene, _ = setup(tmp_path, beats='Хто бере участь: Юлія\nОповідач: Юлія, перша особа')
    bundle = build_context(repo, scene.id, 'brief', role())
    assert any(s.field == 'narrator' and s.expected == 'first:j' for s in bundle.dependency_snapshot.selectors)
    old = bundle.dependency_snapshot.model_copy(update={'selectors': [s for s in bundle.dependency_snapshot.selectors if s.field != 'narrator']})
    ref = repo.save_version(story.id, scene.id, 'brief', BRIEF, bundle.input_refs, dependency_snapshot=old)
    assert stale_fields(repo, story, ref) == []
    narrate(repo, scene, SceneNarrator(person='third_omniscient'))
    assert stale_fields(repo, story, ref) == []


@pytest.mark.req('SCENE-NARRATOR')
def test_unchanged_title_and_target_with_the_narrator_do_not_invalidate_heads(tmp_path):
    # The scene card sends title and target_words with every save; only fields that really change count.
    repo, story, first, scene = setup(tmp_path)
    first = repo.get_scene(first.id)
    prose = repo.save_version(story.id, first.id, 'manual', 'Текст.', [])
    repo.set_head(first.id, 'prose', prose.id, repo.get_scene(first.id).revision)
    following = repo.save_version(story.id, scene.id, 'draft', 'Далі.', [prose.id])
    first = repo.get_scene(first.id)
    repo.update_scene_metadata(first.id, {'title': first.title, 'target_words': first.target_words,
                                          'narrator': {'person': 'third_omniscient', 'character_id': None}}, first.revision)
    assert repo.get_version(following.id).stale is False
    assert repo.get_scene(scene.id).needs_review is False
