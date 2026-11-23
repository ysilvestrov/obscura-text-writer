"""VALID-LINKS: a context refused for a head whose incoming link does not hold names the scene and what to do."""
import json
import pytest
from storygen.generation.context import build_context
from storygen.memory.service import save_scene_memory
from storygen.providers.models import ProviderSettings, RoleSettings
from tests.storage.test_links import book, statuses


@pytest.mark.req('VALID-LINKS')
def test_stale_context_names_the_scene_and_action(tmp_path):
    # The previous memory changed by hand: the model brief of the next scene no longer holds by construction (Z1).
    repo, story, (first, second) = book(tmp_path, 2)
    journal = json.loads(repo.read_text(repo.get_scene(first.id).heads['memory']))
    journal['events'][-1]['text'] = 'Олена в бібліотеці вночі'
    save_scene_memory(repo, first.id, json.dumps(journal, ensure_ascii=False), repo.get_scene(first.id).revision)
    assert statuses(repo, story, second)['brief'] == ('unchecked', None, None)
    with pytest.raises(ValueError) as error:
        build_context(repo, second.id, 'draft', RoleSettings(provider=ProviderSettings(model='writer')))
    assert str(error.value) == ('Сцена «Сцена 1»: завдання не перевірено проти плану й пам’яті попередньої сцени — '
                                'затвердьте завдання або оновіть його')


@pytest.mark.req('VALID-LINKS')
def test_unchecked_author_prose_names_its_action_and_other_stale_text_stays(tmp_path):
    from storygen.generation.context import STALE_CONTEXT, stale_material_message
    from storygen.generation.dependencies import save_manual_prose
    repo, story, (scene,) = book(tmp_path)
    old_brief = repo.get_scene(scene.id).heads['brief']
    save_manual_prose(repo, scene.id, 'Олена увійшла до старої бібліотеки.', repo.get_scene(scene.id).revision)
    view = repo.context_view(story.id)
    prose = view.get_version(repo.get_scene(scene.id).heads['prose'])
    assert prose.stale
    assert stale_material_message(view, prose) == ('Сцена «Сцена 0»: прозу не перевірено — затвердьте відповідність '
                                                   'завданню або прийміть прозу як авторську')
    assert stale_material_message(view, view.get_version(old_brief).model_copy(update={'complete': False})) == STALE_CONTEXT
