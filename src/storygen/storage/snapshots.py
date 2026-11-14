"""Finite selectors for actual semantic inputs, never SQL or executable expressions."""
from ..dependency_models import DependencySnapshot, DependencySelector, DependencyChange, FreshnessResult
from ..story_horizon import selected_plan_scenes, horizon_future_count
from ..book.lineage import previous_scenes
from ..rating.levels import effective_rating, from_wire, is_lower, to_wire

# Generation scopes limited by the scene's effective content rating; author text and memory are not.
RATING_SCOPES = frozenset({'brief', 'draft', 'prose_edit', 'patches', 'author_rewrite'})
# Scopes whose result is prose of the scene (STORY-LANGUAGE-S04): a brief and memory do not depend on the prose language.
PROSE_LANGUAGE_SCOPES = frozenset({'draft', 'prose_edit', 'patches', 'author_rewrite'})


def build_dependency_snapshot(
    view,
    scene_id: str | None,
    stage: str,
    settings,
    input_refs: list[str],
) -> DependencySnapshot:
    story = view.get_story(view.story.id)
    scene = view.get_scene(scene_id) if scene_id else None
    scenes = view.list_scenes(story.id)
    scope = (
        'patches'
        if stage == 'edit' and settings.edit_mode in {'patches', 'diff'}
        else 'prose_edit' if stage == 'edit' else 'author_rewrite' if stage=='rewrite' else stage
    )
    selectors = []
    order = []
    def select(kind, owner, field, value):
        selectors.append(DependencySelector(kind=kind, owner_id=owner, field=field, expected=value))
    def head(item, name):
        select('head', item.id, name, item.heads.get(name))
    if scope == 'prepare':
        select('story',story.id,'characters_version_id',story.characters_version_id)
        for kind in (['source_plan'] if story.characters_version_id else ['source_plan','source_characters']):
            ref = view.active_source(story.id, kind)
            select('source', story.id, kind, ref.id if ref else None)
    elif scope == 'patches':
        head(scene, 'draft')
    elif scope == 'memory':
        if settings.memory_mode=='evidence_delta':
            select('scene',scene.id,'character_ids',scene.character_ids)
            memory_core_selectors(view,story,scene,scenes,select)
        prefix = previous_scenes(story, scenes, scene) + [scene]
        order = [s.id for s in prefix]
        select('order', scene.id, 'prefix', order)
        for item in prefix:
            head(item, 'prose')
        if len(prefix) > 1:
            previous_memory_selector(view, story, scene, select, head)
    else:
        plans=selected_plan_scenes(scenes,scene,settings)
        count=horizon_future_count(settings)
        if count is None:
            order = [s.id for s in scenes]
            select('order', story.id, 'all', order)
        else:
            order=[s.id for s in previous_scenes(story,scenes,scene)]+[s.id for s in plans]
            selectors.append(
                DependencySelector(
                    kind='order',
                    owner_id=scene.id,
                    field='narrative_window',
                    expected=order,
                    future_count=count,
                )
            )
            select('story',story.id,'scene_count',len(scenes))
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
        from ..memory.forwarding import projection_policy
        select('scene',scene.id,'memory_projection_policy',projection_policy(view,scene.id))
        selected_ids={item.id for item in plans}
        previous = previous_scenes(story, scenes, scene)
        earlier_ids = {s.id for s in previous}
        for item in scenes:
            if item.id in selected_ids:
                head(item, 'plan')
                if not item.heads.get('plan'):
                    select('scene', item.id, 'beats', item.beats)
            elif item.id in earlier_ids:
                head(item, 'prose')
        if previous:
            previous_memory_selector(view, story, scene, select, head)
        for name in {'brief': [], 'draft': ['brief'], 'prose_edit': ['brief', 'draft'], 'author_text': [],'author_rewrite': []}[scope]:
            head(scene, name)
        # CONTEXT-002-S05: these stages see «ЗМІНИВСЯ ДЕНЬ», so a change of the parsed day is a change of their input.
        memory_core_selectors(view,story,scene,scenes,select)
    if scope in SERIES_SCOPES:
        from ..memory.series_start import scene_series_start
        start = scene_series_start(story, scenes, scene)
        # SERIES: written only for a first scene of a series book, so other snapshots stay byte for byte the same.
        if start:select('scene', scene.id, 'series_start', start)
    if scope in RATING_SCOPES:
        select('scene', scene.id, 'content_rating', to_wire(effective_rating(story, scene)))
    from ..memory.story_time import is_flashback
    if scope in FLASHBACK_SCOPES and is_flashback(scene):
        # STORY-TIME: written only for a flashback, so snapshots of a book without flashbacks stay byte for byte the same.
        select('scene', scene.id, 'flashback', True)
    if scope in FOREIGN_FLASHBACK_SCOPES:
        from ..memory.flashbacks import flashback_facts_value
        value=flashback_facts_value(view,story,scenes,scene)
        if value:select('scene', scene.id, 'flashback_facts', value)
    if scope in PROSE_LANGUAGE_SCOPES:
        from ..language import prose_language
        select('scene', scene.id, 'prose_language', prose_language(story, scene))
    return DependencySnapshot(
        scope=scope,
        frozen_author_source_id=next((id for id in input_refs if view.get_version(id).scene_id==scene_id and view.get_version(id).kind=='draft'),None) if scope=='author_rewrite' else None,
        selectors=selectors,
        refs={id: view.get_version(id).sha256 for id in dict.fromkeys(input_refs)},
        ref_baselines={
            id: view.acceptances[id].id if id in view.acceptances else None
            for id in input_refs
        },
        scene_order=order,
        accepted_stale_prose_ids=[
            id for id in input_refs
            if (scope == 'memory' or view.get_version(id).stale)
            and view.get_version(id).kind in {'edited', 'manual'}
        ] if scope != 'patches' else [],
    )


