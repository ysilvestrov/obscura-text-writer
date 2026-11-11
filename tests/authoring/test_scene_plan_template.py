import json

import pytest
from fastapi.testclient import TestClient
from storygen.application.settings import AppSettings
from storygen.domain import SceneCreate, StoryCreate
from storygen.memory.story_time import scene_start
from storygen.scene_plan_template import next_scene_plan, plan_fields
from storygen.storage.repository import Repository
from storygen.web.app import create_app

PREVIOUS = '''## Сцена 4: Вокзал
Локація: Перон другої колії
Початок: день 2, 08:00
Кінець: день 2, 09:30
Хто бере участь: Олена, Марко (здалеку)
Що було в попередніх сценах: Олена купила квиток.
Що відбувається: Потяг запізнюється, Олена чекає.
Дії:
1. Олена виходить на перон.
2. Оголошують запізнення.
3. Вона сідає на лавку.
Ключове усвідомлення: Поспіх нічого не змінить.
Емоційний акцент: Нетерпіння, що стихає.
'''

EXPECTED = '''## Сцена 5: Дорога
Локація: Перон другої колії
Початок: день 2, 09:30
Кінець:
Хто бере участь: Олена, Марко (здалеку)
Що було в попередніх сценах: Потяг запізнюється, Олена чекає.
Що відбувається:
Дії:
1.
2.
3.
Ключове усвідомлення: Поспіх нічого не змінить.
Емоційний акцент: Нетерпіння, що стихає.
'''

EMPTY = '''## Сцена 1: Перша
Локація:
Початок:
Кінець:
Хто бере участь:
Що було в попередніх сценах:
Що відбувається:
Дії:
1.
2.
3.
Ключове усвідомлення:
Емоційний акцент:
'''


def cards(repo, story, people=(('olena', 'Олена'), ('marko', 'Марко'))):
    payload = [dict(schema_version=2, id=id, name=name, entries=[dict(id='entry-' + id, text='опис-' + id, availability='timeless', origin='author')]) for id, name in people]
    ref = repo.save_version(story.id, None, 'character_cards', json.dumps(payload, ensure_ascii=False), [])
    repo.publish_story_material(story.id, 'characters_version_id', ref.id, repo.get_story(story.id).revision)


def story_with(tmp_path, *plans, language='uk'):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Твір', language=language))
    cards(repo, story)
    scenes = [repo.create_scene(story.id, SceneCreate(title=f'Стара {index}', beats=plan)) for index, plan in enumerate(plans)]
    return repo, story, scenes


def test_all_six_fields_carry_over_and_the_rest_stays_empty(tmp_path):
    repo, story, _ = story_with(tmp_path, PREVIOUS)
    scene = repo.create_scene(story.id, SceneCreate(title='Дорога'), plan_template=True)
    assert scene.beats == EXPECTED
    assert scene.title == 'Дорога' and scene.author_scene_number == 5
    assert scene.character_ids == ['olena', 'marko']
    # The previous «Кінець» keeps the form memory reads as the day signal (MEMORY-003).
    assert scene_start(scene.beats) == ('day:2', '09:30')
    assert repo.get_scene(scene.id).beats == EXPECTED


def test_first_scene_gets_the_same_lines_with_empty_values(tmp_path):
    repo, story, _ = story_with(tmp_path)
    scene = repo.create_scene(story.id, SceneCreate(title='Перша'), plan_template=True)
    assert scene.beats == EMPTY
    assert scene.author_scene_number == 1 and scene.character_ids == [] and scene_start(scene.beats) is None


def test_missing_labels_give_empty_values(tmp_path):
    repo, story, _ = story_with(tmp_path, '## Сцена 2: Кухня\nЛокація: Кухня\nЩо відбувається: Марко варить каву.')
    scene = repo.create_scene(story.id, SceneCreate(title='Далі'), plan_template=True)
    assert scene.beats == EMPTY.replace('Сцена 1: Перша', 'Сцена 3: Далі').replace('Локація:', 'Локація: Кухня').replace('Що було в попередніх сценах:', 'Що було в попередніх сценах: Марко варить каву.')


