"""EDITOR-NAME-SPELLING: the editor request names the scene cast with the spelling to keep, in every edit mode."""
import pytest

from storygen.generation import editor_loop
from storygen.generation.context import build_context
from storygen.providers.models import ProviderSettings, RoleSettings
from tests.generation.test_character_names_context import remember, setup

RULE = ('НАПИСАННЯ ІМЕН\nПиши імена персонажів точно так, як подано нижче: тими самими літерами й тим самим алфавітом. '
        'Не транслітеруй, не перекладай і не замінюй їх іншими формами. Відмінюй їх так, як це вже робить чернетка.')
RULE_EN = ('NAME SPELLING\nWrite the character names exactly as given below: the same letters in the same alphabet. '
           'Do not transliterate, translate or replace them with other forms. Inflect them the way the draft already does.')


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
    assert RULE_EN in text
    assert '— Хазяїн (also: Бос)' in text


@pytest.mark.req('EDITOR-NAME-SPELLING')
@pytest.mark.parametrize('mode', ['patches', 'diff'])
def test_user_text_stays_the_editor_material(tmp_path, mode):
    from storygen.evidence import render_fragments
    repo, scenes = setup(tmp_path)
    scene, draft = with_draft(repo, scenes[0])
    expected = 'Юлія чекає біля воріт.' if mode == 'diff' else render_fragments('Юлія чекає біля воріт.')
    for context in (build_context(repo, scene.id, 'edit', role(mode)), editor_loop.context(repo, scene.id, role(mode), draft.id)):
        assert 'НАПИСАННЯ ІМЕН' not in context.user_text
        assert context.user_text.endswith(expected)
        if mode == 'diff':
            # The model returns the whole text: the request sends the draft alone, so the block cannot echo.
            assert context.user_text == expected


@pytest.mark.req('EDITOR-NAME-SPELLING')
@pytest.mark.parametrize('flag', [{'stale': True}, {'complete': False}])
def test_stale_or_incomplete_cards_give_no_block_and_no_error(tmp_path, flag):
    repo, scenes = setup(tmp_path)
    scene, draft = with_draft(repo, scenes[0])
    cards = repo.get_version(repo.get_story(scene.story_id).characters_version_id)
    with repo.db.connection() as db:
        db.execute('UPDATE versions SET payload=? WHERE id=?', (cards.model_copy(update=flag).model_dump_json(), cards.id))
    assert repo.get_version(cards.id).model_dump(include=set(flag)) == flag
    for mode in ('patches', 'diff'):
        for context in (build_context(repo, scene.id, 'edit', role(mode)), editor_loop.context(repo, scene.id, role(mode), draft.id)):
            assert 'НАПИСАННЯ ІМЕН' not in context.system_text


@pytest.mark.req('EDITOR-NAME-SPELLING')
def test_no_block_without_cards(tmp_path):
    from storygen.domain import SceneCreate, StoryCreate
    repo = __import__('storygen.storage.repository', fromlist=['Repository']).Repository(tmp_path)
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