# STORY-TIME: the scopes whose input depends on the scene being a flashback (memory and every writing stage).
FLASHBACK_SCOPES={'memory','brief','draft','prose_edit','author_text','author_rewrite'}
# SERIES: the scopes whose input includes the start snapshot of a series book.
SERIES_SCOPES={'memory','brief','draft','prose_edit','author_rewrite'}
# STORY-TIME: the scopes whose request carries «Минуле інших арок».
FOREIGN_FLASHBACK_SCOPES={'brief','draft','prose_edit','author_rewrite'}


def core_cards(view,story):
    from ..characters.models import load_characters
    if not story.characters_version_id:return []
    ref=view.peek_version(story.characters_version_id)  # no deep copy: planning counts them
    return load_characters(view.read_blob(ref.relative_path,ref.sha256).decode('utf-8'))


def memory_core_selectors(view,story,scene,scenes,select):
    from ..book.protagonists import has_explicit_protagonists, scene_tracked
    from ..memory.story_time import comparison_scene,day_key
    tracked=scene_tracked(story,core_cards(view,story),scenes,scene)
    # BOOK-LINEAGE-S04: a book without an explicit arc protagonist keeps the story selector (same snapshots as before).
    if has_explicit_protagonists(story):select('scene',scene.id,'tracked_characters',tracked)
    else:select('story',story.id,'tracked_characters',tracked)
    owners=[scene]+[item for item in (comparison_scene(scenes,scene,hero,story) for hero in tracked) if item]
    for item in dict((item.id,item) for item in owners).values():
        select('scene',item.id,'memory_day_key',day_key(item))


def previous_memory_selector(view, story, scene, select, head):
    """The selector of the memory a scene extends: the memory head of its one head scene, or for a scene after a merge
    point story/memory_merge_heads of its key (MEMORY-MERGE). Returns the version id (or None)."""
    from ..memory.previous import previous_memory
    before = previous_memory(view, scene, require=False)
    if before.merge_key:
        select('story', story.id, 'memory_merge_heads', {before.merge_key: before.memory_id or ''})
    elif before.ancestors:
        head(before.ancestors[-1], 'memory')
    return before.memory_id


