from ..domain import Scene, VersionRef


def invalidate_dependents(repo,changed_version_ids: list[str]) -> list[str]:
    return repo.invalidate_dependents(changed_version_ids)


def select_prose(repo,scene_id: str,version_id: str,expected_revision: int) -> Scene:
    return repo.set_head(scene_id,'prose',version_id,expected_revision)


def save_manual_prose(repo,scene_id: str,text: str,expected_revision: int,content_format=None) -> VersionRef:
    if not text.strip():
        raise ValueError('Проза не може бути порожньою')
    unchanged=repo.unchanged_scene_text(scene_id,'prose',text,expected_revision,content_format)
    if unchanged:return unchanged[1]
    scene=repo.get_scene(scene_id)
    content_format=_author_format(repo,scene,'prose',content_format)
    from ..memory.forwarding import projection_policy
    policy=projection_policy(repo.context_view(scene.story_id),scene.id)
    snapshot=_manual_snapshot(repo,scene,'prose')
    ref=repo.save_version(scene.story_id,scene.id,'manual',text,list(snapshot.refs),dependency_snapshot=snapshot,manual_projection_policy=policy,content_format=content_format,author_lineage=_lineage(scene,'prose'))
    repo.set_head(scene.id,'prose',ref.id,expected_revision)
    return ref


def writing_fingerprint(repo,scene) -> str:
    """MCP-BRIDGE: SHA-256 of what a draft written outside Obscura rests on: the author-text snapshot of `draft` plus the brief head."""
    import hashlib,json
    payload={'snapshot':_manual_snapshot(repo,scene,'draft').model_dump(mode='json'),'brief':scene.heads.get('brief')}
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()


CONTEXT_CHANGED='Контекст сцени змінився — прочитайте його знову'


def save_manual_draft(repo,scene_id: str,text: str,expected_revision: int,content_format=None,*,author_lineage=None,ghost_rewrite=None,external_origin=None,expected_context_fingerprint=None) -> VersionRef:
    """`author_lineage` overrides the previous draft head as the parent; a Ghost Mode save always creates a version (#55).

    MCP-BRIDGE: a draft with `external_origin` must name the context fingerprint it was written from and always creates a version."""
    if not text.strip():
        raise ValueError('Чернетка не може бути порожньою')
    if external_origin is not None and expected_context_fingerprint is None:
        raise ValueError('Чернетка із зовнішнього клієнта потребує відбитка контексту')
    if expected_context_fingerprint is not None:
        from ..domain import RevisionConflict
        current=repo.get_scene(scene_id)
        if current.revision!=expected_revision:raise RevisionConflict('Сцену вже змінено')
        if writing_fingerprint(repo,current)!=expected_context_fingerprint:raise RevisionConflict(CONTEXT_CHANGED)
    if ghost_rewrite is None and external_origin is None:
        unchanged=repo.unchanged_scene_text(scene_id,'draft',text,expected_revision,content_format)
        if unchanged:return unchanged[1]
    scene=repo.get_scene(scene_id)
    content_format=_author_format(repo,scene,'draft',content_format)
    from ..memory.forwarding import projection_policy
    policy=projection_policy(repo.context_view(scene.story_id),scene.id)
    snapshot=_manual_snapshot(repo,scene,'draft')
    ref=repo.save_version(scene.story_id,scene.id,'draft',text,list(snapshot.refs),dependency_snapshot=snapshot,manual_projection_policy=policy,content_format=content_format,author_lineage=author_lineage or _lineage(scene,'draft'),ghost_rewrite=ghost_rewrite,external_origin=external_origin)
    repo.set_head(scene.id,'draft',ref.id,expected_revision)
    return ref


def _lineage(scene,head):
    """The current head of the same material: the version this manual save was made from (metadata only, #44)."""
    from ..domain import AuthorLineage
    parent=scene.heads.get(head)
    return AuthorLineage(parent_version_id=parent) if parent else None


def _author_format(repo,scene,head,requested):
    """Old clients preserve the selected material's explicit interpretation."""
    if requested is not None:return requested
    current=scene.heads.get(head)
    return repo.get_version(current).content_format if current else 'plain'


def _manual_snapshot(repo,scene,head):
    from ..dependency_models import DependencySelector,DependencySnapshot
    view=repo.context_view(scene.story_id);story=view.story
    previous=[s for s in view.list_scenes(scene.story_id) if s.position<scene.position]
    selectors=[];refs={};baselines={}
    def select(kind,owner,field,value):
        selectors.append(DependencySelector(kind=kind,owner_id=owner,field=field,expected=value))
    def source(id):
        if id:
            refs[id]=view.versions[id].sha256
            baselines[id]=view.acceptances[id].id if id in view.acceptances else None
    for field in ['canon_version_id','style_version_id','characters_version_id']:
        id=getattr(story,field);select('story',story.id,field,id);source(id)
    for field in ['title','target_words','character_ids']:
        select('scene',scene.id,field,getattr(scene,field))
    select('order',scene.id,'prefix',[s.id for s in previous]+[scene.id])
    select('head',scene.id,'plan',scene.heads.get('plan'));source(scene.heads.get('plan'))
    if not scene.heads.get('plan'):select('scene',scene.id,'beats',scene.beats)
    from ..memory.forwarding import projection_policy
    select('scene',scene.id,'memory_projection_policy',projection_policy(view,scene.id))
    bindings=[(s,'prose') for s in previous]
    if previous:bindings.append((previous[-1],'memory'))
    for item,name in bindings:
        id=item.heads.get(name);select('head',item.id,name,id);source(id)
    return DependencySnapshot(scope='author_text',selectors=selectors,refs=refs,ref_baselines=baselines,scene_order=[s.id for s in previous]+[scene.id])
