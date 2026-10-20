import re
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from ..application.exports import export_story
from ..domain import DomainModel

router=APIRouter()


class ExportRequest(DomainModel):
    format: Literal['md','txt'] = 'md'
    allow_incomplete: bool = False


@router.post('/api/stories/{id}/export')
def export(id: str,body: ExportRequest,request: Request):
    path=export_story(request.app.state.repo,id,body.format,body.allow_incomplete)
    return {'download_url':f'/api/stories/{id}/exports/{path.name}','manifest_url':f'/api/stories/{id}/exports/{path.with_suffix(".manifest.json").name}'}


@router.get('/api/stories/{id}/exports/{name}')
def download(id: str,name: str,request: Request):
    repo=request.app.state.repo
    repo.get_story(id)
    if not re.fullmatch(r'[0-9a-f]{32}\.(md|txt|manifest\.json)',name):raise KeyError('Немає експорту')
    path=repo.files.resolve(f'stories/{id}/exports/{name}')
    if not path.is_file():raise KeyError('Немає експорту')
    return FileResponse(path,filename=name,media_type='application/octet-stream')
