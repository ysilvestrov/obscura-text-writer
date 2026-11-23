"""The memory carry in the queue: a multi-stage run is not refused by the carry it queues itself (neutral texts)."""
from storygen.authoring.blueprints import save_role_settings
from storygen.generation.worker import RunCoordinator
from storygen.run_models import RunRequest
from tests.generation.test_scene_pipeline import FakeGateway
from tests.memory.test_memory_carry import carry_runs, new_memory, run_carries, state
from tests.storage.test_links import book, roles


def test_one_run_generates_three_scenes_without_refusal(tmp_path):
    repo, story, scenes = book(tmp_path, 3)
    for name, settings in roles().items():
        save_role_settings(repo, story.id, name, settings, repo.get_story(story.id).revision)
    first = repo.get_scene(scenes[0].id)
    # A new title changes the context of every stage of scene 1, so the run writes new material for all three scenes.
    repo.update_scene_metadata(first.id, {'title': 'Нова сцена'}, first.revision)
    old = {s.id: repo.get_scene(s.id).heads['memory'] for s in scenes}
    worker = RunCoordinator(repo, gateway_factory=lambda _: FakeGateway(repo))
    run = worker.enqueue(RunRequest(story_id=story.id, scene_id=first.id, mode='remaining'), 'regenerate')
    run.state = 'running'
    repo.save_run(run)
    worker._execute(run.id)
    run = worker.get_run(run.id)
    assert run.state == 'completed', run.error
    assert 'переноситься' not in (run.error or '') + (run.warning or '')
    assert all(repo.get_scene(s.id).heads['memory'] != old[s.id] for s in scenes)
    # Scenes 2 and 3 had memory when scene 1 got its new one: a carry was queued and finds nothing left to carry.
    assert carry_runs(repo, story.id)
    assert all(r.state == 'completed' for r in run_carries(repo, story.id))
    assert all(state(repo, story, s) == 'current' for s in scenes[1:])


def test_restart_requeues_a_carry(tmp_path):
    repo, story, scenes = book(tmp_path, 2)
    new_memory(repo, scenes[0])
    worker = RunCoordinator(repo)
    worker.recover_interrupted()
    (carry,) = carry_runs(repo, story.id)
    assert carry.state == 'queued'
    assert state(repo, story, scenes[1]) == 'pending'
