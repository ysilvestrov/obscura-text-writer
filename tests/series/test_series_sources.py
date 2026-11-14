"""SERIES-S08: a prequel by the chronology axis and the sources of the start memory (neutral examples)."""
from storygen.book.series import prequel_ids, start_sources
from storygen.domain import StoryCreate
from storygen.series_models import SeriesStart
from storygen.storage import series as store
from storygen.storage.repository import Repository


def book(repo, item, number, start=None):
    story = repo.create_story(StoryCreate(title=f'Книга {number}'))
    anchor_start = SeriesStart(offset=start[0], anchor=start[1]) if start else None
    return store.set_story_series(repo, story.id, item.id, number, anchor_start, story.revision)


def setup(tmp_path):
    repo = Repository(tmp_path)
    return repo, store.create_series(repo, 'Сага')


def books(repo, item):
    return store.series_books(repo, item.id)


def test_prequel_is_earlier_on_the_axis_than_a_smaller_number(tmp_path):
    repo, item = setup(tmp_path)
    book(repo, item, 1)
    second = book(repo, item, 2, ('Рік -10', 1))
    book(repo, item, 3, ('Рік 2', 1))
    fourth = book(repo, item, 4, ('Рік 1', 1))
    assert prequel_ids(books(repo, item)) == {second.id, fourth.id}


def test_book_off_the_axis_is_not_a_prequel(tmp_path):
    repo, item = setup(tmp_path)
    book(repo, item, 1)
    book(repo, item, 2, ('Рік -10', 5))
    assert prequel_ids(books(repo, item)) == set()


def test_sources_are_the_main_book_and_prequels_between(tmp_path):
    repo, item = setup(tmp_path)
    first = book(repo, item, 1)
    second = book(repo, item, 2, ('Рік -10', 1))
    third = book(repo, item, 3, ('Рік 2', 1))
    stories = repo.list_stories(include_trashed=True)
    assert [s.id for s in start_sources(stories, third)] == [first.id, second.id]
    assert [s.id for s in start_sources(stories, second)] == [first.id]
    assert start_sources(stories, first) == []


def test_trashed_main_book_moves_to_the_previous_one(tmp_path):
    repo, item = setup(tmp_path)
    first = book(repo, item, 1)
    second = book(repo, item, 2, ('Рік 5', 1))
    third = book(repo, item, 3, ('Рік -1', 1))
    fourth = book(repo, item, 4, ('Рік 9', 1))
    repo.set_story_trashed(second.id, repo.get_story(second.id).revision, False)
    stories = repo.list_stories(include_trashed=True)
    assert [s.id for s in start_sources(stories, fourth)] == [first.id, third.id]


def test_prequel_of_a_prequel_sources(tmp_path):
    repo, item = setup(tmp_path)
    first = book(repo, item, 1)
    second = book(repo, item, 2, ('Рік -10', 1))
    third = book(repo, item, 3, ('Рік -20', 1))
    stories = repo.list_stories(include_trashed=True)
    assert [s.id for s in start_sources(stories, third)] == [first.id, second.id]
