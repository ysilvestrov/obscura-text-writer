from .models import MemorySnapshot
from .journal import MemoryJournal, load_memory, legacy_view, validate_memory_journal, normalize_manual_memory


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
    if isinstance(snapshot,MemoryJournal):
        return validate_memory_journal(snapshot,source_versions)
    if len(set(snapshot.source_prose_ids))!=len(snapshot.source_prose_ids) or snapshot.source_prose_ids!=list(source_versions):
        raise ValueError('Пам’ять повинна посилатися на всі поточні джерела прози')
    for field in ('facts','character_states','open_threads','timeline'):
        for entry in getattr(snapshot,field):
            text=source_versions.get(entry.source_version_id)
            if text is None or entry.quote not in text:
                raise ValueError('Запис пам’яті не має дослівного підтвердження у прозі')
    return snapshot


def journal_before(repo,scene_id: str) -> MemoryJournal:
    scene=repo.get_scene(scene_id)
    previous=[s for s in repo.list_scenes(scene.story_id) if s.position<scene.position]
    if not previous:
        return MemoryJournal()
    selected={}
    for item in previous:
        prose_id=item.heads.get('prose')
        if not prose_id:
            raise ValueError('Потрібні актуальна проза й пам’ять попередніх сцен')
        selected[prose_id]=repo.read_text(prose_id)
    memory_id=previous[-1].heads.get('memory')
    if not memory_id or repo.get_version(memory_id).stale:
        raise ValueError('Спершу оновіть пам’ять попередньої сцени')
    try:
        snapshot=load_memory(repo.read_text(memory_id))
        return validate_memory_journal(snapshot,selected)
    except ValueError:
        raise ValueError('Попередня пам’ять не відповідає вибраній прозі; оновіть пам’ять') from None


def memory_before(repo,scene_id: str) -> MemorySnapshot:
    """Legacy wire view; callers must not persist this in place of the journal."""
    return legacy_view(journal_before(repo,scene_id))


def save_scene_memory(repo,scene_id,text,expected_revision):
    unchanged=repo.unchanged_scene_text(scene_id,'memory',text,expected_revision)
    if unchanged:return unchanged[1]
    from ..domain import RevisionConflict
    from ..providers.models import RoleSettings, ProviderSettings
    from ..storage.snapshots import build_dependency_snapshot
    scene=repo.get_scene(scene_id)
    view=repo.context_view(scene.story_id)
    scene=view.get_scene(scene_id)
    if scene.revision!=expected_revision:
        raise RevisionConflict('Пам’ять або прозу сцени вже оновлено. Відкрийте вкладку «Пам’ять» заново; незбережені правки спершу скопіюйте окремо.')
    previous=journal_before(view,scene_id)
    prose_id=scene.heads.get('prose')
    if not prose_id:raise ValueError('Спершу виберіть прозу')
    ref=view.get_version(prose_id)
    if ref.kind not in {'manual','edited'} or not ref.complete:
        raise ValueError('Потрібна завершена вибрана проза')
    sources={id:view.read_text(id) for id in previous.source_prose_ids+[prose_id]}
    journal=normalize_manual_memory(text,previous,prose_id,sources[prose_id],scene.character_ids)
    validate_memory_journal(journal,sources,previous)
    refs=list(sources)
    earlier=[s for s in view.list_scenes(scene.story_id) if s.position<scene.position]
    if earlier:refs.append(earlier[-1].heads['memory'])
    snapshot=build_dependency_snapshot(view,scene_id,'memory',RoleSettings(provider=ProviderSettings(model='manual-memory')),refs)
    version=repo.save_version(scene.story_id,scene_id,'memory',journal.model_dump_json(),refs,dependency_snapshot=snapshot)
    repo.set_head(scene_id,'memory',version.id,expected_revision)
    return version


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
