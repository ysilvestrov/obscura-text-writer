"""MODEL-RETIREMENT-S02: a run warns about a retiring model on every execution path and keeps the other warnings."""
from datetime import date

import pytest

from storygen.providers.models import ModelRetirement
from tests.generation import test_editor_loop as loop_tests
from tests.generation import test_editor_workflow as workflow_tests

RETIRING = ModelRetirement(date=date(2026, 12, 1), replacement='glm-test')


def retiring(worker, models):
    """Gateways of the given role models report the provider's retirement notice, like OpenAIGenerationGateway."""
    original = worker.gateway_factory
    def factory(provider):
        gateway = original(provider)
        gateway.retirement = RETIRING if provider.model in models else None
        return gateway
    worker.gateway_factory = factory


def lines(warning):
    return (warning or '').splitlines()


@pytest.mark.req('MODEL-RETIREMENT')
def test_edit_loop_warns_about_the_editor_model(tmp_path):
    repo, scene, draft, worker, run, calls = loop_tests.seeded(tmp_path, ['{"edits":[]}'])
    retiring(worker, {'synthetic'})
    worker._execute(run.id)
    warning = worker.get_run(run.id).warning
    assert 'Провайдер прибирає модель «synthetic» 01.12.2026; заміна: «glm-test». Змініть модель у налаштуваннях ролі.' in lines(warning)
    assert any(line.startswith('Редактор не запропонував нових змін') for line in lines(warning))


@pytest.mark.req('MODEL-RETIREMENT')
def test_scene_pipeline_keeps_the_writer_warning_after_the_editor_finishes(tmp_path):
    repo, scenes, worker, run, calls = workflow_tests.setup_workflow(tmp_path)
    retiring(worker, {'writer'})
    worker._execute(run.id)
    current = worker.get_run(run.id)
    assert current.state == 'needs_review', current.error
    assert 'Провайдер прибирає модель «writer» 01.12.2026; заміна: «glm-test». Змініть модель у налаштуваннях ролі.' in lines(current.warning)
    assert sum('Спроб:' in line for line in lines(current.warning)) == 1


@pytest.mark.req('MODEL-RETIREMENT')
def test_the_next_scene_replaces_the_stop_line_and_keeps_the_retirement_warning(tmp_path):
    from storygen.generation.copyedit_review import copyedit_preview, select_copyedits
    repo, scenes, worker, run, calls = workflow_tests.setup_workflow(tmp_path)
    retiring(worker, {'writer'})
    for scene in scenes:
        worker._execute(run.id)
        current = worker.get_run(run.id)
        checkpoint = current.editor_loops[str(current.cursor)]
        preview = copyedit_preview(repo, scene.id, checkpoint['proposal_attempt_id'])
        result = select_copyedits(repo, scene.id, checkpoint['proposal_attempt_id'], list(range(len(preview['edits']))), preview['expected_revision'], preview['proposal_fingerprint'])
        worker.continue_after_acceptance(run.id, result['version'].id, current.cursor, result['scene'].revision)
    warning = worker.get_run(run.id).warning
    assert sum(line.startswith(('Підсумкові правки прийнято.', 'Редактор', 'Досягнуто', 'Виявлено')) for line in lines(warning)) == 1
    assert sum(line.startswith('Провайдер прибирає модель «writer»') for line in lines(warning)) == 1


@pytest.mark.req('MODEL-RETIREMENT')
def test_a_model_without_a_notice_adds_no_warning(tmp_path):
    repo, scene, draft, worker, run, calls = loop_tests.seeded(tmp_path, ['{"edits":[]}'])
    retiring(worker, set())
    worker._execute(run.id)
    assert not any(line.startswith('Провайдер прибирає') for line in lines(worker.get_run(run.id).warning))


@pytest.mark.req('MODEL-RETIREMENT')
def test_book_review_call_carries_the_warning(monkeypatch):
    import threading
    from types import SimpleNamespace
    from storygen.generation import stages
    from storygen.review import runner as review_runner
    from storygen.run_models import Run, RunRequest
    run = Run(id='r1', request_id='q', request=RunRequest(story_id='s', mode='impact'), story_id='s', state='running', tasks=[], impact={'phase': 'review'})
    saved, events = {'r1': run}, []
    worker = SimpleNamespace(repo=None, condition=threading.RLock(), cancel_event=threading.Event(),
        gateway_factory=lambda provider: SimpleNamespace(retirement=RETIRING), get_run=lambda id: saved[id],
        _save=lambda current: saved.__setitem__(current.id, current), event=lambda *args: events.append(args))
    attempt = SimpleNamespace(id='a', state='completed', usage={}, finish_reason='stop', error=None,
        context={'model_retirement_warnings': ['Провайдер прибирає модель «local-review» 01.12.2026; заміна: «glm-test». Змініть модель у налаштуваннях ролі.']})
    monkeypatch.setattr(stages, 'execute_stage', lambda *args, **kwargs: attempt)
    context = SimpleNamespace(scene_id='c', estimated_tokens=1, settings=SimpleNamespace(provider=SimpleNamespace(provider='local', model='local-review')))
    assert review_runner.call(worker, run, 'review_part', context) is attempt
    assert 'Провайдер прибирає модель «local-review»' in saved['r1'].warning
    assert any(event[1] == 'context_warning' for event in events)