def selector_value(view, selector: DependencySelector):
    kind, owner, field = selector.kind, selector.owner_id, selector.field
    if kind=='scene' and field=='memory_day_key':
        from ..memory.story_time import day_key
        return day_key(view.peek_scene(owner))
    if kind=='story' and owner==view.story.id and field=='tracked_characters':
        from ..memory.core import tracked_characters
        return tracked_characters(core_cards(view,view.peek_story(owner)),view.peek_scenes(owner))
    if kind=='scene' and field=='tracked_characters':
        from ..book.protagonists import scene_tracked
        scene=view.peek_scene(owner)
        story=view.peek_story(scene.story_id)
        return scene_tracked(story,core_cards(view,story),view.peek_scenes(story.id),scene)
    if kind=='scene' and field=='memory_projection_policy':
        from ..memory.forwarding import projection_policy
        return projection_policy(view,owner)
    if kind=='story' and owner==view.story.id and field in {'timeline_summary_heads','memory_merge_heads'}:
        heads=getattr(view.peek_story(owner),field)
        return {key:heads.get(key,'') for key in sorted(selector.expected or {})}
    if kind=='scene' and field=='memory_kind_overrides':
        from ..memory.kinds import kind_overrides
        return kind_overrides(view,owner)
    if kind=='scene' and field=='flashback':
        from ..memory.story_time import is_flashback
        return is_flashback(view.peek_scene(owner))
    if kind=='scene' and field=='flashback_facts':
        from ..memory.flashbacks import flashback_facts_value
        return flashback_facts_value(view,view.peek_story(view.story.id),view.peek_scenes(view.story.id),view.peek_scene(owner))
    if kind=='scene' and field=='series_start':
        from ..memory.series_start import scene_series_start
        return scene_series_start(view.peek_story(view.story.id), view.peek_scenes(view.story.id), view.peek_scene(owner))
    if kind=='scene' and field=='prose_language':
        from ..language import prose_language
        return prose_language(view.peek_story(view.story.id), view.peek_scene(owner))
    if kind=='scene' and field=='content_rating':
        return to_wire(effective_rating(view.peek_story(view.story.id), view.peek_scene(owner)))
    if kind == 'story' and owner == view.story.id and field in {
        'style_version_id',
        'canon_version_id',
        'characters_version_id'
    }:
        return getattr(view.peek_story(owner), field)
    if kind=='story' and owner==view.story.id and field=='scene_count':
        return len(view.peek_scenes(owner))
    if kind == 'scene' and field in {'title', 'target_words', 'character_ids', 'beats'}:
        value = getattr(view.peek_scene(owner), field)
        # A new list: DependencyChange.current must never alias the view's scene.
        return list(value) if isinstance(value, list) else value
    if kind == 'head' and field in {'plan', 'brief', 'draft', 'prose', 'memory'}:
        return view.peek_scene(owner).heads.get(field)
    if kind == 'source' and owner == view.story.id and field in {'source_plan', 'source_characters', 'source_preamble'}:
        ref = view.active_source(owner, 'source_plan' if field=='source_preamble' else field)
        return source_preamble(view,ref) if field=='source_preamble' else ref.id if ref else None
    if kind == 'order':
        scenes = view.peek_scenes(view.story.id)
        if field == 'all' and owner == view.story.id:
            return [s.id for s in scenes]
        if field == 'prefix':
            scene = view.peek_scene(owner)
            return [s.id for s in previous_scenes(view.peek_story(view.story.id), scenes, scene)] + [scene.id]
        if field=='narrative_window':
            scene=view.peek_scene(owner)
            future=[s for s in scenes if s.position>=scene.position][:selector.future_count+1]
            return [s.id for s in previous_scenes(view.peek_story(view.story.id), scenes, scene)]+[s.id for s in future]
    raise ValueError('Невідомий селектор залежностей')


