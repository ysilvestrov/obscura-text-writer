"""VALID-LINKS: the three links of a scene and whether each one holds.

Z1 «previous memory + plan → brief», Z2 «brief + previous memory → prose», Z3 «prose → memory». A link holds by
construction (the lower component was made by a model from the current upper ones), by a verdict of the auditor or by
the author's decision for the current fingerprint. Pure reads of the view: no freshness, no stale flags, so the
freshness of a head may be computed from here without recursion."""
import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal
from .context_view import memo
from .link_records import LINKS, LinkName

Status = Literal['valid', 'unchecked', 'discrepancy', 'unavailable', 'missing']
MAX_CHAIN = 50
EDIT_SCOPES = {'prose_edit', 'patches'}


@dataclass(frozen=True)
class LinkState:
    link: LinkName
    status: Status
    source: Literal['construction', 'auditor', 'author'] | None = None
    reason: str | None = None
    inputs: dict = field(default_factory=dict)
    fingerprint: str | None = None

    def as_dict(self):
        return {'status': self.status, 'source': self.source, 'reason': self.reason, 'fingerprint': self.fingerprint}


def own_events(journal):
    """The events whose source is the scene's own prose: the last source of the journal."""
    if not journal.source_prose_ids:
        return []
    own = journal.source_prose_ids[-1]
    return [event for event in journal.events if event.source_version_id == own]


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def memory_digest(view, memory_id: str) -> str:
    """Identity of a scene memory as a component: its own events with every field that shapes the projection, without
    the ids of prose and evidence versions (event_id is derived from them)."""
    def build():
        from ..memory.journal import load_memory
        try:
            journal = memo(view, ('memory', memory_id, 'scene'), lambda: load_memory(view.read_text(memory_id)))
        except (ValueError, KeyError, OSError):
            return 'unreadable:' + memory_id
        return _digest([event.model_dump(mode='json', exclude={'event_id', 'source_version_id', 'evidence_version_id'})
                        for event in own_events(journal)])
    return memo(view, ('link_digest', memory_id), build)


def p0_identity(view, memory_id: str | None) -> str | None:
    if memory_id is None:
        return None
    ref = view.versions.get(memory_id)
    if ref is None:
        return 'missing:' + memory_id
    if ref.kind == 'memory':
        return memory_digest(view, memory_id)
    if ref.kind == 'memory_merge':
        return 'merge:' + memory_id
    return 'series:' + memory_id


def model_made(ref) -> bool:
    """An Obscura stage (run id) or text from an external client (external origin): a chat stage result, or a chat
    draft saved through MCP save_draft against the writing-context fingerprint. The author's own texts and Ghost Mode
    carry neither."""
    if ref is None:
        return False
    snapshot = ref.dependency_snapshot
    return ref.source_run_id is not None or (
        ref.external_origin is not None and snapshot is not None and snapshot.scope != 'author_rewrite')


def _selector(snapshot, kind, owner, field_name):
    for selector in snapshot.selectors:
        if selector.kind == kind and selector.owner_id == owner and selector.field == field_name:
            return selector
    return None


def _recorded_p0(snapshot, story, scene, before):
    """The previous memory a snapshot was made from: the inverse of snapshots.previous_memory_selector, and for a first
    scene the series start it recorded (scene/series_start), so leaving or joining a series changes it."""
    if before.merge_key:
        selector = _selector(snapshot, 'story', story.id, 'memory_merge_heads')
        value = (selector.expected or {}).get(before.merge_key) if selector and isinstance(selector.expected, dict) else None
        return value or None
    if before.ancestors:
        selector = _selector(snapshot, 'head', before.ancestors[-1].id, 'memory')
        return selector.expected if selector else None
    series = _selector(snapshot, 'scene', scene.id, 'series_start')
    if series is not None and isinstance(series.expected, str) and series.expected:
        return series.expected
    if before.series_start and before.memory_id in snapshot.refs:
        return before.memory_id
    return None


def _same_p0(view, snapshot, story, scene, before, current_p0):
    return p0_identity(view, _recorded_p0(snapshot, story, scene, before)) == current_p0


def _plan_matches(snapshot, scene):
    plan = scene.heads.get('plan')
    if plan:
        selector = _selector(snapshot, 'head', scene.id, 'plan')
        return selector is not None and selector.expected == plan
    selector = _selector(snapshot, 'scene', scene.id, 'beats')
    return selector is not None and selector.expected == scene.beats


def _brief_by_construction(view, scene, story, before, p0):
    ref = view.versions.get(scene.heads['brief'])
    snapshot = ref.dependency_snapshot if ref else None
    return bool(model_made(ref) and snapshot and snapshot.scope == 'brief'
                and _plan_matches(snapshot, scene) and _same_p0(view, snapshot, story, scene, before, p0))


