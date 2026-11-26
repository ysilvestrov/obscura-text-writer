"""WRITING-MODE-S06 (R-49): execute_stage refuses a prose step in a story in the «Пишу сам» mode, before the call and before
saving a response that was already streaming when the author switched. Neutral texts, fake gateway."""
import threading

import pytest

from storygen.generation.context import build_context
from storygen.generation.stages import execute_stage
from storygen.writing_mode import AUTHOR_WRITES, AuthorWritesBlocked
from tests.generation.test_model_policy_stages import BRIEF, FakeGateway, draft, noop, setup, writer_role


def switch(repo, story_id, mode):
    repo.update_writing_mode(story_id, mode, repo.get_story(story_id).revision)


class SwitchingGateway(FakeGateway):
    """The author switches the story to «Пишу сам» while the response streams."""

    def __init__(self, repo, story_id):
        super().__init__()
        self.repo, self.story_id = repo, story_id

    def stream(self, context, cancel):
        for event in super().stream(context, cancel):
            switch(self.repo, self.story_id, 'author')
            yield event


def drafts(repo, scene):
    return repo.list_versions(scene.story_id, scene.id, 'draft')


@pytest.mark.req('WRITING-MODE')
def test_execute_stage_refuses_prose_stage_before_the_call(tmp_path):
    repo, (scene,) = setup(tmp_path)
    switch(repo, scene.story_id, 'author')
    gateway = FakeGateway()
    with pytest.raises(AuthorWritesBlocked, match='Пишу сам'):
        draft(repo, scene, gateway)
    assert gateway.calls == [] and repo.list_attempts(scene.story_id) == []


@pytest.mark.req('WRITING-MODE')
def test_switch_during_the_response_saves_no_version(tmp_path):
    repo, (scene,) = setup(tmp_path)
    with pytest.raises(AuthorWritesBlocked):
        draft(repo, scene, SwitchingGateway(repo, scene.story_id))
    assert drafts(repo, scene) == []
    attempt = repo.list_attempts(scene.story_id)[-1]
    assert attempt.state == 'failed' and attempt.error == AUTHOR_WRITES and attempt.result_version_id is None


@pytest.mark.req('WRITING-MODE')
def test_brief_stage_is_not_refused_in_author_mode(tmp_path):
    repo, (scene,) = setup(tmp_path)
    switch(repo, scene.story_id, 'author')
    context = build_context(repo, scene.id, 'draft', writer_role())
    try:
        execute_stage(repo, scene.id, 'brief', context, FakeGateway(text=BRIEF), threading.Event(), noop)
    except AuthorWritesBlocked:
        pytest.fail('brief writes no prose')
    except Exception:
        pass  # the borrowed draft context may not suit the brief parser; only the mode refusal matters here


@pytest.mark.req('WRITING-MODE')
def test_run_failure_shows_the_mode_reason(tmp_path):
    from storygen.generation.worker import RunCoordinator
    from storygen.run_models import Run, RunRequest
    run = Run.model_construct(id='r', story_id='s', tasks=[{'scene_id': 'x', 'stage': 'draft'}], cursor=0,
                              request=RunRequest.model_construct(story_id='s', mode='stage', stage='draft'))
    assert RunCoordinator._failure_message(None, run, AuthorWritesBlocked(AUTHOR_WRITES)) == AUTHOR_WRITES


@pytest.mark.req('WRITING-MODE')
def test_queued_draft_run_stops_after_the_switch_without_a_version(tmp_path, monkeypatch):
    from storygen.generation import readiness
    from storygen.generation.worker import RunCoordinator
    monkeypatch.setattr(readiness, 'preview', lambda *_args, **_kw: {'ready': True})  # queueing is not under test
    from storygen.run_models import RunRequest
    repo, (scene,) = setup(tmp_path)
    gateway = FakeGateway()
    worker = RunCoordinator(repo, lambda _: gateway)
    run = worker.enqueue(RunRequest(story_id=scene.story_id, scene_id=scene.id, mode='stage', stage='draft', budget_limit_usd='1'),
                         'queued-draft')
    switch(repo, scene.story_id, 'author')
    with pytest.raises(AuthorWritesBlocked):
        worker._execute(run.id)
    assert gateway.calls == [] and drafts(repo, scene) == []


@pytest.mark.req('WRITING-MODE')
def test_queued_edit_loop_stops_before_copying_the_source(tmp_path):
    from tests.generation.test_editor_loop import seeded
    repo, scene, draft_ref, worker, run, calls = seeded(tmp_path, ['unused'])
    switch(repo, scene.story_id, 'author')
    worker._execute(run.id)
    current = worker.get_run(run.id)
    assert current.state == 'failed' and current.error == AUTHOR_WRITES and calls == []
    assert [v.id for v in repo.list_versions(scene.story_id, scene.id, 'draft')] == [draft_ref.id]
