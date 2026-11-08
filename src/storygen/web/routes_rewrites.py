from fastapi import APIRouter,Request
from ..domain import DomainModel
from ..run_models import RunRequest
from ..generation.rewrite_review import rewrite_preview,selection_preview,apply_selection

router=APIRouter()

class Selection(DomainModel):
    expected_revision:int
    expected_comments_revision:int
    proposal_fingerprint:str
    selected_indices:list[int]

class RewriteSource(DomainModel):
    source_version_id:str
    comment_set_id:str
    comment_fingerprint:str

@router.post('/api/scenes/{scene_id}/rewrites/preflight')
def preflight(scene_id:str,body:RewriteSource,request:Request):
    from ..generation.assisted_writing import readiness
    repo=request.app.state.repo;scene=repo.get_scene(scene_id)
    return readiness(repo,RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='rewrite',**body.model_dump()))

@router.get('/api/scenes/{scene_id}/rewrites')
def list_rewrites(scene_id:str,request:Request):
    # Only the scene's story and its active state are needed: no context view for an attempt list.
    repo=request.app.state.repo;story_id=repo.active_scene_story_id(scene_id)
    return {'attempts':[dict(id=a.id,created_at=a.created_at,state=a.state) for a in repo.list_attempts(story_id,scene_id=scene_id,context_key='rewrite_proposal') if a.context.get('rewrite_proposal')]}

@router.get('/api/scenes/{scene_id}/rewrites/{attempt_id}')
def preview(scene_id:str,attempt_id:str,request:Request):
    return rewrite_preview(request.app.state.repo,scene_id,attempt_id)

@router.post('/api/scenes/{scene_id}/rewrites/{attempt_id}/selection-preview')
def preview_selection(scene_id:str,attempt_id:str,body:Selection,request:Request):
    return selection_preview(request.app.state.repo,scene_id,attempt_id,body.selected_indices,body.expected_revision,body.proposal_fingerprint,body.expected_comments_revision)

@router.post('/api/scenes/{scene_id}/rewrites/{attempt_id}')
@router.post('/api/scenes/{scene_id}/rewrites/{attempt_id}/apply')
def apply(scene_id:str,attempt_id:str,body:Selection,request:Request):
    return apply_selection(request.app.state.repo,scene_id,attempt_id,body.selected_indices,body.expected_revision,body.proposal_fingerprint,body.expected_comments_revision)
