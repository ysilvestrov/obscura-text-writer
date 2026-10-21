"""Finite selectors for actual semantic inputs, never SQL or executable expressions."""
from ..dependency_models import DependencySnapshot, DependencySelector, DependencyChange, FreshnessResult


def build_dependency_snapshot(view, scene_id, stage, settings, input_refs):
    story = view.get_story(view.story.id)
    scene = view.get_scene(scene_id) if scene_id else None
    scenes = view.list_scenes(story.id)
    scope = 'patches' if stage == 'edit' and settings.edit_mode == 'patches' else 'prose_edit' if stage == 'edit' else stage
    selectors = []
    order = []
    def select(kind, owner, field, value):
        selectors.append(DependencySelector(kind=kind, owner_id=owner, field=field, expected=value))
    def head(item, name):
        select('head', item.id, name, item.heads.get(name))
    if scope == 'prepare':
        for kind in ['source_plan', 'source_characters']:
            ref = view.active_source(story.id, kind)
            select('source', story.id, kind, ref.id if ref else None)
    elif scope == 'patches':
        head(scene, 'draft')
    elif scope == 'memory':
        if settings.memory_mode=='evidence_delta':
            select('scene',scene.id,'character_ids',scene.character_ids)
        prefix = [s for s in scenes if s.position <= scene.position]
        order = [s.id for s in prefix]
        select('order', scene.id, 'prefix', order)
        for item in prefix:
            head(item, 'prose')
        if len(prefix) > 1:
            head(prefix[-2], 'memory')
    else:
        order = [s.id for s in scenes]
        select('order', story.id, 'all', order)
        for field in ['style_version_id', 'canon_version_id', 'characters_version_id']:
            select('story', story.id, field, getattr(story, field))
        if not story.characters_version_id:
            ref = view.active_source(story.id, 'source_characters')
            select('source', story.id, 'source_characters', ref.id if ref else None)
        # Absence of a global preamble is meaningful too.
        ref = view.active_source(story.id, 'source_plan')
        select('source', story.id, 'source_preamble', source_preamble(view,ref))
        for field in ['title', 'target_words', 'character_ids']:
            select('scene', scene.id, field, getattr(scene, field))
        for item in scenes:
            if item.position >= scene.position:
                head(item, 'plan')
                if not item.heads.get('plan'):
                    select('scene', item.id, 'beats', item.beats)
            else:
                head(item, 'prose')
        previous = [s for s in scenes if s.position < scene.position]
        if previous:
            head(previous[-1], 'memory')
        for name in {'brief': [], 'draft': ['brief'], 'prose_edit': ['brief', 'draft'], 'author_text': []}[scope]:
            head(scene, name)
    return DependencySnapshot(scope=scope, selectors=selectors,
        refs={id: view.get_version(id).sha256 for id in dict.fromkeys(input_refs)}, ref_baselines={id: view.acceptances[id].id if id in view.acceptances else None for id in input_refs}, scene_order=order,
        accepted_stale_prose_ids=[id for id in input_refs if (scope=='memory' or view.get_version(id).stale) and view.get_version(id).kind in {'edited','manual'}] if scope != 'patches' else [])


def selector_value(view, selector):
    kind, owner, field = selector.kind, selector.owner_id, selector.field
    if kind == 'story' and owner == view.story.id and field in {'style_version_id', 'canon_version_id', 'characters_version_id'}:
        return getattr(view.get_story(owner), field)
    if kind == 'scene' and field in {'title', 'target_words', 'character_ids', 'beats'}:
        return getattr(view.get_scene(owner), field)
    if kind == 'head' and field in {'plan', 'brief', 'draft', 'prose', 'memory'}:
        return view.get_scene(owner).heads.get(field)
    if kind == 'source' and owner == view.story.id and field in {'source_plan', 'source_characters', 'source_preamble'}:
        ref = view.active_source(owner, 'source_plan' if field=='source_preamble' else field)
        return source_preamble(view,ref) if field=='source_preamble' else ref.id if ref else None
    if kind == 'order':
        scenes = view.list_scenes(view.story.id)
        if field == 'all' and owner == view.story.id:
            return [s.id for s in scenes]
        if field == 'prefix':
            scene = view.get_scene(owner)
            return [s.id for s in scenes if s.position <= scene.position]
    raise ValueError('Невідомий селектор залежностей')


def compare_snapshot(view, snapshot):
    snapshot = DependencySnapshot.model_validate(snapshot)
    changes = []
    for selector in snapshot.selectors:
        try:
            current = selector_value(view, selector)
            if current != selector.expected:
                changes.append(DependencyChange(selector=selector, expected=selector.expected, current=current, reason='selector_changed'))
        except (KeyError, ValueError):
            changes.append(DependencyChange(selector=selector, expected=selector.expected, reason='selector_unavailable'))
    for id, sha in snapshot.refs.items():
        try:
            ref = view.get_version(id)
            view.read_blob(ref.relative_path, sha)
            if ref.sha256 != sha or not ref.complete:
                raise ValueError('Пошкоджене джерело')
            source_result=view.freshness_cache.get(id)
            if source_result and any(c.reason=='dependency_cycle' for c in source_result.reasons):
                changes.append(DependencyChange(version_id=id,reason='dependency_cycle'))
            if id in view.resolving:
                changes.append(DependencyChange(version_id=id,reason='dependency_cycle'))
            actual_baseline=view.acceptances[id].id if id in view.acceptances else None
            if actual_baseline!=snapshot.ref_baselines.get(id):
                changes.append(DependencyChange(version_id=id,expected=snapshot.ref_baselines.get(id),current=actual_baseline,reason="source_baseline_changed"))
            if snapshot.scope!='author_text' and ref.stale and id not in snapshot.accepted_stale_prose_ids:
                changes.append(DependencyChange(version_id=id,reason='source_stale'))
        except (KeyError, ValueError, OSError):
            changes.append(DependencyChange(version_id=id, expected=sha, reason='source_unavailable'))
    return changes