def rating_fallback(view, snapshot: DependencySnapshot) -> tuple[bool, DependencySelector | None]:
    """Whether the snapshot's rating input comes from the story's initial rating, and that baseline selector.

    Old snapshots predate the rating, and a recorded None means the story was not rated yet: either way the story's
    first rating is their baseline, so setting it stales nothing. (True, None) means the snapshot's own rating
    selectors are dropped and no baseline exists yet (story not rated, or no owner to attach it to).
    """
    rating=[s for s in snapshot.selectors if s.field=='content_rating']
    if snapshot.scope not in RATING_SCOPES or any(s.expected is not None for s in rating):return False,None
    initial=view.peek_story(view.story.id).initial_content_rating
    owner_field=('head','draft') if snapshot.scope=='patches' else ('scene','title')
    owner=rating[0].owner_id if rating else next((s.owner_id for s in snapshot.selectors if (s.kind,s.field)==owner_field),None)
    if not owner or initial is None:return True,None
    return True,DependencySelector(kind='scene',owner_id=owner,field='content_rating',expected=to_wire(initial))


def legacy_selectors(snapshot: DependencySnapshot, selectors: list) -> list:
    """Implicit selectors of snapshots recorded before a selector existed (STORY-LANGUAGE-S04 for prose language)."""
    selectors=list(selectors)
    if snapshot.scope in PROSE_LANGUAGE_SCOPES and not any(s.field=='prose_language' for s in selectors):
        # Snapshots from before #32 were all built for Ukrainian prose; patches record only the scene's draft head.
        owner=next((s.owner_id for s in selectors if s.kind=='scene' and s.field=='title'),None) or next(
            (s.owner_id for s in selectors if s.kind=='head' and s.field=='draft'),None)
        if owner:selectors.append(DependencySelector(kind='scene',owner_id=owner,field='prose_language',expected='uk'))
    return selectors


def snapshot_scene(selectors: list) -> str | None:
    """The scene a snapshot was built for: the owner of scene/title or of the order prefix/narrative_window selector."""
    return next((s.owner_id for s in selectors if s.kind=='scene' and s.field=='title'),None) or next(
        (s.owner_id for s in selectors if s.kind=='order' and s.field in {'prefix','narrative_window'}),None)


def current_value(view, selector: DependencySelector, owner_scene: str | None):
    """BOOK-LINEAGE-S04: the story tracked-characters selector compares with the tracked characters of the snapshot's
    own scene, so a protagonist given to a later arc stales only that arc's written scenes. The stored selector stays
    as it is (a book without explicit protagonists gets the same value and the same report as before)."""
    if selector.kind=='story' and selector.field=='tracked_characters' and owner_scene and owner_scene in getattr(view,'scenes',()):
        return selector_value(view,DependencySelector(kind='scene',owner_id=owner_scene,field='tracked_characters',expected=None))
    return selector_value(view,selector)


def language_only(result) -> bool:
    """Stale only because the scene now wants prose in another language: its facts did not change."""
    return bool(result.reasons) and all(r.reason=='selector_changed' and r.selector is not None
        and r.selector.field=='prose_language' for r in result.reasons)


