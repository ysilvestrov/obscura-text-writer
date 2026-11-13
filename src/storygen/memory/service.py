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
    from .reuse import journal_for_read
    return journal_for_read(repo,scene_id)


def memory_before(repo,scene_id: str) -> MemorySnapshot:
    """Legacy wire view; callers must not persist this in place of the journal."""
    return legacy_view(journal_before(repo,scene_id))


class ManualMemoryContext:
    """Inputs of a manual memory save read from one context view: the scene, the journal it extends and the prose sources."""
    def __init__(self,view,scene,previous,provenance,accepted_memory_ids,prose_id,sources,tracked):
        self.view=view;self.scene=scene;self.previous=previous;self.provenance=provenance
        self.accepted_memory_ids=accepted_memory_ids;self.prose_id=prose_id;self.sources=sources;self.tracked=tracked


def manual_memory_context(repo,scene_id,expected_revision) -> ManualMemoryContext:
    from ..domain import RevisionConflict
    scene=repo.get_scene(scene_id)
    view=repo.context_view(scene.story_id)
    scene=view.get_scene(scene_id)
    if scene.revision!=expected_revision:
        raise RevisionConflict('Пам’ять або прозу сцени вже оновлено. Відкрийте вкладку «Пам’ять» заново; незбережені правки спершу скопіюйте окремо.')
    from .reuse import memory_for_manual_edit
    previous,provenance,accepted_memory_ids=memory_for_manual_edit(view,scene_id)
    prose_id=scene.heads.get('prose')
    if not prose_id:raise ValueError('Спершу виберіть прозу')
    ref=view.get_version(prose_id)
    if ref.kind not in {'manual','edited'} or not ref.complete:
        raise ValueError('Потрібна завершена вибрана проза')
    sources={id:view.read_text(id) for id in previous.source_prose_ids+[prose_id]}
    from ..storage.snapshots import core_cards
    from ..book.protagonists import scene_tracked
    story=view.get_story(scene.story_id)
    tracked=scene_tracked(story,core_cards(view,story),view.list_scenes(scene.story_id),scene)
    return ManualMemoryContext(view,scene,previous,provenance,accepted_memory_ids,prose_id,sources,tracked)


def publish_memory_journal(repo,scene_id,journal,expected_revision,context=None):
    """Validate, snapshot, save and publish a scene journal; returns (version, scene after set_head)."""
    from ..providers.models import RoleSettings, ProviderSettings
    from ..storage.snapshots import build_dependency_snapshot
    ctx=context or manual_memory_context(repo,scene_id,expected_revision)
    view,scene=ctx.view,ctx.scene
    validate_memory_journal(journal,ctx.sources,ctx.previous)
    refs=list(ctx.sources)
    from .previous import previous_memory
    before=previous_memory(view,scene)
    if before.memory_id:refs.append(before.memory_id)
    snapshot=build_dependency_snapshot(view,scene_id,'memory',RoleSettings(provider=ProviderSettings(model='manual-memory')),refs)
    snapshot.memory_provenance=ctx.provenance
    snapshot.accepted_stale_memory_ids=ctx.accepted_memory_ids
    version=repo.save_version(scene.story_id,scene_id,'memory',journal.model_dump_json(),refs,dependency_snapshot=snapshot)
    return version,repo.set_head(scene_id,'memory',version.id,expected_revision)


def save_memory_journal(repo,scene_id,journal,expected_revision,context=None):
    return publish_memory_journal(repo,scene_id,journal,expected_revision,context)[0]


def save_scene_memory(repo,scene_id,text,expected_revision):
    unchanged=repo.unchanged_scene_text(scene_id,'memory',text,expected_revision)
    if unchanged:return unchanged[1]
    ctx=manual_memory_context(repo,scene_id,expected_revision)
    journal=normalize_manual_memory(text,ctx.previous,ctx.prose_id,ctx.sources[ctx.prose_id],ctx.scene.character_ids,tracked=ctx.tracked)
    return save_memory_journal(repo,scene_id,journal,expected_revision,ctx)


def rebuild_memory(repo,from_scene_id: str,gateway_factory,cancel,on_event,settings=None,run_id=None):
    from ..authoring.blueprints import get_role_settings
    from ..generation.context import build_context
    from ..generation.stages import execute_stage
    first=repo.get_scene(from_scene_id)
    role=settings or get_role_settings(repo,first.story_id)['memory']
    attempts=[]
    for scene in repo.list_scenes(first.story_id):
        if scene.position<first.position:  # reading order: a rebuild runs every scene from here down
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
