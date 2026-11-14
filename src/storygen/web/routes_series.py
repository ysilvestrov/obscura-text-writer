"""SERIES API: series of books and the series fields of a book. Long prose only (BUILD-EDITION-001)."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

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
    outside += [b.id for b in books if b.trashed_at]
    rows = [{'id': b.id, 'title': b.title, 'number': b.series_number, 'trashed': bool(b.trashed_at), 'start': b.series_start,
             'status': asdict(series_status(repo, b))} for b in books]
    return {'series': item, 'books': rows, 'placed': placed, 'outside': outside}


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
    _long_prose_page()
    store.get_series(request.app.state.repo, series_id)
    return request.app.state.templates.TemplateResponse(request=request, name='series.html', context={'series_id': series_id})


@router.post('/api/series')
def series_create(data: SeriesIn, request: Request):
    require_long_prose()
    return store.create_series(request.app.state.repo, data.title)


@router.patch('/api/series/{series_id}')
def series_rename(series_id: str, data: SeriesRename, request: Request):
    require_long_prose()
    return store.rename_series(request.app.state.repo, series_id, data.title, data.expected_revision)


@router.delete('/api/series/{series_id}')
def series_delete(series_id: str, expected_revision: int, request: Request):
    require_long_prose()
    store.delete_series(request.app.state.repo, series_id, expected_revision)
    return {'deleted': series_id}


@router.post('/api/series/{series_id}/books')
def series_new_book(series_id: str, data: SeriesIn, request: Request):
    require_long_prose()
    store.get_series(request.app.state.repo, series_id)
    return store.create_book(request.app.state.repo, series_id, data.title)


@router.patch('/api/stories/{story_id}/series')
def story_series(story_id: str, data: StorySeries, request: Request):
    require_long_prose()
    start = data.start
    if data.start_text and data.start_text.strip():
        from ..plan_sections import parse_series_start
        start = parse_series_start(data.start_text)
        if start is None:
            raise HTTPException(422, START_UNPARSED)
    return store.set_story_series(request.app.state.repo, story_id, data.series_id, data.number, start, data.expected_revision)


@router.post('/api/stories/{story_id}/series/refresh')
def story_series_refresh(story_id: str, data: SeriesRefresh, request: Request):
    """«Оновити з попередньої книги»: stales the memory of the book's first scenes, so it runs only with confirm."""
    require_long_prose()
    if not data.confirm:
        raise HTTPException(422, REFRESH_CONFIRM)
    story, warnings = store.refresh_snapshot(request.app.state.repo, story_id, data.expected_revision)
    return {'story': story, 'warnings': warnings}


@router.get('/api/stories/{story_id}/series/facts')
def story_series_facts(story_id: str, request: Request):
    """The records of the book's start memory with their source book and decision (SERIES-S09). Long prose only."""
    require_long_prose()
    try:
        return {'facts': store.start_facts(request.app.state.repo, story_id)}
    except ValueError as error:
        raise HTTPException(404, str(error)) from None


@router.put('/api/stories/{story_id}/series/decisions')
def story_series_decisions(story_id: str, data: SeriesDecisions, request: Request):
    """Past and future decisions of a prequel: stale the memory of the first scenes, so they run only with confirm."""
    require_long_prose()
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
    return {'id': item.id, 'title': item.title, 'number': story.series_number, 'start': story.series_start,
            'status': asdict(series_status(repo, story))}
