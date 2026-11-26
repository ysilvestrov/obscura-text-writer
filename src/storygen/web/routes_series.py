"""SERIES API: series of books and the series fields of a book. Long prose only (BUILD-EDITION-001)."""
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field

from ..book import guard
from ..book.guard import require_long_prose
from ..domain import DomainModel, RevisionConflict, SeriesStart
from ..storage import series as store

router = APIRouter()
START_UNPARSED = 'Початок має бути позначкою часу (рік, місяць, день зі знаком) і номером опори'
REFRESH_CONFIRM = 'Оновлення робить застарілою пам’ять перших сцен книги; підтвердьте його'
DECISIONS_CONFIRM = 'Нові позначки роблять застарілими пам’ять і завдання перших сцен книги; підтвердьте їх'



class SeriesIn(DomainModel):
    title: str = Field(min_length=1, max_length=300)


class SeriesRename(SeriesIn):
    expected_revision: int


class SeriesRefresh(DomainModel):
    expected_revision: int
    confirm: bool = False


class SeriesDecisions(DomainModel):
    decisions: dict[str, str]
    expected_revision: int
    confirm: bool = False


class StorySeries(DomainModel):
    series_id: str | None = Field(default=None, min_length=1, max_length=64)
    number: int | None = Field(default=None, ge=1, le=1000000)
    start: SeriesStart | None = None
    start_text: str | None = Field(default=None, max_length=300)  # «Рік -5, опора 1» as the author types it
    bible: bool = False  # the series' world bible: no number, no start (SERIES-BIBLE)
    expected_revision: int


@router.get('/api/series')
def series_list(request: Request):
    return store.list_series(request.app.state.repo)


@router.get('/api/series/{series_id}')
def series_view(series_id: str, request: Request):
    """The series screen: books in release order (trashed too) with the snapshot state, and the chronology axis."""
    from dataclasses import asdict
    from ..book.series import chronology, series_status
    repo = request.app.state.repo
    item = store.get_series(repo, series_id)
    books = store.series_books(repo, series_id)
    placed, outside = chronology([b for b in books if not b.trashed_at])
    outside += [b.id for b in books if b.trashed_at and not b.series_bible]
    rows = [{'id': b.id, 'title': b.title, 'number': b.series_number, 'bible': b.series_bible, 'trashed': bool(b.trashed_at),
             'start': b.series_start, 'status': asdict(series_status(repo, b))} for b in books]
    bible = next((b.id for b in books if b.series_bible), None)  # SERIES-BIBLE: shown apart from the axis
    return {'series': item, 'books': rows, 'placed': placed, 'outside': outside, 'bible': bible}


@router.get('/api/series/{series_id}/start-readiness')
def series_start_readiness(series_id: str, request: Request, number: int = Query(ge=1, le=1000000)):
    """MANUSCRIPT-IMPORT §4.2: the start snapshot a new book with this number would get, read only. `state` as
    `SeriesStatus` without a snapshot: 'first' (no earlier book), 'no_summary' (the source has no memory summary yet:
    the import preview warns with a link) or 'source_finished'."""
    from ..book.series import start_readiness
    repo = request.app.state.repo
    store.get_series(repo, series_id)
    status = start_readiness(repo, series_id, number)
    source = repo.get_story(status.source_story_id) if status.source_story_id else None
    return {'state': status.state, 'source_story_id': status.source_story_id,
            'source_title': source.title if source else None, 'source_number': status.source_number}


def _long_prose_page():
    from .. import build_edition
    if not build_edition.current().long_prose:
        raise HTTPException(404)


@router.get('/series')
def series_index_page(request: Request):
    _long_prose_page()
    return request.app.state.templates.TemplateResponse(request=request, name='series.html', context={'series_id': None})


@router.get('/series/{series_id}')
def series_page(series_id: str, request: Request):
    if not guard.series_long_prose(request.app.state.repo, series_id):
        raise HTTPException(404)
    store.get_series(request.app.state.repo, series_id)
    return request.app.state.templates.TemplateResponse(request=request, name='series.html', context={'series_id': series_id})