def test_author_plan_is_never_replaced(tmp_path):
    repo, story, _ = story_with(tmp_path, PREVIOUS)
    scene = repo.create_scene(story.id, SceneCreate(title='Своя', beats='Олена їде додому.'), plan_template=True)
    assert scene.beats == 'Олена їде додому.' and scene.author_scene_number is None
    blank = repo.create_scene(story.id, SceneCreate(title='Пробіли', beats=' \n'), plan_template=True)
    # The previous scene has no author number, so the number is the place in reading order.
    assert blank.beats.startswith('## Сцена 3: Пробіли\nЛокація:\n')


def test_storage_callers_without_the_flag_keep_an_empty_plan(tmp_path):
    repo, story, _ = story_with(tmp_path, PREVIOUS)
    assert repo.create_scene(story.id, SceneCreate(title='Без шаблону')).beats == ''


def test_previous_scene_is_the_closest_active_one_before_the_new_position(tmp_path):
    first = PREVIOUS.replace('Сцена 4', 'Сцена 1').replace('Перон другої колії', 'Каса')
    repo, story, scenes = story_with(tmp_path, first, PREVIOUS.replace('Сцена 4', 'Сцена 2'), PREVIOUS.replace('Сцена 4', 'Сцена 3').replace('Перон другої колії', 'Вагон'))
    middle = repo.create_scene(story.id, SceneCreate(title='Вставка', position=1), plan_template=True)
    assert 'Локація: Каса\n' in middle.beats
    # Number 2 belongs to the next scene: the first free number after the previous one is taken instead.
    assert middle.author_scene_number == 4 and middle.beats.startswith('## Сцена 4: Вставка\n')
    assert [s.id for s in repo.list_scenes(story.id)][1] == middle.id
    repo.set_scene_trashed(story.id, scenes[2].id, repo.get_scene(scenes[2].id).revision, False)
    last = repo.create_scene(story.id, SceneCreate(title='Після кошика'), plan_template=True)
    assert 'Локація: Перон другої колії\n' in last.beats and 'Вагон' not in last.beats
    top = repo.create_scene(story.id, SceneCreate(title='Нова перша', position=0), plan_template=True)
    assert 'Локація:\n' in top.beats and top.author_scene_number == 5


def test_unnumbered_previous_scene_counts_by_reading_order(tmp_path):
    repo, story, _ = story_with(tmp_path, 'Локація: Двір', 'Локація: Сад')
    scene = repo.create_scene(story.id, SceneCreate(title='Третя'), plan_template=True)
    assert scene.beats.startswith('## Сцена 3: Третя\nЛокація: Сад\n') and scene.author_scene_number == 3


def test_explicit_number_and_cast_of_the_request_win(tmp_path):
    repo, story, _ = story_with(tmp_path, PREVIOUS)
    scene = repo.create_scene(story.id, SceneCreate(title='Явна', author_scene_number=9, character_ids=['marko']), plan_template=True)
    assert scene.beats.startswith('## Сцена 9: Явна\n') and 'Хто бере участь: Марко\n' in scene.beats
    assert scene.author_scene_number == 9 and scene.character_ids == ['marko']
    with pytest.raises(ValueError):
        repo.create_scene(story.id, SceneCreate(title='Зайнята', author_scene_number=9), plan_template=True)


def test_cast_without_a_plan_line_is_written_by_card_names(tmp_path):
    repo, story, scenes = story_with(tmp_path, 'Локація: Двір')
    repo.update_scene_metadata(scenes[0].id, {'character_ids': ['olena', 'marko']}, scenes[0].revision)
    scene = repo.create_scene(story.id, SceneCreate(title='Далі'), plan_template=True)
    assert 'Хто бере участь: Олена, Марко\n' in scene.beats and scene.character_ids == ['olena', 'marko']
    # A manual cast over an empty cast line is still the cast of the previous scene.
    emptied = repo.update_scene_plan(scene.id, 'Персонажі:\nЛокація: Сад', scene.revision)
    repo.update_scene_metadata(scene.id, {'character_ids': ['marko']}, emptied.revision)
    following = repo.create_scene(story.id, SceneCreate(title='Ще далі'), plan_template=True)
    assert 'Хто бере участь: Марко\n' in following.beats and following.character_ids == ['marko']


