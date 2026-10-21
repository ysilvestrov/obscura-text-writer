from concurrent.futures import ThreadPoolExecutor

from storygen.domain import StoryCreate, new_id
from storygen.run_models import Run, RunRequest
from storygen.storage.repository import Repository
from storygen.generation.worker import RunCoordinator


def test_event_sequences_are_unique_under_two_writers(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Події'))
    request = RunRequest(story_id=story.id, mode='prepare')
    run, _ = repo.enqueue_run(Run(id=new_id(), story_id=story.id, request_id='events', request=request, tasks=[]))
    def write(writer):
        for index in range(20):
            repo.append_run_event(run.id, 'test', {'writer': writer, 'index': index})
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(write, [1, 2]))
    events = repo.list_run_events(run.id)
    assert [e.seq for e in events] == list(range(1, 41))
    assert [e.seq for e in repo.list_run_events(run.id, 20)] == list(range(21, 41))
    assert {(e.data['writer'], e.data['index']) for e in events} == {(w, i) for w in [1, 2] for i in range(20)}


def test_enqueue_is_idempotent_before_changed_preflight(tmp_path, monkeypatch):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Черга'))
    request = RunRequest(story_id=story.id, mode='prepare')
    run = Run(id=new_id(), story_id=story.id, request_id='same', request=request, tasks=[])
    stored, created = repo.enqueue_run(run)
    assert created
    def fail(*args):
        raise AssertionError('Повтор не повинен запускати preflight')
    monkeypatch.setattr('storygen.generation.readiness.preview', fail)
    coordinator = RunCoordinator(repo)
    assert coordinator.enqueue(request, 'same') == stored
    assert len(repo.list_runs()) == 1


def test_evaluation_publication_detects_concurrent_change(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Оцінювання'))
    source = repo.save_version(story.id, None, 'canon', 'Джерело', [])
    report = repo.save_version(story.id, None, 'evaluation', '{}', [source.id])
    repo.write_role_settings(story.id, {}, story.revision)
    published = repo.publish_evaluation(report.id, story.revision, [source.id])
    assert published.stale
    assert repo.get_version(report.id).stale
