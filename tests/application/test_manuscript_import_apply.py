"""MANUSCRIPT-IMPORT: applying a previewed manuscript as a new book (spec §4.1–4.3, §8)."""
import hashlib

import pytest

from storygen.application import manuscript_import as service
from storygen.book.guard import NO_LONG_PROSE
from storygen.domain import RevisionConflict
from storygen.publication.manuscript_structure import ParseSettings
from storygen.storage.integrity import check_integrity
from storygen.storage.links import scene_links
from storygen.storage.repository import Repository
from tests.publication.manuscript_fixtures import docx, para

P = 'Перший абзац {} глави, досить довгий. '
# 0 title, 1 short preface (front matter), 2 heading, 3-4 prose, 5 heading, 6-7 prose
BOOK = '\n\n'.join(['# Книга', 'Коротка передмова.', '## Глава перша', P.format('першої') * 5, 'Другий *абзац* першої. ' * 5,
                    '## Глава друга', P.format('другої') * 5, 'Другий абзац другої. ' * 5]).encode()


def setup(tmp_path, content=BOOK, name='book.md', settings=ParseSettings()):
    repo = Repository(tmp_path / 'data')
    return repo, service.preview(repo, content, name, settings)


def body(preview, scenes=None, **extra):
    scenes = scenes if scenes is not None else [{'start': s.start, 'title': s.title} for s in preview.scenes]
    return {'fingerprint': preview.fingerprint, 'title': 'Моя книга', 'language': 'uk', 'content_rating': None,
            'scenes': scenes, 'parts': [], **extra}


def temp_files(tmp_path):
    folder = tmp_path / 'data' / 'manuscript-import'
    return sorted(path.name for path in folder.iterdir()) if folder.exists() else []


def story_files(tmp_path):
    folder = tmp_path / 'data' / 'stories'
    return [path for path in folder.rglob('*') if path.is_file()] if folder.exists() else []


def prose(repo, scene_id):
    scene = repo.get_scene(scene_id)
    return repo.get_version(scene.heads['prose']), repo.read_text(scene.heads['prose'])


def test_apply_creates_book_with_manual_prose(tmp_path):
    repo, preview = setup(tmp_path)
    rating = {'sexual': 0, 'violence': 1, 'themes': 0}
    result = service.apply_import(repo, preview.import_id, body(preview, content_rating=rating, language='en'))
    story = repo.get_story(result['story_id'])
    assert story.title == 'Моя книга' and story.language == 'en' and story.content_rating.model_dump() == rating
    assert story.target_words == 5000  # StoryCreate's lower bound; the scenes carry their own word counts
    assert [s.title for s in repo.list_scenes(story.id)] == ['Глава перша', 'Глава друга']
    first, text = prose(repo, result['scene_ids'][0])
    assert first.kind == 'manual' and first.complete and not first.stale
    assert first.manuscript_import.file_sha256 == hashlib.sha256(BOOK).hexdigest()
    assert first.manuscript_import.file_name == 'book.md'
    assert text.startswith('Перший абзац першої') and 'Глава' not in text
    assert repo.get_scene(result['scene_ids'][0]).target_words == preview.scenes[0].words


def test_markdown_format_for_docx_and_md_plain_for_txt(tmp_path):
    content = docx(para('Глава 1', 'Heading1') + para('Він сказав ') + para('тихо', italic=True) + para('Глава 2', 'Heading1')
                   + para('Кінець історії.'), styles=['<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>'])
    repo, preview = setup(tmp_path / 'docx', content, 'book.docx')
    result = service.apply_import(repo, preview.import_id, body(preview))
    version, text = prose(repo, result['scene_ids'][0])
    assert version.content_format == 'markdown' and '*тихо*' in text
    repo, preview = setup(tmp_path / 'md')
    version, text = prose(repo, service.apply_import(repo, preview.import_id, body(preview))['scene_ids'][0])
    assert version.content_format == 'markdown' and '*абзац*' in text
    plain = 'Глава 1\n\nПростий *текст* першої глави.\n\nГлава 2\n\nДруга глава.'.encode()
    repo, preview = setup(tmp_path / 'txt', plain, 'book.txt')
    version, text = prose(repo, service.apply_import(repo, preview.import_id, body(preview))['scene_ids'][0])
    assert version.content_format == 'plain' and text == 'Простий *текст* першої глави.'


