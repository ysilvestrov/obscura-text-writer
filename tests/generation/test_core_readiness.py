import pytest

from storygen.authoring.blueprints import save_role_settings
from storygen.domain import SceneCreate
from storygen.generation.worker import RunCoordinator
from storygen.memory.journal import MemoryJournal, _add_event, _extend
from storygen.providers.models import ProviderSettings, RoleSettings
from tests.memory.test_core_review import two_scenes


def core_story(tmp_path):
    """Two scenes whose memory heads carry core slots, plus a scene without memory."""
    repo, story, s1, s2, journal, claims = two_scenes(tmp_path)
    p2 = s2.heads['prose']
    moved = _add_event('character_states', 'Біля дверей', p2, 'Стукав сусід.', 0, ['A'], slot='location')
    memory = repo.save_version(story.id, s2.id, 'memory', _extend(journal, p2, [moved], 3).model_dump_json(), [s1.heads['prose'], p2])
    repo.set_head(s2.id, 'memory', memory.id, repo.get_scene(s2.id).revision)
    repo.create_scene(story.id, SceneCreate(title='С3', beats='Анна.', character_ids=['A']))
    for name in ['planner', 'writer', 'editor', 'memory']:
        save_role_settings(repo, story.id, name, RoleSettings(provider=ProviderSettings(model=name)), repo.get_story(story.id).revision)
    return repo, story, repo.get_scene(s1.id), repo.get_scene(s2.id)


@pytest.mark.req('MEMORY-CONFIRM')
def test_unconfirmed_count_is_info_not_block(tmp_path):
    repo, story, s1, s2 = core_story(tmp_path)
    worker = RunCoordinator(repo)
    before = worker.readiness(story.id, s1.id)['operations']
    assert before['remaining']['unconfirmed_core_scenes'] == 2 and before['scene']['unconfirmed_core_scenes'] == 2
    repo.confirm_memory(s1.id, s1.heads['memory'], s1.revision)
    after = worker.readiness(story.id, s1.id)['operations']
    for name in ('remaining', 'scene'):
        assert after[name]['unconfirmed_core_scenes'] == 1
        # Information only: readiness and its reason are the same as before the confirmation.
        assert (after[name]['ready'], after[name]['reason']) == (before[name]['ready'], before[name]['reason'])
    assert 'unconfirmed_core_scenes' not in after['memory'] and 'unconfirmed_core_scenes' not in after['brief']


def test_unconfirmed_count_ignores_scenes_without_core(tmp_path):
    repo, story, s1, s2 = core_story(tmp_path)
    # A journal without slot events (old memory) is not a core to confirm.
    p1 = s1.heads['prose']
    plain = MemoryJournal(schema_version=3, source_prose_ids=[p1],
        events=[_add_event('facts', 'Будинок старий', p1, 'Анна в халаті.', 0)])
    memory = repo.save_version(story.id, s1.id, 'memory', plain.model_dump_json(), [p1])
    repo.set_head(s1.id, 'memory', memory.id, repo.get_scene(s1.id).revision)
    operations = RunCoordinator(repo).readiness(story.id, s1.id)['operations']
    assert operations['remaining']['unconfirmed_core_scenes'] == 1


def test_unconfirmed_count_parses_each_journal_once_per_request(tmp_path, monkeypatch):
    from storygen.generation import readiness as journal_module
    repo, story, s1, s2 = core_story(tmp_path)
    calls = []
    real = journal_module.load_memory
    monkeypatch.setattr(journal_module, 'load_memory', lambda raw: calls.append(raw) or real(raw))
    operations = RunCoordinator(repo).readiness(story.id, s1.id)['operations']
    assert operations['scene']['unconfirmed_core_scenes'] == operations['remaining']['unconfirmed_core_scenes'] == 2
    assert len(calls) == 2  # two unconfirmed journals, parsed once for both previews


def test_unconfirmed_count_skips_parsing_journal_without_slot_events(tmp_path, monkeypatch):
    from storygen.generation import readiness as journal_module
    repo, story, s1, s2 = core_story(tmp_path)
    p1, p2 = s1.heads['prose'], s2.heads['prose']
    for scene, prose in ((s1, p1), (s2, p2)):
        plain = MemoryJournal(schema_version=3, source_prose_ids=[prose],
            events=[_add_event('facts', 'Будинок старий', prose, 'Анна в халаті.', 0)])
        memory = repo.save_version(story.id, scene.id, 'memory', plain.model_dump_json(), [prose])
        repo.set_head(scene.id, 'memory', memory.id, repo.get_scene(scene.id).revision)
    calls = []
    real = journal_module.load_memory
    monkeypatch.setattr(journal_module, 'load_memory', lambda raw: calls.append(raw) or real(raw))
    operations = RunCoordinator(repo).readiness(story.id, s1.id)['operations']
    assert operations['scene']['unconfirmed_core_scenes'] == 0
    assert calls == []
