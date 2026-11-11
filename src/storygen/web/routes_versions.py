import difflib
from typing import Literal

from fastapi import APIRouter, Query, Request

from ..domain import DomainModel, ExternalOrigin
from ..generation.dependencies import save_manual_draft, save_manual_prose, select_prose
from ..generation.worker import RunRequest
from ..memory.models import MemorySnapshot
from ..memory.service import memory_before, validate_memory
from ..memory.service import save_scene_memory
from ..generation.models import WritersBrief
from ..domain import RevisionConflict
from ..authoring.comments import CommentPayload
from pydantic import Field,model_validator

router=APIRouter()


class ProseChange(DomainModel):
    expected_revision: int
    text: str


class BriefChange(ProseChange):
    source_brief_id: str | None = None


class AuthorTextChange(ProseChange):
    content_format: Literal['plain','markdown'] | None = None


class DraftChange(AuthorTextChange):
    comment_set: CommentPayload | None = None
    external_origin: ExternalOrigin | None = None
    expected_context_fingerprint: str | None = Field(default=None,pattern=r'^[0-9a-f]{64}$')
    expected_comments_revision: int | None = Field(default=None,ge=0)
    expected_source_version_id: str | None = None
    # MCP-BRIDGE (#108): the draft head the external client read with get_scene_text; null — there was no draft.
    expected_draft_version_id: str | None = Field(default=None,max_length=64)

    @model_validator(mode='after')
    def notes_cas(self):
        if self.comment_set is not None and (self.expected_comments_revision is None or 'expected_source_version_id' not in self.model_fields_set):
            raise ValueError('Коментарі потребують ревізії та джерела')
        if self.comment_set is None and (self.expected_comments_revision is not None or self.expected_source_version_id is not None):
            raise ValueError('Немає набору коментарів')
        if self.comment_set is not None and (self.external_origin is not None or self.expected_context_fingerprint is not None):
            raise ValueError('Чернетка із зовнішнього клієнта не зберігається разом із коментарями')
        if 'expected_draft_version_id' in self.model_fields_set and self.external_origin is None:
            raise ValueError('Ідентифікатор прочитаної чернетки передає лише зовнішній клієнт')
        return self


class Selection(DomainModel):
    expected_revision: int
    version_id: str


class CopyeditSelection(DomainModel):
    expected_revision: int
    proposal_fingerprint: str
    selected_indices: list[int]


class ClassifyProposal(DomainModel):
    request_id: str
    proposal_fingerprint: str
    budget_limit_usd: str | None = None


@router.post('/api/scenes/{scene_id}/copyedits/{attempt_id}/classify')
def classify_copyedits(scene_id: str,attempt_id: str,body: ClassifyProposal,request: Request):
    scene=request.app.state.repo.get_scene(scene_id)
    return request.app.state.coordinator.enqueue(RunRequest(story_id=scene.story_id,scene_id=scene_id,mode='classify',proposal_attempt_id=attempt_id,proposal_fingerprint=body.proposal_fingerprint,budget_limit_usd=body.budget_limit_usd),body.request_id)


@router.post('/api/scenes/{scene_id}/copyedits/{attempt_id}/selection-preview')
def preview_copyedit_selection(scene_id: str,attempt_id: str,body: CopyeditSelection,request: Request):
    from ..generation.copyedit_review import selection_preview
    return selection_preview(request.app.state.repo,scene_id,attempt_id,body.selected_indices,body.expected_revision,body.proposal_fingerprint)


@router.get('/api/scenes/{scene_id}/copyedits/{attempt_id}')
def preview_copyedits(scene_id: str,attempt_id: str,request: Request):
    from ..generation.copyedit_review import copyedit_preview
    return copyedit_preview(request.app.state.repo,scene_id,attempt_id)


@router.post('/api/scenes/{scene_id}/copyedits/{attempt_id}')
def apply_copyedit_selection(scene_id: str,attempt_id: str,body: CopyeditSelection,request: Request):
    from ..generation.copyedit_review import select_copyedits
    return select_copyedits(request.app.state.repo,scene_id,attempt_id,body.selected_indices,body.expected_revision,body.proposal_fingerprint)