@router.post('/api/series')
def series_create(data: SeriesIn, request: Request):
    require_long_prose()
    return store.create_series(request.app.state.repo, data.title)


@router.patch('/api/series/{series_id}')
def series_rename(series_id: str, data: SeriesRename, request: Request):
    guard.require_series_long_prose(request.app.state.repo, series_id)
    return store.rename_series(request.app.state.repo, series_id, data.title, data.expected_revision)


@router.delete('/api/series/{series_id}')
def series_delete(series_id: str, expected_revision: int, request: Request):
    guard.require_series_long_prose(request.app.state.repo, series_id)
    store.delete_series(request.app.state.repo, series_id, expected_revision)
    return {'deleted': series_id}


@router.post('/api/series/{series_id}/books')
def series_new_book(series_id: str, data: SeriesIn, request: Request):
    guard.require_series_long_prose(request.app.state.repo, series_id)
    store.get_series(request.app.state.repo, series_id)
    return store.create_book(request.app.state.repo, series_id, data.title)


@router.post('/api/series/{series_id}/bible')
def series_new_bible(series_id: str, data: SeriesIn, request: Request):
    """«Нова біблія світу»: a second bible of the series is refused (SERIES-BIBLE)."""
    guard.require_series_long_prose(request.app.state.repo, series_id)
    store.get_series(request.app.state.repo, series_id)
    return store.create_bible(request.app.state.repo, series_id, data.title)


@router.patch('/api/stories/{story_id}/series')
def story_series(story_id: str, data: StorySeries, request: Request):
    guard.require_long_prose_for(request.app.state.repo, story_id)
    start = data.start
    if data.start_text and data.start_text.strip():
        from ..plan_sections import parse_series_start
        start = parse_series_start(data.start_text)
        if start is None:
            raise HTTPException(422, START_UNPARSED)
    return store.set_story_series(request.app.state.repo, story_id, data.series_id, data.number, start, data.expected_revision,
                                  bible=data.bible)


@router.post('/api/stories/{story_id}/series/refresh')
def story_series_refresh(story_id: str, data: SeriesRefresh, request: Request):
    """«Оновити з попередньої книги»: stales the memory of the book's first scenes, so it runs only with confirm."""
    guard.require_long_prose_for(request.app.state.repo, story_id)
    if not data.confirm:
        raise HTTPException(422, REFRESH_CONFIRM)
    story, warnings = store.refresh_snapshot(request.app.state.repo, story_id, data.expected_revision)
    return {'story': story, 'warnings': warnings}


@router.get('/api/stories/{story_id}/series/facts')
def story_series_facts(story_id: str, request: Request):
    """The records of the book's start memory with their source book and decision (SERIES-S09). Long prose only."""
    guard.require_long_prose_for(request.app.state.repo, story_id)
    try:
        return {'facts': store.start_facts(request.app.state.repo, story_id)}
    except ValueError as error:
        raise HTTPException(404, str(error)) from None


@router.put('/api/stories/{story_id}/series/decisions')
def story_series_decisions(story_id: str, data: SeriesDecisions, request: Request):
    """Past and future decisions of a prequel: stale the memory of the first scenes, so they run only with confirm."""
    guard.require_long_prose_for(request.app.state.repo, story_id)
    if not data.confirm:
        raise HTTPException(422, DECISIONS_CONFIRM)
    try:
        return store.save_decisions(request.app.state.repo, story_id, data.decisions, data.expected_revision)
    except RevisionConflict:
        raise
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


def series_block(repo, story):
    """The `series` block of the story view: only for a book in a series."""
    if not story.series_id:
        return None
    from ..book.series import series_status
    from dataclasses import asdict
    item = store.get_series(repo, story.series_id)
    return {'id': item.id, 'title': item.title, 'number': story.series_number, 'bible': story.series_bible,
            'start': story.series_start,
            'status': asdict(series_status(repo, story))}
