from fastapi import APIRouter, Request

from ..domain import DomainModel
from ..providers.models import ProviderSettings
from ..providers.policy import POLICY_ROLES, endpoint

router=APIRouter()


class PolicyTarget(DomainModel):
    role: str
    provider: str
    model: str
    base_url: str | None = None


def _args(target: PolicyTarget):
    if target.role not in POLICY_ROLES:raise ValueError('Невідома роль')
    settings=ProviderSettings(provider=target.provider,model=target.model,base_url=target.base_url)
    return dict(role=target.role,provider=settings.provider,base_url=endpoint(settings),model=settings.model)


def _state(repo,args):
    consent=repo.model_policy('get_consent',**args)
    refusal=repo.model_policy('get_refusal',**args)
    return {
        'consent':{'consented_at':consent['consented_at']} if consent else None,
        'refusals':[{'rating':item['rating'],'at':item['at'],'category':item['category'],
            'story_id':item['story_id'],'scene_id':item.get('scene_id')} for item in (refusal or {}).get('refusals',[])],
    }


def _target(role: str,provider: str,model: str,base_url: str | None=None):
    return PolicyTarget(role=role,provider=provider,model=model,base_url=base_url)


@router.get('/api/model-policy')
def read_policy(request: Request,role: str,provider: str,model: str,base_url: str | None=None):
    return _state(request.app.state.repo,_args(_target(role,provider,model,base_url)))


@router.put('/api/model-policy/consent')
def grant_consent(target: PolicyTarget,request: Request):
    repo=request.app.state.repo
    args=_args(target)
    repo.model_policy('set_consent',**args)
    return _state(repo,args)


@router.delete('/api/model-policy/consent')
def clear_consent(request: Request,role: str,provider: str,model: str,base_url: str | None=None):
    repo=request.app.state.repo
    args=_args(_target(role,provider,model,base_url))
    repo.model_policy('delete_consent',**args)
    return _state(repo,args)


@router.delete('/api/model-policy/refusal')
def clear_refusal(request: Request,role: str,provider: str,model: str,base_url: str | None=None):
    repo=request.app.state.repo
    args=_args(_target(role,provider,model,base_url))
    repo.model_policy('delete_refusal',**args)
    return _state(repo,args)
