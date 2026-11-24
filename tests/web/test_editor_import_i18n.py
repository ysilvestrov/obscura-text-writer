"""EDITOR-IMPORT: the proposal source in the copyedit API and the English text of every import message."""
import re
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from storygen.application import editor_import
from storygen.application.editor_import import preview_import
from storygen.application.settings import AppSettings
from storygen.web.app import create_app
from storygen.web.localization import diagnostic
from tests.generation.test_copyedit_review import generate
from tests.publication.test_editor_import import book, edit, drop_manifest, imported, split, tracked

CYRILLIC = re.compile('[А-Яа-яІіЇїЄєҐґ]')

# The uk texts exactly as the server builds them, with Latin values for the variable parts so the result is checkable.
MESSAGES = [
    editor_import.PENDING_REVIEW,
    editor_import.FORMATTING_LOST,
    editor_import.STALE_PREVIEW,
    editor_import.SCENE_CHANGED,
    editor_import.WHOLE_SCENE_DELETED,
    'Розмітку прози не можна передати через DOCX без змін; сцену не імпортовано.',
    'Проза у простому тексті: курсив і жирний з DOCX не переносяться.',
    'Правку в заголовку сцени не імпортовано: заголовок не є прозою.',
    'Прозу сцени змінено після експорту.',
    'Експорт не знайдено; редактор правив без режиму виправлень або прозу змінено.',
    'Редактор видалив увесь текст сцени.',
    'Лише чернетка: правки не вміщуються в перегляд.',
    'Примітки понад межі не імпортовано: 3.',
    'Примітки поза розпізнаними сценами не імпортовано: 2.',
    'У чинній чернетці є коментарі (4); вони лишаться в попередній версії чернетки.',
    'Експорт, з якого зроблено файл, не знайдено або його маніфест пошкоджено: '
    'сцени, правлені без режиму виправлень, потребують вашого вибору.',
    'Заголовок «Dawn»: закладка сцени повторюється, фрагмент не розпізнано.',
    'Заголовок «Dawn»: закладка не відповідає жодній сцені твору, фрагмент не розпізнано.',
    'Заголовок «Dawn»: кілька закладок сцен, фрагмент не розпізнано.',
    'Назву змінено редактором: заголовок «Dawn» прийнято за сцену «Dusk» за місцем у тексті.',
    'Заголовок «Dawn»: не вдалося визначити сцену, фрагмент не розпізнано.',
    # reader warnings, bare (no paragraph) and with the place prefix of a scene
    'таблицю пропущено разом з текстом у ній',
    'малюнок або фігуру не імпортовано',
    'вбудований об’єкт не імпортовано',
    'виноску не імпортовано',
    'зміну форматування проігноровано (імпортується лише текст)',
    # the apply result prefixes a scene warning with its title
    '«Dawn»: редактор вилучив увесь текст сцени; сцену не імпортовано.',
    '«Dawn»: ' + editor_import.PENDING_REVIEW,
    '«Dawn»: сцену не імпортовано — ' + editor_import.SCENE_CHANGED,
    '«Dawn»: сцену не імпортовано — disk error',
    '«Dawn»: ' + editor_import.FORMATTING_LOST,
    '«Dawn»: Проза у простому тексті: курсив і жирний з DOCX не переносяться.',
    '«Dawn»: Правку в заголовку сцени не імпортовано: заголовок не є прозою.',
    '«Dawn»: Прозу сцени змінено після експорту.',
    '«Dawn»: Експорт не знайдено; редактор правив без режиму виправлень або прозу змінено.',
    '«Dawn»: Редактор видалив увесь текст сцени.',
    '«Dawn»: Лише чернетка: правки не вміщуються в перегляд.',
    '«Dawn»: Примітки понад межі не імпортовано: 3.',
    '«Dawn»: У чинній чернетці є коментарі (4); вони лишаться в попередній версії чернетки.',
    # HTTP errors: ValueError gets the «Некоректні дані: » prefix from the app, the 413 detail does not
    'Файл з іншого твору',
    'Невідомий вибір для змінених сцен',
    'Оберіть, що робити зі сценами, зміненими після експорту',
    'Завантажте файл як multipart/form-data',
    'Завантажте один файл DOCX',
    'Оберіть один файл DOCX',
    'Файл має бути до 20 MiB',
    'DOCX: файл завеликий для імпорту',
    'DOCX: файл зашифровано або це старий формат Word; збережіть його як звичайний .docx без пароля',
    'DOCX: файл не є пакетом DOCX (ZIP)',
    'DOCX: у файлі немає word/document.xml',
    'DOCX: вміст файлу завеликий після розпаковування',
    'DOCX: файл пошкоджено',
    'DOCX: файл містить DOCTYPE; такий XML не читається',
    'DOCX: word/document.xml не є коректним XML',
    'DOCX: структура документа занадто глибоко вкладена',
    'DOCX: у word/document.xml немає тіла документа',
]


@pytest.mark.parametrize('text', MESSAGES)
def test_every_import_message_has_english(text):
    english = diagnostic(text, 'en')
    assert english != text, text
    assert not CYRILLIC.search(english.replace('Dawn', '').replace('Dusk', '')), english
    assert diagnostic(text, 'uk') == text


def test_prefixed_http_error_has_english():
    assert not CYRILLIC.search(diagnostic('Некоректні дані: Файл з іншого твору', 'en'))


