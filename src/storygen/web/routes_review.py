"""Versioned sequential review commands; every dispatch is explicit."""
from fastapi import APIRouter,Request
from typing import Literal
from pydantic import Field
from ..domain import DomainModel
from ..run_models import RunRequest
from ..review import decisions
from ..review.readiness import readiness

router=APIRouter()


class Start(DomainModel):
    request_id:str=Field(min_length=1,max_length=200)
    fingerprint:str=Field(pattern=r'^[a-f0-9]{64}$')
    budget_limit_usd:str|None=None
    review_contract_version:Literal[3,4]|None=None


class Preview(DomainModel):
    review_contract_version:Literal[3,4]=3


class Priority(DomainModel):
    material:Literal['brief','prose']
    expected_revision:int=Field(ge=0,strict=True)
    operation_id:str=Field(min_length=1,max_length=200)
    preferred:dict|None=None
    superseded:dict|None=None
    revoke_id:str|None=None
    replace_id:str|None=None


class Decision(DomainModel):
    operation_id:str=Field(min_length=1,max_length=200)
    fingerprint:str=Field(pattern=r'^[a-f0-9]{64}$')
    choices:dict[str,str]=Field(default_factory=dict)


@router.post('/api/stories/{story_id}/review/preview')
def preview(story_id:str,request:Request,body:Preview|None=None):
    result=readiness(request.app.state.repo,RunRequest(story_id=story_id,mode='impact',impact_protocol=3,review_contract_version=body.review_contract_version if body else None))
    if result.get('plan'):
        result['plan']=dict(story_id=story_id,fingerprint=result['fingerprint'],targets=[{k:t[k] for k in ['scene_id','scene_title','material','version_id','blockers']} for t in result['plan']['targets']])
    return result


@router.post('/api/stories/{story_id}/review')
def start(story_id:str,body:Start,request:Request):
    return request.app.state.coordinator.enqueue(RunRequest(story_id=story_id,mode='impact',impact_protocol=3,review_contract_version=body.review_contract_version,impact_plan_fingerprint=body.fingerprint,budget_limit_usd=body.budget_limit_usd),body.request_id)


@router.get('/api/stories/{story_id}/review/priorities/{scene_id}')
def priorities(story_id:str,scene_id:str,request:Request):
    return request.app.state.repo.review('priorities',story_id=story_id,scene_id=scene_id)


@router.post('/api/stories/{story_id}/review/priorities/{scene_id}')
def priority(story_id:str,scene_id:str,body:Priority,request:Request):
    return request.app.state.repo.review('priority_decide',story_id=story_id,scene_id=scene_id,**body.model_dump())


@router.get('/api/stories/{story_id}/review/{run_id}')
def current(story_id:str,run_id:str,request:Request):
    return decisions.preview(request.app.state.repo,story_id,run_id)


@router.post('/api/stories/{story_id}/review/{run_id}/decide')
def decide(story_id:str,run_id:str,body:Decision,request:Request):
    return decisions.decide(request.app.state.coordinator,story_id,run_id,body.fingerprint,body.operation_id,body.choices)


@router.post('/api/stories/{story_id}/review/{run_id}/finish')
def finish(story_id:str,run_id:str,body:Decision,request:Request):
    if body.choices:raise ValueError('Завершення використовує вже збережені рішення')
    return decisions.finish(request.app.state.coordinator,story_id,run_id,body.fingerprint,body.operation_id)
