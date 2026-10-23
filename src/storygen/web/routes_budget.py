from typing import Literal
from fastapi import APIRouter, Request
from ..domain import DomainModel
from ..billing.models import Tariff, money
from ..billing.service import set_limit, summary, save_tariff
from ..providers.models import ProviderSettings

router=APIRouter()


class BudgetChange(DomainModel):
    expected_revision:int
    limit_usd:str
    default_run_limit_usd:str|None=None


class PriceChange(DomainModel):
    provider:Literal['venice','openrouter']
    model:str
    refresh:bool=False
    input_per_million:str|None=None
    output_per_million:str|None=None
    request_usd:str='0'
    source:str|None=None
    expires_at:str|None=None


class Reconcile(DomainModel):
    amount_usd:str
    source:str


def scope(request,id):
    request.app.state.repo.get_story(id)
    return 'story:'+id


@router.get('/api/stories/{id}/budget')
def read_budget(id:str,request:Request):
    return summary(request.app.state.repo,scope(request,id))


@router.put('/api/stories/{id}/budget')
def write_budget(id:str,body:BudgetChange,request:Request):
    owner=scope(request,id)
    set_limit(request.app.state.repo,owner,body.limit_usd,body.expected_revision,body.default_run_limit_usd)
    return summary(request.app.state.repo,owner)


@router.get('/api/stories/{id}/budget/calls')
def read_calls(id:str,request:Request):
    return request.app.state.repo.billing('calls',scope=scope(request,id))


@router.post('/api/stories/{id}/budget/prices')
def prices(id:str,body:PriceChange,request:Request):
    scope(request,id)
    config=ProviderSettings(provider=body.provider,model=body.model)
    if body.refresh:
        from ..billing.pricing import refresh
        from ..providers.client import build_openai_client
        with build_openai_client(config) as client:
            return refresh(request.app.state.repo,config,client)
    tariff=Tariff(provider=body.provider,model=body.model,base_url=config.base_url,
        input_per_million=body.input_per_million,output_per_million=body.output_per_million,
        request_usd=body.request_usd,source=body.source,expires_at=body.expires_at,kind='manual')
    return save_tariff(request.app.state.repo,tariff)


@router.post('/api/stories/{id}/budget/calls/{call_id}/reconcile')
def reconcile(id:str,call_id:str,body:Reconcile,request:Request):
    return request.app.state.repo.billing('manual',scope=scope(request,id),call_id=call_id,
        amount_nanos=money(body.amount_usd),source=body.source)
