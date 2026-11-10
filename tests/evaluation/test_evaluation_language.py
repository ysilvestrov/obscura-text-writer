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