def build_evaluation_snapshot(view, scene_id, case, mode):
    story = view.get_story(view.story.id)
    selectors = []
    def select(kind, owner, field, expected):
        selectors.append(DependencySelector(kind=kind, owner_id=owner, field=field, expected=expected))
    for field in ['canon_version_id', 'style_version_id', 'characters_version_id']:
        select('story', story.id, field, getattr(story, field))
    if not story.characters_version_id:
        ref = view.active_source(story.id, 'source_characters')
        select('source', story.id, 'source_characters', ref.id if ref else None)
    scenes = view.list_scenes(story.id)
    if mode == 'story':
        order = [s.id for s in scenes]
        select('order', story.id, 'all', order)
        targets = scenes
    else:
        scene = view.get_scene(scene_id)
        prefix = [s for s in scenes if s.position <= scene.position]
        order = [s.id for s in prefix]
        select('order', scene.id, 'prefix', order)
        targets = [scene]
        if len(prefix) > 1:
            previous = prefix[-2]
            select('head', previous.id, 'prose', previous.heads.get('prose'))
    for scene in targets:
        for name in ['plan', 'prose'] + (['brief'] if mode != 'story' else []) + (['draft'] if mode == 'edit_pair' else []):
            select('head', scene.id, name, scene.heads.get(name))
    return DependencySnapshot(scope='evaluation', selectors=selectors,
        refs={d.version: view.get_version(d.version).sha256 for d in case.documents}, ref_baselines={d.version: view.acceptances[d.version].id if d.version in view.acceptances else None for d in case.documents}, scene_order=order)


def resolve_freshness(view, version_id):
    if version_id in view.freshness_cache:
        return view.freshness_cache[version_id].model_copy(deep=True)
    if version_id in view.resolving:
        return FreshnessResult(stale=True, reasons=[DependencyChange(version_id=version_id, reason='dependency_cycle')])
    ref = view.versions.get(version_id)
    if ref is None:
        return FreshnessResult(stale=True, reasons=[DependencyChange(version_id=version_id, reason='source_missing')])
    view.resolving.add(version_id)
    try:
        reasons = []
        if not ref.complete:
            reasons.append(DependencyChange(version_id=version_id, reason='incomplete'))
        try:
            view.read_blob(ref.relative_path, ref.sha256)
        except (ValueError, OSError):
            reasons.append(DependencyChange(version_id=version_id, reason='integrity_error'))
        acceptance=view.acceptances.get(version_id)
        baseline=acceptance.baseline if acceptance else ref.dependency_snapshot
        if baseline is None:
            if ref.stale:
                reasons.append(DependencyChange(version_id=version_id, reason='legacy_stale'))
        else:
            reasons.extend(compare_snapshot(view, baseline))
        result = FreshnessResult(stale=bool(reasons), reasons=reasons, baseline_id=acceptance.id if acceptance else ref.id if baseline else None)
        view.freshness_cache[version_id] = result
        return result.model_copy(deep=True)
    finally:
        view.resolving.remove(version_id)


def source_preamble(view, ref):
    import re
    if not ref:
        return None
    text=view.read_text(ref.id)
    heading=re.search(r'(?m)^\s*(?:#{1,6}\s*)?Сцена\s+\d+[.:]',text,re.IGNORECASE)
    return ref.id if heading and text[:heading.start()].strip() else None


def build_author_baseline(view, scene_id):
    scene=view.get_scene(scene_id)
    story=view.get_story(scene.story_id)
    selectors=[]
    refs={}
    def select(kind,owner,field,value):
        selectors.append(DependencySelector(kind=kind,owner_id=owner,field=field,expected=value))
    def include(id):
        if id:refs[id]=view.get_version(id).sha256
    for field in ['style_version_id','canon_version_id','characters_version_id']:
        id=getattr(story,field)
        select('story',story.id,field,id);include(id)
    for kind in ['source_plan','source_characters']:
        ref=view.active_source(story.id,kind)
        select('source',story.id,kind,ref.id if ref else None)
        include(ref.id if ref else None)
    scenes=view.list_scenes(story.id)
    order=[s.id for s in scenes]
    select('order',story.id,'all',order)
    for item in scenes:
        select('head',item.id,'plan',item.heads.get('plan'))
        include(item.heads.get('plan'))
        if not item.heads.get('plan'):select('scene',item.id,'beats',item.beats)
    for field in ['title','target_words','character_ids']:
        select('scene',scene.id,field,getattr(scene,field))
    return DependencySnapshot(scope='author_text',selectors=selectors,refs=refs,scene_order=order,
        ref_baselines={id:view.acceptances[id].id if id in view.acceptances else None for id in refs})
