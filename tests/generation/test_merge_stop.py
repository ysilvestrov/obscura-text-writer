"""MEMORY-MERGE-S02 (pipeline): a run stops before a scene whose merge point has no confirmed merge; readiness names it."""
from storygen.authoring.blueprints import save_role_settings
from storygen.generation.readiness import preview
from storygen.generation.worker import RunCoordinator, RunRequest
from storygen.memory.previous import MERGE_REQUIRED
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.providers.streaming import GenerationEvent
from tests.generation.test_worker import wait_until
from tests.storage.test_memory_merges import meeting_book


def planner(repo, story_id):
    save_role_settings(repo, story_id, 'planner', RoleSettings(provider=ProviderSettings(model='planner')), repo.get_story(story_id).revision)


def test_run_stops_before_merge_scene(tmp_path):
    repo, story, scenes = meeting_book(tmp_path)
    planner(repo, story.id)

    class Gateway:
        calls = 0

        def stream(self, *args):
            self.calls += 1
            yield GenerationEvent(type='delta', text='{"objective":"Мета","beats":["Подія"]}')
            yield GenerationEvent(type='terminal', finish_reason='stop')
    gateway = Gateway()
    worker = RunCoordinator(repo, lambda _: gateway)
    worker.start()
    try:
        run = worker.enqueue(RunRequest(story_id=story.id, scene_id=scenes[3].id, mode='stage', stage='brief'), 'merge-stop')
        wait_until(lambda: worker.get_run(run.id).state in {'completed', 'failed', 'needs_review'})
        current = worker.get_run(run.id)
    finally:
        worker.stop()
    assert current.state == 'needs_review' and current.error == MERGE_REQUIRED
    assert gateway.calls == 0


def test_readiness_names_memory_merge_required(tmp_path):
    repo, story, scenes = meeting_book(tmp_path)
    planner(repo, story.id)
    result = preview(repo, RunRequest(story_id=story.id, scene_id=scenes[3].id, mode='stage', stage='brief'))
    assert result['ready'] is False and result['reason'] == MERGE_REQUIRED
    assert result['reason_code'] == 'memory_merge_required' and result['merge_key'].startswith('heads:')
