"""EDITOR-IMPORT: the preview, save and cancel of an editor's DOCX; no model dispatch."""
import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.datastructures import UploadFile
from starlette.concurrency import run_in_threadpool
from starlette.formparsers import MultiPartException, MultiPartParser

from ..application import editor_import
from ..domain import DomainModel
from ..publication import docx_import

router = APIRouter()
_IMPORT_ID = re.compile('[0-9a-f]{32}')


def _too_large() -> str:
    return f'Файл має бути до {docx_import.MAX_FILE / (1024 * 1024):g} MiB'


class ImportApply(DomainModel):
    fingerprint: str
    changed_scenes: Literal['skip', 'replace'] | None = None


def _checked(import_id: str) -> str:
    if not _IMPORT_ID.fullmatch(import_id):
        raise KeyError('Імпорт не знайдено')
    return import_id


@router.post('/api/stories/{story_id}/editor-import/preview')
async def preview(story_id: str, request: Request):
    repo = request.app.state.repo
    repo.get_story(story_id)
    if not request.headers.get('content-type', '').lower().startswith('multipart/form-data'):
        raise ValueError('Завантажте файл як multipart/form-data')
    limit = docx_import.MAX_FILE
    total = 0

    async def bounded_stream():
        nonlocal total
        async for chunk in request.stream():
            total += len(chunk)
            if total > limit + 65536:
                raise MultiPartException('upload_limit')
            yield chunk
    try:
        form = await MultiPartParser(request.headers, bounded_stream(), max_files=1, max_fields=0).parse()
    except MultiPartException as exc:
        if exc.message == 'upload_limit':
            raise HTTPException(413, _too_large()) from None
        raise ValueError('Завантажте один файл DOCX') from None
    try:
        item = form.get('file')
        if len(form.multi_items()) != 1 or not isinstance(item, UploadFile):
            raise ValueError('Оберіть один файл DOCX')
        content = await item.read(limit + 1)
        if len(content) > limit:
            raise HTTPException(413, _too_large())
    finally:
        await form.close()
    return await run_in_threadpool(editor_import.preview_import, repo, story_id, content)


@router.post('/api/stories/{story_id}/editor-import/{import_id}')
def apply(story_id: str, import_id: str, body: ImportApply, request: Request):
    return editor_import.apply_import(request.app.state.repo, story_id, _checked(import_id), body.fingerprint,
                                      body.changed_scenes)


@router.delete('/api/stories/{story_id}/editor-import/{import_id}', status_code=204)
def cancel(story_id: str, import_id: str, request: Request):
    editor_import.cancel_import(request.app.state.repo, story_id, _checked(import_id))
    return Response(status_code=204)
