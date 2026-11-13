"""MEMORY-MERGE-S02: a scene after a merge point reads the confirmed merge; without it the context is not built."""
import pytest

from storygen.generation.context import build_context
from storygen.memory.journal import _extend, replay_memory
from storygen.memory.previous import MergeRequired, previous_memory
from storygen.memory.service import journal_before, save_scene_memory
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.memory_merges import merge_point, save_merge
from storygen.storage.snapshots import compare_snapshot
from tests.memory.merge_helpers import fact
from tests.storage.test_memory_merges import meeting_book

SETTINGS = RoleSettings(provider=ProviderSettings(model='test'))


def confirm(repo, story, scenes, choice):
    point = merge_point(story, scenes, scene_id=scenes[3].id)
    memory_ids = [repo.get_scene(h).heads['memory'] for h in point.heads]
    return save_merge(repo, story.id, point.key, {'slot:c1:clothing': {'choice': choice}}, repo.get_story(story.id).revision, memory_ids)


def test_merge_scene_without_merge_refuses_context(tmp_path):
    repo, story, scenes = meeting_book(tmp_path)
    with pytest.raises(MergeRequired, match='Потрібне злиття пам’яті перед цією сценою'):
        build_context(repo, scenes[3].id, 'brief', SETTINGS)
    with pytest.raises(MergeRequired):
        journal_before(repo, scenes[3].id)
    assert previous_memory(repo.context_view(story.id), scenes[3], require=False).memory_id is None


def test_merged_journal_is_previous_memory(tmp_path):
    repo, story, scenes = meeting_book(tmp_path)
    _, version_id = confirm(repo, story, scenes, scenes[2].id)
    journal = journal_before(repo, scenes[3].id)
    assert any(e.text == 'Анна в плащі' for e in replay_memory(journal).values())
    context = build_context(repo, scenes[3].id, 'brief', SETTINGS)
    assert version_id in context.input_refs and 'Анна в плащі' in context.user_text
    # A manual memory of the meeting scene extends the merged journal.
    scene = repo.get_scene(scenes[3].id)
    extended = _extend(journal, scene.heads['prose'], [fact('Анна й Богдан зустрілися', scene.heads['prose'])], 3)
    saved = save_scene_memory(repo, scene.id, extended.model_dump_json(), scene.revision)
    assert version_id in repo.get_version(saved.id).input_refs


def test_snapshot_of_merge_scene_selects_merge_head(tmp_path):
    repo, story, scenes = meeting_book(tmp_path)
    confirm(repo, story, scenes, scenes[2].id)
    context = build_context(repo, scenes[3].id, 'brief', SETTINGS)
    assert not compare_snapshot(repo.context_view(story.id), context.dependency_snapshot)
    confirm(repo, repo.get_story(story.id), scenes, scenes[1].id)
    assert compare_snapshot(repo.context_view(story.id), context.dependency_snapshot)


def test_prose_tail_of_merge_scene_is_latest_head(tmp_path):
    repo, story, scenes = meeting_book(tmp_path)
    confirm(repo, story, scenes, scenes[2].id)
    context = build_context(repo, scenes[3].id, 'brief', SETTINGS)
    assert context.fragments['previous_prose_tail'].endswith('Сцена 3. Анна йде містом.')
