"""EDITOR-NAME-SPELLING: the editor request names the scene cast with the spelling to keep, in every edit mode."""
import pytest

from storygen.generation import editor_loop
from storygen.generation.context import build_context
from storygen.providers.models import ProviderSettings, RoleSettings
from tests.generation.test_character_names_context import remember, setup

RULE = 'Пиши імена персонажів точно так, як подано нижче'


def role(mode):
    return RoleSettings(provider=ProviderSettings(model='fake'), edit_mode=mode, context_tokens=262144)


def with_draft(repo, scene):
    brief = repo.save_version(scene.story_id, scene.id, 'brief', '{"objective":"Юлія чекає","beats":["Чекає"],"constraints":[],"proposed_changes":[]}', [])
    repo.set_head(scene.id, 'brief', brief.id, repo.get_scene(scene.id).revision)
    draft = repo.save_version(scene.story_id, scene.id, 'draft', 'Юлія чекає біля воріт.', [brief.id])
    repo.set_head(scene.id, 'draft', draft.id, repo.get_scene(scene.id).revision)
    return repo.get_scene(scene.id), draft


def section(text):
    start = text.index('НАПИСАННЯ ІМЕН')
    return text[start:].split('\n\n')[0]


@pytest.mark.req('EDITOR-NAME-SPELLING')
@pytest.mark.parametrize('mode', ['prose', 'patches', 'diff'])
def test_every_edit_mode_names_the_cast_available_in_the_scene(tmp_path, mode):
    repo, scenes = setup(tmp_path)
    scene, draft = with_draft(repo, scenes[0])
    for context in (build_context(repo, scene.id, 'edit', role(mode)), editor_loop.context(repo, scene.id, role(mode), draft.id)):
        block = section(context.system_text)
        assert RULE in block
        assert '— Юлія\n— Хазяїн (також: Бос)' in block
        # A name that becomes available only in a later scene is not revealed earlier.
        assert 'Джон' not in block
        # The diff request still sends the draft alone: the model returns the whole text, and the block must not echo.
        if mode == 'diff':
            assert context.user_text == 'Юлія чекає біля воріт.'


@pytest.mark.req('EDITOR-NAME-SPELLING')
def test_name_current_in_a_later_scene_comes_first(tmp_path):
    repo, scenes = setup(tmp_path)
    scenes = remember(repo, scenes, 0)
    scene, _ = with_draft(repo, scenes[1])
    assert '— Джон (також: Хазяїн, Бос)' in section(build_context(repo, scene.id, 'edit', role('patches')).system_text)


@pytest.mark.req('EDITOR-NAME-SPELLING')
def test_english_story_label_and_rule(tmp_path):
    repo, scenes = setup(tmp_path, language='en')
    scene, _ = with_draft(repo, scenes[0])
    text = build_context(repo, scene.id, 'edit', role('patches')).system_text
    assert 'NAME SPELLING\nWrite the character names exactly as given below' in text
    assert '— Хазяїн (also: Бос)' in text


@pytest.mark.req('EDITOR-NAME-SPELLING')
def test_no_block_and_no_error_without_fresh_cards(tmp_path):
    from types import SimpleNamespace
    from storygen.characters.context import name_spelling_section
    from storygen.domain import SceneCreate, StoryCreate
    repo, scenes = setup(tmp_path)
    story = repo.get_story(scenes[0].story_id)
    # Stale or incomplete cards give no block instead of an error.
    for flags in ({'stale': True, 'complete': True}, {'stale': False, 'complete': False}):
        view = SimpleNamespace(get_version=lambda _id, flags=flags: SimpleNamespace(id=_id, **flags))
        assert name_spelling_section(view, story, scenes[0]) == ''
    other = repo.create_story(StoryCreate(title='Без карток'))
    lone = repo.create_scene(other.id, SceneCreate(title='Сцена', beats='Тиша.'))
    lone, lone_draft = with_draft(repo, lone)
    assert 'НАПИСАННЯ ІМЕН' not in editor_loop.context(repo, lone.id, role('diff'), lone_draft.id).system_text


@pytest.mark.req('EDITOR-NAME-SPELLING')
def test_block_adds_no_refs(tmp_path):
    repo, scenes = setup(tmp_path)
    scene, draft = with_draft(repo, scenes[0])
    story = repo.get_story(scene.story_id)
    assert story.characters_version_id not in editor_loop.context(repo, scene.id, role('patches'), draft.id).input_refs


@pytest.mark.req('EDITOR-NAME-SPELLING')
def test_custom_editor_prompt_keeps_the_block(tmp_path):
    repo, scenes = setup(tmp_path)
    scene, _ = with_draft(repo, scenes[0])
    from storygen.domain import PromptContract
    prompt = repo.save_version(scene.story_id, None, 'prompt', 'Власний промпт редактора.', [],
                               prompt_contract=PromptContract(stage='edit', mode='prose', schema_version=1))
    settings = role('prose').model_copy(update={'prompt_version_id': prompt.id})
    context = build_context(repo, scene.id, 'edit', settings)
    assert context.system_text.startswith('Власний промпт редактора.')
    assert RULE in context.system_text
