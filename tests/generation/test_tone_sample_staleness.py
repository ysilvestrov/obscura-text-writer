"""STYLE-SAMPLE-001: a change of the voice sample alone keeps the stages blind to it fresh (brief, evaluation)."""
import pytest

from storygen.authoring.blueprints import update_story_profile
from storygen.domain import SceneCreate, StoryCreate
from storygen.generation.context import build_context
from storygen.generation.models import StyleProfile
from storygen.impact.planning import capture_target
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository
from storygen.storage.snapshots import compare_snapshot


def role():
    return RoleSettings(provider=ProviderSettings(model='fake'), context_tokens=262144, max_output_tokens=2048)


def generated(repo, scene_id, stage, text):
    ctx = build_context(repo, scene_id, stage, role())
    ref = repo.save_version(ctx.story_id, scene_id, stage, text, ctx.input_refs, dependency_snapshot=ctx.dependency_snapshot)
    repo.set_head(scene_id, stage, ref.id, repo.get_scene(scene_id).revision)
    return ref


def world(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Звучання'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена 1', beats='Анна чекає на пристані.'))
    update_story_profile(repo, story.id, StyleProfile(tone='стримано', tone_sample='Перший зразок.'), repo.get_story(story.id).revision)
    brief = generated(repo, scene.id, 'brief', 'Завдання сцени.')
    draft = generated(repo, scene.id, 'draft', 'Чернетка сцени.')
    return repo, story, scene, brief, draft


def change(repo, story, **fields):
    profile = StyleProfile(**{'tone': 'стримано', 'tone_sample': 'Перший зразок.', **fields})
    update_story_profile(repo, story.id, profile, repo.get_story(story.id).revision)


@pytest.mark.req('STYLE-SAMPLE-001')
def test_sample_change_keeps_brief_fresh(tmp_path):
    repo, story, scene, brief, draft = world(tmp_path)
    change(repo, story, tone_sample='Другий зразок.')
    assert repo.get_version(brief.id).stale is False
    assert not compare_snapshot(repo.context_view(story.id), brief.dependency_snapshot)


@pytest.mark.req('STYLE-SAMPLE-001')
def test_scene_with_only_a_brief_is_not_marked_for_review(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Лише завдання'))
    # The first style of a story marks every existing scene for review; set it before the scene exists.
    update_story_profile(repo, story.id, StyleProfile(tone='стримано', tone_sample='Перший зразок.'), repo.get_story(story.id).revision)
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена 1', beats='Анна чекає.'))
    brief = generated(repo, scene.id, 'brief', 'Завдання сцени.')
    assert repo.get_scene(scene.id).needs_review is False
    change(repo, repo.get_story(story.id), tone_sample='Другий зразок.')
    assert repo.get_version(brief.id).stale is False and repo.get_scene(scene.id).needs_review is False


@pytest.mark.req('STYLE-SAMPLE-001')
def test_sample_change_keeps_an_evaluation_fresh(tmp_path):
    from storygen.evaluation.story_adapter import build_evaluation_case
    from storygen.storage.snapshots import build_evaluation_snapshot
    repo, story, scene, brief, draft = world(tmp_path)
    # Prose that does not depend on the style (an old version without inputs): any prose written with the style
    # hears the sample, goes stale itself and takes its evaluation with it.
    prose = repo.save_version(story.id, scene.id, 'manual', 'Проза сцени.', [])
    repo.set_head(scene.id, 'prose', prose.id, repo.get_scene(scene.id).revision)
    case = build_evaluation_case(repo, story.id, scene.id, 'scene')
    snapshot = build_evaluation_snapshot(repo.context_view(story.id), scene.id, case, 'scene')
    evaluation = repo.save_version(story.id, scene.id, 'evaluation', '{}', [d.version for d in case.documents],
                                   dependency_snapshot=snapshot)
    change(repo, story, tone_sample='Другий зразок.')
    assert repo.get_version(evaluation.id).stale is False
    assert not [c for c in compare_snapshot(repo.context_view(story.id), snapshot) if c.selector and c.selector.field == 'style_version_id']
    change(repo, story, tone='гостро', tone_sample='Другий зразок.')
    assert repo.get_version(evaluation.id).stale is True


@pytest.mark.req('STYLE-SAMPLE-001')
def test_sample_change_stales_the_draft(tmp_path):
    repo, story, scene, brief, draft = world(tmp_path)
    change(repo, story, tone_sample='Другий зразок.')
    assert repo.get_version(draft.id).stale is True
    assert repo.get_scene(scene.id).needs_review is True
    assert compare_snapshot(repo.context_view(story.id), draft.dependency_snapshot)


@pytest.mark.req('STYLE-SAMPLE-001')
def test_other_style_change_still_stales_brief(tmp_path):
    repo, story, scene, brief, draft = world(tmp_path)
    change(repo, story, tone='гостро', tone_sample='Другий зразок.')
    assert repo.get_version(brief.id).stale is True
    assert compare_snapshot(repo.context_view(story.id), brief.dependency_snapshot)


@pytest.mark.req('STYLE-SAMPLE-001')
def test_brief_without_snapshot_goes_stale(tmp_path):
    repo, story, scene, brief, draft = world(tmp_path)
    old = repo.save_version(story.id, scene.id, 'brief', 'Старе завдання.', [repo.get_story(story.id).style_version_id])
    change(repo, story, tone_sample='Другий зразок.')
    assert repo.get_version(old.id).stale is True


