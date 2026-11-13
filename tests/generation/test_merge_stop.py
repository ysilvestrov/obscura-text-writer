"""MEMORY-MERGE-S02 (pipeline): a run stops before a scene whose merge point has no confirmed merge; readiness names it."""
from storygen.authoring.blueprints import save_role_settings
from storygen.generation.readiness import preview
from storygen.generation.worker import RunCoordinator, RunRequest
from storygen.memory.previous import MERGE_REQUIRED
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import GenerationEvent
from tests.storage.test_memory_merges import meeting_book


def planner(repo, story_id):
    save_role_settings(repo, story_id, 'planner', RoleSettings(provider=ProviderSettings(model='planner')), repo.get_story(story_id).revision)


def test_run_stops_before_merge_scene(tmp_path):
    # The merge is confirmed when the run is queued and becomes unusable before the worker reaches the scene.
    repo, story, scenes = meeting_book(tmp_path)
    planner(repo, story.id)
    from tests.memory.test_previous_memory import confirm
    confirm(repo, repo.get_story(story.id), scenes, scenes[2].id)

    class Gateway:
        calls = 0

        def stream(self, *args):
            self.calls += 1
            yield GenerationEvent(type='delta', text='{"objective":"Мета","beats":["Подія"]}')
            yield GenerationEvent(type='terminal', finish_reason='stop')
    gateway = Gateway()
    worker = RunCoordinator(repo, lambda _: gateway)
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scenes[3].id, mode='stage', stage='brief'), 'merge-stop')
    from storygen.memory.journal import load_memory
    from tests.memory.merge_helpers import fact, save_scene_journal
    head = repo.get_scene(scenes[2].id)
    previous = load_memory(repo.read_text(scenes[0].heads['memory']))
    save_scene_journal(repo, head, previous, [fact('Анна знайшла ключ', head.heads['prose'])])
    worker._execute(run.id)  # synchronously, as the worker loop would; start() would treat a queued run as interrupted
    current = worker.get_run(run.id)
    assert (current.state, current.error) == ('needs_review', MERGE_REQUIRED)
    assert gateway.calls == 0


def test_run_cannot_be_queued_at_a_merge_scene(tmp_path):
    import pytest
    repo, story, scenes = meeting_book(tmp_path)
    planner(repo, story.id)
    with pytest.raises(ValueError, match='злиття'):
        RunCoordinator(repo, lambda _: None).enqueue(RunRequest(story_id=story.id, scene_id=scenes[3].id, mode='stage', stage='brief'), 'q')


def test_readiness_names_memory_merge_required(tmp_path):
    repo, story, scenes = meeting_book(tmp_path)
    planner(repo, story.id)
    result = preview(repo, RunRequest(story_id=story.id, scene_id=scenes[3].id, mode='stage', stage='brief'))
    assert result['ready'] is False and result['reason'] == MERGE_REQUIRED
    assert result['reason_code'] == 'memory_merge_required' and result['merge_key'].startswith('heads:')
