"""R-52 (MCP-BRIDGE): the chat reads and changes character cards with a preview and the author's consent."""
import pytest

pytest.importorskip('mcp')
from storygen.domain import StoryCreate  # noqa: E402
from storygen.mcp.bridge import build_server  # noqa: E402
from storygen.mcp.character_changes import ChangeError, apply_changes, describe  # noqa: E402

from tests.mcp.test_bridge import call, obscura, text  # noqa: E402

PLAN = '# План\n\nСцена 1: Лист\nХто бере участь: Анна.\nАнна знаходить лист.\n'
CHARACTERS = '# Персонажі\n\n## Анна\nДоглядачка маяка.\n\n## Петро\nРибалка.\nЗнайомий з: Анна\n'


def story_with_cards(tmp_path):
    app, http = obscura(tmp_path)
    story = app.state.repo.create_story(StoryCreate(title='Маяк'))
    server = build_server(http)
    result = call(server, 'import_plan_and_characters', {'story_id': story.id, 'plan_markdown': PLAN, 'characters_markdown': CHARACTERS})
    assert not result.is_error, text(result)
    return app, http, server, story


def read(server, story):
    result = call(server, 'get_characters', {'story_id': story.id})
    assert not result.is_error, text(result)
    return result.structured_content


def card(cards, name):
    return next(c for c in cards if c['name'] == name)


@pytest.mark.req('MCP-BRIDGE')
def test_rename_preview_writes_nothing_and_confirm_keeps_the_old_name(tmp_path):
    app, http, server, story = story_with_cards(tmp_path)
    data = read(server, story)
    anna = card(data['cards'], 'Анна')
    args = {'story_id': story.id, 'expected_revision': data['revision'],
            'changes': [{'op': 'rename', 'character_id': anna['id'], 'name': 'Ганна'}]}
    preview = call(server, 'update_characters', args).structured_content
    assert preview['saved'] is False and preview['unresolved_scenes'] == []
    assert preview['changes'][0]['name_was'] == 'Анна' and preview['changes'][0]['entries_added'] == ["Інше ім'я: Анна"]
    assert read(server, story)['revision'] == data['revision']
    saved = call(server, 'update_characters', args | {'confirm': True})
    assert not saved.is_error, text(saved)
    after = card(saved.structured_content['cards'], 'Ганна')
    marker = after['entries'][-1]
    assert after['id'] == anna['id']
    assert (marker['text'], marker['availability'], marker['origin']) == ("Інше ім'я: Анна", 'timeless', 'author')
    assert after['entries'][0]['origin'] == 'imported'  # untouched entries keep their origin and sources


@pytest.mark.req('MCP-BRIDGE')
def test_removing_a_name_a_plan_still_uses_is_refused_even_with_confirm(tmp_path):
    app, http, server, story = story_with_cards(tmp_path)
    data = read(server, story)
    anna = card(data['cards'], 'Анна')
    args = {'story_id': story.id, 'expected_revision': data['revision'], 'confirm': True,
            'changes': [{'op': 'rename', 'character_id': anna['id'], 'name': 'Ганна', 'keep_old_name': False}]}
    result = call(server, 'update_characters', args)
    assert result.is_error and 'не розпізнаються' in text(result) and 'Лист' in text(result)
    preview = call(server, 'update_characters', args | {'confirm': False}).structured_content
    places = {item.get('scene_id') or item.get('character_id') for item in preview['unresolved_scenes']}
    scene_id = app.state.repo.context_view(story.id).list_scenes(story.id)[0].id
    assert places == {scene_id, card(data['cards'], 'Петро')['id']}  # the plan cast and the «Знайомий з:» line
    assert read(server, story)['revision'] == data['revision']


@pytest.mark.req('MCP-BRIDGE')
def test_stale_revision_and_unknown_ids_are_refused_without_a_write(tmp_path):
    app, http, server, story = story_with_cards(tmp_path)
    data = read(server, story)
    stale = call(server, 'update_characters', {'story_id': story.id, 'expected_revision': data['revision'] - 1,
                                               'changes': [{'op': 'add_character', 'name': 'Марта'}]})
    assert stale.is_error and '409' in text(stale) and 'get_characters' in text(stale)
    unknown = call(server, 'update_characters', {'story_id': story.id, 'expected_revision': data['revision'],
                                                 'changes': [{'op': 'remove_entry', 'character_id': 'nope', 'entry_id': 'x'}]})
    assert unknown.is_error and 'немає картки' in text(unknown)
    assert read(server, story)['revision'] == data['revision']


@pytest.mark.req('MCP-BRIDGE')
def test_add_character_and_entry_from_scene(tmp_path):
    app, http, server, story = story_with_cards(tmp_path)
    data = read(server, story)
    scene_id = data['scenes'][0]['id']
    anna = card(data['cards'], 'Анна')
    changes = [{'op': 'add_character', 'name': 'Марта', 'entries': [{'text': 'Сестра Анни.'}]},
               {'op': 'set_entry', 'character_id': anna['id'], 'text': "Інше ім'я: Ганна", 'availability': 'from_scene',
                'available_from_scene_id': scene_id}]
    result = call(server, 'update_characters', {'story_id': story.id, 'expected_revision': data['revision'], 'changes': changes, 'confirm': True})
    assert not result.is_error, text(result)
    cards = read(server, story)['cards']
    assert card(cards, 'Марта')['entries'][0]['origin'] == 'author'
    assert card(cards, 'Анна')['entries'][-1]['available_from_scene_id'] == scene_id


