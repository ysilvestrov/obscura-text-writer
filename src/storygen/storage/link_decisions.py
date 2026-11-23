"""VALID-LINKS-S08: the author's decision on a link of a scene, CAS on the link fingerprint."""
from ..domain import RevisionConflict, now
from .context_view import ContextView
from .link_records import LinkVerdict, ProseEquivalence, new_verdict_id, write_equivalence, write_verdict, PROSE_KINDS
from .links import link_state, scene_validity

# Z3 «keep the previous memory» also records a prose equivalence. An unavailable link (carry_failed, no memory) is a
# conflict: only a new memory of the scene clears it.
DECIDABLE = {'brief', 'prose', 'memory'}
CARRY_FAILED = 'Пам’ять сцени не перенесено на нову пам’ять попередньої сцени, і рішення автора її не залишить — створіть нову пам’ять цієї сцени'


class LinkDecisionRefused(ValueError):
    """The link cannot take this decision (422)."""


def decide_link(repo, scene_id: str, link: str, action: str, fingerprint: str) -> dict:
    if link not in DECIDABLE or action != 'approve':
        raise LinkDecisionRefused('Для цього зв’язку немає такого рішення')
    scene = repo.get_scene(scene_id)
    with repo.db.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        view = ContextView(repo, db, scene.story_id)
        state = link_state(view, scene_id, link)
        if state.reason == 'carry_failed':
            raise RevisionConflict(CARRY_FAILED)
        if state.reason == 'carry_pending':
            from ..memory.carry import CARRY_PENDING
            raise RevisionConflict(CARRY_PENDING)
        if state.status in {'missing', 'unavailable'} or state.fingerprint != fingerprint:
            raise RevisionConflict('Зв’язок сцени змінився; оновіть сторінку')
        if state.status != 'valid':
            verdict = LinkVerdict(id=new_verdict_id(), story_id=scene.story_id, scene_id=scene_id, link=link,
                                  inputs=state.inputs, fingerprint=fingerprint, source='author', outcome='valid',
                                  created_at=now())
            write_verdict(db, verdict)
            if link == 'memory':
                _record_equivalence(db, view, scene_id, verdict)
            view = ContextView(repo, db, scene.story_id)
            state = link_state(view, scene_id, link)
        return {'link': state.as_dict(), 'validity': scene_validity(view, scene_id)}


def _record_equivalence(db, view, scene_id, verdict) -> None:
    """The prose the kept memory was made from (the last source of its journal) is equivalent to the current prose."""
    from ..memory.journal import load_memory
    heads = view.scenes[scene_id].heads
    sources = load_memory(view.read_text(heads['memory'])).source_prose_ids
    old = sources[-1] if sources else None
    ref = view.versions.get(old) if old else None
    if ref is not None and ref.scene_id == scene_id and ref.kind in PROSE_KINDS and old != heads['prose']:
        write_equivalence(db, ProseEquivalence(id=new_verdict_id(), story_id=verdict.story_id, scene_id=scene_id,
                                               old_prose_id=old, new_prose_id=heads['prose'], verdict_id=verdict.id,
                                               created_at=verdict.created_at))