@router.get('/api/scenes/{scene_id}/copyedits')
def list_copyedit_proposals(scene_id: str,request: Request):
    repo=request.app.state.repo
    # Only the scene's story and its active state are needed: no context view for an attempt list.
    story_id=repo.active_scene_story_id(scene_id)
    return {'attempts':[{'id':a.id,'created_at':a.created_at,'state':a.state} for a in repo.list_attempts(story_id,scene_id=scene_id,context_key='copyedit_proposal')
                        if a.context.get('copyedit_proposal') and a.state in {'completed','needs_review','alternative'}]}


class Rebuild(DomainModel):
    request_id: str


@router.get('/api/scenes/{scene_id}/versions')
def versions(scene_id: str,request: Request):
    repo=request.app.state.repo
    # One SQL snapshot per request: the scene, its versions and the acceptance journal come from one view.
    view=repo.scene_view(scene_id)
    scene=repo.get_scene(scene_id,view=view)
    return {'scene':scene,'versions':repo.list_versions(scene.story_id,scene_id,view=view),'acceptances':view.list_acceptances(scene.story_id)}


@router.get('/api/versions/compare')
def compare(left: str,right: str,request: Request):
    repo=request.app.state.repo
    if repo.get_version(left).story_id!=repo.get_version(right).story_id:
        raise ValueError('Оберіть версії одного твору')
    a,b=repo.read_text(left),repo.read_text(right)
    return {'left':a,'right':b,'diff':'\n'.join(difflib.unified_diff(a.splitlines(),b.splitlines(),fromfile=left,tofile=right,lineterm=''))}


@router.get('/api/versions/{id}')
def version(id: str,request: Request):
    repo=request.app.state.repo
    return {'version':repo.get_version(id),'text':repo.read_text(id)}


@router.get('/api/versions/{id}/language-warnings')
def check_language(id: str,request: Request):
    from ..generation.language import language_warnings, language_suite_hash, scene_prose_language
    repo=request.app.state.repo
    ref=repo.get_version(id)
    if ref.kind not in {'draft','edited','manual'} or not ref.scene_id:
        raise ValueError('Мовна перевірка доступна лише для збереженої чернетки або прози')
    return {'version_id':ref.id,'sha256':ref.sha256,'stale':ref.stale,'suite_hash':language_suite_hash(),'warnings':language_warnings(repo.read_text(id),scene_prose_language(repo,ref.scene_id))}


@router.post('/api/scenes/{scene_id}/prose')
def prose(scene_id: str,body: AuthorTextChange,request: Request):
    ref=save_manual_prose(request.app.state.repo,scene_id,body.text,body.expected_revision,body.content_format)
    return {'version':ref,'scene':request.app.state.repo.get_scene(scene_id)}


@router.get('/api/scenes/{scene_id}/writing-context')
def scene_writing_context(scene_id: str,request: Request):
    """MCP-BRIDGE: plan, brief, participant cards and preceding memory as the draft stage sees them, plus the context fingerprint."""
    from ..application.writing_context import writing_context
    return writing_context(request.app.state.repo,scene_id)


@router.get('/api/scenes/{scene_id}/text/{material}')
def scene_material_text(scene_id: str,material: Literal['plan','brief','draft','prose','memory'],request: Request,
                        offset: int=Query(default=0,ge=0),max_chars: int=Query(default=20000,ge=1000,le=50000)):
    """MCP-BRIDGE (#108): one material of a scene with its head version, in parts."""
    from ..application.writing_context import scene_text
    return scene_text(request.app.state.repo,scene_id,material,offset,max_chars)


