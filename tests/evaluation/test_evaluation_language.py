"""STORY-LANGUAGE-S06: the evaluator is calibrated on Ukrainian only; English prose is not evaluated (#32)."""
import pytest

from storygen.domain import SceneCreate, StoryCreate
from storygen.evaluation.story_adapter import build_evaluation_case
from storygen.generation.dependencies import save_manual_prose
from storygen.storage.repository import Repository


def story_with(tmp_path, language, prose_language=None):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Tide', language=language))
    scene = repo.create_scene(story.id, SceneCreate(title='One', prose_language=prose_language))
    draft = repo.save_version(story.id, scene.id, 'draft', 'Draft.', [])
    repo.set_head(scene.id, 'draft', draft.id, repo.get_scene(scene.id).revision)
    save_manual_prose(repo, scene.id, 'Prose.', repo.get_scene(scene.id).revision)
    return repo, story, scene


@pytest.mark.req('STORY-LANGUAGE')
@pytest.mark.parametrize('language,prose_language', [('en', None), ('uk', 'en')])
def test_english_scene_evaluation_rejected(tmp_path, language, prose_language):
    repo, story, scene = story_with(tmp_path, language, prose_language)
    for mode in ['scene', 'edit_pair']:
        with pytest.raises(ValueError, match='англійськ'):
            build_evaluation_case(repo, story.id, scene.id, mode)
    with pytest.raises(ValueError, match='англійськ'):
        build_evaluation_case(repo, story.id, None, 'story')


@pytest.mark.req('STORY-LANGUAGE')
def test_ukrainian_scene_of_english_story_evaluated(tmp_path):
    repo, story, scene = story_with(tmp_path, 'en', 'uk')
    assert build_evaluation_case(repo, story.id, scene.id, 'edit_pair').mode == 'revision'


@pytest.mark.req('STORY-LANGUAGE')
def test_worker_skips_edit_pair_for_english_scene(tmp_path, monkeypatch):
    from storygen.evaluation.models import EvaluatorConfig
    from storygen.evaluation.story_adapter import EvaluationSettings
    from storygen.generation.worker import RunCoordinator
    from storygen.run_models import RunRequest
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Tide', language='uk'))
    first = repo.create_scene(story.id, SceneCreate(title='One'))
    repo.create_scene(story.id, SceneCreate(title='Two', prose_language='en'))
    settings = EvaluationSettings(config=EvaluatorConfig(provider='codex_cli', max_input_chars=100000), policy='report')
    repo.write_evaluator_settings(story.id, settings.model_dump())
    # Readiness (roles, budget) is not what this test is about: only which tasks the run plans.
    monkeypatch.setattr('storygen.generation.readiness.preview', lambda repo, request: {'ready': True})
    worker = RunCoordinator(repo, gateway_factory=lambda _: None)
    run = worker.enqueue(RunRequest(story_id=story.id, mode='remaining', scene_id=first.id), 'language-run')
    evaluated = [task['scene_id'] for task in run.tasks if task['stage'] == 'evaluate']
    assert evaluated == [first.id]
    from storygen.evaluation.story_adapter import ENGLISH_NOT_EVALUATED
    skipped = [e.data for e in worker.list_events(run.id) if e.type == 'evaluation_skipped']
    assert skipped == [{'scene_id': repo.list_scenes(story.id)[1].id, 'reason': ENGLISH_NOT_EVALUATED}]


