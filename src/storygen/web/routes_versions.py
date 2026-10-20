import difflib

from fastapi import APIRouter, Request

from ..domain import DomainModel
from ..generation.dependencies import save_manual_draft, save_manual_prose, select_prose
from ..generation.worker import RunRequest
from ..memory.models import MemorySnapshot
from ..memory.service import memory_before, validate_memory
from ..generation.models import WritersBrief
from ..domain import RevisionConflict

router=APIRouter()


class ProseChange(DomainModel):
    expected_revision: int
    text: str


class Selection(DomainModel):
    expected_revision: int
    version_id: str


class Rebuild(DomainModel):
    request_id: str


@router.get('/api/scenes/{scene_id}/versions')
def versions(scene_id: str,request: Request):
    repo=request.app.state.repo
    scene=repo.get_scene(scene_id)
    return {'scene':scene,'versions':repo.list_versions(scene.story_id,scene_id)}


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
    scene=repo.get_scene(scene_id)
    brief=WritersBrief.model_validate_json(body.text)
    story=repo.get_story(scene.story_id)
    inputs=[id for id in [story.style_version_id,story.canon_version_id,story.characters_version_id] if id]
    for item in repo.list_scenes(story.id):
        if item.heads.get('plan'):inputs.append(item.heads['plan'])
        if item.position<scene.position:
            inputs.extend(item.heads[key] for key in ['prose','memory'] if key in item.heads)
    for kind in ['source_plan','source_characters']:
        source=repo.active_source(story.id,kind)
        if source:inputs.append(source.id)
    ref=repo.save_version(scene.story_id,scene_id,'brief',brief.model_dump_json(),list(dict.fromkeys(inputs)))
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
    scene=repo.get_scene(scene_id)
    if scene.revision!=body.expected_revision:
        raise RevisionConflict('Пам’ять або прозу сцени вже оновлено. Відкрийте вкладку «Пам’ять» заново; незбережені правки спершу скопіюйте окремо.')
    previous=memory_before(repo,scene_id)
    sources={id:repo.read_text(id) for id in previous.source_prose_ids}
    if 'prose' not in scene.heads:
        raise ValueError('Спершу виберіть прозу')
    sources[scene.heads['prose']]=repo.read_text(scene.heads['prose'])
    snapshot=MemorySnapshot.model_validate_json(body.text)
    if snapshot.source_prose_ids!=list(sources):
        raise ValueError('Ця пам’ять посилається на іншу версію прози. Відкрийте актуальну вкладку «Пам’ять» або згенеруйте її кнопкою «Оновити пам’ять». Ваші правки в редакторі не змінено.')
    validate_memory(snapshot,sources)
    ref=repo.save_version(scene.story_id,scene_id,'memory',snapshot.model_dump_json(),list(sources))
    return repo.set_head(scene_id,'memory',ref.id,body.expected_revision)


@router.post('/api/scenes/{scene_id}/rebuild-memory')
def rebuild(scene_id: str,body: Rebuild,request: Request):
    scene=request.app.state.repo.get_scene(scene_id)
    return request.app.state.coordinator.enqueue(RunRequest(story_id=scene.story_id,scene_id=scene.id,mode='rebuild_memory'),body.request_id)
