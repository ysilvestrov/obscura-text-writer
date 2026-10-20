import pytest
from storygen.domain import StoryCreate, SceneCreate
from storygen.storage.repository import Repository
from storygen.generation.dependencies import save_manual_prose
from storygen.evaluation.story_adapter import build_evaluation_case, EvaluationSettings, save_evaluation_settings
from storygen.evaluation.models import EvaluatorConfig


def test_revision_evaluation_uses_exact_draft_and_edit_refs(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Оцінка'));scene=repo.create_scene(story.id,SceneCreate(title='Один'))
    draft=repo.save_version(story.id,scene.id,'draft','Їй двадцять сім.',[]);repo.set_head(scene.id,'draft',draft.id,0)
    prose=save_manual_prose(repo,scene.id,'Їй тридцять сім.',1)
    case=build_evaluation_case(repo,story.id,scene.id,'edit_pair')
    assert case.mode=='revision' and case.target_ids==[draft.id,prose.id]
    assert case.documents[-1].text=='Їй тридцять сім.'


def test_partial_story_coverage_never_looks_like_full_pass(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Неповний'));scene=repo.create_scene(story.id,SceneCreate(title='Один'))
    save_manual_prose(repo,scene.id,'Початок',0)
    repo.create_scene(story.id,SceneCreate(title='Немає тексту'))
    case=build_evaluation_case(repo,story.id,None,'story')
    assert case.coverage.unchecked_links
    assert len(case.coverage.expected_scene_ids)==2


def test_incomplete_calibration_cannot_enable_pause_on_failure(tmp_path):
    repo=Repository(tmp_path);story=repo.create_story(StoryCreate(title='Профіль'))
    settings=EvaluationSettings(config=EvaluatorConfig(provider='codex_cli',max_input_chars=100000),policy='pause_on_failure')
    with pytest.raises(ValueError,match='калібрування'):save_evaluation_settings(repo,story.id,settings)
