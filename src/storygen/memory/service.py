from .models import MemorySnapshot


def merge_memory_delta(previous, delta, prose_id: str, prose: str) -> MemorySnapshot:
    from .models import MemoryEntry
    from ..generation.evidence import fragment_text
    if prose_id in previous.source_prose_ids:
        raise ValueError('Джерело пам’яті вже враховане')
    fragments = {f.id: f for f in fragment_text(prose)}
    result = previous.model_copy(deep=True)
    result.source_prose_ids.append(prose_id)
    for field in ('facts', 'character_states', 'open_threads', 'timeline'):
        for claim in getattr(delta, field):
            fragment = fragments.get(claim.evidence_id)
            if fragment is None:
                raise ValueError('Невідомий фрагмент підтвердження пам’яті')
            entry = MemoryEntry(text=claim.text, source_version_id=prose_id, quote=fragment.text)
            if entry not in getattr(result, field):
                getattr(result, field).append(entry)
    return result


def validate_memory(snapshot: MemorySnapshot,source_versions: dict[str,str]) -> MemorySnapshot:
    if len(set(snapshot.source_prose_ids))!=len(snapshot.source_prose_ids) or snapshot.source_prose_ids!=list(source_versions):
        raise ValueError('Пам’ять повинна посилатися на всі поточні джерела прози')
    for field in ('facts','character_states','open_threads','timeline'):
        for entry in getattr(snapshot,field):
            text=source_versions.get(entry.source_version_id)
            if text is None or entry.quote not in text:
                raise ValueError('Запис пам’яті не має дослівного підтвердження у прозі')
    return snapshot


def memory_before(repo,scene_id: str) -> MemorySnapshot:
    scene=repo.get_scene(scene_id)
    previous=[s for s in repo.list_scenes(scene.story_id) if s.position<scene.position]
    if not previous:
        return MemorySnapshot()
    selected={}
    for item in previous:
        prose_id=item.heads.get('prose')
        if not prose_id:
            raise ValueError('Потрібні актуальна проза й пам’ять попередніх сцен')
        selected[prose_id]=repo.read_text(prose_id)
    memory_id=previous[-1].heads.get('memory')
    if not memory_id or repo.get_version(memory_id).stale:
        raise ValueError('Спершу оновіть пам’ять попередньої сцени')
    snapshot=MemorySnapshot.model_validate_json(repo.read_text(memory_id))
    try:
        return validate_memory(snapshot,selected)
    except ValueError:
        raise ValueError('Попередня пам’ять не відповідає вибраній прозі; оновіть пам’ять') from None


def rebuild_memory(repo,from_scene_id: str,gateway_factory,cancel,on_event,settings=None,run_id=None):
    from ..authoring.blueprints import get_role_settings
    from ..generation.context import build_context
    from ..generation.stages import execute_stage
    first=repo.get_scene(from_scene_id)
    role=settings or get_role_settings(repo,first.story_id)['memory']
    attempts=[]
    for scene in repo.list_scenes(first.story_id):
        if scene.position<first.position:
            continue
        if cancel.is_set() or not scene.heads.get('prose'):
            break
        # A stale prose is retained for author review. Explicit rebuild accepts its selected text.
        context=build_context(repo,scene.id,'memory',role)
        attempt=execute_stage(repo,scene.id,'memory',context,gateway_factory(role.provider),cancel,lambda text:on_event('delta',{'text':text}),run_id)
        attempts.append(attempt)
        on_event('stage_finished',{'attempt_id':attempt.id,'state':attempt.state})
        if attempt.state!='completed':
            break
    return attempts
