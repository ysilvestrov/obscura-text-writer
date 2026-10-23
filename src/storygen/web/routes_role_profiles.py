from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import Field

from ..domain import DomainModel
from ..role_profiles import MAX_BYTES, capture_profile, preview_profile, apply_profile, export_profile, parse_profile

router=APIRouter()


class CaptureRequest(DomainModel):
    name: str = Field(min_length=1,max_length=100)
    expected_revision: int = Field(ge=0)
    include_evaluator: bool = False
    profile_id: str | None = None
    expected_version: int | None = Field(default=None,ge=1)


class ProfileSelection(DomainModel):
    profile_id: str
    version: int = Field(ge=1)
    expected_revision: int = Field(ge=0)


@router.get('/api/role-profiles')
def profiles(request: Request):
    return {'profiles':request.app.state.repo.role_profiles('list')}


@router.post('/api/role-profiles/import')
async def import_document(request: Request):
    chunks=[];size=0
    async for chunk in request.stream():
        size+=len(chunk)
        if size>MAX_BYTES:return JSONResponse({'detail':'Файл профілю перевищує 2 MiB'},status_code=413)
        chunks.append(chunk)
    try:raw=b''.join(chunks).decode('utf-8')
    except UnicodeError:raise ValueError('Потрібен JSON у кодуванні UTF-8') from None
    document=parse_profile(raw)
    return request.app.state.repo.role_profiles('save',document=document.model_dump())


@router.get('/api/role-profiles/{profile_id}/versions/{version}')
def read(profile_id: str,version: int,request: Request):
    return request.app.state.repo.role_profiles('read',profile_id=profile_id,version=version)


@router.get('/api/role-profiles/{profile_id}/versions/{version}/export')
def export(profile_id: str,version: int,request: Request):
    raw=export_profile(request.app.state.repo,profile_id,version)
    return Response(raw,media_type='application/json',headers={'Content-Disposition':'attachment; filename="obscura-role-profile.json"'})


@router.post('/api/stories/{story_id}/role-profiles/capture')
def capture(story_id: str,body: CaptureRequest,request: Request):
    return capture_profile(request.app.state.repo,story_id,**body.model_dump())


@router.post('/api/stories/{story_id}/role-profiles/preview')
def preview(story_id: str,body: ProfileSelection,request: Request):
    return preview_profile(request.app.state.repo,story_id,**body.model_dump())


@router.post('/api/stories/{story_id}/role-profiles/apply')
def apply(story_id: str,body: ProfileSelection,request: Request):
    return apply_profile(request.app.state.repo,story_id,**body.model_dump())
