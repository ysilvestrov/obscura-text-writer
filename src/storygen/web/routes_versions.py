import difflib

from fastapi import APIRouter, Request

from ..domain import DomainModel
from ..generation.dependencies import save_manual_draft, save_manual_prose, select_prose
from ..generation.worker import RunRequest
from ..memory.models import MemorySnapshot
from ..memory.service import memory_before, validate_memory
from ..memory.service import save_scene_memory
from ..generation.models import WritersBrief
from ..domain import RevisionConflict

router=APIRouter()


class ProseChange(DomainModel):
    expected_revision: int
    text: str


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
    scene=repo.get_scene(scene_id)
    return {'attempts':[{'id':a.id,'created_at':a.created_at,'state':a.state} for a in repo.list_attempts(scene.story_id)
                        if a.scene_id==scene_id and a.context.get('copyedit_proposal') and a.state in {'completed','needs_review','alternative'}]}


class Rebuild(DomainModel):
    request_id: str


@router.get('/api/scenes/{scene_id}/versions')
def versions(scene_id: str,request: Request):
    repo=request.app.state.repo
    scene=repo.get_scene(scene_id)
    return {'scene':scene,'versions':repo.list_versions(scene.story_id,scene_id),'acceptances':repo.list_acceptances(scene.story_id)}


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
    from ..generation.language import language_warnings, language_suite_hash
    repo=request.app.state.repo
    ref=repo.get_version(id)
    if ref.kind not in {'draft','edited','manual'} or not ref.scene_id:
        raise ValueError('Мовна перевірка доступна лише для збереженої чернетки або прози')
    return {'version_id':ref.id,'sha256':ref.sha256,'stale':ref.stale,'suite_hash':language_suite_hash(),'warnings':language_warnings(repo.read_text(id))}


@router.post('/api/scenes/{scene_id}/prose')
def prose(scene_id: str,body: ProseChange,request: Request):
    ref=save_manual_prose(request.app.state.repo,scene_id,body.text,body.expected_revision)
    return {'version':ref,'scene':request.app.state.repo.get_scene(scene_id)}


@router.post('/api/scenes/{scene_id}/draft')
def manual_draft(scene_id: str,body: ProseChange,request: Request):
    ref=save_manual_draft(request.app.state.repo,scene_id,body.text,body.expected_revision)
    return {'version':ref,'scene':request.app.state.repo.get_scene(scene_id)}


@router.post('/api/scenes/{scene_id}/brief')
def manual_brief(scene_id: str,body: ProseChange,request: Request):
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
    from ..memory.forwarding import hidden_before
    policy=sorted(hidden_before(view,scene_id))
    ref=repo.save_version(scene.story_id,scene_id,'brief',brief.model_dump_json(),list(dict.fromkeys(inputs)),manual_projection_policy=policy)
    if scene.revision!=body.expected_revision:
        raise RevisionConflict('Сцену вже змінено; ваша версія завдання збережена в історії')
    if not brief.proposed_changes:
        scene=repo.set_head(scene_id,'brief',ref.id,body.expected_revision)
    return {'version':ref,'scene':scene,'needs_review':bool(brief.proposed_changes)}


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