def compare_snapshot(view, snapshot: DependencySnapshot | dict) -> list[DependencyChange]:
    snapshot = DependencySnapshot.model_validate(snapshot)
    changes = []
    selectors=list(snapshot.selectors)
    if snapshot.scope in {'brief','draft','prose_edit','author_text','author_rewrite'} and not any(s.field=='memory_projection_policy' for s in selectors):
        owner=next((s.owner_id for s in selectors if s.kind=='scene' and s.field=='title'),None)
        if owner:selectors.append(DependencySelector(kind='scene',owner_id=owner,field='memory_projection_policy',expected=[]))
    if snapshot.scope in FLASHBACK_SCOPES and not any(s.field=='flashback' for s in selectors):
        # STORY-TIME-S06: a missing flashback selector means «not a flashback»; a flag set later stales the version.
        owner=snapshot_scene(selectors)
        if owner:selectors.append(DependencySelector(kind='scene',owner_id=owner,field='flashback',expected=False))
    if snapshot.scope in FOREIGN_FLASHBACK_SCOPES and not any(s.field=='flashback_facts' for s in selectors):
        # STORY-TIME-S06: a missing selector means no visible foreign flashback; a new one stales the version.
        owner=snapshot_scene(selectors)
        if owner:selectors.append(DependencySelector(kind='scene',owner_id=owner,field='flashback_facts',expected=[]))
    if snapshot.scope in SERIES_SCOPES and not any(s.field=='series_start' for s in selectors):
        # SERIES: a missing selector means «no start snapshot»; one taken later stales a first scene's version.
        owner=snapshot_scene(selectors)
        if owner:selectors.append(DependencySelector(kind='scene',owner_id=owner,field='series_start',expected=None))
    selectors=legacy_selectors(snapshot,selectors)
    replace,fallback=rating_fallback(view,snapshot)
    if replace:
        selectors=[s for s in selectors if s.field!='content_rating']+([fallback] if fallback else [])
    owner_scene=snapshot_scene(selectors)
    for selector in selectors:
        try:
            current = current_value(view, selector, owner_scene)
            if selector.field=='content_rating':
                # Asymmetric: only a rating lower than expected on some axis changes the input.
                changed=is_lower(from_wire(current),from_wire(selector.expected))
            else:
                changed=current != selector.expected
            if changed:
                changes.append(DependencyChange(selector=selector, expected=selector.expected, current=current, reason='selector_changed'))
        except (KeyError, ValueError):
            changes.append(DependencyChange(selector=selector, expected=selector.expected, reason='selector_unavailable'))
    for id, sha in snapshot.refs.items():
        try:
            ref = view.peek_version(id)
            # Evaluated here, as get_version did, so freshness_cache holds id before the cycle check below.
            stale = view.is_stale(id)
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
            approved_memory=(snapshot.scope=='memory' and ref.kind=='memory'
                             and id in snapshot.accepted_stale_memory_ids
                             and any(p.memory_id==id for p in snapshot.memory_provenance))
            frozen=(snapshot.scope=='author_rewrite' and id==snapshot.frozen_author_source_id and ref.kind=='draft'
                    and ref.story_id==view.story.id and any(s.kind=='scene' and s.owner_id==ref.scene_id and s.field=='title' for s in snapshot.selectors))
            if snapshot.scope=='author_rewrite' and id==snapshot.frozen_author_source_id and not frozen:
                raise ValueError('Невідповідне історичне джерело')
            if stale and language_only(view.freshness_cache.get(id) or freshness(view,id)):
                # STORY-LANGUAGE-S03: the source's facts are unchanged; only its own scene must be rewritten.
                stale=False
            if snapshot.scope!='author_text' and not frozen and stale and id not in snapshot.accepted_stale_prose_ids and not approved_memory:
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
        prefix = [s for s in scenes if s.position <= scene.position]  # reading order (evaluation; BOOK-LINEAGE exception)
        order = [s.id for s in prefix]
        select('order', scene.id, 'prefix', order)
        targets = [scene]
        if len(prefix) > 1:
            previous = prefix[-2]
            select('head', previous.id, 'prose', previous.heads.get('prose'))
    for scene in targets:
        select('scene',scene.id,'character_ids',scene.character_ids)
        for name in (
            ['plan', 'prose']
            + (['brief'] if mode != 'story' else [])
            + (['draft'] if mode == 'edit_pair' else [])
        ):
            select('head', scene.id, name, scene.heads.get(name))
    return DependencySnapshot(
        scope='evaluation',
        selectors=selectors,
        refs={d.version: view.get_version(d.version).sha256 for d in case.documents},
        ref_baselines={
            d.version: view.acceptances[d.version].id if d.version in view.acceptances else None
            for d in case.documents
        },
        scene_order=order,
    )


def resolve_freshness(view, version_id: str) -> FreshnessResult:
    return freshness(view, version_id).model_copy(deep=True)