def test_apply_rejects_stale_fingerprint(tmp_path):
    repo, preview = setup(tmp_path)
    with pytest.raises(RevisionConflict):
        service.apply_import(repo, preview.import_id, {**body(preview), 'fingerprint': '0' * 64})
    # A re-preview with other markers keeps the import but invalidates the fingerprint of the first preview.
    other = service.preview(repo, b'', '', ParseSettings(chapter_markers=('Сцена',)), preview.import_id)
    assert other.fingerprint != preview.fingerprint
    with pytest.raises(RevisionConflict):
        service.apply_import(repo, preview.import_id, body(preview))
    assert repo.list_stories(include_trashed=True) == [] and story_files(tmp_path) == []
    assert service.apply_import(repo, preview.import_id, body(other))['story_id']


@pytest.mark.parametrize('starts', [
    [3, 5],     # a chapter heading is not a prose paragraph
    [3, 99],    # beyond the file
    [3, -1],
    [6, 3],     # unsorted
    [3, 3],     # duplicate: an empty scene
    [4, 6],     # the first scene must start at the first prose paragraph, nothing is dropped
    [1, 6],     # front matter not requested
    [],         # no scenes
])
def test_apply_rejects_boundary_inside_paragraph_or_unsorted_or_empty(tmp_path, starts):
    repo, preview = setup(tmp_path)
    with pytest.raises(ValueError):
        service.apply_import(repo, preview.import_id, body(preview, [{'start': s, 'title': f'С{s}'} for s in starts]))
    assert repo.list_stories(include_trashed=True) == [] and story_files(tmp_path) == []
    assert any(name.endswith('.md') for name in temp_files(tmp_path))


def test_apply_scene_boundaries_from_author(tmp_path):
    repo, preview = setup(tmp_path)
    assert [s.start for s in preview.scenes] == [3, 6]
    result = service.apply_import(repo, preview.import_id, body(preview, [{'start': 3, 'title': 'Початок'},
                                                                          {'start': 4, 'title': 'Решта'}]))
    titles = [s.title for s in repo.list_scenes(result['story_id'])]
    assert titles == ['Початок', 'Решта']
    _, first = prose(repo, result['scene_ids'][0])
    _, rest = prose(repo, result['scene_ids'][1])
    assert first.startswith('Перший абзац першої') and 'Другий' not in first
    assert rest.startswith('Другий *абзац*')
    assert 'Глава друга' not in rest and 'Перший абзац другої' in rest and rest.endswith('Другий абзац другої.')


def test_front_matter_included_when_requested(tmp_path):
    repo, preview = setup(tmp_path)
    assert preview.front_matter == [1]
    without = service.apply_import(repo, preview.import_id, body(preview))
    assert 'передмова' not in prose(repo, without['scene_ids'][0])[1]
    repo, preview = setup(tmp_path / 'with')
    scenes = [{'start': 1, 'title': 'Глава перша'}, {'start': 6, 'title': 'Глава друга'}]
    with_front = service.apply_import(repo, preview.import_id, body(preview, scenes, include_front_matter=True))
    assert prose(repo, with_front['scene_ids'][0])[1].startswith('Коротка передмова.')


def test_store_edition_rejects_parts_and_series_before_write(tmp_path, store_edition):
    repo, preview = setup(tmp_path)
    kept = temp_files(tmp_path)
    for extra in ({'parts': [{'index': 0, 'title': 'Частина'}]}, {'series': {'series_id': 'a' * 32, 'number': 1}}):
        with pytest.raises(ValueError, match=NO_LONG_PROSE):
            service.apply_import(repo, preview.import_id, body(preview, **extra))
    with pytest.raises(ValueError, match=NO_LONG_PROSE):
        service.apply_import(repo, preview.import_id, body(preview, [{'start': 3, 'title': 'А', 'part_index': 0},
                                                                     {'start': 6, 'title': 'Б', 'part_index': 0}]))
    assert repo.list_stories(include_trashed=True) == [] and story_files(tmp_path) == []
    assert temp_files(tmp_path) == kept


def test_parts_and_scene_part_index(tmp_path):
    repo, preview = setup(tmp_path)
    scenes = [{'start': 3, 'title': 'А', 'part_index': 0}, {'start': 6, 'title': 'Б', 'part_index': 1}]
    parts = [{'index': 0, 'title': 'Перша'}, {'index': 1, 'title': 'Друга'}]
    result = service.apply_import(repo, preview.import_id, body(preview, scenes, parts=parts))
    assert [p.title for p in repo.get_story(result['story_id']).book_structure.parts] == ['Перша', 'Друга']
    repo, preview = setup(tmp_path / 'bad')
    for bad in ([{'start': 3, 'title': 'А', 'part_index': 5}, {'start': 6, 'title': 'Б'}],
                [{'start': 3, 'title': 'А', 'part_index': 1}, {'start': 6, 'title': 'Б', 'part_index': 0}]):
        with pytest.raises(ValueError):
            service.apply_import(repo, preview.import_id, body(preview, bad, parts=parts))
    assert repo.list_stories(include_trashed=True) == []


