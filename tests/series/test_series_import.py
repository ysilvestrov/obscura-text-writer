"""SERIES-S01, S03: the plan preamble «Серія:/Номер:/Початок:» puts the book into a series (neutral examples)."""
from storygen.authoring.imports import SourceFile, import_sources
from storygen.characters.models import load_characters
from storygen.domain import StoryCreate
from storygen.plan_sections import cut_series_lines, parse_series_start
from storygen.series_models import SeriesStart
from storygen.storage import series as store
from storygen.storage.repository import Repository
from tests.series.helpers import finished_book, into_series

SCENES = '## Сцена 1: Ранок\nАнна йде містом.\n\n## Сцена 2: Вечір\nАнна повертається.\n'


def run(repo, story, plan, cards=None):
    files = [SourceFile(name='plan.md', raw=plan.encode(), kind='source_plan')]
    if cards:
        files.append(SourceFile(name='cards.md', raw=cards.encode(), kind='source_characters'))
    result = import_sources(repo, story.id, files)
    return repo.get_story(story.id), [w for f in result.files for w in f.warnings]


def test_series_lines_are_cut_and_parsed():
    text, lines, invalid = cut_series_lines('# План\nСерія: Морська сага\n**Номер:** 2\nStart: Рік -5 від шторму, опора 1\nВступ.\n')
    assert (text, invalid) == ('# План\nВступ.\n', False)
    assert (lines.title, lines.number, lines.start) == ('Морська сага', 2, SeriesStart(offset='Рік -5', anchor=1))
    assert cut_series_lines('Вступ.\n') == ('Вступ.\n', None, False)
    assert cut_series_lines('Серія: Сага\nНомер: два\n')[1:] == (None, True)
    assert cut_series_lines('Номер: 2\n')[1:] == (None, True)
    assert parse_series_start('Рік 3, День -2 після війни 4') == SeriesStart(offset='Рік 3, День -2', anchor=4)
    assert parse_series_start('Рік 3 без опори') is None


def test_preamble_puts_the_book_into_a_new_series(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга 1'))
    story, warnings = run(repo, story, 'Серія: Морська сага\nНомер: 1\n\n' + SCENES)
    item = store.find_series(repo, ' морська  САГА ')
    assert (story.series_id, story.series_number) == (item.id, 1)
    assert warnings == ['Створено нову серію «Морська сага»']
    assert 'Серія:' not in repo.read_text(repo.active_source(story.id, 'source_plan').id)
    assert len(repo.list_scenes(story.id)) == 2


def test_preamble_with_existing_series_takes_the_snapshot_before_cards(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    first, _, _ = finished_book(repo)
    into_series(repo, first, item.id, 1)
    second = repo.create_story(StoryCreate(title='Книга 2'))
    story, warnings = run(repo, second, 'Серія: сага\nНомер: 2\nПочаток: Рік 1, опора 1\n\n' + SCENES,
                          cards='# Анна\nАнна — лікарка з міста.\n\n# Борис\nБорис — рибалка.\n')
    assert story.series_start_version_id and story.series_start == SeriesStart(offset='Рік 1', anchor=1)
    cards = load_characters(repo.read_text(story.characters_version_id))
    assert sorted(c.name for c in cards) == ['Анна', 'Борис'] and next(c for c in cards if c.name == 'Анна').id == 'A'
    assert any('Анна' in w for w in warnings)


def test_taken_number_warns_and_imports_the_plan(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    first = repo.create_story(StoryCreate(title='Книга 1'))
    into_series(repo, first, item.id, 1)
    other = repo.create_story(StoryCreate(title='Книга 1 ще раз'))
    story, warnings = run(repo, other, 'Серія: Сага\nНомер: 1\n\n' + SCENES)
    assert story.series_id is None and len(repo.list_scenes(story.id)) == 2
    assert any('Номер 1 у серії вже зайнятий' in w for w in warnings)


def test_unparsed_lines_warn(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    story, warnings = run(repo, story, 'Серія: Сага\nНомер: перший\n\n' + SCENES)
    assert story.series_id is None and store.find_series(repo, 'Сага') is None
    assert any('«Серія:»' in w for w in warnings)


def test_own_number_is_not_taken(tmp_path):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Сага')
    story = repo.create_story(StoryCreate(title='Книга 1'))
    into_series(repo, story, item.id, 1)
    story, warnings = run(repo, repo.get_story(story.id), 'Серія: Сага\nНомер: 1\n\n' + SCENES)
    assert (story.series_id, story.series_number) == (item.id, 1)
    assert not any('зайнятий' in w for w in warnings)


def test_store_edition_leaves_lines_in_the_plan(tmp_path, store_edition):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Книга'))
    story, warnings = run(repo, story, 'Серія: Сага\nНомер: 1\n\n' + SCENES)
    assert story.series_id is None and store.list_series(repo) == []