def test_decorated_and_alternative_labels_are_read(tmp_path):
    plan = '**Сцена 7: Ринок**\n- **Локація:** Ринок\n- **Кінець:** 01.03.2024, 18:00\n- **Персонажі:** Олена\n- **Що відбувається:** Торг.\n- **Емоційний акцент:** Азарт'
    repo, story, _ = story_with(tmp_path, plan)
    scene = repo.create_scene(story.id, SceneCreate(title='Після ринку'), plan_template=True)
    assert scene.beats.startswith('## Сцена 8: Після ринку\nЛокація: Ринок\nПочаток: 01.03.2024, 18:00\nКінець:\nХто бере участь: Олена\nЩо було в попередніх сценах: Торг.\n')
    assert scene.beats.endswith('Ключове усвідомлення:\nЕмоційний акцент: Азарт\n')
    assert scene_start(scene.beats) == ('date:1.3.2024', '18:00') and scene.character_ids == ['olena']


def test_english_story_uses_english_labels_and_reads_both_languages(tmp_path):
    repo, story, _ = story_with(tmp_path, PREVIOUS, language='en')
    scene = repo.create_scene(story.id, SceneCreate(title='The road'), plan_template=True)
    assert scene.beats == '''## Scene 5: The road
Location: Перон другої колії
Start: день 2, 09:30
End:
Characters: Олена, Марко (здалеку)
Previously: Потяг запізнюється, Олена чекає.
What happens:
Beats:
1.
2.
3.
Key realisation: Поспіх нічого не змінить.
Emotional focus: Нетерпіння, що стихає.
'''
    assert scene.title == 'The road' and scene.character_ids == ['olena', 'marko'] and scene_start(scene.beats) == ('day:2', '09:30')
    following = repo.create_scene(story.id, SceneCreate(title='Arrival'), plan_template=True)
    assert following.beats.startswith('## Scene 6: Arrival\nLocation: Перон другої колії\nStart:\nEnd:\nCharacters: Олена, Марко (здалеку)\nPreviously:\n')


def test_pure_template_keeps_one_line_title_and_first_value():
    assert plan_fields('Локація: А\nЛокація: Б\nКінець:   день 1, 10:00  ') == {'location': 'А', 'end': 'день 1, 10:00'}
    text = next_scene_plan('uk', 2, 'Назва\nз переносом', {'location': 'А'})
    assert text.startswith('## Сцена 2: Назва з переносом\nЛокація: А\n') and text.count('\n') == 13


def test_api_creates_scene_with_template_and_keeps_given_plan(tmp_path):
    app = create_app(AppSettings(data_dir=tmp_path))
    with TestClient(app, base_url='http://127.0.0.1:8765') as client:
        story = client.post('/api/stories', json={'title': 'Твір'}).json()
        first = client.post(f"/api/stories/{story['id']}/scenes", json={'title': 'Вокзал', 'beats': PREVIOUS}).json()
        assert first['beats'] == PREVIOUS
        created = client.post(f"/api/stories/{story['id']}/scenes", json={'title': 'Дорога'}).json()
        assert created['beats'] == EXPECTED and created['author_scene_number'] == 5 and created['title'] == 'Дорога'
        assert app.state.repo.get_scene(created['id']).beats == EXPECTED


def test_add_scene_button_sends_only_the_title():
    from importlib.resources import files
    script = files('storygen.web').joinpath('static', 'editor.js').read_text(encoding='utf-8')
    assert "api('/api/stories/'+state.storyId+'/scenes',json('POST',{title}))" in script
