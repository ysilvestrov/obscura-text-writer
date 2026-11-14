"""SERIES API: series of books and the series fields of a book. Long prose only (BUILD-EDITION-001)."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

from ..book.guard import require_long_prose
from ..domain import DomainModel, SeriesStart
from ..storage import series as store

router = APIRouter()
REFRESH_CONFIRM = 'Оновлення робить застарілою пам’ять перших сцен книги; підтвердьте його'



class SeriesIn(DomainModel):
    title: str = Field(min_length=1, max_length=300)


class SeriesRename(SeriesIn):
    expected_revision: int


class SeriesRefresh(DomainModel):
    expected_revision: int
    confirm: bool = False


class StorySeries(DomainModel):
    series_id: str | None = Field(default=None, min_length=1, max_length=64)
    number: int | None = Field(default=None, ge=1, le=1000000)
    start: SeriesStart | None = None
    expected_revision: int


@router.get('/api/series')
def series_list(request: Request):
    return store.list_series(request.app.state.repo)


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
    return store.set_story_series(request.app.state.repo, story_id, data.series_id, data.number, data.start, data.expected_revision)


@router.post('/api/stories/{story_id}/series/refresh')
def story_series_refresh(story_id: str, data: SeriesRefresh, request: Request):
    """«Оновити з попередньої книги»: stales the memory of the book's first scenes, so it runs only with confirm."""
    require_long_prose()
    if not data.confirm:
        raise HTTPException(422, REFRESH_CONFIRM)
    story, warnings = store.refresh_snapshot(request.app.state.repo, story_id, data.expected_revision)
    return {'story': story, 'warnings': warnings}


def series_block(repo, story):
    """The `series` block of the story view: only for a book in a series."""
    if not story.series_id:
        return None
    from ..book.series import series_status
    from dataclasses import asdict
    item = store.get_series(repo, story.series_id)
    return {'id': item.id, 'title': item.title, 'number': story.series_number, 'start': story.series_start,
            'status': asdict(series_status(repo, story))}