def freshness(view, version_id: str) -> FreshnessResult:
    """Внутрішнє читання без копії: спільний об'єкт freshness_cache; не змінювати результат."""
    if version_id in view.freshness_cache:
        return view.freshness_cache[version_id]
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
            if ref.scene_id and ref.kind in {'brief','draft','edited','manual'}:
                from ..memory.forwarding import projection_policy
                hidden=projection_policy(view,ref.scene_id)
                expected=ref.manual_projection_policy if ref.manual_projection_policy is not None else []
                if hidden!=expected:reasons.append(DependencyChange(selector=DependencySelector(kind='scene',owner_id=ref.scene_id,field='memory_projection_policy',expected=expected),expected=expected,current=hidden,reason='selector_changed'))
        else:
            reasons.extend(compare_snapshot(view, baseline))
        # A review adds live dependencies even when the original version was fresh.
        # A later explicit author rebase supersedes that review, retaining its own contract.
        from ..review.store import latest as latest_review,current_acceptance
        reviewed=latest_review(view,version_id)
        review_applies=reviewed and (not acceptance or reviewed.target.baseline_ids.get(version_id)==acceptance.id)
        if not any(r.reason in {'incomplete','integrity_error'} for r in reasons):
            if review_applies:
                if current_acceptance(view,version_id):reasons=[]
                else:reasons.append(DependencyChange(version_id=version_id,reason='review_basis_changed'))
            elif reasons:
                from .impact_validity import valid_overlay
                if valid_overlay(view,version_id):reasons=[]
        from .review_authority import revision
        material='brief' if ref.kind=='brief' else 'prose' if ref.kind in {'edited','manual'} else None
        if material and ref.scene_id and revision(view,ref.scene_id,material):
            current=current_acceptance(view,version_id)
            if not current or getattr(current,'authority_revision',0)!=revision(view,ref.scene_id,material):
                reasons.append(DependencyChange(version_id=version_id,reason='review_basis_changed'))
        result = FreshnessResult(
            stale=bool(reasons),
            reasons=reasons,
            baseline_id=acceptance.id if acceptance else ref.id if baseline else None
        )
        view.freshness_cache[version_id] = result
        return result
    finally:
        view.resolving.remove(version_id)


def source_preamble(view, ref):
    from ..plan_sections import split_plan
    if not ref:return None
    key=(ref.id,ref.sha256)
    if key not in view.preamble_cache:
        view.preamble_cache[key]=ref.id if split_plan(view.read_text(ref.id))[0].strip() else None
    return view.preamble_cache[key]


def build_author_baseline(view, scene_id: str) -> DependencySnapshot:
    scene=view.get_scene(scene_id)
    story=view.get_story(scene.story_id)
    selectors=[]
    refs={}
    def select(kind,owner,field,value):
        selectors.append(DependencySelector(kind=kind,owner_id=owner,field=field,expected=value))
    def include(id):
        if id:
            refs[id]=view.get_version(id).sha256
    for field in ['style_version_id','canon_version_id','characters_version_id']:
        id=getattr(story,field)
        select('story',story.id,field,id)
        include(id)
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
        if not item.heads.get('plan'):
            select('scene',item.id,'beats',item.beats)
    for field in ['title','target_words','character_ids']:
        select('scene',scene.id,field,getattr(scene,field))
    from ..memory.forwarding import projection_policy
    select('scene',scene.id,'memory_projection_policy',projection_policy(view,scene.id))
    previous=previous_scenes(story,scenes,scene)
    for item in previous:
        id=item.heads.get('prose');select('head',item.id,'prose',id);include(id)
    if previous:
        include(previous_memory_selector(view,story,scene,select,lambda item,name:select('head',item.id,name,item.heads.get(name))))
    return DependencySnapshot(scope='author_text',selectors=selectors,refs=refs,scene_order=order,
        ref_baselines={id:view.acceptances[id].id if id in view.acceptances else None for id in refs})
