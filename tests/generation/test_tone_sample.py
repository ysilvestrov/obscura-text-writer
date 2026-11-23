"""STYLE-SAMPLE-001: the voice sample of a story goes only to the prose stages, as its own section."""
import pytest
from pydantic import ValidationError

from storygen.authoring.blueprints import update_story_profile
from storygen.domain import SceneCreate, StoryCreate
from storygen.evaluation.story_adapter import build_evaluation_case
from storygen.generation.context import build_context
from storygen.generation.dependencies import save_manual_prose
from storygen.generation.models import StyleProfile
from storygen.providers.models import ProviderSettings, RoleSettings
from storygen.storage.repository import Repository
from tests.link_helpers import approve_links

SAMPLE = 'Вітер ішов низько. Ліхтар гойднувся раз, другий — і завмер.'
LABEL = 'ЗРАЗОК ЗВУЧАННЯ — НЕ СЮЖЕТ: ПЕРЕЙМИ РИТМ, ЛЕКСИКУ Й БУДОВУ РЕЧЕНЬ; НЕ БЕРИ ПОДІЙ, ІМЕН ЧИ СВІТУ'
EN_LABEL = 'VOICE SAMPLE — NOT PLOT: TAKE ITS RHYTHM, VOCABULARY AND SENTENCE STRUCTURE; NOT ITS EVENTS, NAMES OR WORLD'


def role(**kwargs):
    return RoleSettings(provider=ProviderSettings(model='fake'), context_tokens=262144, max_output_tokens=2048, **kwargs)


def world(tmp_path, sample=SAMPLE, language='uk'):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Звучання', language=language))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена 1', beats='Анна чекає на пристані.'))
    update_story_profile(repo, story.id, StyleProfile(tone='стримано', tone_sample=sample), repo.get_story(story.id).revision)
    brief = repo.save_version(story.id, scene.id, 'brief', 'Завдання сцени.', [])
    repo.set_head(scene.id, 'brief', brief.id, repo.get_scene(scene.id).revision)
    draft = repo.save_version(story.id, scene.id, 'draft', 'Чернетка сцени.', [])
    repo.set_head(scene.id, 'draft', draft.id, repo.get_scene(scene.id).revision)
    approve_links(repo, story.id)
    return repo, repo.get_story(story.id), repo.get_scene(scene.id), draft


@pytest.mark.req('STYLE-SAMPLE-001')
@pytest.mark.parametrize('stage', ['draft', 'rewrite', 'edit'])
def test_draft_rewrite_and_full_edit_get_the_sample_section(tmp_path, stage):
    repo, story, scene, draft = world(tmp_path)
    ctx = build_context(repo, scene.id, stage, role(), editor_source_id=draft.id if stage == 'rewrite' else None)
    assert ctx.user_text.count(SAMPLE) == 1 and ctx.user_text.count(LABEL + '\n' + SAMPLE) == 1
    assert '"tone_sample"' not in ctx.user_text and 'стримано' in ctx.user_text
    assert ctx.user_text.index(LABEL) > ctx.user_text.index(f'[version_id={story.style_version_id}]')


@pytest.mark.req('STYLE-SAMPLE-001')
def test_english_story_gets_the_english_label(tmp_path):
    repo, story, scene, draft = world(tmp_path, sample='The wind ran low.', language='en')
    ctx = build_context(repo, scene.id, 'draft', role())
    assert ctx.user_text.count(EN_LABEL + '\nThe wind ran low.') == 1 and LABEL not in ctx.user_text


@pytest.mark.req('STYLE-SAMPLE-001')
@pytest.mark.parametrize('stage,settings', [('brief', {}), ('memory', {}), ('edit', {'edit_mode': 'patches'}), ('edit', {'edit_mode': 'diff'})])
def test_brief_memory_and_patches_do_not_get_the_sample(tmp_path, stage, settings):
    repo, story, scene, draft = world(tmp_path)
    if stage == 'memory':
        save_manual_prose(repo, scene.id, 'Проза сцени.', scene.revision)
    ctx = build_context(repo, scene.id, stage, role(**settings))
    assert SAMPLE not in ctx.user_text and LABEL not in ctx.user_text and '"tone_sample"' not in ctx.user_text


@pytest.mark.req('STYLE-SAMPLE-001')
def test_evaluator_style_document_has_no_sample(tmp_path):
    repo, story, scene, draft = world(tmp_path)
    save_manual_prose(repo, scene.id, 'Проза сцени.', scene.revision)
    case = build_evaluation_case(repo, story.id, scene.id, 'scene')
    style = next(d for d in case.documents if d.id == story.style_version_id)
    assert SAMPLE not in style.text and 'tone_sample' not in style.text and 'стримано' in style.text


@pytest.mark.req('STYLE-SAMPLE-001')
def test_story_without_sample_keeps_the_same_request(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Без зразка'))
    scene = repo.create_scene(story.id, SceneCreate(title='Сцена 1', beats='Анна чекає.'))
    old = '{"ending_goal":"","genre":"","tone":"стримано","point_of_view":"третя особа","tense":"минулий","rules":"","previous_tail_chars":1200}'
    style = repo.save_version(story.id, None, 'style', old, [])
    repo.publish_writing_settings(story.id, repo.get_story(story.id).revision, None, style.id)
    brief = repo.save_version(story.id, scene.id, 'brief', 'Завдання сцени.', [])
    repo.set_head(scene.id, 'brief', brief.id, repo.get_scene(scene.id).revision)
    approve_links(repo, story.id)
    ctx = build_context(repo, scene.id, 'draft', role())
    assert old in ctx.user_text and LABEL not in ctx.user_text


@pytest.mark.req('STYLE-SAMPLE-001')
def test_sample_longer_than_3000_is_rejected():
    StyleProfile(tone_sample='я' * 3000)
    with pytest.raises(ValidationError):
        StyleProfile(tone_sample='я' * 3001)


@pytest.mark.req('STYLE-SAMPLE-001')
def test_writing_context_has_sample_only_when_set(tmp_path):
    from storygen.application.writing_context import context_fingerprint, writing_context
    repo, story, scene, draft = world(tmp_path, sample='')
    before = context_fingerprint(repo, scene.id)
    assert 'tone_sample' not in writing_context(repo, scene.id)
    update_story_profile(repo, story.id, StyleProfile(tone='стримано', tone_sample=SAMPLE), repo.get_story(story.id).revision)
    assert writing_context(repo, scene.id)['tone_sample'] == SAMPLE
    assert context_fingerprint(repo, scene.id) != before