@router.post('/api/scenes/{scene_id}/draft')
def manual_draft(scene_id: str,body: DraftChange,request: Request):
    if body.comment_set is not None:
        repo=request.app.state.repo
        format=body.content_format or (repo.get_version(body.expected_source_version_id).content_format if body.expected_source_version_id else 'plain')
        return repo.save_draft_with_comments(scene_id,body.text,format,body.expected_revision,body.expected_comments_revision,body.comment_set,expected_source_version_id=body.expected_source_version_id)
    read={'expected_draft_version_id':body.expected_draft_version_id} if 'expected_draft_version_id' in body.model_fields_set else {}
    ref=save_manual_draft(request.app.state.repo,scene_id,body.text,body.expected_revision,body.content_format,external_origin=body.external_origin,expected_context_fingerprint=body.expected_context_fingerprint,**read)
    return {'version':ref,'scene':request.app.state.repo.get_scene(scene_id)}


class GhostClientStats(DomainModel):
    peeks: int = Field(default=0,ge=0,le=1_000_000)
    peek_ms: int = Field(default=0,ge=0,le=10**10)
    pastes_blocked: int = Field(default=0,ge=0,le=1_000_000)
    blocks_skipped: int = Field(default=0,ge=0,le=1_000_000)


class GhostRewriteBody(AuthorTextChange):
    source_draft_id: str = Field(min_length=1)
    client_stats: GhostClientStats = Field(default_factory=GhostClientStats)


@router.post('/api/scenes/{scene_id}/ghost-rewrite')
def ghost_rewrite(scene_id: str,body: GhostRewriteBody,request: Request):
    from ..authoring.ghost import save_ghost_rewrite
    repo=request.app.state.repo
    ref=save_ghost_rewrite(repo,scene_id,source_draft_id=body.source_draft_id,text=body.text,content_format=body.content_format,
        expected_revision=body.expected_revision,client_stats=body.client_stats.model_dump())
    return {'version':ref,'scene':repo.get_scene(scene_id)}


@router.post('/api/scenes/{scene_id}/brief')
def manual_brief(scene_id: str,body: BriefChange,request: Request):
    repo=request.app.state.repo
    unchanged=repo.unchanged_scene_text(scene_id,'brief',body.text,body.expected_revision)
    if unchanged:
        return {'version':unchanged[1],'scene':unchanged[0],'needs_review':False}
    owner=repo.get_scene(scene_id)
    view=repo.context_view(owner.story_id)
    scene=view.effective_scene(scene_id)
    brief=WritersBrief.model_validate_json(body.text)
    story=view.get_story(scene.story_id)
    inputs=[id for id in [story.style_version_id,story.canon_version_id,story.characters_version_id] if id]
    for item in view.list_scenes(story.id):
        if item.heads.get('plan'):inputs.append(item.heads['plan'])
        if item.position<scene.position:
            inputs.extend(item.heads[key] for key in ['prose','memory'] if key in item.heads)
    for kind in ['source_plan','source_characters']:
        source=view.active_source(story.id,kind)
        if source:inputs.append(source.id)
    from ..memory.forwarding import projection_policy
    policy=projection_policy(view,scene_id)
    ref=repo.save_version(scene.story_id,scene_id,'brief',brief.model_dump_json(),list(dict.fromkeys(inputs)),manual_projection_policy=policy)
    if scene.revision!=body.expected_revision:
        raise RevisionConflict('Сцену вже змінено; ваша версія завдання збережена в історії')
    accepted_source=body.source_brief_id is not None and body.source_brief_id==scene.heads.get('brief')
    needs_review=bool(brief.proposed_changes) and not accepted_source
    if not needs_review:
        scene=repo.set_head(scene_id,'brief',ref.id,body.expected_revision)
    return {'version':ref,'scene':scene,'needs_review':needs_review}


@router.post('/api/scenes/{scene_id}/select-version')
def select(scene_id: str,body: Selection,request: Request):
    return select_prose(request.app.state.repo,scene_id,body.version_id,body.expected_revision)


@router.post('/api/scenes/{scene_id}/accept-brief')
def accept_brief(scene_id: str,body: Selection,request: Request):
    repo=request.app.state.repo
    scene=repo.set_head(scene_id,'brief',body.version_id,body.expected_revision)
    for attempt in repo.list_attempts(scene.story_id):
        if attempt.result_version_id==body.version_id and attempt.state=='needs_review':
            attempt.state='completed';attempt.error=None;repo.save_attempt(attempt)
    return scene


