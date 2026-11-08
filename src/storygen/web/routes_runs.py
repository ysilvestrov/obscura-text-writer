import asyncio
import json
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ..domain import DomainModel
from ..run_models import run_summary
from ..generation.worker import RunRequest, TERMINAL

router=APIRouter()


class Enqueue(DomainModel):
    request_id: str
    request: RunRequest


class Resume(DomainModel):
    repeat_interrupted: bool = False


class Prepare(DomainModel):
    request_id: str


@router.post('/api/runs')
def enqueue(body: Enqueue,request: Request):
    return request.app.state.coordinator.enqueue(body.request,body.request_id)


@router.post('/api/runs/cancel-request')
def cancel_request(body: Enqueue,request: Request):
    return request.app.state.coordinator.cancel_request(body.request,body.request_id)


@router.get('/api/stories/{story_id}/runs')
def story_runs(story_id: str,request: Request):
    return {'runs':[run_summary(run) for run in request.app.state.coordinator.list_runs(story_id)]}


@router.get('/api/stories/{story_id}/readiness')
def readiness(story_id: str,request: Request,scene_id: str | None = None,
              editor_source_head: Literal['draft','prose'] | None = None,editor_source_version_id: str | None = None,
              operation: Literal['prepare','brief','draft','edit','memory','scene','remaining','rebuild_memory','edit_loop'] | None = None):
    return request.app.state.coordinator.readiness(story_id,scene_id,editor_source_head,editor_source_version_id,operation)


@router.post('/api/stories/{story_id}/prepare')
def prepare(story_id: str,body: Prepare,request: Request):
    return request.app.state.coordinator.enqueue(RunRequest(story_id=story_id,mode='prepare'),body.request_id)


def _public_attempt(attempt):
    data=attempt.model_dump(exclude={'context'})
    # Only the app-written memory diagnostics leave the context: labels and codes, never model values.
    violations=attempt.context.get('memory_violations')
    if isinstance(violations,dict):data['memory_violations']=violations
    warnings=attempt.context.get('memory_warnings')
    if isinstance(warnings,list):data['memory_warnings']=warnings
    return data


@router.get('/api/runs/{id}')
def get_run(id: str,request: Request):
    worker=request.app.state.coordinator
    run=worker.get_run(id)
    attempts=worker.repo.list_attempts(run.story_id,run.id)
    # Exact manifests are server-side; only public metadata and output appear in the UI.
    public=[_public_attempt(a) for a in attempts]
    partial=worker.repo.files.read_partial(attempts[-1].partial_path) if attempts else ''
    return {'run':run,'attempts':public,'partial':partial}


@router.get('/api/runs/{id}/readiness')
def run_readiness(id: str,request: Request):
    return request.app.state.coordinator.run_readiness(id)


@router.post('/api/runs/{id}/pause')
def pause(id: str,request: Request):
    return request.app.state.coordinator.pause(id)


@router.post('/api/runs/{id}/cancel')
def cancel(id: str,request: Request):
    return request.app.state.coordinator.cancel(id)


@router.post('/api/runs/{id}/resume')
def resume(id: str,body: Resume,request: Request):
    return request.app.state.coordinator.resume(id,body.repeat_interrupted)


@router.get('/api/runs/{id}/events')
async def events(id: str,request: Request,after: int = 0,once: bool = False):
    worker=request.app.state.coordinator
    worker.get_run(id)
    last=request.headers.get('last-event-id')
    try:
        cursor=max(after,int(last or 0))
    except ValueError:
        raise ValueError('Некоректний event ID') from None
    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            for event in worker.list_events(id,cursor):
                cursor=event.seq
                yield f'id: {event.seq}\ndata: {event.model_dump_json()}\n\n'
            if once or worker.get_run(id).state in TERMINAL:
                return
            yield ': keepalive\n\n'
            await asyncio.sleep(.3)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})


class ContinueAccepted(DomainModel):
    version_id: str
    expected_cursor: int
    expected_scene_revision: int
    acceptance_id: str | None = None


@router.post('/api/runs/{id}/continue-after-acceptance')
def continue_after_acceptance(id: str,body: ContinueAccepted,request: Request):
    return request.app.state.coordinator.continue_after_acceptance(id,body.version_id,body.expected_cursor,body.expected_scene_revision,body.acceptance_id)
