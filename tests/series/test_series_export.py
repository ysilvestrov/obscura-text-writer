"""SERIES-S06: an empty cycle of the publication card takes the series title and number in exports."""
import io
import zipfile

from storygen.domain import SceneCreate, StoryCreate
from storygen.publication.book import capture
from storygen.publication.epub import render
from storygen.publication_models import PublicationData
from storygen.storage import series as store
from storygen.storage.repository import Repository
from tests.series.helpers import prose


def series_book(tmp_path, number=2):
    repo = Repository(tmp_path)
    item = store.create_series(repo, 'Морська сага')
    story = repo.create_story(StoryCreate(title='Книга'))
    prose(repo, repo.create_scene(story.id, SceneCreate(title='Сцена')), 'Анна вийшла.')
    store.set_story_series(repo, story.id, item.id, number, None, repo.get_story(story.id).revision)
    return repo, repo.get_story(story.id)


def test_epub_takes_the_series_when_cycle_is_empty(tmp_path):
    repo, story = series_book(tmp_path)
    book = capture(repo, story.id, 'epub', True)
    assert (book.snapshot.publication.card.cycle_title, book.snapshot.publication.card.cycle_number) == ('Морська сага', 2)
    archive = zipfile.ZipFile(io.BytesIO(render(book)))
    opf = next(archive.read(n).decode('utf-8') for n in archive.namelist() if n.endswith('.opf'))
    assert 'belongs-to-collection' in opf and 'Морська сага' in opf


def test_card_cycle_wins_over_the_series(tmp_path):
    repo, story = series_book(tmp_path)
    repo.publication('save_card', story_id=story.id, data=PublicationData(title='Книга', cycle_title='Цикл автора', cycle_number=7),
                     expected_revision=0, expected_signature_revisions={})
    card = capture(repo, story.id, 'epub', True).snapshot.publication.card
    assert (card.cycle_title, card.cycle_number) == ('Цикл автора', 7)


def test_book_outside_series_keeps_an_empty_cycle(tmp_path):
    repo = Repository(tmp_path)
    story = repo.create_story(StoryCreate(title='Окрема'))
    card = capture(repo, story.id, 'epub', True).snapshot.publication.card
    assert not card.cycle_title and card.cycle_number is None