def test_keep_old_name_joins_an_existing_marker_line_with_its_markup():
    cards = [{'id': 'c1', 'name': 'Анна', 'entries': [
        {'id': 'e1', 'text': 'Доглядачка.\n- **Також відома як:** —', 'availability': 'unclassified', 'available_from_scene_id': None,
         'origin': 'author', 'sources': []}]}]
    after = apply_changes(cards, [{'op': 'rename', 'character_id': 'c1', 'name': 'Ганна'}], 'uk')
    assert after[0]['entries'][0]['text'] == 'Доглядачка.\n- **Також відома як:** Анна' and len(after[0]['entries']) == 1
    again = apply_changes(after, [{'op': 'rename', 'character_id': 'c1', 'name': 'Анна'}], 'uk')
    assert again[0]['entries'][0]['text'] == 'Доглядачка.\n- **Також відома як:** Анна, Ганна'
    assert cards[0]['name'] == 'Анна'  # the input is not modified
    assert describe(cards, after) == [{'character_id': 'c1', 'name': 'Ганна', 'name_was': 'Анна', 'entries_changed': [
        {'entry_id': 'e1', 'text_was': 'Доглядачка.\n- **Також відома як:** —', 'text': 'Доглядачка.\n- **Також відома як:** Анна',
         'availability': 'unclassified', 'available_from_scene_id': None}]}]


def test_set_entry_leaving_from_scene_clears_the_scene_and_bad_changes_name_their_number():
    cards = [{'id': 'c1', 'name': 'Анна', 'entries': [{'id': 'e1', 'text': 'Вдова.', 'availability': 'from_scene',
                                                        'available_from_scene_id': 's1', 'origin': 'author', 'sources': []}]}]
    after = apply_changes(cards, [{'op': 'set_entry', 'character_id': 'c1', 'entry_id': 'e1', 'availability': 'timeless'}], 'uk')
    assert after[0]['entries'][0]['available_from_scene_id'] is None
    for changes, message in (([], 'хоча б одну'), ([{'op': 'delete'}], 'Зміна 1'),
                             ([{'op': 'rename', 'character_id': 'c1'}], 'бракує name'),
                             ([{'op': 'set_entry', 'character_id': 'c1', 'availability': 'from_scene', 'text': 'x'}], 'available_from_scene_id')):
        with pytest.raises(ChangeError, match=message):
            apply_changes(cards, changes, 'uk')


@pytest.mark.req('VALID-CARDS')
def test_dependent_scenes_need_the_authors_answer_and_only_yes_unchecks_them(tmp_path):
    from fastapi.testclient import TestClient
    from storygen.application.settings import AppSettings
    from storygen.web.app import create_app
    from tests.storage.test_links import book
    from tests.web.test_card_invalidation import card as new_card, cast, material_status, save_cards
    repo, story, (first, second) = book(tmp_path, 2)
    with TestClient(create_app(AppSettings(data_dir=tmp_path, env_file=tmp_path / 'absent.env')), base_url='http://127.0.0.1:8765') as http:
        saved = save_cards(http, story.id, [new_card('Олена', 'Бібліотекарка.')])
        olena = saved['cards'][0]
        cast(repo, first.id, character_ids=[olena['id']])
        cast(repo, second.id, character_ids=[olena['id']])
        server = build_server(http)

        def update(text, **extra):
            revision = read(server, story)['revision']
            return call(server, 'update_characters', {'story_id': story.id, 'expected_revision': revision, 'changes': [
                {'op': 'set_entry', 'character_id': olena['id'], 'entry_id': olena['entries'][0]['id'], 'text': text}], **extra})
        preview = update('Бібліотекарка з міста.').structured_content
        assert [scene['id'] for scene in preview['dependent_scenes']] == [first.id, second.id] and 'mark_unchecked' in preview['message']
        unanswered = update('Бібліотекарка з міста.', confirm=True)
        assert unanswered.is_error and 'mark_unchecked' in text(unanswered)
        assert read(server, story)['cards'][0]['entries'][0]['text'] == 'Бібліотекарка.'
        no = update('Бібліотекарка з міста.', confirm=True, mark_unchecked=False).structured_content
        assert no['saved'] is True and no['marked'] is False
        assert material_status(http, story.id, first.id)['validity'] == 'valid'  # saving through MCP alone changes no link
        yes = update('Бібліотекарка з села.', confirm=True, mark_unchecked=True).structured_content
        assert yes['marked'] == 2
        assert {material_status(http, story.id, scene.id)['validity'] for scene in (first, second)} == {'unchecked'}