def test_real_preview_warnings_have_english(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    changed = edit(content, lambda xml: xml.replace('Вечір.', 'Вечір.</w:t></w:r><w:r><w:drawing/><w:t>'))
    preview = preview_import(repo, story.id, changed)
    [reader] = preview.scenes[2].warnings
    title = scenes[2].title
    assert reader == f'«{title}», абзац 1: малюнок або фігуру не імпортовано'
    assert diagnostic(reader, 'en') == f'«{title}», paragraph 1: the picture or shape was not imported'
    # the same warning after the apply prefixed it with the scene title
    assert diagnostic(f'«{title}»: {reader}', 'en') == f'«{title}»: «{title}», paragraph 1: the picture or shape was not imported'
    drop_manifest(tmp_path, story, content)
    manifest = preview_import(repo, story.id, content)
    assert not CYRILLIC.search(diagnostic(manifest.warnings[0], 'en'))


@pytest.mark.parametrize('text,english', [
    ('«Dawn», заголовок: таблицю пропущено разом з текстом у ній', '«Dawn», heading: the table was skipped together with the text in it'),
    ('«Dawn», абзац 3: виноску не імпортовано', '«Dawn», paragraph 3: the footnote was not imported'),
    ('Фрагмент «Dusk», заголовок: виноску не імпортовано', 'Fragment «Dusk», heading: the footnote was not imported'),
    ('Фрагмент «Dusk», абзац 2: малюнок або фігуру не імпортовано', 'Fragment «Dusk», paragraph 2: the picture or shape was not imported'),
    ('Абзац 7 документа: вбудований об’єкт не імпортовано', 'Paragraph 7 of the document: the embedded object was not imported'),
    ('Примітки понад межі не імпортовано: 3.', 'Comments over the limit were not imported: 3.'),
    ('«Dawn»: Примітки понад межі не імпортовано: 3.', '«Dawn»: Comments over the limit were not imported: 3.'),
    ('«Dawn»: У чинній чернетці є коментарі (4); вони лишаться в попередній версії чернетки.',
     '«Dawn»: The current draft has comments (4); they stay in the previous draft version.'),
    ('Примітки поза розпізнаними сценами не імпортовано: 2.', 'Comments outside the recognized scenes were not imported: 2.'),
    ('Заголовок «Dawn»: кілька закладок сцен, фрагмент не розпізнано.', 'Heading «Dawn»: several scene bookmarks, the fragment was not recognized.'),
    ('Назву змінено редактором: заголовок «Dawn» прийнято за сцену «Dusk» за місцем у тексті.',
     'The title was changed by the editor: heading «Dawn» was taken for the scene «Dusk» by its place in the text.'),
    ('«Dawn»: сцену не імпортовано — ' + editor_import.SCENE_CHANGED,
     '«Dawn»: the scene was not imported — the scene prose was changed after the summary'),
    ('«Dawn»: сцену не імпортовано — disk error', '«Dawn»: the scene was not imported — disk error'),
    ('«Dawn»: сцену не імпортовано — ' + 'Твір змінився після зведення; перегляньте його ще раз',
     '«Dawn»: the scene was not imported — The story changed after the summary; review the file again'),
    ('Файл має бути до 20 MiB', 'The file must be at most 20 MiB'),
    ('DOCX: word/document.xml не є коректним XML', 'DOCX: word/document.xml is not valid XML'),
])
def test_parameters_land_in_place(text, english):
    assert diagnostic(text, 'en') == english


def test_no_repeated_placeholder_in_import_keys():
    from storygen.web.localization import catalogs
    for locale, messages in catalogs().items():
        for key, value in messages.items():
            if key.startswith('editor_import.server.'):
                names = re.findall(r'{(p\d+)}', value)
                assert len(names) == len(set(names)), (locale, key, value)


def test_js_diagnostic_translates_the_same_import_strings():
    result = subprocess.run(['node', str(Path(__file__).parent / 'js' / 'editor_import_diagnostic.mjs')],
                            capture_output=True, encoding='utf8', timeout=20)
    assert result.returncode == 0, result.stderr


def client_for(tmp_path):
    return TestClient(create_app(AppSettings(data_dir=tmp_path)), base_url='http://127.0.0.1:8765')


def test_proposal_list_marks_editor_import(tmp_path):
    repo, story, scenes, content = book(tmp_path)
    imported(repo, story, edit(content, lambda xml: split(xml, 'пішов', tracked('пішов', 'побіг'))))
    [attempt] = repo.list_attempts(story.id, scene_id=scenes[1].id, context_key='editor_import')
    with client_for(tmp_path) as client:
        listed = client.get(f'/api/scenes/{scenes[1].id}/copyedits').json()['attempts']
        assert [(a['id'], a['source']) for a in listed] == [(attempt.id, 'editor_import')]
        view = client.get(f'/api/scenes/{scenes[1].id}/copyedits/{attempt.id}').json()
        assert view['source'] == 'editor_import'


def test_model_proposal_has_no_source(tmp_path):
    repo, scene, _, attempt = generate(tmp_path)
    with client_for(tmp_path) as client:
        listed = client.get(f'/api/scenes/{scene.id}/copyedits').json()['attempts']
        assert listed and all(a['source'] is None for a in listed)
        assert client.get(f'/api/scenes/{scene.id}/copyedits/{attempt.id}').json()['source'] is None
