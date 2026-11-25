"""MANUSCRIPT-IMPORT: preview, paragraph descriptions and cancel of a manuscript import; no book exists yet (spec §4.1)."""
import re

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from ..application import manuscript_import
from ..publication.manuscript_structure import ParseSettings

router = APIRouter()
_IMPORT_ID = re.compile('[0-9a-f]{32}')
MAX_MARKERS = 20
MAX_MARKER_LENGTH = 40
PROLOGUE = {'uk': 'Пролог', 'en': 'Prologue'}


def _checked(import_id: str) -> str:
    if not _IMPORT_ID.fullmatch(import_id):
        raise KeyError(manuscript_import.NOT_FOUND)
    return import_id


def _markers(form, name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    values = []
    for raw in form.getlist(name):
        if isinstance(raw, str):
            values += [piece.strip() for piece in re.split(r'[\r\n,;]+', raw)]
    values = [value for value in dict.fromkeys(values) if value]
    if not values:
        return default
    if len(values) > MAX_MARKERS or any(len(value) > MAX_MARKER_LENGTH for value in values):
        raise ValueError('Занадто багато або надто довгі маркери глав і частин')
    return tuple(values)


def _settings(form) -> ParseSettings:
    defaults = ParseSettings()
    source = str(form.get('chapter_source') or 'auto')
    if source in ('1', '2', '3'):
        chapter_source = int(source)
    elif source in ('auto', 'markers'):
        chapter_source = source
    else:
        raise ValueError('Невідоме джерело глав')
    language = str(form.get('language') or '')
    return ParseSettings(chapter_markers=_markers(form, 'chapter_markers', defaults.chapter_markers),
                         part_markers=_markers(form, 'part_markers', defaults.part_markers), chapter_source=chapter_source,
                         prologue_title=PROLOGUE.get(language, defaults.prologue_title))


@router.post('/api/manuscript-import/preview')
async def preview(request: Request):
    repo = request.app.state.repo
    if not request.headers.get('content-type', '').lower().startswith('multipart/form-data'):
        raise ValueError('Завантажте файл як multipart/form-data')
    limit = manuscript_import.MAX_FILE
    total = 0

    async def bounded_stream():
        nonlocal total
        async for chunk in request.stream():
            total += len(chunk)
            if total > limit + 65536:
                raise MultiPartException('upload_limit')
            yield chunk
    try:
        form = await MultiPartParser(request.headers, bounded_stream(), max_files=1, max_fields=20).parse()
    except MultiPartException as exc:
        if exc.message == 'upload_limit':
            raise HTTPException(413, str(manuscript_import.ManuscriptTooLarge())) from None
        raise ValueError('Завантажте один файл рукопису') from None
    try:
        settings = _settings(form)
        item = form.get('file')
        import_id = form.get('import_id')
        if isinstance(item, UploadFile):
            if import_id:
                raise ValueError('Передайте або файл, або import_id')
            content = await item.read(limit + 1)
            if len(content) > limit:
                raise HTTPException(413, str(manuscript_import.ManuscriptTooLarge()))
            file_name, import_id = item.filename or '', None
        elif isinstance(import_id, str) and import_id:
            content, file_name = b'', ''
            import_id = _checked(import_id)
        else:
            raise ValueError('Оберіть файл рукопису')
    finally:
        await form.close()
    try:
        return await run_in_threadpool(manuscript_import.preview, repo, content, file_name, settings, import_id)
    except manuscript_import.ManuscriptTooLarge as exc:
        raise HTTPException(413, str(exc)) from None


@router.get('/api/manuscript-import/{import_id}/paragraphs')
async def paragraphs(import_id: str, start: int, end: int, request: Request):
    return await run_in_threadpool(manuscript_import.paragraphs, request.app.state.repo, _checked(import_id), start, end)


@router.delete('/api/manuscript-import/{import_id}', status_code=204)
def cancel(import_id: str, request: Request):
    manuscript_import.discard(request.app.state.repo, _checked(import_id))
    return Response(status_code=204)