@pytest.mark.req('STORY-LANGUAGE')
def test_scene_case_with_english_preceding_prose_rejected(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Tide', language='uk'))
    first = repo.create_scene(story.id, SceneCreate(title='One', prose_language='en'))
    save_manual_prose(repo, first.id, 'English prose.', repo.get_scene(first.id).revision)
    second = repo.create_scene(story.id, SceneCreate(title='Two'))
    draft = repo.save_version(story.id, second.id, 'draft', 'Чернетка.', [])
    repo.set_head(second.id, 'draft', draft.id, repo.get_scene(second.id).revision)
    save_manual_prose(repo, second.id, 'Проза.', repo.get_scene(second.id).revision)
    with pytest.raises(ValueError, match='англійськ'):
        build_evaluation_case(repo, story.id, second.id, 'edit_pair')


def blocked_evaluator(repo, story):
    from storygen.evaluation.blocks import block_evaluator
    from storygen.evaluation.models import EvaluatorConfig, FailureDetail
    from storygen.evaluation.story_adapter import EvaluationSettings
    config = EvaluatorConfig(provider='local', model='judge', max_input_chars=100000)
    # Written directly: pause_on_failure normally needs a calibrated profile, which is not what this test is about.
    repo.write_evaluator_settings(story.id, EvaluationSettings(config=config, policy='pause_on_failure').model_dump())
    block_evaluator(repo, story.id, config, FailureDetail(category='refusal_unknown', message='Refusal'), None, None)


@pytest.mark.req('STORY-LANGUAGE')
def test_english_run_not_blocked_by_evaluator_it_will_not_call(tmp_path):
    from storygen.authoring.blueprints import save_role_settings
    from storygen.generation.readiness import preview
    from storygen.providers.models import ProviderSettings, RoleSettings
    from storygen.run_models import RunRequest
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Tide', language='en'))
    scene = repo.create_scene(story.id, SceneCreate(title='One', beats='Anna waits.'))
    for name in ['planner', 'writer', 'editor', 'memory']:
        save_role_settings(repo, story.id, name, RoleSettings(provider=ProviderSettings(model='fake'), context_tokens=262144),
                           repo.get_story(story.id).revision)
    blocked_evaluator(repo, story)
    result = preview(repo, RunRequest(story_id=story.id, scene_id=scene.id, mode='scene'))
    assert result['ready'], result['reason']
    assert result['evaluator'] is None and not result.get('warning')


@pytest.mark.req('STORY-LANGUAGE')
def test_scene_switched_to_english_after_queueing_skips_evaluation(tmp_path):
    from storygen.domain import new_id
    from storygen.evaluation.models import EvaluatorConfig
    from storygen.evaluation.story_adapter import ENGLISH_NOT_EVALUATED, EvaluationSettings
    from storygen.generation.worker import RunCoordinator
    from storygen.run_models import Run, RunRequest
    repo, story, scene = story_with(tmp_path, 'uk')
    repo.write_evaluator_settings(story.id, EvaluationSettings(config=EvaluatorConfig(provider='codex_cli', max_input_chars=100000), policy='report').model_dump())
    run = Run(id=new_id(), story_id=story.id, request_id=new_id(), request=RunRequest(story_id=story.id, mode='scene', scene_id=scene.id),
              tasks=[{'scene_id': scene.id, 'stage': 'evaluate', 'evaluation_mode': 'edit_pair'}], state='running')
    run, _ = repo.enqueue_run(run)
    repo.update_scene_metadata(scene.id, {'prose_language': 'en'}, repo.get_scene(scene.id).revision)
    worker = RunCoordinator(repo, gateway_factory=lambda _: None)
    worker._evaluate(worker.get_run(run.id))
    assert worker.get_run(run.id).cursor == 1
    events = [e for e in worker.list_events(run.id) if e.type == 'evaluation_skipped']
    assert events and events[-1].data['reason'] == ENGLISH_NOT_EVALUATED


@pytest.mark.req('STORY-LANGUAGE')
def test_story_evaluation_ignores_english_scene_without_prose(tmp_path):
    # The story case reads prose only: an English scene that has none is not evaluated, so it does not block (S08).
    repo, story, scene = story_with(tmp_path, 'uk')
    repo.create_scene(story.id, SceneCreate(title='Two', prose_language='en'))
    assert build_evaluation_case(repo, story.id, None, 'story').mode == 'story'
