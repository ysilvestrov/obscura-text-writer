from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import Response

from ..application.exports import export_story,download_export
from ..domain import DomainModel

router=APIRouter()


class ExportRequest(DomainModel):
    format: Literal['md','txt','fb2','epub','pdf'] = 'md'
    allow_incomplete: bool = False


@router.post('/api/stories/{id}/export')
def export(id: str,body: ExportRequest,request: Request):
    path=export_story(request.app.state.repo,id,body.format,body.allow_incomplete)
    return {'download_url':f'/api/stories/{id}/exports/{path.name}','manifest_url':f'/api/stories/{id}/exports/{path.with_suffix(".manifest.json").name}'}


@router.get('/api/stories/{id}/exports/{name}')
def download(id: str,name: str,request: Request):
    content=download_export(request.app.state.repo,id,name)
    extension=name.rsplit('.',1)[-1]
    mime={'pdf':'application/pdf','epub':'application/epub+zip','fb2':'application/x-fictionbook+xml','json':'application/json','md':'text/markdown','txt':'text/plain'}[extension]
    return Response(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="{name}"'})
