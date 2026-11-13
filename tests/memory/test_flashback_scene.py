"""STORY-TIME-S03 (the flag and the mark make a flashback), S06 (the selector is written only with a non-default value)."""
from storygen.domain import Scene, SceneCreate, StoryCreate
from storygen.memory.story_time import flashback_mode, is_flashback
from storygen.storage.repository import Repository
from tests.memory.merge_helpers import arc_book


def scene(**fields):
    return Scene(id='s', story_id='b', position=0, title='С', **fields)


def selectors_of(repo, version_id):
    return repo.get_version(version_id).dependency_snapshot.selectors


def test_flag_or_mark_makes_a_flashback():
    assert is_flashback(scene(flashback=True))
    assert is_flashback(scene(beats='Початок: Рік -3 (спогад)'))
    assert not is_flashback(scene(beats='Початок: Рік 1'))


def test_book_story_time_reexports_is_flashback():
    from storygen.book import story_time
    assert story_time.is_flashback is is_flashback


def test_mode_follows_the_book(tmp_path):
    repo = Repository(tmp_path / 'flat')
    story = repo.create_story(StoryCreate(title='Оповідання'))
    repo.create_scene(story.id, SceneCreate(title='Сцена 1'))
    assert flashback_mode(repo.get_story(story.id), repo.list_scenes(story.id)) == 'simple'
    repo, story, scenes = arc_book(tmp_path / 'book', 'A B', [['A', 'B']])
    assert flashback_mode(story, scenes) == 'full'


def test_patch_sets_flag_and_bumps_revision(tmp_path):
    repo, _, scenes = arc_book(tmp_path, 'A', [['A']])
    saved = repo.update_scene_metadata(scenes[0].id, {'flashback': True}, scenes[0].revision)
    assert saved.flashback and saved.revision == scenes[0].revision + 1


def test_flag_stales_memory_through_the_selector(tmp_path):
    from storygen.memory.journal import load_memory
    from storygen.memory.service import save_memory_journal
    repo, _, scenes = arc_book(tmp_path, 'A B A', [['A', 'B']])
    # A memory version with a dependency snapshot (written before the flag existed: no flashback selector in it).
    journal = load_memory(repo.read_text(scenes[2].heads['memory']))
    memory = save_memory_journal(repo, scenes[2].id, journal, scenes[2].revision).id
    scenes[2] = repo.get_scene(scenes[2].id)
    assert not any(s.field == 'flashback' for s in repo.get_version(memory).dependency_snapshot.selectors)
    assert not repo.get_version(memory).stale
    repo.update_scene_metadata(scenes[2].id, {'flashback': True}, scenes[2].revision)
    assert repo.get_version(memory).stale
    assert not repo.get_version(scenes[0].heads['memory']).stale


def test_book_without_flashbacks_writes_no_flashback_selector(tmp_path):
    from storygen.providers.models import ProviderSettings, RoleSettings
    from storygen.storage.snapshots import build_dependency_snapshot
    repo, story, scenes = arc_book(tmp_path, 'A B A', [['A', 'B']])
    view = repo.context_view(story.id)
    for item in scenes:
        snapshot = build_dependency_snapshot(view, item.id, 'memory', RoleSettings(provider=ProviderSettings(model='t')), [])
        assert not any(s.field == 'flashback' for s in snapshot.selectors)


def test_flashback_scene_writes_the_selector(tmp_path):
    from storygen.providers.models import ProviderSettings, RoleSettings
    from storygen.storage.snapshots import build_dependency_snapshot
    repo, story, scenes = arc_book(tmp_path, 'A B', [['A', 'B']])
    repo.update_scene_metadata(scenes[1].id, {'flashback': True}, scenes[1].revision)
    snapshot = build_dependency_snapshot(repo.context_view(story.id), scenes[1].id, 'memory', RoleSettings(provider=ProviderSettings(model='t')), [])
    assert [(s.owner_id, s.expected) for s in snapshot.selectors if s.field == 'flashback'] == [(scenes[1].id, True)]
