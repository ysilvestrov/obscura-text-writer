"""Local publication card and public signatures; no model dispatch."""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
from pydantic import Field
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartParser, MultiPartException

from ..domain import DomainModel
from ..publication_models import PublicationData
from ..publication_suggestions import SuggestionAcceptance
from ..publication.covers import MAX_BYTES
from ..publication.genres import genre_catalog

router=APIRouter()


class SignatureCreate(DomainModel):
    display_name: str = Field(min_length=1,max_length=300)


class SignatureUpdate(DomainModel):
    expected_revision: int = Field(ge=0)
    display_name: str | None = Field(default=None,min_length=1,max_length=300)
    archived: bool | None = None


class CardUpdate(DomainModel):
    expected_revision: int = Field(ge=0)
    data: PublicationData
    expected_signature_revisions: dict[str,int] = Field(default_factory=dict)
    suggestion: SuggestionAcceptance | None = None


@router.get('/stories/{story_id}/publication')
def page(story_id: str,request: Request):
    story=request.app.state.repo.get_story(story_id)
    return request.app.state.templates.TemplateResponse(request=request,name='publication.html',
        context={'story':story,'genres':sorted(genre_catalog(),key=lambda g:g[1])})


@router.get('/api/publication-signatures')
def signatures(request: Request,include_archived: bool=False):
    return {'signatures':request.app.state.repo.publication('list_signatures',include_archived=include_archived)}


@router.post('/api/publication-signatures')
def create_signature(body: SignatureCreate,request: Request):
    return request.app.state.repo.publication('create_signature',display_name=body.display_name)


@router.patch('/api/publication-signatures/{id}')
def update_signature(id: str,body: SignatureUpdate,request: Request):
    return request.app.state.repo.publication('update_signature',id=id,**body.model_dump())


@router.get('/api/stories/{story_id}/publication')
def read_card(story_id: str,request: Request):
    return request.app.state.repo.publication('get_card',story_id=story_id)


@router.put('/api/stories/{story_id}/publication')
def save_card(story_id: str,body: CardUpdate,request: Request):
    return request.app.state.repo.publication('save_card',story_id=story_id,**{
        'data':body.data,'expected_revision':body.expected_revision,
        'expected_signature_revisions':body.expected_signature_revisions,'suggestion':body.suggestion})


@router.get('/api/stories/{story_id}/publication/suggestions')
def suggestions(story_id: str,request: Request):
    from ..generation.publication_metadata import suggestions_state
    return suggestions_state(request.app.state.repo,story_id)


@router.get('/api/stories/{story_id}/publication/suggestions/readiness')
def suggestion_readiness(story_id: str,request: Request):
    from ..generation.publication_metadata import readiness
    from ..run_models import RunRequest
    return readiness(request.app.state.repo,RunRequest(story_id=story_id,mode='publication_suggest'))


@router.post('/api/stories/{story_id}/publication/cover')
async def upload_cover(story_id: str,request: Request):
    repo=request.app.state.repo
    repo.get_story(story_id)
    if not request.headers.get('content-type','').lower().startswith('multipart/form-data'):
        raise ValueError('Завантажте файл як multipart/form-data')
    total=0
    async def bounded_stream():
        nonlocal total
        async for chunk in request.stream():
            total+=len(chunk)
            if total>MAX_BYTES+65536:raise MultiPartException('upload_limit')
            yield chunk
    try:
        form=await MultiPartParser(request.headers,bounded_stream(),max_files=1,max_fields=0).parse()
    except MultiPartException as exc:
        if exc.message=='upload_limit':raise HTTPException(413,'Обкладинка має бути до 10 MiB') from None
        raise ValueError('Завантажте один файл обкладинки') from None
    try:
        item=form.get('file')
        if len(form.multi_items())!=1 or not isinstance(item,UploadFile):
            raise ValueError('Оберіть один файл обкладинки')
        content=await item.read(MAX_BYTES+1)
        if len(content)>MAX_BYTES:raise HTTPException(413,'Обкладинка має бути до 10 MiB')
        return repo.publication('upload_cover',story_id=story_id,content=content)
    finally:
        await form.close()


@router.get('/api/stories/{story_id}/publication/covers/{id}')
def cover(story_id: str,id: str,request: Request):
    content,mime=request.app.state.repo.publication('read_cover',story_id=story_id,id=id)
    return Response(content,media_type=mime,headers={'X-Content-Type-Options':'nosniff'})