@router.post('/api/scenes/{scene_id}/accept-draft')
def accept_draft(scene_id: str,body: Selection,request: Request):
    return request.app.state.repo.set_head(scene_id,'draft',body.version_id,body.expected_revision)


@router.post('/api/scenes/{scene_id}/memory')
def manual_memory(scene_id: str,body: ProseChange,request: Request):
    repo=request.app.state.repo
    save_scene_memory(repo,scene_id,body.text,body.expected_revision)
    return repo.get_scene(scene_id)


from ..memory.forwarding import ForwardingChange


@router.get('/api/scenes/{scene_id}/memory-view')
def memory_table(scene_id: str,request: Request):
    from ..memory.forwarding import memory_view
    return memory_view(request.app.state.repo,scene_id)


@router.put('/api/scenes/{scene_id}/memory-view')
def memory_forwarding(scene_id: str,body: ForwardingChange,request: Request):
    from ..memory.forwarding import save_forwarding
    return save_forwarding(request.app.state.repo,scene_id,body.choices,body.expected_revision,body.fingerprint)


@router.post('/api/scenes/{scene_id}/rebuild-memory')
def rebuild(scene_id: str,body: Rebuild,request: Request):
    scene=request.app.state.repo.get_scene(scene_id)
    return request.app.state.coordinator.enqueue(RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='rebuild_memory'),body.request_id)


class AcceptanceSelection(Selection):
    preview_fingerprint: str
    note: str | None = None


@router.get('/api/scenes/{scene_id}/acceptance-preview')
def acceptance_preview(scene_id: str,version_id: str,request: Request):
    return request.app.state.repo.preview_acceptance(scene_id,version_id)


@router.post('/api/scenes/{scene_id}/accept-version')
def accept_version(scene_id: str,body: AcceptanceSelection,request: Request):
    result=request.app.state.repo.accept_version(scene_id,body.version_id,body.expected_revision,body.preview_fingerprint,body.note)
    return {'scene':result.scene,'version':result.version,'acceptance':result.acceptance}


@router.get('/api/scenes/{scene_id}/core-review')
def core_review_view(scene_id: str,request: Request):
    from ..memory.core_review import core_review
    from .localization import request_locale
    return core_review(request.app.state.repo,scene_id,request_locale(request))


from ..memory.core_review import CoreReviewBody


@router.post('/api/scenes/{scene_id}/core-review')
def core_review_apply(scene_id: str,body: CoreReviewBody,request: Request):
    from fastapi.responses import JSONResponse
    from ..memory.core_review import apply_core_review
    from .localization import diagnostic, request_locale
    locale=request_locale(request)
    try:
        return apply_core_review(request.app.state.repo,scene_id,body,locale)
    except RevisionConflict:
        raise
    except ValueError as error:
        # An edit the author must change (keep without a model answer, quote outside the prefix), not malformed data.
        return JSONResponse({'detail':diagnostic(str(error),locale),'detail_original':str(error)},status_code=422)


@router.get('/api/scenes/{scene_id}/core-review/scenes')
def core_review_scenes(scene_id: str,request: Request):
    from ..memory.core_review import prefix_scenes
    return prefix_scenes(request.app.state.repo,scene_id)


@router.get('/api/scenes/{scene_id}/core-review/fragments')
def core_review_fragments(scene_id: str,request: Request,q: str='',source_scene_id: str | None = Query(default=None,alias='scene_id')):
    from fastapi.responses import JSONResponse
    from ..memory.core_review import prefix_fragments
    from .localization import diagnostic, request_locale
    try:
        return prefix_fragments(request.app.state.repo,scene_id,q,source_scene_id)
    except ValueError as error:
        # A query outside the scene prefix is a request the author must change, not malformed data.
        return JSONResponse({'detail':diagnostic(str(error),request_locale(request)),'detail_original':str(error)},status_code=422)
