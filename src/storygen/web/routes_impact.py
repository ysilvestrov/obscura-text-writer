"""Explicit impact analysis preview, queue dispatch and report rejection."""
from fastapi import APIRouter,Request
from pydantic import Field
from ..domain import DomainModel
from ..run_models import RunRequest
from ..impact.planning import plan_impact
from ..impact.presentation import scene_status,public_record
from ..generation.impact_context import readiness

router=APIRouter()


class Start(DomainModel):
    request_id: str = Field(min_length=1,max_length=200)
    fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    budget_limit_usd: str | None = None


def _target(target):
    return dict(scene_id=target.scene_id,scene_title=target.scene_title,material=target.material,version_id=target.version_id,blockers=target.blockers)


@router.get('/api/stories/{story_id}/impact')
def overview(story_id:str,request:Request):
    from ..review.capture import plan_review
    repo=request.app.state.repo;view=repo.context_view(story_id);plan=plan_review(view)
    records=repo.impact('state',story_id=story_id)
    return dict(review_protocols=[1,2,3],pending=[_target(t) for t in plan.targets],reports=[public_record(row['record'],row['current'],row['memory_needs_update'],repo.get_attempt(row['record'].delta_attempt_id).context.get('impact_result'),row['memory_check_current'],row['memory_evidence_status']) for row in records],scene_status=scene_status(view))


@router.post('/api/stories/{story_id}/impact/preview')
def preview(story_id:str,request:Request):
    result=readiness(request.app.state.repo,RunRequest(story_id=story_id,mode='impact'))
    if result.get('plan'):
        from ..impact.models import ImpactPlan
        plan=ImpactPlan.model_validate(result['plan'])
        manifest=result.pop('chunk_manifest',None)
        result['plan']=dict(story_id=story_id,fingerprint=manifest['fingerprint'] if manifest else plan.fingerprint,targets=[_target(t) for t in plan.targets])
    return result


@router.post('/api/stories/{story_id}/impact')
def start(story_id:str,body:Start,request:Request):
    return request.app.state.coordinator.enqueue(RunRequest(story_id=story_id,mode='impact',impact_plan_fingerprint=body.fingerprint,budget_limit_usd=body.budget_limit_usd),body.request_id)


@router.post('/api/stories/{story_id}/impact/{record_id}/reject')
def reject(story_id:str,record_id:str,request:Request):
    return request.app.state.repo.impact('reject_report',story_id=story_id,record_id=record_id)
