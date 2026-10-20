import json
from typing import Literal

from fastapi import APIRouter, Request

from ..domain import DomainModel
from ..evaluation.story_adapter import EvaluationSettings, get_evaluation_settings, save_evaluation_settings, queue_evaluation, install_calibration
from ..evaluation.models import EvaluationOutcome
from ..evaluation.models import EvaluatorConfig

router=APIRouter()


class EvaluateRequest(DomainModel):
    scene_id: str | None = None
    mode: str = 'scene'
    request_id: str


class CalibrationImport(DomainModel):
    outcomes: list[EvaluationOutcome]


class EvaluationPolicy(DomainModel):
    policy: Literal['off','report','pause_on_failure']


@router.put('/api/stories/{id}/evaluator/policy')
def policy(id: str,body: EvaluationPolicy,request: Request):
    repo=request.app.state.repo
    repo.get_story(id)
    try:settings=get_evaluation_settings(repo,id)
    except ValueError:
        settings=EvaluationSettings(config=EvaluatorConfig(provider='codex_cli',max_input_chars=100000),context_tokens=128000,policy='off')
    settings.policy=body.policy
    save_evaluation_settings(repo,id,settings)
    return settings


@router.post('/api/stories/{id}/evaluator/calibration')
def calibration(id: str,body: CalibrationImport,request: Request):
    repo=request.app.state.repo
    settings=get_evaluation_settings(repo,id)
    settings.profile=install_calibration(repo,settings.config,body.outcomes)
    save_evaluation_settings(repo,id,settings)
    return settings


@router.get('/api/stories/{id}/evaluator')
def config(id: str,request: Request):
    return get_evaluation_settings(request.app.state.repo,id)


@router.put('/api/stories/{id}/evaluator')
def configure(id: str,body: EvaluationSettings,request: Request):
    save_evaluation_settings(request.app.state.repo,id,body)
    return body


@router.post('/api/stories/{id}/evaluate')
def enqueue(id: str,body: EvaluateRequest,request: Request):
    if body.mode not in {'scene','edit_pair','story'}:raise ValueError('Невідомий режим оцінювання')
    settings=get_evaluation_settings(request.app.state.repo,id)
    if settings.policy=='off':raise ValueError('Оцінювання вимкнено')
    return queue_evaluation(request.app.state.coordinator,id,body.scene_id,body.mode,body.request_id)


@router.get('/api/stories/{id}/evaluations')
def reports(id: str,request: Request):
    repo=request.app.state.repo
    repo.get_story(id)
    return {'evaluations':[{'version':ref,'outcome':json.loads(repo.read_text(ref.id))} for ref in repo.list_versions(id,kind='evaluation')]}
