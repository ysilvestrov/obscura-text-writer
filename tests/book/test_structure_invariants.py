"""BOOK-STRUCTURE-S01/S02: the structure never enters a context, a fingerprint or a dependency snapshot."""
import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.memory.models import MemoryEntry, MemorySnapshot
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.book_structure import clear_structure, put_structure
from storygen.storage.repository import Repository
from storygen.storage.snapshots import compare_snapshot

SETTINGS = RoleSettings(provider=ProviderSettings(model='test'))


def book(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    scenes = [repo.create_scene(story.id, SceneCreate(title=f'Сцена {i+1}', beats=f'План {i+1}')) for i in range(3)]
    prose = repo.save_version(story.id, scenes[0].id, 'manual', 'Минуле сталося.', [])
    repo.set_head(scenes[0].id, 'prose', prose.id, 0)
    memory = MemorySnapshot(facts=[MemoryEntry(text='Минуле', source_version_id=prose.id, quote='Минуле')], source_prose_ids=[prose.id])
    ref = repo.save_version(story.id, scenes[0].id, 'memory', memory.model_dump_json(), [prose.id])
    repo.set_head(scenes[0].id, 'memory', ref.id, 1)
    return repo, story.id, scenes


def brief(repo, scene_id):
    context = build_context(repo, scene_id, 'brief', SETTINGS)
    return context.system_text, context.user_text, context.input_refs, context.fingerprint, context.dependency_snapshot


def fresh(repo, story_id, snapshot):
    return not compare_snapshot(repo.context_view(story_id), snapshot)


@pytest.mark.req('BOOK-STRUCTURE')
def test_flat_book_context_unchanged_by_structure_round_trip(tmp_path):
    repo, story_id, scenes = book(tmp_path)
    before = brief(repo, scenes[1].id)
    story = put_structure(repo, story_id, [{'id': 'p1', 'arcs': [{'id': 'a1'}]}], {}, repo.get_story(story_id).revision)
    clear_structure(repo, story_id, story.revision)
    after = brief(repo, scenes[1].id)
    assert after[:4] == before[:4]
    assert fresh(repo, story_id, before[4])


@pytest.mark.req('BOOK-STRUCTURE')
def test_structured_book_context_unchanged_by_regrouping(tmp_path):
    repo, story_id, scenes = book(tmp_path)
    parts = [{'id': 'p1', 'title': 'Перша', 'arcs': [{'id': 'a1', 'title': 'Ранок'}]}, {'id': 'p2', 'arcs': [{'id': 'b1'}]}]
    put_structure(repo, story_id, parts, {scenes[0].id: 'a1', scenes[1].id: 'a1', scenes[2].id: 'b1'}, repo.get_story(story_id).revision)
    before = brief(repo, scenes[1].id)
    regrouped = [{'id': 'p1', 'title': 'Інша назва', 'arcs': [{'id': 'a1', 'title': 'Вечір'}, {'id': 'a2'}]}, {'id': 'p2', 'arcs': [{'id': 'b1'}]}]
    put_structure(repo, story_id, regrouped, {scenes[0].id: 'a1', scenes[1].id: 'a2', scenes[2].id: 'b1'}, repo.get_story(story_id).revision)
    after = brief(repo, scenes[1].id)
    assert after[:4] == before[:4]
    assert 'Ранок' not in after[1] and 'Вечір' not in after[1] and 'Перша' not in after[1]
    assert fresh(repo, story_id, before[4])