def test_series_number_and_start(tmp_path, monkeypatch):
    from storygen.storage import series as series_store
    repo, preview = setup(tmp_path)
    series = series_store.create_series(repo, 'Серія')
    first = series_store.create_book(repo, series.id, 'Перша')
    files_before = len(story_files(tmp_path))
    with pytest.raises(ValueError):
        service.apply_import(repo, preview.import_id, body(preview, series={'series_id': series.id, 'number': first.series_number}))
    assert [s.id for s in repo.list_stories(include_trashed=True)] == [first.id]
    assert len(story_files(tmp_path)) == files_before
    snapshots = []
    original = series_store.take_snapshot_if_ready
    monkeypatch.setattr(series_store, 'take_snapshot_if_ready', lambda repo, story_id: snapshots.append(story_id) or original(repo, story_id))
    result = service.apply_import(repo, preview.import_id, body(preview, series={'series_id': series.id, 'number': 2}))
    story = repo.get_story(result['story_id'])
    assert (story.series_id, story.series_number, story.series_bible) == (series.id, 2, False)
    assert snapshots == [story.id]  # the start snapshot is taken as «Нова книга серії» does
    assert story.series_start_version_id is None and any('попередньої книги' in w for w in result['warnings'])
    assert check_integrity(repo.root).ok


def test_series_start_snapshot_from_previous_book(tmp_path):
    from storygen.storage import series as series_store
    from tests.series.helpers import finished_book, into_series
    repo, preview = setup(tmp_path)
    series = series_store.create_series(repo, 'Серія')
    first, _, _ = finished_book(repo)
    into_series(repo, first, series.id, 1)
    result = service.apply_import(repo, preview.import_id, body(preview, series={'series_id': series.id, 'number': 2}))
    story = repo.get_story(result['story_id'])
    assert story.series_start_version_id and result['warnings'] == []
    view = repo.context_view(story.id)
    assert not any(view.get_version(view.get_scene(id).heads['prose']).stale for id in result['scene_ids'])
    assert check_integrity(repo.root).ok


def test_first_book_of_series_has_no_start_warning(tmp_path):
    from storygen.storage import series as series_store
    repo, preview = setup(tmp_path)
    series = series_store.create_series(repo, 'Серія')
    result = service.apply_import(repo, preview.import_id, body(preview, series={'series_id': series.id, 'number': 1}))
    assert repo.get_story(result['story_id']).series_number == 1 and result['warnings'] == []


def test_plan_written_later_does_not_stale_prose_or_memory(tmp_path):
    repo, preview = setup(tmp_path)
    result = service.apply_import(repo, preview.import_id, body(preview))
    scene_id = result['scene_ids'][1]
    heads = {id: repo.get_scene(id).heads['prose'] for id in result['scene_ids']}
    view = repo.context_view(result['story_id'])
    before = {id: scene_links(view, id)['memory'].status for id in result['scene_ids']}
    scene = repo.get_scene(scene_id)
    repo.update_scene_plan(scene_id, 'Новий план сцени: герой іде додому.', scene.revision)
    view = repo.context_view(result['story_id'])
    for id in result['scene_ids']:
        scene = view.get_scene(id)
        assert scene.heads['prose'] == heads[id] and not view.get_version(heads[id]).stale
        assert scene_links(view, id)['memory'].status == before[id]
    assert view.get_scene(scene_id).heads.get('plan')


def test_temp_file_removed_after_apply(tmp_path):
    repo, preview = setup(tmp_path)
    assert temp_files(tmp_path)
    service.apply_import(repo, preview.import_id, body(preview))
    assert temp_files(tmp_path) == []
    with pytest.raises(KeyError):
        service.apply_import(repo, preview.import_id, body(preview))


def test_integrity_ok_after_import(tmp_path):
    repo, preview = setup(tmp_path)
    service.apply_import(repo, preview.import_id, body(preview))
    assert check_integrity(repo.root).ok


def test_origin_file_name_is_sanitized():
    assert service.origin_file_name('C:\\Users\\a/Мій роман.docx') == 'Мій роман.docx'
    assert service.origin_file_name('кни\ud800га.md') == 'книга.md'
    assert len(service.origin_file_name('я' * 400 + '.txt')) == 255
    assert service.origin_file_name('dir/') == 'manuscript'