def _prose_by_construction(view, scene, story, before, p0):
    ref = view.versions.get(scene.heads['prose'])
    if ref is None or ref.kind != 'edited':
        return False
    for _ in range(MAX_CHAIN):
        snapshot = ref.dependency_snapshot if ref else None
        if not model_made(ref) or snapshot is None:
            return False
        # The writer's draft: a draft stage, or a chat draft (author_text scope with an external origin and head/brief).
        if snapshot.scope == 'draft' or (snapshot.scope == 'author_text' and ref.kind == 'draft' and ref.external_origin):
            brief = _selector(snapshot, 'head', scene.id, 'brief')
            return (brief is not None and brief.expected == scene.heads['brief']
                    and _same_p0(view, snapshot, story, scene, before, p0))
        if snapshot.scope not in EDIT_SCOPES:
            return False
        draft = _selector(snapshot, 'head', scene.id, 'draft')
        if draft is None or not draft.expected:
            return False
        ref = view.versions.get(draft.expected)
    return False


def _memory_by_construction(view, scene):
    ref = view.versions.get(scene.heads['memory'])
    snapshot = ref.dependency_snapshot if ref else None
    if snapshot is None or snapshot.scope != 'memory':
        return False
    prose = _selector(snapshot, 'head', scene.id, 'prose')
    return prose is not None and prose.expected == scene.heads['prose']


def _from_verdicts(view, scene_id, link, fingerprint, inputs):
    verdict = view.link_verdicts.get((scene_id, link, fingerprint))
    if verdict is None:
        return LinkState(link, 'unchecked', inputs=inputs, fingerprint=fingerprint)
    if verdict.outcome == 'valid':
        return LinkState(link, 'valid', verdict.source, inputs=inputs, fingerprint=fingerprint)
    return LinkState(link, verdict.outcome, verdict.source, verdict.reason, inputs, fingerprint)


def _compute(view, scene_id):
    from ..memory.previous import previous_memory
    scene = view.scenes.get(scene_id)
    if scene is None or getattr(scene, 'trashed_at', None) or view.story is None or scene.story_id != view.story.id:
        return {link: LinkState(link, 'missing') for link in LINKS}
    story = view.story
    heads = scene.heads
    before = previous_memory(view, scene, peek=True, require=False)
    p0_required = bool(before.ancestors) or before.merge_key is not None or before.series_start
    p0 = p0_identity(view, before.memory_id)
    states = {}

    def build(link, present, inputs, construction):
        if not present:
            return LinkState(link, 'missing')
        fingerprint = _digest([link] + [inputs[key] for key in inputs])
        if link in {'brief', 'prose'} and p0_required and before.memory_id is None:
            return LinkState(link, 'unavailable', None, 'no_previous_memory', inputs, fingerprint)
        if construction():
            return LinkState(link, 'valid', 'construction', inputs=inputs, fingerprint=fingerprint)
        return _from_verdicts(view, scene_id, link, fingerprint, inputs)

    states['brief'] = build('brief', bool(heads.get('brief')),
                            {'plan': heads.get('plan'), 'p0': p0, 'brief': heads.get('brief')},
                            lambda: _brief_by_construction(view, scene, story, before, p0))
    states['prose'] = build('prose', bool(heads.get('brief') and heads.get('prose')),
                            {'brief': heads.get('brief'), 'p0': p0, 'prose': heads.get('prose')},
                            lambda: _prose_by_construction(view, scene, story, before, p0))
    if heads.get('prose') and not heads.get('memory'):
        states['memory'] = LinkState('memory', 'unavailable', None, 'no_memory')
    else:
        memory = heads.get('memory')
        states['memory'] = build('memory', bool(heads.get('prose') and memory),
                                 {'prose': heads.get('prose'), 'memory': memory and memory_digest(view, memory)},
                                 lambda: _memory_by_construction(view, scene))
    return states


def scene_links(view, scene_id: str) -> dict:
    """{link: LinkState} for the scene; a new dict over shared, frozen states."""
    return dict(memo(view, ('links', scene_id), lambda: _compute(view, scene_id)))


def link_state(view, scene_id: str, link: LinkName) -> LinkState:
    return scene_links(view, scene_id)[link]


def scene_validity(view, scene_id: str) -> Literal['valid', 'unchecked', 'discrepancy', 'incomplete']:
    heads = view.scenes[scene_id].heads if scene_id in view.scenes else {}
    if not heads.get('brief') or not heads.get('prose'):
        return 'incomplete'
    states = [state for state in scene_links(view, scene_id).values() if state.status != 'missing']
    if any(state.status == 'discrepancy' for state in states):
        return 'discrepancy'
    return 'valid' if all(state.status == 'valid' for state in states) else 'unchecked'
